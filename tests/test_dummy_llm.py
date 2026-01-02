#!/usr/bin/env python3
"""
Tests for DummyLLM behavior.
"""

from macos_llm_file_cleanup.llm import DummyLLM


def test_dummy_llm_uses_title():
	llm = DummyLLM(model="dummy")
	metadata = {
		"title": "Project Plan",
		"keywords": ["alpha", "beta"],
		"extension": "pdf",
	}
	name, category = llm.suggest_name_and_category(metadata, "old.pdf")
	assert "Project" in name
	assert category == "docs"
