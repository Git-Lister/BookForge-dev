"""XTTS v2 TTS backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch
from TTS.api import TTS  # coqui-tts

from ..config import PresetConfig
from ..process.chunker import Chunk
from ..process.sanitize import sanitise_for_tts
from .backend import TTSBackend


class XTTSBackend(TTSBackend):
    """XTTS v2 backend using Coqui TTS."""

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        gpu: bool = True,
        speaker_wav: Optional[Path] = None,
        language: str = "en",
    ) -> None:
        # Decide device based on flag + availability
        if gpu:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = "cpu"

        self._device = device
        self._model_name = model_name
        self._speaker_wav = str(speaker_wav) if speaker_wav else None
        self._language = language

        # Initialise coqui-tts model on chosen device
        # Note: in newer coqui-tts versions, .to(device) is the canonical way.
        self.tts = TTS(model_name).to(device)

    @property
    def device(self) -> str:
        return self._device

    def synthesize_chunk(
        self,
        chunk: Chunk,
        config: PresetConfig,
        out_path: Path,
    ) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        safe_text = sanitise_for_tts(chunk.text)

        kwargs = {
            "text": safe_text,
            "file_path": str(out_path),
        }
        if self._speaker_wav:
            kwargs["speaker_wav"] = self._speaker_wav
        if self._language:
            kwargs["language"] = self._language

        # XTTS handles prosody; we don't currently map config.rate
        self.tts.tts_to_file(**kwargs)