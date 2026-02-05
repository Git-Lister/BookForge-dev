"""Piper TTS backend."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .backend import TTSBackend
from ..config import PresetConfig
from ..process.chunker import Chunk
from ..process.sanitize import sanitise_for_tts


class PiperBackend(TTSBackend):
    """Simple wrapper around the `piper` CLI."""

    def __init__(self, voice: str) -> None:
        # voice is the path to a Piper ONNX model file for now
        self.voice = voice

    def synthesize_chunk(self, chunk: Chunk, config: PresetConfig, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        safe_text = sanitise_for_tts(chunk.text)
        text_bytes = safe_text.encode("utf-8")

        # Piper length_scale: smaller = faster; map our rate (1.0 = normal) → inverse.
        length_scale = 1.0 / max(config.rate, 0.1)

        cmd = [
            "piper",
            "--model",
            self.voice,
            "--output_file",
            str(out_path),
            "--length_scale",
            str(length_scale),
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = proc.communicate(text_bytes)
        if proc.returncode != 0:
            stderr = stderr_bytes.decode("utf-8", errors="ignore")
            raise RuntimeError(f"Piper failed: {stderr}")
