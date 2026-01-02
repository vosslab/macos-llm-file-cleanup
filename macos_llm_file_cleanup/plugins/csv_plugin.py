#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path
import csv

# local repo modules
from .base import FileMetadata, FileMetadataPlugin

#============================================


class CSVPlugin(FileMetadataPlugin):
	"""
	Plugin for CSV/TSV files.
	"""

	name = "csv"
	supported_suffixes: set[str] = {"csv", "tsv"}

	#============================================
	def supports(self, path: Path) -> bool:
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		meta.title = path.stem
		preview = self._read_preview(path)
		if preview:
			meta.summary = preview
		return meta

	#============================================
	def _read_preview(self, path: Path) -> str | None:
		"""
		Read first few rows for context.
		"""
		delimiter = "\t" if path.suffix.lower().lstrip(".") == "tsv" else ","
		try:
			with path.open("r", encoding="utf-8", errors="ignore") as handle:
				reader = csv.reader(handle, delimiter=delimiter)
				rows = []
				for idx, row in enumerate(reader):
					rows.append(row)
					if idx >= 2:
						break
			if not rows:
				return None
			joined = [" | ".join(row) for row in rows]
			flat = " || ".join(joined)
			flat = " ".join(flat.split())
			if not flat:
				return None
			return flat[:800]
		except Exception:
			return None
