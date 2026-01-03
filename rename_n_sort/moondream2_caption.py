#!/usr/bin/env python3
"""
Moondream2 captioning helpers bundled with this repo.
"""

from __future__ import annotations

import logging
import sys
import types

import numpy as np
import torch
from PIL import Image
from transformers import AutoTokenizer
from transformers import AutoModelForCausalLM
import transformers.utils.logging as translogging


MODEL_ID = "vikhyatk/moondream2"
MODEL_REVISION = "2025-01-09"


def _get_mps_device() -> str:
	if not torch.backends.mps.is_available():
		raise RuntimeError("Moondream2 requires Apple Silicon with MPS support.")
	return "mps"


def _resize_image(image: Image.Image, max_dimension: int) -> Image.Image:
	width, height = image.size
	if max(width, height) <= max_dimension:
		return image
	if width > height:
		new_width = max_dimension
		new_height = int((max_dimension / width) * height)
	else:
		new_height = max_dimension
		new_width = int((max_dimension / height) * width)
	return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _ensure_pyvips_shim() -> None:
	try:
		__import__("pyvips")
		return
	except Exception:
		pass

	class _VipsImage:
		def __init__(self, array: np.ndarray) -> None:
			self._array = array
			self.height, self.width = array.shape[:2]

		@classmethod
		def new_from_array(cls, array: np.ndarray) -> "_VipsImage":
			return cls(array)

		def resize(self, scale: float, vscale: float | None = None) -> "_VipsImage":
			if vscale is None:
				vscale = scale
			new_w = max(1, int(round(self.width * scale)))
			new_h = max(1, int(round(self.height * vscale)))
			image = Image.fromarray(self._array)
			resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
			return _VipsImage(np.asarray(resized))

		def numpy(self) -> np.ndarray:
			return self._array

	module = types.ModuleType("pyvips")
	module.Image = _VipsImage
	sys.modules["pyvips"] = module
	logging.warning("pyvips not installed; using PIL-based shim for Moondream2.")


def setup_ai_components(prompt: str | None = None) -> dict:
	"""
	Setup the Moondream2 model and tokenizer.
	"""
	translogging.set_verbosity_error()
	_ensure_pyvips_shim()
	device = _get_mps_device()
	model = AutoModelForCausalLM.from_pretrained(
		MODEL_ID,
		trust_remote_code=True,
		revision=MODEL_REVISION,
		torch_dtype=torch.float16,
		device_map={"": device},
	)
	tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
	model.to(device)
	return {
		"model": model,
		"tokenizer": tokenizer,
		"device": device,
		"prompt": prompt,
	}


def generate_caption(image_path: str, ai_components: dict) -> str:
	"""
	Generate a caption for an image using Moondream2.
	"""
	image = Image.open(image_path)
	image = _resize_image(image, 1280)
	model = ai_components["model"]
	prompt = ai_components.get("prompt")
	if prompt:
		result = model.query(image, prompt)
		caption = result.get("answer", "")
	else:
		result = model.caption(image, length="normal")
		caption = result.get("caption", "")
	if not caption:
		raise RuntimeError("Moondream2 returned an empty caption.")
	return caption
