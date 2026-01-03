#!/usr/bin/env python3
"""
Ollama chat transport.
"""

from __future__ import annotations

# Standard Library
import json
import random
import time
import urllib.request


class OllamaTransport:
	name = "Ollama"

	def __init__(
		self,
		model: str,
		base_url: str = "http://localhost:11434",
		system_message: str = "",
	) -> None:
		self.model = model
		self.base_url = base_url.rstrip("/")
		self.messages: list[dict[str, str]] = []
		if system_message:
			self.messages.append({"role": "system", "content": system_message})

	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		self.messages.append({"role": "user", "content": prompt})
		payload: dict[str, object] = {
			"model": self.model,
			"messages": self.messages,
			"stream": False,
			"options": {"num_predict": max_tokens},
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
