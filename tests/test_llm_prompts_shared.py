#!/usr/bin/env python3
"""
Prompt builder and sanitization tests.
"""

from rename_n_sort.llm_prompts import RenameRequest, build_format_fix_prompt, build_rename_prompt
from rename_n_sort.llm_utils import _sanitize_prompt_text


def test_format_fix_prompt_includes_schema_and_original():
	original = "original prompt text"
	schema = "<response><new_name>X</new_name></response>"
	prompt = build_format_fix_prompt(original, schema)
	assert "previous reply did not match" in prompt.lower()
	assert schema in prompt
	assert original in prompt


def test_sanitize_prompt_text_removes_long_tokens_and_duplicates():
	raw = "short\n" + ("x" * 100) + "\nshort\n"
	cleaned = _sanitize_prompt_text(raw, max_token_len=20)
	assert "x" * 100 not in cleaned
	assert cleaned.count("short") == 1


def test_rename_prompt_uses_sanitized_description():
	req = RenameRequest(metadata={"description": "Line1\nLine1\n" + ("y" * 90)}, current_name="a.txt")
	prompt = build_rename_prompt(req)
	assert "Line1" in prompt
	assert ("y" * 90) not in prompt
