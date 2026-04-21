"""Streamlit UI for BookForge with a staged processing workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import streamlit as st

from bookforge.incremental_processor import IncrementalProcessor
from bookforge.project import BookProject
from bookforge.tts.factory import get_backend

st.set_page_config(page_title="BookForge Studio", layout="wide")


def init_state() -> None:
    defaults: dict[str, Any] = {
        "workflow_stage": "setup",
        "processor": None,
        "current_project_dir": None,
        "current_input_file": None,
        "config_saved": False,
        "job_error": None,
        "job_message": "",
        "uploaded_input_path": None,
        "uploaded_speaker_wav_path": None,
        "selected_project": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def books_dir() -> Path:
    return Path("books")


def voices_dir() -> Path:
    return Path("voices")


def out_dir() -> Path:
    return Path("out")


def temp_dir() -> Path:
    path = Path("temp")
    path.mkdir(parents=True, exist_ok=True)
    return path


def available_books() -> list[Path]:
    d = books_dir()
    if not d.exists():
        return []
    return sorted(d.glob("*.txt"))


def available_voices() -> list[Path]:
    d = voices_dir()
    if not d.exists():
        return []
    return sorted(d.glob("*.onnx"))


def available_projects() -> list[Path]:
    d = out_dir()
    if not d.exists():
        return []
    return sorted([p for p in d.iterdir() if p.is_dir()])


def save_uploaded_file(uploaded_file, prefix: str) -> Path:
    destination = temp_dir() / f"{prefix}_{uploaded_file.name}"
    with destination.open("wb") as f:
        f.write(uploaded_file.getvalue())
    return destination


def reset_workflow(keep_project_selection: bool = True) -> None:
    selected_project = st.session_state.selected_project if keep_project_selection else None
    st.session_state.workflow_stage = "setup"
    st.session_state.processor = None
    st.session_state.current_project_dir = None
    st.session_state.current_input_file = None
    st.session_state.config_saved = False
    st.session_state.job_error = None
    st.session_state.job_message = ""
    st.session_state.uploaded_input_path = None
    st.session_state.uploaded_speaker_wav_path = None
    st.session_state.selected_project = selected_project


def stage_badge(stage: str) -> str:
    mapping = {
        "setup": "1. Setup",
        "prepared": "2. Prepared",
        "processing": "3. Processing",
        "complete": "4. Complete",
        "error": "Error",
    }
    return mapping.get(stage, stage.title())


def get_selected_input_file(selected_book_name: Optional[str], uploaded_file) -> Optional[Path]:
    if uploaded_file is not None:
        uploaded_path = save_uploaded_file(uploaded_file, "input")
        st.session_state.uploaded_input_path = uploaded_path
        return uploaded_path

    if selected_book_name:
        candidate = books_dir() / selected_book_name
        if candidate.exists():
            return candidate

    return None


def get_selected_speaker_wav(uploaded_wav) -> Optional[Path]:
    if uploaded_wav is None:
        return None
    wav_path = save_uploaded_file(uploaded_wav, "speaker")
    st.session_state.uploaded_speaker_wav_path = wav_path
    return wav_path


def render_header() -> None:
    st.title("🔨 BookForge Studio")
    st.caption("Step-by-step audiobook creation with local TTS backends.")


def render_sidebar() -> None:
    st.sidebar.header("Workflow")
    st.sidebar.metric("Current stage", stage_badge(st.session_state.workflow_stage))

    if st.session_state.current_project_dir:
        st.sidebar.caption(f"Project: {st.session_state.current_project_dir}")

    if st.session_state.job_message:
        st.sidebar.info(st.session_state.job_message)

    if st.session_state.job_error:
        st.sidebar.error(st.session_state.job_error)

    st.sidebar.divider()

    if st.sidebar.button("Reset workflow", use_container_width=True):
        reset_workflow()
        st.rerun()


def render_setup_tab() -> None:
    st.subheader("Setup")
    st.write("Choose your input, backend, and output settings, then save the configuration.")

    local_books = available_books()
    local_voices = available_voices()

    with st.form("setup_form", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Source")
            selected_book_name = st.selectbox(
                "Book from books/",
                options=[""] + [p.name for p in local_books],
                help="Pick a local .txt file from the books directory.",
            )
            uploaded_book = st.file_uploader(
                "Or upload a .txt file",
                type=["txt"],
                help="Uploaded files are copied to a temporary folder for processing.",
            )

            output_name = st.text_input(
                "Output project name",
                value="my-audiobook",
                help="This creates/uses out/<project-name>.",
            ).strip()

        with col2:
            st.markdown("### Voice")
            backend = st.radio(
                "Backend",
                options=["piper", "xtts"],
                horizontal=True,
            )

            voice_model_name: Optional[str] = None
            if backend == "piper":
                voice_model_name = st.selectbox(
                    "Piper voice model",
                    options=[""] + [p.name for p in local_voices],
                    help="Select an ONNX model from voices/.",
                )
                uploaded_speaker_wav = None
            else:
                uploaded_speaker_wav = st.file_uploader(
                    "Reference voice WAV",
                    type=["wav"],
                    help="Required for XTTS. Upload a clean speaker sample WAV.",
                )

            preset = st.selectbox(
                "Preset",
                options=["calm_longform", "calm_longform_v2"],
                index=0,
            )

            chapter_strategy = st.selectbox(
                "Chapter detection",
                options=["auto", "markdown", "structured", "heuristic", "paragraph", "none"],
                index=0,
            )

            chapter_min_confidence = st.slider(
                "Chapter confidence",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.05,
            )

            normalize = st.checkbox("Normalize final book", value=False)
            target_lufs = st.number_input(
                "Target LUFS",
                value=-16.0,
                step=0.5,
                format="%.1f",
                disabled=not normalize,
            )

        submitted = st.form_submit_button("Save configuration", use_container_width=True)

    if submitted:
        try:
            input_file = get_selected_input_file(selected_book_name or None, uploaded_book)
            if input_file is None:
                raise ValueError("Select a local book or upload a .txt file.")

            if not output_name:
                raise ValueError("Please provide an output project name.")

            voice_model = None
            speaker_wav_path = None

            if backend == "piper":
                if not voice_model_name:
                    raise ValueError("Please select a Piper voice model.")
                voice_model = voices_dir() / voice_model_name
                if not voice_model.exists():
                    raise ValueError(f"Voice model not found: {voice_model}")
            else:
                speaker_wav_path = get_selected_speaker_wav(uploaded_speaker_wav)
                if speaker_wav_path is None:
                    raise ValueError("XTTS requires a reference speaker WAV.")

            config = {
                "input_file": input_file,
                "output_dir": out_dir() / output_name,
                "backend": backend,
                "voice_model": voice_model,
                "speaker_wav": speaker_wav_path,
                "preset": preset,
                "chapter_strategy": chapter_strategy,
                "chapter_min_confidence": chapter_min_confidence,
                "normalize": normalize,
                "target_lufs": target_lufs,
            }

            tts_backend = get_backend(
                backend_type=backend,
                voice_model=voice_model,
                speaker_wav=speaker_wav_path,
            )

            processor = IncrementalProcessor(
                input_file=config["input_file"],
                output_dir=config["output_dir"],
                backend=tts_backend,
                preset=config["preset"],
                chapter_strategy=config["chapter_strategy"],
                chapter_min_confidence=config["chapter_min_confidence"],
                normalize=config["normalize"],
                target_lufs=config["target_lufs"],
            )

            st.session_state.processor = processor
            st.session_state.current_input_file = str(config["input_file"])
            st.session_state.current_project_dir = str(config["output_dir"])
            st.session_state.config_saved = True
            st.session_state.workflow_stage = "setup"
            st.session_state.job_error = None
            st.session_state.job_message = "Configuration saved. Ready to prepare the book."
            st.success("Configuration saved.")
            st.rerun()

        except Exception as e:
            st.session_state.job_error = str(e)
            st.error(f"Failed to save configuration: {e}")

    if st.session_state.config_saved and st.session_state.current_project_dir:
        st.info(f"Ready to work on: `{st.session_state.current_project_dir}`")


def render_progress_metrics() -> None:
    processor = st.session_state.processor
    if processor is None:
        st.info("No active workflow yet. Save configuration in Setup first.")
        return

    progress = processor.get_progress()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stage", str(progress.stage).replace("_", " ").title())
    col2.metric("Chapter", f"{progress.current_chapter}/{progress.total_chapters}")
    col3.metric("Chunk", f"{progress.current_chunk}/{progress.total_chunks}")
    col4.metric("Overall", f"{progress.overall_progress:.1%}")

    st.progress(progress.overall_progress)
    st.caption(progress.status_message)

    col5, col6 = st.columns(2)
    col5.info(f"Elapsed: {progress.elapsed_time}")
    col6.info(f"ETA: {progress.estimated_time_remaining}")


def render_workflow_tab() -> None:
    st.subheader("Workflow")

    if st.session_state.processor is None:
        st.info("Start in the Setup tab to create a processor.")
        return

    render_progress_metrics()

    st.markdown("### Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Prepare book", use_container_width=True):
            try:
                st.session_state.processor.prepare_text()
                st.session_state.workflow_stage = "prepared"
                st.session_state.job_error = None
                st.session_state.job_message = "Book prepared. Chapters are ready for synthesis."
                st.success("Preparation complete.")
                st.rerun()
            except Exception as e:
                st.session_state.workflow_stage = "error"
                st.session_state.job_error = str(e)
                st.error(f"Preparation failed: {e}")

    with col2:
        if st.button("Process next chapter", use_container_width=True):
            try:
                st.session_state.processor.process_next_chapter()
                st.session_state.workflow_stage = (
                    "complete" if st.session_state.processor.is_complete() else "processing"
                )
                st.session_state.job_error = None
                st.session_state.job_message = "Processed one chapter."
                st.success("Processed next chapter.")
                st.rerun()
            except Exception as e:
                st.session_state.workflow_stage = "error"
                st.session_state.job_error = str(e)
                st.error(f"Chapter processing failed: {e}")

    with col3:
        if st.button("Finalize book", use_container_width=True):
            try:
                st.session_state.processor.finalize_book()
                st.session_state.workflow_stage = "complete"
                st.session_state.job_error = None
                st.session_state.job_message = "Book finalized successfully."
                st.success("Finalization complete.")
                st.rerun()
            except Exception as e:
                st.session_state.workflow_stage = "error"
                st.session_state.job_error = str(e)
                st.error(f"Finalization failed: {e}")

    st.markdown("### Bulk processing")
    if st.button("Process all remaining chapters", type="primary", use_container_width=True):
        try:
            while not st.session_state.processor.is_complete():
                st.session_state.processor.process_next_chapter()
            st.session_state.workflow_stage = "complete"
            st.session_state.job_error = None
            st.session_state.job_message = "All chapters processed. You can finalize or review outputs."
            st.success("Finished processing all remaining chapters.")
            st.rerun()
        except Exception as e:
            st.session_state.workflow_stage = "error"
            st.session_state.job_error = str(e)
            st.error(f"Bulk processing failed: {e}")


def render_library_tab() -> None:
    st.subheader("Library")

    projects = available_projects()
    if not projects:
        st.info("No projects found in out/. Process a book first.")
        return

    project_names = [p.name for p in projects]
    current_selection = st.session_state.selected_project
    default_index = 0
    if current_selection in project_names:
        default_index = project_names.index(current_selection)

    selected = st.selectbox("Projects", project_names, index=default_index)
    st.session_state.selected_project = selected

    project_path = out_dir() / selected
    project = BookProject(project_path)
    meta = project.load_meta()
    index = project.load_index()

    col1, col2, col3 = st.columns(3)
    col1.metric("Chunks", len(index))
    col2.metric("Backend", str(meta.get("backend", "unknown")) if meta else "unknown")
    col3.metric("Preset", str(meta.get("preset", "unknown")) if meta else "unknown")

    book_wav = project_path / "book.wav"
    if book_wav.exists():
        st.markdown("### Full book")
        st.audio(str(book_wav), format="audio/wav")

    chapter_files = sorted(project.chapters_dir.glob("*.wav"))
    if chapter_files:
        st.markdown("### Chapters")
        for chapter_file in chapter_files:
            with st.expander(chapter_file.name):
                st.audio(str(chapter_file), format="audio/wav")

    with st.expander("Project metadata"):
        st.json(meta if meta else {})


def render_review_tab() -> None:
    st.subheader("Review")

    projects = available_projects()
    if not projects:
        st.info("No projects available for review yet.")
        return

    project_names = [p.name for p in projects]
    current_selection = st.session_state.selected_project
    default_index = 0
    if current_selection in project_names:
        default_index = project_names.index(current_selection)

    selected = st.selectbox("Review project", project_names, index=default_index, key="review_project")
    st.session_state.selected_project = selected

    project_path = out_dir() / selected
    project = BookProject(project_path)
    index = project.load_index()

    if not index:
        st.info("No chunk index found for this project yet.")
        return

    chapters = sorted(list({int(m["chapter_index"]) for m in index}))
    selected_chapter = st.selectbox(
        "Chapter",
        chapters,
        format_func=lambda x: f"Chapter {x + 1}",
    )

    chapter_chunks = [m for m in index if int(m["chapter_index"]) == selected_chapter]
    st.caption(f"{len(chapter_chunks)} chunk(s) in this chapter.")

    for meta in chapter_chunks:
        chunk_id = int(meta["id"])
        file_name = str(meta["file"])
        wav_file = project.chunks_dir / file_name
        text_value = str(meta.get("text", ""))

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"**Chunk {chunk_id:03d}**")
            if wav_file.exists():
                st.audio(str(wav_file), format="audio/wav")
            else:
                st.warning(f"Missing audio: {file_name}")

        with col2:
            st.text_area(
                f"Chunk text {chunk_id}",
                value=text_value[:1000],
                height=140,
                disabled=True,
                key=f"chunk_text_{chunk_id}",
            )
        st.divider()


def main() -> None:
    init_state()
    render_header()
    render_sidebar()

    workflow_tab, setup_tab, library_tab, review_tab = st.tabs(
        ["Workflow", "Setup", "Library", "Review"]
    )

    with workflow_tab:
        render_workflow_tab()

    with setup_tab:
        render_setup_tab()

    with library_tab:
        render_library_tab()

    with review_tab:
        render_review_tab()


if __name__ == "__main__":
    main()