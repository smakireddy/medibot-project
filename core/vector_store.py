"""
Qdrant collection bootstrap and client factory.
Defines the named-vector schema (dense + sparse) used by both
ingestion (write) and retrieval (read).
"""
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)
from core.config import settings

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DENSE_DIM = 384  # BAAI/bge-small-en-v1.5 output dimension


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    kwargs: dict = {"url": settings.qdrant_url}
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return QdrantClient(**kwargs)


def ensure_collection(client: QdrantClient | None = None) -> None:
    """
    Create the Qdrant collection with dense + sparse named vectors
    if it does not already exist, then ensure the payload index on
    access_roles exists (required for RBAC metadata filtering).
    """
    client = client or get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}

    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=DENSE_DIM,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(on_disk=False)
                )
            },
        )
        print(f"[vector_store] Created collection '{settings.qdrant_collection}'")

    # Payload index on access_roles is required for MatchAny filtering (RBAC).
    # create_payload_index is idempotent — safe to call even if it already exists.
    client.create_payload_index(
        collection_name=settings.qdrant_collection,
        field_name="access_roles",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    print(f"[vector_store] Payload index on 'access_roles' ready")
