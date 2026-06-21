"""
Stage 2 — Hierarchical chunking.

Uses Docling's HybridChunker which:
  1. Splits along the document's natural structure (section → subsection → paragraph/table)
  2. Applies token-aware size limits as a second pass

Each chunk's embedded_text carries its parent section heading as context.
A chunk that just says "25mg twice daily" is useless without the heading
"Adult Dosage — Amoxicillin" prepended.
"""
from dataclasses import dataclass
from pathlib import Path

from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument, TableItem, SectionHeaderItem

from core.config import settings


@dataclass
class RawChunk:
    text: str           # original chunk text (stored as payload)
    embedded_text: str  # heading + text (used for embedding — richer context)
    section_title: str  # nearest parent heading
    chunk_type: str     # text | table | heading | code


def _detect_type(doc_items: list) -> str:
    for item in doc_items:
        if isinstance(item, TableItem):
            return "table"
        if isinstance(item, SectionHeaderItem):
            return "heading"
        label = getattr(item, "label", "")
        if str(label).lower() in ("code", "code_block"):
            return "code"
    return "text"


def chunk_document(doc: DoclingDocument) -> list[RawChunk]:
    """Return chunks with heading-enriched embedded text."""
    chunker = HybridChunker(
        tokenizer=settings.dense_model,
        max_tokens=512,
        merge_peers=True,
    )

    chunks: list[RawChunk] = []
    for chunk in chunker.chunk(dl_doc=doc):
        text = chunk.text.strip()
        if not text:
            continue

        # HybridChunker populates chunk.meta.headings as a list of parent headings
        headings: list[str] = getattr(chunk.meta, "headings", None) or []
        section_title = headings[-1] if headings else ""

        # Prepend all ancestor headings → gives the LLM full context
        heading_context = " > ".join(headings) if headings else ""
        embedded_text = f"{heading_context}\n\n{text}" if heading_context else text

        doc_items = getattr(chunk.meta, "doc_items", [])
        chunk_type = _detect_type(doc_items)

        chunks.append(RawChunk(
            text=text,
            embedded_text=embedded_text,
            section_title=section_title,
            chunk_type=chunk_type,
        ))

    return chunks
