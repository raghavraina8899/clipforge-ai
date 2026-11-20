"""Speech-to-text with faster-whisper (open source, runs locally). Produces word-level timestamps."""
import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("transcribe")
_models: dict = {}
_lock = threading.Lock()
LANGS = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}


def hinglish_text(t: str) -> str:
    from .hinglish import romanize
    return romanize(t)


def _model(size: str):
    with _lock:
        if size not in _models:
            from faster_whisper import WhisperModel
            log.info("loading whisper model %s (first use downloads it once from Hugging Face)", size)
            _models[size] = WhisperModel(size, device="cpu", compute_type="int8")
        return _models[size]


def transcribe(audio: Path, out_json: Path, size: str = "small", language: str = "auto", duration: float = 0.0,
               on_progress: Optional[Callable[[float, str], None]] = None) -> dict:
    if on_progress:
        on_progress(0, f"Loading speech model “{size}” (downloaded once, then cached)")
    try:
        model = _model(size)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Could not load the Whisper model “{size}”. The first run needs internet access to download it. Details: {e}")
    hinglish = language == "hinglish"
    lang = "hi" if hinglish else (None if language in ("auto", "", None) else language)
    # A Hinglish prompt nudges Whisper to write Hindi in English letters; any Devanagari left is converted below.
    prompt = "Aaj hum baat karenge, mujhe lagta hai ki yeh bahut accha hai. Kya aap samajh rahe ho? Bilkul, chalo shuru karte hain." if hinglish else None
    segments, info = model.transcribe(str(audio), language=lang, word_timestamps=True, vad_filter=True,
                                      condition_on_previous_text=False, beam_size=5, initial_prompt=prompt)
    words, segs = [], []
    for seg in segments:
        segs.append({"start": round(seg.start, 3), "end": round(seg.end, 3), "text": hinglish_text(seg.text.strip()) if hinglish else seg.text.strip()})
        for w in seg.words or []:
            t = w.word.strip()
            if hinglish:
                t = hinglish_text(t)
            if t:
                words.append({"w": t, "s": round(w.start, 3), "e": round(w.end, 3)})
        if on_progress and duration:
            on_progress(min(99.0, seg.end / duration * 100), f"Transcribing… {int(seg.end)}s of {int(duration)}s")
    data = {"language": info.language, "language_probability": round(info.language_probability, 3),
            "model": size, "segments": segs, "words": words}
    out_json.write_text(json.dumps(data, ensure_ascii=False))
    return data


def load(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None
