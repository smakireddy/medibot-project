"""
Shared Pydantic models used across ingestion, RAG, and API layers.
"""
from typing import Literal

from pydantic import BaseModel, Field


# ── Chunk metadata stored in Qdrant ──────────────────────────────────────────

class ChunkMetadata(BaseModel):
    source_document: str
    collection: Literal["general", "clinical", "nursing", "billing", "equipment"]
    access_roles: list[str]
    section_title: str
    chunk_type: Literal["text", "table", "heading", "code"]


# ── API request / response shapes ────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    role: str = ""   # ignored — role is always read from the JWT token


class SourceCitation(BaseModel):
    source_document: str
    section_title: str
    collection: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    retrieval_type: Literal["hybrid_rag", "sql_rag"]
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
