"""Plain text ingestion for BookForge."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class BookText:
    """Simple representation of a book's text content."""

    title: str
    chapters: List[str]


CHAPTER_HEADING_RE = re.compile(r"^\s*(chapter\s+\d+|chapter\s+[ivxlcdm]+)\b", re.IGNORECASE)


def load_txt(path: Path) -> BookText:
    """Load a plain text file and split into chapters.

    Heuristic:
    - Strip leading/trailing whitespace.
    - Split into lines.
    - Start a new chapter when a line matches CHAPTER_HEADING_RE.
    - If no headings found, treat whole file as a single chapter.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    chapters: List[List[str]] = [[]]
    found_heading = False

    for line in lines:
        if CHAPTER_HEADING_RE.match(line):
            found_heading = True
            # start new chapter, keep heading line
            if chapters[-1]:
                chapters.append([])
            chapters[-1].append(line)
        else:
            chapters[-1].append(line)

    if not found_heading:
        # single chapter: entire text
        return BookText(title=path.stem, chapters=["\n".join(lines)])

    chapter_texts = ["\n".join(ch).strip() for ch in chapters if any(l.strip() for l in ch)]
    return BookText(title=path.stem, chapters=chapter_texts)
