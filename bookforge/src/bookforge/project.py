<<<<<<< HEAD
# src/bookforge/project.py
=======
"""BookProject manages project directories & chunk index."""
>>>>>>> a106b5adb4cfb29e4a5155a15b8489c180cacb80

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import json


class BookProject:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.chunks_dir = root / "chunks"
        self.chunks_dir.mkdir(exist_ok=True)
        self.index_path = root / "project.json"
        self.meta_path = root / "meta.json"
        self.chapters_dir = root / "chapters"
        self.chapters_dir.mkdir(exist_ok=True)

    def save_index(self, index: List[Dict[str, Any]]) -> None:
        """Save chunk metadata index as JSON."""
        with self.index_path.open("w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

    def load_index(self) -> List[Dict[str, Any]]:
        """Load chunk metadata index if it exists."""
        if not self.index_path.exists():
            return []
        with self.index_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_meta(self, meta: Dict[str, Any]) -> None:
        """Save simple project metadata (e.g., source file)."""
        with self.meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def load_meta(self) -> Dict[str, Any]:
        """Load project metadata if it exists."""
        if not self.meta_path.exists():
            return {}
        with self.meta_path.open("r", encoding="utf-8") as f:
            return json.load(f)
