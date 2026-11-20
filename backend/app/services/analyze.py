"""Clip discovery. Heuristic analyzer (always available, no API) + optional LLM refinement.
Every candidate - from either source - is validated and re-scored here before it reaches the renderer."""
import logging
import re
from typing import Optional

from . import llm

log = logging.getLogger("analyze")

W = {"hook": .25, "emotion": .15, "info": .20, "engagement": .15, "standalone": .15, "ending": .10}
LABELS = {"hook": "Opening hook", "emotion": "Emotional impact", "info": "Information value",
          "engagement": "Engagement potential", "standalone": "Standalone context", "ending": "Ending quality"}
POWER = set("secret mistake mistakes never nobody truth why stop biggest worst best actually crazy insane wrong myth lie lies "
            "everything nothing always real fake only first last free easy hard simple impossible proof shocking warning "
            "problem fail failed failure win won lost money rich dangerous hidden exactly".split())
EMOTION = set("love hate afraid fear scared amazing terrible awful incredible beautiful angry happy sad cry cried tears "
              "proud shame ashamed excited hurt pain painful heart passion dream dreams struggle struggled grateful sorry "
              "unbelievable wow haha laugh laughed funny hilarious".split())
INFO = ["because", "for example", "for instance", "that means", "the reason", "step", "how to", "key", "important",
        "means", "lesson", "learn", "rule", "principle", "tip", "strategy", "framework", "works", "so that"]
CONTROV = set("controversial wrong lie lies myth overrated scam fake unpopular honestly truth nobody everyone disagree".split())
FUNNY = re.compile(r"\b(ha){2,}|\bhaha|\blol\b|\(laugh|hilarious|joke|funny", re.I)
WEAK_START = set("and but so or because then also well um uh yeah yes no okay ok like that it this they he she them those these which who".split())
WEAK_END = set("and but so or because then the a an of to in with that which".split())
STOP = set("the a an and or but if then so to of in on at for with from by is are was were be been being it its this that these those "
           "i you he she we they me him her us them my your his our their as not no yes do does did have has had will would can could "
           "should just very really about into out up down over than too also there here what when where who how all any some".split())


def fmt(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def sentences(words: list) -> list:
    """Group word dicts into sentences using punctuation and pauses."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end = bool(re.search(r"[.!?।…]$|[.!?।]['\")\]]$", w["w"])) or (nxt is not None and nxt["s"] - w["e"] > 0.9) or nxt is None
        if end or len(cur) >= 45:
            out.append({"i0": cur[0], "i1": cur[-1], "s": words[cur[0]]["s"], "e": words[cur[-1]]["e"],
                        "text": " ".join(words[j]["w"] for j in cur)})
            cur = []
    return out


def _toks(text: str) -> list:
    return re.findall(r"[\w'’$%]+", text.lower())


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def score_window(sents: list) -> tuple:
    """Return (components dict, evidence list, kind) for a run of sentences."""
    text = " ".join(s["text"] for s in sents)
    first, last = sents[0]["text"], sents[-1]["text"]
    ft, lt, at = _toks(first), _toks(last), _toks(text)
    dur = max(0.1, sents[-1]["e"] - sents[0]["s"])
    ev = []

    hook = 38.0
    if "?" in first:
        hook += 22; ev.append("opens with a question")
    if re.search(r"\d", first):
        hook += 12; ev.append("opens with a concrete number")
    p = sum(1 for t in ft if t in POWER)
    if p:
        hook += min(24, 12 * p); ev.append("uses strong opening words")
    if 5 <= len(ft) <= 18:
        hook += 10
    if ft and ft[0] in ("so", "and", "um", "uh", "yeah", "well", "okay", "ok", "like"):
        hook -= 22
    if len(ft) > 28:
        hook -= 12
    hook = _clamp(hook)

    emo = 25.0 + 9 * text.count("!") + 12 * sum(1 for t in at if t in EMOTION)
    laughs = len(FUNNY.findall(text))
    emo += 14 * laughs + 4 * len(re.findall(r"\b[A-Z]{3,}\b", text))
    if emo > 40:
        ev.append("carries emotional language")
    emo = _clamp(emo)

    hits = sum(1 for k in INFO if k in text.lower())
    nums = len(re.findall(r"\d+", text))
    info = 22.0 + 9 * hits + 5 * min(nums, 5) + 30 * (len(set(at)) / max(1, len(at)) - 0.4)
    if hits >= 2:
        ev.append("explains something concrete")
    info = _clamp(info)

    q = text.count("?")
    you = sum(1 for t in at if t in ("you", "your", "you're", "you've"))
    contrast = sum(1 for t in at if t in ("but", "however", "actually", "instead", "except"))
    eng = 25.0 + 7 * min(q, 3) + 3 * min(you, 8) + 5 * min(contrast, 3) + 8 * sum(1 for t in at if t in CONTROV)
    if you >= 3:
        ev.append("speaks directly to the viewer")
    eng = _clamp(eng)

    sa = 78.0
    if ft and ft[0] in WEAK_START:
        sa -= 28
    if re.search(r"\b(as i said|like i said|as i mentioned|earlier|as we discussed|going back)\b", text.lower()):
        sa -= 20
    if len(ft) >= 2 and ft[0] in ("it", "this", "that", "they", "he", "she"):
        sa -= 10
    if len(sents) >= 2:
        sa += 6
    sa = _clamp(sa)
    if sa >= 70:
        ev.append("makes sense without extra context")

    end = 55.0
    if re.search(r"[.!?।]['\")]?$", last):
        end += 18
    if 4 <= len(lt) <= 20:
        end += 10
    if lt and lt[-1] in WEAK_END:
        end -= 30
    if re.search(r"(that's why|remember|the point is|so\b.*\.|in the end|bottom line|that's it)", last.lower()):
        end += 10
    end = _clamp(end)
    if end >= 75:
        ev.append("ends on a complete thought")

    wps = len(at) / dur
    comps = {"hook": hook, "emotion": emo, "info": info, "engagement": eng, "standalone": sa, "ending": end}
    if wps < 1.3:  # long silences / filler
        comps = {k: v * 0.8 for k, v in comps.items()}
        ev.append("(slow pacing lowers the score)")
    kind = "Insight"
    if laughs:
        kind = "Funny"
    elif emo >= 55 and emo >= info:
        kind = "Emotional"
    elif sum(1 for t in at if t in CONTROV) >= 2 or (hook >= 70 and eng >= 55):
        kind = "Surprising"
    elif info >= 50:
        kind = "Educational"
    return comps, ev, kind


def total(comps: dict) -> float:
    return round(sum(comps[k] * W[k] for k in W), 1)


def _title(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip().rstrip(".,;:")
    if len(t) > 62:
        t = t[:62].rsplit(" ", 1)[0] + "…"
    return t[:1].upper() + t[1:]


def heuristic(words: list, duration: float, min_d: float, max_d: float, max_clips: int = 8) -> list:
    sents = sentences(words)
    if not sents:
        return []
    target = (min_d + max_d) / 2
    cands = []
    for i in range(len(sents)):
        ends = []
        for j in range(i, len(sents)):
            d = sents[j]["e"] - sents[i]["s"]
            if d > max_d:
                break
            if d >= min_d:
                ends.append((abs(d - target), j))
        ends.sort()
        for _, j in ends[:3]:
            run = sents[i:j + 1]
            comps, ev, kind = score_window(run)
            cands.append((total(comps), i, j, comps, ev, kind))
    cands.sort(reverse=True)
    chosen = []
    for sc, i, j, comps, ev, kind in cands:
        if len(chosen) >= max_clips:
            break
        s0, e0 = sents[i]["s"], sents[j]["e"]
        if any(min(e0, c["end"]) - max(s0, c["start"]) > 0.1 * (e0 - s0) for c in chosen):
            continue
        run = sents[i:j + 1]
        best_hook = max(run[:4], key=lambda s: score_window([s])[0]["hook"])
        top2 = sorted(((comps[k], k) for k in comps), reverse=True)[:2]
        reason = f"{kind} moment: " + ("; ".join(ev[:3]) if ev else f"strongest in {LABELS[top2[0][1]].lower()}") + "."
        chosen.append(dict(start=round(max(0, s0 - 0.15), 2), end=round(min(duration or e0 + 1, e0 + 0.35), 2), score=sc, scores=comps,
                           reason=reason[0].upper() + reason[1:], title=_title(run[0]["text"]), hook=_title(best_hook["text"]),
                           caption=_title(run[0]["text"]), kind=kind))
    chosen.sort(key=lambda c: c["start"])
    return chosen


def summarize_heuristic(words: list) -> str:
    sents = sentences(words)
    if not sents:
        return ""
    freq: dict = {}
    for t in _toks(" ".join(w["w"] for w in words)):
        if t not in STOP and len(t) > 3:
            freq[t] = freq.get(t, 0) + 1
    top = [k for k, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:6]]
    return "Frequent topics: " + ", ".join(top) + "." if top else ""


# ---------------------------------------------------------------- LLM-assisted path

SYSTEM = ("You are an expert short-form video editor. You choose moments from a transcript that work as standalone 15-90 second "
          "Shorts/Reels. You never invent or paraphrase speech: titles and hooks may be catchy but must stay faithful to what is said "
          "and must not mislead. Respond with JSON only.")


def _llm_chunk(lines: str, min_d: float, max_d: float, n: int, title: str) -> dict:
    prompt = f"""Video title: {title or 'unknown'}
Transcript lines are "[seconds] text". Pick up to {n} clip candidates, each {min_d:.0f}-{max_d:.0f} seconds long,
that start at the beginning of a sentence and end at the end of a sentence, and make sense on their own.
Score each component 0-100: hook (opening strength), emotion, info (information value), engagement, standalone (context), ending.
Return JSON: {{"summary": "2 sentences about the video", "clips": [{{"start": seconds, "end": seconds, "title": "...", "reason": "why chosen (1 sentence)",
"hook": "strongest opening line, faithful to the speech, max 80 chars", "caption": "suggested social caption",
"kind": "Educational|Funny|Emotional|Surprising|Insight", "scores": {{"hook":0,"emotion":0,"info":0,"engagement":0,"standalone":0,"ending":0}}}}]}}

TRANSCRIPT:
{lines}"""
    return llm.generate_json(prompt, SYSTEM)


def _snap(sents: list, start: float, end: float, min_d: float, max_d: float, duration: float):
    """Snap an LLM-provided range to real sentence boundaries; return None if unusable."""
    if not sents:
        return None
    i = min(range(len(sents)), key=lambda k: abs(sents[k]["s"] - start))
    j = min(range(i, len(sents)), key=lambda k: abs(sents[k]["e"] - end))
    while j > i and sents[j]["e"] - sents[i]["s"] > max_d:
        j -= 1
    while j + 1 < len(sents) and sents[j]["e"] - sents[i]["s"] < min_d and sents[j + 1]["e"] - sents[i]["s"] <= max_d:
        j += 1
    d = sents[j]["e"] - sents[i]["s"]
    if d < min_d * 0.8 or d > max_d * 1.05:
        return None
    return i, j


def analyze(words: list, duration: float, title: str, min_d: float, max_d: float, max_clips: int = 8) -> dict:
    """Returns {clips, summary, engine, note}. Falls back to built-in heuristics with an honest note."""
    base = heuristic(words, duration, min_d, max_d, max_clips)
    relaxed = ""
    if not base and words:
        speech_len = words[-1]["e"] - words[0]["s"]
        lo, hi = max(5.0, min(min_d, speech_len * 0.6)), max(max_d, min(speech_len, 180.0))
        base = heuristic(words, duration, lo, hi, max_clips)
        if base:
            relaxed = f"No moment fit {min_d:.0f}–{max_d:.0f} s (the speech is only {speech_len:.0f} s long), so the length range was relaxed to {lo:.0f}–{hi:.0f} s."
    out = {"clips": base, "summary": summarize_heuristic(words), "engine": "builtin", "note": relaxed}
    prov = llm.active_provider()
    if not prov or not words:
        if not words:
            out["note"] = "No speech was detected, so no clips could be suggested."
        return out
    sents = sentences(words)
    try:
        lines, chunks, size = [], [], 0
        for s in sents:
            ln = f"[{s['s']:.1f}] {s['text']}"
            lines.append(ln)
            size += len(ln)
            if size > 24000:
                chunks.append("\n".join(lines)); lines, size = [], 0
        if lines:
            chunks.append("\n".join(lines))
        per = max(2, -(-max_clips // len(chunks)) + 1)
        raw, summary = [], ""
        for ch in chunks[:8]:
            r = _llm_chunk(ch, min_d, max_d, per, title)
            summary = summary or str(r.get("summary", ""))[:600]
            raw.extend(r.get("clips") or r.get("items") or [])
        valid = []
        for c in raw:
            try:
                snapped = _snap(sents, float(c["start"]), float(c["end"]), min_d, max_d, duration)
            except (KeyError, TypeError, ValueError):
                continue
            if not snapped:
                continue
            i, j = snapped
            run = sents[i:j + 1]
            heur, ev, kind = score_window(run)
            comps = {}
            for k in W:
                try:
                    lv = _clamp(float((c.get("scores") or {}).get(k)))
                    comps[k] = round(0.6 * lv + 0.4 * heur[k], 1)
                except (TypeError, ValueError):
                    comps[k] = round(heur[k], 1)
            valid.append(dict(start=round(max(0, run[0]["s"] - 0.15), 2), end=round(min(duration or 1e9, run[-1]["e"] + 0.35), 2),
                              score=total(comps), scores=comps, reason=str(c.get("reason") or "")[:300] or "Selected by AI.",
                              title=str(c.get("title") or _title(run[0]["text"]))[:90], hook=str(c.get("hook") or _title(run[0]["text"]))[:100],
                              caption=str(c.get("caption") or "")[:300], kind=c.get("kind") if c.get("kind") in
                              ("Educational", "Funny", "Emotional", "Surprising", "Insight") else kind))
        valid.sort(key=lambda c: -c["score"])
        picked = []
        for c in valid:
            if len(picked) >= max_clips:
                break
            if any(min(c["end"], p["end"]) - max(c["start"], p["start"]) > 0.1 * (c["end"] - c["start"]) for p in picked):
                continue
            picked.append(c)
        if not picked:
            out["note"] = "The AI returned no usable clips; showing built-in analyzer results instead."
            return out
        picked.sort(key=lambda c: c["start"])
        return {"clips": picked, "summary": summary or out["summary"], "engine": prov, "note": ""}
    except llm.LLMError as e:
        out["note"] = f"AI provider failed ({e}) - used the built-in analyzer instead."
        log.warning("llm analysis failed: %s", e)
        return out


def series(words: list, duration: float, part_len: float, start: float = 0.0, end: Optional[float] = None, max_parts: int = 200) -> dict:
    """Cut the speech into consecutive parts in story order, each ending on a sentence boundary (Part 1/N ... N/N)."""
    max_len = part_len * 1.3
    sents = [s for s in sentences(words) if s["s"] >= start - 0.01 and (end is None or s["e"] <= end + 0.01)]
    if not sents:
        return {"clips": [], "summary": "", "engine": "builtin", "note": "No speech was found in the chosen range."}
    groups, cur = [], []
    for s in sents:
        if cur and s["e"] - cur[0]["s"] > max_len:
            groups.append(cur); cur = []
        cur.append(s)
        if cur[-1]["e"] - cur[0]["s"] >= part_len:
            groups.append(cur); cur = []
    if cur:
        if groups and cur[-1]["e"] - cur[0]["s"] < 0.4 * part_len and (cur[-1]["e"] - groups[-1][0]["s"]) <= max_len * 1.2:
            groups[-1] += cur
        else:
            groups.append(cur)
    note = ""
    if len(groups) > max_parts:
        groups, note = groups[:max_parts], f"Only the first {max_parts} parts are shown; use the start/end range for the rest."
    n, clips, prev_end = len(groups), [], 0.0
    for i, g in enumerate(groups, 1):
        s0 = max(prev_end, max(0.0, g[0]["s"] - 0.1))
        e0 = min(duration or g[-1]["e"] + 1, g[-1]["e"] + 0.3)
        comps, ev, _ = score_window(g)
        clips.append(dict(start=round(s0, 2), end=round(e0, 2), score=total(comps), scores=comps, kind="Series",
                          title=f"Part {i}/{n}", hook=f"Part {i}", caption=_title(g[0]["text"]),
                          reason=f"Part {i} of {n}: the story in order, about {e0 - s0:.0f} s, cut at a sentence break.",
                          settings_patch={"hook": {"enabled": True, "text": f"Part {i}", "duration": 2.0, "style": "pop"}}))
        prev_end = e0
    return {"clips": clips, "summary": summarize_heuristic(words), "engine": "series", "note": note}
