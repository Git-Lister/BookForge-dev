"""Text cleaning utilities for BookForge."""

from __future__ import annotations

import re


GUTENBERG_HEADER_RE = re.compile(r"\*{3}\s*START OF (THIS|THE) PROJECT GUTENBERG", re.IGNORECASE)
GUTENBERG_FOOTER_RE = re.compile(r"\*{3}\s*END OF (THIS|THE) PROJECT GUTENBERG", re.IGNORECASE)


def strip_gutenberg_boilerplate(text: str) -> str:
    """Remove Project Gutenberg header/footer if present."""
    # Header
    header_match = GUTENBERG_HEADER_RE.search(text)
    if header_match:
        text = text[header_match.end() :]
    # Footer
    footer_match = GUTENBERG_FOOTER_RE.search(text)
    if footer_match:
        text = text[: footer_match.start()]
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse excessive whitespace and normalise newlines."""
    # convert Windows newlines, collapse multiple blank lines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    # collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Run all cleaning steps on text."""
    text = strip_gutenberg_boilerplate(text)
    text = normalize_whitespace(text)
    # TODO: de-hyphenation, ligatures if needed
    return text
