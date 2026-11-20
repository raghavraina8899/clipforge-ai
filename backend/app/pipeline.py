"""Orchestration: ingest -> transcribe -> analyze -> clips; rendering; thumbnails; helpers shared by the API."""
import copy
import json
import shutil
import logging
import re
import time
from pathlib import Path
from typing import Optional

from . import db
from .config import FONTS_DIR, PROJECTS_DIR, project_dir
from .jobs import JobCtx
from .services import analyze, ffmpeg, render, settings_store, transcribe

from .services.hinglish import has_devanagari as has_dev

log = logging.getLogger("pipeline")
DEFAULT_PREFS = {"min_dur": 30, "max_dur": 60, "max_clips": 8, "language": "auto"}


def paths(pid: str) -> dict:
    d = project_dir(pid)
    return {"dir": d, "transcript": d / "transcript.json", "proxy": d / "proxy.mp4", "thumb": d / "thumb.jpg",
            "audio": d / "audio.wav", "exports": d / "exports", "thumbs": d / "thumbs", "work": d / "work"}


def clip_defaults() -> dict:
    s = settings_store.load()
    d = copy.deepcopy(s["video"])
    d["caption"] = copy.deepcopy(s["caption"])
    d["audio"] = {}
    return d


def clip_settings(clip: dict) -> dict:
    """Stored settings merged over current defaults; caption is expanded to the full style so the UI can edit every field."""
    from .services import captions
    out = settings_store._merge(clip_defaults(), clip.get("settings") or {})
    cap = out.get("caption") or {}
    out["caption"] = {**captions.merge_style(cap), "preset": cap.get("preset", "hormozi")}
    return out


def media_url(pid: str, p: Path) -> str:
    return f"/media/{pid}/{p.relative_to(PROJECTS_DIR / pid).as_posix()}?v={int(p.stat().st_mtime)}" if p.exists() else ""


def load_transcript(pid: str) -> Optional[dict]:
    return transcribe.load(paths(pid)["transcript"])


def clip_words(pid: str, start: float, end: float) -> list:
    tr = load_transcript(pid)
    if not tr:
        return []
    return [{**w, "i": i} for i, w in enumerate(tr["words"]) if w["e"] > start and w["s"] < end and w["w"] != ""]


def pretty_error(e: Exception) -> str:
    return str(e) or e.__class__.__name__


# ------------------------------------------------------------------ analysis

def make_clips(pid: str, result: dict) -> int:
    db.delete("clips", "project_id=?", (pid,))
    defaults = clip_defaults()
    for i, c in enumerate(result["clips"]):
        st = settings_store._merge(defaults, c["settings_patch"]) if c.get("settings_patch") else defaults
        db.insert("clips", dict(id=db.new_id(), project_id=pid, idx=i, title=c["title"], start=c["start"], end=c["end"],
                                score=c["score"], scores=c["scores"], reason=c["reason"], hook=c["hook"], caption=c["caption"],
                                kind=c["kind"], selected=1, settings=st, social=None, exports=[], created_at=time.time()))
    return len(result["clips"])


def run_analysis(pid: str, ctx: JobCtx, p0: float = 0, p1: float = 100) -> None:
    proj = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    tr = load_transcript(pid)
    if not tr:
        raise RuntimeError("There is no transcript to analyze yet.")
    prefs = {**DEFAULT_PREFS, **(proj.get("prefs") or {})}
    ctx.update("Analyzing for engaging moments", p0 + (p1 - p0) * 0.1,
               "Scoring candidate moments" if not __import__("app.services.llm", fromlist=["x"]).active_provider() else "Asking the AI provider to rank moments")
    meta = proj.get("meta") or {}
    dur_total = meta.get("duration") or (tr["words"][-1]["e"] if tr["words"] else 0)
    if prefs.get("mode") == "series":
        res = analyze.series(tr["words"], dur_total, float(prefs.get("part_len") or 60), float(prefs.get("range_start") or 0),
                             float(prefs["range_end"]) if prefs.get("range_end") else None)
    else:
        rs, re_ = float(prefs.get("range_start") or 0), float(prefs.get("range_end") or 0)
        words_in = [w for w in tr["words"] if w["s"] >= rs - 0.01 and (not re_ or w["e"] <= re_ + 0.01)]
        res = analyze.analyze(words_in, dur_total, proj["name"], float(prefs["min_dur"]), float(prefs["max_dur"]), int(prefs["max_clips"]))
    n = make_clips(pid, res)
    db.update("projects", pid, analysis={"summary": res["summary"], "engine": res["engine"], "note": res["note"], "clips": n, "mode": prefs.get("mode", "moments"),
                                          "language": tr.get("language"), "word_timing": tr.get("word_timing", "precise"),
                                          "devanagari": any(has_dev(w["w"]) for w in tr["words"])},
              language=tr.get("language"))


def ingest_job(pid: str):
    def fn(ctx: JobCtx):
        P = paths(pid)
        proj = db.one("SELECT * FROM projects WHERE id=?", (pid,))
        db.update("projects", pid, status="processing", error=None)
        try:
            video = Path(proj["video_path"])
            ctx.update("Reading video", 2, "Inspecting the file")
            meta = ffmpeg.probe(video)
            db.update("projects", pid, meta={**(proj.get("meta") or {}), **meta})
            if meta["duration"] < 3:
                raise ffmpeg.MediaError("This video is shorter than 3 seconds; there is nothing to clip.")
            if not meta["has_audio"]:
                raise ffmpeg.MediaError("This video has no audio track, so speech cannot be transcribed. Clipping needs spoken content.")
            ctx.update("Creating preview", 4, "Encoding a 720p preview so the browser can play any format")
            for t in (min(meta["duration"] * 0.1, 10), 0.0):  # thumbnail is cosmetic: never fail the import over it
                try:
                    ffmpeg.extract_frame(video, t, P["thumb"], 640)
                    break
                except ffmpeg.MediaError:
                    log.warning("thumbnail extraction at %.1fs failed", t)
            ffmpeg.make_proxy(video, P["proxy"], meta["duration"], ctx, lambda p: ctx.update("Creating preview", 4 + p * 0.2, f"Encoding preview {p:.0f}%"))
            db.update("projects", pid, proxy_path=str(P["proxy"]), thumb_path=str(P["thumb"]))
            ctx.update("Extracting audio", 25, "Converting audio to 16 kHz mono")
            prefs = {**DEFAULT_PREFS, **(proj.get("prefs") or {})}
            rs = float(prefs.get("range_start") or 0)
            re_ = min(float(prefs.get("range_end") or 0) or meta["duration"], meta["duration"])
            if rs >= re_ - 1:
                rs, re_ = 0.0, meta["duration"]
            span = re_ - rs
            ranged = span < meta["duration"] - 1
            ffmpeg.extract_audio(video, P["audio"], ctx, lambda p: ctx.update(None, 25 + p * 0.05), meta["duration"], start=rs, length=span if ranged else None)
            size = settings_store.load()["transcription"]["model"]
            lang = prefs.get("language") or "auto"
            ctx.update("Transcribing speech", 30)
            tr = transcribe.transcribe(P["audio"], P["transcript"], size, lang, span,
                                       lambda p, m: (ctx.update("Transcribing speech", 30 + p * 0.5, m + (f" (section {rs / 60:.0f}-{re_ / 60:.0f} min only)" if ranged else ""))),
                                       offset=rs if ranged else 0.0)
            P["audio"].unlink(missing_ok=True)
            if not tr["words"]:
                db.update("projects", pid, status="ready", language=tr["language"],
                          analysis={"summary": "", "engine": "builtin", "note": "No speech was detected in this video, so no clips could be suggested. You can still add clips manually.", "clips": 0})
                db.delete("clips", "project_id=?", (pid,))
                return {"clips": 0}
            run_analysis(pid, ctx, 82, 100)
            db.update("projects", pid, status="ready", stage="Ready", progress=100)
            return {"clips": db.one("SELECT COUNT(*) c FROM clips WHERE project_id=?", (pid,))["c"]}
        except Exception as e:
            from .jobs import Cancelled
            if isinstance(e, Cancelled):
                db.update("projects", pid, status="error", error="Processing was cancelled.")
            else:
                db.update("projects", pid, status="error", error=pretty_error(e))
            raise
    return fn


def reanalyze_job(pid: str):
    def fn(ctx: JobCtx):
        try:
            run_analysis(pid, ctx)
            db.update("projects", pid, status="ready", error=None)
        except Exception as e:
            db.update("projects", pid, error=pretty_error(e))
            raise
    return fn


class ScaledCtx:
    """Run a sub-task (ingest) inside part of a bigger job's progress range."""
    def __init__(self, ctx, lo: float, hi: float):
        self._c, self._lo, self._hi = ctx, lo, hi

    def update(self, stage=None, progress=None, message=None):
        self._c.update(stage, None if progress is None else self._lo + progress * (self._hi - self._lo) / 100, message)

    def __getattr__(self, k):
        return getattr(self._c, k)


def cleanup_source(pid: str) -> bool:
    """Delete the downloaded / uploaded copy of the source video (and its preview proxy). Exports, transcript and clips are kept.
    Live recordings are never deleted: that file is the only copy of the footage."""
    proj = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not proj or proj["source_type"] not in ("youtube", "upload") or not proj.get("video_path"):
        return False
    P = paths(pid)
    Path(proj["video_path"]).unlink(missing_ok=True)
    P["proxy"].unlink(missing_ok=True)
    shutil.rmtree(P["thumbs"], ignore_errors=True)
    shutil.rmtree(P["dir"] / "preview", ignore_errors=True)
    shutil.rmtree(P["work"], ignore_errors=True)
    db.update("projects", pid, video_path=None, proxy_path=None, meta={**(proj.get("meta") or {}), "source_deleted": True})
    return True


def delete_exports(pid: str, clip_ids: Optional[list] = None) -> int:
    """Delete exported files (mp4/srt/thumbnails) from disk and forget them; clip definitions stay. Returns bytes freed."""
    P = paths(pid)
    freed = 0
    for c in db.many("SELECT id, exports FROM clips WHERE project_id=?", (pid,)):
        if clip_ids is not None and c["id"] not in clip_ids:
            continue
        for e in c["exports"] or []:
            for name in (e.get("file"), e.get("srt")):
                f = P["exports"] / name if name else None
                if f and f.exists():
                    freed += f.stat().st_size
                    f.unlink()
        for t in P["exports"].glob(f"thumb-{c['id'][:6]}-*.png") if P["exports"].exists() else []:
            freed += t.stat().st_size
            t.unlink()
        db.update("clips", c["id"], exports=[])
    return freed


def maybe_cleanup(pid: str) -> None:
    """Auto-delete the downloaded video once every selected clip has been exported (if the user asked for that)."""
    proj = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not proj or not (proj.get("meta") or {}).get("auto_delete") or proj["source_type"] != "youtube":
        return
    clips = db.many("SELECT selected, exports FROM clips WHERE project_id=?", (pid,))
    sel = [c for c in clips if c["selected"]]
    if sel and all(c["exports"] for c in sel):
        cleanup_source(pid)


# ------------------------------------------------------------------ URL-only preview segments

import threading
_tr_lock = threading.Lock()


def preview_paths(pid: str, clip_id: str) -> tuple:
    d = paths(pid)["dir"] / "preview"
    return d / f"{clip_id}.mp4", d / f"{clip_id}.json"


def preview_info(clip: dict) -> Optional[dict]:
    """Info about a cached preview segment if it still covers the clip's range."""
    f, j = preview_paths(clip["project_id"], clip["id"])
    if not (f.exists() and j.exists()):
        return None
    try:
        info = json.loads(j.read_text())
    except ValueError:
        return None
    if clip["start"] < info["seg_start"] - 0.01 or clip["end"] > info["seg_start"] + info["duration"] + 0.01:
        return None
    return {**info, "url": media_url(clip["project_id"], f)}


def splice_words(pid: str, seg_start: float, seg_end: float, new_words: list) -> None:
    """Replace caption-estimated words in [seg_start, seg_end] with precisely timed ones."""
    with _tr_lock:
        P = paths(pid)
        tr = load_transcript(pid)
        if not tr:
            return
        keep = [w for w in tr["words"] if w["e"] <= seg_start or w["s"] >= seg_end]
        add = [{"w": w["w"], "s": round(w["s"] + seg_start, 3), "e": round(w["e"] + seg_start, 3)} for w in new_words]
        tr["words"] = sorted(keep + add, key=lambda w: w["s"])
        tr["word_timing"] = "mixed"
        P["transcript"].write_text(json.dumps(tr, ensure_ascii=False))


def preview_job(clip_id: str):
    def fn(ctx: JobCtx):
        from .services import ytdl
        clip = db.one("SELECT * FROM clips WHERE id=?", (clip_id,))
        proj = db.one("SELECT * FROM projects WHERE id=?", (clip["project_id"],))
        if not ((proj.get("meta") or {}).get("yt_authorized") and proj.get("source_url")) or (proj.get("meta") or {}).get("yt_mode", "segments") != "segments":
            raise RuntimeError("Downloading is not enabled for this project.")
        pid = proj["id"]
        f, j = preview_paths(pid, clip_id)
        f.parent.mkdir(parents=True, exist_ok=True)
        seg_start, seg_end = max(0.0, clip["start"] - 2.0), clip["end"] + 2.0
        ctx.update("Loading preview", 2, "Downloading a small 480p copy of this clip only (deleted after you export it)")
        try:
            got = ytdl.download_segment(proj["source_url"], seg_start, seg_end, f.parent, clip_id,
                                        lambda p: ctx.update("Loading preview", 2 + p * 0.5, f"Downloading {p:.0f}%"), lambda: ctx.cancelled.is_set(), max_height=480)
        except ytdl.DownloadError as e:
            raise RuntimeError(str(e))
        if got != f:
            got.replace(f)
        info = ffmpeg.probe(f)
        ctx.update("Syncing captions", 55, "Exact word timing from the real audio")
        work = paths(pid)["work"] / f"pv_{clip_id}"
        work.mkdir(parents=True, exist_ok=True)
        try:
            wav = work / "a.wav"
            ffmpeg.extract_audio(f, wav)
            tr = transcribe.transcribe(wav, work / "t.json", settings_store.load()["transcription"]["model"],
                                       (proj.get("prefs") or {}).get("language") or "auto", info["duration"],
                                       lambda p, m: ctx.update("Syncing captions", 55 + p * 0.4, m))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        splice_words(pid, seg_start, seg_start + info["duration"], tr["words"])
        j.write_text(json.dumps({"seg_start": seg_start, "duration": info["duration"], "width": info["width"], "height": info["height"], "fps": info["fps"]}))
        return {"ok": True}
    return fn


# ------------------------------------------------------------------ rendering

def render_job(clip_id: str, settings_override: Optional[dict] = None):
    def fn(ctx: JobCtx):
        clip = db.one("SELECT * FROM clips WHERE id=?", (clip_id,))
        proj = db.one("SELECT * FROM projects WHERE id=?", (clip["project_id"],))
        has_video = bool(proj.get("video_path")) and Path(proj["video_path"]).exists()
        segment_mode = (not has_video and (proj.get("meta") or {}).get("yt_authorized") and proj.get("source_url")
                        and (proj.get("meta") or {}).get("yt_mode", "segments") == "segments")
        if not has_video and not segment_mode:
            raise RuntimeError("The original video file is not attached to this project, so it cannot be rendered. Attach your video file first.")
        P = paths(proj["id"])
        st = clip_settings(clip)
        if settings_override:
            st = settings_store._merge(st, settings_override)
        P["exports"].mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe = re.sub(r"[^A-Za-z0-9]+", "-", clip["title"])[:40].strip("-") or "clip"
        out = P["exports"] / f"{clip['idx'] + 1:02d}-{safe}-{clip_id[:4]}-{stamp}.mp4"
        work = P["work"] / clip_id
        seg_file: Optional[Path] = None
        try:
            if segment_mode:
                from .services import ytdl
                pad = 2.0
                seg_start = max(0.0, clip["start"] - pad)
                seg_end = clip["end"] + pad
                ctx.update("Downloading this clip's segment", 1, "Fetching only the selected time range (temporary, deleted after rendering)")
                try:
                    seg_file = ytdl.download_segment(proj["source_url"], seg_start, seg_end, work / "download", "segment",
                                                     lambda p: ctx.update("Downloading this clip's segment", 1 + p * 0.19, f"Downloading {p:.0f}%"), lambda: ctx.cancelled.is_set())
                except ytdl.DownloadError as e:
                    raise RuntimeError(str(e))
                ctx.update("Reading segment", 20)
                src = ffmpeg.probe(seg_file)
                if not src["has_audio"]:
                    raise RuntimeError("The downloaded segment has no audio.")
                ctx.update("Transcribing this clip", 22, "Exact word timing from the real audio")
                audio = work / "audio.wav"
                ffmpeg.extract_audio(seg_file, audio)
                tr = transcribe.transcribe(audio, work / "transcript.json", settings_store.load()["transcription"]["model"],
                                           (proj.get("prefs") or {}).get("language") or "auto", src["duration"],
                                           lambda p, m: ctx.update("Transcribing this clip", 22 + p * 0.18, m))
                # times relative to the segment; the clip starts `clip.start - seg_start` into it
                off = clip["start"] - seg_start
                c2 = {**clip, "start": off, "end": min(off + (clip["end"] - clip["start"]), src["duration"])}
                words = [w for w in tr["words"] if w["e"] > c2["start"] and w["s"] < c2["end"]]
                info = render.render_clip(seg_file, src, None, c2, st, words, out, work, ctx,
                                          lambda p, m: ctx.update("Rendering clip", 40 + p * 0.6, m))
                rel_words = [{"w": w["w"], "s": w["s"] - c2["start"], "e": w["e"] - c2["start"]} for w in words]
                info["notes"] = ["Source segment was downloaded temporarily and deleted after rendering."] + info["notes"]
            else:
                words = clip_words(proj["id"], clip["start"], clip["end"])
                info = render.render_clip(Path(proj["video_path"]), proj["meta"], P["proxy"] if P["proxy"].exists() else None, clip, st, words, out,
                                          work, ctx, lambda p, m: ctx.update("Rendering clip", p, m))
                rel_words = [{"w": w["w"], "s": w["s"] - clip["start"], "e": w["e"] - clip["start"]} for w in words]
        except BaseException:
            out.unlink(missing_ok=True)  # cancelled or failed: never leave a half-written video behind
            raise
        finally:
            shutil.rmtree(work, ignore_errors=True)  # temp download + render scratch files; exports are kept
        if segment_mode:  # export is done: remove the temporary preview download too
            for f in preview_paths(proj["id"], clip_id):
                f.unlink(missing_ok=True)
        srt = out.with_suffix(".srt")
        from .services import captions
        srt.write_text(captions.build_srt(captions.filter_hidden(rel_words, (st.get("caption") or {}).get("hidden"))), encoding="utf-8")
        entry = {"file": out.name, "srt": srt.name, "at": time.time(), **info}
        fresh = db.one("SELECT exports FROM clips WHERE id=?", (clip_id,))
        db.update("clips", clip_id, exports=(fresh["exports"] or []) + [entry], settings=st)
        maybe_cleanup(proj["id"])
        return entry
    return fn


# ------------------------------------------------------------------ thumbnails

FONT_FILES = {"Poppins Black": "Poppins-Black.ttf", "Poppins ExtraBold": "Poppins-ExtraBold.ttf", "Poppins Bold": "Poppins-Bold.ttf",
              "Poppins": "Poppins-Regular.ttf", "Anton": "Anton-Regular.ttf", "Bebas Neue": "BebasNeue-Regular.ttf",
              "Bangers": "Bangers-Regular.ttf", "Archivo Black": "ArchivoBlack-Regular.ttf"}
SYSTEM_FONTS = {"Impact": "/System/Library/Fonts/Supplemental/Impact.ttf", "Arial": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "Georgia": "/System/Library/Fonts/Supplemental/Georgia Bold.ttf", "Verdana": "/System/Library/Fonts/Supplemental/Verdana Bold.ttf"}


def candidate_frames(clip: dict, proj: dict, n: int = 6) -> list:
    P = paths(proj["id"])
    d = P["thumbs"] / clip["id"]
    d.mkdir(parents=True, exist_ok=True)
    dur = clip["end"] - clip["start"]
    out = []
    for i in range(n):
        f = d / f"f{i}.jpg"
        t = clip["start"] + dur * (0.06 + 0.88 * i / max(1, n - 1))
        if not f.exists():
            ffmpeg.extract_frame(Path(proj["video_path"]), t, f, 1280)
        out.append({"i": i, "t": round(t, 2), "url": media_url(proj["id"], f)})
    return out


def compose_thumbnail(clip: dict, proj: dict, o: dict, final: bool) -> Path:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont
    P = paths(proj["id"])
    d = P["thumbs"] / clip["id"]
    src = d / f"f{int(o.get('frame', 0))}.jpg"
    if not src.exists():
        candidate_frames(clip, proj)
    im = Image.open(src).convert("RGB")
    aspect = o.get("aspect", "9:16")
    a, b = render.ASPECTS.get(aspect, (9, 16))
    w, h = im.size
    tw = min(w, int(h * a / b))
    th = int(tw * b / a)
    if th > h:
        th, tw = h, int(h * a / b)
    x0 = int((w - tw) * float(o.get("focus", 0.5)))
    im = im.crop((x0, 0, x0 + tw, th))
    if not final:
        im.thumbnail((540, 540))
    if abs(float(o.get("contrast", 1)) - 1) > 0.01:
        im = ImageEnhance.Contrast(im).enhance(float(o["contrast"]))
    if abs(float(o.get("brightness", 1)) - 1) > 0.01:
        im = ImageEnhance.Brightness(im).enhance(float(o["brightness"]))
    W, H = im.size
    text = (o.get("text") or "").strip()
    if text:
        fam = o.get("font", "Anton")
        path = FONTS_DIR / FONT_FILES[fam] if fam in FONT_FILES and (FONTS_DIR / FONT_FILES[fam]).exists() else Path(SYSTEM_FONTS.get(fam, "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
        fs = int(H * float(o.get("size", 0.09)))
        font = ImageFont.truetype(str(path), fs)
        if o.get("uppercase", True):
            text = text.upper()
        lines, cur = [], ""
        dr = ImageDraw.Draw(im)
        for word in text.split():
            test = (cur + " " + word).strip()
            if dr.textlength(test, font=font) > W * 0.86 and cur:
                lines.append(cur); cur = word
            else:
                cur = test
        lines.append(cur)
        lh = int(fs * 1.15)
        bh = lh * len(lines)
        y0 = int((H - bh) * float(o.get("y", 0.7)))
        shape = o.get("shape", "bar")
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        col = o.get("shapeColor", "#E11D48")
        if shape == "bar":
            od.rectangle((0, y0 - fs * 0.3, W, y0 + bh + fs * 0.3), fill=col + "E6" if len(col) == 7 else col)
        elif shape == "box":
            wmax = max(dr.textlength(l, font=font) for l in lines)
            od.rounded_rectangle(((W - wmax) / 2 - fs * .4, y0 - fs * .2, (W + wmax) / 2 + fs * .4, y0 + bh + fs * .2), radius=int(fs * .3), fill=col + "F2" if len(col) == 7 else col)
        elif shape == "gradient":
            for yy in range(H // 2, H):
                od.line((0, yy, W, yy), fill=(0, 0, 0, int(220 * (yy - H // 2) / (H / 2))))
        im = Image.alpha_composite(im.convert("RGBA"), ov)
        dr = ImageDraw.Draw(im)
        for i, ln in enumerate(lines):
            tx = (W - dr.textlength(ln, font=font)) / 2
            dr.text((tx, y0 + i * lh), ln, font=font, fill=o.get("color", "#FFFFFF"), stroke_width=max(2, fs // 14),
                    stroke_fill="#000000" if shape in ("none", "gradient") else "#00000000")
        im = im.convert("RGB")
    out = d / ("thumb.png" if final else "preview.jpg")
    im.save(out, quality=92) if not final else im.save(out)
    return out
