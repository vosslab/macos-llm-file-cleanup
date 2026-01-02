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
from dataclasses import dataclass
from pathlib import Path

#============================================


def sanitize_filename(name: str) -> str:
	"""
	Sanitize filename for macOS.

	Args:
		name: Proposed filename without extension.

	Returns:
		Sanitized name under 80 characters.
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
	if len(cleaned) > 256:
		cleaned = cleaned[:256]
	return cleaned or "file"


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
		return "docs"
	if ext in {"ppt", "pptx", "odp"}:
		return "docs"
	if ext in {"xls", "xlsx", "ods", "csv", "tsv"}:
		return "data"
	if ext in {"png", "jpg", "jpeg", "heic", "gif", "tif", "tiff", "bmp", "svg", "svgz"}:
		return "images"
	if ext in {"mp3", "wav", "flac", "aiff", "ogg"}:
		return "audio"
	if ext in {"mp4", "mov", "mkv", "webm", "avi"}:
		return "video"
	if ext in {"py", "m", "cpp", "js", "sh", "pl", "rb", "php"}:
		return "code"
	return "other"


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
class LocalLLM:
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
		suggestion: tuple[str, str] = (current_name, "other")
		return suggestion

	#============================================
	def rename_file(self, metadata: dict, current_name: str) -> str:
		"""
		Suggest a descriptive filename (no path).
		"""
		name, _cat = self.suggest_name_and_category(metadata, current_name)
		return name

	#============================================
	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		"""
		Suggest a descriptive filename plus a short reason.
		"""
		return (self.rename_file(metadata, current_name), "")

	#============================================
	def rename_with_keep(self, metadata: dict, current_name: str) -> tuple[str, bool]:
		"""
		Return (new_name, keep_original) from rename mode.
		"""
		new_name = self.rename_file(metadata, current_name)
		return (new_name, True)

	#============================================
	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		"""
		Decide whether original filename stem is worth keeping, plus a short reason.
		"""
		return (True, "")

	#============================================
	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		"""
		Assign categories for a batch of file summaries.
		"""
		return {}

	#============================================
	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		"""
		Assign categories plus a per-file reason.
		"""
		return (self.assign_categories(summaries), {})


#============================================


class DummyLLM(LocalLLM):
	"""
	Simple fallback LLM without heuristics.
	"""

	#============================================
	def suggest_name_and_category(
		self, metadata: dict, current_name: str
	) -> tuple[str, str]:
		"""
		Deterministic fallback suggestion.

		Args:
			metadata: Metadata dictionary.
			current_name: Current filename.

		Returns:
			Name and category tuple.
		"""
		title = metadata.get("title", "")
		keywords = metadata.get("keywords", [])
		summary = metadata.get("summary", "")
		extension = metadata.get("extension", "")
		stem = Path(current_name).stem
		parts: list[str] = []
		if title:
			parts.append(str(title))
		if keywords:
			parts.append("-".join(str(k) for k in keywords[:2]))
		if summary:
			first_words = " ".join(summary.split()[:12])
			if first_words:
				parts.append(first_words)
		if not parts:
			parts.append(stem)
		name_core = "-".join(parts)
		name_core = sanitize_filename(name_core)
		category = pick_category(extension)
		if extension and not name_core.lower().endswith(f".{extension.lower()}"):
			new_name = f"{name_core}.{extension}"
		else:
			new_name = name_core
		result: tuple[str, str] = (new_name, category)
		return result

	#============================================
	def rename_file(self, metadata: dict, current_name: str) -> str:
		name, _cat = self.suggest_name_and_category(metadata, current_name)
		return name

	#============================================
	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		name, _cat = self.suggest_name_and_category(metadata, current_name)
		reason_parts: list[str] = []
		if metadata.get("title"):
			reason_parts.append("used title")
		if metadata.get("keywords"):
			reason_parts.append("used keywords")
		if metadata.get("summary") or metadata.get("description"):
			reason_parts.append("used summary")
		if not reason_parts:
			reason_parts.append("used original stem")
		return (name, "; ".join(reason_parts))

	#============================================
	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		stem = Path(current_name).stem
		lower = stem.lower()
		if re.fullmatch(r"[0-9a-f]{16,}", lower):
			return (False, "original looks like a hex hash")
		if re.fullmatch(
			r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", lower
		):
			return (False, "original looks like a UUID")
		if len(stem) >= 40 and re.fullmatch(r"[A-Za-z0-9_-]+", stem):
			return (False, "original is long and token-like")
		return (True, "original may contain useful context")

	#============================================
	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		mapping: dict[int, str] = {}
		for item in summaries:
			ext = item.get("ext", "").lower()
			category = pick_category(ext)
			if category == "docs":
				category = "Document"
			elif category == "data":
				category = "Data"
			elif category == "images":
				category = "Image"
			elif category == "audio":
				category = "Audio"
			elif category == "video":
				category = "Video"
			elif category == "code":
				category = "Code"
			else:
				category = "Other"
			mapping[item["index"]] = category
		return mapping

	#============================================
	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		mapping = self.assign_categories(summaries)
		reasons: dict[int, str] = {}
		for item in summaries:
			idx = item["index"]
			ext = item.get("ext", "")
			reasons[idx] = f"extension .{ext} bucket"
		return (mapping, reasons)

#============================================


class MacOSLocalLLM(LocalLLM):
	"""
	macOS-local backend (default).

	This is a placeholder backend that currently uses DummyLLM heuristics. It
	exists so the CLI can choose between "macos" and "ollama" backends.
	"""

	#============================================
	def __init__(self, model: str) -> None:
		self.model = model
		self._fallback = DummyLLM(model=model)

	#============================================
	def suggest_name_and_category(
		self, metadata: dict, current_name: str
	) -> tuple[str, str]:
		return self._fallback.suggest_name_and_category(metadata, current_name)

	#============================================
	def rename_file(self, metadata: dict, current_name: str) -> str:
		return self._fallback.rename_file(metadata, current_name)

	#============================================
	def rename_with_keep(self, metadata: dict, current_name: str) -> tuple[str, bool]:
		return self._fallback.rename_with_keep(metadata, current_name)

	#============================================
	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		return self._fallback.assign_categories(summaries)

	#============================================
	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		return self._fallback.rename_file_explain(metadata, current_name)

	#============================================
	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		return self._fallback.should_keep_original_explain(metadata, current_name, new_name)

	#============================================
	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		return self._fallback.assign_categories_explain(summaries)


#============================================


class OllamaChatLLM(LocalLLM):
	"""
	Ollama-backed chat client that keeps a local message history.
	"""

	#============================================
	def _extract_response_block(self, response_text: str) -> str | None:
		"""
		Extract a single <response>...</response> block from a chatty model output.
		"""
		match = re.search(
			r"<response\b[^>]*>.*?</response>",
			response_text,
			flags=re.IGNORECASE | re.DOTALL,
		)
		if not match:
			return None
		return match.group(0)

	#============================================
	def _tag_text(self, xml_block: str, tag: str) -> str:
		match = re.search(
			rf"<{tag}\b[^>]*>(.*?)</{tag}>",
			xml_block,
			flags=re.IGNORECASE | re.DOTALL,
		)
		if not match:
			return ""
		text = match.group(1).strip()
		if text.startswith("<![CDATA[") and text.endswith("]]>"):
			text = text[len("<![CDATA[") : -len("]]>")].strip()
		return text.strip()

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
		try:
			response_text = self.ask(prompt)
		except Exception:
			fallback = DummyLLM(model=self.model)
			return fallback.suggest_name_and_category(metadata, current_name)
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
		try:
			response_text = self.ask(prompt)
			return self._parse_keep_response(response_text)
		except Exception:
			return True

	#============================================
	def should_keep_original_explain(
		self, metadata: dict, current_name: str, new_name: str
	) -> tuple[bool, str]:
		prompt = self._build_keep_prompt(metadata, current_name, new_name)
		try:
			response_text = self.ask(prompt)
			return self._parse_keep_response_explain(response_text)
		except Exception:
			return (True, "fallback default: keep original")

	#============================================
	def rename_file(self, metadata: dict, current_name: str) -> str:
		"""
		Rename mode: descriptive filename only.
		"""
		prompt = self._build_rename_prompt(metadata, current_name)
		try:
			response_text = self.ask(prompt)
		except Exception:
			fallback = DummyLLM(model=self.model)
			return fallback.rename_file(metadata, current_name)
		return self._parse_rename_response(response_text, current_name)

	#============================================
	def rename_file_explain(self, metadata: dict, current_name: str) -> tuple[str, str]:
		prompt = self._build_rename_prompt(metadata, current_name)
		try:
			response_text = self.ask(prompt)
		except Exception:
			fallback = DummyLLM(model=self.model)
			return fallback.rename_file_explain(metadata, current_name)
		return self._parse_rename_response_explain(response_text, current_name)

	#============================================
	def assign_categories(self, summaries: list[dict]) -> dict[int, str]:
		"""
		Sorting mode: batch category assignment constrained to ALLOWED_CATEGORIES.
		"""
		if not summaries:
			return {}
		prompt = self._build_sort_prompt(summaries)
		try:
			response_text = self.ask(prompt)
		except Exception:
			fallback = DummyLLM(model=self.model)
			return fallback.assign_categories(summaries)
		expected = [int(item["index"]) for item in summaries]
		return self._parse_sort_response(response_text, expected)

	#============================================
	def assign_categories_explain(
		self, summaries: list[dict]
	) -> tuple[dict[int, str], dict[int, str]]:
		if not summaries:
			return ({}, {})
		prompt = self._build_sort_prompt(summaries)
		try:
			response_text = self.ask(prompt)
		except Exception:
			fallback = DummyLLM(model=self.model)
			return fallback.assign_categories_explain(summaries)
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
		lines.append("Rename mode: create a concise macOS-safe filename up to 256 characters.")
		lines.append("Use 3-8 meaningful tokens (names, IDs, dates, set numbers).")
		lines.append("Separate tokens with underscores or hyphens (e.g., Group_Of_8_Promo_Boxes).")
		lines.append("Summarize captions/descriptions into keywords; do NOT copy long sentences.")
		lines.append("Avoid filler adjectives like vibrant/beautiful; avoid repeating the original hashy name.")
		lines.append("Respond with a single XML block and nothing else:")
		lines.append("<response>")
		lines.append("  <new_name>NAME_WITH_EXTENSION</new_name>")
		lines.append("  <reason>short justification</reason>")
		lines.append("</response>")
		lines.append(f"current_name: {current_name}")
		lines.append(f"title: {metadata.get('title')}")
		lines.append(f"keywords: {metadata.get('keywords')}")
		lines.append(f"description: {metadata.get('summary') or metadata.get('description')}")
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
		xml_block = self._extract_response_block(response_text)
		if xml_block:
			new_name = self._tag_text(xml_block, "new_name") or current_name
			reason = self._tag_text(xml_block, "reason")
			return (sanitize_filename(new_name), reason)
		new_name = self._parse_rename_response(response_text, current_name)
		reason = ""
		for line in response_text.splitlines():
			trimmed = line.strip()
			if trimmed.lower().startswith("reason:"):
				reason = trimmed.split(":", 1)[1].strip()
				break
		return (new_name, reason)

	#============================================
	def _build_keep_prompt(self, metadata: dict, current_name: str, new_name: str) -> str:
		lines: list[str] = []
		lines.append("Decide if the original filename is meaningful and should be kept.")
		lines.append("Respond with a single XML block and nothing else:")
		lines.append("<response>")
		lines.append("  <keep_original>true</keep_original>")
		lines.append("  <reason>short justification</reason>")
		lines.append("</response>")
		lines.append("Keep if the original stem has a person name, username, project name, set number, or unique ID; discard if random hash/uuid or generic camera name.")
		lines.append(f"current_name: {current_name}")
		lines.append(f"suggested_name: {new_name}")
		lines.append(f"title: {metadata.get('title')}")
		lines.append(f"description: {metadata.get('summary') or metadata.get('description')}")
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
		xml_block = self._extract_response_block(response_text)
		if xml_block:
			keep_text = self._tag_text(xml_block, "keep_original").strip().lower()
			keep = keep_text.startswith("t") or keep_text == "1" or keep_text == "yes"
			reason = self._tag_text(xml_block, "reason")
			return (keep, reason)
		keep = self._parse_keep_response(response_text)
		reason = ""
		for line in response_text.splitlines():
			trimmed = line.strip()
			if trimmed.lower().startswith("reason:"):
				reason = trimmed.split(":", 1)[1].strip()
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
		lines.append("Respond with a single XML block and nothing else:")
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
		xml_block = self._extract_response_block(response_text)
		if xml_block:
			mapping: dict[int, str] = {}
			reasons: dict[int, str] = {}
			for match in re.finditer(
				r"<file\b[^>]*\bindex\s*=\s*[\"'](\d+)[\"'][^>]*>(.*?)</file>",
				xml_block,
				flags=re.IGNORECASE | re.DOTALL,
			):
				try:
					idx = int(match.group(1))
				except ValueError:
					continue
				body = match.group(2)
				category_text = self._tag_text(body, "category")
				reason_text = self._tag_text(body, "reason")
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
