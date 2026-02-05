"""Configuration and preset handling."""

from pathlib import Path
from pydantic_settings import BaseSettings


class PresetConfig(BaseSettings):
    voice: str
    rate: float = 1.0
    pitch: float = 0.0
    pause_short: float = 0.3
    pause_para: float = 1.2
    pause_chapter: float = 3.0
    seed: int = 42
    target_chunk_secs: int = 30

    @classmethod
    def load(cls, name: str) -> "PresetConfig":
        """Load preset from presets/<name>.yaml (simple stub)."""
        # TODO: implement proper YAML reading & validation
        # For now, return defaults with given voice name.
        return cls(voice=name)
