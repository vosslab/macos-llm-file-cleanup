#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path
import xml.etree.ElementTree as ET
import sys
import time

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_field

import pillow_heif
from PIL import Image
import pytesseract

pillow_heif.register_heif_opener()

#============================================


class ImagePlugin(FileMetadataPlugin):
	"""
	Plugin for common image formats.
	"""

	name = "image"
	supported_suffixes: set[str] = {
		"jpg",
		"jpeg",
		"png",
		"gif",
		"heic",
		"tif",
		"tiff",
		"bmp",
	}

	#============================================
	def supports(self, path: Path) -> bool:
		ext = path.suffix.lower().lstrip(".")
		return ext in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		title = mdls_field(path, "kMDItemTitle")
		if title:
			meta.title = title
		ocr_text = self._extract_ocr_text(path)
		self._print_meta(
			"ocr_status",
			f"completed ({len(ocr_text) if ocr_text else 0} chars)",
		)
		if ocr_text:
			meta.extra["ocr_text"] = ocr_text
			self._print_meta("ocr_sample", ocr_text)
		caption = self._try_caption(path)
		if caption:
			meta.extra["caption"] = caption
		if caption or ocr_text:
			meta.extra["caption_note"] = (
				"Moondream2 is descriptive; OCR is literal text. Prefer OCR for exact UI strings."
			)
		meta.summary = self._combine_summary(caption, ocr_text, path)
		return meta

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

	#============================================
	def _combine_summary(self, caption: str | None, ocr_text: str | None, path: Path) -> str:
		parts: list[str] = []
		if caption:
			parts.append(caption)
		if ocr_text:
			parts.append(f"OCR: {ocr_text}")
		if parts:
			joined = " | ".join(parts)
			return joined[:800]
		return f"Image file {path.suffix.lower().lstrip('.')}"

	#============================================
	def _extract_ocr_text(self, path: Path) -> str | None:
		"""
		Extract OCR text for bitmap images using Tesseract.
		"""
		with Image.open(path) as image:
			text = pytesseract.image_to_string(image)
		text = " ".join(text.split())
		return text or None

	#============================================
	def _try_caption(self, path: Path) -> str | None:
		"""
		Caption using Moondream2 (required).
		"""
		ext = path.suffix.lower().lstrip(".")
		if ext in {"svg", "svgz"}:
			return None
		if not hasattr(self, "_moondream2_module"):
			from rename_n_sort import moondream2_caption
			self._moondream2_module = moondream2_caption
		moondream2 = self._moondream2_module
		if not hasattr(self, "_ai_components"):
			try:
				self._ai_components = moondream2.setup_ai_components()
			except Exception as exc:
				raise RuntimeError(f"Failed to initialize Moondream2: {exc}") from exc
		start = time.monotonic()
		print(f"\033[35m[CAPTION]\033[0m {path.name}: running Moondream2...")
		try:
			caption = moondream2.generate_caption(str(path), self._ai_components)
		except Exception as exc:
			duration = time.monotonic() - start
			print(
				f"\033[35m[CAPTION]\033[0m {path.name}: failed after {duration:.2f}s"
			)
			raise RuntimeError(f"Moondream2 captioning failed for {path.name}: {exc}") from exc
		duration = time.monotonic() - start
		short_caption = self._shorten(caption, limit=240)
		print(
			f"\033[35m[CAPTION]\033[0m {path.name}: finished in {duration:.2f}s - {short_caption}"
		)
		return caption

	#============================================
	def _read_svg_text(self, path: Path) -> str | None:
		"""
		Extract visible text from SVG.
		"""
		try:
			tree = ET.parse(path)
			root = tree.getroot()
			text_nodes = []
			for elem in root.iter():
				if elem.text and elem.text.strip():
					text_nodes.append(elem.text.strip())
			if not text_nodes:
				return None
			joined = " ".join(text_nodes)
			return joined[:256]
		except Exception:
			return None
