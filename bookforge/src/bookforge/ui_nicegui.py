"""
BookForge Studio – NiceGUI UI (live progress, stop button, chapter status cards, load existing configs)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from nicegui import ui

from bookforge.incremental_processor import IncrementalProcessor, AbortException
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
# Helpers
# ---------------------------------------------------------------------------
def list_books() -> list[str]:
    return sorted([p.name for p in BOOKS_DIR.glob("*.txt") if p.is_file()])

def list_voices() -> list[str]:
    return sorted([p.name for p in VOICES_DIR.glob("*.onnx") if p.is_file()])

def list_projects() -> list[str]:
    # Only projects that have meta.json
    return sorted([
        p.name for p in OUT_DIR.iterdir()
        if p.is_dir() and (p / "meta.json").exists()
    ])

async def run_in_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

async def extract_upload_bytes(e) -> tuple[bytes, str]:
    source = None
    if hasattr(e, "file") and e.file is not None:
        source = e.file
    elif hasattr(e, "files") and e.files:
        source = e.files[0]
    if source is None:
        raise AttributeError("Upload event has no file data.")
    if hasattr(source, "data") and source.data is not None:
        data = source.data
        if isinstance(data, bytes):
            return data, getattr(source, "name", "uploaded_file")
        if asyncio.iscoroutine(data):
            result = await data
            if isinstance(result, bytes):
                return result, getattr(source, "name", "uploaded_file")
            if hasattr(result, "read"):
                return result.read(), getattr(source, "name", "uploaded_file")
    if hasattr(source, "content") and source.content is not None:
        return source.content.read(), getattr(source, "name", "uploaded_file")
    if hasattr(source, "read"):
        val = source.read()
        if asyncio.iscoroutine(val):
            val = await val
        if isinstance(val, bytes):
            return val, getattr(source, "name", "uploaded_file")
    raise AttributeError(f"Cannot extract bytes from {type(source).__name__}")

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
@ui.page("/")
async def main_page():
    processor: Optional[IncrementalProcessor] = None
    book_event: Optional[Any] = None
    speaker_event: Optional[Any] = None
    step_state = ["Setup"]
    step_cards: dict[str, ui.element] = {}

    # Notification area
    with ui.column().classes("w-full") as notif_area:
        pass

    def safe_notify(msg: str, type: str = "positive"):
        with notif_area:
            ui.notify(msg, type=type, timeout=5)

    # Stepper header
    with ui.row().classes("gap-4 q-mb-md justify-center"):
        for step_name in ["Setup", "Prepare", "Synthesize", "Finalize", "Review"]:
            ui.button(step_name).props("flat").on_click(lambda s=step_name: set_step(s))

    def set_step(step: str):
        step_state[0] = step
        for name, card in step_cards.items():
            card.visible = (name == step)

    # ████████████████████████ Setup Card ████████████████████████
    with ui.column().classes("w-full") as setup_card:
        step_cards["Setup"] = setup_card
        ui.label("1. Setup").classes("text-h6 q-mb-md")
        ui.markdown("Select your book, TTS backend, and voice settings. Or load a previous project.")

        # ---- Load existing project ----
        existing_projects = list_projects()
        if existing_projects:
            with ui.row().classes("items-center gap-2 q-mb-md"):
                ui.label("Load previous project").classes("text-caption")
                load_project_select = ui.select(
                    options=[""] + existing_projects,
                    value="",
                    on_change=lambda e: load_existing_project(e.value),
                ).classes("w-64")
        else:
            load_project_select = None

        def load_existing_project(project_name: str):
            if not project_name:
                return
            meta_path = OUT_DIR / project_name / "meta.json"
            if not meta_path.exists():
                return
            import json
            with meta_path.open("r") as f:
                meta = json.load(f)
            # Fill form fields with saved values
            source_file = meta.get("source_file", "")
            book_name = Path(source_file).name if source_file else ""
            if book_name and (BOOKS_DIR / book_name).exists():
                book_select.value = book_name
            else:
                book_select.value = ""
            output_name.value = project_name
            backend_radio.value = meta.get("backend", "piper")
            # After changing backend, rebuild voice widgets
            build_voice_widgets()
            # Voice model for piper
            if meta.get("voice_model"):
                vm_path = Path(meta["voice_model"])
                vm_name = vm_path.name if vm_path.exists() else ""
                if vm_name and backend_radio.value == "piper" and voice_model_select:
                    voice_model_select.value = vm_name
            # Speaker wav is tricky (uploaded file), so skip.
            # Preset, chapter strategy, etc.
            preset_select.value = meta.get("preset", "calm_longform")
            chapter_strategy.value = meta.get("chapter_strategy", "auto")
            chapter_confidence.value = float(meta.get("chapter_min_confidence", 0.5))
            normalize_check.value = meta.get("normalize", False)
            if meta.get("target_lufs"):
                target_lufs.value = float(meta["target_lufs"])
            safe_notify(f"Loaded project '{project_name}'. You can adjust settings and continue.")

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
                    label="Output project name", value="my-audiobook"
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
                chapter_confidence = ui.slider(min=0.0, max=1.0, step=0.05, value=0.5).classes("w-full")
                ui.label().bind_text_from(chapter_confidence, "value", backward=lambda v: f"Confidence: {v:.2f}")
                normalize_check = ui.checkbox("Normalize final book", value=False)
                target_lufs = ui.number(
                    label="Target LUFS", value=-16.0, step=0.5, format="%.1f"
                ).bind_visibility_from(normalize_check, "value")

        def on_book_upload(e):
            nonlocal book_event
            book_event = e
            name = getattr(e.file, "name", "uploaded_book.txt") if hasattr(e, "file") else "uploaded_book.txt"
            safe_notify(f"Book '{name}' selected", type="positive")

        def on_speaker_upload(e):
            nonlocal speaker_event
            speaker_event = e
            name = getattr(e.file, "name", "speaker.wav") if hasattr(e, "file") else "speaker.wav"
            safe_notify(f"Speaker WAV '{name}' selected", type="positive")

        ui.button("Save & Continue", on_click=lambda: setup_next()).props("unelevated color=primary")

    async def setup_next():
        nonlocal processor, book_event, speaker_event
        errors = []
        book_path: Optional[Path] = None
        if book_event is not None:
            try:
                book_bytes, book_filename = await extract_upload_bytes(book_event)
                book_path = TMP_DIR / book_filename
                book_path.write_bytes(book_bytes)
            except Exception as e:
                errors.append(f"Failed to read uploaded book: {e}")
        elif book_select.value:
            book_path = BOOKS_DIR / book_select.value
        else:
            errors.append("Please select a book.")
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
        else:
            if speaker_event is None:
                errors.append("XTTS requires a reference speaker WAV upload.")
            else:
                try:
                    speaker_bytes, speaker_filename = await extract_upload_bytes(speaker_event)
                    speaker_wav = TMP_DIR / speaker_filename
                    speaker_wav.write_bytes(speaker_bytes)
                except Exception as e:
                    errors.append(f"Failed to read speaker WAV: {e}")
        if errors:
            for err in errors:
                safe_notify(err, type="negative")
            return
        try:
            tts_backend = await run_in_thread(
                get_backend,
                backend_type=backend,
                voice_model=voice_model,
                speaker_wav=speaker_wav,
            )
            processor = IncrementalProcessor(
                input_file=book_path,
                output_dir=OUT_DIR / output_name.value.strip(),
                backend=tts_backend,
                preset=preset_select.value,
                chapter_strategy=chapter_strategy.value,
                chapter_min_confidence=chapter_confidence.value,
                normalize=normalize_check.value,
                target_lufs=target_lufs.value,
            )
            processor.backend_name = backend
            safe_notify("Configuration saved!", type="positive")
            set_step("Prepare")
        except Exception as e:
            safe_notify(f"Failed to create processor: {e}", type="negative")

    # ████████████████████████ Prepare Card ████████████████████████
    with ui.column().classes("w-full") as prepare_card:
        step_cards["Prepare"] = prepare_card
        ui.label("2. Prepare Book").classes("text-h6")
        prepare_status = ui.label("Press the button to analyse the book.")
        prepare_btn = ui.button("Prepare Book", icon="auto_stories")

        async def on_prepare():
            nonlocal processor
            if processor is None:
                safe_notify("No configuration saved.", type="negative")
                return
            prepare_btn.disable()
            try:
                await run_in_thread(processor.prepare_text)
                progress = processor.get_progress()
                prepare_status.set_text(f"✅ {progress.total_chapters} chapters found.")
                safe_notify("Book prepared!", type="positive")
                set_step("Synthesize")
            except Exception as e:
                safe_notify(f"Preparation failed: {e}", type="negative")
            finally:
                prepare_btn.enable()

        prepare_btn.on_click(lambda: on_prepare())

    # ████████████████████████ Synthesize Card ████████████████████████
    with ui.column().classes("w-full") as synth_card:
        step_cards["Synthesize"] = synth_card
        ui.label("3. Synthesize").classes("text-h6")
        status_label = ui.label("Ready")
        overall_progress = ui.linear_progress(value=0).props("size=20px")
        chapter_progress = ui.linear_progress(value=0).props("size=15px color=secondary")
        spinner = ui.spinner(size="lg").props("color=primary")
        spinner.visible = False
        # Use ui.html to display chapter badges (HTML)
        chapter_status_html = ui.html("").classes("q-mb-md")

        timer = ui.timer(1.0, lambda: update_progress_display(), active=False)

        def update_progress_display():
            nonlocal processor
            if not processor:
                return
            progress = processor.get_progress()
            overall_progress.set_value(progress.overall_progress)
            chapter_progress.set_value(progress.chapter_progress)
            status_label.set_text(f"{progress.status_message} (ETA: {progress.estimated_time_remaining})")
            if processor.chapter_progress:
                html_parts = ['<div style="display:flex; flex-wrap:wrap; gap:8px;">']
                for ch in processor.chapter_statuses:
                    badge = "⚪"
                    if ch["error"]:
                        badge = "🔴"
                    elif ch["processed"]:
                        badge = "🟢"
                    else:
                        badge = "🔵" if ch["chunks_done"] > 0 else "⚪"
                    status_text = f"{badge} Ch{ch['index']}"
                    if ch["error"]:
                        status_text += " ❌"
                    html_parts.append(
                        f'<span style="padding:4px 8px; border:1px solid #ccc; border-radius:4px; font-size:0.85rem;">{status_text}</span>'
                    )
                html_parts.append('</div>')
                chapter_status_html.set_content(''.join(html_parts))

        stop_flag = False
        next_btn = ui.button("Process Next Chapter", icon="skip_next")
        all_btn = ui.button("Process All Remaining", icon="fast_forward")
        stop_btn = ui.button("Stop", icon="stop", color="negative")
        stop_btn.visible = False

        async def _process_chapter():
            nonlocal processor
            if processor is None or processor.book_text is None:
                safe_notify("No prepared book.", type="negative")
                return False
            try:
                await run_in_thread(processor.process_next_chapter)
                return True
            except AbortException:
                safe_notify("Processing stopped by user.", type="warning")
                return False
            except Exception as e:
                safe_notify(f"Chapter error: {e}", type="negative")
                return False

        async def process_one():
            nonlocal stop_flag
            stop_flag = False
            start_processing_ui()
            success = await _process_chapter()
            stop_processing_ui()
            if success:
                update_progress_display()
                if processor and processor.is_complete():
                    set_step("Finalize")

        async def process_all():
            nonlocal stop_flag
            stop_flag = False
            start_processing_ui()
            all_btn.disable()
            try:
                while processor and not processor.is_complete() and not stop_flag:
                    success = await _process_chapter()
                    if not success:
                        break
                    update_progress_display()
                    await asyncio.sleep(0.1)
            except Exception:
                safe_notify("Processing stopped unexpectedly.", type="negative")
            finally:
                all_btn.enable()
                stop_processing_ui()
                update_progress_display()
                if processor and processor.is_complete():
                    safe_notify("All chapters synthesised!", type="positive")
                    set_step("Finalize")

        def start_processing_ui():
            spinner.visible = True
            stop_btn.visible = True
            timer.activate()
            update_progress_display()

        def stop_processing_ui():
            spinner.visible = False
            stop_btn.visible = False
            timer.deactivate()
            update_progress_display()

        def stop_handler():
            nonlocal stop_flag
            if processor:
                processor.abort()
            stop_flag = True

        next_btn.on_click(lambda: process_one())
        all_btn.on_click(lambda: process_all())
        stop_btn.on_click(lambda: stop_handler())

    # ████████████████████████ Finalize Card ████████████████████████
    with ui.column().classes("w-full") as finalize_card:
        step_cards["Finalize"] = finalize_card
        ui.label("4. Finalize Book").classes("text-h6")
        finalize_status = ui.label("Synthesis complete. Click to finalize.")
        finalize_btn = ui.button("Finalize Book", icon="done_all")
        audio_player = ui.audio("").classes("hidden")

        async def on_finalize():
            nonlocal processor
            if processor is None:
                safe_notify("No active project.", type="negative")
                return
            finalize_btn.disable()
            try:
                await run_in_thread(processor.finalize_book)
                book_wav = processor.output_dir / "book.wav"
                if book_wav.exists():
                    audio_player.set_source(str(book_wav))
                    audio_player.classes(remove="hidden")
                    finalize_status.set_text("✅ Audiobook ready!")
                    safe_notify("Book finalized!", type="positive")
                    set_step("Review")
            except Exception as e:
                safe_notify(f"Finalization error: {e}", type="negative")
            finally:
                finalize_btn.enable()

        finalize_btn.on_click(lambda: on_finalize())

    # ████████████████████████ Review Card ████████████████████████
    with ui.column().classes("w-full") as review_card:
        step_cards["Review"] = review_card
        ui.label("5. Review Existing Projects").classes("text-h6")
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

    set_step("Setup")

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