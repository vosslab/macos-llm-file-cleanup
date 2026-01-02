#!/usr/bin/env python3
"""
Tests for collision handling.
"""

from pathlib import Path

from macos_llm_file_cleanup.renamer import apply_move


def test_collision_creates_counter(tmp_path: Path):
	first = tmp_path / "file.txt"
	first.write_text("data")
	second = tmp_path / "file2.txt"
	second.write_text("other")
	target = tmp_path / "file.txt"
	placed = apply_move(first, target, dry_run=False)
	assert placed.exists()
	third = apply_move(second, target, dry_run=False)
	assert third.name != target.name
	assert third.name.startswith("file (")
