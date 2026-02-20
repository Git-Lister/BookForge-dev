"""BookForge CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict

import typer

from .config import PresetConfig
from .project import BookProject
from .ingest.txt_ingest import load_txt, BookText as TxtBookText
from .process.cleaner import clean_text
from .process.chunker import chunk_chapter, Chunk
from .audio.concat import concat_wavs
from .tts.piper import PiperBackend
from .tts.xtts import XTTSBackend

app = typer.Typer(help="Convert texts/epubs into audiobooks using local TTS.")


def _rebuild_audio_from_index(
    project: BookProject,
    index: List[Dict[str, object]],
    skip_first_chunks: int = 0,
) -> None:
    """Rebuild per-chapter WAVs and book.wav from existing chunk WAVs and index."""
    if not index:
        typer.echo("Index is empty; nothing to concatenate.")
        return

    typer.echo("Rebuilding per-chapter WAVs from existing chunks ...")

    sorted_meta = sorted(index, key=lambda m: int(m["id"]))
    if skip_first_chunks > 0:
        typer.echo(f"Skipping first {skip_first_chunks} chunks when concatenating.")
        sorted_meta = sorted_meta[skip_first_chunks:]

    chunks_by_chapter: Dict[int, List[Path]] = {}
    for meta in sorted_meta:
        chapter_idx = int(meta["chapter_index"])
        fname = str(meta["file"])
        wav_path = project.chunks_dir / fname
        if not wav_path.exists():
            continue
        chunks_by_chapter.setdefault(chapter_idx, []).append(wav_path)

    chapter_wavs: List[Path] = []
    for chapter_idx in sorted(chunks_by_chapter.keys()):
        chapter_chunk_files = sorted(chunks_by_chapter[chapter_idx])
        chapter_wav = project.chapters_dir / f"chapter_{chapter_idx + 1:02d}.wav"
        typer.echo(
            f"  Concatenating {len(chapter_chunk_files)} chunks "
            f"for chapter {chapter_idx + 1} → {chapter_wav.name}"
        )
        concat_wavs(chapter_chunk_files, chapter_wav)
        chapter_wavs.append(chapter_wav)

    if chapter_wavs:
        book_wav = project.root / "book.wav"
        typer.echo(f"Concatenating {len(chapter_wavs)} chapter WAVs into {book_wav} ...")
        concat_wavs(chapter_wavs, book_wav)
        typer.echo("Rebuild complete.")
    else:
        typer.echo("No chapter WAVs created during rebuild.")


@app.command()
def process(
    input_file: Path,
    output_dir: Path,
    voice_model: Path = typer.Option(
        ...,
        "--voice-model",
        "-m",
        help=(
            "Path to Piper ONNX model file "
            "(e.g. en_GB-southern_english_female-medium.onnx)."
        ),
    ),
    backend: str = typer.Option(
        "piper",
        "--backend",
        help="TTS backend to use: 'piper' or 'xtts'",
    ),
    speaker_wav: Optional[Path] = typer.Option(
        None,
        "--speaker-wav",
        help="Optional reference WAV for XTTS voice cloning",
    ),
    preset: str = "calm_longform",
    skip_first_chunks: int = typer.Option(
        0,
        "--skip-first-chunks",
        help="Number of initial chunks to skip when building chapter/book WAVs.",
    ),
    chapter_strategy: str = typer.Option(
        "auto",
        "--chapter-strategy",
        help=(
            "Chapter detection method: "
            "auto (default, tries multiple strategies), "
            "markdown (# headers), "
            "structured (Chapter N, Part I, etc.), "
            "heuristic (contextual scoring), "
            "paragraph (large gaps), "
            "none (single chapter)"
        ),
    ),
    chapter_min_confidence: float = typer.Option(
        0.5,
        "--chapter-min-confidence",
        help="Minimum confidence for chapter detection (0.0-1.0).",
    ),
    normalize: bool = typer.Option(
        False,
        "--normalize",
        help="Apply loudness normalization to final book.wav (EBU R128 standard).",
    ),
    target_lufs: float = typer.Option(
        -16.0,
        "--target-lufs",
        help="Target loudness in LUFS for normalization (default: -16.0 for audiobooks).",
    ),
) -> None:
    """Process INPUT_FILE into an audiobook under OUTPUT_DIR (TXT only for now)."""
    if not input_file.exists():
        raise typer.BadParameter(f"Input file not found: {input_file}")

    output_dir.mkdir(parents=True, exist_ok=True)
    project = BookProject(output_dir)
    config = PresetConfig.load(preset)

    # Choose TTS backend
    if backend == "piper":
        tts_backend = PiperBackend(str(voice_model))
    elif backend == "xtts":
        tts_backend = XTTSBackend(speaker_wav=speaker_wav)
    else:
        raise typer.BadParameter(f"Unknown backend: {backend}")

    typer.echo(f"Loading text from {input_file} ...")
    # Pass chapter detection options to loader
    book: TxtBookText = load_txt(
        input_file,
        chapter_strategy=chapter_strategy,
        min_confidence=chapter_min_confidence,
    )

    typer.echo(f"Title: {book.title}")
    typer.echo(f"Chapters: {len(book.chapters)}")

    # Report detected chapter titles
    if book.chapter_titles:
        typer.echo("\nDetected chapters:")
        for i, title in enumerate(book.chapter_titles[:10]):  # Show first 10
            typer.echo(f"  {i + 1}. {title}")
        if len(book.chapter_titles) > 10:
            typer.echo(f"  ... and {len(book.chapter_titles) - 10} more")
        typer.echo("")

    all_chunk_meta: List[Dict[str, object]] = []
    chunk_id = 0

    for chapter_index, chapter_text in enumerate(book.chapters):
        typer.echo(f"Cleaning chapter {chapter_index + 1} ...")
        cleaned = clean_text(chapter_text)

        typer.echo(f"Chunking chapter {chapter_index + 1} ...")
        chunks = chunk_chapter(cleaned, config, chapter_index, starting_chunk_id=chunk_id)
        if not chunks:
            continue
        chunk_id = chunks[-1].id + 1

        for chunk in chunks:
            out_wav = project.chunks_dir / f"chunk_{chunk.id:05d}.wav"
            typer.echo(
                f"  Synthesizing chunk {chunk.id} (chapter {chapter_index + 1}) "
                f"→ {out_wav.name}"
            )
            tts_backend.synthesize_chunk(chunk, config, out_wav)
            all_chunk_meta.append(chunk.to_dict())

    # Save project index
    project.save_index(all_chunk_meta)
    typer.echo(
        f"Saved project index with {len(all_chunk_meta)} chunks to {project.index_path}"
    )

    # Save simple metadata (including source file path for review)
    project.save_meta(
        {
            "source_file": str(input_file.resolve()),
            "preset": preset,
            "voice_model": str(voice_model),
            "chapter_strategy": chapter_strategy,
            "chapter_min_confidence": chapter_min_confidence,
        }
    )

    # Build per-chapter WAVs and book.wav from the index
    if not all_chunk_meta:
        typer.echo("No chunks generated; nothing to concatenate.")
        return

    _rebuild_audio_from_index(project, all_chunk_meta, skip_first_chunks=skip_first_chunks)
    typer.echo(f"  - {len(all_chunk_meta)} chunk WAVs in {project.chunks_dir}")

    # Apply normalization if requested
    if normalize:
        book_wav = output_dir / "book.wav"
        if book_wav.exists():
            typer.echo(f"\nNormalizing audio to {target_lufs} LUFS ...")
            normalized_wav = output_dir / "book_normalized.wav"

            from .audio.normalise import normalize_audio
            normalize_audio(book_wav, normalized_wav, target_lufs=target_lufs)

            # Replace original with normalized version
            book_wav.unlink()
            normalized_wav.rename(book_wav)
            typer.echo(f"✓ Normalized {book_wav}")
        else:
            typer.echo("Warning: book.wav not found, skipping normalization.")


@app.command()
def review(
    project_dir: Path,
    chunk: int,
    new_text: Optional[str] = typer.Option(
        None,
        "--new-text",
        help="Override text for this chunk; if omitted, reuses current text.",
    ),
    skip_first_chunks: int = typer.Option(
        0,
        "--skip-first-chunks",
        help="Number of initial chunks to skip when rebuilding chapter/book WAVs.",
    ),
) -> None:
    """Review/re-render a specific CHUNK inside an existing project directory."""
    project = BookProject(project_dir)

    index = project.load_index()
    if not index:
        raise typer.BadParameter(f"No project.json found in {project_dir}")

    meta = project.load_meta()
    source_file_str = meta.get("source_file")
    if not source_file_str:
        raise typer.BadParameter(
            f"No source_file recorded in {project.meta_path}; "
            "re-run process to create meta.json."
        )

    source_file = Path(source_file_str)
    if not source_file.exists():
        raise typer.BadParameter(f"Source file not found: {source_file}")

    # Find metadata for this chunk id
    try:
        chunk_meta = next(m for m in index if int(m["id"]) == chunk)
    except StopIteration:
        raise typer.BadParameter(f"Chunk id {chunk} not found in project index.")

    chapter_idx = int(chunk_meta["chapter_index"])

    # Re-ingest and re-chunk to get the text for this chunk
    typer.echo(f"Reloading source text from {source_file} ...")
    book: TxtBookText = load_txt(source_file)

    if chapter_idx >= len(book.chapters):
        raise typer.BadParameter(
            f"Chapter index {chapter_idx} out of range for source text."
        )

    from .process.chunker import chunk_chapter as re_chunk_chapter

    preset_name = str(meta.get("preset", "calm_longform"))
    config = PresetConfig.load(preset_name)

    typer.echo(f"Re-chunking chapter {chapter_idx + 1} to locate chunk {chunk} ...")
    cleaned = clean_text(book.chapters[chapter_idx])
    chapter_chunks: List[Chunk] = re_chunk_chapter(
        cleaned, config, chapter_idx, starting_chunk_id=chunk_meta["id"]
    )

    # Find the matching Chunk instance by id
    try:
        original_chunk = next(c for c in chapter_chunks if c.id == chunk)
    except StopIteration:
        raise typer.BadParameter(
            f"Chunk id {chunk} not found when re-chunking chapter {chapter_idx + 1}."
        )

    typer.echo("\nCurrent chunk text (truncated to 400 chars):\n")
    preview = original_chunk.text[:400]
    typer.echo(preview + ("..." if len(original_chunk.text) > 400 else ""))
    typer.echo("")

    # Decide which text to use
    updated_text = new_text if new_text is not None else original_chunk.text
    if new_text is not None:
        typer.echo("Using provided --new-text for re-synthesis.")

    # Build a new Chunk object with updated text
    updated_chunk = Chunk(
        id=original_chunk.id,
        chapter_index=original_chunk.chapter_index,
        relative_index=original_chunk.relative_index,
        text=updated_text,
        estimated_seconds=original_chunk.estimated_seconds,
    )

    # Re-synthesise this chunk
    voice_model_str = meta.get("voice_model")
    if not voice_model_str:
        raise typer.BadParameter(
            f"No voice_model recorded in {project.meta_path}; "
            "re-run process to create meta.json."
        )

    backend = PiperBackend(voice_model_str)
    out_wav = project.chunks_dir / f"chunk_{updated_chunk.id:05d}.wav"
    typer.echo(f"Re-synthesising chunk {updated_chunk.id} → {out_wav} ...")
    backend.synthesize_chunk(updated_chunk, config, out_wav)

    # Rebuild chapter WAV(s) and book.wav
    typer.echo("Rebuilding chapter and book audio after chunk update ...")
    _rebuild_audio_from_index(project, index, skip_first_chunks=skip_first_chunks)

@app.command()
def normalise(
    audio_file: Path,
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: adds '_normalised' suffix to input)",
    ),
    target_lufs: float = typer.Option(
        -16.0,
        "--target-lufs",
        help="Target loudness in LUFS (default: -16.0 for audiobooks).",
    ),
) -> None:
    """Normalise an existing audio file to consistent loudness (EBU R128)."""
    if not audio_file.exists():
        raise typer.BadParameter(f"Audio file not found: {audio_file}")

    # Default output: same name with _normalised suffix
    if output_file is None:
        output_file = audio_file.parent / f"{audio_file.stem}_normalised{audio_file.suffix}"

    typer.echo(f"Normalising {audio_file} ...")
    typer.echo(f"Target loudness: {target_lufs} LUFS")
    typer.echo("This may take several minutes for large files...")

    from .audio.normalise import normalize_audio
    normalize_audio(audio_file, output_file, target_lufs=target_lufs)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    typer.echo(f"\n✓ Success!")
    typer.echo(f"  Input:  {audio_file}")
    typer.echo(f"  Output: {output_file}")
    typer.echo(f"  Size:   {file_size_mb:.1f} MB")



def main() -> None:
    app()


if __name__ == "__main__":
    main()
