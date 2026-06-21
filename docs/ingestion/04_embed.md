# Step 4 — Embed (`ingestion/pipeline.py` + `core/embeddings.py`)

## What it does

Runs **two embedding passes** on the `embedded_text` (heading path + chunk text) of every chunk, producing one dense vector and one sparse vector per chunk.

Both models run **locally on CPU** — no API call, no cost, no internet dependency at runtime.

---

## Dense embedding — `BAAI/bge-small-en-v1.5`

```python
# core/embeddings.py
HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

# ingestion/pipeline.py
dense_vecs = dense_embedder.embed_documents(embedded_texts)
# → list of 384-dim float vectors
```

| Property | Value |
|---|---|
| Output dimensions | 384 floats per chunk |
| Distance metric | Cosine (L2-normalized → dot product at query time) |
| What it captures | **Semantic similarity** — paraphrases, synonyms, contextual meaning |
| Example | "myocardial infarction" and "heart attack" produce similar vectors |

`normalize_embeddings=True` normalises each vector to unit length. This means cosine similarity reduces to a simple dot product at query time — faster computation, same ranking result.

The model is a **singleton** (`@lru_cache`) — loaded once and reused across all chunks in the ingestion run.

### The embedding model used for ingestion must match retrieval

`core/embeddings.py` is imported by **both** `ingestion/pipeline.py` (write path) and `rag/retrieval.py` (read path). This is intentional — using the same factory in both places guarantees the query vector at retrieval time lives in the exact same vector space as the stored chunk vectors. A mismatch here would silently produce random similarity scores.

---

## Sparse embedding — BM25 via `Qdrant/bm25` (fastembed)

```python
# ingestion/pipeline.py
bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")
sparse_vecs = list(bm25.embed(embedded_texts))
# → list of SparseEmbedding objects: {indices: [...], values: [...]}
```

| Property | Value |
|---|---|
| Output format | Sparse vector — only tokens present in the text get non-zero weights |
| What it captures | **Exact keyword matching** — drug names, ICD codes, equipment model numbers |
| Example | "bge-reranker-base" matches only if those exact tokens appear |

BM25 weights a term higher if it appears frequently in the chunk but rarely across all chunks (TF-IDF style). This is why it excels at rare, domain-specific terms that a semantic model might embed poorly.

---

## Why both? — The Hybrid in Hybrid RAG

| | Dense (BGE) | Sparse (BM25) |
|---|---|---|
| **Wins on** | Paraphrases, synonyms, contextual questions | Exact terms, codes, model numbers, abbreviations |
| **Fails on** | Rare/specialised terminology | Synonyms, contextual meaning |

Neither retriever alone is sufficient for a medical assistant:
- A nurse asking *"what are the hand hygiene steps?"* — dense retrieval finds semantically similar passages even if different words are used
- A billing executive asking *"claims under ICICI Lombard with ICD code J18.9"* — BM25 catches the exact insurer name and code

The two vectors are stored together per chunk and fused at query time using **Reciprocal Rank Fusion (RRF)** — a single Qdrant query, not two separate queries merged in application code.

---

## All chunks are embedded in one batch

```python
embedded_texts = [c.embedded_text for c in raw_chunks]   # collect all first
dense_vecs  = dense_embedder.embed_documents(embedded_texts)  # one batch call
sparse_vecs = list(bm25.embed(embedded_texts))                # one batch call
```

Batching all chunks from one file before any upsert call is significantly faster than embedding one chunk at a time — the model processes them in parallel internally.

---

## Source

- Embedding factory: [`core/embeddings.py`](../../core/embeddings.py)
- Embed + upsert orchestration: [`ingestion/pipeline.py`](../../ingestion/pipeline.py)
- Config (model names): [`core/config.py`](../../core/config.py)
