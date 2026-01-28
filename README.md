# arxivate

Python script that prepares a LaTeX project for arXiv submission. Created partly through an LLM, so YMMV!

## Features

- **Dependency collection**: Recursively finds all files referenced by your LaTeX project
  - `\input{}` and `\include{}` for nested .tex files
  - `\includegraphics{}` for figures (PDF, PNG, JPG, etc.)
  - `\bibliography{}` and `\bibliographystyle{}` for bibliography files
  - `\lstinputlisting{}` for verbatim file inclusions
  - Local `.sty` style files
- **Comment stripping**: Removes all LaTeX comments from .tex files (arXiv makes source available)
- **Path flattening**: Flattens directory structure and updates all paths automatically
- **Filename sanitization**: Ensures all filenames use only arXiv-allowed characters
- **Compilation**: Runs pdflatex + bibtex to generate the .bbl file required by arXiv
- **Cleanup**: Removes temporary files while keeping essential ones (.tex, figures, .bbl, .bst)
- **Zip archive**: Creates a ready-to-upload `.zip` file for arXiv submission

## Requirements

- Python 3.10+
- pdflatex and bibtex installed and available in PATH

## Installation

```bash
pip install typer
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Basic usage - creates output in <main_file>_arxiv/
python arxivate.py path/to/main.tex

# Specify output directory
python arxivate.py path/to/main.tex --output arxiv_submission

# Short form
python arxivate.py paper.tex -o submission
```

## Example

```bash
# Prepare the example project for arXiv
python arxivate.py example/00_main.tex --output arxiv_submission
```

This will:
1. Parse `00_main.tex` and find all dependencies (other .tex files, figures, bibliography)
2. Copy all required files to `arxiv_submission/` with flattened names
3. Strip comments from all .tex files
4. Update all file paths to use the new flattened names
5. Compile the document (pdflatex → bibtex → pdflatex → pdflatex)
6. Clean up temporary files, keeping only what arXiv needs

## Output

The output directory will contain:
- All .tex files (comment-stripped, with updated paths)
- All referenced figures
- Any local `.sty` style files
- The `.bbl` file (compiled bibliography, required by arXiv)
- The `.bst` file (bibliography style)
- The compiled `.pdf` file

Additionally, a `.zip` archive is created alongside the output directory, ready for upload to arXiv.

## Notes

- arXiv requires the `.bbl` file instead of `.bib` because they don't run bibtex
- Comments are stripped because arXiv makes the source available to readers
- The script handles paths with or without file extensions (LaTeX allows both)
- File name collisions are handled automatically with numeric suffixes

## License

MIT License
