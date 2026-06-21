"""
Hybrid retrieval with RBAC enforcement.

Single Qdrant query with two prefetch legs (dense + sparse),
fused via Reciprocal Rank Fusion — no separate queries merged in app code.
RBAC filter is applied inside the Qdrant query: restricted chunks
never reach the application layer.
"""
from functools import lru_cache

from fastembed import SparseTextEmbedding
from langchain_core.documents import Document
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    Prefetch,
    SparseVector,
)

from core.access import collections_for_role
from core.config import settings
from core.embeddings import get_dense_embeddings
from core.vector_store import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, get_qdrant_client


@lru_cache(maxsize=1)
def _get_bm25() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name="Qdrant/bm25")


def _build_rbac_filter(role: str) -> Filter:
    """
    Build the Qdrant filter that restricts results to chunks the role can access.
    access_roles field on each point holds a list of permitted roles.
    MatchAny checks if the user's role appears in that list.
    """
    return Filter(
        must=[
            FieldCondition(
                key="access_roles",
                match=MatchAny(any=[role]),
            )
        ]
    )


def hybrid_retrieve(question: str, role: str) -> list[Document]:
    """
    Hybrid dense + BM25 retrieval scoped to the user's role.
    Returns top-k LangChain Documents ready for reranking.
    """
    permitted = collections_for_role(role)
    if not permitted:
        return []

    # Encode query — both dense and sparse
    dense_embedder = get_dense_embeddings()
    dense_vec = dense_embedder.embed_query(question)

    bm25 = _get_bm25()
    sparse_result = list(bm25.embed([question]))[0]
    sparse_vec = SparseVector(
        indices=sparse_result.indices.tolist(),
        values=sparse_result.values.tolist(),
    )

    client = get_qdrant_client()
    # Single query: two prefetch legs fused with RRF
    # prefetch limit is higher than final limit — RRF needs a candidate pool
    prefetch_limit = settings.retrieval_top_k * 2

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(query=dense_vec, using=DENSE_VECTOR_NAME, limit=prefetch_limit),
            Prefetch(query=sparse_vec, using=SPARSE_VECTOR_NAME, limit=prefetch_limit),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=_build_rbac_filter(role),  # RBAC enforced here, not post-retrieval
        limit=settings.retrieval_top_k,
        with_payload=True,
    )

    docs: list[Document] = []
    for point in results.points:
        payload = point.payload or {}
        docs.append(Document(
            page_content=payload.get("text", ""),
            metadata={
                "source_document": payload.get("source_document", ""),
                "section_title":   payload.get("section_title", ""),
                "collection":      payload.get("collection", ""),
                "chunk_type":      payload.get("chunk_type", "text"),
                "score":           point.score,
            },
        ))

    return docs
