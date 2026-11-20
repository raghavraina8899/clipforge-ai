"""System check: finds the usual reasons Frameflow does not work on a machine and says how to fix each one.
Usable without the server:  backend/.venv/bin/python -m app.doctor"""
import importlib.metadata as md
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import config


def _v(pkg: str) -> str:
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return ""


def _cmd(cmd: list, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception:  # noqa: BLE001
        return ""


def run_checks(network: bool = True) -> list:
    out: list = []

    def add(id_, name, ok, detail, fix="", level=None):
        out.append({"id": id_, "name": name, "ok": bool(ok), "level": "ok" if ok else (level or "error"), "detail": detail, "fix": "" if ok else fix})

    py = sys.version_info
    add("python", "Python 3.10 or newer", py >= (3, 10), f"Python {py.major}.{py.minor}.{py.micro}",
        "Install Python 3.12 (Mac: brew install python@3.12), delete backend/.venv, then run ./start.sh again.", None if py >= (3, 10) else "warn")

    ff, fp = config.FFMPEG, config.FFPROBE
    add("ffmpeg", "FFmpeg installed", ff and fp, (_cmd([ff, "-version"]).splitlines() or ["not found"])[0] if ff else "not found",
        "Mac: ./setup-mac.sh (or brew install ffmpeg-full). Linux: sudo apt install ffmpeg.")
    if ff:
        filters = _cmd([ff, "-hide_banner", "-filters"])
        enc = _cmd([ff, "-hide_banner", "-encoders"])
        add("libass", "FFmpeg can burn in captions (libass)", re.search(r"\bsubtitles\b", filters) is not None, "subtitles filter " + ("found" if re.search(r"\bsubtitles\b", filters) else "missing"),
            "Your FFmpeg has no caption support. Mac: brew uninstall ffmpeg && brew install ffmpeg-full.")
        add("x264", "FFmpeg can write H.264 video", "libx264" in enc, "libx264 " + ("found" if "libx264" in enc else "missing"), "Install a full FFmpeg build (Mac: brew install ffmpeg-full).")

    wv, av = _v("faster-whisper"), _v("av")
    add("whisper", "Speech recognition (faster-whisper)", bool(wv), f"faster-whisper {wv or 'missing'}", "Run ./start.sh again to install the Python packages.")
    if av:
        major = int(av.split(".")[0])
        add("av", "Audio library compatible with faster-whisper", major < 17, f"av {av}", "Run: backend/.venv/bin/pip install 'av>=14,<17'")
    cv = _v("opencv-python-headless")
    try:
        import cv2
        has_cc = hasattr(cv2, "CascadeClassifier")
    except Exception:  # noqa: BLE001
        has_cc = False
    add("opencv", "Face detection (OpenCV 4.x)", has_cc, f"opencv {cv or 'missing'}", "Run: backend/.venv/bin/pip install 'opencv-python-headless>=4.10,<5'")

    yd, ejs = _v("yt-dlp"), _v("yt-dlp-ejs")
    js = shutil.which("node") or shutil.which("deno")
    add("ytdlp", "YouTube downloader (yt-dlp, only for links)", bool(yd), f"yt-dlp {yd or 'missing'}", "Run ./start.sh again.", None if yd else "warn")
    if yd:
        add("ejs", "YouTube challenge solver + JavaScript runtime", bool(ejs and js), f"yt-dlp-ejs {ejs or 'missing'}, runtime: {js or 'none'}",
            "Install Node.js (Mac: brew install node) and run: backend/.venv/bin/pip install -U 'yt-dlp[default]'", "warn")

    d = config.DATA_DIR
    try:
        d.mkdir(parents=True, exist_ok=True)
        t = d / ".write_test"
        t.write_text("x")
        t.unlink()
        writable = True
    except OSError:
        writable = False
    add("datadir", "Data folder is writable", writable, str(d), "Set CLIPFORGE_DATA to a folder you can write to.")
    free = shutil.disk_usage(d if d.exists() else Path.home()).free / 1e9
    add("disk", "Free disk space", free >= 5, f"{free:.1f} GB free", "Free some space: videos need several GB. Use 'Delete downloaded video' or the bundle cleanup.", "error" if free < 2 else "warn")
    synced = any(s in str(d) for s in ("com~apple~CloudDocs", "/Desktop/", "/Documents/", "Dropbox", "OneDrive"))
    add("sync", "Data is not inside a cloud-synced folder", not synced, "synced folder" if synced else "local folder", "Set CLIPFORGE_DATA to a folder outside Desktop/Documents/Dropbox.", "warn")
    nfonts = len(list(config.FONTS_DIR.glob("*.ttf")))
    add("fonts", "Caption fonts", nfonts > 0, f"{nfonts} fonts", "Run ./scripts/fetch_fonts.sh (needs internet). System fonts still work.", "warn")

    cache = Path.home() / ".cache" / "huggingface" / "hub"
    have = [p.name.split("--")[-1] for p in cache.glob("models--Systran--faster-whisper-*")] if cache.exists() else []
    add("model", "Speech model downloaded", bool(have), ("cached: " + ", ".join(have)) if have else "not downloaded yet",
        "Downloads automatically the first time you process a video (needs internet, ~480 MB for 'small').", "warn")

    if network:
        import httpx
        for key, name, url in (("net_hf", "Reach Hugging Face (model download)", "https://huggingface.co"), ("net_yt", "Reach YouTube (links)", "https://www.youtube.com/generate_204")):
            try:
                r = httpx.get(url, timeout=5, follow_redirects=True)
                add(key, name, r.status_code < 500, f"HTTP {r.status_code}", "Check your internet connection / VPN.", "warn")
            except Exception as e:  # noqa: BLE001
                add(key, name, False, e.__class__.__name__, "Check your internet connection / VPN / firewall.", "warn")
    return out


def report(network: bool = True) -> str:
    lines = ["Frameflow diagnostic report", "=" * 28,
             f"OS: {platform.platform()}", f"Python: {sys.version.split()[0]}", f"Data folder: {config.DATA_DIR}", ""]
    for c in run_checks(network):
        mark = {"ok": "OK  ", "warn": "WARN", "error": "FAIL"}[c["level"]]
        lines.append(f"[{mark}] {c['name']}: {c['detail']}" + (f"\n        fix: {c['fix']}" if c["fix"] else ""))
    log = config.LOG_DIR / "clipforge.log"
    if log.exists():
        tail = log.read_text(errors="replace").splitlines()[-60:]
        lines += ["", "Last log lines:", *[re.sub(r"(api[_-]?key|x-goog-api-key)[=: ]+\S+", r"\1=***", ln)[:300] for ln in tail]]
    return "\n".join(lines)


if __name__ == "__main__":
    bad = 0
    for c in run_checks():
        mark = {"ok": "\033[32m✓\033[0m", "warn": "\033[33m!\033[0m", "error": "\033[31m✗\033[0m"}[c["level"]]
        print(f" {mark} {c['name']}: {c['detail']}")
        if c["fix"]:
            print(f"     → {c['fix']}")
        bad += c["level"] == "error"
    print("\nEverything essential looks fine." if not bad else f"\n{bad} problem(s) need fixing before Frameflow works.")
    sys.exit(1 if bad else 0)
