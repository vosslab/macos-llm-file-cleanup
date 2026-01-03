#!/usr/bin/env python3
"""
Tests for shared XML parsing helpers.
"""

from rename_n_sort.llm_parsers import parse_keep_response, parse_rename_response, parse_sort_response
from rename_n_sort.llm_utils import extract_xml_tag_content


def test_parse_keep_response():
	result = parse_keep_response(
		"<stem_action>drop</stem_action>"
		"<reason>too generic</reason>",
		"abc123",
	)
	assert result.stem_action == "drop"
	assert "generic" in result.reason


def test_parse_rename_response():
	result = parse_rename_response(
		"<new_name>My_File.pdf</new_name><reason>title + date</reason>"
	)
	assert result.new_name == "My_File.pdf"
	assert "title" in result.reason.lower()


def test_parse_rename_response_with_code_fence():
	result = parse_rename_response(
		"```xml\n<new_name>My_File.pdf</new_name><reason>title</reason>\n```"
	)
	assert result.new_name == "My_File.pdf"


def test_parse_sort_response_expected_paths():
	result = parse_sort_response(
		"<category>Document</category>",
		["/tmp/a.pdf"],
	)
	assert result.assignments["/tmp/a.pdf"] == "Document"


def test_parse_sort_response_with_reason():
	result = parse_sort_response(
		"<category>Document</category><reason>invoice</reason>",
		["/tmp/a.pdf"],
	)
	assert result.reasons["/tmp/a.pdf"] == "invoice"


def test_extracts_last_response_block():
	raw = "<response>first</response> chatter <response>second</response>"
	result = extract_xml_tag_content(raw, "response")
	assert result == "second"
