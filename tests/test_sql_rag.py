"""
Tests for rag/sql_rag.py — schema introspection and SQL extraction.
Tests DB introspection and _extract_sql without making LLM calls.
"""
import pytest
from rag.sql_rag import _build_schema_context, _extract_sql, _execute_sql


# ── Schema introspection ──────────────────────────────────────────────────────

def test_schema_context_contains_tables():
    schema = _build_schema_context()
    assert "claims" in schema
    assert "maintenance_tickets" in schema


def test_schema_context_contains_columns():
    schema = _build_schema_context()
    assert "claim_id" in schema
    assert "status" in schema
    assert "ticket_id" in schema
    assert "equipment_name" in schema


def test_schema_context_contains_enum_values():
    schema = _build_schema_context()
    assert "escalated" in schema    # claims.status value
    assert "pending" in schema
    assert "approved" in schema


def test_schema_context_is_cached():
    """Calling twice should return identical object (lru_cache)."""
    s1 = _build_schema_context()
    s2 = _build_schema_context()
    assert s1 is s2


# ── SQL extraction ────────────────────────────────────────────────────────────

def test_extract_sql_from_fenced_block():
    raw = "```sql\nSELECT COUNT(*) FROM claims WHERE status = 'escalated'\n```"
    sql = _extract_sql(raw)
    assert sql.startswith("SELECT")
    assert "```" not in sql


def test_extract_sql_from_plain_text_with_explanation():
    raw = "Here is the SQL query:\nSELECT COUNT(*) FROM claims WHERE status = 'pending'"
    sql = _extract_sql(raw)
    assert "SELECT" in sql


def test_extract_sql_already_clean():
    raw = "SELECT * FROM maintenance_tickets WHERE status = 'open'"
    assert _extract_sql(raw) == raw


def test_extract_sql_backtick_without_lang():
    raw = "```\nSELECT department, COUNT(*) FROM claims GROUP BY department\n```"
    sql = _extract_sql(raw)
    assert "SELECT" in sql
    assert "```" not in sql


# ── Direct SQL execution ──────────────────────────────────────────────────────

def test_execute_sql_count_claims():
    result = _execute_sql("SELECT COUNT(*) as total FROM claims")
    assert "total" in result
    assert "85" in result          # we know claims has 85 rows


def test_execute_sql_escalated_claims():
    result = _execute_sql("SELECT COUNT(*) as cnt FROM claims WHERE status = 'escalated'")
    assert "cnt" in result


def test_execute_sql_maintenance_tickets():
    result = _execute_sql("SELECT COUNT(*) as total FROM maintenance_tickets")
    assert "total" in result
    assert "78" in result          # maintenance_tickets has 78 rows


def test_execute_sql_bad_query_returns_error_string():
    result = _execute_sql("SELECT * FROM nonexistent_table")
    assert "error" in result.lower()


def test_execute_sql_empty_result():
    result = _execute_sql("SELECT * FROM claims WHERE status = 'nonexistent_status_xyz'")
    assert "no results" in result.lower()
