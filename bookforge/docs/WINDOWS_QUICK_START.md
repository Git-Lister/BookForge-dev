# 🪟 Windows Quick Start Guide for BookForge

## The Issue You Hit

You used **Linux/Mac line continuation** (`\`) on Windows:

```batch
❌ WRONG - This breaks:
bookforge process books/test.txt out/my-first-book \
  --backend piper \
  --voice-model voices/en_GB-southern_english_female-low.onnx
```

**Error:** `Got unexpected extra argument (\)`

---

## ✅ Correct Windows Syntax

### Option 1: Single-Line (Recommended - No Hassle)

```batch
bookforge process books/test.txt out/my-first-book --backend piper --voice-model voices/en_GB-southern_english_female-low.onnx
```

### Option 2: Multi-Line with `^` (Windows Continuation Character)

```batch
bookforge process books/test.txt out/my-first-book ^
  --backend piper ^
  --voice-model voices/en_GB-southern_english_female-low.onnx ^
  --preset calm_longform
```

**Key Difference:**
- **Linux/Mac:** `\` at end of line
- **Windows:** `^` at end of line

---

## Common Commands (Windows)

### 1. Process a Book (Piper Backend)
```batch
bookforge process books/test.txt out/my-audiobook --backend piper --voice-model voices/en_GB-southern_english_female-low.onnx
```

### 2. Process with XTTS Backend
```batch
bookforge process books/test.txt out/my-audiobook --backend xtts --speaker-wav voices/reference.wav
```

### 3. Review a Specific Chunk
```batch
bookforge review out/my-audiobook 53
```

### 4. Re-synthesize with New Text
```batch
bookforge review out/my-audiobook 53 --new-text "New text here"
```

### 5. Launch Streamlit UI
```batch
streamlit run src/bookforge/ui.py
```

### 6. Normalize Audio
```batch
bookforge normalise out/my-audiobook/book.wav --target-lufs -16.0
```

---

## Help & Options

```batch
bookforge --help
bookforge process --help
bookforge review --help
bookforge normalise --help
```

---

## ✅ What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| **Piper TTS** | ✅ Ready | Fully implemented |
| **XTTS Backend** | ✅ Ready | Supports voice cloning |
| **Voice Models** | ✅ Ready | `voices/en_GB-southern_english_female-low.onnx` present |
| **Streamlit UI** | ✅ Ready | Run `streamlit run src/bookforge/ui.py` |
| **Chapter Detection** | ✅ Ready | Multiple strategies supported |
| **Audio Normalization** | ✅ Ready | EBU R128 standard |

---

## 📝 Shell vs Batch

| Feature | PowerShell | CMD (batch) | WSL (Linux) |
|---------|-----------|-----------|-----------|
| **Line Continuation** | `` ` `` (backtick) | `^` | `\` |
| **Recommended** | ✅ Works well | ✅ Traditional | ✅ Full Linux |
| **Example** | `` bookforge process ... ` `` | `bookforge process ... ^` | `bookforge process ... \` |

---

## 🔧 Troubleshooting

### "Got unexpected extra argument (\)"
→ Remove the `\` or change to `^` for Windows

### "'--backend' is not recognized as an internal or external command"
→ You split the command using `\` (Linux syntax). Use single-line or `^` instead.

### "ffmpeg not found"
→ Install ffmpeg: `winget install ffmpeg` or see full README

### "ModuleNotFoundError: No module named 'pathvalidate'"
→ Run: `pip install pathvalidate`

---

## 🚀 Next Steps

1. **Run this command to process a book:**
   ```batch
   bookforge process books/test.txt out/test-book --backend piper --voice-model voices/en_GB-southern_english_female-low.onnx
   ```

2. **View it in Streamlit:**
   ```batch
   streamlit run src/bookforge/ui.py
   ```

3. **Review specific chunks:**
   ```batch
   bookforge review out/test-book 0
   ```

Enjoy! 🎧
