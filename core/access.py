"""
Role → permitted collections mapping.
Used at ingestion time to stamp access_roles on every chunk,
and at retrieval time to build the Qdrant metadata filter.
"""

ROLE_COLLECTIONS: dict[str, list[str]] = {
    "doctor":            ["general", "clinical", "nursing"],
    "nurse":             ["general", "nursing"],
    "billing_executive": ["general", "billing"],
    "technician":        ["general", "equipment"],
    "admin":             ["general", "clinical", "nursing", "billing", "equipment"],
}

# Roles that may use SQL RAG
SQL_ALLOWED_ROLES: set[str] = {"billing_executive", "admin"}

ALL_COLLECTIONS: list[str] = ["general", "clinical", "nursing", "billing", "equipment"]


def collections_for_role(role: str) -> list[str]:
    """Return the list of collections a role is permitted to access."""
    return ROLE_COLLECTIONS.get(role, [])


def roles_for_collection(collection: str) -> list[str]:
    """Return every role that can access a given collection (used at ingest time)."""
    return [role for role, cols in ROLE_COLLECTIONS.items() if collection in cols]
