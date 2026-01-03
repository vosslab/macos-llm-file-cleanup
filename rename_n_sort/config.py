#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from dataclasses import dataclass, field
from pathlib import Path

#============================================


def _default_roots() -> list[Path]:
	return []


#============================================


@dataclass(slots=True)
class AppConfig:
	"""
	Runtime configuration settings.

	Attributes:
		roots: Paths to scan.
		target_root: Folder where cleaned files are stored (default: <search_root>/Organized).
		dry_run: Only print planned work.
		max_files: Optional limit.
		max_depth: Maximum directory depth to scan.
		include_extensions: Optional filter set.
		exclude_hidden: Skip dotfiles when True.
		llm_backend: LLM backend selector ("macos" or "ollama").
		model_override: Optional Ollama model name.
	"""
	roots: list[Path] = field(default_factory=_default_roots)
	target_root: Path | None = None
	dry_run: bool = True
	max_files: int | None = 150
	max_depth: int = 1
	randomize: bool = True
	include_extensions: set[str] | None = None
	exclude_hidden: bool = True
	llm_backend: str = "macos"
	model_override: str | None = None
	verbose: bool = False
	context: str | None = None

	#============================================
	def normalized_roots(self) -> list[Path]:
		"""
		Normalize user root paths.

		Returns:
			List of normalized Path objects.
		"""
		paths: list[Path] = [root.expanduser().resolve() for root in self.roots]
		return paths

	#============================================
	def normalized_target_root(self) -> Path:
		"""
		Normalize target root.

		Returns:
			Normalized Path.
		"""
		if self.target_root is None:
			raise RuntimeError("target_root is not set.")
		target: Path = self.target_root.expanduser().resolve()
		return target


#============================================
def parse_exts(exts: list[str] | None) -> set[str] | None:
	"""
	Normalize extension filters.

	Args:
		exts: Extensions from CLI.

	Returns:
		Set of lowercase extensions or None.
	"""
	if not exts:
		return None
	cleaned: set[str] = set()
	for ext in exts:
		if ext:
			cleaned.add(ext.lower().lstrip("."))
	if not cleaned:
		return None
	return cleaned


#============================================
