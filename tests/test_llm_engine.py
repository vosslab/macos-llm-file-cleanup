#!/usr/bin/env python3
"""
Tests for LLMEngine retry and fallback behavior.
"""

from rename_n_sort.llm_engine import LLMEngine


class GuardrailViolationError(Exception):
	pass


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


def test_format_fix_retry_on_parse_error():
	transport = DummyTransport(
		responses=[
			"not xml",
			"<response><new_name>Good.pdf</new_name><reason>title</reason></response>",
		]
	)
	engine = LLMEngine(transports=[transport])
	result = engine.rename("old.pdf", {"extension": "pdf"})
	assert result.new_name == "Good.pdf"
	assert len(transport.calls) == 2


def test_guardrail_fallback_to_second_transport():
	guardrail = DummyTransport(error=GuardrailViolationError("guardrail"))
	ok = DummyTransport(
		responses=["<response><new_name>Ok.pdf</new_name><reason>title</reason></response>"]
	)
	engine = LLMEngine(transports=[guardrail, ok])
	result = engine.rename("old.pdf", {"extension": "pdf"})
	assert result.new_name == "Ok.pdf"
	assert len(guardrail.calls) == 2
	assert len(ok.calls) == 1


def test_guardrail_retry_minimal_prompt_on_first_transport():
	class FlakyGuardrail(DummyTransport):
		def __init__(self):
			super().__init__(responses=[
				"<response><new_name>Ok.pdf</new_name><reason>title</reason></response>"
			])
			self.first = True

		def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
			self.calls.append((purpose, prompt))
			if self.first:
				self.first = False
				raise GuardrailViolationError("guardrail")
			return super().generate(prompt, purpose=purpose, max_tokens=max_tokens)

	engine = LLMEngine(transports=[FlakyGuardrail()])
	result = engine.rename("old.pdf", {"extension": "pdf", "summary": "text"})
	assert result.new_name == "Ok.pdf"
	assert engine.transports[0].calls[0][1] != engine.transports[0].calls[1][1]


def test_parse_failure_falls_back_to_second_transport_on_format_fix():
	first = DummyTransport(responses=["not xml", "still bad"])
	second = DummyTransport(
		responses=["<response><new_name>Fixed.pdf</new_name><reason>ok</reason></response>"]
	)
	engine = LLMEngine(transports=[first, second])
	result = engine.rename("old.pdf", {"extension": "pdf"})
	assert result.new_name == "Fixed.pdf"
	assert len(first.calls) == 2
	assert len(second.calls) == 1
	assert "format fix" in second.calls[0][0].lower()


def test_guardrail_then_format_fix_falls_back_to_second_transport():
	guardrail = DummyTransport(error=GuardrailViolationError("guardrail"))
	second = DummyTransport(
		responses=[
			"not xml",
			"<response><new_name>Ok.pdf</new_name><reason>ok</reason></response>",
		]
	)
	engine = LLMEngine(transports=[guardrail, second])
	result = engine.rename("old.pdf", {"extension": "pdf"})
	assert result.new_name == "Ok.pdf"
	assert len(guardrail.calls) == 3
	assert len(second.calls) == 2
	assert "format fix" in second.calls[1][0].lower()
