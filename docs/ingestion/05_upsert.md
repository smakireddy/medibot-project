# Step 5 — Upsert to Qdrant (`ingestion/pipeline.py` + `core/vector_store.py`)

## What it does

Assembles each chunk into a `PointStruct` containing both vectors and all metadata, then writes them to Qdrant Cloud in batches of 32.

---

## The PointStruct — what one chunk looks like in Qdrant

```python
PointStruct(
    id     = "0081987b-3943-4abe-be79-5b8a981da5fd",   # random UUID
    vector = {
        "dense":  [0.021, -0.043, 0.017, ...],          # 384 floats (semantic)
        "sparse": SparseVector(
            indices = [142, 891, 2043],                  # token IDs present in chunk
            values  = [0.72,  0.31, 0.55],               # BM25 weights
        ),
    },
    payload = {
        "text":            "25mg twice daily. Duration: 7 days.",
        "source_document": "drug_formulary.pdf",
        "collection":      "clinical",
        "access_roles":    ["doctor", "admin"],
        "section_title":   "Adult Dosage",
        "chunk_type":      "text",
    }
)
```

Three components per point:

| Component | Content | Used at query time for |
|---|---|---|
| `id` | Random UUID | Point identity (upsert key) |
| `vector["dense"]` | 384-dim float vector | Semantic similarity search |
| `vector["sparse"]` | Sparse BM25 vector | Keyword similarity search |
| `payload["text"]` | Raw chunk text | Passed to LLM in context window |
| `payload["access_roles"]` | `["doctor", "admin"]` | RBAC `MatchAny` filter |
| other payload fields | source, section, collection | Source citations in the UI |

---

## Batch size of 32

```python
_BATCH_SIZE = 32

for batch_start in range(0, len(points), _BATCH_SIZE):
    batch = points[batch_start : batch_start + _BATCH_SIZE]
    client.upsert(collection_name=settings.qdrant_collection, points=batch)
```

All chunks for one file are assembled first, then uploaded in batches of 32. This balances:
- **Too small** (1 per call): high round-trip overhead to Qdrant Cloud
- **Too large** (all at once): risk of timeout or memory spike on large files

---

## The Qdrant collection schema

Created once by `ensure_collection()` before the first upsert:

```python
# core/vector_store.py
client.create_collection(
    collection_name="medibot",
    vectors_config={
        "dense": VectorParams(size=384, distance=Distance.COSINE)
    },
    sparse_vectors_config={
        "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
    },
)

# Payload index — required for MatchAny RBAC filter to be fast
client.create_payload_index(
    collection_name="medibot",
    field_name="access_roles",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

| Schema element | Detail |
|---|---|
| Named vector `"dense"` | 384-dim, cosine distance |
| Named vector `"sparse"` | BM25 sparse, in-memory index |
| Payload index on `access_roles` | `KEYWORD` type — makes `MatchAny` filter fast (index scan, not full scan) |

The `KEYWORD` index on `access_roles` is critical. Without it, Qdrant would need to scan every point to evaluate the RBAC filter — with it, only matching points are considered.

`ensure_collection()` is **idempotent** — it checks if the collection already exists before creating it, and `create_payload_index` is safe to call multiple times. The API server calls it at startup via the FastAPI lifespan hook.

---

## What is stored in Qdrant Cloud vs locally

| Data | Location |
|---|---|
| Dense vectors (384 floats × N points) | **Qdrant Cloud** |
| Sparse BM25 vectors | **Qdrant Cloud** |
| Payload (text, metadata, access_roles) | **Qdrant Cloud** |
| Original PDF files | **Local** (`data/` folder) |
| SQLite database | **Local** (`data/db/mediassist.db`) |
| BGE embedding model weights | **Local** (HuggingFace cache) |
| BGE reranker model weights | **Local** (HuggingFace cache) |

The raw PDFs are never uploaded. Only the derived vectors and metadata go to Qdrant. At query time, the query is embedded locally and only the 384-dim query vector is sent to Qdrant — Qdrant returns the top-10 matching payloads (text + metadata), not the vectors.

---

## Current state of the collection

```
Collection : medibot
URL        : https://c20c3b2e-3891-42bf-a751-64b92dda381f.us-east-1-1.aws.cloud.qdrant.io
Points     : 254   (11 PDFs across 5 collections)
Status     : green
```

---

## Source

- Upsert logic: [`ingestion/pipeline.py`](../../ingestion/pipeline.py)
- Collection schema + client: [`core/vector_store.py`](../../core/vector_store.py)
- Config (collection name, URL): [`core/config.py`](../../core/config.py)
