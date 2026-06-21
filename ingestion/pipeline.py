"""
Stage 4 — Embed + upsert pipeline.

For every document:
  parse → chunk → stamp metadata → embed (dense + sparse) → batch upsert to Qdrant

Dense vectors  : BAAI/bge-small-en-v1.5 via sentence-transformers (local)
Sparse vectors : BM25 via fastembed  (Qdrant/bm25 model, local)
Both are stored as named vectors inside a single PointStruct per chunk.
"""
import uuid
from pathlib import Path

from fastembed import SparseTextEmbedding
from qdrant_client.models import PointStruct, SparseVector

from core.config import settings
from core.embeddings import get_dense_embeddings
from core.vector_store import get_qdrant_client, ensure_collection, DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME
from ingestion.parser import parse_document
from ingestion.chunker import chunk_document
from ingestion.metadata import stamp_metadata


_BATCH_SIZE = 32  # upsert this many points per Qdrant call

_bm25_model: SparseTextEmbedding | None = None


def _get_bm25() -> SparseTextEmbedding:
    global _bm25_model
    if _bm25_model is None:
        _bm25_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _bm25_model


def ingest_file(path: Path, collection: str) -> int:
    """
    Ingest a single file into Qdrant.
    Returns the number of chunks upserted.
    """
    print(f"  [parse]  {path.name}")
    doc = parse_document(path)

    print(f"  [chunk]  {path.name}")
    raw_chunks = chunk_document(doc)
    if not raw_chunks:
        print(f"  [skip]   {path.name} — no chunks produced")
        return 0

    # Embed all chunks in one batch (faster than one-by-one)
    embedded_texts = [c.embedded_text for c in raw_chunks]

    print(f"  [embed]  {path.name} — {len(raw_chunks)} chunks")
    dense_embedder = get_dense_embeddings()
    dense_vecs = dense_embedder.embed_documents(embedded_texts)

    bm25 = _get_bm25()
    sparse_vecs = list(bm25.embed(embedded_texts))

    client = get_qdrant_client()
    points: list[PointStruct] = []

    for i, chunk in enumerate(raw_chunks):
        meta = stamp_metadata(chunk, collection, path)
        payload = meta.model_dump()
        payload["text"] = chunk.text  # store raw text for LLM context window

        sv = sparse_vecs[i]
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector={
                DENSE_VECTOR_NAME: dense_vecs[i],
                SPARSE_VECTOR_NAME: SparseVector(
                    indices=sv.indices.tolist(),
                    values=sv.values.tolist(),
                ),
            },
            payload=payload,
        ))

    # Batch upsert
    for batch_start in range(0, len(points), _BATCH_SIZE):
        batch = points[batch_start: batch_start + _BATCH_SIZE]
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=batch,
        )

    print(f"  [done]   {path.name} — {len(points)} points upserted")
    return len(points)


def ingest_collection(collection_dir: Path, collection_name: str) -> int:
    """Ingest all PDFs and Markdown files in a collection directory."""
    files = sorted(
        f for f in collection_dir.iterdir()
        if f.suffix.lower() in {".pdf", ".md", ".markdown"}
    )
    if not files:
        print(f"[warn] No documents found in {collection_dir}")
        return 0

    total = 0
    for f in files:
        total += ingest_file(f, collection_name)
    return total


def run_ingestion(data_dir: Path, collections: list[str] | None = None) -> None:
    """
    Entry point for the full ingestion run.
    collections=None means ingest all five collections.
    """
    all_collections = ["general", "clinical", "nursing", "billing", "equipment"]
    target = collections or all_collections

    print(f"\n=== MediBot Ingestion ===")
    print(f"Collection : {settings.qdrant_collection}")
    print(f"Qdrant URL : {settings.qdrant_url}")
    print(f"Targets    : {target}\n")

    ensure_collection()

    grand_total = 0
    for col in target:
        col_dir = data_dir / col
        if not col_dir.exists():
            print(f"[skip] {col_dir} not found")
            continue
        print(f"\n── {col.upper()} ──────────────────────────────")
        count = ingest_collection(col_dir, col)
        grand_total += count
        print(f"  Subtotal: {count} chunks")

    print(f"\n=== Done — {grand_total} total chunks in Qdrant ===\n")
