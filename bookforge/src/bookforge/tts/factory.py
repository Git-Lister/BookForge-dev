from __future__ import annotations

from pathlib import Path
from typing import Optional


def get_backend(
    backend_type: str,
    voice_model: Optional[Path] = None,
    speaker_wav: Optional[Path] = None,
):
    """Factory to instantiate the correct TTS backend lazily."""
    backend_type = backend_type.lower().strip()

    if backend_type == "piper":
        if voice_model is None:
            raise ValueError("You must provide --voice-model when using backend 'piper'.")
        from .piper import PiperBackend
        return PiperBackend(str(voice_model))

    if backend_type == "xtts":
        try:
            from .xtts import XTTSBackend
        except ModuleNotFoundError as e:
            raise ValueError(
                "XTTS dependencies are not installed. Please install torch and Coqui TTS."
            ) from e

    raise ValueError(f"Unknown backend: {backend_type}")