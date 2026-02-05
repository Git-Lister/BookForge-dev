"""Utilities to sanitise text before sending to TTS engines."""

from __future__ import annotations

import unicodedata
from pathlib import Path


DEBUG_SANITISE = False  # flip to True if you want debug dumps


def _is_surrogate(ch: str) -> bool:
    code = ord(ch)
    return 0xD800 <= code <= 0xDFFF


def _is_control(ch: str) -> bool:
    # Keep whitespace, drop other control chars
    if ch in ("\n", "\r", "\t"):
        return False
    return unicodedata.category(ch)[0] == "C"


def _debug_dump(label: str, text: str) -> None:
    if not DEBUG_SANITISE:
        return
    debug_dir = Path("out") / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    # Append for now
    with (debug_dir / "sanitise_log.txt").open("a", encoding="utf-8") as f:
        f.write(f"\n--- {label} ---\n")
        f.write(repr(text))
        f.write("\n")


def sanitise_for_tts(text: str) -> str:
    """Remove or normalise characters that TTS backends commonly reject."""
    _debug_dump("raw", text)

    cleaned_chars: list[str] = []

    for ch in text:
        if _is_surrogate(ch):
            continue
        if _is_control(ch):
            continue
        cleaned_chars.append(ch)

    cleaned = "".join(cleaned_chars)

    # Normalise punctuation
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    cleaned = cleaned.replace("“", '"').replace("”", '"')
    cleaned = cleaned.replace("’", "'")

    # Unicode normalisation
    cleaned = unicodedata.normalize("NFC", cleaned)
    _debug_dump("after_basic", cleaned)

    # Final safety: drop anything that can't be encoded in UTF-8
    cleaned_bytes = cleaned.encode("utf-8", errors="ignore")
    cleaned_final = cleaned_bytes.decode("utf-8", errors="ignore")

    # Extra: if somehow any surrogate survived, remove by codepoint check
    cleaned_final = "".join(ch for ch in cleaned_final if not _is_surrogate(ch))

    _debug_dump("final", cleaned_final)
    return cleaned_final
