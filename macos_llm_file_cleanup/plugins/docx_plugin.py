#!/usr/bin/env python3
# Standard Library
from pathlib import Path

# PIP3 modules
try:
	import docx
except Exception:
	docx = None

# local repo modules
from .base import FileMetadata, FileMetadataPlugin

#============================================


class DocxPlugin(FileMetadataPlugin):
	"""
	Plugin for .docx documents.
	"""

	name = "docx"
	supported_suffixes: set[str] = {"docx"}

	#============================================
	def supports(self, path: Path) -> bool:
		"""
		Check support for docx files.

		Args:
			path: File path.

		Returns:
			True when extension is docx.
		"""
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		"""
		Extract core properties and preview.

		Args:
			path: File path.

		Returns:
			FileMetadata with available info.
		"""
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		if not docx:
			return meta
		try:
			document = docx.Document(path)
			if document.core_properties.title:
				meta.title = document.core_properties.title
			if document.core_properties.author:
				meta.keywords.append(document.core_properties.author)
			all_text: list[str] = []
			for paragraph in document.paragraphs:
				if paragraph.text:
					all_text.append(paragraph.text.strip())
			if all_text:
				full = " ".join(all_text)
				head = full[:256]
				tail = full[-256:] if len(full) > 256 else ""
				meta.summary = f"{head} ... {tail}".strip()
		except Exception:
			return meta
		return meta
