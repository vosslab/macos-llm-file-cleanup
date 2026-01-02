# Changelog

## 2026-01-02
- Bump version to `26.01` and add root `VERSION` file synced with `pyproject.toml`.
- Lazy-import `ai_image_caption.moondream2` so optional caption dependencies load only when needed.
- Add `--one-by-one` mode to process each file through PLAN1/PLAN2 (and DRY RUN/APPLY) before starting the next file.
- Add `--llm-backend {macos,ollama}` to choose between the default macOS-local backend and Ollama.
- Print rename/keep/category decision details by default.
- Fix Ollama sorting-mode parsing to fill missing categories using the actual file indices in the batch (not `0..N-1`).
- Add tests for VERSION sync and keep-original heuristics, plus a CLI smoke script at `tests/run_smoke_cli.sh`.
- Fix pyflakes warnings (unused imports and duplicate dictionary keys).
- Update Ollama prompts/parsing to use an XML `<response>...</response>` block for robust extraction from chatty model outputs.
- Add repo-root runner script `run_file_cleanup.py`.
- Switch PDF parsing dependency from PyPDF2 to pypdf.
