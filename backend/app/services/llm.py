"""Optional LLM providers (Gemini with the user's own key, or a local Ollama server).
The built-in provider needs nothing and is handled by analyze.py's heuristics."""
import json
import logging
import re
from typing import Optional

import httpx

from . import settings_store

log = logging.getLogger("llm")
GEMINI = "https://generativelanguage.googleapis.com/v1beta"


class LLMError(RuntimeError):
    pass


def _gemini_headers() -> dict:
    key = settings_store.get_secret()
    if not key:
        raise LLMError("No Gemini API key is configured. Add one in AI Settings.")
    return {"x-goog-api-key": key, "Content-Type": "application/json"}  # header, never URL: keeps it out of logs


def gemini_models() -> list:
    try:
        r = httpx.get(f"{GEMINI}/models", params={"pageSize": 200}, headers=_gemini_headers(), timeout=20)
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the Gemini API: {e.__class__.__name__}")
    _check(r)
    out = []
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            out.append({"id": m["name"].split("/", 1)[1], "name": m.get("displayName", m["name"]),
                        "description": (m.get("description") or "")[:160]})
    return out


def _check(r: httpx.Response) -> None:
    if r.status_code == 200:
        return
    try:
        msg = r.json().get("error", {}).get("message", r.text)
    except ValueError:
        msg = r.text
    if r.status_code in (400, 401, 403) and "API key" in msg:
        raise LLMError("Gemini rejected the API key. Check that it is correct and enabled.")
    if r.status_code == 429:
        raise LLMError("Gemini rate limit or free-tier quota reached. Wait a bit, pick another model, or continue with the built-in analyzer.")
    raise LLMError(f"Gemini error {r.status_code}: {msg[:300]}")


def ollama_models(host: str) -> list:
    try:
        r = httpx.get(host.rstrip("/") + "/api/tags", timeout=5)
        r.raise_for_status()
    except httpx.HTTPError:
        raise LLMError(f"No local model server found at {host}. Install Ollama (ollama.com), start it, and pull a model, e.g. `ollama pull llama3.2`.")
    return [{"id": m["name"], "name": m["name"], "description": f"{m.get('size', 0) / 1e9:.1f} GB"} for m in r.json().get("models", [])]


def active_provider() -> Optional[str]:
    s = settings_store.load()["ai"]
    p = s["provider"]
    if p == "gemini" and s["gemini"]["api_key"] and s["gemini"]["model"]:
        return "gemini"
    if p == "local" and s["local"]["model"]:
        return "local"
    return None


def generate_json(prompt: str, system: str = "") -> dict:
    """Ask the configured provider for a JSON object. Raises LLMError on any failure."""
    s = settings_store.load()["ai"]
    prov = active_provider()
    if prov == "gemini":
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            r = httpx.post(f"{GEMINI}/models/{s['gemini']['model']}:generateContent", json=body, headers=_gemini_headers(), timeout=120)
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach the Gemini API: {e.__class__.__name__}")
        _check(r)
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise LLMError("Gemini returned no usable answer (possibly blocked by its safety filters).")
    elif prov == "local":
        body = {"model": s["local"]["model"], "stream": False, "format": "json",
                "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.4}}
        try:
            r = httpx.post(s["local"]["host"].rstrip("/") + "/api/chat", json=body, timeout=600)
            r.raise_for_status()
            text = r.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LLMError(f"Local model request failed: {e.__class__.__name__}")
    else:
        raise LLMError("No AI provider configured.")
    return parse_json(text)


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        data = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}|\[.*\]", text, re.S)
        if not m:
            raise LLMError("The AI response was not valid JSON.")
        try:
            data = json.loads(m.group(0))
        except ValueError:
            raise LLMError("The AI response was not valid JSON.")
    return data if isinstance(data, dict) else {"items": data}
