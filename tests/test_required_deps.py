#!/usr/bin/env python3
"""
Ensure required dependencies are installed and available.
"""

from tempfile import TemporaryDirectory


def test_moondream2_available():
	from rename_n_sort import moondream2_caption

	assert hasattr(moondream2_caption, "setup_ai_components")


def test_apple_foundation_models_available():
	from applefoundationmodels import apple_intelligence_available

	assert apple_intelligence_available() is True


def test_tesseract_available():
	import pytesseract

	_ = pytesseract.get_tesseract_version()


def test_pdf2image_available():
	from pypdf import PdfWriter
	from pdf2image import pdfinfo_from_path

	with TemporaryDirectory() as tmp_dir:
		pdf_path = f"{tmp_dir}/sample.pdf"
		writer = PdfWriter()
		writer.add_blank_page(width=72, height=72)
		with open(pdf_path, "wb") as handle:
			writer.write(handle)
		info = pdfinfo_from_path(pdf_path)
		assert int(info.get("Pages", 0)) == 1


def test_openpyxl_available():
	import openpyxl

	assert hasattr(openpyxl, "load_workbook")


def test_xlrd_available():
	import xlrd

	assert hasattr(xlrd, "open_workbook")


def test_python_pptx_available():
	import pptx

	assert hasattr(pptx, "Presentation")
