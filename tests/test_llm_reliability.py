#!/usr/bin/env python3
"""Reliability tests for LLM behavior normalization."""

import pytest

from rename_n_sort.llm_engine import LLMEngine
from rename_n_sort.llm_utils import MAX_FILENAME_CHARS


class DummyTransport:
	name = "Dummy"

	def __init__(self, responses=None, error: Exception | None = None):
		self.responses = list(responses or [])
		self.error = error
		self.calls: list[tuple[str, str]] = []

	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		self.calls.append((purpose, prompt))
		if self.error:
			raise self.error
		if not self.responses:
			raise RuntimeError("No response queued")
		return self.responses.pop(0)


def test_rename_sanitizes_filename_and_reason():
	transport = DummyTransport(
		responses=[
			"<response><new_name>Bad Name/?.pdf</new_name><reason>short reason</reason></response>"
		]
	)
	engine = LLMEngine(transports=[transport])
	result = engine.rename("old.pdf", {"extension": "pdf"})
	assert " " not in result.new_name
	assert "/" not in result.new_name
	assert "?" not in result.new_name
	assert result.new_name.endswith(".pdf")
	assert len(result.new_name) <= MAX_FILENAME_CHARS
	assert result.reason == ""


def test_keep_original_normalizes_placeholder_reason():
	transport = DummyTransport(
		responses=[
			(
				"<response><keep_original>true</keep_original>"
				"<reason>short justification original_stem=\"Report\"</reason>"
				"</response>"
			)
		]
	)
	engine = LLMEngine(transports=[transport])
	result = engine.keep_original("Report", "NewReport")
	assert result.keep_original is True
	assert result.reason == ""


def test_format_fix_raises_last_transport_error():
	first = DummyTransport(responses=["not xml"])
	second = DummyTransport(error=ValueError("transport down"))
	engine = LLMEngine(transports=[first, second])
	with pytest.raises(ValueError, match="transport down"):
		engine.rename("old.pdf", {"extension": "pdf"})
