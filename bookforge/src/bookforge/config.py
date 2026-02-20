"""Configuration and preset handling."""

from pathlib import Path
from pydantic import BaseModel
import yaml


class PresetConfig(BaseModel):
    """Voice and pacing configuration preset."""
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
        """Load preset from presets/<name>.yaml file."""
        # Look for preset file in presets/ directory
        preset_file = Path(__file__).parent.parent.parent / "presets" / f"{name}.yaml"
        
        if not preset_file.exists():
            # Fallback to defaults if preset not found
            return cls(voice=name)
        
        try:
            with preset_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Failed to load preset '{name}': {e}")
