# Agents and LLM Modes

This project supports two distinct LLM interaction modes plus a deterministic fallback. The CLI remains unchanged; the internal structure is ready to switch between modes as needed.

## Modes

### 1) Rename mode (per file)
- Goal: generate a descriptive filename only (no folders).
- API: `rename_file(metadata: dict, current_name: str) -> str`.
- Prompt guidance:
  - 3–8 meaningful tokens; preserve names, dates, IDs, set numbers.
  - Summarize captions/descriptions into keywords; do not copy long sentences.
  - Avoid filler adjectives (“vibrant”, “beautiful”) and hashy originals.
  - Cap length at 256 chars; sanitized to `[A-Za-z0-9._-]`.

### 2) Sorting mode (batch categorization)
- Goal: assign stable categories for a batch using a fixed set.
- API: `assign_categories(file_summaries: list[dict]) -> dict[int, str]`.
- Input records per file:
  - `index`, `name` (new_name from rename mode), `ext`, `description` (title/caption/summary).
- Allowed categories (fixed):
  - Document, Spreadsheet, Presentation, Image, Audio, Video, Code, Data, Project, Other.
- Prompt guidance:
  - Show allowed categories.
  - Present numbered files with name/ext/description.
  - Respond `file_N: Category`.
- Parsing:
  - Map to allowed categories (case-insensitive); unknown => closest alias or `Other`.

### Heuristic fallback (DummyLLM)
- Provides rename and category assignment without Ollama:
  - Rename from title/keywords/summary; category from extension buckets.
- `rename_with_keep` (LLM-driven) returns `(new_name, keep_original)`; fallback uses a fixed default.

## Decision helpers
  - `rename_with_keep(metadata, current_name) -> (new_name, keep_original)` (keep decision via LLM; fallback default keeps original)
  - `OllamaChatLLM` asks the model; `DummyLLM` uses heuristics (words vs hashes).

## Organizer flow (two-phase)
1) For each file: gather metadata -> `rename_file` -> emit PLAN1 with new name.
2) Batch summaries -> `assign_categories` -> update targets -> emit PLAN2 with final path.

## Plugins
- Bitmap images: captions via Moondream2 when available.
- Vector images (SVG/SVGZ): text extraction only.
- Documents: doc/pdf/odt previews include head/tail snippets.
- Spreadsheets: csv/tsv previews; xlsx sheet names; dedicated CSV plugin.
- Other formats: type-specific plugins or generic stat/mdls fallback.

## Output conventions
- ANSI colors (TTY-aware): INFO blue, PLAN1/PLAN2 cyan, DRY RUN yellow, APPLY green, CAPTION magenta.
- Names sanitized to ASCII `[A-Za-z0-9._-]`, max 256 chars, dedupe double extensions.
See Python coding style in docs/PYTHON_STYLE.md.
## Coding Style
See Markdown style in docs/MARKDOWN_STYLE.md.
When making edits, document them in docs/CHANGELOG.md.
See repo style in docs/REPO_STYLE.md.
Agents may run programs in the tests folder, including smoke tests and pyflakes/mypy runner scripts.
