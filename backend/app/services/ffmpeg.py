"""Thin, honest wrappers around ffmpeg/ffprobe."""
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from ..config import FFMPEG, FFPROBE
from ..jobs import JobCtx

log = logging.getLogger("ffmpeg")


class MediaError(RuntimeError):
    pass


def require() -> None:
    if not FFMPEG or not FFPROBE:
        raise MediaError("FFmpeg is not installed. Install it (see README) and restart ClipForge.")


def probe(path: Path) -> dict:
    require()
    r = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise MediaError(f"This file could not be read as a video: {r.stderr.strip()[-300:] or 'unknown error'}")
    info = json.loads(r.stdout)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not v:
        raise MediaError("No video stream found in this file.")
    num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    if not fps:
        num, _, den = (v.get("r_frame_rate") or "30/1").partition("/")
        fps = float(num) / float(den or 1)
    dur = float(info.get("format", {}).get("duration") or v.get("duration") or 0)
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) in (90, 270):
        w, h = h, w
    return dict(duration=dur, width=w, height=h, fps=round(fps, 3), vcodec=v.get("codec_name"),
                acodec=a.get("codec_name") if a else None, has_audio=a is not None,
                size=int(info.get("format", {}).get("size") or 0), container=info.get("format", {}).get("format_name"))


def run(cmd: list, duration: float = 0.0, ctx: Optional[JobCtx] = None,
        on_progress: Optional[Callable[[float], None]] = None, cwd: Optional[Path] = None) -> None:
    """Run ffmpeg, parsing -progress output to report real percent. Raises MediaError with stderr tail."""
    require()
    full = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats", *map(str, cmd)]
    log.info("ffmpeg %s", " ".join(map(str, cmd))[:600])
    p = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, cwd=cwd)
    if ctx:
        ctx.procs.append(p)
    err_lines: list = []
    import threading

    def drain():
        for line in p.stderr:  # type: ignore[union-attr]
            err_lines.append(line)
            del err_lines[:-60]

    t = threading.Thread(target=drain, daemon=True)
    t.start()
    try:
        for line in p.stdout:  # type: ignore[union-attr]
            if ctx and ctx.cancelled.is_set():
                p.kill()
                break
            m = re.match(r"out_time_(?:us|ms)=(\d+)", line)
            if m and duration > 0 and on_progress:
                on_progress(min(100.0, int(m.group(1)) / 1_000_000 / duration * 100))
        p.wait()
        t.join(timeout=2)
    finally:
        if ctx and p in ctx.procs:
            ctx.procs.remove(p)
    if ctx:
        ctx.check()
    if p.returncode != 0:
        tail = "".join(err_lines)[-700:]
        raise MediaError(f"FFmpeg failed (exit {p.returncode}): {tail}")


def encoders() -> dict:
    if not FFMPEG:
        return {}
    out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    filt = subprocess.run([FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return {
        "libx264": "libx264" in out, "libx265": "libx265" in out,
        "h264_videotoolbox": "h264_videotoolbox" in out,
        "subtitles": re.search(r"\bsubtitles\b", filt) is not None,
        "gblur": "gblur" in filt, "deshake": "deshake" in filt, "afftdn": "afftdn" in filt,
    }


def extract_audio(src: Path, dst: Path, ctx=None, on_progress=None, duration=0.0, start: float = 0.0, length: Optional[float] = None) -> None:
    pre = (["-ss", f"{start:.3f}"] if start else []) + (["-t", f"{length:.3f}"] if length else [])
    run([*pre, "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dst], length or duration, ctx, on_progress)


def make_proxy(src: Path, dst: Path, duration: float, ctx=None, on_progress=None) -> None:
    run(["-i", src, "-vf", "scale=-2:'min(720,ih)',format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
         "-g", "30", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", dst], duration, ctx, on_progress)


def extract_frame(src: Path, t: float, dst: Path, width: int = 0) -> None:
    vf = ["-vf", f"scale={width}:-2"] if width else []
    run(["-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", *vf, "-q:v", "2", dst])


def audio_duration(path: Path) -> float:
    """Duration of an audio-only file (probe() insists on a video stream)."""
    require()
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise MediaError(f"Could not read the audio file: {r.stderr.strip()[-200:] or 'unknown error'}")
