#!/usr/bin/env python3
"""
Tests for CLI LLM backend selection.
"""

from macos_llm_file_cleanup.cli import build_llm
from macos_llm_file_cleanup.config import AppConfig
from macos_llm_file_cleanup.llm import MacOSLocalLLM, OllamaChatLLM


def test_backend_macos_default():
	cfg = AppConfig(roots=[])
	cfg.llm_backend = "macos"
	llm = build_llm(cfg)
	assert isinstance(llm, MacOSLocalLLM)


def test_backend_ollama_unavailable_falls_back(monkeypatch):
	import macos_llm_file_cleanup.cli as cli

	monkeypatch.setattr(cli, "_ollama_available", lambda _url: False)
	cfg = AppConfig(roots=[])
	cfg.llm_backend = "ollama"
	llm = build_llm(cfg)
	assert isinstance(llm, MacOSLocalLLM)


def test_backend_ollama_available_uses_ollama(monkeypatch):
	import macos_llm_file_cleanup.cli as cli

	monkeypatch.setattr(cli, "_ollama_available", lambda _url: True)
	cfg = AppConfig(roots=[])
	cfg.llm_backend = "ollama"
	llm = build_llm(cfg)
	assert isinstance(llm, OllamaChatLLM)
