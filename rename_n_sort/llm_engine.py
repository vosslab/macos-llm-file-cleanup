#!/usr/bin/env python3
"""
Backend-agnostic LLM engine with fallback and strict parsing.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass

# local repo modules
from .llm_parsers import ParseError, KeepResult, RenameResult, SortResult, parse_keep_response, parse_rename_response, parse_sort_response
from .llm_prompts import (
	KeepRequest,
	RenameRequest,
	SortItem,
	SortRequest,
	RENAME_SCHEMA_XML,
	KEEP_SCHEMA_XML,
	SORT_SCHEMA_XML,
	build_format_fix_prompt,
	build_keep_prompt,
	build_rename_prompt,
	build_rename_prompt_minimal,
	build_sort_prompt,
)
from .llm_utils import (
	compute_stem_features,
	_is_guardrail_error,
	_print_llm,
	normalize_reason,
	sanitize_filename,
)
from .transports.base import LLMTransport

#============================================


@dataclass(slots=True)
class LLMEngine:
	transports: list[LLMTransport]
	context: str | None = None

	#============================================
	def rename(self, current_name: str, metadata: dict) -> RenameResult:
		req = RenameRequest(metadata=metadata, current_name=current_name, context=self.context)
		prompt = build_rename_prompt(req)
		raw = self._generate_with_fallback(
			prompt,
			purpose="filename based on content",
			max_tokens=200,
			retry_prompt=build_rename_prompt_minimal(req),
		)
		result = self._parse_with_retry(
			lambda text: parse_rename_response(text),
			prompt,
			RENAME_SCHEMA_XML,
			raw,
			purpose="filename based on content",
			max_tokens=200,
		)
		result.new_name = sanitize_filename(result.new_name)
		result.reason = normalize_reason(result.reason)
		return result

	#============================================
	def keep_original(self, original_stem: str, suggested_name: str) -> KeepResult:
		features = compute_stem_features(original_stem, suggested_name)
		req = KeepRequest(
			original_stem=original_stem, suggested_name=suggested_name, features=features
		)
		prompt = build_keep_prompt(req)
		raw = self._generate_with_fallback(
			prompt,
			purpose="if original filename should be kept",
			max_tokens=120,
			retry_prompt=None,
		)
		result = self._parse_with_retry(
			lambda text: parse_keep_response(text, original_stem),
			prompt,
			KEEP_SCHEMA_XML,
			raw,
			purpose="if original filename should be kept",
			max_tokens=120,
		)
		result.reason = normalize_reason(result.reason)
		return result

	#============================================
	def sort(self, files: list[SortItem]) -> SortResult:
		req = SortRequest(files=files, context=self.context)
		prompt = build_sort_prompt(req)
		raw = self._generate_with_fallback(
			prompt,
			purpose="category assignment",
			max_tokens=240,
			retry_prompt=None,
		)
		expected_paths = [item.path for item in files]
		return self._parse_with_retry(
			lambda text: parse_sort_response(text, expected_paths),
			prompt,
			SORT_SCHEMA_XML,
			raw,
			purpose="category assignment",
			max_tokens=240,
		)

	#============================================
	def _generate_with_fallback(
		self,
		prompt: str,
		*,
		purpose: str,
		max_tokens: int,
		retry_prompt: str | None,
	) -> str:
		last_exc: Exception | None = None
		for idx, transport in enumerate(self.transports):
			try:
				_print_llm(f"asking {transport.name} for {purpose}")
				return self._generate_on_transport(transport, prompt, purpose, max_tokens)
			except Exception as exc:
				last_exc = exc
				if _is_guardrail_error(exc):
					if retry_prompt and idx == 0:
						try:
							_print_llm(
								f"retrying {transport.name} with minimal prompt for {purpose}"
							)
							return self._generate_on_transport(
								transport, retry_prompt, purpose, max_tokens
							)
						except Exception as retry_exc:
							last_exc = retry_exc
							if _is_guardrail_error(retry_exc):
								continue
							raise
					continue
				raise
		if last_exc:
			raise last_exc
		raise RuntimeError("No LLM transports available.")

	#============================================
	def _parse_with_retry(
		self,
		parser,
		original_prompt: str,
		schema_xml: str,
		raw_text: str,
		*,
		purpose: str,
		max_tokens: int,
	):
		try:
			return parser(raw_text)
		except ParseError as exc:
			excerpt = " ".join(raw_text.split())[:160]
			print(f"[WHY] parse_error: {exc} (excerpt: {excerpt})")
			fix_prompt = build_format_fix_prompt(original_prompt, schema_xml)
			last_parse: ParseError | None = None
			last_transport: Exception | None = None
			for transport in self.transports:
				try:
					_print_llm(f"asking {transport.name} for {purpose} (format fix)")
					fixed = self._generate_on_transport(
						transport,
						fix_prompt,
						f"{purpose} (format fix)",
						max_tokens,
					)
				except Exception as transport_exc:
					if _is_guardrail_error(transport_exc):
						last_transport = transport_exc
						continue
					last_transport = transport_exc
					continue
				try:
					return parser(fixed)
				except ParseError as parse_exc:
					last_parse = parse_exc
					continue
			if last_parse:
				raise last_parse
			if last_transport:
				raise last_transport
			raise ParseError("Format-fix retry failed.")

	#============================================
	def _generate_on_transport(
		self,
		transport: LLMTransport,
		prompt: str,
		purpose: str,
		max_tokens: int,
	) -> str:
		return transport.generate(prompt, purpose=purpose, max_tokens=max_tokens)
