# Supported Extensions (Content vs Metadata)

Notes
- This reflects the active plugin registry order.
- If multiple plugins support the same extension, the first registered plugin wins.
- “Content-aware” means we read file contents (text/OCR/captions), not just metadata.

## PDF (content-aware)
- pdf
  - Extracts text via pypdf.
  - Renders the first two pages for OCR + Moondream2 captions.

## Documents (content-aware)
- doc (DocumentPlugin)
  - Prefers LibreOffice (`soffice`) to convert to .docx, then parses via python-docx.
- docx (DocxPlugin)
  - Extracts paragraphs via python-docx (head/tail snippets).
- odt (OdtPlugin)
  - Extracts paragraphs via odfpy (head/tail snippets).
- txt, md, rtf (DocumentPlugin)
  - Reads a short text preview (first ~800 chars).

## Documents (metadata-only)
- pages
  - Title/metadata via mdls only.

## Spreadsheets / data (content-aware)
- csv, tsv
  - Reads first ~3 rows as preview.
- xlsx
  - Sheet names + Row1 + Col1 via openpyxl.
- xls
  - Sheet names + Row1 + Col1 via xlrd.
- ods
  - Sheet names + preview rows + Col1 via odfpy.

## Presentations (content-aware)
- ppt (PresentationPlugin)
  - Prefers LibreOffice (`soffice`) to convert to .pptx, then parses via python-pptx.
- pptx
  - Extracts slide text via python-pptx.
- odp
  - Extracts slide text via odfpy.

## Images (content-aware)
- jpg, jpeg, png, gif, heic, tif, tiff, bmp
  - Moondream2 captions + OCR (Tesseract).

## Vector images (content-aware)
- svg, svgz
  - Extracts visible text nodes from SVG.

## Audio (metadata-only)
- mp3, wav, flac, aiff, ogg
  - Title/metadata via mdls only.

## Video (metadata-only)
- mp4, mov, mkv, webm, avi
  - Title/metadata via mdls only.

## Code / scripts (content-aware)
- py, m, cpp, js, sh, pl, rb, php
  - Reads first ~10 lines of code.

## Fallback
- Any other extension
  - mdls/stat only; no content extraction.
