#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path

# local repo modules
from .base import FileMetadata, FileMetadataPlugin

#============================================


class CodePlugin(FileMetadataPlugin):
	"""
	Plugin for code and scripts treated as text.
	"""

	name = "code"
	supported_suffixes: set[str] = {
		"py",
		"m",
		"cpp",
		"js",
		"sh",
		"pl",
		"rb",
		"php",
	}

	#============================================
	def supports(self, path: Path) -> bool:
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		meta.title = path.stem
		snippet = self._read_preview(path)
		if snippet:
			meta.summary = snippet
		return meta

	#============================================
	def _read_preview(self, path: Path) -> str | None:
		"""
		Read first chunk of code for context.
		"""
		try:
			text_blob = path.read_text(encoding="utf-8", errors="ignore")
		except Exception:
			return None
		lines = text_blob.splitlines()
		head = "\n".join(lines[:10])
		flat = " ".join(head.split())
		if not flat:
			return None
		return flat[:800]
