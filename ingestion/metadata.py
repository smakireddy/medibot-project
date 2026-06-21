"""
Stage 3 — Metadata stamping.

Attaches the full ChunkMetadata schema to every RawChunk.
access_roles is derived from the collection name via core/access.py —
single source of truth, no manual mapping per document.
"""
from pathlib import Path

from core.access import roles_for_collection
from core.schemas import ChunkMetadata
from ingestion.chunker import RawChunk


def stamp_metadata(chunk: RawChunk, collection: str, source_path: Path) -> ChunkMetadata:
    return ChunkMetadata(
        source_document=source_path.name,
        collection=collection,          # type: ignore[arg-type]
        access_roles=roles_for_collection(collection),
        section_title=chunk.section_title,
        chunk_type=chunk.chunk_type,    # type: ignore[arg-type]
    )
