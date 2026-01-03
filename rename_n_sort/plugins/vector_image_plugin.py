#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path
import xml.etree.ElementTree as ET

# PIP3 modules
try:
	from odf import text as odf_text
	from odf.opendocument import load as odf_load
	from odf import teletype as odf_teletype
except Exception:
	odf_text = None
	odf_load = None
	odf_teletype = None

# local repo modules
from .base import FileMetadata, FileMetadataPlugin

#============================================


class VectorImagePlugin(FileMetadataPlugin):
	"""
	Plugin for vector images (SVG/SVGZ/ODG).
	"""

	name = "vector_image"
	supported_suffixes: set[str] = {"svg", "svgz", "odg"}

	#============================================
	def supports(self, path: Path) -> bool:
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		ext = path.suffix.lower().lstrip(".")
		meta.extra["extension"] = ext
		meta.title = path.stem
		if ext in {"svg", "svgz"}:
			text_bits = self._read_svg_text(path)
			if text_bits:
				meta.summary = f"Vector image (SVG) with text: {text_bits}"
			else:
				meta.summary = "Vector image (SVG)"
			return meta
		if ext == "odg":
			text_bits = self._read_odg_text(path)
			if text_bits:
				meta.summary = f"Drawing (ODG) with text: {text_bits}"
			else:
				meta.summary = "Drawing (ODG)"
			return meta
		meta.summary = "Vector image"
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

	def _read_odg_text(self, path: Path) -> str | None:
		if not odf_load or not odf_text or not odf_teletype:
			return None
		try:
			document = odf_load(str(path))
		except Exception:
			return None
		paras = document.getElementsByType(odf_text.P)
		snippets: list[str] = []
		for para in paras:
			text = odf_teletype.extractText(para).strip()
			if text:
				snippets.append(text)
			if len(snippets) >= 40:
				break
		if not snippets:
			return None
		full = " ".join(snippets)
		flat = " ".join(full.split())
		return flat[:256] if flat else None
