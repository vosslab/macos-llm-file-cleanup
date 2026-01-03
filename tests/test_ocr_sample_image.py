#!/usr/bin/env python3
"""OCR sanity check for the sample image."""

from pathlib import Path

import pytesseract
from PIL import Image


def test_ocr_sample_image_contains_sample():
	path = Path("tests/test_files/sample_ocr.png")
	if not path.exists():
		return
	with Image.open(path) as image:
		text = pytesseract.image_to_string(image)
	assert "SAMPLE" in text.upper()
