#!/usr/bin/env python3
from __future__ import annotations

# Standard Library
import subprocess
from pathlib import Path

#============================================


def mdls_field(path: Path, field: str) -> str | None:
	"""
	Read a single mdls field.

	Args:
		path: File path.
		field: Field name.

	Returns:
		Value string or None.
	"""
	try:
		result = subprocess.run(
			["mdls", "-name", field, "-raw", str(path)],
			capture_output=True,
			text=True,
			check=False,
		)
	except FileNotFoundError:
		return None
	if result.returncode != 0:
		return None
	value = result.stdout.strip()
	if not value or value == "(null)":
		return None
	return value


def mdls_fields(path: Path, fields: list[str]) -> dict[str, str]:
	"""
	Read multiple mdls fields.

	Args:
		path: File path.
		fields: Field names.

	Returns:
		Dictionary of field values.
	"""
	data: dict[str, str] = {}
	for field in fields:
		val = mdls_field(path, field)
		if val:
			data[field] = val
	return data
