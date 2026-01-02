#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
from dataclasses import dataclass, field
from pathlib import Path
import json

# PIP3 modules
try:
	import yaml
except Exception:
	yaml = None

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
		target_root: Folder where cleaned files are stored.
		dry_run: Only print planned work.
		max_files: Optional limit.
		recursive: Traverse subdirectories.
		include_extensions: Optional filter set.
		exclude_hidden: Skip dotfiles when True.
		llm_backend: LLM backend selector ("macos" or "ollama").
		explain: Print LLM decisions and reasoning.
		model_override: Optional Ollama model name.
		config_path: Optional user config path.
	"""
	roots: list[Path] = field(default_factory=_default_roots)
	target_root: Path = field(default_factory=lambda: Path.home() / "Organized")
	dry_run: bool = True
	max_files: int | None = 150
	recursive: bool = True
	include_extensions: set[str] | None = None
	exclude_hidden: bool = True
	llm_backend: str = "macos"
	explain: bool = True
	model_override: str | None = None
	config_path: Path | None = None
	verbose: bool = False
	context: str | None = None
	randomize: bool = False
	one_by_one: bool = False

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


def load_user_config(config_path: Path | None) -> dict:
	"""
	Load user configuration from yaml or json.

	Args:
		config_path: Path to config file.

	Returns:
		Dictionary of loaded values or empty dict.
	"""
	if not config_path:
		return {}
	if not config_path.exists():
		return {}
	if config_path.suffix.lower() in {".yml", ".yaml"} and yaml:
		with config_path.open("r", encoding="utf-8") as handle:
			loaded = yaml.safe_load(handle)
			return loaded or {}
	with config_path.open("r", encoding="utf-8") as handle:
		return json.load(handle)
