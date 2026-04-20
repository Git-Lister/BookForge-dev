# Incremental Book Processing for UI

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audio.concat import concat_wavs
from .config import PresetConfig
from .ingest.txt_ingest import BookText, load_txt
from .process.chunker import Chunk, chunk_chapter
from .process.cleaner import clean_text
from .project import BookProject
from .tts.backend import TTSBackend


@dataclass
class ProcessingProgress:
    """Detailed progress information for UI display."""
    stage: str  # 'preparing_text', 'processing_chapters', 'finalizing'
    current_chapter: int
    total_chapters: int
    current_chunk: int
    total_chunks: int
    chapter_progress: float  # 0.0 to 1.0
    overall_progress: float  # 0.0 to 1.0
    estimated_time_remaining: str
    status_message: str
    start_time: datetime
    elapsed_time: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage': self.stage,
            'current_chapter': self.current_chapter,
            'total_chapters': self.total_chapters,
            'current_chunk': self.current_chunk,
            'total_chunks': self.total_chunks,
            'chapter_progress': self.chapter_progress,
            'overall_progress': self.overall_progress,
            'estimated_time_remaining': self.estimated_time_remaining,
            'status_message': self.status_message,
            'start_time': self.start_time.isoformat(),
            'elapsed_time': self.elapsed_time,
        }


@dataclass
class ChapterProgress:
    """Progress state for a single chapter."""
    chapter_index: int
    cleaned_text: str
    chunks: List[Chunk]
    processed_chunks: int = 0
    chapter_audio_created: bool = False


class IncrementalProcessor:
    """
    Incremental book processor designed for UI-based workflows.

    Stages:
    1. Prepare text (fast): Load, detect chapters, clean text
    2. Process chapters (incremental): Chunk and synthesize each chapter
    3. Finalize (fast): Concatenate chapters into full book
    """

    def __init__(
        self,
        input_file: Path,
        output_dir: Path,
        backend: TTSBackend,
        preset: str = "calm_longform",
        chapter_strategy: str = "auto",
        chapter_min_confidence: float = 0.5,
        normalize: bool = False,
        target_lufs: float = -16.0,
    ):
        self.input_file = input_file
        self.output_dir = output_dir
        self.backend = backend
        self.preset = preset
        self.chapter_strategy = chapter_strategy
        self.chapter_min_confidence = chapter_min_confidence
        self.normalize = normalize
        self.target_lufs = target_lufs

        self.project = BookProject(output_dir)
        self.config = PresetConfig.load(preset)

        # State
        self.book_text: Optional[BookText] = None
        self.chapter_progress: List[ChapterProgress] = []
        self.all_chunks: List[Chunk] = []
        self.start_time = datetime.now()
        self.last_update_time = self.start_time

        # Progress file for persistence
        self.progress_file = self.output_dir / "processing_progress.json"

        # Load existing progress if available
        self._load_progress()

    def _load_progress(self) -> None:
        """Load existing progress from file."""
        if self.progress_file.exists():
            try:
                with self.progress_file.open('r') as f:
                    data = json.load(f)
                    # Restore state from saved progress
                    # (Implementation would restore chapter_progress, etc.)
                    pass
            except Exception:
                # If progress file is corrupted, start fresh
                pass

    def _save_progress(self) -> None:
        """Save current progress to file."""
        progress_data = {
            'input_file': str(self.input_file),
            'output_dir': str(self.output_dir),
            'preset': self.preset,
            'chapter_strategy': self.chapter_strategy,
            'chapter_min_confidence': self.chapter_min_confidence,
            'normalize': self.normalize,
            'target_lufs': self.target_lufs,
            'book_text': self.book_text.__dict__ if self.book_text else None,
            'chapter_progress': [
                {
                    'chapter_index': cp.chapter_index,
                    'processed_chunks': cp.processed_chunks,
                    'chapter_audio_created': cp.chapter_audio_created,
                    'chunks_count': len(cp.chunks),
                }
                for cp in self.chapter_progress
            ],
            'all_chunks_count': len(self.all_chunks),
            'start_time': self.start_time.isoformat(),
        }

        with self.progress_file.open('w') as f:
            json.dump(progress_data, f, indent=2)

    def prepare_text(self) -> None:
        """Stage 1: Load and prepare text (fast operation)."""
        if self.book_text is not None:
            return  # Already prepared

        # Load and detect chapters
        self.book_text = load_txt(
            self.input_file,
            chapter_strategy=self.chapter_strategy,
            min_confidence=self.chapter_min_confidence
        )

        # Initialize chapter progress
        self.chapter_progress = []
        for i, chapter_text in enumerate(self.book_text.chapters):
            cleaned = clean_text(chapter_text)
            self.chapter_progress.append(ChapterProgress(
                chapter_index=i,
                cleaned_text=cleaned,
                chunks=[]
            ))

        self._save_progress()

    def process_next_chapter(self) -> bool:
        """
        Stage 2: Process the next unprocessed chapter.

        Returns True if a chapter was processed, False if all done.
        """
        if not self.book_text:
            raise ValueError("Must call prepare_text() first")

        # Find next unprocessed chapter
        for chapter_prog in self.chapter_progress:
            if not chapter_prog.chapter_audio_created:
                self._process_chapter(chapter_prog)
                self._save_progress()
                return True

        return False  # All chapters processed

    def _process_chapter(self, chapter_prog: ChapterProgress) -> None:
        """Process a single chapter: chunk and synthesize."""
        chapter_idx = chapter_prog.chapter_index

        # Chunk the chapter if not already done
        if not chapter_prog.chunks:
            starting_chunk_id = len(self.all_chunks)
            chapter_prog.chunks = chunk_chapter(
                chapter_prog.cleaned_text,
                self.config,
                chapter_idx,
                starting_chunk_id=starting_chunk_id
            )

        # Synthesize chunks
        chunk_wav_files = []
        for chunk in chapter_prog.chunks:
            if chapter_prog.processed_chunks >= len(chapter_prog.chunks):
                continue  # Already processed

            # Synthesize this chunk
            out_wav = self.project.chunks_dir / f"chunk_{chunk.id:05d}.wav"
            self.backend.synthesize_chunk(chunk, self.config, out_wav)

            chunk_wav_files.append(out_wav)
            chapter_prog.processed_chunks += 1
            self.all_chunks.append(chunk)

            # Save progress after each chunk for resumability
            self._save_progress()

        # Concatenate chapter chunks into chapter audio
        if chunk_wav_files and not chapter_prog.chapter_audio_created:
            chapter_wav = self.project.chapters_dir / f"chapter_{chapter_idx + 1:02d}.wav"
            concat_wavs(chunk_wav_files, chapter_wav)
            chapter_prog.chapter_audio_created = True

    def finalize_book(self) -> None:
        """Stage 3: Finalize the complete book (fast operation)."""
        if not self.is_complete():
            raise ValueError("Cannot finalize: processing not complete")

        # Concatenate all chapter WAVs into final book
        chapter_wavs = []
        for i in range(len(self.chapter_progress)):
            chapter_wav = self.project.chapters_dir / f"chapter_{i + 1:02d}.wav"
            if chapter_wav.exists():
                chapter_wavs.append(chapter_wav)

        if chapter_wavs:
            book_wav = self.output_dir / "book.wav"
            concat_wavs(chapter_wavs, book_wav)

            # Apply normalization if requested
            if self.normalize:
                from .audio.normalise import normalize_audio
                normalized_wav = self.output_dir / "book_normalized.wav"
                normalize_audio(book_wav, normalized_wav, target_lufs=self.target_lufs)
                book_wav.unlink()
                normalized_wav.rename(book_wav)

        # Save final project metadata
        chunk_dicts = [chunk.to_dict() for chunk in self.all_chunks]
        self.project.save_index(chunk_dicts)

        self.project.save_meta({
            "backend": getattr(self.backend, '__class__', {}).get('__name__', 'unknown'),
            "source_file": str(self.input_file.resolve()),
            "preset": self.preset,
            "chapter_strategy": self.chapter_strategy,
            "chapter_min_confidence": self.chapter_min_confidence,
            "normalize": self.normalize,
            "target_lufs": self.target_lufs,
            "version": "1.1.0",
            "processing_completed": datetime.now().isoformat(),
        })

        # Clean up progress file
        if self.progress_file.exists():
            self.progress_file.unlink()

    def is_complete(self) -> bool:
        """Check if all processing is complete."""
        return (
            self.book_text is not None and
            all(cp.chapter_audio_created for cp in self.chapter_progress)
        )

    def get_progress(self) -> ProcessingProgress:
        """Get detailed progress information for UI display."""
        if not self.book_text:
            return ProcessingProgress(
                stage='preparing_text',
                current_chapter=0,
                total_chapters=0,
                current_chunk=0,
                total_chunks=0,
                chapter_progress=0.0,
                overall_progress=0.0,
                estimated_time_remaining='Unknown',
                status_message='Preparing text...',
                start_time=self.start_time,
                elapsed_time=self._format_elapsed_time(),
            )

        total_chapters = len(self.chapter_progress)
        completed_chapters = sum(1 for cp in self.chapter_progress if cp.chapter_audio_created)

        # Find current chapter being processed
        current_chapter_idx = 0
        current_chunk_total = 0
        for i, cp in enumerate(self.chapter_progress):
            if not cp.chapter_audio_created:
                current_chapter_idx = i
                current_chunk_total = len(cp.chunks)
                break
            current_chapter_idx = total_chapters  # All done

        # Calculate current chunk progress
        current_chunk = 0
        if current_chapter_idx < total_chapters:
            cp = self.chapter_progress[current_chapter_idx]
            current_chunk = cp.processed_chunks

        # Calculate progress percentages
        chapter_progress = current_chunk / max(current_chunk_total, 1)
        overall_progress = (completed_chapters + chapter_progress) / max(total_chapters, 1)

        # Estimate time remaining
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if overall_progress > 0:
            total_estimated = elapsed / overall_progress
            remaining = total_estimated - elapsed
            eta = self._format_time_remaining(remaining)
        else:
            eta = 'Calculating...'

        # Status message
        if current_chapter_idx >= total_chapters:
            status = 'Processing complete!'
        elif current_chunk_total == 0:
            status = f'Preparing chapter {current_chapter_idx + 1}/{total_chapters}'
        else:
            status = f'Synthesizing chunk {current_chunk}/{current_chunk_total} in Chapter {current_chapter_idx + 1}'

        return ProcessingProgress(
            stage='processing_chapters' if self.book_text else 'preparing_text',
            current_chapter=current_chapter_idx + 1,
            total_chapters=total_chapters,
            current_chunk=current_chunk,
            total_chunks=current_chunk_total,
            chapter_progress=chapter_progress,
            overall_progress=overall_progress,
            estimated_time_remaining=eta,
            status_message=status,
            start_time=self.start_time,
            elapsed_time=self._format_elapsed_time(),
        )

    def _format_time_remaining(self, seconds: float) -> str:
        """Format seconds into human-readable time."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def _format_elapsed_time(self) -> str:
        """Format elapsed time."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return self._format_time_remaining(elapsed)
