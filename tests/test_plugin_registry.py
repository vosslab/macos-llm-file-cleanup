#!/usr/bin/env python3
"""
Tests for plugin selection.
"""

from pathlib import Path

from macos_llm_file_cleanup.plugins import build_registry


def test_registry_picks_pdf_plugin(tmp_path: Path):
	registry = build_registry()
	test_file = tmp_path / "sample.pdf"
	test_file.write_text("content")
	plugin = registry.for_path(test_file)
	assert plugin.name == "pdf"


def test_registry_picks_image_plugin(tmp_path: Path):
	registry = build_registry()
	test_file = tmp_path / "photo.jpg"
	test_file.write_bytes(b"data")
	plugin = registry.for_path(test_file)
	assert plugin.name == "image"
