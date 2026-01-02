#!/usr/bin/env python3
"""
Tests for model selection.
"""

from macos_llm_file_cleanup import llm


def test_model_selection_small(monkeypatch):
	monkeypatch.setattr(llm, "get_vram_size_in_gb", lambda: 2)
	model = llm.choose_model(None)
	assert model == "llama3.2:1b-instruct-q4_K_M"


def test_model_selection_medium(monkeypatch):
	monkeypatch.setattr(llm, "get_vram_size_in_gb", lambda: 20)
	model = llm.choose_model(None)
	assert model == "phi4:14b-q4_K_M"


def test_model_selection_large(monkeypatch):
	monkeypatch.setattr(llm, "get_vram_size_in_gb", lambda: 40)
	model = llm.choose_model(None)
	assert model == "gpt-oss:20b"
