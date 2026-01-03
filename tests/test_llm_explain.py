#!/usr/bin/env python3
"""
Tests for LLM explain-mode parsing helpers.
"""

from rename_n_sort.llm import OllamaChatLLM, extract_xml_tag_content


def test_parse_keep_response_explain():
	llm = OllamaChatLLM(model="test")
	keep, reason = llm._parse_keep_response_explain(
		"Sure.\n<response>\n  <keep_original>false</keep_original>\n  <reason>looks like a UUID</reason>\n</response>\nThanks."
	)
	assert keep is False
	assert "uuid" in reason.lower()


def test_parse_rename_response_explain():
	llm = OllamaChatLLM(model="test")
	name, reason = llm._parse_rename_response_explain(
		"<response><new_name>My_File.pdf</new_name><reason>title + date</reason></response>",
		"old.pdf",
	)
	assert name == "My_File.pdf"
	assert "title" in reason.lower()


def test_parse_sort_response_expected_indices():
	llm = OllamaChatLLM(model="test")
	mapping, reasons = llm._parse_sort_response_explain(
		"OK\n<response>\n"
		"  <file index=\"10\"><category>Document</category><reason>pdf</reason></file>\n"
		"  <file index=\"11\"><category>Image</category></file>\n"
		"</response>\n",
		[10, 11, 12],
	)
	assert mapping[10] == "Document"
	assert mapping[11] == "Image"
	assert mapping[12] == "Other"
	assert "pdf" in reasons[10].lower()


def test_xml_parse_falls_back_to_plain_text():
	llm = OllamaChatLLM(model="test")
	name, reason = llm._parse_rename_response_explain(
		"new_name: Plain.pdf\nreason: plain\n",
		"old.pdf",
	)
	assert name == "Plain.pdf"
	assert reason == "plain"


def test_extracts_last_response_block():
	raw = "<response>first</response> chatter <response>second</response>"
	result = extract_xml_tag_content(raw, "response")
	assert result == "second"
