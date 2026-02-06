"""Audio concatenation utilities for BookForge."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import ffmpeg  # type: ignore[import]


def concat_wavs(wav_paths: Iterable[Path], output_path: Path) -> None:
    """Concatenate multiple WAV files into a single WAV using ffmpeg.

    Assumes all inputs share the same sample rate/format (Piper's output).
    """
    wav_list: List[Path] = [p for p in wav_paths if p.exists()]
    if not wav_list:
        raise ValueError("No WAV files to concatenate.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use ffmpeg concat filter
    inputs = [ffmpeg.input(str(p)) for p in wav_list]
    joined = ffmpeg.concat(*inputs, v=0, a=1)
    out = ffmpeg.output(joined, str(output_path))
    out = ffmpeg.overwrite_output(out)
    out.run(quiet=True)
