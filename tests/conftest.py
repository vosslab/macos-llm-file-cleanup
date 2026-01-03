"""
Pytest config to ensure local package imports work without installation.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_repo_root_to_path() -> None:
	"""
	Insert the repo root into sys.path for local imports.
	"""
	repo_root = Path(__file__).resolve().parent.parent
	repo_root_str = str(repo_root)
	if repo_root_str not in sys.path:
		sys.path.insert(0, repo_root_str)


_add_repo_root_to_path()

from rename_n_sort.llm_parsers import KeepResult, RenameResult, SortResult  # noqa: E402


class StubLLM:
	"""
	Test-only stub LLM for organizer/unit tests.
	"""

	def __init__(self) -> None:
		self.model = "stub"

	def rename(self, current_name: str, metadata: dict) -> RenameResult:
		return RenameResult(new_name="stub_name", reason="stub reason", raw_text="")

	def keep_original(self, original_stem: str, suggested_name: str) -> KeepResult:
		return KeepResult(keep_original=False, reason="stub keep", raw_text="")

	def sort(self, files: list) -> SortResult:
		assignments = {item.path: "Document" for item in files}
		return SortResult(assignments=assignments, raw_text="")
