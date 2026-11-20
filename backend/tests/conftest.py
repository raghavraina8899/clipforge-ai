"""Test setup: every test run gets its own empty data folder, so real projects are never touched."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DATA = tempfile.mkdtemp(prefix="hookhunt-test-")
os.environ["HOOKHUNT_DATA"] = DATA
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "app" / "assets"


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(DATA, ignore_errors=True)


@pytest.fixture(scope="session")
def sample_wav() -> Path:
    return ASSETS / "speed_sample.wav"


@pytest.fixture(scope="session")
def have_ffmpeg() -> bool:
    from app import config
    return bool(config.FFMPEG and config.FFPROBE)


@pytest.fixture(scope="session")
def test_video(tmp_path_factory, sample_wav, have_ffmpeg) -> Path:
    """A real 1280x720 test video (colour bars) carrying the bundled 30 s speech sample."""
    if not have_ffmpeg:
        pytest.skip("FFmpeg not installed")
    from app import config
    out = tmp_path_factory.mktemp("media") / "test.mp4"
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-i", str(sample_wav),
                    "-t", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)], check=True)
    return out


def make_words(text: str, start: float = 0.0, per: float = 0.4, gap_after_sentence: float = 0.0) -> list:
    """Evenly timed word list from a sentence string (for analysis/caption tests)."""
    words, t = [], start
    for w in text.split():
        words.append({"w": w, "s": round(t, 3), "e": round(t + per, 3)})
        t += per
        if w[-1] in ".?!":
            t += gap_after_sentence
    return words
