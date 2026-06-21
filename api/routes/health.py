from fastapi import APIRouter

from core.config import settings
from core.vector_store import get_qdrant_client

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Health check — verifies Qdrant is reachable."""
    try:
        client = get_qdrant_client()
        collections = [c.name for c in client.get_collections().collections]
        qdrant_status = "ok"
    except Exception as e:
        collections = []
        qdrant_status = f"error: {e}"

    return {
        "status": "ok" if qdrant_status == "ok" else "degraded",
        "qdrant": qdrant_status,
        "collection": settings.qdrant_collection,
        "collections_found": collections,
        "llm_provider": settings.llm_provider,
    }
