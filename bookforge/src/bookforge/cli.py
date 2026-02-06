"""BookForge CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .config import PresetConfig
from .project import BookProject
from .ingest.txt_ingest import load_txt, BookText as TxtBookText
from .process.cleaner import clean_text
from .process.chunker import chunk_chapter
from .tts.piper import PiperBackend
from .audio.concat import concat_wavs


app = typer.Typer(help="Convert texts/epubs into audiobooks using local TTS.")


@app.command()
def process(
    input_file: Path,
    output_dir: Path,
    voice_model: Path = typer.Option(
        ...,
        "--voice-model",
        "-m",
        help="Path to Piper ONNX model file (e.g. en_GB-southern_english_female-medium.onnx).",
    ),
    preset: str = "calm_longform",
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

    chunk_id = 0
    for chapter_index, chapter_text in enumerate(book.chapters):
        typer.echo(f"Cleaning chapter {chapter_index + 1} ...")
        cleaned = clean_text(chapter_text)

        typer.echo(f"Chunking chapter {chapter_index + 1} ...")
        chunks = chunk_chapter(cleaned, config, chapter_index, starting_chunk_id=chunk_id)
        chunk_id = chunks[-1].id + 1 if chunks else chunk_id

        for chunk in chunks:
            out_wav = output_dir / "chunks" / f"chunk_{chunk.id:05d}.wav"
            typer.echo(f"  Synthesizing chunk {chunk.id} → {out_wav.name}")
            backend.synthesize_chunk(chunk, config, out_wav)

        # After synthesizing all chunks, concatenate them into a single book.wav
    chunks_dir = output_dir / "chunks"
    chunk_files = sorted(chunks_dir.glob("chunk_*.wav"))

    if chunk_files:
        book_wav = output_dir / "book.wav"
        typer.echo(f"Concatenating {len(chunk_files)} chunks into {book_wav} ...")
        concat_wavs(chunk_files, book_wav)
        typer.echo("Done. Generated book.wav and individual chunk WAVs.")
    else:
        typer.echo("No chunk WAV files found; nothing to concatenate.")


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
