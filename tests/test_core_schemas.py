"""
Tests for core/schemas.py — Pydantic model validation.
"""
import pytest
from pydantic import ValidationError
from core.schemas import ChunkMetadata, ChatRequest, ChatResponse, SourceCitation, LoginRequest


def test_chunk_metadata_valid():
    m = ChunkMetadata(
        source_document="drug_formulary.pdf",
        collection="clinical",
        access_roles=["doctor", "admin"],
        section_title="Adult Dosage",
        chunk_type="text",
    )
    assert m.collection == "clinical"
    assert "doctor" in m.access_roles


def test_chunk_metadata_invalid_collection():
    with pytest.raises(ValidationError):
        ChunkMetadata(
            source_document="file.pdf",
            collection="secret",        # not in Literal
            access_roles=["admin"],
            section_title="",
            chunk_type="text",
        )


def test_chunk_metadata_invalid_chunk_type():
    with pytest.raises(ValidationError):
        ChunkMetadata(
            source_document="file.pdf",
            collection="general",
            access_roles=["admin"],
            section_title="",
            chunk_type="image",          # not in Literal
        )


def test_chat_request_role_optional():
    """role has a default — only question is required from the client."""
    req = ChatRequest(question="What is the protocol?")
    assert req.question == "What is the protocol?"
    assert req.role == ""


def test_chat_response_valid():
    resp = ChatResponse(
        answer="The protocol is...",
        sources=[SourceCitation(source_document="a.pdf", section_title="Sec 1", collection="clinical")],
        retrieval_type="hybrid_rag",
        role="doctor",
    )
    assert resp.retrieval_type == "hybrid_rag"
    assert len(resp.sources) == 1


def test_chat_response_invalid_retrieval_type():
    with pytest.raises(ValidationError):
        ChatResponse(
            answer="answer",
            sources=[],
            retrieval_type="vector_search",   # not in Literal
            role="doctor",
        )


def test_login_request():
    req = LoginRequest(username="dr.mehta", password="doctor123")
    assert req.username == "dr.mehta"
