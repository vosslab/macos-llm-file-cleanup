#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path
import shutil
import subprocess
import tempfile

# PIP3 modules
try:
	import docx
except Exception:
	docx = None

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
	def _print_why(self, path: Path, message: str) -> None:
		print(f"[WHY] {path.name}: {message}")

	#============================================
	def _read_preview(self, path: Path) -> str | None:
		"""
		Read a short preview for text-like documents.
		"""
		ext = path.suffix.lower().lstrip(".")
		if ext == "doc":
			return self._read_doc_via_soffice(path)
		if ext not in {"txt", "md", "rtf"}:
			return None
		try:
			text_blob = path.read_text(encoding="utf-8", errors="ignore")
		except Exception:
			return None
		flattened = " ".join(text_blob.split())
		if not flattened:
			return None
		return flattened[:800]

	def _read_doc_via_soffice(self, path: Path) -> str | None:
		if not docx:
			self._print_why(path, "python-docx not installed; skipping DOC conversion")
			return None
		soffice = shutil.which("soffice")
		if not soffice:
			self._print_why(path, "LibreOffice not found; skipping DOC conversion")
			return None
		with tempfile.TemporaryDirectory() as tmp_dir:
			output_path = Path(tmp_dir) / f"{path.stem}.docx"
			try:
				subprocess.run(
					[
						soffice,
						"--headless",
						"--convert-to",
						"docx",
						"--outdir",
						tmp_dir,
						str(path),
					],
					check=True,
					stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL,
					timeout=30,
				)
			except Exception as exc:
				self._print_why(path, f"LibreOffice conversion failed ({exc.__class__.__name__})")
				return None
			if not output_path.exists():
				self._print_why(path, "LibreOffice conversion produced no output")
				return None
			return self._extract_docx_summary(output_path)

	def _extract_docx_summary(self, path: Path) -> str | None:
		if not docx:
			return None
		try:
			document = docx.Document(path)
		except Exception:
			return None
		all_text: list[str] = []
		for paragraph in document.paragraphs:
			if paragraph.text:
				all_text.append(paragraph.text.strip())
		if not all_text:
			return None
		full = " ".join(all_text)
		head = full[:256]
		tail = full[-256:] if len(full) > 256 else ""
		return f"{head} ... {tail}".strip() if tail else head
