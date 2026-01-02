#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
import importlib
from pathlib import Path
import xml.etree.ElementTree as ET

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_field

try:
	import pillow_heif
	pillow_heif.register_heif_opener()
except Exception:
	pillow_heif = None

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
		caption = self._try_caption(path)
		if caption:
			meta.summary = caption
		else:
			meta.summary = f"Image file {path.suffix.lower().lstrip('.')}"
		if caption:
			print(f"\033[35m[CAPTION]\033[0m {path.name}: {caption}")
		return meta

	#============================================
	def _try_caption(self, path: Path) -> str | None:
		"""
		Attempt to caption using moondream2 if available.
		"""
		ext = path.suffix.lower().lstrip(".")
		if ext in {"svg", "svgz"}:
			return None
		moondream2 = getattr(self, "_moondream2_module", None)
		if moondream2 is None and not getattr(self, "_moondream2_import_attempted", False):
			try:
				moondream2 = importlib.import_module("ai_image_caption.moondream2")
			except Exception:
				moondream2 = None
			self._moondream2_module = moondream2
			self._moondream2_import_attempted = True
		if not moondream2:
			if not hasattr(self, "_caption_status_printed"):
				print("\033[35m[CAPTION]\033[0m Moondream2 not available; install its dependencies to enable image captions.")
				self._caption_status_printed = True
			return None
		if not hasattr(self, "_ai_components"):
			try:
				self._ai_components = moondream2.setup_ai_components()
				print("\033[35m[CAPTION]\033[0m Moondream2 initialized; captions enabled.")
			except Exception as exc:
				if not hasattr(self, "_caption_status_printed"):
					print(f"\033[35m[CAPTION]\033[0m Failed to initialize Moondream2 ({exc}); skipping captions.")
					self._caption_status_printed = True
				self._ai_components = None
		if not getattr(self, "_ai_components", None):
			return None
		try:
			return moondream2.generate_caption(str(path), self._ai_components)
		except Exception as exc:
			if not hasattr(self, "_caption_status_printed"):
				print(f"\033[35m[CAPTION]\033[0m Captioning failed for {path.name} ({exc}); skipping.")
				self._caption_status_printed = True
			return None

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
