#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path
import csv
import zipfile
import xml.etree.ElementTree as ET

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_field

#============================================


class SpreadsheetPlugin(FileMetadataPlugin):
	"""
	Plugin for spreadsheet and delimited files.
	"""

	name = "spreadsheet"
	supported_suffixes: set[str] = {"xls", "xlsx", "ods", "csv", "tsv"}

	#============================================
	def supports(self, path: Path) -> bool:
		return path.suffix.lower().lstrip(".") in self.supported_suffixes

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = path.stat().st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		title = mdls_field(path, "kMDItemTitle")
		if title:
			meta.title = title
		meta.summary = self._build_summary(path)
		return meta

	#============================================
	def _build_summary(self, path: Path) -> str:
		"""
		Construct a summary using headers/rows or sheet names.
		"""
		ext = path.suffix.lower().lstrip(".")
		if ext in {"csv", "tsv"}:
			preview = self._read_delimited(path, delimiter="\t" if ext == "tsv" else ",")
			if preview:
				return preview
		if ext in {"xlsx"}:
			names = self._xlsx_sheet_names(path)
			if names:
				return f"Sheets: {', '.join(names[:5])}"
		return f"Data file {path.name}"

	#============================================
	def _read_delimited(self, path: Path, delimiter: str) -> str | None:
		"""
		Read first few lines for delimited text.
		"""
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
			joined_rows = [" | ".join(r) for r in rows]
			head = " || ".join(joined_rows)
			head = " ".join(head.split())
			if not head:
				return None
			return head[:800]
		except Exception:
			return None

	#============================================
	def _xlsx_sheet_names(self, path: Path) -> list[str]:
		"""
		Parse sheet names from an xlsx file without heavy deps.
		"""
		names: list[str] = []
		try:
			with zipfile.ZipFile(path) as zf:
				with zf.open("xl/workbook.xml") as wb:
					tree = ET.parse(wb)
					root = tree.getroot()
					for sheet in root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
						name = sheet.attrib.get("name")
						if name:
							names.append(name)
		except Exception:
			return []
		return names
