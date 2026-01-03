#!/usr/bin/env python3
# Standard Library
from pathlib import Path

# PIP3 modules
try:
	from odf import text
	from odf.opendocument import load
	from odf import teletype
except Exception:
	text = None
	load = None
	teletype = None

# local repo modules
from .base import FileMetadata, FileMetadataPlugin

#============================================


class OdtPlugin(FileMetadataPlugin):
	"""
	Plugin for .odt documents.
	"""

	name = "odt"
	supported_suffixes: set[str] = {"odt"}

	#============================================
	def supports(self, path: Path) -> bool:
		"""
		Check support for odt files.

		Args:
			path: File path.

		Returns:
			True when extension is odt.
		"""
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		"""
		Extract preview text when odf is installed.

		Args:
			path: File path.

		Returns:
			FileMetadata with summary when possible.
		"""
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		if not load or not text or not teletype:
			return meta
		try:
			document = load(str(path))
			paras = document.getElementsByType(text.P)
			snippets: list[str] = []
			for para in paras:
				para_text = teletype.extractText(para).strip()
				if para_text:
					snippets.append(para_text)
			if snippets:
				full = " ".join(snippets)
				head = full[:256]
				tail = full[-256:] if len(full) > 256 else ""
				meta.summary = f"{head} ... {tail}".strip()
		except Exception:
			return meta
		return meta
