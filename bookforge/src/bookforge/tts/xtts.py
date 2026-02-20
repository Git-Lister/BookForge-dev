"""XTTS v2 TTS backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from TTS.api import TTS  # Coqui TTS

from .backend import TTSBackend
from ..config import PresetConfig
from ..process.chunker import Chunk
from ..process.sanitize import sanitise_for_tts


class XTTSBackend(TTSBackend):
    """XTTS v2 backend using Coqui TTS."""

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        gpu: bool = True,
        speaker_wav: Optional[Path] = None,
        language: str = "en",
    ) -> None:
        self.tts = TTS(model_name, gpu=gpu)
        self.speaker_wav = str(speaker_wav) if speaker_wav else None
        self.language = language

    def synthesize_chunk(self, chunk: Chunk, config: PresetConfig, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        safe_text = sanitise_for_tts(chunk.text)

        kwargs = {
            "text": safe_text,
            "file_path": str(out_path),
        }
        if self.speaker_wav:
            kwargs["speaker_wav"] = self.speaker_wav
        if self.language:
            kwargs["language"] = self.language

        # XTTS handles prosody; we don't currently map config.rate
        self.tts.tts_to_file(**kwargs)
