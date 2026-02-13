"""Text sanitization for TTS engines."""

from __future__ import annotations

import re
import unicodedata


def sanitise_for_tts(text: str) -> str:
    """
    Sanitize text for TTS synthesis.
    
    - Remove/replace characters that cause TTS errors
    - Expand abbreviations for better pronunciation
    - Add prosody hints (pauses) for natural rhythm
    """
    # Normalize unicode (remove weird encoding artifacts)
    text = unicodedata.normalize("NFKC", text)
    
    # Remove or replace problematic characters
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\ufeff', '')  # BOM
    text = text.replace('\r', '')      # Windows line endings
    
    # Replace em/en dashes with hyphens (TTS handles better)
    text = text.replace('—', ' - ')
    text = text.replace('–', ' - ')
    
    # Expand common abbreviations that TTS mispronounces
    text = text.replace("e.g.", "for example")
    text = text.replace("E.g.", "For example")
    text = text.replace("i.e.", "that is")
    text = text.replace("I.e.", "That is")
    text = text.replace("etc.", "et cetera")
    text = text.replace("vs.", "versus")
    text = text.replace("c.f.", "compare")
    
    # Expand academic abbreviations
    text = text.replace("et al.", "and others")
    text = text.replace("ibid.", "same source")
    text = text.replace("op. cit.", "previously cited")
    
    # Add natural pauses for better rhythm
    # (Piper doesn't support SSML, but we can use strategic spacing)
    
    # Longer pause after sentence-ending punctuation
    text = re.sub(r'([.!?])\s+', r'\1  ', text)  # Double space
    
    # Preserve paragraph breaks for natural pauses
    text = re.sub(r'\n\n+', '\n\n', text)
    
    # Clean up excessive whitespace but preserve intentional breaks
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs → single space
    text = text.strip()
    
    # Final safety: remove any remaining surrogates or non-UTF8 chars
    text = text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
    
    return text
