#!/usr/bin/env python3
"""
Generate small, deterministic images under tests/test_files.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
	image = Image.new("RGB", (32, 32), color=color)
	image.save(path)

def _write_text_image(path: Path, text: str) -> None:
	width, height = 128, 32
	image = Image.new("RGB", (width, height), color=(255, 255, 255))
	draw = ImageDraw.Draw(image)
	font = ImageFont.load_default()
	bbox = draw.textbbox((0, 0), text, font=font)
	text_w = bbox[2] - bbox[0]
	text_h = bbox[3] - bbox[1]
	x = max(0, (width - text_w) // 2)
	y = max(0, (height - text_h) // 2)
	draw.text((x, y), text, fill=(0, 0, 0), font=font)
	image.save(path)


def generate_images(output_dir: Path) -> None:
	output_dir.mkdir(parents=True, exist_ok=True)
	_write_image(output_dir / "sample_image.png", (220, 50, 50))
	_write_image(output_dir / "sample_image.jpg", (50, 200, 80))
	_write_image(output_dir / "sample_image.gif", (40, 80, 220))
	_write_image(output_dir / "sample_image.bmp", (200, 200, 50))
	_write_image(output_dir / "sample_image.tiff", (120, 120, 120))
	_write_text_image(output_dir / "sample_ocr.png", "SAMPLE")


def main() -> None:
	generate_images(Path("tests/test_files"))


if __name__ == "__main__":
	main()
