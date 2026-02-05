"""BookProject: manages project directory & chunk index (skeleton)."""

from pathlib import Path


class BookProject:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "chunks").mkdir(exist_ok=True)
