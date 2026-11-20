"""Logic that needs no video, network or model."""
import pytest

from app.services import analyze, captions, engine, hinglish, sources, ytdl
from conftest import make_words


# ---- Hinglish
@pytest.mark.parametrize("dev,roman", [("नमस्ते", "namaste"), ("आपको", "aapko"), ("समझना", "samjhna"), ("नहीं", "nahin"), ("क्या", "kya"), ("बहुत", "bahut")])
def test_hinglish_words(dev, roman):
    assert hinglish.romanize(dev) == roman


def test_hinglish_keeps_english():
    assert hinglish.romanize("भाई this is a game") == "bhai this is a game"
    assert not hinglish.has_devanagari("plain text")


# ---- captions
def test_ass_has_events_and_style():
    ass, overlays = captions.build_ass(make_words("Hello brave new world today."), {"preset": "hormozi"}, 1080, 1920, 5)
    assert "PlayResX: 1080" in ass and ass.count("Dialogue:") >= 4 and overlays == []


def test_captions_can_be_switched_off():
    ass, _ = captions.build_ass(make_words("Hello world."), {"preset": "hormozi", "show": False}, 1080, 1920, 5)
    assert "Dialogue:" not in ass


def test_hook_is_added():
    ass, _ = captions.build_ass([], {"preset": "hormozi"}, 1080, 1920, 5, {"enabled": True, "text": "Watch this", "duration": 2})
    assert "WATCH THIS" in ass


def test_hidden_ranges_drop_words():
    w = [{"w": str(i), "s": i, "e": i + 0.8} for i in range(10)]
    kept = [x["w"] for x in captions.filter_hidden(w, [{"start": 3, "end": 5.5}, {"start": 8, "end": 10}])]
    assert kept == ["0", "1", "2", "6", "7"]
    assert captions.filter_hidden(w, None) == w


def test_srt_format():
    srt = captions.build_srt(make_words("One two three four five six seven eight."))
    assert srt.startswith("1\n00:00:00,000 --> ") and "," in srt.splitlines()[1]


def test_emoji_overlay_for_keyword():
    _, overlays = captions.build_ass(make_words("make money fast."), {"preset": "hormozi", "emoji": True}, 1080, 1920, 5)
    assert overlays and overlays[0]["emoji"] == "💰"


# ---- analysis
SPEECH = ("Here is the biggest mistake people make with money. They never track what they spend. Why does this matter? "
          "Because 90 percent of rich people know their numbers. Start today, and you will thank yourself later. "
          "Now let me tell you a second story. Last year I lost three thousand dollars on a bad investment. "
          "It was painful. But here is the lesson I learned. Never invest in something you do not understand.")


def test_sentences_split_on_punctuation():
    s = analyze.sentences(make_words(SPEECH))
    assert len(s) == 10 and s[0]["text"].endswith("money.")


def test_heuristic_clips_respect_length_and_do_not_overlap():
    words = make_words(SPEECH, per=0.35, gap_after_sentence=0.3)
    dur = words[-1]["e"]
    clips = analyze.heuristic(words, dur, 8, 14, 5)
    assert clips
    for c in clips:
        assert 6 <= c["end"] - c["start"] <= 16 and 0 <= c["score"] <= 100
    for a, b in zip(clips, clips[1:]):
        assert a["end"] <= b["start"] + 0.01


def test_series_is_consecutive_and_complete():
    words = make_words(SPEECH, per=0.35, gap_after_sentence=0.3)
    res = analyze.series(words, words[-1]["e"], 10)
    clips = res["clips"]
    assert len(clips) >= 2 and clips[0]["title"].startswith("Part 1/")
    for a, b in zip(clips, clips[1:]):
        assert b["start"] >= a["end"] - 0.01          # in story order, no overlap
    assert clips[0]["start"] < 1 and clips[-1]["end"] >= words[-1]["e"] - 0.5   # covers the whole speech


def test_series_range():
    words = make_words(SPEECH, per=0.35, gap_after_sentence=0.3)
    res = analyze.series(words, words[-1]["e"], 6, start=10, end=20)
    assert res["clips"] and all(c["start"] >= 9.8 and c["end"] <= 21 for c in res["clips"])


def test_score_components_are_bounded():
    comps, _, _ = analyze.score_window(analyze.sentences(make_words(SPEECH))[:3])
    assert set(comps) == set(analyze.W) and all(0 <= v <= 100 for v in comps.values())


# ---- engine choice
def test_engine_choice_and_fallback():
    av = engine.available()
    assert av[-1] == "cpu" and engine.choose("auto")["engine"] == av[0]
    assert engine.choose("cpu")["engine"] == "cpu"
    other = next((e for e in ("mlx", "cuda") if e not in av), None)
    if other:  # asking for an engine this computer lacks falls back and explains why
        c = engine.choose(other)
        assert c["engine"] == av[0] and c["note"]


# ---- YouTube links and error messages
@pytest.mark.parametrize("url,rng", [("https://youtu.be/dQw4w9WgXcQ?t=7200", (7200, 0)), ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1h30m5s", (5405, 0)),
                                     ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&start=7200&end=10800", (7200, 10800)), ("https://youtu.be/dQw4w9WgXcQ", (0, 0))])
def test_youtube_link_ranges(url, rng):
    assert sources.youtube_id(url) == "dQw4w9WgXcQ" and sources.youtube_range(url) == rng


def test_youtube_id_rejects_other_sites():
    assert sources.youtube_id("https://example.com/x") is None


def test_stream_urls():
    assert sources.validate_stream_url("udp://127.0.0.1:9000")
    with pytest.raises(ValueError):
        sources.validate_stream_url("https://www.youtube.com/watch?v=x")
    with pytest.raises(ValueError):
        sources.validate_stream_url("ftp://x/y")


def test_download_errors_are_explained():
    assert "not a bot" in ytdl._friendly("ERROR: Sign in to confirm you’re not a bot")
    assert "no downloadable format" in ytdl._friendly("ERROR: Requested format is not available")
    assert "private" in ytdl._friendly("ERROR: Private video").lower()
