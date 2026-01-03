#!/usr/bin/env python3
"""
Core organizer: metadata -> LLM -> rename plan.
"""

# Standard Library
import logging
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
import sys
import os

# local repo modules
from .config import AppConfig
from .llm_engine import LLMEngine
from .llm_prompts import SortItem
from .llm_utils import normalize_reason, sanitize_filename
from .plugins import FileMetadata, PluginRegistry, build_registry
from .renamer import apply_move
from .scanner import iter_files

logger = logging.getLogger(__name__)
_DOC_TYPE_TOKENS = {"invoice", "receipt", "order"}

#============================================


@dataclass(slots=True)
class PlannedChange:
	"""
	Planned move or rename.
	"""

	source: Path
	target: Path
	category: str
	plugin: str
	dry_run: bool
	new_name: str = ""
	stem_action: str = "keep"
	rename_reason: str = ""
	stem_reason: str = ""
	stem_raw: str = ""
	category_reason: str = ""


#============================================


class Organizer:
	"""
	Orchestrates scanning and renaming.
	"""

	#============================================
	def _color(self, text: str, code: str) -> str:
		if sys.stdout.isatty():
			return f"\033[{code}m{text}\033[0m"
		return text

	#============================================
	def _print_separator(self) -> None:
		print("=" * 60, file=sys.stderr)

	#============================================
	def _display_path(self, path: Path) -> str:
		for root in self.config.normalized_roots():
			try:
				return str(path.resolve().relative_to(root.resolve()))
			except Exception:
				continue
		return path.name

	#============================================
	def _display_target(self, path: Path) -> str:
		if self.config.target_root is not None:
			try:
				return str(path.resolve().relative_to(self.config.normalized_target_root()))
			except Exception:
				return path.name
		for root in self.config.normalized_roots():
			candidate = root / "Organized"
			try:
				return str(path.resolve().relative_to(candidate.resolve()))
			except Exception:
				continue
		return path.name

	#============================================
	def _target_root_for_source(self, source: Path) -> Path:
		if self.config.target_root is not None:
			return self.config.normalized_target_root()
		for root in self.config.normalized_roots():
			try:
				source.resolve().relative_to(root.resolve())
				return root / "Organized"
			except Exception:
				continue
		return source.parent / "Organized"

	#============================================
	def _print_dry_run_summary(self, plans: list[PlannedChange]) -> None:
		if not plans:
			return
		tag = self._color("[SUMMARY]", "36")
		print(f"{tag} Dry run target structure")
		grouped: dict[str, dict[str, list[str]]] = {}
		for plan in plans:
			target_root = self._target_root_for_source(plan.source)
			root_label = str(target_root)
			try:
				rel_path = plan.target.resolve().relative_to(target_root.resolve())
			except Exception:
				rel_path = Path(plan.target.name)
			dir_key = rel_path.parent.as_posix()
			if dir_key == ".":
				dir_key = ""
			grouped.setdefault(root_label, {}).setdefault(dir_key, []).append(rel_path.name)
		for root_label in sorted(grouped.keys()):
			print(f"{tag} {root_label}/")
			for dir_key in sorted(grouped[root_label].keys()):
				if dir_key:
					print(f"  {dir_key}/")
				for name in sorted(grouped[root_label][dir_key]):
					prefix = "    " if dir_key else "  "
					print(f"{prefix}{name}")

	#============================================
	def _print_pair(self, label: str, left: str, right: str, detail: str = "") -> None:
		tag = f"[{label}]"
		colored = self._color(tag, "36")
		indent = " " * (len(tag) + 1)
		print(f"{colored} {left}")
		if detail:
			print(f"{indent}-> {right} {detail}")
		else:
			print(f"{indent}-> {right}")

	#============================================
	def _print_why(self, label: str, value: str) -> None:
		if not value:
			return
		tag = self._color("[WHY]", "35")
		print(f"{tag} {label}: {self._shorten(value)}")

	#============================================
	def _shorten(self, text: str, limit: int = 160) -> str:
		if not text:
			return ""
		cleaned = " ".join(str(text).split())
		if len(cleaned) <= limit:
			return cleaned
		return cleaned[: limit - 3] + "..."

	#============================================
	def _log_keep_original_raw(
		self,
		path: Path,
		raw_text: str,
		stem_action: str,
		reason: str,
	) -> None:
		if raw_text is None:
			return
		try:
			with open("KEEP_ORIGINAL.log", "a", encoding="utf-8") as handle:
				handle.write("=" * 80 + "\n")
				handle.write(f"FILE: {self._display_path(path)}\n")
				handle.write(f"stem_action={stem_action}\n")
				handle.write(f"reason={reason}\n")
				raw = raw_text.strip()
				handle.write("raw_response=\n")
				handle.write(raw + "\n")
		except Exception:
			return

	#============================================
	def _log_sort_decision(self, plan: PlannedChange) -> None:
		try:
			with open("sort_decisions.log", "a", encoding="utf-8") as handle:
				handle.write("=" * 80 + "\n")
				handle.write(f"FILE: {self._display_path(plan.source)}\n")
				handle.write(f"FOLDER: {self._display_target(plan.target.parent)}\n")
				handle.write(f"TARGET: {self._display_target(plan.target)}\n")
				handle.write(f"category={plan.category}\n")
				handle.write(f"reason={plan.category_reason or ''}\n")
		except Exception:
			return

	#============================================
	def _log_run_metrics(self, plans: list[PlannedChange]) -> None:
		if not plans:
			return
		total = len(plans)
		fewer_tokens = 0
		keep_count = 0
		invoice_files = 0
		receipt_files = 0
		for plan in plans:
			orig_tokens = len(self._tokenize(plan.source.stem))
			new_tokens = len(self._tokenize(plan.new_name))
			if new_tokens < orig_tokens:
				fewer_tokens += 1
			if plan.stem_action == "keep":
				keep_count += 1
			name_tokens = self._tokenize(plan.new_name)
			if "invoice" in name_tokens:
				invoice_files += 1
			if "receipt" in name_tokens:
				receipt_files += 1
		def _pct(count: int) -> str:
			return f"{(count / total) * 100:.1f}%"
		try:
			with open("run_metrics.log", "a", encoding="utf-8") as handle:
				handle.write("=" * 80 + "\n")
				handle.write(f"total_files={total}\n")
				handle.write(f"fewer_tokens={fewer_tokens} ({_pct(fewer_tokens)})\n")
				handle.write(f"stem_action_keep={keep_count} ({_pct(keep_count)})\n")
				handle.write(f"invoice_files={invoice_files}\n")
				handle.write(f"receipt_files={receipt_files}\n")
		except Exception:
			return

	#============================================
	def _build_sort_description(self, meta_payload: dict) -> str:
		filetype_hint = meta_payload.get("filetype_hint") if meta_payload else ""
		title = meta_payload.get("title") if meta_payload else ""
		parts = [part for part in (filetype_hint, title) if part]
		return " - ".join(parts)

	#============================================
	def _normalize_text(self, text: str) -> str:
		if not text:
			return ""
		return " ".join(str(text).split()).strip().lower()

	#============================================
	def _tokenize(self, text: str) -> set[str]:
		if not text:
			return set()
		return {token.lower() for token in re.findall(r"[A-Za-z0-9]+", text)}

	#============================================
	def _collect_doc_type_text(self, meta_payload: dict, path: Path, orig_stem: str) -> str:
		parts: list[str] = [orig_stem, path.name]
		for key in ("title", "summary", "description", "caption", "ocr_text"):
			value = meta_payload.get(key)
			if isinstance(value, (list, tuple, set)):
				parts.extend(str(item) for item in value if item)
			elif value:
				parts.append(str(value))
		keywords = meta_payload.get("keywords")
		if isinstance(keywords, (list, tuple, set)):
			parts.extend(str(item) for item in keywords if item)
		elif keywords:
			parts.append(str(keywords))
		return " ".join(parts)

	#============================================
	def _apply_doc_type_safeguard(
		self,
		*,
		path: Path,
		meta_payload: dict,
		orig_stem: str,
		new_name: str,
		stem_action: str,
	) -> tuple[str, str]:
		if stem_action != "normalize":
			return stem_action, ""
		name_tokens = self._tokenize(new_name)
		suspect = name_tokens.intersection(_DOC_TYPE_TOKENS)
		if not suspect:
			return stem_action, ""
		content_text = self._collect_doc_type_text(meta_payload, path, orig_stem)
		content_tokens = self._tokenize(content_text)
		missing = sorted(term for term in suspect if term not in content_tokens)
		if not missing:
			return stem_action, ""
		override = f"override: doc type not found in metadata ({', '.join(missing)})"
		return "keep", override

	#============================================
	def _print_meta(self, label: str, value: str) -> None:
		if not value:
			return
		tag = self._color("[META]", "33")
		print(f"{tag} {label}: {self._shorten(value)}")

	#============================================
	def _plan_one(self, path: Path) -> tuple[PlannedChange, SortItem]:
		metadata = self._collect_metadata(path)
		pdf_text = metadata.extra.get("pdf_text") if metadata else None
		if pdf_text:
			if self._normalize_text(metadata.summary) != self._normalize_text(pdf_text):
				self._print_meta("raw_pdf_text_sample", pdf_text)
		meta_payload = self._to_payload(metadata, path)
		rename_result = self.llm.rename(path.name, meta_payload)
		new_name = self._normalize_new_name(path.name, rename_result.new_name)
		rename_reason = rename_result.reason
		orig_stem = Path(path.name).stem
		keep_result = self.llm.stem_action(
			orig_stem,
			new_name,
			extension=path.suffix.lstrip("."),
		)
		stem_action = keep_result.stem_action
		stem_reason = keep_result.reason
		stem_raw = keep_result.raw_text
		stem_reason = normalize_reason(stem_reason)
		stem_action, override_reason = self._apply_doc_type_safeguard(
			path=path,
			meta_payload=meta_payload,
			orig_stem=orig_stem,
			new_name=new_name,
			stem_action=stem_action,
		)
		if override_reason:
			stem_reason = f"{stem_reason}; {override_reason}" if stem_reason else override_reason
		if stem_action == "keep":
			if orig_stem.lower() not in new_name.lower():
				combined = f"{orig_stem}_{new_name}"
				new_name = self._normalize_new_name(path.name, combined)
				stem_reason = stem_reason or ""
		elif stem_action == "normalize":
			normalized_stem = sanitize_filename(orig_stem)
			if normalized_stem and normalized_stem.lower() not in new_name.lower():
				combined = f"{normalized_stem}_{new_name}"
				new_name = self._normalize_new_name(path.name, combined)
				stem_reason = stem_reason or ""
		plan = PlannedChange(
			source=path,
			target=path,
			category="Other",
			plugin=metadata.plugin_name,
			dry_run=self.config.dry_run,
			new_name=new_name,
			stem_action=stem_action,
			rename_reason=rename_reason,
			stem_reason=stem_reason,
			stem_raw=stem_raw,
		)
		self._log_keep_original_raw(path, stem_raw, stem_action, stem_reason)
		sort_description = self._build_sort_description(meta_payload)
		summary = SortItem(
			path=str(path.resolve()),
			name=new_name,
			ext=path.suffix.lstrip("."),
			description=sort_description,
		)
		return (plan, summary)

	#============================================
	def __init__(self, config: AppConfig, llm: LLMEngine | None = None) -> None:
		self.config = config
		self.registry: PluginRegistry = build_registry()
		self._supported_extensions = self._collect_supported_extensions()
		if not llm:
			raise RuntimeError("Organizer requires a configured LLM backend.")
		self.llm = llm
		self._reset_run_logs()

	#============================================
	def _reset_run_logs(self) -> None:
		start_line = f"RUN_START {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
		for log_path in (
			"KEEP_ORIGINAL.log",
			"XML_PARSE_FAILURES.log",
			"sort_decisions.log",
			"run_metrics.log",
		):
			try:
				with open(log_path, "w", encoding="utf-8") as handle:
					handle.write(start_line)
			except Exception:
				continue

	#============================================
	def plan(self, files: list[Path] | None = None) -> list[PlannedChange]:
		"""
		Build plan for all files.

		Returns:
			List of planned changes.
		"""
		plans: list[PlannedChange] = []
		summaries: list[SortItem] = []
		candidates = files if files is not None else iter_files(self.config)
		first = True
		for idx, path in enumerate(candidates):
			if not first:
				self._print_separator()
			first = False
			print(f"{self._color('[FILE]', '34')} {self._display_path(path)}")
			if not path.exists() or not path.is_file():
				self._print_why("error", "Path is not a file")
				self._print_why("action", "skipping path")
				continue
			if not self._is_supported_extension(path):
				ext = path.suffix.lower().lstrip(".")
				self._print_why("error", f"Unsupported extension: .{ext}")
				self._print_why("action", "skipping file due to unsupported extension")
				continue
			plan, summary = self._plan_one(path)
			title = summary.description or ""
			self._print_meta("text sample", title)
			self._print_why("rename_reason", plan.rename_reason)
			stem_detail = plan.stem_action
			if plan.stem_reason:
				stem_detail = f"{stem_detail} ({plan.stem_reason})"
			elif plan.stem_action == "keep":
				stem_detail = f"{stem_detail} (no justification provided)"
			self._print_why("stem_action", stem_detail)
			plans.append(plan)
			self._print_pair(
				"RENAME",
				self._display_path(plan.source),
				plan.new_name,
				f"(plugin={plan.plugin})",
			)
			summaries.append(summary)
		self._assign_categories(plans, summaries)
		for plan in plans:
			self._print_pair(
				"DEST",
				self._display_path(plan.source),
				self._display_target(plan.target),
				f"(category={plan.category}, plugin={plan.plugin})",
			)
			self._print_why("category_reason", plan.category_reason)
		if self.config.dry_run:
			self._print_dry_run_summary(plans)
		self._log_run_metrics(plans)
		return plans

	#============================================
	def process_one_by_one(self, files: list[Path] | None = None) -> list[PlannedChange]:
		"""
		Process files to completion one by one (RENAME -> DEST -> DRY RUN/APPLY).
		"""
		plans: list[PlannedChange] = []
		candidates = files if files is not None else iter_files(self.config)
		first = True
		for path in candidates:
			if not first:
				self._print_separator()
			first = False
			print(f"{self._color('[FILE]', '34')} {self._display_path(path)}")
			if not path.exists() or not path.is_file():
				self._print_why("error", "Path is not a file")
				self._print_why("action", "skipping path")
				continue
			if not self._is_supported_extension(path):
				ext = path.suffix.lower().lstrip(".")
				self._print_why("error", f"Unsupported extension: .{ext}")
				self._print_why("action", "skipping file due to unsupported extension")
				continue
			try:
				plan, summary = self._plan_one(path)
			except Exception as exc:
				self._print_why("error", f"{exc.__class__.__name__}: {exc}")
				self._print_why("action", "skipping file due to LLM error")
				continue
			desc = summary.description or ""
			self._print_meta("text sample", desc)
			self._print_why("rename_reason", plan.rename_reason)
			stem_detail = plan.stem_action
			if plan.stem_reason:
				stem_detail = f"{stem_detail} ({plan.stem_reason})"
			elif plan.stem_action == "keep":
				stem_detail = f"{stem_detail} (no justification provided)"
			self._print_why("stem_action", stem_detail)
			self._print_pair(
				"RENAME",
				self._display_path(plan.source),
				plan.new_name,
				f"(plugin={plan.plugin})",
			)
			try:
				result = self.llm.sort([summary])
				selection = result.assignments.get(summary.path, "Other")
				sort_reason = result.reasons.get(summary.path, "")
			except Exception as exc:
				self._print_why("error", f"{exc.__class__.__name__}: {exc}")
				self._print_why("action", "using fallback category Other")
				selection = "Other"
				sort_reason = ""
			category = selection.split("/")[0] if selection else "Other"
			plan.category = category
			plan.category_reason = sort_reason
			plan.target = self._target_path(plan.source, plan.new_name, category)
			self._log_sort_decision(plan)
			self._print_pair(
				"DEST",
				self._display_path(plan.source),
				self._display_target(plan.target),
				f"(category={plan.category}, plugin={plan.plugin})",
			)
			self._print_why("category_reason", plan.category_reason)
			if self.config.dry_run:
				self._print_pair(
					"DRY RUN",
					self._display_path(plan.source),
					self._display_target(plan.target),
					f"(category={plan.category}, plugin={plan.plugin})",
				)
			else:
				plan.target = apply_move(plan.source, plan.target, dry_run=False)
				if plan.target.exists():
					self._print_pair(
						"APPLY",
						self._display_path(plan.source),
						self._display_target(plan.target),
						f"(category={plan.category}, plugin={plan.plugin})",
					)
			plans.append(plan)
		if self.config.dry_run:
			self._print_dry_run_summary(plans)
		self._log_run_metrics(plans)
		return plans

	#============================================
	def _assign_categories(self, plans: list[PlannedChange], summaries: list[SortItem]) -> None:
		"""
		Assign categories in batches and update targets.
		"""
		if not summaries:
			return
		batch_size = 50
		for start in range(0, len(summaries), batch_size):
			batch = summaries[start : start + batch_size]
			result = self.llm.sort(batch)
			for offset, item in enumerate(batch):
				category_text = result.assignments.get(item.path, "Other")
				category = category_text.split("/")[0] if category_text else "Other"
				sort_reason = result.reasons.get(item.path, "")
				plan_index = start + offset
				if plan_index < len(plans):
					plans[plan_index].category = category
					plans[plan_index].category_reason = sort_reason
					plans[plan_index].target = self._target_path(
						plans[plan_index].source, plans[plan_index].new_name, category
					)
					self._log_sort_decision(plans[plan_index])

	#============================================
	def apply(self, plans: list[PlannedChange]) -> list[PlannedChange]:
		"""
		Apply planned moves.

		Args:
			plans: Planned changes.

		Returns:
			Plans after application.
		"""
		for change in plans:
			final_path = apply_move(change.source, change.target, change.dry_run)
			if self.config.verbose:
				if change.dry_run:
					logger.info(
						f"[DRY RUN] {change.source} -> {final_path} "
						f"(category={change.category}, plugin={change.plugin})"
					)
				else:
					logger.info(
						f"[APPLY] {change.source} -> {final_path} "
						f"(category={change.category}, plugin={change.plugin})"
					)
		return plans

	#============================================
	def _collect_metadata(self, path: Path) -> FileMetadata:
		"""
		Collect metadata from plugins.

		Args:
			path: File path.

		Returns:
			FileMetadata object.
		"""
		plugin = self.registry.for_path(path)
		meta = plugin.extract_metadata(path)
		meta.plugin_name = plugin.name
		meta.extra["extension"] = path.suffix.lstrip(".")
		if "filetype_hint" not in meta.extra and getattr(plugin, "filetype_hint", None):
			meta.extra["filetype_hint"] = plugin.filetype_hint
		if "extension" not in meta.extra:
			meta.extra["extension"] = path.suffix.lstrip(".")
		meta.extra["keywords"] = meta.keywords
		meta.extra["title"] = meta.title
		meta.extra["summary"] = meta.summary
		return meta

	#============================================
	def _collect_supported_extensions(self) -> set[str]:
		supported: set[str] = set()
		for plugin in self.registry.plugins():
			if plugin.name == "generic":
				continue
			for ext in plugin.supported_suffixes:
				supported.add(ext.lower())
		return supported

	#============================================
	def _is_supported_extension(self, path: Path) -> bool:
		ext = path.suffix.lower().lstrip(".")
		if not ext:
			return True
		return ext in self._supported_extensions

	#============================================
	def _to_payload(self, meta: FileMetadata, path: Path) -> dict:
		"""
		Convert metadata object to dictionary for LLMs.

		Args:
			meta: FileMetadata object.
			path: Source path.

		Returns:
			Dictionary payload.
		"""
		payload: dict = {
			"title": meta.title,
			"keywords": meta.keywords,
			"summary": meta.summary,
			"extension": path.suffix.lstrip("."),
			"plugin": meta.plugin_name,
		}
		payload.update(meta.extra)
		return payload

	#============================================
	def _target_path(self, path: Path, suggested_name: str, category: str) -> Path:
		"""
		Build target path with category and sanitized name.

		Args:
			path: Source path.
			suggested_name: Proposed name without extension.
			category: Category folder.

		Returns:
			Target Path.
		"""
		ext = path.suffix
		clean_name = sanitize_filename(suggested_name)
		base, ext_in_name = os.path.splitext(clean_name)
		if ext_in_name.lower() == ext.lower():
			new_filename = clean_name
		else:
			new_filename = f"{clean_name}{ext}"
		target_root = self._target_root_for_source(path)
		if category:
			target_root = target_root / sanitize_filename(category)
		target_path = target_root / new_filename
		return target_path

	#============================================
	def _normalize_new_name(self, current_name: str, proposed: str) -> str:
		"""
		Clean up LLM-proposed names that may duplicate extensions or echo the current name token.
		"""
		name = sanitize_filename(proposed)
		stem = Path(current_name).stem
		ext = Path(current_name).suffix.lower()
		lower_name = name.lower()
		if "-current_name" in lower_name:
			name = name[: lower_name.index("-current_name")]
			name = name.rstrip("-_.")
		while ext and name.lower().endswith(ext + ext):
			name = name[: -len(ext)]
		if not name:
			name = stem
		return sanitize_filename(name)
