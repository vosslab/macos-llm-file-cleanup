#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from datetime import datetime
from pathlib import Path

# local repo modules
from .base import FileMetadata, FileMetadataPlugin
from .mdls_utils import mdls_fields

#============================================


class GenericPlugin(FileMetadataPlugin):
	"""
	Generic fallback metadata plugin.
	"""

	name = "generic"
	supported_suffixes: set[str] = set()

	#============================================
	def supports(self, path: Path) -> bool:
		"""
		Always supports the file as a fallback.

		Args:
			path: File path.

		Returns:
			True for all files.
		"""
		return True

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		"""
		Collect basic stat and mdls fields.

		Args:
			path: File path.

		Returns:
			Populated FileMetadata.
		"""
		file_stat = path.stat()
		meta = FileMetadata(path=path, plugin_name=self.name)
		meta.extra["size_bytes"] = file_stat.st_size
		meta.extra["extension"] = path.suffix.lstrip(".")
		created_ts = getattr(file_stat, "st_birthtime", None)
		if not created_ts:
			created_ts = file_stat.st_mtime
		meta.extra["created"] = datetime.fromtimestamp(created_ts).isoformat()
		meta.extra["modified"] = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
		mdls_data = mdls_fields(
			path,
			[
				"kMDItemKind",
				"kMDItemContentType",
				"kMDItemWhereFroms",
			],
		)
		if "kMDItemKind" in mdls_data:
			meta.title = mdls_data["kMDItemKind"]
		if "kMDItemWhereFroms" in mdls_data:
			meta.keywords.append(mdls_data["kMDItemWhereFroms"])
		meta.extra.update(mdls_data)
		return meta
