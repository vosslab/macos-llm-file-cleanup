#!/usr/bin/env python3
from __future__ import annotations
# Standard Library
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_fields
from .image_plugin import ImagePlugin

from pypdf import PdfReader
from pdf2image import convert_from_path

#============================================


class PDFPlugin(FileMetadataPlugin):
	"""
	PDF metadata extractor.
	"""

	name = "pdf"
	supported_suffixes: set[str] = {"pdf"}

	#============================================
	def supports(self, path: Path) -> bool:
		"""
		Check extension support.

		Args:
			path: File path.

		Returns:
			True when file is pdf.
		"""
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		"""
		Extract PDF metadata and preview.

		Args:
			path: File path.

		Returns:
			FileMetadata populated with metadata.
		"""
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		mdls_data = mdls_fields(
			path,
			[
				"kMDItemTitle",
				"kMDItemAuthors",
				"kMDItemKeywords",
				"kMDItemPageCount",
			],
		)
		if "kMDItemTitle" in mdls_data:
			meta.title = mdls_data["kMDItemTitle"]
		if "kMDItemAuthors" in mdls_data:
			meta.keywords.append(mdls_data["kMDItemAuthors"])
		if "kMDItemKeywords" in mdls_data:
			meta.keywords.append(mdls_data["kMDItemKeywords"])
		if "kMDItemPageCount" in mdls_data:
			meta.extra["page_count"] = mdls_data["kMDItemPageCount"]
		meta.extra.update(mdls_data)
		self._read_preview(path, meta)
		return meta

	#============================================
	def _read_preview(self, path: Path, meta: FileMetadata) -> None:
		"""
		Read first couple pages when pypdf exists.

		Args:
			path: File path.
			meta: Metadata object to populate.
		"""
		try:
			with path.open("rb") as handle:
				reader = PdfReader(handle)
				pages = reader.pages
				text_bits: list[str] = []
				for page in pages[:2]:
					extracted = page.extract_text()
					if extracted:
						text_bits.append(extracted.strip())
				if text_bits:
					joined = " ".join(text_bits)
					meta.extra["pdf_text"] = joined[:2000]
				page_count = len(pages)
				meta.extra["page_count"] = page_count
				if page_count <= 2:
					self._summarize_with_images(path, page_count, meta)
				elif text_bits:
					meta.summary = joined[:1500]
		except Exception:
			return

	#============================================
	def _summarize_with_images(self, path: Path, page_count: int, meta: FileMetadata) -> None:
		"""
		Render PDF pages to images and run OCR/captioning.
		"""
		self._print_meta("pdf_render", f"rendering {page_count} page(s) for OCR/captioning")
		image_plugin = ImagePlugin()
		captions: list[str] = []
		ocr_bits: list[str] = []
		with TemporaryDirectory() as tmp_dir:
			tmp_path = Path(tmp_dir)
			images = convert_from_path(
				str(path),
				first_page=1,
				last_page=page_count,
				dpi=200,
			)
			for page_idx, image in enumerate(images, start=1):
				out_path = tmp_path / f"{path.stem}_page{page_idx}.png"
				image.save(out_path)
				ocr_text = image_plugin._extract_ocr_text(out_path)
				if ocr_text:
					ocr_bits.append(f"Page {page_idx}: {ocr_text}")
				caption = image_plugin._try_caption(out_path)
				if caption:
					captions.append(f"Page {page_idx}: {caption}")
		caption_text = " | ".join(captions).strip()
		ocr_text = " | ".join(ocr_bits).strip()
		if caption_text:
			meta.extra["caption"] = caption_text
			self._print_meta("caption_sample", caption_text)
		if ocr_text:
			meta.extra["ocr_text"] = ocr_text
			self._print_meta("ocr_sample", ocr_text)
		if caption_text or ocr_text:
			meta.extra["caption_note"] = (
				"Moondream2 is descriptive; OCR is literal text. Prefer OCR for exact UI strings."
			)
		parts: list[str] = []
		if caption_text:
			parts.append(caption_text)
		if ocr_text:
			parts.append(f"OCR: {ocr_text}")
		if parts:
			meta.summary = " | ".join(parts)[:1500]

	#============================================
	def _color(self, text: str, code: str) -> str:
		if sys.stdout.isatty():
			return f"\033[{code}m{text}\033[0m"
		return text

	#============================================
	def _shorten(self, text: str, limit: int = 160) -> str:
		if not text:
			return ""
		cleaned = " ".join(str(text).split())
		if len(cleaned) <= limit:
			return cleaned
		return cleaned[: limit - 3] + "..."

	#============================================
	def _print_meta(self, label: str, value: str | None) -> None:
		if not value:
			return
		tag = self._color("[META]", "33")
		print(f"{tag} {label}: {self._shorten(value)}")
