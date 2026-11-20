"""Download ONLY a time range of a YouTube video the user has confirmed they own / may use.
Public videos only: no cookies, no logins, no DRM circumvention. The segment is temporary and deleted after rendering."""
import logging
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("ytdl")


class DownloadError(RuntimeError):
    pass


# YouTube regularly breaks individual clients; try several before giving up.
CLIENT_SETS = [None, ["tv"], ["mweb"], ["web_safari"], ["ios"]]


def _download(opts: dict, url: str) -> None:
    import time
    import yt_dlp
    last: Optional[Exception] = None
    errors: list = []
    for i, clients in enumerate(CLIENT_SETS):
        o = dict(opts)
        o["extractor_retries"] = 3
        o["js_runtimes"] = {"node": {}, "deno": {}}  # solve YouTube's JS challenges with whichever is installed
        if clients:
            o["extractor_args"] = {"youtube": {"player_client": clients}}
        try:
            with yt_dlp.YoutubeDL(o) as ydl:
                ydl.download([url])
            return
        except DownloadError:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            errors.append(str(e))
            msg = str(e).lower()
            # retrying with other clients cannot fix these, and hammering YouTube during a bot check prolongs the block
            if any(k in msg for k in ("private video", "removed", "does not exist", "copyright", "members-only", "live event", "not a bot")):
                break  # retrying with another client cannot fix these
            log.warning("yt-dlp attempt %d (%s) failed: %s", i + 1, clients or "default", str(e)[:200])
            time.sleep(1.5)
    # report the most informative failure, not just the last one
    for key in ("not a bot", "private video", "sign in", "live event"):
        hit = next((m for m in errors if key in m.lower()), None)
        if hit:
            raise DownloadError(_friendly(hit))
    raise DownloadError(_friendly(str(last)))


def _friendly(msg: str) -> str:
    m = msg.lower()
    if "not a bot" in m:
        return ("YouTube is asking this network to prove it is not a bot, so it blocked the download (your browser works because it is signed in). "
                "This usually passes after waiting 30-60 minutes without retrying. Updating yt-dlp or switching network (e.g. a phone hotspot) can also help.")
    if "private video" in m or "this video is private" in m:
        return "This video is private."
    if "sign in" in m or "login" in m or ("age" in m and "restrict" in m):
        return "This video requires a login or age verification. HookHunt only downloads public videos and will not bypass that."
    if "requested format is not available" in m:
        return ("YouTube offered no downloadable format for this video right now. The usual causes are YouTube's bot check or an outdated yt-dlp "
                "(update with: backend/.venv/bin/pip install -U 'yt-dlp[default]'). Try again later.")
    if "video unavailable" in m or "has been removed" in m or "not available in your country" in m or "blocked it" in m:
        return "This video is unavailable (removed, region-locked or blocked)."
    if "live event" in m or "is live" in m:
        return "This is a live broadcast. Use the live-stream recorder instead, or wait for the replay."
    if "needs to be reloaded" in m:
        return "YouTube refused the request ('page needs to be reloaded'). Try again in a few minutes."
    if "javascript" in m or "js runtime" in m or "n challenge" in m:
        return "YouTube extraction needs a JavaScript runtime (Node.js or Deno) and the yt-dlp-ejs package. Run ./start.sh again to install it."
    if "http error 429" in m or "too many requests" in m:
        return "YouTube is rate-limiting this network. Try again later."
    return f"Download failed: {msg.strip().splitlines()[-1][:300] if msg.strip() else 'unknown error'}"


def download_segment(url: str, start: float, end: float, out_dir: Path, name: str,
                     on_progress: Optional[Callable[[float], None]] = None, cancelled: Optional[Callable[[], bool]] = None,
                     max_height: int = 1080) -> Path:
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
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b", "merge_output_format": "mp4", "outtmpl": tmpl, "noplaylist": True,
        "download_ranges": download_range_func(None, [(max(0.0, start), end)]), "force_keyframes_at_cuts": True,
        "quiet": True, "no_warnings": True, "noprogress": True, "progress_hooks": [hook], "retries": 3, "socket_timeout": 30,
        "overwrites": True,
    }
    _download(opts, url)
    files = sorted(out_dir.glob(f"{name}.*"))
    files = [f for f in files if f.suffix in (".mp4", ".mkv", ".webm")]
    if not files:
        raise DownloadError("The download finished but no video file was produced.")
    return files[0]


def download_audio(url: str, out_dir: Path, on_progress: Optional[Callable[[float], None]] = None, cancelled: Optional[Callable[[], bool]] = None,
                   start: float = 0.0, end: float = 0.0) -> Path:
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

    opts = {"format": "worstaudio[ext=m4a]/worstaudio/ba[abr<=128]/ba", "outtmpl": str(out_dir / "audio_src.%(ext)s"), "noplaylist": True, "quiet": True, "no_warnings": True,
            "noprogress": True, "progress_hooks": [hook], "retries": 3, "socket_timeout": 30}
    if end > start:  # only the chosen section is downloaded
        from yt_dlp.utils import download_range_func
        opts["download_ranges"] = download_range_func(None, [(max(0.0, start), end)])
    _download(opts, url)
    files = list(out_dir.glob("audio_src.*"))
    if not files:
        raise DownloadError("The audio download produced no file.")
    return files[0]


def download_full(url: str, out_dir: Path, name: str, max_height: int = 1080,
                  on_progress: Optional[Callable[[float], None]] = None, cancelled: Optional[Callable[[], bool]] = None) -> Path:
    """Download the whole video ONCE (one request instead of one per clip). Public videos only."""
    try:
        import yt_dlp  # noqa: F401
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

    opts = {"format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b", "merge_output_format": "mp4",
            "outtmpl": str(out_dir / f"{name}.%(ext)s"), "noplaylist": True, "quiet": True, "no_warnings": True, "noprogress": True,
            "progress_hooks": [hook], "retries": 3, "socket_timeout": 30, "overwrites": True}
    _download(opts, url)
    files = [f for f in sorted(out_dir.glob(f"{name}.*")) if f.suffix in (".mp4", ".mkv", ".webm")]
    if not files:
        raise DownloadError("The download finished but no video file was produced.")
    return files[0]
