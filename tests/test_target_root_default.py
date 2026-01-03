#!/usr/bin/env python3
"""
Tests for default target root behavior.
"""

from pathlib import Path

from rename_n_sort.config import AppConfig
from rename_n_sort.organizer import Organizer
from conftest import StubLLM


def test_default_target_root_uses_search_root(tmp_path: Path) -> None:
	root = tmp_path
	source = root / "example.txt"
	source.write_text("hello world", encoding="utf-8")
	cfg = AppConfig(roots=[root], dry_run=True)
	org = Organizer(cfg, llm=StubLLM())
	plan, _summary = org._plan_one(source)
	target = org._target_path(source, plan.new_name, "Document")
	assert str(target).startswith(str(root / "Organized"))
