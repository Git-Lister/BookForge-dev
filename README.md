# BookForge (AI READ ME - For AI, by AI)

> **Local, GPU-accelerated audiobook creation with Piper TTS and XTTS v2**

BookForge converts plain text files into high-quality audiobooks using open-source neural text-to-speech engines. Run entirely on your own machine — no cloud APIs, no subscriptions, full control.

## ✨ Features

- 🎙️ **Dual TTS backends**: Fast Piper TTS or expressive XTTS v2 voice cloning
- 🐳 **Docker support**: Reproducible CUDA environment for XTTS on Windows/Linux
- 📖 **Smart chapter detection**: Auto, markdown, structured, heuristic strategies
- 🎵 **Incremental processing**: Chapter-by-chapter synthesis with progress tracking
- 🖥️ **Streamlit UI**: Browser-based interface for setup, processing, and review
- 🔄 **Chunk-level control**: Review and re-synthesize individual segments
- 🎚️ **Audio normalization**: EBU R128 loudness standardization
- 🗂️ **Project store**: Resume interrupted sessions, keep organized outputs

## 🚀 Quick Start

### With Docker (Recommended for XTTS)

```bash
# Clone and navigate
git clone https://github.com/Git-Lister/BookForge-dev.git
cd BookForge-dev/bookforge

# Build the Docker image
docker build -t bookforge-xtts .

# Run Streamlit UI
docker run --gpus all --rm -it -p 8501:8501 -v "%cd%:/app" bookforge-xtts
```

Open `http://localhost:8501` and follow the UI workflow.

### Without Docker (Piper only)

```bash
cd bookforge
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev,piper,ui]"
streamlit run src/bookforge/ui.py
```

## 📚 Documentation

- **[Installation Guide](bookforge/README.md)** — Full setup for Windows/Linux/Mac
- **[Docker Setup](bookforge/docs/DOCKER_SETUP.md)** — XTTS + CUDA environment
- **[How BookForge Works](bookforge/docs/HOW_BOOKFORGE_WORKS.md)** — Architecture deep-dive
- **[Streamlit UI Guide](bookforge/docs/STREAMLIT_SETUP.md)** — Using the web interface
- **[Contributing](bookforge/CONTRIBUTING.md)** — Development guidelines

## 🎯 Use Cases

- **Academic audiobooks** for complex theory texts
- **Personal narration** of public-domain literature
- **Accessibility** tools for visual impairments
- **Rapid prototyping** of TTS workflows

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| TTS (quality) | Coqui XTTS v2 |
| TTS (speed) | Piper TTS |
| Deep learning | PyTorch + CUDA 12.1 |
| UI | Streamlit |
| CLI | Typer |
| Container | Docker (NVIDIA CUDA base) |
| Audio | ffmpeg, libsndfile |

## 📝 License

MIT License — see [LICENSE](bookforge/LICENSE)

## 🙏 Acknowledgments

- [Coqui TTS](https://github.com/coqui-ai/TTS) for XTTS v2
- [Piper TTS](https://github.com/rhasspy/piper) for lightweight synthesis
- [rhasspy](https://github.com/rhasspy) for voice models

---

**Status:** Active development | Python 3.11+ | Docker recommended for XTTS
