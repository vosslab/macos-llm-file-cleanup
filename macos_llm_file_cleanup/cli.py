#!/usr/bin/env python3
"""
Command line interface for macos-llm-file-cleanup.
"""

# Standard Library
import argparse
import logging
from pathlib import Path
import urllib.request
import random
from collections import Counter
import sys

# local repo modules
from .config import AppConfig, load_user_config, parse_exts
from .llm import MacOSLocalLLM, OllamaLLM, choose_model
from .organizer import Organizer
from .scanner import iter_files

#============================================


def parse_args() -> argparse.Namespace:
	"""
	Parse CLI arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Rename and sort macOS files using a local LLM."
	)
	parser.add_argument(
		"-p",
		"--paths",
		dest="paths",
		nargs="+",
		required=True,
		help="Paths to scan (required).",
	)
	parser.add_argument(
		"-d",
		"--dry-run",
		dest="dry_run",
		action="store_true",
		help="Only print planned actions.",
	)
	parser.add_argument(
		"-a",
		"--apply",
		dest="apply",
		action="store_true",
		help="Perform renames and moves.",
	)
	parser.add_argument(
		"-m",
		"--max-files",
		dest="max_files",
		type=int,
		help="Maximum files to process.",
	)
	parser.add_argument(
		"-c",
		"--config",
		dest="config_path",
		help="Optional JSON or YAML config file.",
	)
	parser.add_argument(
		"-v",
		"--verbose",
		dest="verbose",
		action="store_true",
		help="Verbose logging.",
	)
	parser.add_argument(
		"--explain",
		dest="explain",
		action="store_true",
		help="Print per-file decision details (rename/keep/category).",
	)
	parser.add_argument(
		"-e",
		"--ext",
		dest="extensions",
		action="append",
		help="Include only files with these extensions (repeatable).",
	)
	parser.add_argument(
		"-g",
		"--category",
		dest="categories",
		action="append",
		help="Limit to a high-level category (docs, data, images, audio, video, code).",
	)
	parser.add_argument(
		"-t",
		"--target",
		dest="target_root",
		help="Target root for organized files (default ~/Organized).",
	)
	parser.add_argument(
		"-r",
		"--recursive",
		dest="recursive",
		action="store_true",
		help="Recursively scan directories.",
	)
	parser.add_argument(
		"-s",
		"--stop-recursive",
		dest="stop_recursive",
		action="store_true",
		help="Disable recursion even if config enables it.",
	)
	parser.add_argument(
		"-o",
		"--model",
		dest="model",
		help="Override Ollama model name.",
	)
	parser.add_argument(
		"--llm-backend",
		dest="llm_backend",
		choices=["macos", "ollama"],
		default="macos",
		help="Choose LLM backend: macos (default) or ollama.",
	)
	parser.add_argument(
		"-x",
		"--context",
		dest="context",
		help="Optional user/folder context to keep naming on-theme.",
	)
	parser.add_argument(
		"-z",
		"--randomize",
		dest="randomize",
		action="store_true",
		help="Randomize file processing order (useful for testing).",
	)
	parser.add_argument(
		"--one-by-one",
		dest="one_by_one",
		action="store_true",
		help="Process each file to completion before moving to the next.",
	)
	parser.set_defaults(dry_run=False, apply=False)
	return parser.parse_args()


#============================================


def build_config(args: argparse.Namespace) -> AppConfig:
	"""
	Build runtime config from args and file.
	"""
	config = AppConfig()
	config.roots = [Path(p).expanduser() for p in args.paths]
	if args.target_root:
		config.target_root = Path(args.target_root).expanduser()
	if args.max_files:
		config.max_files = args.max_files
	exts = parse_exts(args.extensions) if args.extensions else None
	cat_exts = parse_category_exts(args.categories) if getattr(args, "categories", None) else None
	if exts and cat_exts:
		config.include_extensions = exts.union(cat_exts)
	elif exts:
		config.include_extensions = exts
	elif cat_exts:
		config.include_extensions = cat_exts
	if args.stop_recursive:
		config.recursive = False
	if args.recursive:
		config.recursive = True
	config.dry_run = True
	if args.apply:
		config.dry_run = False
	elif args.dry_run:
		config.dry_run = True
	if args.config_path:
		config.config_path = Path(args.config_path)
		user_cfg = load_user_config(config.config_path)
		if user_cfg.get("target_root"):
			config.target_root = Path(user_cfg["target_root"]).expanduser()
		if user_cfg.get("include_extensions"):
			config.include_extensions = parse_exts(user_cfg["include_extensions"])
		if user_cfg.get("context"):
			config.context = str(user_cfg.get("context"))
		if user_cfg.get("llm_backend"):
			config.llm_backend = str(user_cfg.get("llm_backend"))
		if "explain" in user_cfg:
			config.explain = bool(user_cfg.get("explain"))
	if args.model:
		config.model_override = args.model
	if args.llm_backend:
		config.llm_backend = args.llm_backend
	if args.context:
		config.context = args.context
	if args.randomize:
		config.randomize = True
	if args.one_by_one:
		config.one_by_one = True
	if args.explain:
		config.explain = True
	config.verbose = args.verbose
	return config


#============================================


def build_llm(config: AppConfig):
	"""
	Instantiate LLM client with model selection.

	Args:
		config: Application configuration.

	Returns:
		OllamaLLM or DummyLLM instance.
	"""
	model = choose_model(config.model_override)
	system_prompt = ""
	if config.context:
		system_prompt = (
			"Keep names and categories aligned to this user/folder context: "
			+ config.context
		)
	if config.llm_backend == "ollama":
		base_url = "http://localhost:11434"
		if not _ollama_available(base_url):
			logging.warning("Ollama service not reachable; using local macOS backend")
			return MacOSLocalLLM(model=model)
		return OllamaLLM(model=model, system_message=system_prompt, base_url=base_url)
	return MacOSLocalLLM(model=model)


#============================================


def _color(text: str, code: str) -> str:
	if sys.stdout.isatty():
		return f"\033[{code}m{text}\033[0m"
	return text


#============================================


def parse_category_exts(categories: list[str] | None) -> set[str] | None:
	if not categories:
		return None
	mapping = {
		"docs": {"pdf", "doc", "docx", "odt", "rtf", "pages", "txt", "md"},
		"data": {"xls", "xlsx", "ods", "csv", "tsv"},
		"images": {"jpg", "jpeg", "png", "gif", "heic", "tif", "tiff", "bmp", "svg", "svgz"},
		"audio": {"mp3", "wav", "flac", "aiff", "ogg"},
		"video": {"mp4", "mov", "mkv", "webm", "avi"},
		"code": {"py", "m", "cpp", "js", "sh", "pl", "rb", "php"},
	}
	collected: set[str] = set()
	for cat in categories:
		if cat in mapping:
			collected.update(mapping[cat])
	return collected or None


#============================================


def _ollama_available(base_url: str) -> bool:
	"""
	Check if Ollama service is up.
	"""
	try:
		request = urllib.request.Request(f"{base_url}/api/tags", method="GET")
		with urllib.request.urlopen(request, timeout=2) as response:
			return response.status < 400
	except Exception:
		return False


#============================================


def main() -> None:
	"""
	Entry point for the CLI.
	"""
	args = parse_args()
	config = build_config(args)
	if config.verbose:
		logging.basicConfig(level=logging.INFO)
	else:
		logging.basicConfig(level=logging.WARNING)
	llm = build_llm(config)
	organizer = Organizer(config=config, llm=llm)
	files = iter_files(config)
	print(f"{_color('[INFO]', '34')} Found {len(files)} files to consider.")
	if files:
		ext_counter = Counter(p.suffix.lower().lstrip(".") for p in files)
		top_exts = ext_counter.most_common(8)
		summary = ", ".join(f"{ext}:{count}" for ext, count in top_exts if ext)
		if summary:
			print(f"{_color('[INFO]', '34')} Top extensions: {summary}")
	limited_files = files
	if config.randomize:
		random.shuffle(limited_files)
	if config.max_files:
		limited_files = limited_files[: config.max_files]
	if config.one_by_one:
		organizer.process_one_by_one(limited_files)
		return
	plans = organizer.plan(limited_files)
	for change in plans:
		if config.dry_run:
			print(
				f"{_color('[DRY RUN]', '33')} {change.source} -> {change.target} "
				f"(category={change.category}, plugin={change.plugin})"
			)
	organizer.apply(plans)
	if not config.dry_run:
		for change in plans:
			if change.target.exists():
				print(
					f"{_color('[APPLY]', '32')} {change.source} -> {change.target} "
					f"(category={change.category}, plugin={change.plugin})"
				)


#============================================


if __name__ == "__main__":
	main()
