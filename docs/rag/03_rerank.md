# Cross-Encoder Reranking (`rag/rerank.py`)

## What it does

Takes the top-10 candidates from Qdrant and scores each one jointly against the query using a cross-encoder model. Returns the top-3 by score — these are the only chunks the LLM ever sees.

---

## Why rerank after retrieval?

Vector similarity (used in retrieval) scores the query and each chunk **independently** and compares them. This is fast but misses relevance signals that only appear when you read both together.

A cross-encoder reads the **query + chunk as a pair** and produces a single joint relevance score. It can catch:
- A chunk that mentions the query topic only incidentally (high vector similarity, low cross-encoder score)
- A chunk that paraphrases the answer without sharing vocabulary (low BM25 score, high cross-encoder score)
- Negation — "warfarin is NOT recommended for..." scoring lower than "warfarin dosage is..."

The tradeoff: cross-encoders are too slow to run against an entire collection (tens of thousands of chunks). The hybrid retrieval step narrows from 254 points → 10 candidates cheaply; the reranker then picks the best 3 from those 10 expensively.

---

## The model — `BAAI/bge-reranker-base`

```python
@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    return CrossEncoder(settings.reranker_model)   # "BAAI/bge-reranker-base"
```

- XLMRoberta-based cross-encoder, fine-tuned for relevance scoring
- Runs locally on CPU — no API call
- Loaded once and cached for the process lifetime via `@lru_cache`
- `CrossEncoder` from `sentence-transformers` is used (not `FlagReranker`) — it correctly handles the tokenizer for this model with newer versions of `transformers`

---

## Scoring and ranking

```python
def rerank(question: str, docs: list[Document]) -> list[Document]:
    if not docs:
        return []

    reranker = _get_reranker()
    pairs = [[question, doc.page_content] for doc in docs]
    scores: list[float] = reranker.predict(pairs).tolist()

    scored = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    print("[rerank] scores:", [f"{s:.3f}" for s, _ in scored])

    top_docs = []
    for score, doc in scored[:settings.rerank_top_n]:   # top 3
        doc.metadata["rerank_score"] = round(score, 4)
        top_docs.append(doc)

    return top_docs
```

Each pair `[question, chunk_text]` is tokenized together and passed through the model. The output is a single float per pair — higher means more relevant. `predict()` returns a numpy array; `.tolist()` converts it for sorting.

The `rerank_score` is stored in each document's metadata — used by `node_generate` in the graph to detect out-of-scope queries (score below 0.05 threshold).

---

## Score interpretation

```
[rerank] scores: ['0.316', '0.011', '0.008', '0.007', ...]
```

| Score range | Meaning |
|---|---|
| > 0.3 | High confidence — chunk directly answers the query |
| 0.05 – 0.3 | Moderate relevance — partial match |
| < 0.05 | Low relevance — likely out of scope or wrong collection |

Scores are sigmoid-normalised (the model outputs logits; `CrossEncoder` applies sigmoid by default for `num_labels=1` models). Absolute values matter less than relative ranking — the top-3 by score are always selected regardless of absolute value.

**Note:** Medical structured content (tables, coded data) tends to produce lower absolute scores than natural prose — this is expected behaviour, not a model error.

---

## Source

- Reranker: [`rag/rerank.py`](../../rag/rerank.py)
- Config (model name, top_n): [`core/config.py`](../../core/config.py)
- LangGraph node: `node_rerank` in [`rag/graph.py`](../../rag/graph.py)
