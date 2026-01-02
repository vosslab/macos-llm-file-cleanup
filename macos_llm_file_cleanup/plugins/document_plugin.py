#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_field

#============================================


class DocumentPlugin(FileMetadataPlugin):
	"""
	Plugin for common document formats.
	"""

	name = "document"
	supported_suffixes: set[str] = {"doc", "docx", "odt", "rtf", "pages", "txt", "md"}

	#============================================
	def supports(self, path: Path) -> bool:
		"""
		Check if this plugin supports the extension.
		"""
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		"""
		Extract simple metadata from documents.
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
		Read a short preview for text-like documents.
		"""
		if path.suffix.lower().lstrip(".") not in {"txt", "md", "rtf"}:
			return None
		try:
			text_blob = path.read_text(encoding="utf-8", errors="ignore")
		except Exception:
			return None
		flattened = " ".join(text_blob.split())
		if not flattened:
			return None
		return flattened[:800]
