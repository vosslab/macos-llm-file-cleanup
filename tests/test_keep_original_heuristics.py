#!/usr/bin/env python3
"""
Tests for keep-original heuristics in the local backend.
"""

from macos_llm_file_cleanup.llm import DummyLLM


def test_keep_original_false_for_uuid():
	llm = DummyLLM(model="dummy")
	keep, reason = llm.should_keep_original_explain(
		{}, "550e8400-e29b-41d4-a716-446655440000.pdf", "Some_Name.pdf"
	)
	assert keep is False
	assert "uuid" in reason.lower()


def test_keep_original_false_for_long_token_like():
	llm = DummyLLM(model="dummy")
	keep, reason = llm.should_keep_original_explain(
		{}, "LuWoVaUQXGZ5ahPvFp6A_MagoDinner_0725V10_FINAL_WEB.pdf", "Menu.pdf"
	)
	assert keep is False
	assert "token" in reason.lower() or "long" in reason.lower()


def test_keep_original_true_for_named_file():
	llm = DummyLLM(model="dummy")
	keep, reason = llm.should_keep_original_explain({}, "NeilVoss_Notes.txt", "Notes.txt")
	assert keep is True
	assert reason

