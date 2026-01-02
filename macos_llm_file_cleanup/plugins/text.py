#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_field

#============================================


class TextDocumentPlugin(FileMetadataPlugin):
	"""
	Plugin for text-like files.
	"""

	name = "text"
	supported_suffixes: set[str] = {"txt", "md", "rtf"}

	#============================================
	def supports(self, path: Path) -> bool:
		"""
		Check if this plugin supports the extension.

		Args:
			path: File path.

		Returns:
			True when supported.
		"""
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		"""
		Extract title and preview.

		Args:
			path: File path.

		Returns:
			FileMetadata with summary.
		"""
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		title = mdls_field(path, "kMDItemTitle")
		if title:
			meta.title = title
		snippet = self._read_preview(path)
		if snippet:
			meta.summary = snippet
		return meta

	#============================================
	def _read_preview(self, path: Path) -> str | None:
		"""
		Read text preview.

		Args:
			path: File path.

		Returns:
			Text snippet or None.
		"""
		try:
			text_blob = path.read_text(encoding="utf-8", errors="ignore")
		except Exception:
			return None
		cleaned = " ".join(text_blob.split())
		if not cleaned:
			return None
		return cleaned[:1800]
