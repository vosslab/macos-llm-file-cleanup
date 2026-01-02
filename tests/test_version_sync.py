#!/usr/bin/env python3
"""
Tests for version sync between VERSION and pyproject.toml.
"""

from pathlib import Path
import tomllib


def test_version_file_matches_pyproject():
	repo_root = Path(__file__).resolve().parent.parent
	version_file = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
	pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
	assert version_file == pyproject["project"]["version"]

