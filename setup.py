#!/usr/bin/env python3
"""
scaffold_bookforge.py

One-shot script to create the BookForge v0.1 project structure and minimal stubs.
Run from an empty parent directory:

    python scaffold_bookforge.py

It will create ./bookforge/ with src/, tests/, presets/, etc.
"""

from pathlib import Path
import textwrap

PROJECT_ROOT = Path("bookforge")
PACKAGE_NAME = "bookforge"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def main() -> None:
    root = PROJECT_ROOT
    src_pkg = root / "src" / PACKAGE_NAME

    # ---------- top-level files ----------
    write(
        root / "README.md",
        """
        # BookForge

        Public domain texts → high-quality local TTS audiobooks (Piper backend).

        ## Dev quickstart

        ```bash
        cd bookforge
        python -m venv .venv
        source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
        pip install -e ".[dev,piper]"
        bookforge --help
        ```
        """,
    )

    write(
        root / ".gitignore",
        """
        __pycache__/
        *.py[cod]
        .venv/
        env/
        venv/
        .pytest_cache/
        .mypy_cache/
        .ruff_cache/
        .coverage
        htmlcov/
        *.log
        chunks/
        voices/
        *.wav
        *.m4b
        """,
    )

    write(
        root / "LICENSE",
        """
        MIT License

        Copyright (c) 2026 Your Name

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        [snip – fill in full MIT text]
        """,
    )

    write(
        root / "CHANGELOG.md",
        """
        # Changelog

        ## [0.1.0] - 2026-02-05
        - Initial scaffold, Piper backend stubs, CLI skeleton.
        """,
    )

    write(
        root / "CONTRIBUTING.md",
        """
        # Contributing

        1. Create a virtualenv, `pip install -e ".[dev]"`.
        2. Run `pre-commit install`.
        3. Add tests under `tests/`.
        4. Run `pytest` before opening a PR.
        """,
    )

    # Modern packaging via pyproject.toml
    write(
        root / "pyproject.toml",
        """
        [build-system]
        requires = ["setuptools>=70", "wheel"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "bookforge"
        version = "0.1.0"
        description = "Public domain texts → high-quality local TTS audiobooks"
        readme = "README.md"
        requires-python = ">=3.10"
        license = {text = "MIT"}
        authors = [{name = "Your Name", email = "you@example.com"}]

        dependencies = [
            "typer>=0.12.0",
            "pydantic-settings>=2.0.0",
            "ebooklib>=0.18.0",
        ]

        [project.optional-dependencies]
        piper = [
            "piper-tts>=1.2.0",
            "onnxruntime-gpu>=1.18.0",
        ]
        dev = [
            "pytest>=8.0",
            "pytest-cov>=5.0",
            "ruff>=0.5.0",
            "black>=24.0",
            "mypy>=1.10.0",
            "pre-commit>=3.7.0",
            "ffmpeg-python>=0.2.0",
        ]

        [project.scripts]
        bookforge = "bookforge.cli:app"

        [tool.setuptools.packages.find]
        where = ["src"]

        [tool.black]
        line-length = 100
        target-version = ["py310"]

        [tool.ruff]
        line-length = 100
        target-version = "py310"
        """,
    )

    # Optional minimal setup.py: just delegate to pyproject
    write(
        root / "setup.py",
        """
        from setuptools import setup

        if __name__ == "__main__":
            setup()
        """,
    )

    write(
        root / ".pre-commit-config.yaml",
        """
        repos:
          - repo: https://github.com/psf/black
            rev: 24.4.2
            hooks:
              - id: black
          - repo: https://github.com/astral-sh/ruff-pre-commit
            rev: v0.5.4
            hooks:
              - id: ruff
              - id: ruff-format
          - repo: https://github.com/pre-commit/mirrors-mypy
            rev: v1.10.0
            hooks:
              - id: mypy
        """,
    )

    # ---------- src package skeleton ----------
    write(
        src_pkg / "__init__.py",
        f'''
        """BookForge core package."""
        __all__ = ["__version__"]
        __version__ = "0.1.0"
        ''',
    )

    # cli.py – just wiring for now
    write(
        src_pkg / "cli.py",
        """
        \"\"\"BookForge CLI entrypoint.\"\"\"

        from pathlib import Path
        from typing import Optional

        import typer

        from .config import PresetConfig
        from .project import BookProject

        app = typer.Typer(help="Convert texts/epubs into audiobooks using local TTS.")

        @app.command()
        def process(
            input_file: Path,
            output_dir: Path,
            voice: str = "en_GB-southern_english_female-medium",
            preset: str = "calm_longform",
        ) -> None:
            \"\"\"Process INPUT_FILE into an audiobook under OUTPUT_DIR.\"\"\"
            project = BookProject(output_dir)
            config = PresetConfig.load(preset)

            typer.echo(f"Processing {input_file} → {output_dir}")
            # TODO: ingest → clean → chunk → TTS → package
            typer.echo("Scaffold only: pipeline not yet implemented.")

        @app.command()
        def review(
            project_file: Path,
            chunk: int,
            new_text: Optional[str] = None,
        ) -> None:
            \"\"\"Review/re-render a specific CHUNK inside PROJECT_FILE (future).\"\"\"
            typer.echo(f"Review stub: project={project_file}, chunk={chunk}")

        def main() -> None:
            app()


        if __name__ == "__main__":
            main()
        """,
    )

    # config.py – minimal, YAML loading wired later
    write(
        src_pkg / "config.py",
        """
        \"\"\"Configuration and preset handling.\"\"\"

        from pathlib import Path
        from pydantic_settings import BaseSettings


        class PresetConfig(BaseSettings):
            voice: str
            rate: float = 1.0
            pitch: float = 0.0
            pause_short: float = 0.3
            pause_para: float = 1.2
            pause_chapter: float = 3.0
            seed: int = 42
            target_chunk_secs: int = 30

            @classmethod
            def load(cls, name: str) -> "PresetConfig":
                \"\"\"Load preset from presets/<name>.yaml (simple stub).\"\"\"
                # TODO: implement proper YAML reading & validation
                # For now, return defaults with given voice name.
                return cls(voice=name)
        """,
    )

    # project.py – skeleton only
    write(
        src_pkg / "project.py",
        """
        \"\"\"BookProject: manages project directory & chunk index (skeleton).\"\"\"

        from pathlib import Path


        class BookProject:
            def __init__(self, root: Path) -> None:
                self.root = root
                self.root.mkdir(parents=True, exist_ok=True)
                (self.root / "chunks").mkdir(exist_ok=True)
        """,
    )

    # module stubs
    for subpkg, files in {
        "ingest": ["__init__.py", "txt_ingest.py", "epub_ingest.py"],
        "process": ["__init__.py", "cleaner.py", "chunker.py"],
        "tts": ["__init__.py", "backend.py", "piper.py"],
        "audio": ["__init__.py", "normalize.py", "concat.py", "m4b.py"],
    }.items():
        subdir = src_pkg / subpkg
        subdir.mkdir(parents=True, exist_ok=True)
        for fname in files:
            if fname == "__init__.py":
                content = f'"""BookForge.{subpkg} package."""\n'
            else:
                content = f'"""TODO: implement {subpkg}.{fname[:-3]}."""\n'
            write(subdir / fname, content)

    # ---------- presets & tests ----------
    presets_dir = root / "presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    write(
        presets_dir / "calm_longform.yaml",
        """
        voice: en_GB-southern_english_female-medium
        rate: 0.9
        pitch: -0.1
        pause_short: 0.4
        pause_para: 1.5
        pause_chapter: 4.0
        seed: 42
        target_chunk_secs: 35
        """,
    )

    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    write(
        tests_dir / "test_imports.py",
        """
        def test_import_package():
            import bookforge  # noqa: F401
        """,
    )

    print(f"✅ Created scaffold in {root.resolve()}")


if __name__ == "__main__":
    main()
