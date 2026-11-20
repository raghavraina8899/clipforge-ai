"""Brand kit: logo overlay, intro/outro joining, validation."""
import subprocess

import pytest
from PIL import Image

from app import config, pipeline
from app.services import brand, ffmpeg, render, settings_store
from test_media import need_captions, probe_json  # noqa: F401
from conftest import make_words


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    d = brand.BRAND_DIR
    logo = d / "test_logo.png"
    Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(logo)
    intro = d / "test_intro.mp4"
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:r=25:d=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(intro)], check=True)
    still = d / "test_outro.png"
    Image.new("RGB", (800, 800), (0, 160, 0)).save(still)
    return {"logo": logo.name, "intro": intro.name, "outro": still.name}


def make_kit(assets, **over):
    kit = brand.clean_kit({"id": "k1", "name": "Test", "logo": {"file": assets["logo"], "pos": "tr", "size": 0.2}, "intro": {"file": assets["intro"]}, "outro": {"file": assets["outro"]}})
    kit.update(over)
    s = settings_store.load()
    s["brands"] = [kit]
    settings_store.save(s)
    return kit


def test_clean_kit_validates_everything():
    k = brand.clean_kit({"name": "  ", "logo": {"file": "../../etc/passwd", "pos": "nowhere", "size": 99, "opacity": -3}, "intro": {"file": "missing.mp4"}})
    assert k["name"] == "My brand" and k["logo"]["file"] == "" and k["logo"]["pos"] == "tr" and k["logo"]["size"] == 0.6 and k["logo"]["opacity"] == 0.1
    assert k["intro"]["file"] == "" and k["id"]


def test_logo_positions(assets):
    for pos, (xs, ys) in {"tl": ("43", "43"), "br": ("W-w-43", "H-h-43"), "bc": ("(W-w)/2", "H-h-43")}.items():
        lo = brand.logo_overlay({"logo": {"file": assets["logo"], "pos": pos, "size": 0.2, "margin": 0.04}}, 1080, 1920)
        assert (lo["x"], lo["y"]) == (xs, ys) and lo["scale_w"] == 216
    assert brand.logo_overlay({"logo": {"file": ""}}, 1080, 1920) is None


def test_media_info(assets):
    assert brand.media_info(brand.path_of(assets["logo"]))["image"] is True
    assert 1.9 < brand.media_info(brand.path_of(assets["intro"]))["duration"] < 2.2


def test_garbage_collection_removes_unused_files(assets):
    make_kit(assets)
    stray = brand.BRAND_DIR / "stray.png"
    Image.new("RGB", (4, 4)).save(stray)
    assert brand.collect_garbage() >= 1 and not stray.exists() and brand.path_of(assets["logo"])


def test_render_with_logo_intro_and_outro(tmp_path, test_video, assets):
    need_captions()
    make_kit(assets)
    src = ffmpeg.probe(test_video)
    st = pipeline.clip_defaults()
    st["layout"], st["export"]["quality"] = "center", "small"
    st["brand"] = {"id": "k1", "logo": True, "intro": True, "outro": True}
    words = make_words("hello there everyone watching this test.", start=0.5, per=0.4)
    out = tmp_path / "b.mp4"
    info = render.render_clip(test_video, src, None, {"start": 0.0, "end": 6.0}, st, words, out, tmp_path / "w")
    j = probe_json(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next(s for s in j["streams"] if s["codec_type"] == "audio")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert 10.0 < float(j["format"]["duration"]) < 10.8                 # 2 s intro + 6 s clip + 2.5 s still outro
    assert abs(float(v["duration"]) - float(a["duration"])) < 0.15      # still in sync after joining
    assert info["srt_words"][0]["s"] >= 2.4                              # subtitles shifted past the intro
    assert any("intro" in n and "outro" in n for n in info["notes"]) and any("Logo" in n for n in info["notes"])


def test_logo_really_appears_and_toggles_off(tmp_path, test_video, assets):
    need_captions()
    from PIL import ImageChops
    make_kit(assets)
    src = ffmpeg.probe(test_video)

    def frame(name, brand_opts):
        st = pipeline.clip_defaults()
        st["layout"], st["export"]["quality"] = "center", "small"
        st["brand"] = brand_opts
        out = tmp_path / f"{name}.mp4"
        render.render_clip(test_video, src, None, {"start": 0.0, "end": 3.0}, st, [], out, tmp_path / name)
        png = tmp_path / f"{name}.png"
        subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-ss", "1", "-i", str(out), "-frames:v", "1", str(png)], check=True)
        return Image.open(png).convert("RGB")

    plain = frame("plain", {"id": "", "logo": True, "intro": False, "outro": False})
    logo = frame("logo", {"id": "k1", "logo": True, "intro": False, "outro": False})
    off = frame("off", {"id": "k1", "logo": False, "intro": False, "outro": False})
    top_right = (700, 40, 1060, 260)
    d = lambda a, b: sum(ImageChops.difference(a.crop(top_right).convert("L"), b.crop(top_right).convert("L")).getdata()) / (360 * 220)  # noqa: E731
    assert d(plain, logo) > 5             # a red logo appears in the top-right corner
    assert d(plain, off) < d(plain, logo) / 5   # switching it off removes it


def test_default_brand_has_no_effect(tmp_path, test_video):
    need_captions()
    s = settings_store.load()
    s["brands"] = []
    settings_store.save(s)
    st = pipeline.clip_defaults()
    st["layout"], st["export"]["quality"] = "center", "small"
    out = tmp_path / "d.mp4"
    info = render.render_clip(test_video, ffmpeg.probe(test_video), None, {"start": 0.0, "end": 4.0}, st, [], out, tmp_path / "w")
    assert abs(float(probe_json(out)["format"]["duration"]) - 4.0) < 0.3 and not any("Logo" in n for n in info["notes"])
