"""Clip rendering: builds one FFmpeg filter graph (layout + enhancement + captions + hook) and encodes."""
import copy
import logging
import shutil
from pathlib import Path
from typing import Callable, Optional

from ..config import ASSETS_DIR, FONTS_DIR
from . import captions, ffmpeg, vision

log = logging.getLogger("render")
ASPECTS = {"9:16": (9, 16), "1:1": (1, 1), "16:9": (16, 9), "4:5": (4, 5)}
EVEN = lambda v: int(round(v / 2.0)) * 2  # noqa: E731


def out_size(aspect: str, res: int) -> tuple:
    a, b = ASPECTS.get(aspect, (9, 16))
    short = res
    if a <= b:  # portrait or square: width is the short side
        return EVEN(short), EVEN(short * b / a)
    return EVEN(short * a / b), EVEN(short)


def lerp_expr(points: list, idx: int, lo: str = "0", hi: str = "0") -> str:
    """Piecewise-linear ffmpeg expression over time from [[t, ...]] points; value is points[i][idx]."""
    if not points:
        return "0"
    if len(points) == 1:
        return f"{points[0][idx]:.1f}"
    expr = f"{points[-1][idx]:.1f}"
    for i in range(len(points) - 2, -1, -1):
        a, b = points[i], points[i + 1]
        dt = max(1e-3, b[0] - a[0])
        seg = f"{a[idx]:.1f}+({b[idx] - a[idx]:.2f})*(t-{a[0]:.2f})/{dt:.2f}"
        expr = f"if(lt(t,{b[0]:.2f}),{seg},{expr})"
    return expr


def _emoji_png(emoji: str, dst: Path, size: int) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
        f = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 160)
        im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((20, 10), emoji, font=f, embedded_color=True)
        im = im.crop(im.getbbox()).resize((size, size))
        im.save(dst)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("emoji render unavailable: %s", e)
        return False


def plan(src: dict, settings: dict, track: Optional[dict]) -> dict:
    """Pure calculation of output geometry / honesty notes (also used by the UI before export)."""
    sw, sh, sfps = src["width"], src["height"], src["fps"]
    aspect = settings.get("format", "9:16")
    ex = settings["export"]
    res = int(ex.get("resolution", 1080))
    W, H = out_size(aspect, res)
    ar = W / H
    zoom = settings["enhance"].get("zoom", "none")
    zf = 1.15 if zoom == "punch" else 1.0
    layout = settings.get("layout", "smart")
    notes = []
    if layout in ("smart", "center", "split"):
        if sw / sh >= ar:
            ch = sh / zf; cw = ch * ar
        else:
            cw = sw / zf; ch = cw / ar
        native_short = min(cw, ch) if ar != 1 else cw
        native_scale = (W / cw)
    else:  # blur / fill: whole frame, fitted
        fit = min(W / sw, H / sh)
        native_scale = fit
        cw, ch = sw, sh
    factor = native_scale
    if res >= 1440 and factor > 1.05:
        for lower in (1080, 720):
            W2, H2 = out_size(aspect, lower)
            res = lower
            W, H = W2, H2
            break
        notes.append(f"{ex.get('resolution')}p was reduced to {res}p: the source does not contain enough pixels for a native {ex.get('resolution')}p result.")
        factor = (W / cw) if layout in ("smart", "center", "split") else min(W / sw, H / sh)
    if factor > 1.05:
        notes.append(f"Upscaled {factor:.2f}× from the source ({int(cw)}×{int(ch)} px region) to {W}×{H}; detail is not truly {res}p.")
    fps = int(ex.get("fps", 30))
    src_fps = round(sfps)
    if fps > src_fps + 1:
        notes.append(f"{fps} fps requested but the source is {src_fps} fps; exported at {src_fps} fps (no frame invention).")
        fps = max(24, src_fps)
    return {"W": W, "H": H, "fps": fps, "res": res, "crop_w": cw, "crop_h": ch, "upscale": round(factor, 2), "notes": notes}


def render_clip(src_path: Path, src: dict, proxy: Optional[Path], clip: dict, settings: dict, words: list,
                out_path: Path, work: Path, ctx=None, on_progress: Optional[Callable[[float, str], None]] = None) -> dict:
    ffmpeg.require()
    enc = ffmpeg.encoders()
    if not enc.get("subtitles"):
        raise ffmpeg.MediaError("This FFmpeg build has no subtitle (libass) support. Install `ffmpeg-full` (see README).")
    work.mkdir(parents=True, exist_ok=True)
    start, end = float(clip["start"]), min(float(clip["end"]), src["duration"] or float(clip["end"]))
    dur = max(0.5, end - start)
    st = copy.deepcopy(settings)
    en = st["enhance"]
    ex = st["export"]
    layout = st.get("layout", "smart")
    notes: list = []

    pl = plan(src, st, None)
    W, H, fps = pl["W"], pl["H"], pl["fps"]
    sw, sh = src["width"], src["height"]
    cw, ch = pl["crop_w"], pl["crop_h"]
    notes += pl["notes"]

    track = None
    if layout in ("smart", "split"):
        if on_progress:
            on_progress(2, "Detecting faces and speakers")
        track = vision.track(proxy or src_path, start, end, sw, sh, cw, on_progress=lambda p: on_progress and on_progress(2 + p * 0.08, "Detecting faces and speakers"), ctx=ctx)
        notes.append(track["note"])
        if layout == "split" and len(track["tracks"]) < 2:
            notes.append("Split-screen needs two people on screen; used a single smart crop instead.")
            layout = "smart"
        if layout == "smart" and track["mode"] != "face":
            layout = "center"

    # ----- video graph
    chain = []
    if en.get("stabilize") and enc.get("deshake"):
        chain.append("deshake")
    cx0 = (sw - cw) / 2
    cy0 = (sh - ch) / 2
    graph = []
    if layout in ("smart", "center"):
        if layout == "smart" and track:
            pts = track["points"]
            xe = lerp_expr(pts, 1)
            ye = lerp_expr(pts, 2)
            x = f"min(max(({xe})-{cw / 2:.1f},0),{sw - cw:.1f})"
            y = f"min(max(({ye})-{ch / 2:.1f},0),{sh - ch:.1f})" if ch < sh - 2 else "0"
        else:
            x, y = f"{cx0:.1f}", f"{cy0:.1f}"
        chain.append(f"crop={int(cw)}:{int(ch)}:x='{x}':y='{y}'")
        if en.get("zoom") == "push":
            z = f"(1+0.12*t/{dur:.2f})"
            chain.append(f"scale=w='{W}*{z}':h='{H}*{z}':eval=frame:flags=bicubic,crop={W}:{H}")
        else:
            chain.append(f"scale={W}:{H}:flags=lanczos")
        graph.append("[0:v]" + ",".join(chain) + "[base]")
    elif layout == "split":
        ratio = W / (H / 2)
        t0, t1 = track["tracks"][0], track["tracks"][-1]
        gap = max(200.0, t1["cx"] - t0["cx"])
        cwh = min(sh * ratio, gap * 0.95, float(sw))  # narrow enough not to include the other person
        chh = cwh / ratio
        pos = [(min(max(t["cx"] - cwh / 2, 0), max(0, sw - cwh)), min(max(t["cy"] - chh / 2, 0), max(0, sh - chh))) for t in (t0, t1)]
        pre = (",".join(chain) + ",") if chain else ""
        graph.append(f"[0:v]{pre}split=2[sa][sb]")
        graph.append(f"[sa]crop={int(cwh)}:{int(chh)}:{pos[0][0]:.0f}:{pos[0][1]:.0f},scale={W}:{H // 2}:flags=lanczos[ta]")
        graph.append(f"[sb]crop={int(cwh)}:{int(chh)}:{pos[1][0]:.0f}:{pos[1][1]:.0f},scale={W}:{H // 2}:flags=lanczos[tb]")
        graph.append("[ta][tb]vstack=inputs=2[base]")
    elif layout == "blur":
        pre = (",".join(chain) + ",") if chain else ""
        graph.append(f"[0:v]{pre}split=2[ba][bb]")
        graph.append(f"[ba]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40,eq=brightness=-0.08[bg]")
        graph.append(f"[bb]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[fg]")
        graph.append("[bg][fg]overlay=(W-w)/2:(H-h)/2[base]")
    else:  # fill
        color = st.get("fill_color", "#101010").lstrip("#")
        pre = (",".join(chain) + ",") if chain else ""
        graph.append(f"[0:v]{pre}scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x{color}[base]")

    post = [f"fps={fps}"]
    eqs = []
    if abs(en.get("brightness", 0)) > 1e-3:
        eqs.append(f"brightness={en['brightness']:.3f}")
    if abs(en.get("contrast", 1) - 1) > 1e-3:
        eqs.append(f"contrast={en['contrast']:.3f}")
    if abs(en.get("saturation", 1) - 1) > 1e-3:
        eqs.append(f"saturation={en['saturation']:.3f}")
    if eqs:
        post.append("eq=" + ":".join(eqs))
    if en.get("sharpness", 0) > 0.01:
        post.append(f"unsharp=5:5:{min(2.0, en['sharpness']):.2f}:5:5:0")
    fi, fo = float(en.get("fade_in", 0)), float(en.get("fade_out", 0))
    if fi > 0:
        post.append(f"fade=t=in:st=0:d={fi:.2f}")
    if fo > 0:
        post.append(f"fade=t=out:st={max(0, dur - fo):.2f}:d={fo:.2f}")

    rel_words = [{"w": w["w"], "s": w["s"] - start, "e": w["e"] - start} for w in words if w["e"] > start and w["s"] < end]
    ass, overlays = captions.build_ass(rel_words, st.get("caption"), W, H, dur, st.get("hook"), st.get("ending"))
    (work / "captions.ass").write_text(ass, encoding="utf-8")
    fonts_link = work / "fonts"
    if fonts_link.is_symlink() or fonts_link.exists():
        fonts_link.unlink() if fonts_link.is_symlink() else shutil.rmtree(fonts_link)
    fonts_link.symlink_to(FONTS_DIR)
    post.append("subtitles=captions.ass:fontsdir=fonts")

    inputs = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(Path(src_path).resolve())]
    nin = 1
    last = "base"
    graph.append(f"[base]{','.join(post)}[v0]")
    last = "v0"
    for k, ov in enumerate(overlays[:30]):
        png = work / f"emoji{k}.png"
        if _emoji_png(ov["emoji"], png, int(W * 0.11)):
            inputs += ["-loop", "1", "-t", f"{dur:.2f}", "-i", str(png)]
            graph.append(f"[{last}][{nin}:v]overlay=x=(W-w)/2:y={max(0, ov['y']):.0f}:enable='between(t,{ov['start']:.2f},{ov['end']:.2f})'[v{k + 1}]")
            last = f"v{k + 1}"
            nin += 1
        else:
            notes.append("Emoji overlays are unavailable on this system; captions exported without emoji.")
            break
    graph.append(f"[{last}]format=yuv420p[vout]")

    # ----- audio graph
    achain = []
    if src["has_audio"]:
        if en.get("denoise_audio") and enc.get("afftdn"):
            achain.append("afftdn=nf=-25")
        if en.get("normalize_audio", True):
            achain.append("loudnorm=I=-14:TP=-1.5:LRA=11")
        if fi > 0:
            achain.append(f"afade=t=in:st=0:d={fi:.2f}")
        if fo > 0:
            achain.append(f"afade=t=out:st={max(0, dur - fo):.2f}:d={fo:.2f}")
    extra = []
    for key, loop in (("music", True), ("sfx", False)):
        a = (st.get("audio") or {}).get(key)
        if a and a.get("file"):
            p = ASSETS_DIR / Path(a["file"]).name
            if p.exists():
                inputs += (["-stream_loop", "-1"] if loop else []) + ["-i", str(p)]
                extra.append((nin, float(a.get("volume", 0.15 if loop else 0.8)), loop))
                nin += 1
    amap = None
    if src["has_audio"] or extra:
        parts, labels = [], []
        if src["has_audio"]:
            parts.append("[0:a]" + (",".join(achain) if achain else "anull") + "[a0]")
            labels.append("[a0]")
        for i, (idx, vol, loop) in enumerate(extra):
            lab = f"[x{i}]"
            parts.append(f"[{idx}:a]volume={vol:.2f},atrim=0:{dur:.2f},asetpts=PTS-STARTPTS{lab}")
            labels.append(lab)
        if len(labels) > 1:
            parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0[aout]")
            amap = "[aout]"
        else:
            parts[-1] = parts[-1].rsplit("[", 1)[0] + "[aout]"
            amap = "[aout]"
        graph += parts

    script = work / "graph.txt"
    script.write_text(";\n".join(graph))
    crf = {"h264": {"high": 17, "balanced": 21, "small": 26}, "h265": {"high": 20, "balanced": 24, "small": 28}}
    codec = ex.get("codec", "h264")
    q = ex.get("quality", "high")
    preset = {"high": "slow", "balanced": "medium", "small": "medium"}[q] if codec == "h264" else {"high": "medium", "balanced": "fast", "small": "fast"}[q]
    vcodec = ["-c:v", "libx264" if codec == "h264" else "libx265", "-preset", preset, "-crf", str(crf[codec][q]),
              "-pix_fmt", "yuv420p"] + (["-tag:v", "hvc1"] if codec == "h265" else [])
    if codec == "h265" and not enc.get("libx265"):
        raise ffmpeg.MediaError("H.265 export is not available in this FFmpeg build; choose H.264.")
    cmd = [*inputs, "-/filter_complex", "graph.txt", "-map", "[vout]"]
    if amap:
        cmd += ["-map", amap, "-c:a", "aac", "-b:a", "192k"]
    cmd += [*vcodec, "-movflags", "+faststart", "-t", f"{dur:.3f}", str(Path(out_path).resolve())]

    # cwd=work: relative captions/fonts/graph paths avoid every filter-escaping pitfall (and are thread-safe)
    ffmpeg.run(cmd, dur, ctx, lambda p: on_progress and on_progress(10 + p * 0.9, "Rendering video"), cwd=work)
    return {"width": W, "height": H, "fps": fps, "resolution": pl["res"], "codec": codec, "quality": q,
            "duration": round(dur, 2), "layout_used": layout, "notes": [n for n in notes if n],
            "size": out_path.stat().st_size, "upscale": pl["upscale"]}
