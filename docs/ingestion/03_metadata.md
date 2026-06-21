# Step 3 — Stamp Metadata (`ingestion/metadata.py`)

## What it does

Attaches a `ChunkMetadata` object to every `RawChunk`. This is the step where **RBAC is baked into the data at write time** — before anything reaches Qdrant.

## The metadata schema

```python
ChunkMetadata(
    source_document = "drug_formulary.pdf",
    collection      = "clinical",
    access_roles    = ["doctor", "admin"],   # ← derived here
    section_title   = "Adult Dosage",
    chunk_type      = "text",
)
```

| Field | Value | Purpose |
|---|---|---|
| `source_document` | `"drug_formulary.pdf"` | Shown as source citation in the UI |
| `collection` | `"clinical"` | Identifies which knowledge domain the chunk belongs to |
| `access_roles` | `["doctor", "admin"]` | **RBAC** — list of roles allowed to see this chunk |
| `section_title` | `"Adult Dosage"` | Shown as section citation in the UI |
| `chunk_type` | `"text"` | Tells the LLM whether it is reading prose or a table |

## How `access_roles` is derived

`stamp_metadata()` calls `roles_for_collection(collection)` which **reverses** the access matrix defined in `core/access.py`:

```python
# core/access.py — single source of truth
ROLE_COLLECTIONS = {
    "doctor":            ["general", "clinical", "nursing"],
    "nurse":             ["general", "nursing"],
    "billing_executive": ["general", "billing"],
    "technician":        ["general", "equipment"],
    "admin":             ["general", "clinical", "nursing", "billing", "equipment"],
}

def roles_for_collection(collection: str) -> list[str]:
    return [role for role, cols in ROLE_COLLECTIONS.items() if collection in cols]
```

Example: for `collection = "clinical"`:

```
roles_for_collection("clinical")
→ ["doctor", "admin"]

# nurse, billing_executive, technician do not have "clinical" in their list
# so they are NOT in access_roles for any clinical chunk
```

## Why stamp at ingest time, not query time?

The RBAC filter is applied **inside Qdrant** using the `access_roles` payload field:

```python
Filter(must=[FieldCondition(key="access_roles", match=MatchAny(any=[role]))])
```

This filter runs **server-side in the vector database** — restricted chunks are excluded before the result leaves Qdrant. The application layer never receives them. The LLM never receives them.

If RBAC were applied post-retrieval in application code, a bug could leak restricted chunks. By stamping at ingest and filtering inside Qdrant, there is no application-layer code path that could accidentally expose them.

## The access matrix is the single source of truth

The same `ROLE_COLLECTIONS` dict in `core/access.py` is used:
- At **ingestion time** → to stamp `access_roles` on each chunk via `roles_for_collection()`
- At **query time** → to build the Qdrant RBAC filter via `collections_for_role()`
- At **API time** → to respond to `GET /collections/{role}` requests

Changing the access matrix in one place automatically propagates everywhere — after re-ingestion.

## Source

- Module: [`ingestion/metadata.py`](../../ingestion/metadata.py)
- Access matrix: [`core/access.py`](../../core/access.py)
