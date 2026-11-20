"""Download ONLY a time range of a YouTube video the user has confirmed they own / may use.
Public videos only: no cookies, no logins, no DRM circumvention. The segment is temporary and deleted after rendering."""
import logging
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("ytdl")


class DownloadError(RuntimeError):
    pass


def _friendly(msg: str) -> str:
    m = msg.lower()
    if "sign in" in m or "age" in m and "restrict" in m or "login" in m:
        return "This video requires a login or age verification. ClipForge only downloads public videos and will not bypass that."
    if "private" in m:
        return "This video is private."
    if "unavailable" in m or "removed" in m or "not available" in m:
        return "This video is unavailable (removed, region-locked or blocked)."
    if "live" in m and ("is live" in m or "live event" in m):
        return "This is a live broadcast. Use the live-stream recorder instead, or wait for the replay."
    if "javascript" in m or "js runtime" in m or "n challenge" in m:
        return "YouTube extraction needs a JavaScript runtime (install Node.js or Deno) and an up-to-date yt-dlp."
    if "http error 429" in m or "too many requests" in m:
        return "YouTube is rate-limiting this network. Try again later."
    return f"Download failed: {msg.strip().splitlines()[-1][:300] if msg.strip() else 'unknown error'}"


def download_segment(url: str, start: float, end: float, out_dir: Path, name: str,
                     on_progress: Optional[Callable[[float], None]] = None, cancelled: Optional[Callable[[], bool]] = None) -> Path:
    try:
        import yt_dlp
        from yt_dlp.utils import download_range_func
    except ImportError:
        raise DownloadError("yt-dlp is not installed. Run ./start.sh again to install it.")
    out_dir.mkdir(parents=True, exist_ok=True)
    tmpl = str(out_dir / f"{name}.%(ext)s")

    def hook(d):
        if cancelled and cancelled():
            raise DownloadError("Cancelled.")
        if on_progress and d.get("status") == "downloading":
            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if tot:
                on_progress(min(100.0, d.get("downloaded_bytes", 0) / tot * 100))

    opts = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b", "merge_output_format": "mp4", "outtmpl": tmpl, "noplaylist": True,
        "download_ranges": download_range_func(None, [(max(0.0, start), end)]), "force_keyframes_at_cuts": True,
        "quiet": True, "no_warnings": True, "noprogress": True, "progress_hooks": [hook], "retries": 3, "socket_timeout": 30,
        "overwrites": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except DownloadError:
        raise
    except Exception as e:  # noqa: BLE001 - yt-dlp raises many types; message is user-facing
        raise DownloadError(_friendly(str(e)))
    files = sorted(out_dir.glob(f"{name}.*"))
    files = [f for f in files if f.suffix in (".mp4", ".mkv", ".webm")]
    if not files:
        raise DownloadError("The download finished but no video file was produced.")
    return files[0]


def download_audio(url: str, out_dir: Path, on_progress: Optional[Callable[[float], None]] = None, cancelled: Optional[Callable[[], bool]] = None) -> Path:
    """Audio-only download (used only when a video has no public captions); the caller deletes it after transcription."""
    try:
        import yt_dlp
    except ImportError:
        raise DownloadError("yt-dlp is not installed. Run ./start.sh again to install it.")
    out_dir.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if cancelled and cancelled():
            raise DownloadError("Cancelled.")
        if on_progress and d.get("status") == "downloading":
            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if tot:
                on_progress(min(100.0, d.get("downloaded_bytes", 0) / tot * 100))

    opts = {"format": "ba/b", "outtmpl": str(out_dir / "audio_src.%(ext)s"), "noplaylist": True, "quiet": True, "no_warnings": True,
            "noprogress": True, "progress_hooks": [hook], "retries": 3, "socket_timeout": 30}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except DownloadError:
        raise
    except Exception as e:  # noqa: BLE001
        raise DownloadError(_friendly(str(e)))
    files = list(out_dir.glob("audio_src.*"))
    if not files:
        raise DownloadError("The audio download produced no file.")
    return files[0]
