# TODO

## Bugs and fixes
- Audit Moondream2 caption logging for duplicate output and keep only one full caption line.
- Ensure unsupported extensions are rejected before any LLM call, with a clear reason.
- Standardize keep-original reasons so true always includes a short justification.
- Keep LLM prompt size under control by truncating long tokens and repeated lines.

## Content extraction
- Verify DOC and PPT extraction via `soffice --headless` when available.
- Add clearer skip reasons when LibreOffice is missing or conversion fails.
- Expand HTML extraction to strip scripts/styles and keep meaningful headings.
- Confirm ODG/ODP/ODT extraction covers common text shapes and tables.

## LLM engine and prompts
- Centralize LLM call logging for rename, keep, and sort with consistent prefixes.
- Add a single place to cap prompt payload lengths per operation.
- Validate that format-fix retries always use a different prompt than the first try.
- Add explicit unit tests for guardrail fallback with two transports.

## Tests and tooling
- Add golden extraction tests for `tests/test_files/` across DOCX, ODT, PPTX, ODP.
- Add a smoke test for HTML parsing on a minimal sample file.
- Re-run full test suite on macOS with and without LibreOffice installed.

## Docs
- Add a short troubleshooting note about LibreOffice headless requirements.
- Document how to disable Moondream2 captioning if GPU or model is unavailable.
