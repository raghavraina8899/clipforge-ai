"""Input sources: YouTube metadata/captions (no downloading) and authorized live-stream recording."""
import logging
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from ..config import FFMPEG

log = logging.getLogger("sources")
YT_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/|v/))([A-Za-z0-9_-]{11})")


def youtube_id(url: str) -> Optional[str]:
    m = YT_ID.search(url.strip())
    return m.group(1) if m else None


def _secs(v: str) -> float:
    """'7200', '7200s', '1h2m3s' -> seconds."""
    v = v.strip().lower()
    if re.fullmatch(r"\d+(\.\d+)?s?", v):
        return float(v.rstrip("s"))
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", v)
    return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m and v else 0.0


def youtube_range(url: str) -> tuple:
    """Start/end seconds carried by a YouTube link: share links use ?t=, embed-style links use start= and end=."""
    from urllib.parse import parse_qs, urlparse
    u = urlparse(url.strip())
    q = {k: v[0] for k, v in parse_qs(u.query).items() if v}
    frag = {k: v[0] for k, v in parse_qs(u.fragment).items() if v}
    start = _secs(q.get("start") or q.get("t") or frag.get("t") or "0")
    end = _secs(q.get("end") or "0")
    return (start, end) if not end or end > start else (start, 0.0)


def youtube_info(url: str) -> dict:
    vid = youtube_id(url)
    if not vid:
        raise ValueError("That does not look like a YouTube video URL (expected youtube.com/watch?v=…, youtu.be/…, or /shorts/…).")
    info = {"video_id": vid, "title": "", "author": "", "thumbnail_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}
    try:
        r = httpx.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"}, timeout=15)
        if r.status_code == 200:
            j = r.json()
            info.update(title=j.get("title", ""), author=j.get("author_name", ""), thumbnail_url=j.get("thumbnail_url") or info["thumbnail_url"])
        elif r.status_code in (401, 403):
            info["warning"] = "The video owner disabled embedding, so metadata is limited."
        elif r.status_code == 404:
            raise ValueError("YouTube reports this video does not exist or is private.")
    except httpx.HTTPError:
        info["warning"] = "Could not reach YouTube to read metadata (check your internet connection)."
    return info


def youtube_transcript(video_id: str) -> dict:
    """Public captions only. Returns {ok, segments|None, language, reason}."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return {"ok": False, "reason": "The youtube-transcript-api package is not installed."}
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "hi", "en-US", "en-GB"])
        segs = [{"start": float(s.start), "end": float(s.start + s.duration), "text": re.sub(r"\s+", " ", re.sub(r"[♪♫]|\[[^\]]*\]", " ", s.text)).strip()} for s in fetched if s.text.strip()]
        return {"ok": True, "segments": segs, "language": getattr(fetched, "language_code", "en")}
    except Exception as e:  # noqa: BLE001 - library raises many specific types; the message is user-facing
        name = e.__class__.__name__
        reason = {"TranscriptsDisabled": "The uploader disabled captions for this video.",
                  "NoTranscriptFound": "No English or Hindi captions are available for this video.",
                  "VideoUnavailable": "The video is unavailable (private, removed or region-locked).",
                  "IpBlocked": "YouTube is blocking caption requests from this network.",
                  "RequestBlocked": "YouTube is blocking caption requests from this network."}.get(name, f"Captions could not be fetched ({name}).")
        return {"ok": False, "reason": reason}


def segments_to_words(segs: list) -> list:
    """Estimate word timing inside caption segments (flagged as estimated everywhere it is used)."""
    words = []
    for s in segs:
        toks = s["text"].split()
        if not toks:
            continue
        span = max(0.2, s["end"] - s["start"])
        step = span / len(toks)
        for i, t in enumerate(toks):
            words.append({"w": t, "s": round(s["start"] + i * step, 3), "e": round(s["start"] + (i + 1) * step, 3)})
    return words


# ------------------------------------------------------------------ live recording

BLOCKED_HOSTS = ("youtube.com", "youtu.be", "twitch.tv", "netflix.com", "primevideo.com", "hotstar.com", "disneyplus.com", "instagram.com", "facebook.com", "tiktok.com")


def validate_stream_url(url: str) -> str:
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https", "rtmp", "rtmps", "rtsp", "srt", "udp"):
        raise ValueError("Unsupported stream address. Use a direct stream URL such as an HLS (.m3u8) link, RTMP, RTSP or SRT address.")
    host = (u.hostname or "").lower()
    if any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS):
        raise ValueError("That is a web page address, not a direct stream. ClipForge only records direct stream URLs you are authorized to use "
                         "(your own server, OBS/RTMP output, a camera). It does not extract streams from platform pages or bypass DRM / login.")
    return url.strip()


class Recorder:
    """Records an authorized stream into ts segments; pause = stop segment, resume = new segment."""

    def __init__(self, url: str, folder: Path):
        self.url, self.dir = url, folder
        self.segments: list = []
        self.proc: Optional[subprocess.Popen] = None
        self.state = "idle"  # idle | recording | paused | stopped
        self.t0 = 0.0
        self.elapsed = 0.0
        self.error = ""
        self.lock = threading.Lock()

    def _spawn(self) -> None:
        seg = self.dir / f"seg{len(self.segments):03d}.ts"
        log_f = open(self.dir / f"seg{len(self.segments):03d}.log", "w")
        self.proc = subprocess.Popen([FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", self.url, "-c", "copy", "-f", "mpegts", str(seg)],
                                     stdout=subprocess.DEVNULL, stderr=log_f)
        self.segments.append(seg)
        self.t0 = time.time()
        for _ in range(100):  # up to ~20 s: copy-mode recording must wait for the stream's next keyframe
            time.sleep(0.2)
            if self.proc.poll() is not None:
                tail = (self.dir / seg.with_suffix(".log").name).read_text()[-400:]
                self.segments.pop()
                self.proc = None
                raise RuntimeError(f"Could not read the stream: {tail.strip().splitlines()[-1] if tail.strip() else 'unknown error'}")
            if seg.exists() and seg.stat().st_size > 0:
                break
        else:
            self.proc.kill(); self.proc = None; self.segments.pop()
            raise RuntimeError("The stream did not deliver any data within 20 seconds (it may be offline, or have very sparse keyframes).")

    def _halt(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.proc:
            self.elapsed += time.time() - self.t0
        self.proc = None

    def start(self):
        with self.lock:
            if self.state != "idle":
                raise RuntimeError("Recording already started.")
            self._spawn(); self.state = "recording"

    def pause(self):
        with self.lock:
            if self.state != "recording":
                raise RuntimeError("Not recording.")
            self._halt(); self.state = "paused"

    def resume(self):
        with self.lock:
            if self.state != "paused":
                raise RuntimeError("Not paused.")
            self._spawn(); self.state = "recording"

    def stop(self) -> Path:
        with self.lock:
            if self.state in ("idle", "stopped"):
                raise RuntimeError("Nothing has been recorded.")
            self._halt(); self.state = "stopped"
            segs = [s for s in self.segments if s.exists() and s.stat().st_size > 1000]
            if not segs:
                raise RuntimeError("No data was recorded.")
            lst = self.dir / "segments.txt"
            lst.write_text("".join(f"file '{s.name}'\n" for s in segs))
            out = self.dir / "recording.mkv"
            r = subprocess.run([FFMPEG, "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)],
                               capture_output=True, text=True, cwd=self.dir)
            if r.returncode != 0 or not out.exists():
                raise RuntimeError(f"Could not assemble the recording: {r.stderr[-300:]}")
            return out

    def status(self) -> dict:
        el = self.elapsed + ((time.time() - self.t0) if self.state == "recording" else 0)
        if self.state == "recording" and self.proc and self.proc.poll() is not None:
            self.error = "The stream ended or the connection dropped. Press Stop to keep what was recorded."
            self.elapsed += time.time() - self.t0
            self.state = "paused"
            self.proc = None
        size = sum(s.stat().st_size for s in self.segments if s.exists())
        return {"state": self.state, "elapsed": round(el, 1), "bytes": size, "error": self.error}


RECORDERS: dict = {}
