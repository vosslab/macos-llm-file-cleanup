#!/usr/bin/env python3
"""
Directory scanner for cleanup.
"""

# Standard Library
from pathlib import Path

# local repo modules
from .config import AppConfig

#============================================


def iter_files(config: AppConfig) -> list[Path]:
	"""
	Iterate over files according to config.

	Args:
		config: Application configuration.

	Returns:
		List of file paths.
	"""
	paths: list[Path] = []
	for root in config.normalized_roots():
		if not root.exists():
			continue
		candidates = root.rglob("*") if config.recursive else root.iterdir()
		for path in candidates:
			if path.is_dir():
				continue
			if config.exclude_hidden and path.name.startswith("."):
				continue
			if config.include_extensions:
				ext = path.suffix.lower().lstrip(".")
				if ext not in config.include_extensions:
					continue
			paths.append(path)
	return paths
