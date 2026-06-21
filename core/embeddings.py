"""
Single source of truth for embedding models.
Both ingestion and retrieval import from here — guarantees they use
identical models, preventing silent vector-space drift.
"""
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from core.config import settings


@lru_cache(maxsize=1)
def get_dense_embeddings() -> HuggingFaceEmbeddings:
    """BGE dense encoder — loaded once, cached for the process lifetime."""
    return HuggingFaceEmbeddings(
        model_name=settings.dense_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
