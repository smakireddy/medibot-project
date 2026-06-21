"""
Tests for FastAPI endpoints — uses TestClient (no real server needed).
LLM and Qdrant are mocked so tests run without external services.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    # Patch ensure_collection so startup doesn't need Qdrant
    with patch("core.vector_store.ensure_collection", return_value=None):
        from api.main import app
        return TestClient(app)


@pytest.fixture(scope="module")
def doctor_token(client):
    resp = client.post("/login", json={"username": "dr.mehta", "password": "doctor123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def nurse_token(client):
    resp = client.post("/login", json={"username": "nurse.priya", "password": "nurse123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def billing_token(client):
    resp = client.post("/login", json={"username": "billing.ravi", "password": "billing123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token(client):
    resp = client.post("/login", json={"username": "admin.sys", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_login_doctor(client):
    resp = client.post("/login", json={"username": "dr.mehta", "password": "doctor123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "doctor"
    assert "access_token" in data


def test_login_nurse(client):
    resp = client.post("/login", json={"username": "nurse.priya", "password": "nurse123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "nurse"


def test_login_billing(client):
    resp = client.post("/login", json={"username": "billing.ravi", "password": "billing123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "billing_executive"


def test_login_technician(client):
    resp = client.post("/login", json={"username": "tech.anand", "password": "tech123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "technician"


def test_login_admin(client):
    resp = client.post("/login", json={"username": "admin.sys", "password": "admin123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/login", json={"username": "dr.mehta", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/login", json={"username": "hacker", "password": "hack"})
    assert resp.status_code == 401


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_no_auth_needed(client):
    with patch("api.routes.health.get_qdrant_client") as mock_qdrant:
        mock_qdrant.return_value.get_collections.return_value.collections = []
        resp = client.get("/health")
    assert resp.status_code == 200


# ── Collections endpoint ──────────────────────────────────────────────────────

def test_collections_nurse(client, nurse_token):
    resp = client.get(
        "/collections/nurse",
        headers={"Authorization": f"Bearer {nurse_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "general" in data["collections"]
    assert "nursing" in data["collections"]
    assert "billing" not in data["collections"]
    assert "clinical" not in data["collections"]


def test_collections_admin_sees_all(client, admin_token):
    resp = client.get(
        "/collections/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    cols = resp.json()["collections"]
    assert set(cols) == {"general", "clinical", "nursing", "billing", "equipment"}


def test_collections_nurse_cannot_view_billing_role(client, nurse_token):
    """A nurse cannot inspect the billing role's collections."""
    resp = client.get(
        "/collections/billing_executive",
        headers={"Authorization": f"Bearer {nurse_token}"},
    )
    assert resp.status_code == 403


def test_collections_no_token(client):
    resp = client.get("/collections/nurse")
    assert resp.status_code == 401


# ── Chat endpoint (mocked LLM + Qdrant) ──────────────────────────────────────

def _mock_chat_response():
    from core.schemas import ChatResponse, SourceCitation
    return ChatResponse(
        answer="The infection control procedure involves...",
        sources=[SourceCitation(
            source_document="infection_control.pdf",
            section_title="Standard Precautions",
            collection="nursing",
        )],
        retrieval_type="hybrid_rag",
        role="nurse",
    )


def test_chat_requires_auth(client):
    resp = client.post("/chat", json={"question": "What is infection control?"})
    assert resp.status_code == 401


def test_chat_nurse_hybrid_rag(client, nurse_token):
    with patch("api.routes.chat.run_query", return_value=_mock_chat_response()):
        resp = client.post(
            "/chat",
            json={"question": "What is the infection control procedure?"},
            headers={"Authorization": f"Bearer {nurse_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["retrieval_type"] == "hybrid_rag"
    assert len(data["sources"]) > 0
    assert "answer" in data


def test_chat_empty_question_rejected(client, nurse_token):
    resp = client.post(
        "/chat",
        json={"question": "   "},
        headers={"Authorization": f"Bearer {nurse_token}"},
    )
    assert resp.status_code == 422


def test_chat_role_comes_from_token_not_body(client, nurse_token):
    """Even if body contains role=admin, the JWT role (nurse) must be used."""
    with patch("api.routes.chat.run_query", return_value=_mock_chat_response()) as mock_rq:
        client.post(
            "/chat",
            json={"question": "test", "role": "admin"},   # attacker tries to escalate
            headers={"Authorization": f"Bearer {nurse_token}"},
        )
        # run_query must have been called with role=nurse, not admin
        called_role = mock_rq.call_args.kwargs["role"]
        assert called_role == "nurse"
