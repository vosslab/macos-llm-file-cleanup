#!/usr/bin/env python3
"""Tests for keep_original handling."""

from rename_n_sort.organizer import Organizer
from rename_n_sort.config import AppConfig
from conftest import StubLLM


def test_keep_original_combines_original_stem():
	org = Organizer(AppConfig(roots=[]), llm=StubLLM())
	final = org._normalize_new_name("orig.txt", "orig_NewName.txt")
	assert "orig" in final.lower()
