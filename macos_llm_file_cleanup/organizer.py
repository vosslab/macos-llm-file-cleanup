#!/usr/bin/env python3
"""
Core organizer: metadata -> LLM -> rename plan.
"""

# Standard Library
import logging
from dataclasses import dataclass
from pathlib import Path
import sys
import os

# local repo modules
from .config import AppConfig
from .llm import DummyLLM, LocalLLM, sanitize_filename
from .plugins import FileMetadata, PluginRegistry, build_registry
from .renamer import apply_move
from .scanner import iter_files

logger = logging.getLogger(__name__)

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
	keep_original: bool = True
	rename_reason: str = ""
	keep_reason: str = ""
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
	def _shorten(self, text: str, limit: int = 160) -> str:
		if not text:
			return ""
		cleaned = " ".join(str(text).split())
		if len(cleaned) <= limit:
			return cleaned
		return cleaned[: limit - 3] + "..."

	#============================================
	def _plan_one(self, path: Path, index: int) -> tuple[PlannedChange, dict]:
		metadata = self._collect_metadata(path)
		meta_payload = self._to_payload(metadata, path)
		new_name, rename_reason = self.llm.rename_file_explain(meta_payload, path.name)
		new_name = self._normalize_new_name(path.name, new_name)
		keep_original, keep_reason = self.llm.should_keep_original_explain(
			meta_payload, path.name, new_name
		)
		if keep_original:
			orig_stem = Path(path.name).stem
			if orig_stem.lower() not in new_name.lower():
				combined = f"{orig_stem}_{new_name}"
				new_name = self._normalize_new_name(path.name, combined)
				keep_reason = keep_reason or "kept original stem as prefix"
		plan = PlannedChange(
			source=path,
			target=path,
			category="Other",
			plugin=metadata.plugin_name,
			dry_run=self.config.dry_run,
			new_name=new_name,
			keep_original=keep_original,
			rename_reason=rename_reason,
			keep_reason=keep_reason,
		)
		summary = {
			"index": index,
			"name": new_name,
			"ext": path.suffix.lstrip("."),
			"description": meta_payload.get("summary") or meta_payload.get("description") or "",
		}
		return (plan, summary)

	#============================================
	def __init__(self, config: AppConfig, llm: LocalLLM | None = None) -> None:
		self.config = config
		self.registry: PluginRegistry = build_registry()
		if not llm:
			self.llm = DummyLLM(model="dummy")
		else:
			self.llm = llm

	#============================================
	def plan(self, files: list[Path] | None = None) -> list[PlannedChange]:
		"""
		Build plan for all files.

		Returns:
			List of planned changes.
		"""
		plans: list[PlannedChange] = []
		summaries: list[dict] = []
		candidates = files if files is not None else iter_files(self.config)
		for idx, path in enumerate(candidates):
			print(f"{self._color('[INFO]', '34')} Processing {path}")
			plan, summary = self._plan_one(path, idx)
			if self.config.explain:
				title = self._shorten(summary.get("description", "") or "")
				if title:
					print(f"{self._color('[INFO]', '34')} desc: {title}")
				if plan.rename_reason:
					print(f"{self._color('[INFO]', '34')} rename_reason: {self._shorten(plan.rename_reason)}")
				print(
					f"{self._color('[INFO]', '34')} keep_original: {str(plan.keep_original).lower()}"
					+ (f" ({self._shorten(plan.keep_reason)})" if plan.keep_reason else "")
				)
			plans.append(plan)
			print(
				f"{self._color('[PLAN1]', '36')} {path} -> {plan.new_name} "
				f"(plugin={plan.plugin})"
			)
			summaries.append(summary)
		self._assign_categories(plans, summaries)
		for plan in plans:
			print(
				f"{self._color('[PLAN2]', '36')} {plan.source} -> {plan.target} "
				f"(category={plan.category}, plugin={plan.plugin})"
			)
			if self.config.explain and plan.category_reason:
				print(
					f"{self._color('[INFO]', '34')} category_reason: {self._shorten(plan.category_reason)}"
				)
		return plans

	#============================================
	def process_one_by_one(self, files: list[Path] | None = None) -> list[PlannedChange]:
		"""
		Process files to completion one by one (PLAN1 -> PLAN2 -> DRY RUN/APPLY).
		"""
		plans: list[PlannedChange] = []
		candidates = files if files is not None else iter_files(self.config)
		for path in candidates:
			print(f"{self._color('[INFO]', '34')} Processing {path}")
			plan, summary = self._plan_one(path, index=0)
			if self.config.explain:
				desc = self._shorten(summary.get("description", "") or "")
				if desc:
					print(f"{self._color('[INFO]', '34')} desc: {desc}")
				if plan.rename_reason:
					print(f"{self._color('[INFO]', '34')} rename_reason: {self._shorten(plan.rename_reason)}")
				print(
					f"{self._color('[INFO]', '34')} keep_original: {str(plan.keep_original).lower()}"
					+ (f" ({self._shorten(plan.keep_reason)})" if plan.keep_reason else "")
				)
			print(
				f"{self._color('[PLAN1]', '36')} {plan.source} -> {plan.new_name} "
				f"(plugin={plan.plugin})"
			)
			cats, reasons = self.llm.assign_categories_explain([summary])
			category = cats.get(0, "Other")
			plan.category_reason = reasons.get(0, "")
			plan.category = category
			plan.target = self._target_path(plan.source, plan.new_name, category)
			print(
				f"{self._color('[PLAN2]', '36')} {plan.source} -> {plan.target} "
				f"(category={plan.category}, plugin={plan.plugin})"
			)
			if self.config.explain and plan.category_reason:
				print(
					f"{self._color('[INFO]', '34')} category_reason: {self._shorten(plan.category_reason)}"
				)
			if self.config.dry_run:
				print(
					f"{self._color('[DRY RUN]', '33')} {plan.source} -> {plan.target} "
					f"(category={plan.category}, plugin={plan.plugin})"
				)
			else:
				plan.target = apply_move(plan.source, plan.target, dry_run=False)
				if plan.target.exists():
					print(
						f"{self._color('[APPLY]', '32')} {plan.source} -> {plan.target} "
						f"(category={plan.category}, plugin={plan.plugin})"
					)
			plans.append(plan)
		return plans

	#============================================
	def _assign_categories(self, plans: list[PlannedChange], summaries: list[dict]) -> None:
		"""
		Assign categories in batches and update targets.
		"""
		if not summaries:
			return
		batch_size = 50
		for start in range(0, len(summaries), batch_size):
			batch = summaries[start : start + batch_size]
			if self.config.explain:
				cats, reasons = self.llm.assign_categories_explain(batch)
			else:
				cats = self.llm.assign_categories(batch)
				reasons = {}
			for item in batch:
				idx = item["index"]
				category = cats.get(idx, "Other")
				if idx < len(plans):
					plans[idx].category = category
					plans[idx].category_reason = reasons.get(idx, "")
					plans[idx].target = self._target_path(
						plans[idx].source, plans[idx].new_name, category
					)

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
		if "extension" not in meta.extra:
			meta.extra["extension"] = path.suffix.lstrip(".")
		meta.extra["keywords"] = meta.keywords
		meta.extra["title"] = meta.title
		meta.extra["summary"] = meta.summary
		return meta

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
		target_root = self.config.normalized_target_root()
		if category:
			target_root = target_root / "cleaned" / sanitize_filename(category)
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
