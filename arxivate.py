#!/usr/bin/env python3
"""
arxivate.py - Prepare a LaTeX project for arXiv submission.

This script takes a main .tex file, collects all dependencies recursively,
strips comments, flattens the directory structure, compiles the document,
and cleans up temporary files.
"""

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import typer


# LaTeX commands that include files: command -> (regex pattern, possible extensions)
INCLUDE_PATTERNS: dict[str, tuple[str, list[str]]] = {
    r"\input": (r"\\input\s*\{([^}]+)\}", [".tex", ""]),
    r"\include": (r"\\include\s*\{([^}]+)\}", [".tex"]),
    r"\includegraphics": (
        r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}",
        [".pdf", ".png", ".jpg", ".jpeg", ".eps", ".gif", ""],
    ),
    r"\bibliography": (r"\\bibliography\s*\{([^}]+)\}", [".bib"]),
    r"\bibliographystyle": (r"\\bibliographystyle\s*\{([^}]+)\}", [".bst"]),
    r"\lstinputlisting": (
        r"\\lstinputlisting\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}",
        [""],
    ),
}

# Temp file extensions to remove after compilation
TEMP_EXTENSIONS = {
    ".aux", ".log", ".out", ".blg", ".toc", ".lof", ".lot",
    ".fls", ".fdb_latexmk", ".synctex.gz", ".nav", ".snm",
    ".vrb", ".brf", ".idx", ".ilg", ".ind", ".glo", ".gls",
    ".glg", ".ist", ".acn", ".acr", ".alg", ".run.xml",
    "-blx.bib", ".bcf",
}

# Regex to match LaTeX comments (% not preceded by \)
COMMENT_PATTERN = re.compile(r"(?<!\\)%.*$", re.MULTILINE)


@dataclass
class FileMapping:
    """Mapping from original path to flattened name."""
    original: Path
    flattened: str
    is_tex: bool = False


@dataclass
class ArxivPreparer:
    """Prepares a LaTeX project for arXiv submission."""

    main_tex: Path
    output_dir: Path
    base_dir: Path = field(init=False)
    files: dict[Path, FileMapping] = field(default_factory=dict)
    processed_tex: set[Path] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.main_tex = self.main_tex.resolve()
        self.output_dir = self.output_dir.resolve()
        self.base_dir = self.main_tex.parent

    def run(self) -> None:
        """Execute the full preparation pipeline."""
        print(f"Preparing arXiv submission from: {self.main_tex}")
        print(f"Output directory: {self.output_dir}")

        print("\n[1/5] Collecting dependencies...")
        self._collect_dependencies(self.main_tex)
        print(f"      Found {len(self.files)} files")

        print("\n[2/5] Creating output directory and copying files...")
        self._setup_output_dir()

        print("\n[3/5] Stripping comments and updating paths...")
        self._process_tex_files()

        print("\n[4/5] Compiling document...")
        self._compile()

        print("\n[5/5] Cleaning up temporary files...")
        self._cleanup()

        print("\nDone! arXiv submission ready at:", self.output_dir)

    def _resolve_file(self, path_str: str, extensions: list[str]) -> Path | None:
        """Resolve a file path, trying different extensions if needed."""
        base_path = self.base_dir / path_str

        # Try each extension
        for ext in extensions:
            if ext:
                # Try appending extension
                candidate = Path(str(base_path) + ext)
                if candidate.exists():
                    return candidate.resolve()
            elif base_path.exists():
                return base_path.resolve()

        return None

    def _collect_dependencies(self, tex_file: Path) -> None:
        """Recursively collect all file dependencies from a .tex file."""
        tex_file = tex_file.resolve()

        if tex_file in self.processed_tex:
            return
        self.processed_tex.add(tex_file)

        if not tex_file.exists():
            print(f"      Warning: File not found: {tex_file}")
            return

        self._register_file(tex_file, is_tex=True)
        content = tex_file.read_text(encoding="utf-8", errors="replace")

        for cmd, (pattern, extensions) in INCLUDE_PATTERNS.items():
            for match in re.finditer(pattern, content):
                ref_path = match.group(1).strip()

                if cmd == r"\bibliography":
                    # Handle multiple bib files separated by comma
                    for bib in ref_path.split(","):
                        self._process_include(bib.strip(), extensions)
                else:
                    recurse = cmd in (r"\input", r"\include")
                    self._process_include(ref_path, extensions, recurse_tex=recurse)

    def _process_include(self, ref_path: str, extensions: list[str], recurse_tex: bool = False) -> None:
        """Process a single include reference."""
        resolved = self._resolve_file(ref_path, extensions)

        if resolved is None:
            print(f"      Warning: Could not resolve: {ref_path}")
            return

        is_tex = resolved.suffix.lower() == ".tex"
        self._register_file(resolved, is_tex=is_tex)

        if recurse_tex and is_tex:
            self._collect_dependencies(resolved)

    def _register_file(self, path: Path, is_tex: bool = False) -> None:
        """Register a file with a flattened name."""
        path = path.resolve()
        if path in self.files:
            return

        # Create flattened name by replacing path separators
        try:
            rel_path = path.relative_to(self.base_dir)
            flattened = str(rel_path).replace("/", "_").replace("\\", "_")
        except ValueError:
            flattened = path.name

        # Handle collisions
        base_flattened = flattened
        counter = 1
        while any(f.flattened == flattened for f in self.files.values()):
            stem = Path(base_flattened).stem
            suffix = Path(base_flattened).suffix
            flattened = f"{stem}_{counter}{suffix}"
            counter += 1

        self.files[path] = FileMapping(original=path, flattened=flattened, is_tex=is_tex)

    def _setup_output_dir(self) -> None:
        """Create output directory and copy non-tex files."""
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)

        for path, mapping in self.files.items():
            if not mapping.is_tex:
                dest = self.output_dir / mapping.flattened
                shutil.copy2(path, dest)
                print(f"      Copied: {mapping.flattened}")

    def _process_tex_files(self) -> None:
        """Process all .tex files: strip comments and update paths."""
        for path, mapping in self.files.items():
            if mapping.is_tex:
                content = path.read_text(encoding="utf-8", errors="replace")
                content = self._strip_comments(content)
                content = self._update_paths(content)

                dest = self.output_dir / mapping.flattened
                dest.write_text(content, encoding="utf-8")
                print(f"      Processed: {mapping.flattened}")

    def _strip_comments(self, content: str) -> str:
        """Remove LaTeX comments from content, preserving escaped \\%."""
        # Remove comments (% not preceded by \)
        content = COMMENT_PATTERN.sub("", content)
        # Remove lines that are now empty (were comment-only lines)
        lines = [line.rstrip() for line in content.split("\n")]
        # Filter out empty lines that resulted from comment-only lines, but keep intentional blank lines
        return "\n".join(lines)

    def _update_paths(self, content: str) -> str:
        """Update all file paths in content to use flattened names."""

        def replace_path(match: re.Match, extensions: list[str]) -> str:
            full_match = match.group(0)
            ref_path = match.group(1).strip()

            if "," in ref_path:
                parts = [self._get_flattened_ref(p.strip(), extensions) for p in ref_path.split(",")]
                new_ref = ", ".join(parts)
            else:
                new_ref = self._get_flattened_ref(ref_path, extensions)

            return full_match.replace("{" + match.group(1) + "}", "{" + new_ref + "}")

        for cmd, (pattern, extensions) in INCLUDE_PATTERNS.items():
            content = re.sub(pattern, lambda m, ext=extensions: replace_path(m, ext), content)

        return content

    def _get_flattened_ref(self, ref_path: str, extensions: list[str]) -> str:
        """Get the flattened reference for a path."""
        resolved = self._resolve_file(ref_path, extensions)
        if resolved and resolved in self.files:
            flattened = self.files[resolved].flattened
            # Remove extension for \input, \include, \bibliography, \bibliographystyle
            if resolved.suffix.lower() in (".tex", ".bib", ".bst"):
                return Path(flattened).stem
            return flattened
        return ref_path

    def _compile(self) -> None:
        """Compile the document using pdflatex and bibtex."""
        main_flattened = self.files[self.main_tex].flattened
        main_stem = Path(main_flattened).stem

        commands = [
            ["pdflatex", "-interaction=nonstopmode", main_flattened],
            ["bibtex", main_stem],
            ["pdflatex", "-interaction=nonstopmode", main_flattened],
            ["pdflatex", "-interaction=nonstopmode", main_flattened],
        ]

        for cmd in commands:
            print(f"      Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.output_dir, capture_output=True, text=True)
            # bibtex can fail if there's no \cite, that's ok
            if result.returncode != 0 and cmd[0] != "bibtex":
                print(f"      Warning: {cmd[0]} returned {result.returncode}")

    def _cleanup(self) -> None:
        """Remove temporary files, keeping essential ones."""
        kept = 0
        removed = 0

        for file in self.output_dir.iterdir():
            if file.is_file():
                name_lower = file.name.lower()
                should_remove = any(name_lower.endswith(ext) for ext in TEMP_EXTENSIONS)

                if should_remove:
                    file.unlink()
                    removed += 1
                else:
                    kept += 1

        print(f"      Kept {kept} files, removed {removed} temporary files")


app = typer.Typer(help="Prepare a LaTeX project for arXiv submission")


@app.command()
def main(
    main_tex: Annotated[Path, typer.Argument(help="Path to the main .tex file")],
    output: Annotated[Path | None, typer.Option("-o", "--output", help="Output directory")] = None,
) -> None:
    """
    Prepare a LaTeX project for arXiv submission.

    Collects all dependencies, strips comments, flattens the directory structure,
    compiles the document, and cleans up temporary files.
    """
    if not main_tex.exists():
        print(f"Error: File not found: {main_tex}", file=sys.stderr)
        raise typer.Exit(1)

    if main_tex.suffix.lower() != ".tex":
        print(f"Error: Expected .tex file, got: {main_tex}", file=sys.stderr)
        raise typer.Exit(1)

    output_dir = output or Path(f"{main_tex.stem}_arxiv")

    preparer = ArxivPreparer(main_tex=main_tex, output_dir=output_dir)
    preparer.run()


if __name__ == "__main__":
    app()
