#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path
import xml.etree.ElementTree as ET

# local repo modules
from .base import FileMetadata, FileMetadataPlugin

#============================================


class VectorImagePlugin(FileMetadataPlugin):
	"""
	Plugin for vector images (SVG/SVGZ).
	"""

	name = "vector_image"
	supported_suffixes: set[str] = {"svg", "svgz"}

	#============================================
	def supports(self, path: Path) -> bool:
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		meta.title = path.stem
		text_bits = self._read_svg_text(path)
		if text_bits:
			meta.summary = f"Vector image (SVG) with text: {text_bits}"
		else:
			meta.summary = "Vector image (SVG)"
		return meta

	#============================================
	def _read_svg_text(self, path: Path) -> str | None:
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
