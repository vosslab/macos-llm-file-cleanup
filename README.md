# llm-file-rename-n-sort

Local-first macOS tool that scans Downloads, Desktop, and Documents, extracts metadata with pluggable extractors, and uses Apple Foundation Models (with Ollama fallback) to rename and optionally sort files into category folders. Designed for Apple Silicon with no cloud calls.

## Capabilities
- Recursively scan messy folders with extension filters and file limits.
- Extract metadata via dedicated plugins per file type; fall back to a generic mdls/stat reader.
- Ask Apple Foundation Models (local) for a new file name and category, with Ollama as a backup on guardrail blocks.
- Apply safe renames/moves with collision avoidance; dry run by default.

## Supported file types (v1)
- Documents: pdf, doc, docx, odt, rtf, pages, txt, md, html, htm
- Presentations: ppt, pptx, odp
- Spreadsheets/data: xls, xlsx, ods, csv, tsv (csv/tsv handled by a dedicated plugin)
- Images: jpg, jpeg, png, gif, heic, tif, tiff, bmp (bitmap) and svg/svgz/odg (vector via dedicated plugin)
- Images use Moondream2 + OCR for captions (requires Moondream2 dependencies and Tesseract); install Pillow + pillow-heif (see `image` extra) for HEIC support.
- Audio: mp3, wav, flac, aiff, ogg
- Video: mp4, mov, mkv, webm, avi
- Code/scripts (as text): py, m, cpp, js, sh, pl, rb, php
- Unsupported extensions are skipped.

## Architecture overview
- `cli.py`: argparse interface, builds config, selects LLM, runs organizer.
- `config.py`: runtime settings, extension parsing, optional YAML/JSON overrides.
- `scanner.py`: iterates files respecting recursion, limits, and hidden/extension rules.
- `plugins/`: per-type metadata extractors returning `FileMetadata` objects.
	- Documents: `pdf.py`, `document_plugin.py`, `docx_plugin.py`, `odt_plugin.py`
	- Presentations: `presentation_plugin.py`
	- Spreadsheets/data: `spreadsheet_plugin.py`
	- Media: `image_plugin.py`, `audio_plugin.py`, `video_plugin.py`
	- Code/scripts: `code_plugin.py`
	- Text: `text.py`
	- Fallback: `generic.py` (used for extensionless files only)
- `llm.py`: BaseClassLLM interface, `AppleLLM` (Apple Foundation Models), `OllamaChatLLM` (chat history, /api/chat), filename/category helpers, VRAM/RAM-based model chooser.
- `organizer.py`: orchestrates metadata -> LLM suggestion -> target path -> apply (with collision handling).
- `renamer.py`: safe move/rename with deduping.
- `tests/`: pytest coverage for heuristics, plugin selection, model selection, and collision handling.

## LLM integration
- Interface: `suggest_name_and_category(metadata: dict, current_name: str) -> tuple[str, str]`
- Apple Foundation Models: `AppleLLM` uses the local Apple Intelligence backend.
- Ollama: `OllamaChatLLM` keeps in-memory chat messages and posts to `http://localhost:11434/api/chat` with `stream: false`.
- Availability check: if Apple Foundation Models are unavailable, the tool logs a warning and falls back to Ollama.
- Prompt format expects lines:
	- `new_name: <file name without path>`
	- `category: <short category or empty>`
- Model selection: VRAM/unified memory heuristic
	- >30 GB → `gpt-oss:20b`
	- >14 GB → `phi4:14b-q4_K_M`
	- >4 GB → `llama3.2:3b-instruct-q5_K_M`
	- else `llama3.2:1b-instruct-q4_K_M`
	- Override with `--model`.

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
# install all dependencies (LLM, captions, docs, etc.)
pip install -r pip_requirements.txt
```

## Quick start
```bash
python -m rename_n_sort --paths /path/to/folder --max-files 20          # dry run
python -m rename_n_sort --paths /path/to/folder --apply --max-files 10  # apply moves
python -m rename_n_sort --paths /path/to/folder --apply --model "llama3.2:3b-instruct-q5_K_M"
```

## CLI reference
- `-p/--paths PATH [PATH ...]` required scan roots
- `-a/--apply` perform renames and moves
- `-d/--dry-run` dry run (default)
- `-m/--max-files N` limit processed files
- `--max-depth N` maximum directory depth to scan (default 1)
- `-e/--ext EXT` repeatable extension filter
- `-t/--target PATH` target root (default `<search_path>/Organized`)
- `-o/--model MODEL` override Ollama model
- `-R/--randomize` randomize file processing order (default)
- `-S/--sorted` process files in sorted order
- `-v/--verbose` verbose logging
- `-x/--context "text"` optional context string added to LLM prompts (example: `"Biology class"` or `"Client ACME"`)

## Naming and moves
- Target path: `<target_root>/<category>/<new_name><ext>`
- Collisions: deduped with numeric suffixes.
- Hidden files skipped by default.
- Dry run prints planned moves; apply performs renames/moves.

## Testing
```bash
python -m pytest
```

## Notes and limitations
- macOS-only; uses `mdls` when available for fast metadata.
- Ollama must be running locally for chat mode.
- Plugins aim for lightweight metadata (size, extension, optional title/preview); heavy parsing is out-of-scope for v1.
