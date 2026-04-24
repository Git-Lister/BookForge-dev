"""
BookForge Studio – NiceGUI UI (async upload callbacks)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from nicegui import ui

from bookforge.incremental_processor import IncrementalProcessor
from bookforge.project import BookProject
from bookforge.tts.factory import get_backend

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BOOKS_DIR = Path("books")
VOICES_DIR = Path("voices")
OUT_DIR = Path("out")
TMP_DIR = Path("temp")
TMP_DIR.mkdir(exist_ok=True)
APP_TITLE = "🔨 BookForge Studio"

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_processor: Optional[IncrementalProcessor] = None
_config: dict[str, Any] = {}
_book_bytes: Optional[bytes] = None
_book_filename: str = "uploaded_book.txt"
_speaker_bytes: Optional[bytes] = None
_speaker_filename: str = "speaker.wav"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def list_books() -> list[str]:
    return sorted([p.name for p in BOOKS_DIR.glob("*.txt") if p.is_file()])

def list_voices() -> list[str]:
    return sorted([p.name for p in VOICES_DIR.glob("*.onnx") if p.is_file()])

def list_projects() -> list[str]:
    return sorted([p.name for p in OUT_DIR.iterdir() if p.is_dir()])

async def run_in_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

async def get_upload_bytes(e) -> bytes:
    """
    Extract file bytes from a NiceGUI upload event.
    Works with e.file (async read), e.content, e.data, etc.
    """
    # Primary path: e.file (starlette UploadFile) – requires async read
    if hasattr(e, "file") and e.file is not None:
        file_obj = e.file
        # Single file object with .read() (async)
        if hasattr(file_obj, "read"):
            return await file_obj.read()
        # Fallback if file_obj is a list (multiple files)
        if isinstance(file_obj, list) and file_obj:
            first = file_obj[0]
            if hasattr(first, "read"):
                return await first.read()
            if hasattr(first, "content"):
                return first.content.read()
            if hasattr(first, "data"):
                return first.data
    # Fallback: modern single-file with e.content (BytesIO, sync)
    if hasattr(e, "content") and e.content is not None:
        return e.content.read()
    # Fallback: older single-file with e.data (bytes)
    if hasattr(e, "data") and e.data is not None:
        return e.data
    # Fallback: multi-upload list
    if hasattr(e, "files") and e.files:
        first = e.files[0]
        if hasattr(first, "content"):
            return first.content.read()
        if hasattr(first, "data"):
            return first.data
        if hasattr(first, "read"):
            return await first.read()
    raise AttributeError(
        f"Cannot extract bytes from upload event. "
        f"Event type: {type(e).__name__}, attributes: {dir(e)}"
    )

def get_upload_filename(e) -> str:
    """Extract original filename from upload event."""
    if hasattr(e, "file") and e.file is not None:
        file_obj = e.file
        if hasattr(file_obj, "filename"):
            return file_obj.filename
        if isinstance(file_obj, list) and file_obj:
            first = file_obj[0]
            if hasattr(first, "filename"):
                return first.filename
    if hasattr(e, "name"):
        return e.name
    return "uploaded_file"

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
@ui.page("/")
async def main_page():
    global _processor, _config, _book_bytes, _book_filename, _speaker_bytes, _speaker_filename

    ui.label(APP_TITLE).classes("text-h4 text-primary q-mb-md")
    ui.markdown("Create audiobooks from text files using local TTS engines.")

    with ui.stepper().props("vertical").classes("w-full") as stepper:
        # ██████ Step 1 – Setup ██████
        with ui.step("Setup"):
            ui.label("1. Setup").classes("text-h6 q-mb-md")
            ui.markdown("Select your book, TTS backend, and voice settings.")

            with ui.row().classes("w-full gap-8"):
                with ui.column().classes("w-1/2"):
                    ui.label("📖 Source").classes("font-bold")
                    book_select = ui.select(
                        label="Book from books/",
                        options=[""] + list_books(),
                        value="",
                    ).classes("w-full")
                    ui.upload(
                        label="Or upload a .txt file",
                        on_upload=lambda e: on_book_upload(e),
                    ).classes("w-full")
                    output_name = ui.input(
                        label="Output project name",
                        value="my-audiobook",
                    ).classes("w-full")

                with ui.column().classes("w-1/2"):
                    ui.label("🎤 Voice").classes("font-bold")
                    backend_radio = ui.radio(
                        ["piper", "xtts"], value="piper", on_change=lambda: build_voice_widgets()
                    ).props("inline")
                    voice_container = ui.column().classes("w-full")
                    voice_model_select: Optional[ui.select] = None

                    def build_voice_widgets():
                        nonlocal voice_model_select
                        voice_container.clear()
                        if backend_radio.value == "piper":
                            voice_model_select = ui.select(
                                label="Piper voice model",
                                options=[""] + list_voices(),
                                value="",
                            ).classes("w-full")
                        else:
                            ui.upload(
                                label="Reference speaker WAV",
                                on_upload=lambda e: on_speaker_upload(e),
                            ).classes("w-full")
                            voice_model_select = None

                    build_voice_widgets()

                    preset_select = ui.select(
                        label="Preset",
                        options=["calm_longform", "calm_longform_v2"],
                        value="calm_longform",
                    ).classes("w-full")
                    chapter_strategy = ui.select(
                        label="Chapter detection",
                        options=["auto", "markdown", "structured", "heuristic", "paragraph", "none"],
                        value="auto",
                    ).classes("w-full")
                    chapter_confidence = ui.slider(
                        min=0.0, max=1.0, step=0.05, value=0.5,
                    ).classes("w-full")
                    ui.label().bind_text_from(chapter_confidence, "value", backward=lambda v: f"Confidence: {v:.2f}")

                    normalize_check = ui.checkbox("Normalize final book", value=False)
                    target_lufs = ui.number(
                        label="Target LUFS", value=-16.0, step=0.5, format="%.1f",
                    ).bind_visibility_from(normalize_check, "value")

            # ---- Upload callbacks (now async) ----
            async def on_book_upload(e):
                global _book_bytes, _book_filename
                try:
                    _book_bytes = await get_upload_bytes(e)
                    _book_filename = get_upload_filename(e)
                    ui.notify(f"Book '{_book_filename}' uploaded", type="positive")
                except Exception as exc:
                    ui.notify(f"Failed to read book file: {exc}", type="negative")

            async def on_speaker_upload(e):
                global _speaker_bytes, _speaker_filename
                try:
                    _speaker_bytes = await get_upload_bytes(e)
                    _speaker_filename = get_upload_filename(e)
                    ui.notify(f"Speaker WAV '{_speaker_filename}' uploaded", type="positive")
                except Exception as exc:
                    ui.notify(f"Failed to read speaker file: {exc}", type="negative")

            # ---- Next button ----
            ui.button("Next", on_click=lambda: setup_next()).props("unelevated color=primary")

            async def setup_next():
                global _processor, _config, _book_bytes, _book_filename, _speaker_bytes, _speaker_filename
                errors = []

                book_path: Optional[Path] = None
                if _book_bytes is not None:
                    book_path = TMP_DIR / _book_filename
                    book_path.write_bytes(_book_bytes)
                elif book_select.value:
                    book_path = BOOKS_DIR / book_select.value
                else:
                    errors.append("Please select a book from the list or upload one.")

                if not output_name.value.strip():
                    errors.append("Output project name is required.")

                backend = backend_radio.value
                voice_model: Optional[Path] = None
                speaker_wav: Optional[Path] = None
                if backend == "piper":
                    if not voice_model_select or not voice_model_select.value:
                        errors.append("Piper voice model is required.")
                    else:
                        voice_model = VOICES_DIR / voice_model_select.value
                        if not voice_model.exists():
                            errors.append(f"Voice model not found: {voice_model}")
                else:  # xtts
                    if _speaker_bytes is None:
                        errors.append("XTTS requires a reference speaker WAV upload.")
                    else:
                        speaker_wav = TMP_DIR / _speaker_filename
                        speaker_wav.write_bytes(_speaker_bytes)

                if errors:
                    for err in errors:
                        ui.notify(err, type="negative")
                    return

                _config = {
                    "input_file": book_path,
                    "output_dir": OUT_DIR / output_name.value.strip(),
                    "backend": backend,
                    "voice_model": voice_model,
                    "speaker_wav": speaker_wav,
                    "preset": preset_select.value,
                    "chapter_strategy": chapter_strategy.value,
                    "chapter_min_confidence": chapter_confidence.value,
                    "normalize": normalize_check.value,
                    "target_lufs": target_lufs.value,
                }

                try:
                    tts_backend = get_backend(
                        backend_type=backend,
                        voice_model=voice_model,
                        speaker_wav=speaker_wav,
                    )
                    _processor = IncrementalProcessor(
                        input_file=_config["input_file"],
                        output_dir=_config["output_dir"],
                        backend=tts_backend,
                        preset=_config["preset"],
                        chapter_strategy=_config["chapter_strategy"],
                        chapter_min_confidence=_config["chapter_min_confidence"],
                        normalize=_config["normalize"],
                        target_lufs=_config["target_lufs"],
                    )
                    ui.notify("Configuration saved!", type="positive")
                    stepper.next()
                except Exception as e:
                    ui.notify(f"Failed to create processor: {e}", type="negative")

        # ██████ Step 2 – Prepare ██████
        with ui.step("Prepare"):
            ui.label("2. Prepare Book").classes("text-h6")
            prepare_status = ui.label("Press the button to analyse the book.")
            prepare_btn = ui.button("Prepare Book", icon="auto_stories", on_click=lambda: on_prepare())

            async def on_prepare():
                global _processor
                if _processor is None:
                    ui.notify("No configuration saved. Go back to Setup.", type="negative")
                    return
                prepare_btn.disable()
                try:
                    await run_in_thread(_processor.prepare_text)
                    progress = _processor.get_progress()
                    prepare_status.set_text(f"✅ {progress.total_chapters} chapters found.")
                    ui.notify("Book prepared!", type="positive")
                    stepper.next()
                except Exception as e:
                    ui.notify(f"Preparation failed: {e}", type="negative")
                finally:
                    prepare_btn.enable()

        # ██████ Step 3 – Synthesize ██████
        with ui.step("Synthesize"):
            ui.label("3. Synthesize").classes("text-h6")
            status_label = ui.label("Ready")
            overall_progress = ui.linear_progress(value=0).props("size=20px")
            chapter_progress = ui.linear_progress(value=0).props("size=15px color=secondary")
            stop_flag = False

            async def _process_chapter():
                global _processor
                if _processor is None:
                    return
                try:
                    await run_in_thread(_processor.process_next_chapter)
                    progress = _processor.get_progress()
                    overall_progress.set_value(progress.overall_progress)
                    chapter_progress.set_value(progress.chapter_progress)
                    eta = progress.estimated_time_remaining
                    status_label.set_text(
                        f"{progress.status_message} (ETA: {eta})" if eta else progress.status_message
                    )
                except Exception as e:
                    ui.notify(f"Chapter error: {e}", type="negative")
                    raise

            async def process_one():
                nonlocal stop_flag
                stop_flag = False
                await _process_chapter()

            async def process_all():
                nonlocal stop_flag
                stop_flag = False
                next_btn.disable()
                all_btn.disable()
                try:
                    while _processor and not _processor.is_complete() and not stop_flag:
                        await _process_chapter()
                        await asyncio.sleep(0.1)
                finally:
                    next_btn.enable()
                    all_btn.enable()
                    if _processor and _processor.is_complete():
                        ui.notify("All chapters synthesised!", type="positive")
                        stepper.next()

            next_btn = ui.button("Process Next Chapter", icon="skip_next", on_click=lambda: process_one())
            all_btn = ui.button("Process All Remaining", icon="fast_forward", on_click=lambda: process_all())
            all_btn.props("color=secondary")

        # ██████ Step 4 – Finalize ██████
        with ui.step("Finalize"):
            ui.label("4. Finalize Book").classes("text-h6")
            finalize_status = ui.label("Synthesis complete. Click to finalize.")
            finalize_btn = ui.button("Finalize Book", icon="done_all", on_click=lambda: on_finalize())
            audio_player = ui.audio("").classes("hidden")

            async def on_finalize():
                global _processor
                if _processor is None:
                    ui.notify("No active project.", type="negative")
                    return
                finalize_btn.disable()
                try:
                    await run_in_thread(_processor.finalize_book)
                    book_wav = _processor.output_dir / "book.wav"
                    if book_wav.exists():
                        audio_player.set_source(str(book_wav))
                        audio_player.classes(remove="hidden")
                        finalize_status.set_text("✅ Audiobook ready!")
                        ui.notify("Book finalized!", type="positive")
                except Exception as e:
                    ui.notify(f"Finalization error: {e}", type="negative")
                finally:
                    finalize_btn.enable()

        # ██████ Step 5 – Review ██████
        with ui.step("Review Existing Projects"):
            ui.label("5. Review").classes("text-h6")
            project_select = ui.select(
                label="Select a project",
                options=[""] + list_projects(),
                on_change=lambda e: refresh_review(e.value),
            ).classes("w-full")
            review_area = ui.column()

            def refresh_review(project_name: str):
                review_area.clear()
                if not project_name:
                    return
                project_path = OUT_DIR / project_name
                project = BookProject(project_path)
                meta = project.load_meta()
                index = project.load_index()
                with review_area:
                    ui.label(f"Backend: {meta.get('backend','?')}  |  Chunks: {len(index)}")
                    book_wav = project_path / "book.wav"
                    if book_wav.exists():
                        ui.audio(str(book_wav)).classes("w-full")
                    chapters = sorted({m["chapter_index"] for m in index})
                    for ch in chapters:
                        ch_wav = project_path / "chapters" / f"chapter_{ch+1:02d}.wav"
                        with ui.expansion(f"Chapter {ch+1}", icon="menu_book").classes("w-full"):
                            if ch_wav.exists():
                                ui.audio(str(ch_wav))
                            for m in index:
                                if m["chapter_index"] == ch:
                                    chunk_wav = project_path / "chunks" / m["file"]
                                    if chunk_wav.exists():
                                        ui.label(f"Chunk {m['id']:05d}").classes("text-caption")
                                        ui.audio(str(chunk_wav))

    # Footer
    ui.markdown("---")
    ui.markdown("BookForge · MIT License · running locally")

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8501,
        title="BookForge Studio",
        favicon="🔨",
        reload=False,
        show=False,
    )