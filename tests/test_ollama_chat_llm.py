#!/usr/bin/env python3
"""
Tests for OllamaChatLLM helpers.
"""

from macos_llm_file_cleanup.llm import OllamaChatLLM, sanitize_filename


def test_parse_response_text_extracts_fields():
	llm = OllamaChatLLM(model="test")
	response = "new_name: Project Plan\ncategory: docs"
	name, category = llm._parse_response_text(
		response, {"extension": "pdf"}, "old.pdf"
	)
	assert name == sanitize_filename("Project Plan")
	assert category == sanitize_filename("docs")


def test_add_system_message_stores_history():
	llm = OllamaChatLLM(model="test")
	llm.add_system_message("You rename files")
	assert llm.messages[0]["role"] == "system"
	assert "rename" in llm.messages[0]["content"]
