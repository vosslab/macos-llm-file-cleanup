#!/usr/bin/env python3
"""
Backend-agnostic prompt builders.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass

# local repo modules
from .llm_utils import (
	ALLOWED_CATEGORIES,
	PROMPT_FILENAME_CHARS,
	_sanitize_prompt_list,
	_sanitize_prompt_text,
	_prompt_excerpt,
)

#============================================


@dataclass(slots=True)
class RenameRequest:
	metadata: dict
	current_name: str
	context: str | None = None


@dataclass(slots=True)
class KeepRequest:
	original_stem: str
	suggested_name: str
	features: dict[str, object]


@dataclass(slots=True)
class SortItem:
	path: str
	name: str
	ext: str
	description: str


@dataclass(slots=True)
class SortRequest:
	files: list[SortItem]
	context: str | None = None


RENAME_SCHEMA_XML = (
	"<new_name>NAME_WITH_EXTENSION</new_name>\n"
	"<reason>short reason (5-12 words)</reason>"
)
KEEP_SCHEMA_XML = (
	"<keep_original>true|false</keep_original>\n"
	"<reason>original_stem=\"...\" feature_flag=... short reason</reason>"
)
SORT_SCHEMA_XML = "<file path=\"/path/to/file.ext\">Category</file>"


def build_rename_prompt(req: RenameRequest) -> str:
	lines: list[str] = []
	if req.context:
		lines.append(f"Context: {req.context}")
	lines.append(
		f"Rename mode: create a concise, human-readable filename up to {PROMPT_FILENAME_CHARS} characters."
	)
	lines.append("Goal: the filename should make immediate sense to a person skimming a folder.")
	lines.append("Focus on purpose or type (form, invoice, receipt, contract, screenshot topic).")
	lines.append("Summarize instead of listing every visible word.")
	lines.append("Use 2-6 meaningful tokens; keep names short (1-2 names max).")
	lines.append("Avoid phone numbers, emails, or long numeric strings.")
	lines.append("Include a date only if clearly present and important (format YYYYMMDD).")
	lines.append("Include an ID only if it is a short labeled identifier.")
	lines.append("Avoid repeating tokens or echoing noisy original stems.")
	lines.append("Separate tokens with underscores or hyphens.")
	lines.append("Avoid filler adjectives like vibrant/beautiful.")
	lines.append("Return only the tags shown below. Do not include code fences.")
	lines.append("Do not wrap tags in any outer container.")
	lines.append(RENAME_SCHEMA_XML)
	title = _sanitize_prompt_text(req.metadata.get("title"), max_chars=200)
	keywords = _sanitize_prompt_list(req.metadata.get("keywords"))
	description = _sanitize_prompt_text(
		req.metadata.get("summary") or req.metadata.get("description"),
		max_chars=1200,
	)
	caption = _sanitize_prompt_text(req.metadata.get("caption"), max_chars=800)
	ocr_text = _sanitize_prompt_text(req.metadata.get("ocr_text"), max_chars=800)
	caption_note = _sanitize_prompt_text(req.metadata.get("caption_note"))
	filetype_hint = _sanitize_prompt_text(req.metadata.get("filetype_hint"))
	lines.append(f"current_name: {req.current_name}")
	if filetype_hint:
		lines.append(f"filetype: {filetype_hint}")
	if title:
		lines.append(f"title: {title}")
	if keywords:
		lines.append(f"keywords: {keywords}")
	if description:
		lines.append(f"description: {description}")
	if caption:
		lines.append(f"caption: {caption}")
	if ocr_text:
		lines.append(f"ocr_text: {ocr_text}")
	if caption_note:
		lines.append(f"caption_note: {caption_note}")
	lines.append(f"extension: {req.metadata.get('extension')}")
	return "\n".join(lines)


def build_rename_prompt_minimal(req: RenameRequest) -> str:
	lines: list[str] = []
	if req.context:
		lines.append(f"Context: {req.context}")
	lines.append(
		f"Rename mode: create a concise, human-readable filename up to {PROMPT_FILENAME_CHARS} characters."
	)
	lines.append("Goal: the filename should make immediate sense to a person skimming a folder.")
	lines.append("Summarize instead of listing every visible word.")
	lines.append("Use 2-6 meaningful tokens; keep names short (1-2 names max).")
	lines.append("Avoid phone numbers, emails, or long numeric strings.")
	lines.append("Include a date only if clearly present and important (format YYYYMMDD).")
	lines.append("Return only the tags shown below. Do not include code fences.")
	lines.append("Do not wrap tags in any outer container.")
	lines.append(RENAME_SCHEMA_XML)
	title = _sanitize_prompt_text(req.metadata.get("title"), max_chars=200)
	excerpt = _prompt_excerpt(req.metadata)
	filetype_hint = _sanitize_prompt_text(req.metadata.get("filetype_hint"))
	lines.append(f"current_name: {req.current_name}")
	if filetype_hint:
		lines.append(f"filetype: {filetype_hint}")
	if title:
		lines.append(f"title: {title}")
	if excerpt:
		lines.append(f"excerpt: {excerpt}")
	lines.append(f"extension: {req.metadata.get('extension')}")
	return "\n".join(lines)


def build_keep_prompt(req: KeepRequest) -> str:
	lines: list[str] = []
	lines.append("You are a strict classifier for whether to keep an original filename stem.")
	lines.append("Use only original_stem and the computed feature flags below. Do not re-derive features.")
	lines.append("Apply the rules in order and stop at the first match.")
	lines.append("Rule 1: If is_numeric_only=true or original_stem is empty -> keep_original=false.")
	lines.append("Rule 2: If generic_label=true and alpha_token_count <= 1 -> keep_original=false.")
	lines.append("Rule 3: If alpha_token_count >= 2 and generic_label=false -> keep_original=true.")
	lines.append(
		"Rule 4: If uuid_like=true OR hex_blob=true OR long_digit_run=true -> keep_original=false."
	)
	lines.append(
		"Rule 5: If digit_ratio > 0.6 AND alnum_length >= 10 -> keep_original=false."
	)
	lines.append(
		"Rule 6: Otherwise keep_original=true if has_letter=true AND "
		"(length <= 48 OR token_count <= 8) AND stem_in_suggested=false. Else false."
	)
	lines.append(
		f"Reason must include original_stem=\"{req.original_stem}\" exactly once."
	)
	lines.append("Do not repeat the schema text verbatim; populate real values.")
	lines.append("Reason must not mention rules or instructions.")
	lines.append("Return only the tags shown below. Do not include code fences.")
	lines.append("Do not wrap tags in any outer container.")
	lines.append(KEEP_SCHEMA_XML)
	lines.append(f"original_stem: {req.original_stem}")
	lines.append(f"suggested_name: {req.suggested_name}")
	lines.append("features:")
	for key, value in req.features.items():
		lines.append(f"- {key}: {value}")
	return "\n".join(lines)


def build_sort_prompt(req: SortRequest) -> str:
	lines: list[str] = []
	if req.context:
		lines.append(f"Context: {req.context}")
	lines.append("Sorting mode: assign an allowed category to each file path.")
	lines.append("Allowed categories:")
	for cat in ALLOWED_CATEGORIES:
		lines.append(f"- {cat}")
	lines.append("Files:")
	for item in req.files:
		lines.append(
			f"path={item.path} | name={item.name} | ext={item.ext} | desc={item.description}"
		)
	lines.append("Return only the tags shown below. Do not include code fences.")
	lines.append("Do not wrap tags in any outer container.")
	lines.append(SORT_SCHEMA_XML)
	return "\n".join(lines)


def build_format_fix_prompt(original_prompt: str, schema_xml: str) -> str:
	lines = [
		"Your previous reply did not match the required tags.",
		"Output only the tags below with no extra text.",
		schema_xml,
		"",
		original_prompt,
	]
	return "\n".join(lines)
