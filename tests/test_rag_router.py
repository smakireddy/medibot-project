"""
Tests for rag/router.py — keyword routing logic (no LLM calls).
Tests only the keyword path to avoid LLM API dependency.
"""
import pytest
from unittest.mock import patch
from rag.router import _keyword_route, route_question


# ── Keyword routing (no LLM) ──────────────────────────────────────────────────

def test_keyword_route_how_many():
    assert _keyword_route("how many claims were escalated?") == "sql"


def test_keyword_route_count():
    assert _keyword_route("count of open maintenance tickets") == "sql"


def test_keyword_route_total():
    assert _keyword_route("what is the total approved amount?") == "sql"


def test_keyword_route_average():
    assert _keyword_route("what is the average claim amount?") == "sql"


def test_keyword_route_distribution():
    assert _keyword_route("show me the distribution of ticket categories") == "sql"


def test_keyword_route_knowledge_question():
    assert _keyword_route("what is the infection control procedure?") == "unclear"


def test_keyword_route_clinical_question():
    assert _keyword_route("what are the IV cannula sizes for paediatric patients?") == "unclear"


# ── Full routing with role permission check ───────────────────────────────────

def test_route_sql_allowed_for_billing_executive():
    with patch("rag.router._llm_route", return_value="sql"):
        # keyword match → no LLM call needed
        result = route_question("how many claims are pending?", "billing_executive")
    assert result == "sql"


def test_route_sql_denied_for_nurse():
    result = route_question("how many claims are pending?", "nurse")
    assert result == "sql_denied"


def test_route_sql_denied_for_doctor():
    result = route_question("what is the total claimed amount?", "doctor")
    assert result == "sql_denied"


def test_route_sql_denied_for_technician():
    result = route_question("how many tickets are open?", "technician")
    assert result == "sql_denied"


def test_route_rag_for_knowledge_question():
    with patch("rag.router._llm_route", return_value="rag"):
        result = route_question("what is the infection control procedure?", "nurse")
    assert result == "rag"


def test_route_admin_can_use_sql():
    result = route_question("how many claims are escalated?", "admin")
    assert result == "sql"
