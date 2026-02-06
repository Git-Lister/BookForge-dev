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


app = typer.Typer(help="Convert texts/epubs into audiobooks using local TTS.")


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
    preset: str = "calm_longform",
    skip_first_chunks: int = typer.Option(
        0,
        "--skip-first-chunks",
        help="Number of initial chunks to skip when building chapter/book WAVs.",
    ),
) -> None:
    """Process INPUT_FILE into an audiobook under OUTPUT_DIR (TXT only for now)."""
    if not input_file.exists():
        raise typer.BadParameter(f"Input file not found: {input_file}")

    output_dir.mkdir(parents=True, exist_ok=True)
    project = BookProject(output_dir)
    config = PresetConfig.load(preset)
    backend = PiperBackend(str(voice_model))

    typer.echo(f"Loading text from {input_file} ...")
    # TODO: detect EPUB vs TXT; for now assume TXT
    book: TxtBookText = load_txt(input_file)

    typer.echo(f"Title: {book.title}")
    typer.echo(f"Chapters: {len(book.chapters)}")

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
            backend.synthesize_chunk(chunk, config, out_wav)
            all_chunk_meta.append(chunk.to_dict())

    # Save project index
    project.save_index(all_chunk_meta)
    typer.echo(
        f"Saved project index with {len(all_chunk_meta)} chunks to {project.index_path}"
    )

    # Build per-chapter WAVs
    if not all_chunk_meta:
        typer.echo("No chunks generated; nothing to concatenate.")
        return

    typer.echo("Building per-chapter WAVs ...")

    # Apply global skip based on chunk id order (listenability: skip front matter)
    sorted_meta = sorted(all_chunk_meta, key=lambda m: int(m["id"]))
    if skip_first_chunks > 0:
        typer.echo(f"Skipping first {skip_first_chunks} chunks when concatenating.")
        sorted_meta = sorted_meta[skip_first_chunks:]

    # Group chunk file paths by chapter_index
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

    # Build full book.wav from chapter WAVs
    if chapter_wavs:
        book_wav = output_dir / "book.wav"
        typer.echo(f"Concatenating {len(chapter_wavs)} chapter WAVs into {book_wav} ...")
        concat_wavs(chapter_wavs, book_wav)
        typer.echo("Done. Generated:")
        typer.echo(f"  - {book_wav}")
        typer.echo(f"  - {len(chapter_wavs)} chapter WAVs in {project.chapters_dir}")
        typer.echo(f"  - {len(all_chunk_meta)} chunk WAVs in {project.chunks_dir}")
    else:
        typer.echo("No chapter WAVs created; check chunk metadata/index.")


@app.command()
def review(
    project_file: Path,
    chunk: int,
    new_text: Optional[str] = None,
) -> None:
    """Review/re-render a specific CHUNK inside PROJECT_FILE (future)."""
    typer.echo(f"Review stub: project={project_file}, chunk={chunk}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
