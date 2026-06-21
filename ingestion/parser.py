"""
Stage 1 — Document parsing.

Converts a PDF or Markdown file into a Docling DoclingDocument,
preserving headings, tables, paragraphs, and code blocks as
structured elements rather than flat text.
"""
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument


_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter


def parse_document(path: Path) -> DoclingDocument:
    """Parse a single PDF or Markdown file and return the structured document."""
    result = _get_converter().convert(str(path))
    return result.document
