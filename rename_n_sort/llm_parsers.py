#!/usr/bin/env python3
"""
Backend-agnostic response parsers.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
import re

# local repo modules
from .llm_utils import extract_xml_tag_content

#============================================


class ParseError(RuntimeError):
	"""
	Raised when a model response does not match required XML.
	"""


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


def parse_rename_response(text: str) -> RenameResult:
	response_body = extract_xml_tag_content(text, "response")
	if not response_body:
		raise ParseError("Missing <response> block in rename response.")
	new_name = extract_xml_tag_content(response_body, "new_name")
	reason = extract_xml_tag_content(response_body, "reason")
	if not new_name:
		raise ParseError("Missing <new_name> in rename response.")
	if not reason:
		raise ParseError("Missing <reason> in rename response.")
	return RenameResult(new_name=new_name, reason=reason, raw_text=text)


def parse_keep_response(text: str, original_stem: str) -> KeepResult:
	response_body = extract_xml_tag_content(text, "response")
	if not response_body:
		raise ParseError("Missing <response> block in keep response.")
	keep_text = extract_xml_tag_content(response_body, "keep_original").strip().lower()
	reason = extract_xml_tag_content(response_body, "reason")
	if not keep_text:
		raise ParseError("Missing <keep_original> in keep response.")
	if not reason:
		raise ParseError("Missing <reason> in keep response.")
	keep = keep_text.startswith("t") or keep_text == "1" or keep_text == "yes"
	expected = f'original_stem="{original_stem}"'
	if reason.count(expected) != 1:
		raise ParseError("Keep reason must include original_stem exactly once.")
	return KeepResult(keep_original=keep, reason=reason, raw_text=text)


def parse_sort_response(text: str, expected_paths: list[str]) -> SortResult:
	response_body = extract_xml_tag_content(text, "response")
	if not response_body:
		raise ParseError("Missing <response> block in sort response.")
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
