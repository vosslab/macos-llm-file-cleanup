# ROADMAP

## Near term
- Harden Office extraction to use `soffice --headless` with better error handling.
- Keep LLM prompts and parsing fully backend-agnostic and covered by strict tests.
- Reduce guardrail failures by shrinking prompt payloads and retrying with minimal inputs.
- Add more sample files under `tests/test_files/` and assert extraction summaries.

## Mid term
- Add a cache for OCR and captions to avoid recomputing on repeated runs.
- Provide per-plugin token budgets and summary length controls.
- Add optional HTML and markdown cleanup pipelines for better summaries.
- Add a simple registry report command to show supported extensions and plugins.

## Longer term
- Add optional media transcription for audio and video files.
- Support configurable category sets and custom rules per root.
- Add a plugin sandbox mode to disable heavy dependencies by default.

## Out of scope for now
- Cloud upload or remote storage management.
- Collaborative tagging or multi-user workflows.
- Full-text indexing or search services.
