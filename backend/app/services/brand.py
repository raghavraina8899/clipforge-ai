"""Brand kit: your own logo on the video, an optional intro and outro clip, and a saved caption style per channel.
Everything is something you uploaded and chose; nothing is added automatically."""
import logging
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from ..config import ASSETS_DIR, FFMPEG, FFPROBE
from . import ffmpeg, settings_store

log = logging.getLogger("brand")
BRAND_DIR = ASSETS_DIR / "brand"
BRAND_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
POSITIONS = {"tl", "tr", "bl", "br", "tc", "bc"}
STILL_SECONDS = 2.5   # an image used as intro/outro is shown this long


def safe_name(filename: str) -> str:
    return f"{uuid.uuid4().hex[:8]}_{re.sub(r'[^A-Za-z0-9._-]+', '_', Path(filename).name)[:60]}"


def path_of(name: str) -> Optional[Path]:
    p = BRAND_DIR / Path(name or "").name
    return p if name and p.is_file() else None


def clean_kit(raw: dict) -> dict:
    """Validate and normalise one kit received from the UI."""
    logo = raw.get("logo") or {}
    pos = logo.get("pos") if logo.get("pos") in POSITIONS else "tr"
    kit = {
        "id": raw.get("id") or uuid.uuid4().hex[:8],
        "name": (str(raw.get("name") or "My brand")[:60]).strip() or "My brand",
        "logo": {"file": logo.get("file") if path_of(logo.get("file")) else "", "pos": pos,
                 "size": min(0.6, max(0.04, float(logo.get("size", 0.18)))), "opacity": min(1.0, max(0.1, float(logo.get("opacity", 1.0)))),
                 "margin": min(0.2, max(0.0, float(logo.get("margin", 0.04))))},
        "intro": {"file": (raw.get("intro") or {}).get("file") if path_of((raw.get("intro") or {}).get("file")) else ""},
        "outro": {"file": (raw.get("outro") or {}).get("file") if path_of((raw.get("outro") or {}).get("file")) else ""},
        "caption": raw.get("caption") if isinstance(raw.get("caption"), dict) else None,
    }
    return kit


def get_kit(kit_id: str) -> Optional[dict]:
    if not kit_id:
        return None
    return next((k for k in settings_store.load().get("brands", []) if k.get("id") == kit_id), None)


def referenced_files() -> set:
    out = set()
    for k in settings_store.load().get("brands", []):
        for key in ("logo", "intro", "outro"):
            f = (k.get(key) or {}).get("file")
            if f:
                out.add(Path(f).name)
    return out


def collect_garbage() -> int:
    """Delete uploaded brand files that no kit uses any more."""
    keep, n = referenced_files(), 0
    for f in BRAND_DIR.glob("*"):
        if f.is_file() and f.name not in keep:
            f.unlink(missing_ok=True)
            n += 1
    return n


def media_info(p: Path) -> dict:
    if p.suffix.lower() in IMAGE_EXT:
        from PIL import Image, UnidentifiedImageError
        try:  # a real image reader, not ffprobe (which happily "reads" plain text as a picture)
            with Image.open(p) as im:
                im.verify()
            with Image.open(p) as im:
                w, h = im.size
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise ffmpeg.MediaError("That file is not a readable image (use PNG, JPG or WEBP).")
        return {"width": w, "height": h, "duration": STILL_SECONDS, "image": True}
    i = ffmpeg.probe(p)
    return {"width": i["width"], "height": i["height"], "duration": i["duration"], "image": False, "has_audio": i["has_audio"]}


def logo_overlay(kit: dict, W: int, H: int) -> Optional[dict]:
    """Returns {file, scale_w, x, y, opacity} (ffmpeg expressions for x/y) or None."""
    lg = (kit or {}).get("logo") or {}
    f = path_of(lg.get("file"))
    if not f:
        return None
    m = int(round(min(W, H) * float(lg.get("margin", 0.04))))
    pos = lg.get("pos", "tr")
    x = {"l": f"{m}", "r": f"W-w-{m}", "c": "(W-w)/2"}[{"tl": "l", "bl": "l", "tr": "r", "br": "r", "tc": "c", "bc": "c"}[pos]]
    y = {"t": f"{m}", "b": f"H-h-{m}"}[{"tl": "t", "tr": "t", "tc": "t", "bl": "b", "br": "b", "bc": "b"}[pos]]
    return {"file": f, "scale_w": max(16, int(W * float(lg.get("size", 0.18)))), "x": x, "y": y, "opacity": float(lg.get("opacity", 1.0))}


def add_intro_outro(main: Path, kit: dict, use_intro: bool, use_outro: bool, W: int, H: int, fps: int, vcodec: list, work: Path, ctx=None,
                    on_progress=None) -> dict:
    """Join [intro] + main + [outro] into one file (re-encoded to match). Returns {intro_seconds, outro_seconds}."""
    intro = path_of((kit.get("intro") or {}).get("file")) if use_intro else None
    outro = path_of((kit.get("outro") or {}).get("file")) if use_outro else None
    if not intro and not outro:
        return {"intro_seconds": 0.0, "outro_seconds": 0.0}
    parts = [p for p in (intro, main, outro) if p]
    cmd, filt, labels = [], [], []
    n_in = 0
    info = {"intro_seconds": 0.0, "outro_seconds": 0.0}
    for idx, p in enumerate(parts):
        is_img = p.suffix.lower() in IMAGE_EXT
        mi = media_info(p)
        dur = STILL_SECONDS if is_img else mi["duration"]
        if p == intro:
            info["intro_seconds"] = dur
        elif p == outro:
            info["outro_seconds"] = dur
        cmd += (["-loop", "1", "-t", f"{dur:.3f}", "-i", str(p)] if is_img else ["-i", str(p)])
        vi = n_in
        n_in += 1
        filt.append(f"[{vi}:v]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps},format=yuv420p[v{idx}]")
        if not is_img and mi.get("has_audio"):
            filt.append(f"[{vi}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{idx}]")
        else:  # no sound in this piece: insert silence of the same length
            cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            filt.append(f"[{n_in}:a]aformat=sample_fmts=fltp:channel_layouts=stereo[a{idx}]")
            n_in += 1
        labels.append(f"[v{idx}][a{idx}]")
    filt.append("".join(labels) + f"concat=n={len(parts)}:v=1:a=1[vo][ao]")
    tmp = main.with_suffix(".brand.mp4")
    (work / "brand.txt").write_text(";\n".join(filt))
    full = [*cmd, "-/filter_complex", "brand.txt", "-map", "[vo]", "-map", "[ao]", *vcodec, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp.resolve())]
    total = sum(STILL_SECONDS if p.suffix.lower() in IMAGE_EXT else media_info(p)["duration"] for p in parts)
    ffmpeg.run(full, total, ctx, on_progress, cwd=work)
    shutil.move(str(tmp), str(main))
    return info
