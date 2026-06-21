# Hybrid Retrieval (`rag/retrieval.py`)

## What it does

Runs a single Qdrant query combining dense semantic search and BM25 sparse keyword search, fused with Reciprocal Rank Fusion, with the RBAC filter applied server-side. Returns the top-10 most relevant chunks the user is permitted to see.

---

## Query encoding — same models as ingestion

```python
dense_embedder = get_dense_embeddings()          # BAAI/bge-small-en-v1.5, singleton
dense_vec = dense_embedder.embed_query(question) # 384-dim float vector

bm25 = _get_bm25()                               # Qdrant/bm25, singleton
sparse_result = list(bm25.embed([question]))[0]
sparse_vec = SparseVector(
    indices=sparse_result.indices.tolist(),
    values=sparse_result.values.tolist(),
)
```

The **same** embedding models used at ingestion time are used here. This is enforced by importing from `core/embeddings.py` in both paths — a mismatch would silently produce meaningless similarity scores.

---

## Single Qdrant query with two prefetch legs

```python
results = client.query_points(
    collection_name="medibot",
    prefetch=[
        Prefetch(query=dense_vec,  using="dense",  limit=20),  # semantic candidates
        Prefetch(query=sparse_vec, using="sparse", limit=20),  # keyword candidates
    ],
    query=FusionQuery(fusion=Fusion.RRF),   # merge with Reciprocal Rank Fusion
    query_filter=_build_rbac_filter(role),  # RBAC enforced here
    limit=10,                               # final top-k returned
    with_payload=True,
)
```

### Why two prefetch legs?

Each leg independently fetches 20 candidates using a different similarity metric:
- **Dense prefetch** — finds semantically similar chunks even if different words are used
- **Sparse prefetch** — finds chunks with exact keyword overlap (drug names, codes, abbreviations)

RRF then merges both ranked lists into one combined ranking. A chunk that appears high in both lists scores very highly. A chunk that only appears in one list still has a chance to surface.

This is more accurate than running two separate queries and merging in application code — Qdrant does it in a single round trip.

---

## RBAC filter — enforced inside Qdrant

```python
def _build_rbac_filter(role: str) -> Filter:
    return Filter(must=[
        FieldCondition(
            key="access_roles",
            match=MatchAny(any=[role]),
        )
    ])
```

The filter checks whether the role string appears in the chunk's `access_roles` list:

```
chunk.payload.access_roles = ["doctor", "admin"]

role = "doctor"  → MatchAny matches → chunk is returned
role = "nurse"   → MatchAny no match → chunk excluded
role = "billing_executive" → no match → chunk excluded
```

This filter runs **server-side inside Qdrant** during the vector search — restricted chunks are not retrieved, not transmitted, not visible to the application. The `KEYWORD` payload index on `access_roles` (created at collection setup) makes this filter an index scan rather than a full scan.

---

## Building Document objects

```python
docs: list[Document] = []
for point in results.points:
    payload = point.payload or {}
    docs.append(Document(
        page_content=payload.get("text", ""),      # chunk text → to LLM
        metadata={
            "source_document": payload.get("source_document", ""),
            "section_title":   payload.get("section_title", ""),
            "collection":      payload.get("collection", ""),
            "chunk_type":      payload.get("chunk_type", "text"),
            "score":           point.score,         # RRF fusion score
        },
    ))
```

The payload field `"text"` (set at ingestion) maps to LangChain's `page_content`. The Qdrant `score` is the RRF fusion score — stored in metadata for debugging but superseded by the reranker score after the next step.

---

## Retrieval parameters

| Parameter | Value | Purpose |
|---|---|---|
| `prefetch limit` | `retrieval_top_k × 2 = 20` | Wide candidate pool per leg for RRF to work well |
| `final limit` | `retrieval_top_k = 10` | Candidates passed to the reranker |
| `rerank_top_n` | `3` | Final chunks passed to the LLM (set in `core/config.py`) |

---

## Source

- Retrieval: [`rag/retrieval.py`](../../rag/retrieval.py)
- Embedding factory: [`core/embeddings.py`](../../core/embeddings.py)
- Access matrix: [`core/access.py`](../../core/access.py)
- Collection schema: [`core/vector_store.py`](../../core/vector_store.py)
