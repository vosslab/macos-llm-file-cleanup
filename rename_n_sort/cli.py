#!/usr/bin/env python3
"""
Command line interface for llm-file-rename-n-sort.
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
from .config import AppConfig, parse_exts
from .llm_engine import LLMEngine
from .llm_utils import apple_models_available, choose_model
from .transports import AppleTransport, OllamaTransport
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
	mode_group = parser.add_mutually_exclusive_group()
	mode_group.add_argument(
		"-a",
		"--apply",
		dest="apply",
		action="store_true",
		help="Perform renames and moves.",
	)
	mode_group.add_argument(
		"-d",
		"--dry-run",
		dest="dry_run",
		action="store_true",
		help="Only print planned actions (default).",
	)
	parser.add_argument(
		"-m",
		"--max-files",
		dest="max_files",
		type=int,
		help="Maximum files to process.",
	)
	parser.add_argument(
		"--max-depth",
		dest="max_depth",
		type=int,
		default=1,
		help="Maximum directory depth to scan (default 1).",
	)
	parser.add_argument(
		"-v",
		"--verbose",
		dest="verbose",
		action="store_true",
		help="Verbose logging.",
	)
	parser.add_argument(
		"-e",
		"--ext",
		dest="extensions",
		action="append",
		help="Include only files with these extensions (repeatable).",
	)
	parser.add_argument(
		"-t",
		"--target",
		dest="target_root",
		help="Target root for organized files (default ~/Organized).",
	)
	parser.add_argument(
		"-o",
		"--model",
		dest="model",
		help="Override Ollama model name.",
	)
	order_group = parser.add_mutually_exclusive_group()
	order_group.add_argument(
		"-R",
		"--randomize",
		dest="randomize",
		action="store_true",
		help="Randomize file processing order (default).",
	)
	order_group.add_argument(
		"-S",
		"--sorted",
		dest="sorted",
		action="store_true",
		help="Process files in sorted order.",
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
		help="Optional context string added to LLM prompts to keep naming on-theme (e.g., 'Biology class', 'Client ACME').",
	)
	parser.set_defaults(apply=False, dry_run=True, randomize=True, sorted=False)
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
	if args.max_depth is not None:
		config.max_depth = args.max_depth
	if args.sorted:
		config.randomize = False
	elif args.randomize:
		config.randomize = True
	exts = parse_exts(args.extensions) if args.extensions else None
	if exts:
		config.include_extensions = exts
	config.dry_run = True
	if args.apply:
		config.dry_run = False
	elif args.dry_run:
		config.dry_run = True
	if args.model:
		config.model_override = args.model
	if args.llm_backend:
		config.llm_backend = args.llm_backend
	if args.context:
		config.context = args.context
	config.verbose = args.verbose
	return config


#============================================


def build_llm(config: AppConfig) -> LLMEngine:
	"""
	Instantiate LLM engine with model selection.

	Args:
		config: Application configuration.

	Returns:
		LLMEngine instance.
	"""
	model = choose_model(config.model_override)
	base_url = "http://localhost:11434"
	transports = []
	if config.llm_backend == "ollama":
		if not _ollama_available(base_url):
			raise RuntimeError("Ollama backend selected but service is not reachable.")
		transports = [OllamaTransport(model=model, base_url=base_url)]
		return LLMEngine(transports=transports, context=config.context)
	if not apple_models_available():
		if _ollama_available(base_url):
			logging.warning("Apple Foundation Models unavailable; using Ollama backup.")
			transports = [OllamaTransport(model=model, base_url=base_url)]
			return LLMEngine(transports=transports, context=config.context)
		raise RuntimeError("No available LLM backend (Apple Foundation Models or Ollama).")
	transports.append(AppleTransport())
	if _ollama_available(base_url):
		transports.append(OllamaTransport(model=model, base_url=base_url))
	return LLMEngine(transports=transports, context=config.context)


#============================================


def _color(text: str, code: str) -> str:
	if sys.stdout.isatty():
		return f"\033[{code}m{text}\033[0m"
	return text


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
	print(f"{_color('[SCAN]', '34')} Found {len(files)} files to consider.")
	if files:
		ext_counter = Counter(p.suffix.lower().lstrip(".") for p in files)
		top_exts = ext_counter.most_common(8)
		summary = ", ".join(f"{ext}:{count}" for ext, count in top_exts if ext)
		if summary:
			print(f"{_color('[SCAN]', '34')} Top extensions: {summary}")
	limited_files = files
	if config.randomize:
		random.shuffle(limited_files)
	else:
		limited_files = sorted(limited_files)
	if config.max_files:
		limited_files = limited_files[: config.max_files]
	organizer.process_one_by_one(limited_files)


#============================================


if __name__ == "__main__":
	main()
