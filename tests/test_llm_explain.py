#!/usr/bin/env python3
"""
Tests for shared XML parsing helpers.
"""

from rename_n_sort.llm_parsers import parse_keep_response, parse_rename_response, parse_sort_response
from rename_n_sort.llm_utils import extract_xml_tag_content


def test_parse_keep_response():
	result = parse_keep_response(
		"<response><keep_original>false</keep_original>"
		"<reason>flagged original_stem=\"abc123\"</reason></response>",
		"abc123",
	)
	assert result.keep_original is False
	assert "abc123" in result.reason


def test_parse_rename_response():
	result = parse_rename_response(
		"<response><new_name>My_File.pdf</new_name><reason>title + date</reason></response>"
	)
	assert result.new_name == "My_File.pdf"
	assert "title" in result.reason.lower()


def test_parse_sort_response_expected_paths():
	result = parse_sort_response(
		"<response>"
		"<file path=\"/tmp/a.pdf\">Document</file>"
		"<file path=\"/tmp/b.png\">Image</file>"
		"</response>",
		["/tmp/a.pdf", "/tmp/b.png"],
	)
	assert result.assignments["/tmp/a.pdf"] == "Document"
	assert result.assignments["/tmp/b.png"] == "Image"


def test_extracts_last_response_block():
	raw = "<response>first</response> chatter <response>second</response>"
	result = extract_xml_tag_content(raw, "response")
	assert result == "second"
