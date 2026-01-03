#!/usr/bin/env python3
"""
Compatibility exports for LLM utilities and engine.
"""

from __future__ import annotations

from .llm_engine import LLMEngine
from .llm_parsers import KeepResult, RenameResult, SortResult, ParseError
from .llm_prompts import KeepRequest, RenameRequest, SortItem, SortRequest
from .llm_utils import (
	ALLOWED_CATEGORIES,
	MAX_FILENAME_CHARS,
	PROMPT_FILENAME_CHARS,
	MIN_MACOS_MAJOR,
	apple_models_available,
	compute_stem_features,
	extract_xml_tag_content,
	get_vram_size_in_gb as _get_vram_size_in_gb,
	total_ram_bytes as _total_ram_bytes,
	normalize_reason,
	pick_category,
	sanitize_filename,
)
from .transports.apple import AppleTransport
from .transports.ollama import OllamaTransport

def get_vram_size_in_gb() -> int | None:
	return _get_vram_size_in_gb()


def total_ram_bytes() -> int:
	return _total_ram_bytes()


def choose_model(model_override: str | None) -> str:
	"""
	Compatibility wrapper so tests can monkeypatch get_vram_size_in_gb/total_ram_bytes.
	"""
	from .llm_utils import choose_model as _choose_model

	original_vram = _get_vram_size_in_gb
	original_ram = _total_ram_bytes

	def _patched_vram() -> int | None:
		return get_vram_size_in_gb()

	def _patched_ram() -> int:
		return total_ram_bytes()

	try:
		globals_dict = _choose_model.__globals__
		globals_dict["get_vram_size_in_gb"] = _patched_vram
		globals_dict["total_ram_bytes"] = _patched_ram
		return _choose_model(model_override)
	finally:
		globals_dict = _choose_model.__globals__
		globals_dict["get_vram_size_in_gb"] = original_vram
		globals_dict["total_ram_bytes"] = original_ram


__all__ = [
	"LLMEngine",
	"KeepResult",
	"RenameResult",
	"SortResult",
	"ParseError",
	"KeepRequest",
	"RenameRequest",
	"SortItem",
	"SortRequest",
	"ALLOWED_CATEGORIES",
	"MAX_FILENAME_CHARS",
	"PROMPT_FILENAME_CHARS",
	"MIN_MACOS_MAJOR",
	"apple_models_available",
	"choose_model",
	"get_vram_size_in_gb",
	"total_ram_bytes",
	"compute_stem_features",
	"extract_xml_tag_content",
	"normalize_reason",
	"pick_category",
	"sanitize_filename",
	"AppleTransport",
	"OllamaTransport",
]
