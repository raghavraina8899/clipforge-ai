import json
import logging
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import db, jobs, pipeline
from ..config import ALLOWED_AUDIO_EXT, ALLOWED_VIDEO_EXT, ASSETS_DIR, FFMPEG, FONTS_DIR, PROJECTS_DIR, project_dir
from ..services import analyze, captions, ffmpeg, llm, render, settings_store, social, sources, transcribe, vision

log = logging.getLogger("api")
router = APIRouter()


def err(status: int, msg: str):
    raise HTTPException(status, msg)


def get_project(pid: str) -> dict:
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        err(404, "Project not found.")
    return p


def get_clip(cid: str) -> dict:
    c = db.one("SELECT * FROM clips WHERE id=?", (cid,))
    if not c:
        err(404, "Clip not found.")
    return c


def view_project(p: dict) -> dict:
    P = pipeline.paths(p["id"])
    p = dict(p)
    p["proxy_url"] = pipeline.media_url(p["id"], P["proxy"])
    p["thumb_url"] = pipeline.media_url(p["id"], P["thumb"]) if P["thumb"].exists() else ""
    p["has_video"] = bool(p.get("video_path")) and Path(p["video_path"]).exists()
    p["yt_authorized"] = bool((p.get("meta") or {}).get("yt_authorized"))
    m = p.get("meta") or {}
    p["yt_mode"] = m.get("yt_mode", "segments")  # older projects fetch per-clip segments
    p["source_deleted"] = bool(m.get("source_deleted"))
    p["can_render"] = p["has_video"] or (p["yt_authorized"] and bool(p.get("source_url")) and p["yt_mode"] == "segments")
    if p["status"] == "needs_video" and p["can_render"]:
        p["status"] = "ready"
    p.pop("video_path", None)
    p.pop("proxy_path", None)
    p.pop("thumb_path", None)
    return p


def view_clip(c: dict) -> dict:
    c = dict(c)
    c["settings"] = pipeline.clip_settings(c)
    c["selected"] = bool(c["selected"])
    c["exports"] = [{**e, "url": f"/api/download/{c['project_id']}/exports/{e['file']}", "srt_url": f"/api/download/{c['project_id']}/exports/{e['srt']}"}
                    for e in (c.get("exports") or []) if (PROJECTS_DIR / c["project_id"] / "exports" / e["file"]).exists()]
    return c


def active_job(pid: str) -> Optional[dict]:
    return db.one("SELECT * FROM jobs WHERE project_id=? AND status IN ('queued','running') AND kind IN ('ingest','analyze') ORDER BY created_at DESC LIMIT 1", (pid,))


# ================================================================ system + settings

@router.get("/system")
def system():
    enc = ffmpeg.encoders()
    ollama = None
    try:
        ollama = len(llm.ollama_models(settings_store.load()["ai"]["local"]["host"]))
    except llm.LLMError:
        pass
    import importlib.util as iu
    return {"ffmpeg": bool(FFMPEG), "ffmpeg_features": enc, "whisper": iu.find_spec("faster_whisper") is not None,
            "opencv": iu.find_spec("cv2") is not None, "mediapipe": iu.find_spec("mediapipe") is not None,
            "youtube_captions": iu.find_spec("youtube_transcript_api") is not None, "ollama_models": ollama,
            "fonts": [f for f in FONTS_DIR.glob("*.ttf")].__len__()}


@router.get("/storage")
def storage_list():
    from .. import storage
    return storage.summary()


@router.post("/storage/delete")
def storage_delete(body: dict):
    from .. import storage
    ids = [str(i) for i in (body.get("ids") or [])]
    if not ids:
        err(400, "Nothing selected.")
    return storage.delete(ids)


@router.get("/speech-engine")
def speech_engine():
    from ..services import engine
    pref = settings_store.load()["transcription"].get("engine", "auto")
    return {**engine.info(), "setting": pref, "chosen": engine.choose(pref), "model": settings_store.load()["transcription"]["model"]}


@router.post("/speed-test")
def speed_test():
    """Times every available engine on a short bundled speech sample (model loading is excluded from the timing)."""
    from ..services import engine, transcribe
    sample = Path(__file__).resolve().parents[1] / "assets" / "speed_sample.wav"
    size = settings_store.load()["transcription"]["model"]

    def fn(ctx):
        import wave
        results, engs = [], engine.available()
        tmp = Path(tempfile.mkdtemp())
        long_sample = tmp / "sample_long.wav"  # the 30 s sample repeated 5x = 150 s: long enough for batching to show its real speed
        with wave.open(str(sample)) as src, wave.open(str(long_sample), "wb") as dst:
            dst.setparams(src.getparams())
            frames = src.readframes(src.getnframes())
            for _ in range(5):
                dst.writeframes(frames)
        audio_s = 150.0
        for i, eng in enumerate(engs):
            base = i / len(engs) * 100
            ctx.update(f"Testing {engine.LABELS[eng]}", base + 2, "Loading the model (first use downloads it once)")
            out = tmp / "t.json"
            transcribe.transcribe(sample, out, size, "en", 30.0, engine_pref=eng)  # warm-up: loads the model, not timed
            ctx.update(f"Testing {engine.LABELS[eng]}", base + 50 / len(engs), "Timing 150 s of speech")
            t = time.time()
            transcribe.transcribe(long_sample, out, size, "en", audio_s, engine_pref=eng)
            dt = max(0.05, time.time() - t)
            x = audio_s / dt
            results.append({"engine": eng, "label": engine.LABELS[eng], "seconds": round(dt, 2), "x_realtime": round(x, 1), "minutes_for_20h": round(20 * 60 / x, 1)})
        shutil.rmtree(tmp, ignore_errors=True)
        return {"results": results, "model": size}
    return {"job_id": jobs.submit("speedtest", fn)}


@router.get("/doctor")
def doctor_checks(network: int = 1):
    from .. import doctor
    return {"checks": doctor.run_checks(bool(network))}


@router.get("/doctor/steps")
def doctor_steps():
    from .. import doctor
    return {"steps": doctor.steps(True)}


@router.get("/doctor/run/{check_id}")
def doctor_run(check_id: str):
    from .. import doctor
    try:
        return doctor.run_check(check_id)
    except KeyError:
        err(404, "Unknown check.")


@router.get("/doctor/report")
def doctor_report():
    from fastapi.responses import PlainTextResponse
    from .. import doctor
    return PlainTextResponse(doctor.report(True))


@router.get("/settings")
def get_settings():
    return settings_store.public()


@router.put("/settings")
def put_settings(body: dict):
    return settings_store.patch(body)


class KeyBody(BaseModel):
    key: str


@router.put("/settings/ai/gemini-key")
def set_key(b: KeyBody):
    if len(b.key.strip()) < 20:
        err(400, "That does not look like a Gemini API key.")
    settings_store.set_gemini_key(b.key)
    return settings_store.public()


@router.delete("/settings/ai/gemini-key")
def del_key():
    settings_store.set_gemini_key("")
    return settings_store.public()


@router.get("/settings/ai/models")
def ai_models(provider: str = "gemini"):
    try:
        if provider == "gemini":
            return {"models": llm.gemini_models()}
        return {"models": llm.ollama_models(settings_store.load()["ai"]["local"]["host"])}
    except llm.LLMError as e:
        err(400, str(e))


@router.post("/settings/ai/test")
def ai_test(body: dict):
    prov = body.get("provider", "gemini")
    try:
        models = llm.gemini_models() if prov == "gemini" else llm.ollama_models(settings_store.load()["ai"]["local"]["host"])
    except llm.LLMError as e:
        err(400, str(e))
    return {"ok": True, "models": models, "message": f"Connected. {len(models)} model(s) available."}


@router.get("/presets")
def presets():
    return {"presets": [{"id": k, "name": v[0], "style": v[1]} for k, v in captions.PRESETS.items()]}


@router.get("/fonts")
def fonts():
    out = []
    for fam, css, weight, fn in captions.FONT_CATALOG:
        if fn is None or (FONTS_DIR / fn).exists():
            out.append({"name": fam, "css": css, "weight": weight, "url": f"/fonts/{fn}" if fn else None})
    return {"fonts": out}


# ================================================================ assets (user-provided audio)

@router.post("/assets")
async def upload_asset(request: Request, filename: str):
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXT:
        err(400, f"Unsupported audio type {ext or '(none)'}. Use one of: {', '.join(sorted(ALLOWED_AUDIO_EXT))}.")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)
    with open(ASSETS_DIR / name, "wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
    return {"file": name}


@router.get("/assets")
def list_assets():
    return {"assets": sorted(p.name for p in ASSETS_DIR.iterdir() if p.suffix.lower() in ALLOWED_AUDIO_EXT)}


# ================================================================ dashboard

@router.get("/stats")
def stats():
    projects = db.many("SELECT * FROM projects ORDER BY created_at DESC")
    clips = db.many("SELECT id, project_id, title, exports, score, start, end FROM clips")
    exports = []
    for c in clips:
        for e in c["exports"] or []:
            if (PROJECTS_DIR / c["project_id"] / "exports" / e["file"]).exists():
                exports.append({"clip_id": c["id"], "title": c["title"], "project_id": c["project_id"], "at": e["at"], "resolution": e["resolution"],
                                "url": f"/api/download/{c['project_id']}/exports/{e['file']}"})
    exports.sort(key=lambda e: -e["at"])
    return {"videos": sum(1 for p in projects if p["status"] == "ready"), "projects": len(projects), "clips": len(clips), "exports": len(exports),
            "recent_projects": [view_project(p) for p in projects[:6]], "recent_exports": exports[:6],
            "active_jobs": db.many("SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY created_at DESC")}


# ================================================================ projects

def new_project(name: str, source_type: str, **kw) -> str:
    pid = db.new_id()
    db.insert("projects", dict(id=pid, name=name, source_type=source_type, status=kw.pop("status", "new"), progress=0,
                               prefs={**pipeline.DEFAULT_PREFS, **kw.pop("prefs", {})}, created_at=time.time(), updated_at=time.time(), **kw))
    return pid


async def save_upload(request: Request, dest: Path) -> int:
    n = 0
    with open(dest, "wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
            n += len(chunk)
    return n


def parse_prefs(q: dict) -> dict:
    out = {}
    for k in ("min_dur", "max_dur", "max_clips"):
        if q.get(k):
            try:
                out[k] = float(q[k]) if "dur" in k else int(q[k])
            except ValueError:
                err(400, f"Invalid {k}.")
    if q.get("mode") == "series":
        out["mode"] = "series"
    for k in ("part_len", "range_start", "range_end"):
        if q.get(k):
            try:
                out[k] = float(q[k])
            except ValueError:
                err(400, f"Invalid {k}.")
    if q.get("language") in ("auto", "en", "hi", "hinglish"):
        out["language"] = q["language"]
    return out


@router.post("/projects/upload")
async def upload(request: Request, filename: str, name: str = ""):
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXT:
        err(400, f"Unsupported file type {ext or '(none)'}. Supported: {', '.join(sorted(ALLOWED_VIDEO_EXT))}.")
    ffmpeg.require() if FFMPEG else err(500, "FFmpeg is not installed. See the README.")
    pid = new_project(name or Path(filename).stem, "upload", prefs=parse_prefs(dict(request.query_params)))
    dest = project_dir(pid) / f"original{ext}"
    try:
        n = await save_upload(request, dest)
    except Exception as e:  # client aborted etc.
        shutil.rmtree(project_dir(pid), ignore_errors=True)
        db.delete("projects", "id=?", (pid,))
        err(400, f"Upload failed: {e}")
    if n == 0:
        shutil.rmtree(project_dir(pid), ignore_errors=True)
        db.delete("projects", "id=?", (pid,))
        err(400, "The uploaded file was empty.")
    try:
        meta = ffmpeg.probe(dest)
    except ffmpeg.MediaError as e:
        shutil.rmtree(project_dir(pid), ignore_errors=True)
        db.delete("projects", "id=?", (pid,))
        err(400, str(e))
    db.update("projects", pid, video_path=str(dest), meta=meta, status="processing")
    jid = jobs.submit("ingest", pipeline.ingest_job(pid), project_id=pid)
    return {"project_id": pid, "job_id": jid, "meta": meta}


@router.post("/projects/{pid}/video")
async def attach_video(pid: str, request: Request, filename: str):
    p = get_project(pid)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXT:
        err(400, f"Unsupported file type {ext or '(none)'}.")
    dest = project_dir(pid) / f"original{ext}"
    await save_upload(request, dest)
    try:
        meta = ffmpeg.probe(dest)
    except ffmpeg.MediaError as e:
        dest.unlink(missing_ok=True)
        err(400, str(e))
    db.update("projects", pid, video_path=str(dest), meta={**(p.get("meta") or {}), **meta}, status="processing")
    return {"project_id": pid, "job_id": jobs.submit("ingest", pipeline.ingest_job(pid), project_id=pid), "meta": meta}


class YT(BaseModel):
    url: str
    language: str = "auto"
    mode: str = "moments"  # moments | series
    part_len: Optional[float] = None
    range_start: Optional[float] = None
    range_end: Optional[float] = None
    yt_download: str = "full"  # full: download the whole video once (recommended) | segments: fetch each clip separately
    auto_delete: bool = True  # delete the downloaded video once every selected clip is exported
    authorized: bool = False  # user confirms they own the video / have permission: enables temporary segment download for rendering
    min_dur: Optional[float] = None
    max_dur: Optional[float] = None


def youtube_job(pid: str, info: dict, url: str, authorized: bool):
    def fn(ctx):
        P = pipeline.paths(pid)
        ctx.update("Reading video information", 10)
        try:
            import httpx
            r = httpx.get(info["thumbnail_url"], timeout=15)
            if r.status_code == 200:
                P["thumb"].write_bytes(r.content)
        except Exception:  # noqa: BLE001 - thumbnail is cosmetic
            pass
        cur = db.one("SELECT meta FROM projects WHERE id=?", (pid,))["meta"] or {}
        if authorized and cur.get("yt_mode", "full") == "full":
            # one download of the whole video; everything after that runs locally on the real file
            from ..services import ytdl
            ctx.update("Downloading the video (one time)", 3, "Downloading the full video once; it is deleted after your clips are exported")
            try:
                vf = ytdl.download_full(url, P["dir"], "original", 1080, lambda p_: ctx.update("Downloading the video (one time)", 3 + p_ * 0.3, f"Downloading {p_:.0f}%"),
                                        lambda: ctx.cancelled.is_set())
            except ytdl.DownloadError as e:
                db.update("projects", pid, status="error", error=str(e))
                raise RuntimeError(str(e))
            db.update("projects", pid, video_path=str(vf))
            return pipeline.ingest_job(pid)(pipeline.ScaledCtx(ctx, 35, 100))
        ctx.update("Fetching public captions", 35)
        t = sources.youtube_transcript(info["video_id"])
        meta = db.one("SELECT meta FROM projects WHERE id=?", (pid,))["meta"]
        if not t["ok"] and authorized:
            # no public captions: fetch audio only (temporary), transcribe locally, then delete it
            from ..services import transcribe, ytdl
            work = P["dir"] / "tmp_audio"
            wav = work / "audio.wav"
            pf = db.one("SELECT prefs FROM projects WHERE id=?", (pid,))["prefs"] or {}
            rs0, re0 = float(pf.get("range_start") or 0), float(pf.get("range_end") or 0)
            if re0 and re0 <= rs0 + 1:
                rs0 = re0 = 0.0
            try:
                if not wav.exists():  # a retry reuses the finished audio of an earlier attempt (long videos take hours)
                    ctx.update("Downloading audio for analysis", 40, f"{t['reason']} Fetching audio only (temporary).")
                    shutil.rmtree(work, ignore_errors=True)  # never resume a stale partial file
                    # whole audio, downloaded the normal (fast) way; the chosen range is cut out below. A ranged download is throttled to ~1x real time.
                    af = ytdl.download_audio(url, work, lambda p: ctx.update("Downloading audio for analysis", 40 + p * 0.1, f"Downloading audio {p:.0f}%"), lambda: ctx.cancelled.is_set())
                    ctx.update("Preparing audio", 50, "Converting audio for the speech model")
                    part = work / "audio_part.wav"
                    cut = (["-ss", f"{rs0:.3f}"] if rs0 else []) + (["-t", f"{re0 - rs0:.3f}"] if re0 else [])
                    ffmpeg.run([*cut, "-i", af, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", part], (re0 - rs0) if re0 else 0, ctx)
                    part.replace(wav)
                    af.unlink(missing_ok=True)
                dur = ffmpeg.audio_duration(wav)
                ctx.update("Transcribing speech", 55, f"Transcribing {dur / 3600:.1f} h of audio locally (roughly 9x faster than real time)")
                tr = transcribe.transcribe(wav, P["transcript"], settings_store.load()["transcription"]["model"],
                                           pf.get("language") or "auto", dur,
                                           lambda p, m_: ctx.update("Transcribing speech", 55 + p * 0.3, m_), offset=rs0)
            except ytdl.DownloadError as e:
                db.update("projects", pid, status="error", error=str(e))
                raise RuntimeError(str(e))
            except Exception as e:  # noqa: BLE001 - never leave the project stuck on "processing"
                from ..jobs import Cancelled
                db.update("projects", pid, status="error", error=("Cancelled. Press Try again to continue (the downloaded audio is kept)." if isinstance(e, Cancelled) else f"{e} (the downloaded audio is kept, so Try again resumes from the transcription step)."))
                raise
            shutil.rmtree(work, ignore_errors=True)  # success: remove the temporary audio
            meta["duration"] = round((re0 if re0 else rs0 + dur), 1)
            db.update("projects", pid, meta=meta)
            if not tr["words"]:
                db.update("projects", pid, status="ready", analysis={"summary": "", "engine": "builtin", "clips": 0, "note": "No speech was detected.", "access": {"transcript": True, "reason": ""}})
                return {"transcript": True}
            pipeline.run_analysis(pid, ctx, 88, 100)
            db.update("projects", pid, status="ready", language=tr["language"],
                      analysis={**db.one("SELECT analysis FROM projects WHERE id=?", (pid,))["analysis"], "access": {"transcript": True, "reason": ""}})
            return {"transcript": True, "source": "audio"}
        if not t["ok"]:
            db.update("projects", pid, status="needs_video",
                      analysis={"summary": "", "engine": "builtin", "clips": 0, "note": "", "access": {"transcript": False, "reason": t["reason"]}},
                      meta={**meta, "duration": 0})
            return {"transcript": False}
        words = sources.segments_to_words(t["segments"])
        if ((db.one("SELECT prefs FROM projects WHERE id=?", (pid,))["prefs"] or {}).get("language")) == "hinglish":
            from ..services import hinglish as _h
            _h.romanize_words(words)
            for sg in t["segments"]:
                sg["text"] = _h.romanize(sg["text"])
        P["transcript"].write_text(json.dumps({"language": t["language"][:2], "model": "youtube-captions", "word_timing": "estimated", "segments": t["segments"], "words": words}, ensure_ascii=False))
        meta["duration"] = round(t["segments"][-1]["end"], 1) if t["segments"] else 0
        db.update("projects", pid, meta=meta)
        pipeline.run_analysis(pid, ctx, 55, 100)
        db.update("projects", pid, status="ready" if authorized else "needs_video", language=t["language"][:2],
                  analysis={**db.one("SELECT analysis FROM projects WHERE id=?", (pid,))["analysis"], "access": {"transcript": True, "reason": ""}})
        return {"transcript": True}
    return fn


@router.post("/projects/youtube")
def add_youtube(b: YT):
    try:
        info = sources.youtube_info(b.url)
    except ValueError as e:
        err(400, str(e))
    prefs = {k: v for k, v in (("min_dur", b.min_dur), ("max_dur", b.max_dur), ("part_len", b.part_len), ("range_start", b.range_start),
                                ("range_end", b.range_end)) if v}
    lr_s, lr_e = sources.youtube_range(b.url)  # time range carried by the link itself (?t=, start=, end=)
    if (lr_s or lr_e) and not (b.range_start or b.range_end):
        if lr_s:
            prefs["range_start"] = lr_s
        if lr_e:
            prefs["range_end"] = lr_e
    if b.mode == "series":
        prefs["mode"] = "series"
    pid = new_project(info["title"] or f"YouTube {info['video_id']}", "youtube", source_url=b.url, status="processing",
                      meta={"title": info["title"], "author": info["author"], "video_id": info["video_id"], "warning": info.get("warning", ""), "yt_authorized": bool(b.authorized), "yt_mode": b.yt_download if b.yt_download in ("full", "segments") else "full", "auto_delete": bool(b.auto_delete)}, prefs=prefs)

    fn = youtube_job(pid, info, b.url, bool(b.authorized))
    return {"project_id": pid, "job_id": jobs.submit("analyze", fn, project_id=pid), "info": info,
            "access": ("You confirmed you may use this video: HookHunt will download only each clip's time range when you render it, then delete it." if b.authorized else "Without confirming you own this video, HookHunt reads metadata and public captions only (text suggestions). Confirm permission or upload the file to render video clips.")}


class Live(BaseModel):
    url: str
    name: str = ""
    authorized: bool = False
    language: str = "auto"


@router.post("/projects/{pid}/retry")
def retry_project(pid: str):
    """Run a failed or cancelled project again (YouTube: restart the analysis; upload/live: redo import + transcription from the saved file)."""
    p = get_project(pid)
    if active_job(pid):
        err(409, "Already processing.")
    if p["source_type"] == "youtube":
        meta = p.get("meta") or {}
        try:
            info = sources.youtube_info(p["source_url"])
        except ValueError as e:
            err(400, str(e))
        db.update("projects", pid, status="processing", error=None)
        return {"job_id": jobs.submit("analyze", youtube_job(pid, info, p["source_url"], bool(meta.get("yt_authorized"))), project_id=pid)}
    if not p.get("video_path") or not Path(p["video_path"]).exists():
        err(400, "The video file is no longer stored, so this project cannot be re-run. Attach the video again.")
    db.update("projects", pid, status="processing", error=None)
    return {"job_id": jobs.submit("ingest", pipeline.ingest_job(pid), project_id=pid)}


@router.post("/projects/{pid}/download-full")
def download_full_video(pid: str, body: Optional[dict] = None):
    """Fetch the whole video once for a YouTube project the user has authorized, then process it like an upload."""
    p = get_project(pid)
    if p["source_type"] != "youtube":
        err(400, "Only YouTube projects use this.")
    meta = p.get("meta") or {}
    if not meta.get("yt_authorized"):
        err(400, "Confirm that you own this video or have permission to use it first.")
    if active_job(pid):
        err(409, "Already processing.")
    try:
        info = sources.youtube_info(p["source_url"])
    except ValueError as e:
        err(400, str(e))
    db.update("projects", pid, status="processing", error=None, meta={**meta, "yt_mode": "full", "auto_delete": bool((body or {}).get("auto_delete", True)), "source_deleted": False})
    return {"job_id": jobs.submit("analyze", youtube_job(pid, info, p["source_url"], True), project_id=pid)}


@router.delete("/projects/{pid}/source")
def delete_source(pid: str):
    """Delete the downloaded video to free disk space (clips, transcript and exports stay)."""
    get_project(pid)
    if active_job(pid):
        err(409, "Still processing.")
    return {"deleted": pipeline.cleanup_source(pid)}


@router.post("/projects/{pid}/authorize-download")
def authorize_download(pid: str, body: dict):
    p = get_project(pid)
    if p["source_type"] != "youtube":
        err(400, "Only YouTube projects use this.")
    if not body.get("authorized"):
        err(400, "Please confirm that you own this video or have permission to use it.")
    db.update("projects", pid, meta={**(p.get("meta") or {}), "yt_authorized": True})
    return {"ok": True}


@router.post("/projects/live")
def add_live(b: Live):
    if not b.authorized:
        err(400, "Please confirm that you own this stream or have permission to record it.")
    try:
        url = sources.validate_stream_url(b.url)
    except ValueError as e:
        err(400, str(e))
    if not FFMPEG:
        err(500, "FFmpeg is not installed.")
    pid = new_project(b.name or "Live recording", "live", source_url="", status="new", prefs={"language": b.language})
    rec = sources.Recorder(url, project_dir(pid))
    sources.RECORDERS[pid] = rec
    return {"project_id": pid}


@router.post("/projects/{pid}/live/{action}")
def live_ctl(pid: str, action: str):
    rec = sources.RECORDERS.get(pid)
    if not rec:
        err(404, "No active recording session for this project (the server may have restarted).")
    try:
        if action == "start":
            rec.start()
        elif action == "pause":
            rec.pause()
        elif action == "resume":
            rec.resume()
        elif action == "stop":
            out = rec.stop()
            db.update("projects", pid, video_path=str(out), status="processing")
            sources.RECORDERS.pop(pid, None)
            return {"project_id": pid, "job_id": jobs.submit("ingest", pipeline.ingest_job(pid), project_id=pid), **rec.status()}
        else:
            err(404, "Unknown action.")
    except RuntimeError as e:
        err(400, str(e))
    return rec.status()


@router.get("/projects/{pid}/live")
def live_status(pid: str):
    rec = sources.RECORDERS.get(pid)
    return rec.status() if rec else {"state": "none", "elapsed": 0, "bytes": 0, "error": ""}


@router.get("/projects")
def list_projects():
    out = []
    for p in db.many("SELECT * FROM projects ORDER BY created_at DESC"):
        v = view_project(p)
        v["clip_count"] = db.one("SELECT COUNT(*) c FROM clips WHERE project_id=?", (p["id"],))["c"]
        v["export_count"] = sum(len(c["exports"] or []) for c in db.many("SELECT exports FROM clips WHERE project_id=?", (p["id"],)))
        out.append(v)
    return {"projects": out}


@router.get("/projects/{pid}")
def project_detail(pid: str):
    p = get_project(pid)
    clips = [view_clip(c) for c in db.many("SELECT * FROM clips WHERE project_id=? ORDER BY start", (pid,))]
    return {"project": view_project(p), "clips": clips, "job": active_job(pid)}


class ProjectPatch(BaseModel):
    name: Optional[str] = None
    prefs: Optional[dict] = None


@router.patch("/projects/{pid}")
def patch_project(pid: str, b: ProjectPatch):
    p = get_project(pid)
    f = {}
    if b.name is not None and b.name.strip():
        f["name"] = b.name.strip()[:120]
    if b.prefs is not None:
        f["prefs"] = {**(p.get("prefs") or {}), **b.prefs}
    db.update("projects", pid, **f)
    return {"ok": True}


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    get_project(pid)
    if active_job(pid):
        err(409, "This project is still processing. Cancel the job first.")
    sources.RECORDERS.pop(pid, None)
    db.delete("clips", "project_id=?", (pid,))
    db.delete("jobs", "project_id=?", (pid,))
    db.delete("projects", "id=?", (pid,))
    shutil.rmtree(PROJECTS_DIR / pid, ignore_errors=True)
    return {"ok": True}


class Reanalyze(BaseModel):
    min_dur: float = 30
    max_dur: float = 60
    max_clips: int = 8
    mode: str = "moments"  # moments | series
    part_len: Optional[float] = None
    range_start: Optional[float] = None
    range_end: Optional[float] = None


@router.post("/projects/{pid}/reanalyze")
def reanalyze(pid: str, b: Reanalyze):
    p = get_project(pid)
    if active_job(pid):
        err(409, "Already processing.")
    if b.mode == "series":
        if not b.part_len or not 10 <= b.part_len <= 180:
            err(400, "Part length must be between 10 and 180 seconds.")
    elif b.min_dur < 5 or b.max_dur > 180 or b.min_dur >= b.max_dur:
        err(400, "Duration range must be between 5 and 180 seconds, with min below max.")
    if not pipeline.load_transcript(pid):
        err(400, "There is no transcript yet.")
    db.update("projects", pid, prefs={**(p.get("prefs") or {}), **{k: v for k, v in b.model_dump().items() if v is not None}})
    return {"job_id": jobs.submit("analyze", pipeline.reanalyze_job(pid), project_id=pid)}


@router.get("/projects/{pid}/transcript")
def get_transcript(pid: str):
    get_project(pid)
    tr = pipeline.load_transcript(pid)
    if not tr:
        err(404, "No transcript yet.")
    return tr


@router.put("/projects/{pid}/words")
def edit_words(pid: str, body: dict):
    get_project(pid)
    tr = pipeline.load_transcript(pid)
    if not tr:
        err(404, "No transcript.")
    for e in body.get("edits", []):
        i = int(e["i"])
        if not 0 <= i < len(tr["words"]):
            continue
        w = tr["words"][i]
        if "w" in e:
            w["w"] = str(e["w"])[:60]
        if "s" in e:
            w["s"] = round(float(e["s"]), 3)
        if "e" in e:
            w["e"] = round(max(float(e["e"]), w["s"] + 0.05), 3)
    pipeline.paths(pid)["transcript"].write_text(json.dumps(tr, ensure_ascii=False))
    return {"ok": True}


# ================================================================ clips

@router.get("/clips")
def library():
    out = []
    projects = {p["id"]: p for p in db.many("SELECT id, name FROM projects")}
    for c in db.many("SELECT * FROM clips ORDER BY created_at DESC"):
        if c["project_id"] in projects:
            v = view_clip(c)
            v["project_name"] = projects[c["project_id"]]["name"]
            out.append(v)
    return {"clips": out}


class NewClip(BaseModel):
    start: float
    end: float
    title: str = "Custom clip"


@router.post("/projects/{pid}/clips")
def add_clip(pid: str, b: NewClip):
    p = get_project(pid)
    dur = (p.get("meta") or {}).get("duration") or 1e9
    if b.end - b.start < 1 or b.start < 0 or b.start >= dur:
        err(400, "Invalid clip range.")
    idx = (db.one("SELECT MAX(idx) m FROM clips WHERE project_id=?", (pid,))["m"] or -1) + 1
    words = pipeline.clip_words(pid, b.start, min(b.end, dur))
    comps, ev, kind = analyze.score_window(analyze.sentences([{k: w[k] for k in ("w", "s", "e")} for w in words])) if words else ({k: 0 for k in analyze.W}, [], "Insight")
    cid = db.new_id()
    db.insert("clips", dict(id=cid, project_id=pid, idx=idx, title=b.title, start=b.start, end=min(b.end, dur), score=analyze.total(comps), scores=comps,
                            reason="Added manually.", hook="", caption="", kind=kind, selected=1, settings=pipeline.clip_defaults(), social=None, exports=[], created_at=time.time()))
    return view_clip(get_clip(cid))


class ClipPatch(BaseModel):
    title: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    selected: Optional[bool] = None
    hook: Optional[str] = None
    caption: Optional[str] = None
    settings: Optional[dict] = None


@router.patch("/clips/{cid}")
def patch_clip(cid: str, b: ClipPatch):
    c = get_clip(cid)
    p = get_project(c["project_id"])
    f = {}
    if b.title is not None:
        f["title"] = b.title[:200]
    if b.hook is not None:
        f["hook"] = b.hook[:300]
    if b.caption is not None:
        f["caption"] = b.caption[:2000]
    if b.selected is not None:
        f["selected"] = int(b.selected)
    s, e = (b.start if b.start is not None else c["start"]), (b.end if b.end is not None else c["end"])
    if b.start is not None or b.end is not None:
        dur = (p.get("meta") or {}).get("duration") or 1e9
        if s < 0 or e > dur + 0.01 or e - s < 1:
            err(400, f"Invalid range: the clip must be at least 1 s long and inside the video (0 – {dur:.1f} s).")
        f["start"], f["end"] = round(s, 2), round(e, 2)
    if b.settings is not None:
        f["settings"] = settings_store._merge(pipeline.clip_settings(c), b.settings)
    db.update("clips", cid, **f)
    return view_clip(get_clip(cid))


@router.delete("/clips/{cid}")
def delete_clip(cid: str):
    get_clip(cid)
    db.delete("clips", "id=?", (cid,))
    return {"ok": True}


@router.get("/clips/{cid}/words")
def get_clip_words(cid: str):
    c = get_clip(cid)
    return {"words": pipeline.clip_words(c["project_id"], c["start"], c["end"])}


def preview_file(pid: str, cid: str):
    return pipeline.preview_paths(pid, cid)[0]


@router.get("/clips/{cid}/preview-info")
def preview_info(cid: str):
    c = get_clip(cid)
    info = pipeline.preview_info(c)
    return {"ready": bool(info), **(info or {})}


@router.post("/clips/{cid}/preview")
def make_preview(cid: str):
    c = get_clip(cid)
    p = get_project(c["project_id"])
    if not (p.get("meta") or {}).get("yt_authorized"):
        err(400, "Downloading is not enabled for this project.")
    if pipeline.preview_info(c):
        return {"ready": True}
    return {"ready": False, "job_id": jobs.submit("preview", pipeline.preview_job(cid), project_id=c["project_id"], clip_id=cid)}


@router.get("/clips/{cid}/framing")
def framing(cid: str, layout: str = "smart"):
    c = get_clip(cid)
    p = get_project(c["project_id"])
    P = pipeline.paths(p["id"])
    pv = pipeline.preview_info(c)
    if not P["proxy"].exists() and not pv:
        err(400, "No video is attached.")
    cache = P["work"] / f"framing3-{cid}-{c['start']:.2f}-{c['end']:.2f}.json"
    if not P["proxy"].exists() and cache.exists() and pv is None:
        cache.unlink()
    if cache.exists():
        return json.loads(cache.read_text())
    st = pipeline.clip_settings(c)
    if P["proxy"].exists():
        meta, video, off = p["meta"], P["proxy"], 0.0
    else:  # URL-only mode: track on the temporary preview segment (times relative to it)
        meta, video, off = {"width": pv["width"], "height": pv["height"], "fps": pv["fps"], "duration": pv["duration"]}, preview_file(p["id"], cid), pv["seg_start"]
    pl = render.plan(meta, st, None)
    res = vision.track(video, c["start"] - off, c["end"] - off, meta["width"], meta["height"], pl["crop_w"])
    out = {**res, "src_w": meta["width"], "src_h": meta["height"]}
    P["work"].mkdir(exist_ok=True)
    cache.write_text(json.dumps(out))
    return out


@router.post("/clips/{cid}/plan")
def plan(cid: str, body: dict):
    c = get_clip(cid)
    p = get_project(c["project_id"])
    st = settings_store._merge(pipeline.clip_settings(c), body.get("settings") or {})
    if not p.get("meta") or not p["meta"].get("width"):
        err(400, "No video attached.")
    return render.plan(p["meta"], st, None)


@router.post("/clips/{cid}/tighten-plan")
def tighten_plan(cid: str, body: Optional[dict] = None):
    """What tightening would cut from this clip with the given options: used for the live summary and for skipping the cuts in the preview."""
    from ..services import tighten
    c = get_clip(cid)
    p = get_project(c["project_id"])
    opts = {**(pipeline.clip_settings(c).get("tighten") or {}), **((body or {}).get("settings") or {})}
    words = pipeline.clip_words(c["project_id"], c["start"], c["end"])
    fps = float(((p.get("meta") or {}).get("fps")) or 30)
    plan = tighten.plan(words, c["start"], c["end"], opts, fps)
    return {"removed": [[a, b] for a, b in plan["removed"]], "pauses": plan["pauses"], "fillers": plan["fillers"], "removed_seconds": plan["removed_seconds"],
            "new_duration": plan["new_duration"], "duration": plan["duration"]}


@router.post("/clips/{cid}/render")
def render_one(cid: str, body: Optional[dict] = None):
    c = get_clip(cid)
    return {"job_id": jobs.submit("render", pipeline.render_job(cid, (body or {}).get("settings")), project_id=c["project_id"], clip_id=cid)}


@router.post("/projects/{pid}/render")
def render_many(pid: str, body: dict):
    p = get_project(pid)
    ids = body.get("clip_ids") or [c["id"] for c in db.many("SELECT id FROM clips WHERE project_id=? AND selected=1", (pid,))]
    if not ids:
        err(400, "Select at least one clip.")
    out = []
    for cid in ids:
        get_clip(cid)
        out.append({"clip_id": cid, "job_id": jobs.submit("render", pipeline.render_job(cid, body.get("settings")), project_id=pid, clip_id=cid)})
    return {"jobs": out}


@router.post("/clips/{cid}/social")
def gen_social(cid: str):
    c = get_clip(cid)
    words = pipeline.clip_words(c["project_id"], c["start"], c["end"])
    text = " ".join(w["w"] for w in words)
    p = get_project(c["project_id"])
    s = social.generate(text, c["hook"] or c["title"], c["title"] or p["name"])
    db.update("clips", cid, social=s)
    return s


@router.get("/clips/{cid}/thumbnails")
def thumbs(cid: str):
    c = get_clip(cid)
    p = get_project(c["project_id"])
    if not p.get("video_path") or not Path(p["video_path"]).exists():
        err(400, "Thumbnails need the original video file.")
    try:
        return {"frames": pipeline.candidate_frames(c, p)}
    except ffmpeg.MediaError as e:
        err(500, str(e))


@router.post("/clips/{cid}/thumbnail")
def thumb(cid: str, body: dict):
    c = get_clip(cid)
    p = get_project(c["project_id"])
    final = bool(body.get("final"))
    try:
        out = pipeline.compose_thumbnail(c, p, body, final)
    except (OSError, ValueError, KeyError) as e:
        err(400, f"Could not build the thumbnail: {e}")
    if final:
        dest = pipeline.paths(p["id"])["exports"]
        dest.mkdir(exist_ok=True)
        name = f"thumb-{cid[:6]}-{int(time.time())}.png"
        shutil.copy(out, dest / name)
        return {"url": f"/api/download/{p['id']}/exports/{name}", "file": name}
    return {"url": pipeline.media_url(p["id"], out)}


@router.get("/clips/{cid}/srt")
def srt(cid: str):
    c = get_clip(cid)
    words = pipeline.clip_words(c["project_id"], c["start"], c["end"])
    rel = [{"w": w["w"], "s": w["s"] - c["start"], "e": w["e"] - c["start"]} for w in words]
    cs = pipeline.clip_settings(c)
    rel = captions.filter_hidden(rel, (cs.get("caption") or {}).get("hidden"))
    from ..services import tighten
    plan = tighten.plan(words, c["start"], c["end"], cs.get("tighten") or {})
    rel = tighten.remap_words(rel, plan["removed"])
    d = pipeline.paths(c["project_id"])["work"]
    d.mkdir(exist_ok=True)
    f = d / f"{cid}.srt"
    f.write_text(captions.build_srt(rel), encoding="utf-8")
    return FileResponse(f, filename=f"{re.sub(r'[^A-Za-z0-9]+', '-', c['title'])[:40] or 'clip'}.srt", media_type="application/x-subrip")


@router.delete("/clips/{cid}/exports/{file}")
def delete_export(cid: str, file: str):
    c = get_clip(cid)
    keep = [e for e in (c["exports"] or []) if e["file"] != file]
    for e in (c["exports"] or []):
        if e["file"] == file:
            (PROJECTS_DIR / c["project_id"] / "exports" / e["file"]).unlink(missing_ok=True)
            (PROJECTS_DIR / c["project_id"] / "exports" / e["srt"]).unlink(missing_ok=True)
    db.update("clips", cid, exports=keep)
    return {"ok": True}


@router.get("/download/{pid}/exports/{file}")
def download(pid: str, file: str):
    f = (PROJECTS_DIR / pid / "exports" / file).resolve()
    if PROJECTS_DIR.resolve() not in f.parents or not f.exists():
        err(404, "File not found.")
    return FileResponse(f, filename=f.name)


@router.get("/projects/{pid}/zip")
def zip_project(pid: str, clips: str = "", clean_source: int = 0, clean_exports: int = 0):
    """One bundle folder: videos/, subtitles/, thumbnails/, text/ and INDEX.txt, clips numbered in story order.
    Optional cleanup runs only AFTER the file has been fully sent."""
    from starlette.background import BackgroundTask
    p = get_project(pid)
    want = set(filter(None, clips.split(",")))
    rows = [c for c in db.many("SELECT * FROM clips WHERE project_id=? ORDER BY start", (pid,)) if not want or c["id"] in want]
    ex = PROJECTS_DIR / pid / "exports"
    tmp = Path(tempfile.mkstemp(suffix=".zip")[1])
    root = re.sub(r"[^A-Za-z0-9]+", "-", p["name"]).strip("-")[:40] or "clips"
    n, index, included = 0, [], []
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
        for c in rows:
            latest = [e for e in (c["exports"] or []) if (ex / e["file"]).exists()]
            if not latest:
                continue
            e = latest[-1]
            n += 1
            base = f"{n:02d}-" + (re.sub(r"[^A-Za-z0-9]+", "-", c["title"]).strip("-")[:50] or "clip")
            z.write(ex / e["file"], f"{root}/videos/{base}.mp4")
            if (ex / e["srt"]).exists():
                z.write(ex / e["srt"], f"{root}/subtitles/{base}.srt")
            for t in ex.glob(f"thumb-{c['id'][:6]}-*.png"):
                z.write(t, f"{root}/thumbnails/{base}-{t.name}")
            if c.get("social"):
                sc = c["social"]
                z.writestr(f"{root}/text/{base}.txt", "TITLES\n" + "\n".join(sc.get("titles", [])) + "\n\nCAPTIONS\n" + "\n\n".join(sc.get("captions", []))
                           + "\n\nHASHTAGS\n" + " ".join(sc.get("hashtags", [])) + "\n\nDESCRIPTION\n" + str(sc.get("description", "")))
            index.append(f"{base}.mp4  |  {c['title']}  |  {c['start']:.1f}s - {c['end']:.1f}s in the original  |  {e['width']}x{e['height']}")
            included.append(c["id"])
        if n:
            z.writestr(f"{root}/INDEX.txt", f"{p['name']}\n{n} clips, in order\n\n" + "\n".join(index) + "\n")
    if n == 0:
        tmp.unlink(missing_ok=True)
        err(400, "Nothing to download yet: export at least one clip first.")

    def after():
        tmp.unlink(missing_ok=True)
        if clean_exports:
            pipeline.delete_exports(pid, included)
        if clean_source:
            pipeline.cleanup_source(pid)

    return FileResponse(tmp, filename=f"{root}.zip", media_type="application/zip", background=BackgroundTask(after))


# ================================================================ jobs

@router.get("/jobs/{jid}")
def job(jid: str):
    j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if not j:
        err(404, "Job not found.")
    return j


@router.get("/projects/{pid}/jobs")
def project_jobs(pid: str):
    return {"jobs": db.many("SELECT * FROM jobs WHERE project_id=? AND status IN ('queued','running') ORDER BY created_at", (pid,))}


@router.post("/jobs/{jid}/cancel")
def cancel(jid: str, only_queued: int = 0):
    return {"cancelled": jobs.cancel(jid, bool(only_queued))}