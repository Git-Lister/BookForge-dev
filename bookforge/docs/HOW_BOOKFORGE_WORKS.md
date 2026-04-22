Good, I have enough context from the research combined with everything we've built together. Here is the full first draft:

***

# HOW_BOOKFORGE_WORKS.md

```markdown
# How BookForge Works

BookForge is a local, GPU-accelerated pipeline for converting plain text books
into high-quality audiobooks using open-source neural text-to-speech (TTS)
backends. It is designed to run entirely on your own machine — no cloud APIs,
no subscriptions, no data leaving your environment.

This document explains the full architecture: what each component does, how
they connect, and what happens at every stage of the pipeline from raw text
to finished audio.

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Project Structure](#3-project-structure)
4. [Ingestion: Loading the Source Text](#4-ingestion-loading-the-source-text)
5. [Chapter Detection](#5-chapter-detection)
6. [Text Cleaning and Sanitisation](#6-text-cleaning-and-sanitisation)
7. [Chunking](#7-chunking)
8. [TTS Backends](#8-tts-backends)
9. [The Incremental Processor](#9-the-incremental-processor)
10. [Audio Assembly](#10-audio-assembly)
11. [Normalisation](#11-normalisation)
12. [The Project Store](#12-the-project-store)
13. [The Streamlit UI](#13-the-streamlit-ui)
14. [The CLI](#14-the-cli)
15. [Configuration and Presets](#15-configuration-and-presets)
16. [Docker Environment](#16-docker-environment)
17. [Known Limitations and Future Work](#17-known-limitations-and-future-work)

---

## 1. Overview

BookForge takes a `.txt` file as input and produces a set of `.wav` audio
files as output: one per chunk (the smallest synthesis unit), one per chapter,
and one final `book.wav` for the complete audiobook.

The pipeline has five logical stages:

```
Raw text
   │
   ▼
Ingestion + Chapter Detection
   │
   ▼
Cleaning + Chunking
   │
   ▼
TTS Synthesis (per chunk)
   │
   ▼
Audio Concatenation (chunks → chapters → book)
   │
   ▼
Optional Normalisation
   │
   ▼
Finished audiobook (book.wav + chapter WAVs)
```

Each stage is independently implemented, which means you can re-run individual
stages (e.g. re-synthesise a single chunk, or re-build the final WAV from
existing chunks) without repeating the whole pipeline.

---

## 2. System Architecture

BookForge is a Python package installed in editable mode (`pip install -e .`)
inside a Docker container. The container provides a reproducible, GPU-capable
environment that avoids the dependency conflicts common in the ML ecosystem on
Windows.

### Key layers

```
┌─────────────────────────────────────────────┐
│           Streamlit UI (ui.py)              │
│    (browser-based, runs on port 8501)       │
├─────────────────────────────────────────────┤
│      Incremental Processor                  │
│  (bookforge/incremental_processor.py)       │
├──────────────────┬──────────────────────────┤
│  Ingest layer    │  Process layer           │
│  txt_ingest.py   │  cleaner.py              │
│                  │  chunker.py              │
│                  │  sanitize.py             │
├──────────────────┴──────────────────────────┤
│         TTS Backend layer                   │
│  factory.py → piper.py / xtts.py           │
├─────────────────────────────────────────────┤
│         Audio layer                         │
│  concat.py / normalise.py                  │
├─────────────────────────────────────────────┤
│         Project store                       │
│  project.py (index, metadata, directories) │
└─────────────────────────────────────────────┘
```

### Technology stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| CLI | Typer |
| Primary TTS (quality) | Coqui XTTS v2 (via coqui-tts) |
| Secondary TTS (speed) | Piper TTS |
| Deep learning runtime | PyTorch + CUDA |
| Audio processing | ffmpeg, libsndfile |
| Container | Docker + NVIDIA CUDA base image |
| Python version (container) | 3.11 |

---

## 3. Project Structure

```
bookforge/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── books/              ← input .txt files go here
├── voices/             ← Piper .onnx models and XTTS reference WAVs
├── out/                ← one subdirectory per project (output)
│   └── my-audiobook/
│       ├── chunks/     ← one WAV per synthesised chunk
│       ├── chapters/   ← one WAV per chapter
│       ├── book.wav    ← final assembled audiobook
│       ├── project.json ← chunk index
│       └── meta.json   ← project metadata
└── src/bookforge/
    ├── cli.py
    ├── ui.py
    ├── config.py
    ├── project.py
    ├── incremental_processor.py
    ├── ingest/
    │   └── txt_ingest.py
    ├── process/
    │   ├── cleaner.py
    │   ├── chunker.py
    │   └── sanitize.py
    ├── tts/
    │   ├── backend.py
    │   ├── factory.py
    │   ├── piper.py
    │   └── xtts.py
    └── audio/
        ├── concat.py
        └── normalise.py
```

---

## 4. Ingestion: Loading the Source Text

**Module:** `src/bookforge/ingest/txt_ingest.py`

The ingestion layer reads a plain `.txt` file from disk and returns a
`BookText` object, which contains:

- `title`: the inferred title of the book (taken from the filename or first
  heading found).
- `chapters`: a list of strings, one per detected chapter.
- `chapter_titles`: a list of the detected heading strings (if any).

This stage does not modify the text content — it only segments it. All
cleaning happens downstream in the process layer.

---

## 5. Chapter Detection

**Module:** `src/bookforge/ingest/txt_ingest.py`

Chapter detection is the process of deciding where one chapter ends and the
next begins inside a flat text file. BookForge supports five detection
strategies, selectable via the `--chapter-strategy` CLI option or the
"Chapter detection" dropdown in the UI.

### Strategies

| Strategy | Description |
|---|---|
| `auto` | Tries multiple strategies in order and picks the one with the highest confidence score. Default and recommended for most books. |
| `markdown` | Looks for `#` or `##` headings in Markdown-formatted text. Best for texts exported from Markdown editors. |
| `structured` | Looks for explicit labels such as "Chapter 1", "Part I", "Section 2", etc. Best for traditionally formatted novels and non-fiction. |
| `heuristic` | Scores lines based on contextual signals: blank lines before/after, capitalisation, line length, position. Best for irregular formatting. |
| `paragraph` | Treats large gaps (multiple blank lines) as chapter boundaries. Fallback for texts with no explicit markers. |
| `none` | Treats the entire book as a single chapter. Useful for short texts or testing. |

### Confidence threshold

Each detected chapter boundary has an associated confidence score between 0.0
and 1.0. Boundaries below the `--chapter-min-confidence` threshold (default
0.5) are discarded. Raising this value produces fewer, more confident chapter
splits; lowering it accepts more speculative boundaries.

---

## 6. Text Cleaning and Sanitisation

**Modules:** `src/bookforge/process/cleaner.py`,
`src/bookforge/process/sanitize.py`

Text goes through two distinct cleaning passes before synthesis.

### Pass 1: Structural cleaning (`cleaner.py`)

`clean_text()` is applied per chapter before chunking. It:

- Normalises whitespace and line endings.
- Removes or replaces characters that have no meaningful spoken equivalent
  (e.g. soft hyphens, zero-width spaces, control characters).
- Normalises quotation marks and dashes to standard ASCII equivalents that TTS
  engines handle predictably.
- Strips Markdown formatting artefacts (asterisks, underscores used for
  emphasis) that would be read aloud literally if left in.

### Pass 2: TTS sanitisation (`sanitize.py`)

`sanitise_for_tts()` is applied per chunk immediately before calling the
synthesis backend. It handles edge cases that cause specific TTS engines to
produce unnatural output:

- Expands common abbreviations (e.g. "Dr." → "Doctor", "e.g." → "for
  example") so they are spoken correctly rather than spelled out.
- Normalises numbers and dates into their spoken forms where needed.
- Removes or replaces any remaining symbols that could cause synthesis errors.

This two-pass design separates structural concerns (handled once per chapter)
from synthesis-facing concerns (handled per chunk, closest to the TTS call).

---

## 7. Chunking

**Module:** `src/bookforge/process/chunker.py`

A "chunk" is the unit of text that gets passed to the TTS engine in a single
synthesis call. TTS models have effective limits on how much text they can
process reliably in one pass — very long inputs lead to degraded prosody,
memory errors, or silent truncation.

`chunk_chapter()` splits a cleaned chapter string into a list of `Chunk`
objects, respecting sentence and paragraph boundaries so that synthesis
boundaries do not fall mid-sentence.

### The Chunk object

```python
@dataclass
class Chunk:
    id: int                  # global sequential ID across all chapters
    chapter_index: int       # which chapter this chunk belongs to
    relative_index: int      # position of this chunk within its chapter
    text: str                # the actual text to synthesise
    estimated_seconds: float # rough estimate of audio duration
```

### Chunking parameters (from PresetConfig)

The chunking behaviour is controlled by the active preset:

| Parameter | Description |
|---|---|
| `max_chars` | Hard upper limit on characters per chunk. |
| `preferred_chars` | Target chunk size; chunker tries to stay near this. |
| `min_chars` | Chunks shorter than this are merged with the next one. |
| `split_on_paragraph` | If true, prefer paragraph boundaries over sentence boundaries. |

These parameters are configured per preset rather than hardcoded, so you can
tune chunk size for different backends (XTTS handles longer chunks better than
Piper, for example).

---

## 8. TTS Backends

**Modules:** `src/bookforge/tts/backend.py`, `src/bookforge/tts/factory.py`,
`src/bookforge/tts/piper.py`, `src/bookforge/tts/xtts.py`

All TTS backends implement the `TTSBackend` abstract base class defined in
`backend.py`, which requires a single method:

```python
def synthesize_chunk(self, chunk: Chunk, config: PresetConfig, out_path: Path) -> None:
    ...
```

This uniform interface means the rest of the pipeline (chunker, processor,
CLI) does not need to know which backend is in use.

### Factory pattern

`factory.py` provides a single `get_backend()` function that takes a
`backend_type` string and returns the appropriate backend instance. Critically,
backends are imported **lazily** inside `get_backend()`: the XTTS backend is
only imported when the user actually selects XTTS, so the UI does not require
Torch and Coqui to be importable at startup time. This is important in mixed
environments where Piper may work but XTTS dependencies are not yet installed.

```python
def get_backend(backend_type, voice_model=None, speaker_wav=None):
    if backend_type == "piper":
        from .piper import PiperBackend
        return PiperBackend(str(voice_model))
    if backend_type == "xtts":
        from .xtts import XTTSBackend
        return XTTSBackend(speaker_wav=speaker_wav, language="en", gpu=True)
```

### Piper backend (`piper.py`)

Piper is a fast, lightweight neural TTS engine. It uses `.onnx` voice model
files stored in the `voices/` directory. Piper is suitable for rapid iteration
and testing the full pipeline, but its prosody and naturalness are lower than
XTTS for complex, long-form text.

- No GPU required (runs on CPU).
- Voice is fixed by the chosen `.onnx` model file.
- No voice cloning — a new voice requires a new model file.

### XTTS v2 backend (`xtts.py`)

XTTS v2 (by Coqui AI) is a transformer-based voice cloning model. It takes a
short reference audio clip (6–30 seconds) and generates new speech that mimics
the timbre, pace, and character of that voice. This makes it significantly more
expressive and natural than Piper for long-form, complex texts.

- **Requires a reference speaker WAV** — this is not optional. Without it,
  Coqui will raise "Neither speaker_wav nor speaker_id was specified."
- GPU strongly recommended; the model is 1.87 GB and synthesis is slow on CPU.
- Output is 24 kHz WAV.
- Supports 17 languages via the `language` parameter.
- The model is downloaded automatically on first use from Coqui's servers and
  cached locally.

The `XTTSBackend` initialises the model once in `__init__`, then calls
`tts.tts_to_file()` for each chunk, passing the stored `speaker_wav` and
`language` on every call to maintain voice consistency across the whole book.

---

## 9. The Incremental Processor

**Module:** `src/bookforge/incremental_processor.py`

The `IncrementalProcessor` is the central coordinator of the pipeline. It
wraps the full ingestion → chunking → synthesis workflow in a
**resumable, chapter-by-chapter** structure designed for use from both the
Streamlit UI and the CLI.

### Why incremental?

Synthesising a full book in one blocking call would take many minutes or hours
and provide no progress feedback. The incremental processor allows the UI to
call `process_next_chapter()` in a loop, updating a progress display between
chapters, and to resume from where it left off if interrupted.

### Lifecycle

```
IncrementalProcessor created
        │
        ▼
prepare_text()
  - Loads and ingests the source file
  - Detects chapters
  - Cleans and chunks all chapters
  - Stores the chapter/chunk plan in memory
        │
        ▼
process_next_chapter()  ← called repeatedly until is_complete()
  - Takes the next unprocessed chapter
  - Synthesises each chunk via the active TTS backend
  - Writes chunk WAVs to out/<project>/chunks/
  - Updates internal progress state
        │
        ▼
finalize_book()
  - Concatenates chunk WAVs into per-chapter WAVs
  - Concatenates chapter WAVs into book.wav
  - Saves project.json (chunk index)
  - Saves meta.json (project metadata)
  - Optionally normalises book.wav
```

### Progress object

`get_progress()` returns a `ProcessingProgress` dataclass that the UI uses to
render progress metrics:

```