"""Utilities to sanitise text before sending to TTS engines."""

from __future__ import annotations

import unicodedata


def _is_surrogate(ch: str) -> bool:
    code = ord(ch)
    return 0xD800 <= code <= 0xDFFF


def _is_control(ch: str) -> bool:
    # Keep whitespace, drop other control chars
    if ch in ("\n", "\r", "\t"):
        return False
    return unicodedata.category(ch)[0] == "C"


def sanitise_for_tts(text: str) -> str:
    """Remove or normalise characters that TTS backends commonly reject.

    - Drop surrogate codepoints (invalid in UTF‑8, cause espeak errors).
    - Drop non-whitespace control characters.
    - Normalise some punctuation to ASCII.
    """
    cleaned_chars: list[str] = []

    for ch in text:
        if _is_surrogate(ch):
            # Skip all surrogate codepoints outright
            continue
        if _is_control(ch):
            continue
        cleaned_chars.append(ch)

    cleaned = "".join(cleaned_chars)

    # Normalise some punctuation
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    cleaned = cleaned.replace("“", '"').replace("”", '"')
    cleaned = cleaned.replace("’", "'")

    # Extra safety: normalise to NFC and then re-drop any new surrogates
    cleaned = unicodedata.normalize("NFC", cleaned)
    cleaned_final_chars: list[str] = []
    for ch in cleaned:
        if _is_surrogate(ch):
            continue
        cleaned_final_chars.append(ch)

    return "".join(cleaned_final_chars)
