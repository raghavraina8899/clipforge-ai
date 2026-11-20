"""Tighten a clip: cut out long pauses and filler words ("um", "uh") so it feels punchier.
Works on the transcript's word timings. Everything is computed in seconds relative to the clip start, and cut points are snapped
to video frames so picture and sound stay exactly in sync."""
import re
from typing import Optional

FILLERS_DEFAULT = "um, umm, uh, uhh, uhm, er, erm, ah, hmm, hm, mm, mmm"
DEFAULTS = {"enabled": False, "silence": True, "silence_max": 0.7, "keep": 0.2, "fillers": True, "filler_words": FILLERS_DEFAULT, "manual": []}


def _norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def merged_opts(o: Optional[dict]) -> dict:
    return {**DEFAULTS, **{k: v for k, v in (o or {}).items() if v is not None}}


def plan(words: list, start: float, end: float, opts: Optional[dict], fps: float = 30.0) -> dict:
    """words: [{w,s,e}] on the video timeline. Returns cut intervals RELATIVE to `start`:
    {"keep": [(a,b)], "removed": [(a,b)], "pauses", "fillers", "removed_seconds", "new_duration", "duration"}"""
    o = merged_opts(opts)
    dur = max(0.0, end - start)
    out = {"keep": [(0.0, dur)], "removed": [], "pauses": 0, "fillers": 0, "removed_seconds": 0.0, "new_duration": dur, "duration": dur}
    # manual cuts (drawn on the timeline, absolute video time) always apply; the automatic pause/filler cutting only when switched on
    manual = [(max(start, float(m["start"])), min(end, float(m["end"]))) for m in (o.get("manual") or []) if isinstance(m, dict) and "start" in m and "end" in m]
    manual = [(a, b) for a, b in manual if b - a > 0.05]
    if (not o["enabled"] and not manual) or dur < 2:
        return out
    cuts: list = list(manual)
    nf = npause = 0
    ws = [w for w in words if w["e"] > start and w["s"] < end and w.get("w", "") != ""] if o["enabled"] else []
    if ws:
        fillers = {_norm(x) for x in re.split(r"[,\n]", o["filler_words"] or "") if _norm(x)} if o["fillers"] else set()
        kept = []
        for w in ws:
            if _norm(w["w"]) in fillers:
                a, b = max(start, w["s"] + 0.02), min(end, w["e"] - 0.02)
                if b - a > 0.05:
                    cuts.append((a, b))
                    nf += 1
                    continue
            kept.append(w)
        if o["silence"] and kept:
            thr, keep = float(o["silence_max"]), float(o["keep"])
            prev = start
            for i, w in enumerate(kept):
                gap = w["s"] - prev
                if gap > thr:
                    a = start if i == 0 else prev + keep
                    b = w["s"] - keep
                    if b - a > 0.1:
                        cuts.append((a, b))
                        npause += 1
                prev = max(prev, w["e"])
            tail = end - prev
            if tail > thr and end - (prev + keep) > 0.1:
                cuts.append((prev + keep, end))
                npause += 1
    cuts.sort()
    merged: list = []
    for a, b in cuts:
        a, b = max(start, a), min(end, b)
        if b <= a:
            continue
        if merged and a <= merged[-1][1] + 0.001:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    # snap to the frame grid (relative to the clip start) so audio and video are cut identically
    snap = lambda t: round(t * fps) / fps  # noqa: E731
    rel = [(snap(a - start), snap(b - start)) for a, b in merged]
    rel = [(a, b) for a, b in rel if b - a >= 0.1]
    keep_iv, cur = [], 0.0
    for a, b in rel:
        if a - cur > 0.04:
            keep_iv.append((cur, a))
        cur = b
    snapped_dur = snap(dur)
    if snapped_dur - cur > 0.04:
        keep_iv.append((cur, snapped_dur))
    total_keep = sum(b - a for a, b in keep_iv)
    if not rel or total_keep < 1.0:
        return out  # nothing worth cutting, or it would leave almost nothing
    out.update(keep=keep_iv, removed=rel, pauses=npause, fillers=nf, removed_seconds=round(dur - total_keep, 2), new_duration=round(total_keep, 3))
    return out


def remap_words(words_rel: list, removed: list) -> list:
    """Words (times relative to the clip start, original timeline) -> words on the tightened timeline; words inside a cut are dropped."""
    if not removed:
        return words_rel
    out = []
    for w in words_rel:
        mid = (w["s"] + w["e"]) / 2
        if any(a <= mid <= b for a, b in removed):
            continue

        def shift(t):
            return t - sum(min(t, b) - a for a, b in removed if t > a)

        out.append({**w, "s": round(max(0.0, shift(w["s"])), 3), "e": round(max(0.0, shift(w["e"])), 3)})
    return out


def select_expr(keep: list) -> str:
    return "+".join(f"gte(t,{a:.4f})*lt(t,{b:.4f})" for a, b in keep)
