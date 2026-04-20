"""Streamlit-based local UI for BookForge project review and processing."""

import json
import threading
import time
from pathlib import Path
from typing import Optional

import streamlit as st

from bookforge.cli import get_backend
from bookforge.incremental_processor import IncrementalProcessor
from bookforge.project import BookProject

st.set_page_config(page_title="BookForge Laboratory", layout="wide")

st.title("🔨 BookForge Studio")
st.markdown("Create and review audiobooks with local TTS.")

# Main navigation
main_tab_process, main_tab_review = st.tabs(["⚡ Process New Book", "🎧 Review Projects"])

# Global state for processing
if 'processor' not in st.session_state:
    st.session_state.processor = None
if 'processing_active' not in st.session_state:
    st.session_state.processing_active = False
if 'last_progress' not in st.session_state:
    st.session_state.last_progress = None

with main_tab_process:
    st.header("📝 Process New Book")
    st.write("Convert a text file into an audiobook with real-time progress tracking.")

    # Input configuration
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📁 Input File")
        books_dir = Path("books")
        if books_dir.exists():
            available_books = [f.name for f in books_dir.glob("*.txt")]
            if available_books:
                selected_book = st.selectbox(
                    "Select book from books/ directory:",
                    available_books,
                    help="Choose a .txt file from the books/ directory"
                )
                input_file = books_dir / selected_book
            else:
                st.warning("No .txt files found in books/ directory")
                input_file = None
        else:
            st.error("books/ directory not found")
            input_file = None

        # Alternative: file upload
        uploaded_file = st.file_uploader(
            "Or upload a text file:",
            type=['txt'],
            help="Upload a .txt file directly"
        )
        if uploaded_file:
            # Save uploaded file temporarily
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            input_file = temp_dir / uploaded_file.name
            with input_file.open('wb') as f:
                f.write(uploaded_file.getvalue())

    with col2:
        st.subheader("🎵 TTS Configuration")

        # Backend selection
        backend = st.radio(
            "TTS Backend:",
            ["piper", "xtts"],
            help="Piper: Fast, lightweight. XTTS: Advanced voice cloning"
        )

        # Voice model selection (for Piper)
        if backend == "piper":
            voices_dir = Path("voices")
            if voices_dir.exists():
                onnx_files = [f.name for f in voices_dir.glob("*.onnx")]
                if onnx_files:
                    voice_model_name = st.selectbox(
                        "Voice Model:",
                        onnx_files,
                        help="Select a Piper voice model (.onnx file)"
                    )
                    voice_model = voices_dir / voice_model_name
                else:
                    st.error("No .onnx voice models found in voices/ directory")
                    voice_model = None
            else:
                st.error("voices/ directory not found")
                voice_model = None
        else:
            voice_model = None

        # Speaker WAV for XTTS
        if backend == "xtts":
            speaker_wav = st.file_uploader(
                "Reference voice (optional):",
                type=['wav'],
                help="Upload a short WAV sample for voice cloning"
            )
            if speaker_wav:
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True)
                speaker_wav_path = temp_dir / speaker_wav.name
                with speaker_wav_path.open('wb') as f:
                    f.write(speaker_wav.getvalue())
            else:
                speaker_wav_path = None
        else:
            speaker_wav_path = None

        # Output directory
        output_name = st.text_input(
            "Output Project Name:",
            value="my-audiobook",
            help="Name for the output directory in out/"
        )
        output_dir = Path("out") / output_name

        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            preset = st.selectbox(
                "Voice Preset:",
                ["calm_longform", "calm_longform_v2"],
                help="Voice configuration preset"
            )
            chapter_strategy = st.selectbox(
                "Chapter Detection:",
                ["auto", "markdown", "structured", "heuristic", "paragraph", "none"],
                help="How to detect chapter breaks"
            )
            normalize = st.checkbox(
                "Apply Audio Normalization",
                value=False,
                help="Normalize loudness to -16 LUFS (audiobook standard)"
            )

    # Processing controls
    st.divider()

    # Check if we can start processing
    can_start = (
        input_file is not None and
        output_dir is not None and
        (backend == "xtts" or (backend == "piper" and voice_model is not None))
    )

    if not can_start:
        st.warning("⚠️ Please complete the configuration above to start processing.")
        st.stop()

    # Start/Stop/Resume processing
    col_start, col_stop, col_reset = st.columns(3)

    with col_start:
        if st.button("🚀 Start Processing", type="primary", disabled=st.session_state.processing_active):
            try:
                # Initialize TTS backend
                tts_backend = get_backend(backend, voice_model, speaker_wav_path)

                # Initialize incremental processor
                st.session_state.processor = IncrementalProcessor(
                    input_file=input_file,
                    output_dir=output_dir,
                    backend=tts_backend,
                    preset=preset,
                    chapter_strategy=chapter_strategy,
                    normalize=normalize,
                )

                st.session_state.processing_active = True
                st.rerun()  # Trigger immediate update

            except Exception as e:
                st.error(f"❌ Failed to initialize processing: {e}")

    with col_stop:
        if st.button("⏹️ Stop Processing", disabled=not st.session_state.processing_active):
            st.session_state.processing_active = False
            st.info("Processing stopped. You can resume later.")

    with col_reset:
        if st.button("🔄 Reset", disabled=st.session_state.processing_active):
            st.session_state.processor = None
            st.session_state.processing_active = False
            st.session_state.last_progress = None
            st.success("Processing reset. Ready to start fresh.")

    # Progress display
    if st.session_state.processor:
        progress = st.session_state.processor.get_progress()
        st.session_state.last_progress = progress

        # Progress overview
        st.subheader("📊 Processing Progress")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Stage", progress.stage.replace('_', ' ').title())
        with col2:
            st.metric("Chapter", f"{progress.current_chapter}/{progress.total_chapters}")
        with col3:
            st.metric("Overall", f"{progress.overall_progress:.1%}")

        # Progress bars
        st.progress(progress.overall_progress)
        if progress.total_chapters > 0:
            chapter_progress = progress.current_chapter / progress.total_chapters
            st.progress(chapter_progress, text=f"Chapter {progress.current_chapter}/{progress.total_chapters}")

        # Status and timing
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"⏱️ Elapsed: {progress.elapsed_time}")
        with col2:
            st.info(f"🎯 ETA: {progress.estimated_time_remaining}")

        # Current status
        st.success(f"📝 {progress.status_message}")

        # Detailed chunk progress
        if progress.current_chunk > 0 or progress.total_chunks > 0:
            chunk_progress = progress.current_chunk / max(progress.total_chunks, 1)
            st.progress(chunk_progress, text=f"Chunk {progress.current_chunk}/{progress.total_chunks}")

        # Auto-advance processing
        if st.session_state.processing_active and not st.session_state.processor.is_complete():
            try:
                # Process next chapter in background
                def process_background():
                    if st.session_state.processor:
                        st.session_state.processor.process_next_chapter()

                # Use a placeholder to trigger rerun after processing
                placeholder = st.empty()
                with placeholder.container():
                    st.info("🔄 Processing next chapter...")

                # Process in background thread
                thread = threading.Thread(target=process_background)
                thread.start()
                thread.join(timeout=1)  # Wait up to 1 second

                # Check if complete
                if st.session_state.processor and st.session_state.processor.is_complete():
                    st.session_state.processing_active = False
                    st.success("✅ Processing complete!")
                    st.balloons()

                    # Offer to finalize
                    if st.button("🎉 Finalize Book"):
                        try:
                            st.session_state.processor.finalize_book()
                            st.success("📚 Book finalized! Switch to Review tab to listen.")
                        except Exception as e:
                            st.error(f"❌ Finalization failed: {e}")
                else:
                    # Continue processing - rerun to update UI
                    time.sleep(0.5)  # Brief pause to prevent too frequent updates
                    st.rerun()

            except Exception as e:
                st.error(f"❌ Processing error: {e}")
                st.session_state.processing_active = False

        # Completion message
        if st.session_state.processor and st.session_state.processor.is_complete() and not st.session_state.processing_active:
            st.success("🎉 All processing complete!")
            st.info("Switch to the **Review Projects** tab to listen to your audiobook.")

    # Instructions
    with st.expander("ℹ️ How It Works"):
        st.markdown("""
        **Processing Stages:**
        1. **Text Preparation** (fast): Load book, detect chapters, clean text
        2. **Chapter Processing** (incremental): Convert each chapter to audio
        3. **Finalization** (fast): Combine chapters into complete book

        **Benefits:**
        - See real-time progress
        - Can stop/resume anytime
        - Process large books without UI freezing
        - Review chapters as they're completed
        """)

with main_tab_review:
    st.header("🎧 Review Existing Projects")
    st.write("Listen to and review your processed audiobooks.")

    # 1. Project Selection
    out_dir = Path("out")
    if not out_dir.exists():
        st.error("❌ No 'out/' directory found.")
        st.info("Process a book first using the **Process New Book** tab.")
        st.stop()

    projects = [p.name for p in out_dir.iterdir() if p.is_dir()]
    if not projects:
        st.warning("No projects found in 'out/' directory.")
        st.info("Create your first project using the **Process New Book** tab.")
        st.stop()

    selected_project_name = st.sidebar.selectbox("Select Project", projects, key="review_project")

    if selected_project_name:
        project_path = out_dir / selected_project_name
        project = BookProject(project_path)

        meta = project.load_meta()
        index = project.load_index()

        # 2. Metadata Display
        st.sidebar.header("📋 Project Info")
        if meta:
            # Display key info in a compact format
            with st.sidebar.expander("View full metadata"):
                st.json(meta)
            st.sidebar.metric("Total Chunks", len(index))
            st.sidebar.metric("Backend", meta.get("backend", "unknown"))
            st.sidebar.metric("Preset", meta.get("preset", "unknown"))
        else:
            st.sidebar.info("No project metadata found")

        # 3. Main View - Tabs for Book vs Chunks
        tab_book, tab_chapters, tab_chunks = st.tabs(["📚 Full Book", "📖 Chapters", "🎵 Chunks"])

        with tab_book:
            book_wav = project_path / "book.wav"
            if book_wav.exists():
                st.audio(str(book_wav), format='audio/wav')
                file_size_mb = book_wav.stat().st_size / (1024 * 1024)
                st.caption(f"📁 {book_wav.name} ({file_size_mb:.1f} MB)")
            else:
                st.info("Full book.wav not yet rendered. Check if synthesis completed.")

        with tab_chapters:
            chapter_files = sorted(list(project.chapters_dir.glob("*.wav")))
            if not chapter_files:
                st.info("No chapter files found yet.")
            else:
                st.write(f"Found {len(chapter_files)} chapter(s)")
                for chap in chapter_files:
                    with st.expander(f"▶️ {chap.name}"):
                        st.audio(str(chap), format='audio/wav')
                        file_size_mb = chap.stat().st_size / (1024 * 1024)
                        st.caption(f"{file_size_mb:.1f} MB")

        with tab_chunks:
            st.header("🎵 Exploratory Chunk Review")
            st.write("Evaluate pacing and prosody of synthesized speech.")

            if not index:
                st.warning("No chunks found in project index.")
                st.stop()

            # Filtering
            chapters = sorted(list(set(int(m["chapter_index"]) for m in index)))
            if not chapters:
                st.error("No chapters found in index.")
                st.stop()

            filter_chap = st.selectbox("Chapter", chapters, format_func=lambda x: f"Chapter {x+1}", key="review_chapter")

            chapter_chunks = [m for m in index if int(m["chapter_index"]) == filter_chap]
            st.write(f"Found {len(chapter_chunks)} chunks in this chapter")

            if not chapter_chunks:
                st.info("No chunks in this chapter.")
                st.stop()

            for meta in chapter_chunks:
                chunk_id = meta["id"]
                wav_file = project.chunks_dir / meta["file"]

                col1, col2 = st.columns([1, 2])

                with col1:
                    st.markdown(f"**Chunk {chunk_id:03d}**")
                    if wav_file.exists():
                        st.audio(str(wav_file))
                    else:
                        st.error(f"⚠️ Missing: {meta['file']}")

                with col2:
                    text_preview = meta.get("text", "[No text]")[:500]
                    st.text_area(
                        label=f"Text (ID: {chunk_id})",
                        value=text_preview,
                        height=100,
                        key=f"review_text_{chunk_id}",
                        disabled=True
                    )
                st.divider()
        st.header("🎵 Exploratory Chunk Review")
        st.write("Evaluate pacing and prosody of synthesized speech.")
        
        if not index:
            st.warning("No chunks found in project index.")
            st.stop()
        
        # Filtering
        chapters = sorted(list(set(int(m["chapter_index"]) for m in index)))
        if not chapters:
            st.error("No chapters found in index.")
            st.stop()
            
        filter_chap = st.selectbox("Chapter", chapters, format_func=lambda x: f"Chapter {x+1}")
        
        chapter_chunks = [m for m in index if int(m["chapter_index"]) == filter_chap]
        st.write(f"Found {len(chapter_chunks)} chunks in this chapter")
        
        if not chapter_chunks:
            st.info("No chunks in this chapter.")
            st.stop()
        
        for meta in chapter_chunks:
            chunk_id = meta["id"]
            wav_file = project.chunks_dir / meta["file"]
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown(f"**Chunk {chunk_id:03d}**")
                if wav_file.exists():
                    st.audio(str(wav_file))
                else:
                    st.error(f"⚠️ Missing: {meta['file']}")
            
            with col2:
                text_preview = meta.get("text", "[No text]")[:500]
                st.text_area(
                    label=f"Text (ID: {chunk_id})",
                    value=text_preview,
                    height=100,
                    key=f"text_{chunk_id}",
                    disabled=True
                )
            st.divider()
