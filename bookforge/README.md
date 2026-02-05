# BookForge

Public domain texts → high-quality local TTS audiobooks (Piper backend).

## Dev quickstart

```bash
cd bookforge
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev,piper]"
bookforge --help
```
