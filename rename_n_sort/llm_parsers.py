#!/usr/bin/env python3
"""
Backend-agnostic response parsers.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
import html
import re

# local repo modules
from .llm_utils import extract_xml_tag_content

#============================================


class ParseError(RuntimeError):
	"""
	Raised when a model response does not match required XML.
	"""

	def __init__(self, message: str, raw_text: str = "") -> None:
		super().__init__(message)
		self.raw_text = raw_text


@dataclass(slots=True)
class RenameResult:
	new_name: str
	reason: str
	raw_text: str


@dataclass(slots=True)
class KeepResult:
	keep_original: bool
	reason: str
	raw_text: str


@dataclass(slots=True)
class SortResult:
	assignments: dict[str, str]
	raw_text: str


_CODE_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
	if not text:
		return ""
	cleaned = text.strip()
	if "```" not in cleaned:
		return cleaned
	def _unwrap(match: re.Match) -> str:
		return match.group(1)
	cleaned = _CODE_FENCE_RE.sub(_unwrap, cleaned)
	return cleaned.strip()


def _coerce_response_body(text: str) -> str:
	cleaned = _strip_code_fences(text).strip().strip('"').strip("'")
	response_body = extract_xml_tag_content(cleaned, "response")
	if not response_body and "&lt;response" in cleaned.lower():
		unescaped = html.unescape(cleaned)
		response_body = extract_xml_tag_content(unescaped, "response")
	if response_body and "<response" in response_body.lower():
		response_body = extract_xml_tag_content(response_body, "response")
	if not response_body and (
		"<keep_original" in cleaned.lower()
		or "<new_name" in cleaned.lower()
		or "<file" in cleaned.lower()
	):
		return cleaned
	return response_body


def _extract_reason_text(response_body: str) -> str:
	reason_text = extract_xml_tag_content(response_body, "reason")
	if reason_text:
		return reason_text
	match = re.search(r"<reason\b([^>/]*?)/?>", response_body, flags=re.IGNORECASE)
	if not match:
		return ""
	attrs = match.group(1).strip()
	if not attrs:
		return ""
	return html.unescape(" ".join(attrs.split()))


def parse_rename_response(text: str) -> RenameResult:
	response_body = _coerce_response_body(text)
	if not response_body:
		raise ParseError("Missing required tags in rename response.", text)
	new_name = extract_xml_tag_content(response_body, "new_name")
	reason = _extract_reason_text(response_body)
	if not new_name:
		raise ParseError("Missing <new_name> in rename response.", text)
	if not reason:
		raise ParseError("Missing <reason> in rename response.", text)
	return RenameResult(new_name=new_name, reason=reason, raw_text=text)

def parse_keep_response(
	text: str, original_stem: str, *, require_stem_reason: bool = False
) -> KeepResult:
	response_body = _coerce_response_body(text)
	if not response_body:
		raise ParseError("Missing required tags in keep response.", text)
	keep_text = extract_xml_tag_content(response_body, "keep_original").strip().lower()
	reason = _extract_reason_text(response_body)
	if not keep_text:
		raise ParseError("Missing <keep_original> in keep response.", text)
	keep = keep_text.startswith("t") or keep_text == "1" or keep_text == "yes"
	if not reason:
		if require_stem_reason:
			raise ParseError("Missing <reason> in keep response.", text)
		reason = ""
	reason = reason.replace('\\"', '"').replace("\\'", "'")
	expected = f'original_stem="{original_stem}"'
	if reason and reason.count(expected) != 1:
		if require_stem_reason:
			raise ParseError("Keep reason must include original_stem exactly once.", text)
		reason = ""
	return KeepResult(keep_original=keep, reason=reason, raw_text=text)


def parse_sort_response(text: str, expected_paths: list[str]) -> SortResult:
	response_body = _coerce_response_body(text)
	if not response_body:
		raise ParseError("Missing required tags in sort response.", text)
	mapping: dict[str, str] = {}
	for match in re.finditer(
		r"<file\b[^>]*\bpath\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</file>",
		response_body,
		flags=re.IGNORECASE | re.DOTALL,
	):
		path = match.group(1).strip()
		value = match.group(2).strip()
		if not path or not value:
			raise ParseError("Empty file path or category in sort response.")
		if path in mapping:
			raise ParseError("Duplicate file path in sort response.")
		mapping[path] = value
	missing = [p for p in expected_paths if p not in mapping]
	if missing:
		raise ParseError(f"Missing file paths in sort response: {missing[:3]}")
	return SortResult(assignments=mapping, raw_text=text)
