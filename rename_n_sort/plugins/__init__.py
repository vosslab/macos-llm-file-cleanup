#!/usr/bin/env python3
from __future__ import annotations

from .base import FileMetadata, FileMetadataPlugin, PluginRegistry
from .audio_plugin import AudioPlugin
from .code_plugin import CodePlugin
from .csv_plugin import CSVPlugin
from .document_plugin import DocumentPlugin
from .docx_plugin import DocxPlugin
from .generic import GenericPlugin
from .html_plugin import HtmlPlugin
from .image_plugin import ImagePlugin
from .odt_plugin import OdtPlugin
from .pdf import PDFPlugin
from .presentation_plugin import PresentationPlugin
from .spreadsheet_plugin import SpreadsheetPlugin
from .text import TextDocumentPlugin
from .video_plugin import VideoPlugin
from .vector_image_plugin import VectorImagePlugin

__all__ = [
	"FileMetadata",
	"FileMetadataPlugin",
	"PluginRegistry",
	"build_registry",
]


def build_registry() -> PluginRegistry:
	"""
	Build default plugin registry.

	Returns:
		PluginRegistry with registered plugins.
	"""
	registry = PluginRegistry()
	registry.register(PDFPlugin())
	registry.register(DocxPlugin())
	registry.register(HtmlPlugin())
	registry.register(OdtPlugin())
	registry.register(DocumentPlugin())
	registry.register(PresentationPlugin())
	registry.register(SpreadsheetPlugin())
	registry.register(ImagePlugin())
	registry.register(VectorImagePlugin())
	registry.register(AudioPlugin())
	registry.register(VideoPlugin())
	registry.register(CSVPlugin())
	registry.register(CodePlugin())
	registry.register(TextDocumentPlugin())
	registry.register(GenericPlugin())
	return registry
