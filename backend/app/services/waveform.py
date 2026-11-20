"""Audio waveform (peak envelope) for the timeline editor."""
import subprocess
from pathlib import Path

from ..config import FFMPEG
from . import ffmpeg


def peaks(src: Path, start: float, end: float, bins: int) -> list:
    """Peak level (0..1) of each of `bins` equal slices of [start, end] seconds of the file's audio."""
    import numpy as np
    ffmpeg.require()
    bins = max(10, min(2000, int(bins)))
    dur = max(0.1, end - start)
    r = subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                       capture_output=True)
    a = np.abs(np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)) / 32768.0
    if a.size < bins:
        return [0.0] * bins
    return [round(float(c.max()), 3) if c.size else 0.0 for c in np.array_split(a, bins)]
