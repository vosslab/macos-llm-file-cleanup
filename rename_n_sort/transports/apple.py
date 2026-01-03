#!/usr/bin/env python3
"""
Apple Foundation Models transport.
"""

from __future__ import annotations

# Standard Library
import platform

# local repo modules
from ..llm_utils import MIN_MACOS_MAJOR, _parse_macos_version


class AppleTransport:
	name = "AppleLLM"

	def __init__(self) -> None:
		pass

	def _require_apple_intelligence(self) -> None:
		try:
			from applefoundationmodels import Session, apple_intelligence_available
		except Exception as exc:
			raise RuntimeError(
				"apple-foundation-models is required for the Apple backend."
			) from exc
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

	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		self._require_apple_intelligence()
		from applefoundationmodels import Session

		with Session() as session:
			response = session.generate(prompt, max_tokens=max_tokens, temperature=0.2)
		return response.text.strip()
