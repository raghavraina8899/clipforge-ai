"""Speech-to-text with word-level timestamps, running locally. The engine is picked automatically for this computer
(Apple GPU / NVIDIA GPU / CPU, see engine.py) and falls back to the next one if it is unavailable or fails."""
import json
import logging
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional

from ..jobs import Cancelled
from . import engine, settings_store

log = logging.getLogger("transcribe")
_models: dict = {}
_lock = threading.Lock()
LANGS = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}
HINGLISH_PROMPT = "Aaj hum baat karenge, mujhe lagta hai ki yeh bahut accha hai. Kya aap samajh rahe ho? Bilkul, chalo shuru karte hain."


def hinglish_text(t: str) -> str:
    from .hinglish import romanize
    return romanize(t)


def _fw_model(size: str, device: str):
    key = (size, device)
    with _lock:
        if key not in _models:
            from faster_whisper import WhisperModel
            log.info("loading faster-whisper %s on %s (first use downloads it once from Hugging Face)", size, device)
            _models[key] = WhisperModel(size, device=device, compute_type="float16" if device == "cuda" else "int8",
                                        **({} if device == "cuda" else {"cpu_threads": engine.cpu_threads()}))
        return _models[key]


def _run_faster(audio: Path, size: str, lang: Optional[str], prompt: Optional[str], duration: float, on_progress, device: str):
    """faster-whisper with batched decoding: ~1.5x faster than the plain loop on CPU, much more on a GPU."""
    from faster_whisper import BatchedInferencePipeline
    pipe = BatchedInferencePipeline(model=_fw_model(size, device))
    segments, info = pipe.transcribe(str(audio), language=lang, word_timestamps=True, initial_prompt=prompt, batch_size=16 if device == "cuda" else 8)
    words, segs = [], []
    for seg in segments:
        segs.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        for w in seg.words or []:
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": w.start, "e": w.end})
        if on_progress and duration:
            on_progress(min(99.0, seg.end / duration * 100), f"Transcribing… {int(seg.end)}s of {int(duration)}s")
    return words, segs, info.language


def _run_mlx(audio: Path, size: str, lang: Optional[str], prompt: Optional[str], duration: float, on_progress):
    """MLX Whisper on the Apple GPU. A voice-activity detector first finds where speech actually is, so silence and music are skipped
    (faster, and no invented text). Audio is read in 10-minute windows, so memory stays small and progress/cancel work for any length."""
    import numpy as np
    import mlx_whisper
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    repo = engine.MLX_REPOS.get(size, engine.MLX_REPOS["small"])
    words, segs = [], []
    detected = lang
    WIN, MAXGROUP, JOIN_GAP = 600.0, 300.0, 8.0
    with wave.open(str(audio)) as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        if (sr, ch, sw) != (16000, 1, 2):
            raise RuntimeError("audio is not 16 kHz mono 16-bit")
        total = n / sr
        t = 0.0
        while t < total - 0.05:
            end = min(total, t + WIN + 30)
            w.setpos(int(t * sr))
            a = np.frombuffer(w.readframes(int((end - t) * sr)), np.int16).astype(np.float32) / 32768.0
            boundary = t + WIN
            spans = get_speech_timestamps(a, VadOptions(min_silence_duration_ms=1000, speech_pad_ms=300), sampling_rate=sr)
            spans = [(t + s["start"] / sr, t + s["end"] / sr) for s in spans if end >= total or t + s["start"] / sr < boundary]
            groups: list = []
            for s0, s1 in spans:  # merge nearby speech into groups (fewer, longer decoding calls)
                if groups and s0 - groups[-1][1] < JOIN_GAP and s1 - groups[-1][0] <= MAXGROUP:
                    groups[-1][1] = s1
                else:
                    groups.append([s0, s1])
            for g0, g1 in groups:
                g0, g1 = max(t, g0 - 0.25), min(end, g1 + 0.25)
                r = mlx_whisper.transcribe(a[int((g0 - t) * sr):int((g1 - t) * sr)], path_or_hf_repo=repo, language=detected, word_timestamps=True,
                                           condition_on_previous_text=False, initial_prompt=prompt, verbose=None, hallucination_silence_threshold=2.0)
                detected = detected or r.get("language")
                for sg in r.get("segments", []):
                    segs.append({"start": g0 + float(sg["start"]), "end": g0 + float(sg["end"]), "text": sg["text"].strip()})
                    for wd in sg.get("words", []):
                        tx = wd["word"].strip()
                        if tx:
                            words.append({"w": tx, "s": g0 + float(wd["start"]), "e": g0 + float(wd["end"])})
                if on_progress:
                    on_progress(min(99.0, g1 / max(total, 1) * 100), f"Transcribing… {int(g1)}s of {int(total)}s")
            last = max([s1 for _, s1 in spans], default=boundary)
            t = max(boundary, last) if spans else boundary
    return words, segs, detected or "en"


def transcribe(audio: Path, out_json: Path, size: str = "small", language: str = "auto", duration: float = 0.0,
               on_progress: Optional[Callable[[float, str], None]] = None, offset: float = 0.0, engine_pref: Optional[str] = None) -> dict:
    pref = engine_pref or settings_store.load()["transcription"].get("engine", "auto")
    sel = engine.choose(pref)
    order = [sel["engine"]] + [e for e in engine.available() if e != sel["engine"]]
    note = sel["note"]
    hinglish = language == "hinglish"
    lang = "hi" if hinglish else (None if language in ("auto", "", None) else language)
    # A Hinglish prompt nudges Whisper to write Hindi in English letters; any Devanagari left is converted below.
    prompt = HINGLISH_PROMPT if hinglish else None
    result, used, last_err = None, None, None
    started = time.time()
    for eng in order:
        if on_progress:
            on_progress(0, f"Loading speech engine: {engine.LABELS[eng]}, model “{size}” (downloaded once, then cached)")
        try:
            result = _run_mlx(audio, size, lang, prompt, duration, on_progress) if eng == "mlx" else _run_faster(audio, size, lang, prompt, duration, on_progress, "cuda" if eng == "cuda" else "cpu")
            used = eng
            break
        except Cancelled:
            raise
        except Exception as e:  # noqa: BLE001 - try the next engine, keep the reason
            last_err = e
            log.warning("speech engine %s failed: %s", eng, e)
            note = f"{engine.LABELS[eng]} did not work here ({str(e)[:120]}), so the next engine was used."
    if result is None:
        raise RuntimeError(f"Could not transcribe. The first run needs internet access to download the speech model “{size}”. Details: {last_err}")
    words_raw, segs_raw, lang_out = result
    words = [{"w": hinglish_text(w["w"]) if hinglish else w["w"], "s": round(w["s"] + offset, 3), "e": round(w["e"] + offset, 3)} for w in words_raw]
    segs = [{"start": round(s["start"] + offset, 3), "end": round(s["end"] + offset, 3), "text": hinglish_text(s["text"]) if hinglish else s["text"]} for s in segs_raw]
    words = [w for w in words if w["w"]]
    elapsed = time.time() - started
    data = {"language": lang_out, "model": size, "engine": used, "engine_note": note, "segments": segs, "words": words,
            "seconds_per_audio_second": round(elapsed / duration, 4) if duration else None}
    out_json.write_text(json.dumps(data, ensure_ascii=False))
    log.info("transcribed %.0fs of audio with %s (%s) in %.0fs (%.1fx real time)", duration, used, size, elapsed, (duration / elapsed) if elapsed else 0)
    return data


def load(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None
