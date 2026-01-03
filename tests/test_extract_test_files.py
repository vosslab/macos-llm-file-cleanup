#!/usr/bin/env python3
"""
Extraction checks for repo test files.
"""

from pathlib import Path

from rename_n_sort.plugins import build_registry


def test_extract_test_files_metadata():
	root = Path("tests/test_files")
	if not root.exists():
		return
	registry = build_registry()
	for path in sorted(root.iterdir()):
		if not path.is_file():
			continue
		plugin = registry.for_path(path)
		if plugin.name == "image":
			plugin._extract_ocr_text = lambda _path: None
			plugin._try_caption = lambda _path: None
		meta = plugin.extract_metadata(path)
		assert meta.plugin_name == plugin.name
		assert meta.extra.get("extension") == path.suffix.lstrip(".")


def test_extract_test_files_content_expectations():
	root = Path("tests/test_files")
	if not root.exists():
		return
	registry = build_registry()
	expected_plugins = {
		"doc": "document",
		"docx": "docx",
		"odt": "odt",
		"odp": "presentation",
		"ppt": "presentation",
		"pptx": "presentation",
		"png": "image",
		"jpg": "image",
		"jpeg": "image",
		"gif": "image",
		"bmp": "image",
		"tiff": "image",
		"txt": "document",
	}
	required_summary_exts = {"docx", "odt", "pptx", "odp", "txt"}
	for path in sorted(root.iterdir()):
		if not path.is_file():
			continue
		ext = path.suffix.lstrip(".").lower()
		if ext not in expected_plugins:
			continue
		plugin = registry.for_path(path)
		if plugin.name == "image":
			plugin._extract_ocr_text = lambda _path: None
			plugin._try_caption = lambda _path: None
		meta = plugin.extract_metadata(path)
		assert plugin.name == expected_plugins[ext]
		if ext in required_summary_exts:
			assert meta.summary
