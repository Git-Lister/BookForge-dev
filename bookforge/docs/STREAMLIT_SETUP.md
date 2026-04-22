# BookForge Streamlit UI Setup Guide

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install in development mode with UI support
pip install -e ".[ui]"

# Or install requirements directly
pip install streamlit>=1.30.0
```

### 2. Process a Book First

The Streamlit UI requires a processed project. Create one using the CLI:

```bash
# Process a text file into audiobook chunks
bookforge process books/test.txt out/my-audiobook --backend piper --voice-model voices/en_GB-southern_english_female-low.onnx

# This creates the output structure:
# out/my-audiobook/
#   ├── chunks/           (individual synthesized chunks)
#   ├── chapters/         (concatenated chapters)
#   ├── book.wav         (full audiobook)
#   ├── project.json     (chunk metadata index)
#   └── meta.json        (project metadata)
```

### 3. Launch the Streamlit UI

Run from the project root directory:

```bash
streamlit run src/bookforge/ui.py
```

This will:
- Open `http://localhost:8501` in your browser
- Display the Streamlit interface
- Load available projects from the `out/` directory

### 4. Using the UI

**📚 Full Book Tab:**
- Listen to the complete rendered audiobook
- Shows file size in MB

**📖 Chapters Tab:**
- Expandable chapters
- Each chapter shows synthesis for that section

**🎵 Chunks Tab:**
- Filter by chapter number
- Preview individual chunks with text
- Evaluate prosody, pacing, and synthesis quality
- Listen to segments separately for detailed review

---

## 📝 Project Structure

After running `bookforge process`:

```
out/
├── my-audiobook/
│   ├── chunks/
│   │   ├── chunk_00001.wav
│   │   ├── chunk_00002.wav
│   │   └── ...
│   ├── chapters/
│   │   ├── chapter_01.wav
│   │   ├── chapter_02.wav
│   │   └── ...
│   ├── book.wav           (concatenated full book)
│   ├── project.json       (chunk metadata: id, chapter_index, text, file)
│   └── meta.json          (backend, preset, source_file, voice_model)
```

---

## 🔧 Development Notes

### Comparing to Django (Your Previous Experience)

| Django | Streamlit |
|--------|-----------|
| URLs & Views | Single script (`ui.py`) |
| Templates (HTML) | Streamlit components (`st.audio`, `st.selectbox`) |
| Static File Serving | Automatic (relative paths) |
| Session State | `st.session_state` dict |
| Database Queries | Direct Python (no ORM needed) |
| Routing | No URL routing; single flow |
| Forms | Streamlit widgets + `st.form()` |

### Key Differences:

1. **No template files** - Everything in Python
2. **Reactive** - Script reruns on every interaction
3. **State management** - Use `st.session_state` for persistence across reruns
4. **Simpler** - No complex routing; just sequential component rendering

### UI Improvements Made:

✅ Better error handling for missing files  
✅ Empty directory warnings  
✅ Added chunk counts and file sizes  
✅ Improved sidebar metadata display  
✅ Enhanced chapter filtering with chunk previews  
✅ Added emoji for visual clarity  
✅ Better file validation  

---

## ✅ Testing Checklist

- [ ] Install streamlit: `pip install streamlit>=1.30.0`
- [ ] Process a test book: `bookforge process books/test.txt out/test-project --backend piper --voice-model voices/en_GB-southern_english_female-low.onnx`
- [ ] Launch UI: `streamlit run src/bookforge/ui.py`
- [ ] Verify project loads in sidebar
- [ ] Test each tab (Full Book, Chapters, Chunks)
- [ ] Verify audio playback works
- [ ] Test chunk filtering by chapter

---

## 🐛 Troubleshooting

**"No 'out/' directory found"**
→ Run `bookforge process` to create a project first

**"Audio file missing"**
→ Check if synthesis completed; verify `out/project-name/chunks/` has `.wav` files

**"No chunks found"**
→ Verify `project.json` exists and has content; check synthesis logs

**Streamlit crashes**
→ Run with debug mode: `streamlit run --logger.level=debug src/bookforge/ui.py`

---

## 📚 Next Steps

1. **Experiment with different presets:** Try `calm_longform_v2` or custom YAML configs
2. **Test XTTS backend:** `--backend xtts --speaker-wav reference.wav`
3. **Use the `review` command:** Re-synthesize specific chunks
4. **Add normalization:** Use `--normalize` flag for consistent loudness

Enjoy your audiobooks! 🎧
