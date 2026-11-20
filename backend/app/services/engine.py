"""Picks the fastest available speech-to-text engine for THIS computer, automatically:
   Apple silicon Mac -> MLX Whisper on the Apple GPU
   NVIDIA graphics card -> faster-whisper on CUDA
   anything else -> faster-whisper on the CPU (batched)
The user can override this in AI Settings; if the chosen engine is missing or fails, the next one is used."""
import importlib.util as iu
import logging
import os
import platform
import sys
from typing import Optional

log = logging.getLogger("engine")

LABELS = {"mlx": "Apple GPU (MLX Whisper)", "cuda": "NVIDIA GPU (CUDA)", "cpu": "CPU (batched)"}

# model size names used in the settings -> MLX community repositories
MLX_REPOS = {"tiny": "mlx-community/whisper-tiny-mlx", "base": "mlx-community/whisper-base-mlx", "small": "mlx-community/whisper-small-mlx",
             "medium": "mlx-community/whisper-medium-mlx", "large-v3": "mlx-community/whisper-large-v3-mlx", "turbo": "mlx-community/whisper-large-v3-turbo"}


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mlx_available() -> bool:
    if not is_apple_silicon() or iu.find_spec("mlx_whisper") is None:
        return False
    try:
        import mlx.core as mx
        return "gpu" in str(mx.default_device()).lower()
    except Exception:  # noqa: BLE001
        return False


def cuda_available() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001
        return False


def available() -> list:
    out = []
    if mlx_available():
        out.append("mlx")
    if cuda_available():
        out.append("cuda")
    out.append("cpu")
    return out


def choose(preference: str = "auto") -> dict:
    """Returns {engine, label, note}. `note` explains a fallback (shown to the user)."""
    av = available()
    if preference in ("mlx", "cuda", "cpu") and preference in av:
        return {"engine": preference, "label": LABELS[preference], "note": ""}
    note = ""
    if preference in ("mlx", "cuda", "cpu"):
        note = f"{LABELS[preference]} is not available on this computer, so {LABELS[av[0]]} is used instead."
    return {"engine": av[0], "label": LABELS[av[0]], "note": note}


def cpu_threads() -> int:
    return max(2, os.cpu_count() or 4)


def info() -> dict:
    av = available()
    return {"available": [{"id": a, "label": LABELS[a]} for a in av], "best": av[0], "machine": f"{platform.system()} {platform.machine()}",
            "mlx_installed": iu.find_spec("mlx_whisper") is not None, "apple_silicon": is_apple_silicon()}
