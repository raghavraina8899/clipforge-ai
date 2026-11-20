"""Real FFmpeg work on a generated video."""
import json
import subprocess

import pytest
from PIL import Image, ImageChops

from app import config, pipeline
from app.services import ffmpeg, render
from conftest import make_words


def probe_json(path):
    r = subprocess.run([config.FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def src(test_video):
    return ffmpeg.probe(test_video)


def need_captions():
    if not ffmpeg.encoders().get("subtitles"):
        pytest.skip("this FFmpeg has no libass (captions) support")


def test_probe(src):
    assert (src["width"], src["height"]) == (1280, 720) and 29 < src["duration"] < 31 and src["has_audio"] and src["fps"] == 30


@pytest.mark.parametrize("fmt,layout,size", [("9:16", "center", (1080, 1920)), ("9:16", "blur", (1080, 1920)), ("1:1", "center", (1080, 1080)), ("16:9", "fill", (1920, 1080))])
def test_render_formats_and_layouts(tmp_path, test_video, src, fmt, layout, size):
    need_captions()
    st = pipeline.clip_defaults()
    st["format"], st["layout"] = fmt, layout
    st["export"].update(resolution=1080, quality="small")
    words = make_words("This is a test of the caption renderer and it should burn in.", start=2.0, per=0.4)
    out = tmp_path / "o.mp4"
    info = render.render_clip(test_video, src, None, {"start": 1.0, "end": 9.0}, st, words, out, tmp_path / "w")
    j = probe_json(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == size and v["codec_name"] == "h264"
    assert any(s["codec_type"] == "audio" for s in j["streams"])
    assert abs(float(j["format"]["duration"]) - 8.0) < 0.4          # right length, audio and video in sync
    assert info["size"] > 10_000 and info["layout_used"] in ("center", "blur", "fill")


def test_hevc_export_is_tagged_for_apple_players(tmp_path, test_video, src):
    need_captions()
    if not ffmpeg.encoders().get("libx265"):
        pytest.skip("no x265")
    st = pipeline.clip_defaults()
    st["export"].update(codec="h265", quality="small", resolution=720)
    out = tmp_path / "h.mp4"
    render.render_clip(test_video, src, None, {"start": 0.0, "end": 4.0}, st, [], out, tmp_path / "w")
    v = next(s for s in probe_json(out)["streams"] if s["codec_type"] == "video")
    assert v["codec_name"] == "hevc" and v.get("codec_tag_string") == "hvc1"


def test_captions_off_and_hidden_ranges_change_the_picture(tmp_path, test_video, src):
    need_captions()
    words = make_words("alpha bravo charlie delta echo foxtrot golf hotel india juliet.", start=0.5, per=0.5)

    def frame(name, caption):
        st = pipeline.clip_defaults()
        st["layout"], st["export"]["quality"] = "center", "small"
        st["caption"].update(caption)
        out = tmp_path / f"{name}.mp4"
        render.render_clip(test_video, src, None, {"start": 0.0, "end": 6.0}, st, words, out, tmp_path / name)
        png = tmp_path / f"{name}.png"
        subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-ss", "2.2", "-i", str(out), "-frames:v", "1", str(png)], check=True)
        return Image.open(png).convert("L")

    def diff(a, b):  # mean absolute pixel difference (compression makes frames differ slightly, never byte-identical)
        return sum(ImageChops.difference(a, b).getdata()) / (a.width * a.height)

    on = frame("on", {"show": True})
    off = frame("off", {"show": False})
    hidden = frame("hid", {"show": True, "hidden": [{"start": 1.5, "end": 3.5}]})
    assert diff(on, off) > 0.5                      # captions really appear
    assert diff(hidden, off) < diff(on, off) / 5    # and a hidden range really removes them


def test_plan_reports_upscaling_honestly(src):
    st = pipeline.clip_defaults()
    st["layout"] = "center"
    st["export"].update(resolution=2160)
    p = render.plan({**src, "width": 1920, "height": 1080, "fps": 30}, st, None)
    assert p["res"] < 2160 and any("4K" in n or "2160" in n for n in p["notes"])      # 4K is refused for a 1080p source
    st["export"].update(resolution=1080, fps=60)
    p = render.plan({**src, "width": 1920, "height": 1080, "fps": 30}, st, None)
    assert p["fps"] == 30 and any("60 fps" in n for n in p["notes"]) and p["upscale"] > 1.5


def test_facecam_geometry():
    fc = {"x": 1440.0, "y": 0.0, "w": 480.0, "h": 480.0}      # corner overlay on a 1080p stream
    g = render.facecam_geometry(fc, 1920, 1080, 1080, 1920, 0.4, True)
    assert g["mode"] == "crop" and g["content"][2] <= 1440 - 8 + 2 and g["Ht"] + g["Hb"] == 1920
    fx, fy, fw, fh = g["face"]
    assert fc["x"] <= fx and fx + fw <= fc["x"] + fc["w"] + 0.01 and fc["y"] <= fy                # the face panel stays inside the overlay
    floating = render.facecam_geometry({"x": 700.0, "y": 300.0, "w": 400.0, "h": 300.0}, 1920, 1080, 1080, 1920, 0.4, True)
    assert floating["mode"] == "blur"                          # not on an edge: blurred instead of cropped out
    assert render.facecam_geometry(fc, 1920, 1080, 1080, 1920, 0.4, False)["mode"] == "keep"
