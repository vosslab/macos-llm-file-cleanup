#!/usr/bin/env python3
"""
Strict parsing error cases for LLM outputs.
"""

import pytest

from rename_n_sort.llm_parsers import ParseError, parse_keep_response, parse_rename_response, parse_sort_response


def test_parse_rename_missing_response_raises():
	with pytest.raises(ParseError):
		parse_rename_response("no xml here")


def test_parse_rename_missing_name_raises():
	with pytest.raises(ParseError):
		parse_rename_response("<response><reason>why</reason></response>")


def test_parse_keep_missing_reason_raises():
	with pytest.raises(ParseError):
		parse_keep_response("<response><keep_original>true</keep_original></response>", "abc")


def test_parse_keep_requires_stem_once():
	with pytest.raises(ParseError):
		parse_keep_response(
			"<response><keep_original>true</keep_original>"
			"<reason>original_stem=\"abc\" and original_stem=\"abc\"</reason></response>",
			"abc",
		)


@pytest.mark.parametrize(
	"keep_value, expected",
	[
		("true", True),
		("TRUE", True),
		("1", True),
		("yes", True),
		("false", False),
		("FALSE", False),
		("0", False),
		("no", False),
	],
)
def test_parse_keep_boolean_variants(keep_value, expected):
	result = parse_keep_response(
		f"<response><keep_original>{keep_value}</keep_original>"
		"<reason>original_stem=\"abc\"</reason></response>",
		"abc",
	)
	assert result.keep_original is expected


def test_parse_keep_requires_exact_stem_match():
	with pytest.raises(ParseError):
		parse_keep_response(
			"<response><keep_original>true</keep_original>"
			"<reason>original_stem=\"Abc\"</reason></response>",
			"abc",
		)


def test_parse_sort_duplicate_paths_raises():
	with pytest.raises(ParseError):
		parse_sort_response(
			"<response>"
			"<file path=\"/tmp/a.pdf\">Document</file>"
			"<file path=\"/tmp/a.pdf\">Image</file>"
			"</response>",
			["/tmp/a.pdf"],
		)


def test_parse_sort_missing_path_raises():
	with pytest.raises(ParseError):
		parse_sort_response(
			"<response><file path=\"/tmp/a.pdf\">Document</file></response>",
			["/tmp/a.pdf", "/tmp/b.pdf"],
		)
