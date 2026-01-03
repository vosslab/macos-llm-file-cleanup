#!/usr/bin/env python3
"""
Strict parsing error cases for LLM outputs.
"""

import pytest

from rename_n_sort.llm_parsers import ParseError, parse_keep_response, parse_rename_response, parse_sort_response


def test_parse_rename_missing_response_raises():
	with pytest.raises(ParseError):
		parse_rename_response("no tags here")


def test_parse_rename_missing_name_raises():
	with pytest.raises(ParseError):
		parse_rename_response("<reason>why</reason>")


def test_parse_keep_missing_reason_raises():
	with pytest.raises(ParseError):
		parse_keep_response(
			"<stem_action>keep</stem_action>",
			"abc",
		)


def test_parse_keep_duplicate_reason_raises():
	with pytest.raises(ParseError):
		parse_keep_response(
			"<stem_action>keep</stem_action>"
			"<reason>one</reason><reason>two</reason>",
			"abc",
		)


@pytest.mark.parametrize(
	"action",
	["keep", "drop", "normalize"],
)
def test_parse_keep_actions(action):
	result = parse_keep_response(
		f"<stem_action>{action}</stem_action>"
		"<reason>ok</reason>",
		"abc",
	)
	assert result.stem_action == action


def test_parse_keep_duplicate_stem_action_raises():
	with pytest.raises(ParseError):
		parse_keep_response(
			"<stem_action>keep</stem_action>"
			"<stem_action>drop</stem_action>"
			"<reason>two values</reason>",
			"abc",
		)


def test_parse_keep_legacy_keep_original_maps_to_action():
	result = parse_keep_response(
		"<keep_original>true</keep_original><reason>legacy</reason>",
		"abc",
	)
	assert result.stem_action == "keep"


def test_parse_sort_duplicate_category_raises():
	with pytest.raises(ParseError):
		parse_sort_response(
			"<category>Document</category><category>Image</category>",
			["/tmp/a.pdf"],
		)


def test_parse_sort_missing_category_raises():
	with pytest.raises(ParseError):
		parse_sort_response(
			"no category tag here",
			["/tmp/a.pdf"],
		)


def test_parse_sort_duplicate_reason_raises():
	with pytest.raises(ParseError):
		parse_sort_response(
			"<category>Document</category><reason>one</reason><reason>two</reason>",
			["/tmp/a.pdf"],
		)
