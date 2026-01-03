#!/usr/bin/env python3
"""
Local LLM helpers for file renaming.
"""

# Standard Library
import json
import os
import random
import re
import subprocess
import time
import urllib.request
import platform
from dataclasses import dataclass
from pathlib import Path
import logging

#============================================


MAX_FILENAME_CHARS = 100
PROMPT_FILENAME_CHARS = 80
MIN_MACOS_MAJOR = 26
_PLACEHOLDER_REASONS = {
	"short justification",
	"short reason",
	"optional",
	"n/a",
	"na",
}
_NONPRINTABLE_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_PROMPT_MAX_TOKEN_LEN = 40
_PROMPT_EXCERPT_CHARS = 240

_UUID_RE = re.compile(
	r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
_HEX_BLOB_RE = re.compile(r"\b[0-9a-fA-F]{8,}\b")
_LONG_DIGIT_RUN_RE = re.compile(r"\d{8,}")
_TOKEN_SPLIT_RE = re.compile(r"[-_.\s]+")
_GENERIC_LABEL_RE = re.compile(
	r"^(img|dsc|scan|screenshot|document|download|file|image|photo|picture)[-_ .]*\d+$",
	re.IGNORECASE,
)

_GUARDRAIL_ERRORS: tuple[type[BaseException], ...] = ()
try:
	from applefoundationmodels.exceptions import GuardrailViolationError
	_GUARDRAIL_ERRORS = (GuardrailViolationError,)
except Exception:
	_GUARDRAIL_ERRORS = ()


def sanitize_filename(name: str) -> str:
	"""
	Sanitize filename for macOS.

	Args:
		name: Proposed filename without extension.

	Returns:
		Sanitized name under MAX_FILENAME_CHARS characters.
	"""
	allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-_"
	result_chars: list[str] = []
	for ch in name:
		if ch.isspace():
			result_chars.append("-")
		elif ch in allowed:
			result_chars.append(ch)
		else:
			result_chars.append("-")
	cleaned = "".join(result_chars)
	while "--" in cleaned:
		cleaned = cleaned.replace("--", "-")
	while "__" in cleaned:
		cleaned = cleaned.replace("__", "_")
	cleaned = cleaned.strip("-_.")
	if len(cleaned) > MAX_FILENAME_CHARS:
		cleaned = cleaned[:MAX_FILENAME_CHARS]
	return cleaned or "file"


#============================================

def normalize_reason(reason: str | None) -> str:
	"""
	Normalize trivial placeholder reasons to empty string.
	"""
	if not reason:
		return ""
	cleaned = " ".join(str(reason).split())
	lower = cleaned.lower().strip()
	plain = re.sub(r"[^a-z0-9 ]+", "", lower).strip()
	if lower in _PLACEHOLDER_REASONS or plain in _PLACEHOLDER_REASONS:
		return ""
	if "short justification" in lower or "short reason" in lower:
		return ""
	if "justification" in lower and len(lower.split()) <= 3:
		return ""
	return cleaned


#============================================

def _sanitize_prompt_text(value: object, max_token_len: int = _PROMPT_MAX_TOKEN_LEN) -> str:
	if value is None:
		return ""
	text = str(value)
	if not text:
		return ""
	text = text.replace("\r\n", "\n").replace("\r", "\n")
	text = _NONPRINTABLE_RE.sub(" ", text)
	text = text.replace("\t", " ")
	lines: list[str] = []
	seen: set[str] = set()
	for raw in text.splitlines():
		compact = " ".join(raw.split())
		if not compact:
			continue
		tokens = [token for token in compact.split(" ") if len(token) <= max_token_len]
		if not tokens:
			continue
		line = " ".join(tokens)
		key = line.lower()
		if key in seen:
			continue
		seen.add(key)
		lines.append(line)
	return "\n".join(lines)


def _sanitize_prompt_list(value: object) -> list[str]:
	if value is None:
		return []
	if isinstance(value, (list, tuple, set)):
		cleaned: list[str] = []
		for item in value:
			text = _sanitize_prompt_text(item)
			if text:
				cleaned.append(text)
		return cleaned
	text = _sanitize_prompt_text(value)
	return [text] if text else []


#============================================

def _prompt_excerpt(metadata: dict) -> str:
	for key in ("summary", "description", "caption", "ocr_text"):
		text = _sanitize_prompt_text(metadata.get(key))
		if text:
			if len(text) > _PROMPT_EXCERPT_CHARS:
				return text[: _PROMPT_EXCERPT_CHARS - 3].rstrip() + "..."
			return text
	return ""


#============================================

def compute_stem_features(original_stem: str, suggested_name: str) -> dict[str, object]:
	"""
	Compute deterministic features for keep-original decisions.
	"""
	stem = original_stem.strip()
	alnum = re.sub(r"[^A-Za-z0-9]", "", stem)
	alnum_length = len(alnum)
	digits = sum(ch.isdigit() for ch in alnum)
	letters = sum(ch.isalpha() for ch in alnum)
	digit_ratio = digits / max(1, alnum_length)
	tokens = [t for t in _TOKEN_SPLIT_RE.split(stem) if t]
	alpha_token_count = sum(1 for t in tokens if any(ch.isalpha() for ch in t))
	token_count = len(tokens)
	has_letter = letters > 0
	is_numeric_only = bool(stem) and stem.isdigit()
	long_digit_run = bool(_LONG_DIGIT_RUN_RE.search(stem))
	uuid_like = bool(_UUID_RE.match(stem))
	hex_blob = bool(_HEX_BLOB_RE.search(stem))
	generic_label = bool(_GENERIC_LABEL_RE.match(stem))
	stem_in_suggested = stem.lower() in suggested_name.lower() if stem and suggested_name else False
	return {
		"has_letter": has_letter,
		"alpha_token_count": alpha_token_count,
		"token_count": token_count,
		"is_numeric_only": is_numeric_only,
		"long_digit_run": long_digit_run,
		"digit_ratio": round(digit_ratio, 3),
		"uuid_like": uuid_like,
		"hex_blob": hex_blob,
		"generic_label": generic_label,
		"length": len(stem),
		"alnum_length": alnum_length,
		"stem_in_suggested": stem_in_suggested,
	}


#============================================

def _is_guardrail_error(exc: Exception) -> bool:
	if _GUARDRAIL_ERRORS and isinstance(exc, _GUARDRAIL_ERRORS):
		return True
	name = exc.__class__.__name__.lower()
	if "guardrail" in name:
		return True
	msg = str(exc).lower()
	return "guardrail" in msg and "unsafe" in msg


#============================================

def _next_guardrail_dump_path() -> Path:
	repo_root = Path(__file__).resolve().parents[1]
	pattern = re.compile(r"GuardrailViolationError_(\d+)\.txt$")
	max_num = 0
	for path in repo_root.glob("GuardrailViolationError_*.txt"):
		match = pattern.match(path.name)
		if not match:
			continue
		try:
			max_num = max(max_num, int(match.group(1)))
		except ValueError:
			continue
	next_num = max_num + 1
	return repo_root / f"GuardrailViolationError_{next_num:02d}.txt"


def _dump_guardrail_prompt(prompt: str) -> Path | None:
	if not prompt:
		return None
	path = _next_guardrail_dump_path()
	try:
		path.write_text(prompt, encoding="utf-8")
	except Exception:
		return None
	return path


#============================================

ALLOWED_CATEGORIES: list[str] = [
	"Document",
	"Spreadsheet",
	"Presentation",
	"Image",
	"Audio",
	"Video",
	"Code",
	"Data",
	"Project",
	"Other",
]


def pick_category(extension: str) -> str:
	"""
	Choose simple category from extension (broad buckets).

	Args:
		extension: File extension without dot.

	Returns:
		Category string.
	"""
	ext = extension.lower()
	if ext in {"pdf", "doc", "docx", "odt", "rtf", "pages", "txt", "md"}:
		return "Document"
	if ext in {"ppt", "pptx", "odp"}:
		return "Presentation"
	if ext in {"xls", "xlsx", "ods", "csv", "tsv"}:
		return "Data"
	if ext in {"png", "jpg", "jpeg", "heic", "gif", "tif", "tiff", "bmp", "svg", "svgz"}:
		return "Image"
	if ext in {"mp3", "wav", "flac", "aiff", "ogg"}:
		return "Audio"
	if ext in {"mp4", "mov", "mkv", "webm", "avi"}:
		return "Video"
	if ext in {"py", "m", "cpp", "js", "sh", "pl", "rb", "php"}:
		return "Code"
	return "Other"


#============================================


def extract_xml_tag_content(raw_text: str, tag: str) -> str:
	"""
	Extract the last occurrence of a given XML-like tag.
	"""
	if not raw_text:
		return ""
	lower = raw_text.lower()
	open_token = f"<{tag}"
	close_token = f"</{tag}"
	start_idx = lower.rfind(open_token)
	if start_idx == -1:
		return ""
	gt_idx = raw_text.find(">", start_idx)
	if gt_idx == -1:
		return ""
	close_idx = lower.find(close_token, gt_idx + 1)
	if close_idx == -1:
		content = raw_text[gt_idx + 1 :]
		return content.strip()
	content = raw_text[gt_idx + 1 : close_idx]
	return content.strip()


def _parse_macos_version() -> tuple[int, int, int]:
	version_str = platform.mac_ver()[0]
	parts = [int(p) for p in version_str.split(".") if p.isdigit()]
	while len(parts) < 3:
		parts.append(0)
	if len(parts) >= 3:
		return parts[0], parts[1], parts[2]
	return 0, 0, 0


def apple_models_available() -> bool:
	try:
		from applefoundationmodels import Session, apple_intelligence_available
	except Exception:
		return False
	arch = platform.machine().lower()
	if arch != "arm64":
		return False
	major, _minor, _patch = _parse_macos_version()
	if major < MIN_MACOS_MAJOR:
		return False
	try:
		if not apple_intelligence_available():
			return False
	except Exception:
		return False
	_ = Session
	return True


#============================================


def total_ram_bytes() -> int:
	"""
	Estimate total system memory.

	Returns:
		Bytes of RAM.
	"""
	pages = 0
	page_size = 0
	if hasattr(os, "sysconf"):
		if "SC_PHYS_PAGES" in os.sysconf_names:
			pages = int(os.sysconf("SC_PHYS_PAGES"))
		if "SC_PAGE_SIZE" in os.sysconf_names:
			page_size = int(os.sysconf("SC_PAGE_SIZE"))
	if pages and page_size:
		value = pages * page_size
		return value
	return 0


#============================================


def get_vram_size_in_gb() -> int | None:
	"""
	Detect VRAM or unified memory size in GB.
	"""
	try:
		arch = subprocess.check_output(["uname", "-m"], text=True).strip()
		is_apple_silicon = arch.startswith("arm64")
		if is_apple_silicon:
			hardware_info = subprocess.check_output(
				["system_profiler", "SPHardwareDataType"], text=True
			)
			match = re.search(r"Memory:\\s(\\d+)\\s?GB", hardware_info)
			if match:
				return int(match.group(1))
		else:
			display_info = subprocess.check_output(
				["system_profiler", "SPDisplaysDataType"], text=True
			)
			vram_match = re.search(r"VRAM.*?: (\\d+)\\s?MB", display_info)
			if vram_match:
				vram_mb = int(vram_match.group(1))
				return vram_mb // 1024
	except Exception:
		return None
	return None


#============================================


def choose_model(model_override: str | None) -> str:
	"""
	Pick an Ollama model based on RAM or override.

	Args:
		model_override: User provided model name.

	Returns:
		Model name string.
	"""
	if model_override:
		return model_override
	vram_gb = get_vram_size_in_gb()
	if vram_gb is not None:
		if vram_gb > 30:
			return "gpt-oss:20b"
		if vram_gb > 14:
			return "phi4:14b-q4_K_M"
		if vram_gb > 4:
			return "llama3.2:3b-instruct-q5_K_M"
		return "llama3.2:1b-instruct-q4_K_M"
	ram = total_ram_bytes()
	if ram and ram > 30 * 1024 * 1024 * 1024:
		return "gpt-oss:20b"
	if ram and ram > 14 * 1024 * 1024 * 1024:
		return "phi4:14b-q4_K_M"
	if ram and ram > 4 * 1024 * 1024 * 1024:
		return "llama3.2:3b-instruct-q5_K_M"
	return "llama3.2:1b-instruct-q4_K_M"


#============================================


@dataclass(slots=True)
class BaseClassLLM:
	"""
	Base local LLM interface.
	"""

	model: str

	#============================================
	def suggest_name_and_category(
		self, metadata: dict, current_name: str
	) -> tuple[str, str]:
		"""
		Provide a suggested name and category.

		Args:
			metadata: Metadata dictionary.
			current_name: Current filename.

		Returns:
			Tuple of (name, category).
		"""
		raise NotImplementedError

	#============================================
	def rename_file(self, metadata: dict, current_name: str) -> str:
		"""
		Suggest a descriptive filename (no path).
		"""
		raise NotImplementedError

	#============================================
	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		"""
		Suggest a descriptive filename plus a short reason.
		"""
		raise NotImplementedError

	#============================================
	def rename_with_keep(self, metadata: dict, current_name: str) -> tuple[str, bool]:
		"""
		Return (new_name, keep_original) from rename mode.
		"""
		raise NotImplementedError

	#============================================
	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		"""
		Decide whether original filename stem is worth keeping, plus a short reason.
		"""
		raise NotImplementedError

	#============================================
	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		"""
		Assign categories for a batch of file summaries.
		"""
		raise NotImplementedError

	#============================================
	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		"""
		Assign categories plus a per-file reason.
		"""
		raise NotImplementedError


#============================================

class FallbackLLM(BaseClassLLM):
	"""
	Primary LLM with a fallback for guardrail violations.
	"""

	def __init__(self, primary: BaseClassLLM, fallback: BaseClassLLM) -> None:
		self.primary = primary
		self.fallback = fallback

	def _with_fallback(self, primary_fn, fallback_fn):
		try:
			return primary_fn()
		except Exception as exc:
			if _is_guardrail_error(exc):
				logging.warning("Apple guardrail triggered; falling back to Ollama.")
				return fallback_fn()
			raise

	def suggest_name_and_category(
		self, metadata: dict, current_name: str
	) -> tuple[str, str]:
		return self._with_fallback(
			lambda: self.primary.suggest_name_and_category(metadata, current_name),
			lambda: self.fallback.suggest_name_and_category(metadata, current_name),
		)

	def rename_file(self, metadata: dict, current_name: str) -> str:
		return self._with_fallback(
			lambda: self.primary.rename_file(metadata, current_name),
			lambda: self.fallback.rename_file(metadata, current_name),
		)

	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		return self._with_fallback(
			lambda: self.primary.rename_file_explain(metadata, current_name),
			lambda: self.fallback.rename_file_explain(metadata, current_name),
		)

	def rename_with_keep(self, metadata: dict, current_name: str) -> tuple[str, bool]:
		return self._with_fallback(
			lambda: self.primary.rename_with_keep(metadata, current_name),
			lambda: self.fallback.rename_with_keep(metadata, current_name),
		)

	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		return self._with_fallback(
			lambda: self.primary.should_keep_original_explain(metadata, current_name, new_name),
			lambda: self.fallback.should_keep_original_explain(metadata, current_name, new_name),
		)

	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		return self._with_fallback(
			lambda: self.primary.assign_categories(summaries),
			lambda: self.fallback.assign_categories(summaries),
		)

	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		return self._with_fallback(
			lambda: self.primary.assign_categories_explain(summaries),
			lambda: self.fallback.assign_categories_explain(summaries),
		)


#============================================


class AppleLLM(BaseClassLLM):
	"""
	Apple Foundation Models backend for local macOS LLM usage.
	"""

	#============================================
	def __init__(self, model: str, system_message: str = "") -> None:
		self.model = model
		self.system_message = system_message.strip()

	#============================================
	def _require_apple_intelligence(self) -> None:
		try:
			from applefoundationmodels import Session, apple_intelligence_available
		except Exception as exc:
			raise RuntimeError("apple-foundation-models is required for the Apple backend.") from exc
		arch = platform.machine().lower()
		if arch != "arm64":
			raise RuntimeError("Apple Intelligence requires Apple Silicon (arm64).")
		major, minor, patch = _parse_macos_version()
		if major < MIN_MACOS_MAJOR:
			raise RuntimeError(
				f"macOS {MIN_MACOS_MAJOR}.0+ is required (detected {major}.{minor}.{patch})."
			)
		if not apple_intelligence_available():
			try:
				reason = Session.get_availability_reason()
			except Exception:
				reason = "Apple Intelligence not available or not enabled."
			raise RuntimeError(str(reason))

	#============================================
	def _ask(self, prompt: str, max_tokens: int = 200) -> str:
		self._require_apple_intelligence()
		from applefoundationmodels import Session
		try:
			with Session(
				instructions=(
					"You generate concise, structured answers for file renaming. "
					"Return only the XML requested by the prompt."
				)
			) as session:
				response = session.generate(prompt, max_tokens=max_tokens, temperature=0.2)
			return response.text.strip()
		except Exception as exc:
			if _is_guardrail_error(exc):
				dump_path = _dump_guardrail_prompt(prompt)
				if dump_path:
					logging.warning("GuardrailViolationError: prompt saved to %s", dump_path)
			raise

	#============================================
	def suggest_name_and_category(
		self, metadata: dict, current_name: str
	) -> tuple[str, str]:
		name = self.rename_file(metadata, current_name)
		cats = self.assign_categories(
			[
				{
					"index": 0,
					"name": name,
					"ext": metadata.get("extension", ""),
					"description": metadata.get("summary") or metadata.get("description") or "",
				}
			]
		)
		return (name, cats.get(0, "Other"))

	#============================================
	def rename_file(self, metadata: dict, current_name: str) -> str:
		name, _reason = self.rename_file_explain(metadata, current_name)
		return name

	#============================================
	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		prompt = self._build_rename_prompt(metadata, current_name)
		try:
			response_text = self._ask(prompt, max_tokens=200)
		except Exception as exc:
			if _is_guardrail_error(exc):
				retry_prompt = self._build_rename_prompt_minimal(metadata, current_name)
				response_text = self._ask(retry_prompt, max_tokens=160)
			else:
				raise
		return self._parse_rename_response_explain(response_text, current_name)

	#============================================
	def rename_with_keep(self, metadata: dict, current_name: str) -> tuple[str, bool]:
		new_name = self.rename_file(metadata, current_name)
		keep, _reason = self.should_keep_original_explain(metadata, current_name, new_name)
		return (new_name, keep)

	#============================================
	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		prompt = self._build_keep_prompt(metadata, current_name, new_name)
		response_text = self._ask(prompt, max_tokens=120)
		return self._parse_keep_response_explain(response_text)

	#============================================
	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		mapping, _reasons = self.assign_categories_explain(summaries)
		return mapping

	#============================================
	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		if not summaries:
			return ({}, {})
		prompt = self._build_sort_prompt(summaries)
		response_text = self._ask(prompt, max_tokens=240)
		expected = [int(item["index"]) for item in summaries]
		return self._parse_sort_response_explain(response_text, expected)

	#============================================
	def _build_rename_prompt(self, metadata: dict, current_name: str) -> str:
		lines: list[str] = []
		if self.system_message:
			lines.append(f"Context: {self.system_message}")
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
		lines.append("When in doubt, choose the shorter, more general filename.")
		lines.append("When in doubt, choose the shorter, more general filename.")
		lines.append("Return XML only with minimal chatter. Use exactly:")
		lines.append("<response>")
		lines.append("  <new_name>NAME_WITH_EXTENSION</new_name>")
		lines.append("  <reason>short reason (5-12 words)</reason>")
		lines.append("</response>")
		title = _sanitize_prompt_text(metadata.get("title"))
		keywords = _sanitize_prompt_list(metadata.get("keywords"))
		description = _sanitize_prompt_text(metadata.get("summary") or metadata.get("description"))
		caption = _sanitize_prompt_text(metadata.get("caption"))
		ocr_text = _sanitize_prompt_text(metadata.get("ocr_text"))
		caption_note = _sanitize_prompt_text(metadata.get("caption_note"))
		lines.append(f"current_name: {current_name}")
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
		lines.append(f"extension: {metadata.get('extension')}")
		return "\n".join(lines)

	#============================================
	def _build_rename_prompt_minimal(self, metadata: dict, current_name: str) -> str:
		lines: list[str] = []
		if self.system_message:
			lines.append(f"Context: {self.system_message}")
		lines.append(
			f"Rename mode: create a concise, human-readable filename up to {PROMPT_FILENAME_CHARS} characters."
		)
		lines.append("Goal: the filename should make immediate sense to a person skimming a folder.")
		lines.append("Summarize instead of listing every visible word.")
		lines.append("Use 2-6 meaningful tokens; keep names short (1-2 names max).")
		lines.append("Avoid phone numbers, emails, or long numeric strings.")
		lines.append("Include a date only if clearly present and important (format YYYYMMDD).")
		lines.append("Return XML only with minimal chatter. Use exactly:")
		lines.append("<response>")
		lines.append("  <new_name>NAME_WITH_EXTENSION</new_name>")
		lines.append("  <reason>short reason (5-12 words)</reason>")
		lines.append("</response>")
		title = _sanitize_prompt_text(metadata.get("title"))
		excerpt = _prompt_excerpt(metadata)
		lines.append(f"current_name: {current_name}")
		if title:
			lines.append(f"title: {title}")
		if excerpt:
			lines.append(f"excerpt: {excerpt}")
		lines.append(f"extension: {metadata.get('extension')}")
		return "\n".join(lines)

	#============================================
	def _build_keep_prompt(self, metadata: dict, current_name: str, new_name: str) -> str:
		lines: list[str] = []
		if self.system_message:
			lines.append(f"Context: {self.system_message}")
		lines.append("You are a strict classifier for whether to keep an original filename stem.")
		lines.append("Use only original_stem and the computed feature flags below. Do not re-derive features.")
		lines.append("Apply the rules in order and stop at the first match.")
		lines.append("Rule 1: If is_numeric_only=true or original_stem is empty -> keep_original=false.")
		lines.append(
			"Rule 2: If generic_label=true and alpha_token_count <= 1 -> keep_original=false."
		)
		lines.append(
			"Rule 3: If alpha_token_count >= 2 and generic_label=false -> keep_original=true."
		)
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
		lines.append("Return XML only with minimal chatter. Use exactly:")
		lines.append("<response>")
		lines.append("  <keep_original>true</keep_original>")
		lines.append("  <reason>One sentence. Refer to one feature flag.</reason>")
		lines.append("</response>")
		original_stem = Path(current_name).stem
		features = compute_stem_features(original_stem, new_name)
		lines.append(f"original_stem: {original_stem}")
		lines.append(f"suggested_name: {new_name}")
		lines.append("features:")
		for key, value in features.items():
			lines.append(f"- {key}: {value}")
		return "\n".join(lines)

	#============================================
	def _build_sort_prompt(self, summaries: list[dict]) -> str:
		lines: list[str] = []
		if self.system_message:
			lines.append(f"Context: {self.system_message}")
		lines.append("Sorting mode: assign an allowed category to each file index.")
		lines.append("Allowed categories:")
		for cat in ALLOWED_CATEGORIES:
			lines.append(f"- {cat}")
		lines.append("Files:")
		for item in summaries:
			lines.append(
				f"file_{item['index']}: name={item['name']}, ext={item.get('ext')}, desc={item.get('description')}"
			)
		lines.append("Return XML only with minimal chatter. Use exactly:")
		lines.append("<response>")
		lines.append("  <file index=\"N\">")
		lines.append("    <category>Document</category>")
		lines.append("    <reason>optional</reason>")
		lines.append("  </file>")
		lines.append("</response>")
		return "\n".join(lines)

	#============================================
	def _parse_rename_response_explain(
		self, response_text: str, current_name: str
	) -> tuple[str, str]:
		response_body = extract_xml_tag_content(response_text, "response")
		if response_body:
			new_name = extract_xml_tag_content(response_body, "new_name") or current_name
			reason = normalize_reason(extract_xml_tag_content(response_body, "reason"))
			return (sanitize_filename(new_name), reason)
		return (sanitize_filename(current_name), "")

	#============================================
	def _parse_keep_response_explain(self, response_text: str) -> tuple[bool, str]:
		response_body = extract_xml_tag_content(response_text, "response")
		if response_body:
			keep_text = extract_xml_tag_content(response_body, "keep_original").strip().lower()
			keep = keep_text.startswith("t") or keep_text == "1" or keep_text == "yes"
			reason = normalize_reason(extract_xml_tag_content(response_body, "reason"))
			return (keep, reason)
		return (True, "")

	#============================================
	def _parse_sort_response_explain(
		self, response_text: str, expected_indices: list[int]
	) -> tuple[dict[int, str], dict[int, str]]:
		response_body = extract_xml_tag_content(response_text, "response")
		if response_body:
			mapping: dict[int, str] = {}
			reasons: dict[int, str] = {}
			for match in re.finditer(
				r"<file\b[^>]*\bindex\s*=\s*[\"'](\d+)[\"'][^>]*>(.*?)</file>",
				response_body,
				flags=re.IGNORECASE | re.DOTALL,
			):
				try:
					idx = int(match.group(1))
				except ValueError:
					continue
				body = match.group(2)
				category_text = extract_xml_tag_content(body, "category")
				reason_text = normalize_reason(extract_xml_tag_content(body, "reason"))
				mapping[idx] = self._normalize_category(category_text)
				if reason_text:
					reasons[idx] = reason_text
			for idx in expected_indices:
				if idx not in mapping:
					mapping[idx] = "Other"
			return (mapping, reasons)
		mapping: dict[int, str] = {}
		reasons: dict[int, str] = {}
		for idx in expected_indices:
			mapping[idx] = "Other"
		return (mapping, reasons)

	#============================================
	def _normalize_category(self, value: str) -> str:
		if not value:
			return "Other"
		val = value.strip().lower()
		for cat in ALLOWED_CATEGORIES:
			if val == cat.lower():
				return cat
			if val.startswith(cat.lower() + " "):
				return cat
			if val.startswith(cat.lower() + "("):
				return cat
			if val.startswith(cat.lower() + "-"):
				return cat
		aliases = {
			"doc": "Document",
			"docs": "Document",
			"spreadsheet": "Spreadsheet",
			"sheet": "Spreadsheet",
			"image": "Image",
			"img": "Image",
			"audio": "Audio",
			"video": "Video",
			"code": "Code",
			"data": "Data",
			"project": "Project",
		}
		if val in aliases:
			return aliases[val]
		return "Other"


#============================================


class OllamaChatLLM(BaseClassLLM):
	"""
	Ollama-backed chat client that keeps a local message history.
	"""

	#============================================
	def __init__(
		self, model: str, base_url: str = "http://localhost:11434", system_message: str = ""
	) -> None:
		self.model = model
		self.base_url = base_url.rstrip("/")
		self.messages: list[dict[str, str]] = []
		if system_message:
			self.add_system_message(system_message)

	#============================================
	def add_system_message(self, content: str) -> None:
		"""
		Append a system directive to the chat history.
		"""
		self.messages.append({"role": "system", "content": content})

	#============================================
	def ask(self, user_content: str) -> str:
		"""
		Send a chat message to Ollama and persist history.

		Args:
			user_content: Prompt to send as user role.

		Returns:
			Assistant message content.
		"""
		self.messages.append({"role": "user", "content": user_content})
		payload = {
			"model": self.model,
			"messages": self.messages,
			"stream": False,
		}
		time.sleep(random.random())
		request = urllib.request.Request(
			f"{self.base_url}/api/chat",
			data=json.dumps(payload).encode("utf-8"),
			headers={"Content-Type": "application/json"},
			method="POST",
		)
		with urllib.request.urlopen(request, timeout=30) as response:
			if response.status >= 400:
				raise RuntimeError(f"Ollama chat error: status {response.status}")
			response_body = response.read()
		parsed = json.loads(response_body.decode("utf-8"))
		assistant_message = parsed.get("message", {}).get("content", "")
		if not assistant_message:
			raise RuntimeError("Ollama chat returned empty content")
		self.messages.append({"role": "assistant", "content": assistant_message})
		return assistant_message

	#============================================
	def suggest_name_and_category(
		self, metadata: dict, current_name: str
	) -> tuple[str, str]:
		"""
		Query Ollama chat for rename suggestion.

		Args:
			metadata: Metadata dictionary.
			current_name: Current filename.

		Returns:
			Name and category tuple.
		"""
		prompt = self._build_prompt(metadata, current_name)
		response_text = self.ask(prompt)
		name, category = self._parse_response_text(
			response_text, metadata, current_name
		)
		result: tuple[str, str] = (name, category)
		return result

	#============================================
	def rename_with_keep(self, metadata: dict, current_name: str) -> tuple[str, bool]:
		"""
		Rename mode with keep_original decision.
		"""
		new_name = self.rename_file(metadata, current_name)
		keep = self.should_keep_original(metadata, current_name, new_name)
		return (new_name, keep)

	#============================================
	def should_keep_original(self, metadata: dict, current_name: str, new_name: str) -> bool:
		"""
		LLM decision on whether original filename is meaningful.
		"""
		prompt = self._build_keep_prompt(metadata, current_name, new_name)
		response_text = self.ask(prompt)
		return self._parse_keep_response(response_text)

	#============================================
	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		prompt = self._build_keep_prompt(metadata, current_name, new_name)
		response_text = self.ask(prompt)
		return self._parse_keep_response_explain(response_text)

	#============================================
	def rename_file(self, metadata: dict, current_name: str) -> str:
		"""
		Rename mode: descriptive filename only.
		"""
		prompt = self._build_rename_prompt(metadata, current_name)
		response_text = self.ask(prompt)
		return self._parse_rename_response(response_text, current_name)

	#============================================
	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		prompt = self._build_rename_prompt(metadata, current_name)
		response_text = self.ask(prompt)
		return self._parse_rename_response_explain(response_text, current_name)

	#============================================
	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		"""
		Sorting mode: batch category assignment constrained to ALLOWED_CATEGORIES.
		"""
		if not summaries:
			return {}
		prompt = self._build_sort_prompt(summaries)
		response_text = self.ask(prompt)
		expected = [int(item["index"]) for item in summaries]
		return self._parse_sort_response(response_text, expected)

	#============================================
	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		if not summaries:
			return ({}, {})
		prompt = self._build_sort_prompt(summaries)
		response_text = self.ask(prompt)
		expected = [int(item["index"]) for item in summaries]
		return self._parse_sort_response_explain(response_text, expected)

	#============================================
	def _build_prompt(self, metadata: dict, current_name: str) -> str:
		"""
		Construct prompt for Ollama chat.

		Args:
			metadata: Metadata dictionary.
			current_name: Current filename.

		Returns:
			Prompt string.
		"""
		lines: list[str] = []
		lines.append("Suggest a descriptive macOS-safe filename and category.")
		lines.append("Prefer keeping key subject terms; be concise but clear.")
		lines.append("Use this format on separate lines:")
		lines.append("new_name: <file name without path>")
		lines.append("category: <short category or empty>")
		lines.append(f"current_name: {current_name}")
		lines.append(f"metadata: {metadata}")
		prompt = "\n".join(lines)
		return prompt

	#============================================
	def _build_rename_prompt(self, metadata: dict, current_name: str) -> str:
		lines: list[str] = []
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
		lines.append("Return XML only with minimal chatter. Use exactly:")
		lines.append("<response>")
		lines.append("  <new_name>NAME_WITH_EXTENSION</new_name>")
		lines.append("  <reason>short reason (5-12 words)</reason>")
		lines.append("</response>")
		title = _sanitize_prompt_text(metadata.get("title"))
		keywords = _sanitize_prompt_list(metadata.get("keywords"))
		description = _sanitize_prompt_text(metadata.get("summary") or metadata.get("description"))
		caption = _sanitize_prompt_text(metadata.get("caption"))
		ocr_text = _sanitize_prompt_text(metadata.get("ocr_text"))
		caption_note = _sanitize_prompt_text(metadata.get("caption_note"))
		lines.append(f"current_name: {current_name}")
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
		lines.append(f"extension: {metadata.get('extension')}")
		return "\n".join(lines)

	#============================================
	def _parse_response_text(
		self, response_text: str, metadata: dict, current_name: str
	) -> tuple[str, str]:
		"""
		Parse plain-text response for name and category fields.

		Args:
			response_text: Assistant reply.
			metadata: Metadata dictionary.
			current_name: Current filename.

		Returns:
			Tuple of (name, category).
		"""
		new_name = current_name
		category = ""
		for line in response_text.splitlines():
			trimmed = line.strip()
			if trimmed.lower().startswith("new_name:"):
				value = trimmed.split(":", 1)[1].strip()
				if value:
					new_name = value
			if trimmed.lower().startswith("category:"):
				value = trimmed.split(":", 1)[1].strip()
				category = value
		if not new_name:
			new_name = current_name
		if not category:
			category = pick_category(metadata.get("extension", ""))
		new_name = sanitize_filename(new_name)
		category = sanitize_filename(category)
		return (new_name, category)

	#============================================
	def _parse_rename_response(self, response_text: str, current_name: str) -> str:
		new_name = current_name
		for line in response_text.splitlines():
			trimmed = line.strip()
			if trimmed.lower().startswith("new_name:"):
				value = trimmed.split(":", 1)[1].strip()
				if value:
					new_name = value
		return sanitize_filename(new_name)

	#============================================
	def _parse_rename_response_explain(
		self, response_text: str, current_name: str
	) -> tuple[str, str]:
		response_body = extract_xml_tag_content(response_text, "response")
		if response_body:
			new_name = extract_xml_tag_content(response_body, "new_name") or current_name
			reason = normalize_reason(extract_xml_tag_content(response_body, "reason"))
			return (sanitize_filename(new_name), reason)
		new_name = self._parse_rename_response(response_text, current_name)
		reason = ""
		for line in response_text.splitlines():
			trimmed = line.strip()
			if trimmed.lower().startswith("reason:"):
				reason = normalize_reason(trimmed.split(":", 1)[1].strip())
				break
		return (new_name, reason)

	#============================================
	def _build_keep_prompt(self, metadata: dict, current_name: str, new_name: str) -> str:
		lines: list[str] = []
		lines.append("You are a strict classifier for whether to keep an original filename stem.")
		lines.append("Use only original_stem and the computed feature flags below. Do not re-derive features.")
		lines.append("Apply the rules in order and stop at the first match.")
		lines.append("Rule 1: If is_numeric_only=true or original_stem is empty -> keep_original=false.")
		lines.append(
			"Rule 2: If generic_label=true and alpha_token_count <= 1 -> keep_original=false."
		)
		lines.append(
			"Rule 3: If alpha_token_count >= 2 and generic_label=false -> keep_original=true."
		)
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
		lines.append("Return XML only with minimal chatter. Use exactly:")
		lines.append("<response>")
		lines.append("  <keep_original>true</keep_original>")
		lines.append("  <reason>One sentence. Refer to one feature flag.</reason>")
		lines.append("</response>")
		original_stem = Path(current_name).stem
		features = compute_stem_features(original_stem, new_name)
		lines.append(f"original_stem: {original_stem}")
		lines.append(f"suggested_name: {new_name}")
		lines.append("features:")
		for key, value in features.items():
			lines.append(f"- {key}: {value}")
		return "\n".join(lines)

	#============================================
	def _parse_keep_response(self, response_text: str) -> bool:
		for line in response_text.splitlines():
			trimmed = line.strip().lower()
			if trimmed.startswith("keep_original:"):
				val = trimmed.split(":", 1)[1].strip()
				if val.startswith("t"):
					return True
				if val.startswith("f"):
					return False
		return True

	#============================================
	def _parse_keep_response_explain(self, response_text: str) -> tuple[bool, str]:
		response_body = extract_xml_tag_content(response_text, "response")
		if response_body:
			keep_text = extract_xml_tag_content(response_body, "keep_original").strip().lower()
			keep = keep_text.startswith("t") or keep_text == "1" or keep_text == "yes"
			reason = normalize_reason(extract_xml_tag_content(response_body, "reason"))
			return (keep, reason)
		keep = self._parse_keep_response(response_text)
		reason = ""
		for line in response_text.splitlines():
			trimmed = line.strip()
			if trimmed.lower().startswith("reason:"):
				reason = normalize_reason(trimmed.split(":", 1)[1].strip())
				break
		return (keep, reason)

	#============================================
	def _build_sort_prompt(self, summaries: list[dict]) -> str:
		lines: list[str] = []
		lines.append("Sorting mode: assign an allowed category to each file index.")
		lines.append("Allowed categories:")
		for cat in ALLOWED_CATEGORIES:
			lines.append(f"- {cat}")
		lines.append("Files:")
		for item in summaries:
			lines.append(
				f"file_{item['index']}: name={item['name']}, ext={item.get('ext')}, desc={item.get('description')}"
			)
		lines.append("Return XML only with minimal chatter. Use exactly:")
		lines.append("<response>")
		lines.append("  <file index=\"N\">")
		lines.append("    <category>Document</category>")
		lines.append("    <reason>optional</reason>")
		lines.append("  </file>")
		lines.append("</response>")
		return "\n".join(lines)

	#============================================
	def _parse_sort_response(
		self, response_text: str, expected_indices: list[int]
	) -> dict[int, str]:
		mapping, _reasons = self._parse_sort_response_explain(response_text, expected_indices)
		return mapping

	#============================================
	def _parse_sort_response_explain(
		self, response_text: str, expected_indices: list[int]
	) -> tuple[dict[int, str], dict[int, str]]:
		response_body = extract_xml_tag_content(response_text, "response")
		if response_body:
			mapping: dict[int, str] = {}
			reasons: dict[int, str] = {}
			for match in re.finditer(
				r"<file\b[^>]*\bindex\s*=\s*[\"'](\d+)[\"'][^>]*>(.*?)</file>",
				response_body,
				flags=re.IGNORECASE | re.DOTALL,
			):
				try:
					idx = int(match.group(1))
				except ValueError:
					continue
				body = match.group(2)
				category_text = extract_xml_tag_content(body, "category")
				reason_text = normalize_reason(extract_xml_tag_content(body, "reason"))
				mapping[idx] = self._normalize_category(category_text)
				if reason_text:
					reasons[idx] = reason_text
			for idx in expected_indices:
				if idx not in mapping:
					mapping[idx] = "Other"
			return (mapping, reasons)
		mapping: dict[int, str] = {}
		reasons: dict[int, str] = {}
		for line in response_text.splitlines():
			trimmed = line.strip()
			if not trimmed.lower().startswith("file_"):
				continue
			try:
				left, right = trimmed.split(":", 1)
			except ValueError:
				continue
			index_str = left.replace("file_", "").strip()
			try:
				idx = int(index_str)
			except ValueError:
				continue
			raw = right.strip()
			category_text = raw
			reason_text = ""
			for sep in (" - ", " | ", "\t", "—", "–"):
				if sep in raw:
					category_text, reason_text = raw.split(sep, 1)
					category_text = category_text.strip()
					reason_text = reason_text.strip()
					break
			category = self._normalize_category(category_text)
			mapping[idx] = category
			if reason_text:
				reasons[idx] = reason_text
		for idx in expected_indices:
			if idx not in mapping:
				mapping[idx] = "Other"
		return (mapping, reasons)

	#============================================
	def _normalize_category(self, value: str) -> str:
		if not value:
			return "Other"
		val = value.strip().lower()
		for cat in ALLOWED_CATEGORIES:
			if val == cat.lower():
				return cat
			if val.startswith(cat.lower() + " "):
				return cat
			if val.startswith(cat.lower() + "("):
				return cat
			if val.startswith(cat.lower() + "-"):
				return cat
		aliases = {
			"doc": "Document",
			"docs": "Document",
			"spreadsheet": "Spreadsheet",
			"sheet": "Spreadsheet",
			"image": "Image",
			"img": "Image",
			"audio": "Audio",
			"video": "Video",
			"code": "Code",
			"data": "Data",
			"project": "Project",
		}
		if val in aliases:
			return aliases[val]
		return "Other"



#============================================
# Compatibility alias for existing code paths.
OllamaLLM = OllamaChatLLM
