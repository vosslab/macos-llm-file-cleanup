#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from pathlib import Path

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_field

#============================================


class VideoPlugin(FileMetadataPlugin):
	"""
	Plugin for video formats.
	"""

	name = "video"
	supported_suffixes: set[str] = {"mp4", "mov", "mkv", "webm", "avi"}

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
		meta.summary = f"Video file {path.suffix.lower().lstrip('.')}"
		return meta
