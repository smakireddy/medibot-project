"""
Tests for core/access.py — role-collection mapping and helper functions.
No external deps required — pure logic tests.
"""
import pytest
from core.access import (
    collections_for_role,
    roles_for_collection,
    SQL_ALLOWED_ROLES,
    ROLE_COLLECTIONS,
    ALL_COLLECTIONS,
)


def test_all_roles_have_general():
    """Every role must have access to the general collection."""
    for role in ROLE_COLLECTIONS:
        assert "general" in collections_for_role(role), f"{role} missing general"


def test_nurse_cannot_access_billing():
    assert "billing" not in collections_for_role("nurse")


def test_nurse_cannot_access_clinical():
    assert "clinical" not in collections_for_role("nurse")


def test_nurse_cannot_access_equipment():
    assert "equipment" not in collections_for_role("nurse")


def test_doctor_can_access_clinical_and_nursing():
    cols = collections_for_role("doctor")
    assert "clinical" in cols
    assert "nursing" in cols


def test_billing_executive_can_access_billing_only():
    cols = collections_for_role("billing_executive")
    assert "billing" in cols
    assert "clinical" not in cols
    assert "nursing" not in cols
    assert "equipment" not in cols


def test_technician_can_access_equipment_only():
    cols = collections_for_role("technician")
    assert "equipment" in cols
    assert "clinical" not in cols
    assert "billing" not in cols


def test_admin_accesses_all_collections():
    cols = collections_for_role("admin")
    assert set(cols) == set(ALL_COLLECTIONS)


def test_unknown_role_returns_empty():
    assert collections_for_role("hacker") == []


def test_sql_allowed_roles():
    assert "billing_executive" in SQL_ALLOWED_ROLES
    assert "admin" in SQL_ALLOWED_ROLES
    assert "nurse" not in SQL_ALLOWED_ROLES
    assert "doctor" not in SQL_ALLOWED_ROLES
    assert "technician" not in SQL_ALLOWED_ROLES


def test_roles_for_collection_general():
    """All 5 roles must appear in the general collection's access list."""
    roles = roles_for_collection("general")
    assert set(roles) == {"doctor", "nurse", "billing_executive", "technician", "admin"}


def test_roles_for_collection_billing():
    roles = roles_for_collection("billing")
    assert set(roles) == {"billing_executive", "admin"}


def test_roles_for_collection_equipment():
    roles = roles_for_collection("equipment")
    assert set(roles) == {"technician", "admin"}
