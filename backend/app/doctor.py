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


def _r(ok, detail, fix="", level="error"):
    return {"ok": bool(ok), "detail": detail, "fix": "" if ok else fix, "level": "ok" if ok else level}


def c_python():
    py = sys.version_info
    return _r(py >= (3, 10), f"Python {py.major}.{py.minor}.{py.micro}", "Install Python 3.12 (Mac: brew install python@3.12), delete backend/.venv, then run ./start.sh again.", "warn")


def c_ffmpeg():
    ff, fp = config.FFMPEG, config.FFPROBE
    return _r(ff and fp, (_cmd([ff, "-version"]).splitlines() or ["not found"])[0] if ff else "not found", "Mac: ./setup-mac.sh (or brew install ffmpeg-full). Linux: sudo apt install ffmpeg.")


def c_libass():
    if not config.FFMPEG:
        return _r(False, "FFmpeg missing", "Install FFmpeg first.")
    ok = re.search(r"\bsubtitles\b", _cmd([config.FFMPEG, "-hide_banner", "-filters"])) is not None
    return _r(ok, "subtitles filter " + ("found" if ok else "missing"), "Your FFmpeg has no caption support. Mac: brew uninstall ffmpeg && brew install ffmpeg-full.")


def c_x264():
    if not config.FFMPEG:
        return _r(False, "FFmpeg missing", "Install FFmpeg first.")
    ok = "libx264" in _cmd([config.FFMPEG, "-hide_banner", "-encoders"])
    return _r(ok, "libx264 " + ("found" if ok else "missing"), "Install a full FFmpeg build (Mac: brew install ffmpeg-full).")


def c_whisper():
    wv = _v("faster-whisper")
    return _r(bool(wv), f"faster-whisper {wv or 'missing'}", "Run ./start.sh again to install the Python packages.")


def c_av():
    av = _v("av")
    if not av:
        return _r(False, "av missing", "Run ./start.sh again.")
    return _r(int(av.split(".")[0]) < 17, f"av {av}", "Run: backend/.venv/bin/pip install 'av>=14,<17'")


def c_opencv():
    cv = _v("opencv-python-headless")
    try:
        import cv2
        ok = hasattr(cv2, "CascadeClassifier")
    except Exception:  # noqa: BLE001
        ok = False
    return _r(ok, f"opencv {cv or 'missing'}", "Run: backend/.venv/bin/pip install 'opencv-python-headless>=4.10,<5'")


def c_ytdlp():
    yd = _v("yt-dlp")
    return _r(bool(yd), f"yt-dlp {yd or 'missing'}", "Run ./start.sh again.", "warn")


def c_ejs():
    ejs, js = _v("yt-dlp-ejs"), shutil.which("node") or shutil.which("deno")
    return _r(bool(ejs and js), f"yt-dlp-ejs {ejs or 'missing'}, runtime: {js or 'none'}", "Install Node.js (Mac: brew install node) and run: backend/.venv/bin/pip install -U 'yt-dlp[default]'", "warn")


def c_datadir():
    d = config.DATA_DIR
    try:
        d.mkdir(parents=True, exist_ok=True)
        t = d / ".write_test"
        t.write_text("x")
        t.unlink()
        return _r(True, str(d))
    except OSError:
        return _r(False, str(d), "Set FRAMEFLOW_DATA to a folder you can write to.")


def c_disk():
    d = config.DATA_DIR
    free = shutil.disk_usage(d if d.exists() else Path.home()).free / 1e9
    return _r(free >= 5, f"{free:.1f} GB free", "Free some space on the Storage page: videos need several GB.", "error" if free < 2 else "warn")


def c_sync():
    d = str(config.DATA_DIR)
    synced = any(x in d for x in ("com~apple~CloudDocs", "/Desktop/", "/Documents/", "Dropbox", "OneDrive"))
    return _r(not synced, "synced folder" if synced else "local folder", "Set FRAMEFLOW_DATA to a folder outside Desktop/Documents/Dropbox.", "warn")


def c_fonts():
    n = len(list(config.FONTS_DIR.glob("*.ttf")))
    return _r(n > 0, f"{n} fonts", "Run ./scripts/fetch_fonts.sh (needs internet). System fonts still work.", "warn")


def c_model():
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    have = [p.name.split("--")[-1] for p in cache.glob("models--Systran--faster-whisper-*")] if cache.exists() else []
    return _r(bool(have), ("cached: " + ", ".join(have)) if have else "not downloaded yet",
              "Downloads automatically the first time you process a video (needs internet, ~480 MB for 'small').", "warn")


def _net(url: str):
    import httpx
    try:
        r = httpx.get(url, timeout=5, follow_redirects=True)
        return _r(r.status_code < 500, f"HTTP {r.status_code}", "Check your internet connection / VPN.", "warn")
    except Exception as e:  # noqa: BLE001
        return _r(False, e.__class__.__name__, "Check your internet connection / VPN / firewall.", "warn")


# (id, name, function, needs_network)
REGISTRY = [
    ("python", "Python 3.10 or newer", c_python, False), ("ffmpeg", "FFmpeg installed", c_ffmpeg, False),
    ("libass", "FFmpeg can burn in captions (libass)", c_libass, False), ("x264", "FFmpeg can write H.264 video", c_x264, False),
    ("whisper", "Speech recognition (faster-whisper)", c_whisper, False), ("av", "Audio library compatible with faster-whisper", c_av, False),
    ("opencv", "Face detection (OpenCV 4.x)", c_opencv, False), ("ytdlp", "YouTube downloader (yt-dlp, only for links)", c_ytdlp, False),
    ("ejs", "YouTube challenge solver + JavaScript runtime", c_ejs, False), ("datadir", "Data folder is writable", c_datadir, False),
    ("disk", "Free disk space", c_disk, False), ("sync", "Data is not inside a cloud-synced folder", c_sync, False),
    ("fonts", "Caption fonts", c_fonts, False), ("model", "Speech model downloaded", c_model, False),
    ("net_hf", "Reach Hugging Face (model download)", lambda: _net("https://huggingface.co"), True),
    ("net_yt", "Reach YouTube (links)", lambda: _net("https://www.youtube.com/generate_204"), True),
]


def steps(network: bool = True) -> list:
    return [{"id": i, "name": n} for i, n, _, net in REGISTRY if network or not net]


def run_check(check_id: str) -> dict:
    for i, n, fn, _ in REGISTRY:
        if i == check_id:
            try:
                return {"id": i, "name": n, **fn()}
            except Exception as e:  # noqa: BLE001 - a crashing check must not break the run
                return {"id": i, "name": n, **_r(False, f"check crashed: {e.__class__.__name__}: {e}", "Run the diagnostic report and send it to whoever is helping you.", "warn")}
    raise KeyError(check_id)


def run_checks(network: bool = True) -> list:
    return [run_check(s["id"]) for s in steps(network)]


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
