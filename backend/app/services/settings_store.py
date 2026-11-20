from __future__ import annotations
"""User settings persisted in data/settings.json (chmod 600). API keys never leave this module
except through get_secret(); public views are masked."""
import copy
import json
import os
import threading

from ..config import SETTINGS_PATH

_lock = threading.Lock()

CAPTION_DEFAULT = {"preset": "hormozi"}

DEFAULTS = {
    "ai": {
        "provider": "builtin",  # builtin | gemini | local
        "gemini": {"api_key": "", "model": ""},
        "local": {"host": "http://localhost:11434", "model": ""},
    },
    "transcription": {"model": "small", "language": "auto", "engine": "auto"},
    "video": {
        "format": "9:16",
        "layout": "smart",
        "facecam": {"share": 0.4, "content": "fit", "hide": True, "caption": "face"},
        "export": {"resolution": 1080, "fps": 30, "codec": "h264", "quality": "high"},
        "enhance": {
            "stabilize": False, "brightness": 0.0, "contrast": 1.0, "saturation": 1.0, "sharpness": 0.0,
            "normalize_audio": True, "denoise_audio": False, "fade_in": 0.0, "fade_out": 0.0,
            "zoom": "none",
        },
        "hook": {"enabled": False, "text": "", "duration": 2.5, "style": "pop"},
        "ending": {"enabled": False, "text": "", "duration": 2.5},
        "brand": {"id": "", "logo": True, "intro": True, "outro": True},
        "tighten": {"enabled": False, "silence": True, "silence_max": 0.7, "keep": 0.2, "fillers": True, "filler_words": "um, umm, uh, uhh, uhm, er, erm, ah, hmm, hm, mm, mmm", "manual": []},
    },
    "caption": {"preset": "hormozi"},
    "brands": [],
    "brand_default": "",
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    with _lock:
        try:
            raw = json.loads(SETTINGS_PATH.read_text())
        except (OSError, ValueError):
            raw = {}
    return _merge(DEFAULTS, raw)


def save(settings: dict) -> None:
    with _lock:
        tmp = SETTINGS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(settings, indent=2))
        os.chmod(tmp, 0o600)
        tmp.replace(SETTINGS_PATH)


def patch(partial: dict) -> dict:
    cur = load()
    # Secrets can only be changed through the dedicated key endpoints.
    partial = copy.deepcopy(partial)
    partial.get("ai", {}).get("gemini", {}).pop("api_key", None)
    new = _merge(cur, partial)
    save(new)
    return public(new)


def public(s: dict | None = None) -> dict:
    s = copy.deepcopy(s or load())
    key = s["ai"]["gemini"].pop("api_key", "")
    s["ai"]["gemini"]["has_key"] = bool(key)
    s["ai"]["gemini"]["key_hint"] = ("…" + key[-4:]) if len(key) >= 8 else ""
    return s


def set_gemini_key(key: str) -> None:
    s = load()
    s["ai"]["gemini"]["api_key"] = key.strip()
    if not key.strip():
        s["ai"]["gemini"]["model"] = ""
    save(s)


def get_secret() -> str:
    return load()["ai"]["gemini"]["api_key"]
