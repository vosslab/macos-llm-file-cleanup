#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#============================================


@dataclass(slots=True)
class FileMetadata:
	"""
	Container for metadata extracted from a file.

	Attributes:
		path: Original file path.
		title: Optional human-readable title.
		keywords: Keyword hints.
		summary: Short text preview.
		plugin_name: Name of plugin used.
		extra: Extra metadata.
	"""
	path: Path
	title: str | None = None
	keywords: list[str] = field(default_factory=list)
	summary: str | None = None
	plugin_name: str = "generic"
	extra: dict[str, object] = field(default_factory=dict)

	#============================================
	def safe_title(self) -> str:
		"""
		Provide a safe fallback title.

		Returns:
			Title string derived from metadata.
		"""
		if self.title:
			return self.title
		return self.path.stem


class FileMetadataPlugin:
	"""
	Base interface for plugins.
	"""

	name: str = "base"
	supported_suffixes: set[str] = set()

	#============================================
	def supports(self, path: Path) -> bool:
		"""
		Determine if this plugin can handle the file.

		Args:
			path: File path.

		Returns:
			True if supported.
		"""
		return False

	#============================================
	def extract_metadata(self, path: Path) -> FileMetadata:
		"""
		Extract metadata for the file.

		Args:
			path: File path.

		Returns:
			FileMetadata payload.
		"""
		return FileMetadata(path=path, plugin_name=self.name)


class PluginRegistry:
	"""
	Registry for metadata plugins.
	"""

	#============================================
	def __init__(self) -> None:
		self._plugins: list[FileMetadataPlugin] = []

	#============================================
	def register(self, plugin: FileMetadataPlugin) -> None:
		"""
		Register a plugin.

		Args:
			plugin: Plugin instance.
		"""
		self._plugins.append(plugin)

	#============================================
	def for_path(self, path: Path) -> FileMetadataPlugin:
		"""
		Find the first plugin that supports the path.

		Args:
			path: File path.

		Returns:
			Plugin instance.
		"""
		for plugin in self._plugins:
			if plugin.supports(path):
				return plugin
		raise LookupError(f"No plugin registered for {path.suffix or 'unknown'}")

	#============================================
	def plugins(self) -> list[FileMetadataPlugin]:
		"""
		Return all plugins.

		Returns:
			List of plugins.
		"""
		return list(self._plugins)
