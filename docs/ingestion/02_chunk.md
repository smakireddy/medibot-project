# Step 2 — Chunk (`ingestion/chunker.py`)

## What it does

Splits the `DoclingDocument` from Step 1 into a list of `RawChunk` objects using Docling's `HybridChunker`. Each chunk carries **two versions of its text** — one for storage and one for embedding.

## Chunker settings

```python
HybridChunker(
    tokenizer="BAAI/bge-small-en-v1.5",  # same tokenizer as the embedding model
    max_tokens=512,                        # hard cap per chunk
    merge_peers=True,                      # merge short sibling sections
)
```

| Setting | Why |
|---|---|
| `tokenizer=dense_model` | Uses the **same** tokenizer as the embedding model — guarantees a chunk always fits in the encoder's context window without silent truncation |
| `max_tokens=512` | Hard ceiling; chunks that exceed it are split further |
| `merge_peers=True` | Short adjacent sibling sections under the same heading are merged — avoids 10-token orphan chunks with no retrieval signal |

## Two versions of text per chunk

Every `RawChunk` has two fields:

```python
@dataclass
class RawChunk:
    text: str           # original chunk text  → stored in Qdrant payload, sent to LLM
    embedded_text: str  # heading path + text  → used to generate the embedding vector
    section_title: str  # nearest parent heading
    chunk_type: str     # text | table | heading | code
```

### Why two versions? — Contextual Embedding

A chunk reading `"25mg twice daily. Duration: 7 days."` is **meaningless** without knowing it belongs under the heading `"Adult Dosage — Amoxicillin"`.

The `embedded_text` field prepends the full ancestor heading path to the chunk text before it is passed to the embedding model:

```
# embedded_text (used for the vector):
"Drug Formulary > Antibiotics > Amoxicillin > Adult Dosage

25mg twice daily. Duration: 7 days."

# text (stored in Qdrant, sent to the LLM):
"25mg twice daily. Duration: 7 days."
```

The heading path gives the embedding model **full context** — the resulting vector captures the meaning of the chunk *in its position in the document*, not just the literal words in isolation.

The heading path is stripped before storage so the LLM receives clean prose without repeated headings.

## Chunk type detection

```python
def _detect_type(doc_items: list) -> str:
    for item in doc_items:
        if isinstance(item, TableItem):       return "table"
        if isinstance(item, SectionHeaderItem): return "heading"
        if str(getattr(item, "label", "")).lower() in ("code", "code_block"):
            return "code"
    return "text"
```

| Docling element | `chunk_type` |
|---|---|
| `TableItem` | `"table"` |
| `SectionHeaderItem` | `"heading"` |
| code / code_block label | `"code"` |
| everything else | `"text"` |

Stored as metadata so downstream steps (and the LLM) know whether they are reading a table or prose.

## Example output

Input: `diagnostic_reference.pdf`

```
RawChunk(
    text          = "Rate, Normal = 60-100 bpm. Rate, Abnormal Significance = < 60 brady; > 100 tachy...",
    embedded_text = "4. ECG Interpretation Quick Guide\n\nRate, Normal = 60-100 bpm...",
    section_title = "4. ECG Interpretation Quick Guide",
    chunk_type    = "table"
)
```

## Source

- Module: [`ingestion/chunker.py`](../../ingestion/chunker.py)
