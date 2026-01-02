#!/usr/bin/env python3
"""
Safe rename and move utilities.
"""

# Standard Library
import shutil
from pathlib import Path

#============================================


def dedupe_path(target: Path) -> Path:
	"""
	Append counter to avoid collisions.

	Args:
		target: Desired target path.

	Returns:
		Unique target path.
	"""
	counter = 1
	candidate = target
	while candidate.exists():
		candidate = candidate.with_stem(f"{target.stem} ({counter})")
		counter += 1
	return candidate


#============================================


def apply_move(source: Path, target: Path, dry_run: bool) -> Path:
	"""
	Apply rename or move safely.

	Args:
		source: Source file.
		target: Desired target file.
		dry_run: When True, no file changes.

	Returns:
		Final target path.
	"""
	if source.resolve() == target.resolve():
		return target
	dest = dedupe_path(target)
	if dry_run:
		return dest
	dest.parent.mkdir(parents=True, exist_ok=True)
	try:
		source.rename(dest)
	except Exception:
		shutil.move(str(source), str(dest))
	return dest
