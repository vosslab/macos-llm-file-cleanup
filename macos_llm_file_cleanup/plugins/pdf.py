#!/usr/bin/env python3
from __future__ import annotations
# Standard Library
from pathlib import Path

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_fields

try:
	from pypdf import PdfReader
except Exception:
	PdfReader = None

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
		if not PdfReader:
			return
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
					meta.summary = joined[:1500]
				meta.extra["page_count"] = len(pages)
		except Exception:
			return
