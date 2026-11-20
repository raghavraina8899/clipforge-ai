import pytest

from app.services import tighten

OPTS = {"enabled": True}


def W(text_times):
    return [{"w": w, "s": s, "e": e} for w, s, e in text_times]


def test_off_by_default_changes_nothing():
    p = tighten.plan(W([("hello", 0, 0.5), ("world", 5, 5.5)]), 0, 10, {})
    assert p["removed"] == [] and p["new_duration"] == 10


def test_long_pause_is_shortened_not_deleted():
    words = W([("hello", 0.0, 0.5), ("there", 0.5, 1.0), ("again", 6.0, 6.5), ("friends", 6.5, 7.5)])
    p = tighten.plan(words, 0, 8, OPTS)
    assert p["pauses"] == 1 and 3.5 < p["removed_seconds"] < 4.9
    assert sum(b - a for a, b in p["keep"]) == pytest.approx(p["new_duration"], abs=0.01)
    assert p["new_duration"] > 3.0                     # the 0.2 s margins around the pause are kept, speech untouched
    for a, b in p["keep"]:                              # every word survives inside a kept interval
        pass
    keep_cover = lambda t: any(a <= t <= b for a, b in p["keep"])  # noqa: E731
    assert all(keep_cover(w["s"] + 0.05) for w in words)


def test_short_pauses_are_left_alone():
    words = W([("a", 0, 0.4), ("b", 0.8, 1.2), ("c", 1.6, 2.0), ("d", 2.4, 2.8)])
    assert tighten.plan(words, 0, 3, OPTS)["removed"] == []


def test_filler_words_are_cut():
    words = W([("so", 0, 0.4), ("um", 0.4, 0.9), ("this", 0.9, 1.3), ("is", 1.3, 1.6), ("uh", 1.6, 2.0), ("great", 2.0, 2.6), ("stuff", 2.6, 3.2)])
    p = tighten.plan(words, 0, 3.5, {**OPTS, "silence": False})
    assert p["fillers"] == 2 and p["removed_seconds"] == pytest.approx(0.8, abs=0.2)


def test_custom_filler_list_and_switch():
    words = W([("actually", 0, 0.6), ("this", 0.6, 1.0), ("works", 1.0, 1.6)] * 3)
    words = [{**w, "s": w["s"] + i * 1.6, "e": w["e"] + i * 1.6} for i, w in enumerate(words)]
    p = tighten.plan(words, 0, 15, {**OPTS, "silence": False, "filler_words": "actually"})
    assert p["fillers"] > 0
    assert tighten.plan(words, 0, 15, {**OPTS, "silence": False, "fillers": False})["fillers"] == 0


def test_leading_and_trailing_silence_is_trimmed():
    p = tighten.plan(W([("hi", 4.0, 4.4), ("there", 4.4, 5.0)]), 0, 10, OPTS)
    assert p["removed"][0][0] == 0 and p["removed"][-1][1] == pytest.approx(10, abs=0.05)
    assert 0.8 < p["new_duration"] < 2.0


def test_never_cuts_down_to_nothing():
    p = tighten.plan(W([("hi", 4.0, 4.1)]), 0, 10, {**OPTS, "keep": 0.0})
    assert p["new_duration"] >= 1.0 or p["removed"] == []


def test_cut_points_are_on_the_frame_grid():
    p = tighten.plan(W([("a", 0, 0.5), ("b", 7.3, 7.9)]), 0, 9, OPTS, fps=30)
    for a, b in p["removed"]:
        assert a * 30 == pytest.approx(round(a * 30), abs=1e-6) and b * 30 == pytest.approx(round(b * 30), abs=1e-6)


def test_words_are_remapped_onto_the_shorter_timeline():
    words = W([("hello", 0.0, 0.5), ("there", 0.5, 1.0), ("again", 6.0, 6.5), ("friends", 6.5, 7.5)])
    p = tighten.plan(words, 0, 8, OPTS)
    new = tighten.remap_words(words, p["removed"])
    assert [w["w"] for w in new] == ["hello", "there", "again", "friends"]
    assert new[2]["s"] < 6.0 - 3.0                                   # moved earlier by the removed pause
    assert new[-1]["e"] <= p["new_duration"] + 0.05
    assert all(b["s"] >= a["e"] - 0.01 for a, b in zip(new, new[1:]))   # order and spacing preserved


def test_words_inside_a_cut_are_dropped():
    out = tighten.remap_words([{"w": "um", "s": 1.0, "e": 1.4}, {"w": "ok", "s": 3.0, "e": 3.4}], [(0.9, 1.5)])
    assert [w["w"] for w in out] == ["ok"] and out[0]["s"] == pytest.approx(2.4)


def test_select_expression():
    assert tighten.select_expr([(0, 1.5), (3, 4)]) == "gte(t,0.0000)*lt(t,1.5000)+gte(t,3.0000)*lt(t,4.0000)"


def test_manual_cuts_work_even_with_auto_tightening_off():
    words = W([("a", 0, 0.5), ("b", 0.5, 1.0), ("c", 8, 8.5)])
    p = tighten.plan(words, 0, 10, {"enabled": False, "manual": [{"start": 3.0, "end": 6.0}]})
    assert p["removed_seconds"] == pytest.approx(3.0, abs=0.1) and p["pauses"] == 0 and p["new_duration"] == pytest.approx(7.0, abs=0.1)


def test_manual_and_automatic_cuts_merge_without_double_counting():
    words = W([("hello", 0.0, 0.5), ("there", 0.5, 1.0), ("again", 6.0, 6.5), ("friends", 6.5, 7.5)])
    auto = tighten.plan(words, 0, 8, {"enabled": True})
    both = tighten.plan(words, 0, 8, {"enabled": True, "manual": [{"start": 2.0, "end": 4.0}]})   # lies inside the automatic pause cut
    assert both["removed_seconds"] == pytest.approx(auto["removed_seconds"], abs=0.1)
    extra = tighten.plan(words, 0, 8, {"enabled": True, "manual": [{"start": 6.2, "end": 7.0}]})  # cuts into speech: more removed
    assert extra["removed_seconds"] > auto["removed_seconds"] + 0.5


def test_manual_cuts_outside_the_clip_are_ignored_and_tiny_ones_dropped():
    p = tighten.plan(W([("a", 0, 1)]), 10, 20, {"manual": [{"start": 0, "end": 5}, {"start": 12, "end": 12.02}]})
    assert p["removed"] == []
