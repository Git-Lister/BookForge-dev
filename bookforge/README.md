```markdown
# BookForge

Convert text files into audiobooks using local TTS (Piper).

## Requirements

- Python 3.10+
- ffmpeg (for audio concatenation)
- ~2GB disk space for voice models

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Git-Lister/BookForge-dev.git
cd BookForge-dev/bookforge
```

### 2. Create and activate virtual environment

```bash
python -m venv .venv
```

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -e ".[dev,piper]"
```

If you encounter `ModuleNotFoundError: No module named 'pathvalidate'`:

```bash
pip install pathvalidate
```

### 4. Install ffmpeg

#### Option A: Using winget (Windows 10/11)

```bash
winget install ffmpeg
```

Close and reopen your terminal, then verify:

```bash
ffmpeg -version
```

#### Option B: Manual installation (if PATH cannot be modified)

1. Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) – choose `ffmpeg-release-essentials.zip`
2. Extract to a stable location, e.g. `C:\Users\<YourUser>\Tools\ffmpeg-release-essentials\`
3. Edit `src/bookforge/audio/concat.py` and set the `FFMPEG_BIN` path:

```python
FFMPEG_BIN = r"C:\Users\<YourUser>\Tools\ffmpeg-release-essentials\bin\ffmpeg.exe"
```

### 5. Download voice model

1. Go to [Hugging Face: rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/southern_english_female/low)
2. Download both files:
   - `en_GB-southern_english_female-low.onnx`
   - `en_GB-southern_english_female-low.onnx.json`
3. Create a `voices/` directory in the repo root and place files inside:

```
BookForge-dev/bookforge/voices/
    en_GB-southern_english_female-low.onnx
    en_GB-southern_english_female-low.onnx.json
```

Alternative voice models available at [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/en).

### 6. Verify installation

```bash
bookforge --help
```

Expected output:

```
Usage: bookforge [OPTIONS] COMMAND [ARGS]...

  Convert texts/epubs into audiobooks using local TTS.

Commands:
  process  Process INPUT_FILE into an audiobook under OUTPUT_DIR
  review   Review/re-render a specific CHUNK inside an existing project...
```

## Usage

### Process a text file

```bash
bookforge process books/input.txt out/output ^
  --voice-model "voices/en_GB-southern_english_female-low.onnx" ^
  --skip-first-chunks 0
```

**Note:** On Linux/Mac use `\` instead of `^` for line continuation.

Output structure:

```
out/output/
  chunks/
    chunk_00000.wav
    chunk_00001.wav
    ...
  chapters/
    chapter_01.wav
    chapter_02.wav
  book.wav
  project.json
  meta.json
```

### Review and re-render a chunk

```bash
bookforge review out/output 53
```

To override chunk text:

```bash
bookforge review out/output 53 --new-text "Corrected text here"
```

## Command Reference

### `bookforge process`

```bash
bookforge process INPUT_FILE OUTPUT_DIR [OPTIONS]
```

**Options:**
- `--voice-model, -m PATH` – Path to Piper ONNX model file (required)
- `--preset TEXT` – Voice preset name (default: `calm_longform`)
- `--skip-first-chunks INT` – Number of initial chunks to skip when concatenating (default: 0)

### `bookforge review`

```bash
bookforge review PROJECT_DIR CHUNK [OPTIONS]
```

**Arguments:**
- `PROJECT_DIR` – Path to existing project directory
- `CHUNK` – Chunk ID to review/re-render

**Options:**
- `--new-text TEXT` – Override text for this chunk
- `--skip-first-chunks INT` – Number of initial chunks to skip when rebuilding (default: 0)

## Project Structure

```
bookforge/
  ├── books/              # Input text files
  ├── out/                # Generated audiobooks (gitignored)
  ├── presets/            # Voice configuration presets
  ├── src/bookforge/      # Main package
  │   ├── audio/          # Audio concatenation
  │   ├── ingest/         # Text/EPUB loaders
  │   ├── process/        # Text cleaning and chunking
  │   └── tts/            # Piper TTS backend
  ├── tests/              # Test suite
  ├── voices/             # Piper voice models (gitignored)
  └── pyproject.toml      # Package configuration
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'pathvalidate'`

```bash
pip install pathvalidate
```

### `FileNotFoundError: [WinError 2] The system cannot find the file specified` (ffmpeg)

ffmpeg is not installed or not on PATH. See Installation step 4.

### `ValueError: Unable to find voice: ...`

Check:
1. Voice model files exist in `voices/` directory
2. Full path to `.onnx` file is passed to `--voice-model`
3. Both `.onnx` and `.onnx.json` files are present

### `RuntimeError: Piper failed: ...`

Check the error message in the traceback. If it mentions "surrogates not allowed", the input text has encoding issues. BookForge will skip the problematic chunk and log it to `out/debug/`.

## License

MIT License – see [LICENSE](LICENSE)
```