"""Paths and global constants. Everything lives on the local filesystem."""
import logging
import logging.handlers
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CLIPFORGE_DATA", ROOT / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
LOG_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "clipforge.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
FONTS_DIR = ROOT / "backend" / "fonts"
ASSETS_DIR = DATA_DIR / "assets"  # user-provided music / sfx

for d in (DATA_DIR, PROJECTS_DIR, LOG_DIR, ASSETS_DIR, FONTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

def _find(name: str):
    return shutil.which(name) or next((str(Path(d) / name) for d in ("/opt/homebrew/opt/ffmpeg-full/bin", "/opt/homebrew/bin", "/usr/local/bin") if (Path(d) / name).exists()), None)


FFMPEG = _find("ffmpeg")
FFPROBE = _find("ffprobe")

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".mpg", ".mpeg", ".ts", ".flv", ".wmv", ".3gp"}
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}


def setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        return
    root.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(LOG_DIR / "clipforge.log", maxBytes=2_000_000, backupCount=3)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)
    # httpx logs full request URLs; keep it quiet so nothing sensitive can leak.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def project_dir(pid: str) -> Path:
    p = PROJECTS_DIR / pid
    p.mkdir(parents=True, exist_ok=True)
    return p
