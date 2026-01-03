#!/usr/bin/env python3
"""
Prompt builder and sanitization tests.
"""

from rename_n_sort.llm_prompts import (
	KeepRequest,
	RenameRequest,
	SortItem,
	SortRequest,
	build_format_fix_prompt,
	build_keep_prompt,
	build_rename_prompt,
	build_sort_prompt,
)
from rename_n_sort.llm_utils import _sanitize_prompt_text


def test_format_fix_prompt_includes_example():
	original = "original prompt text"
	example = "<new_name>X.pdf</new_name><reason>invoice</reason>"
	prompt = build_format_fix_prompt(original, example)
	assert "reply with tags only" in prompt.lower()
	assert example in prompt


def test_format_fix_prompt_avoids_xml_word():
	prompt = build_format_fix_prompt("prompt", "<new_name>X</new_name>")
	assert "xml" not in prompt.lower()


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


def test_rename_prompt_includes_filetype_hint():
	req = RenameRequest(
		metadata={"filetype_hint": "ZIP archive", "summary": "Archive from vendor"},
		current_name="bundle.zip",
	)
	prompt = build_rename_prompt(req)
	assert "filetype: ZIP archive" in prompt


def test_prompts_avoid_response_and_short_reason():
	req = RenameRequest(metadata={"extension": "pdf"}, current_name="old.pdf")
	prompt = build_rename_prompt(req)
	assert "<response>" not in prompt
	assert "short reason" not in prompt.lower()
	keep_prompt = build_keep_prompt(
		KeepRequest(original_stem="A1", suggested_name="Report", extension=None, features={})
	)
	assert "<response>" not in keep_prompt
	assert "short reason" not in keep_prompt.lower()
	assert "<stem_action>" in keep_prompt


def test_sort_prompt_includes_reason():
	req = SortRequest(
		files=[SortItem(path="/tmp/a.pdf", name="A", ext="pdf", description="")],
		context=None,
	)
	prompt = build_sort_prompt(req)
	assert "<category>" in prompt
	assert "<reason>" in prompt
	assert "<file" not in prompt
	assert "<response>" not in prompt
