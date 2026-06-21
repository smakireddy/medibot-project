"""
SQL RAG chain — plain Python function as required by the assignment.

Three explicit steps per spec:
  1. NL → SQL  (LLM, using live-introspected schema as context)
  2. Strip code fences from raw LLM output
  3. Execute SQL → pass result to LLM → natural language answer

Schema context is built by querying the live SQLite database on first call
and cached for the process lifetime — always accurate, zero maintenance.
"""
import re
import sqlite3
import warnings
from functools import lru_cache
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import settings
from core.llm import get_llm

# Columns whose distinct values we want the LLM to know about
# (helps it generate WHERE clauses with correct literals)
_ENUM_COLUMNS: dict[str, list[str]] = {
    "claims": ["status", "department", "claim_type", "insurer"],
    "maintenance_tickets": ["status", "category", "issue_type", "campus"],
}


# Only SELECT and WITH (CTEs) are permitted — no DML or DDL
_SELECT_ONLY = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


def _get_connection(readonly: bool = False) -> sqlite3.Connection:
    db_path = Path(settings.db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path.resolve()}")
    if readonly:
        uri = f"file:{db_path.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=1)
def _build_schema_context() -> str:
    """
    Introspect the live database and return a schema description string.
    Called once; result cached for process lifetime.
    If the DB schema changes, restart the process to pick it up.
    """
    conn = _get_connection(readonly=True)
    cur = conn.cursor()
    lines: list[str] = ["Database: mediassist.db (SQLite)\n"]

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        lines.append(f"Table: {table} ({row_count} rows)")

        cur.execute(f"PRAGMA table_info({table})")
        columns = cur.fetchall()
        for col in columns:
            col_name, col_type = col[1], col[2]
            enum_vals = ""
            if table in _ENUM_COLUMNS and col_name in _ENUM_COLUMNS[table]:
                cur.execute(f"SELECT DISTINCT {col_name} FROM {table} WHERE {col_name} IS NOT NULL ORDER BY {col_name}")
                vals = [str(r[0]) for r in cur.fetchall()]
                if vals:
                    enum_vals = f"  -- values: {', '.join(vals)}"
            lines.append(f"  {col_name} {col_type}{enum_vals}")
        lines.append("")

    conn.close()
    return "\n".join(lines)


def _extract_sql(raw: str) -> str:
    """
    Strip markdown code fences and explanation text from LLM output.
    LLMs often return: ```sql\nSELECT ...\n``` or prefix with explanation.
    """
    # Remove ```sql ... ``` or ``` ... ``` fences
    fenced = re.search(r"```(?:sql)?\s*([\s\S]+?)```", raw, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # If no fences, find the first SELECT / WITH statement
    match = re.search(r"(SELECT|WITH)\b[\s\S]+", raw, re.IGNORECASE)
    if match:
        return match.group(0).strip()

    return raw.strip()


def _execute_sql(sql: str) -> str:
    """Execute the SQL and return results as a plain text table."""
    if not _SELECT_ONLY.match(sql):
        return "SQL execution error: only SELECT queries are permitted."
    conn = _get_connection(readonly=True)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        if not rows:
            return "Query returned no results."
        headers = [desc[0] for desc in cur.description]
        lines = [" | ".join(headers)]
        lines.append("-" * len(lines[0]))
        for row in rows:
            lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))
        return "\n".join(lines)
    except sqlite3.Error as e:
        return f"SQL execution error: {e}"
    finally:
        conn.close()


def sql_rag_chain(question: str) -> str:
    """
    Answer an analytical question using SQL RAG.
    Only call this for billing_executive and admin roles (enforced by the router).

    Returns a natural language answer string.
    """
    llm = get_llm()
    schema = _build_schema_context()

    # ── Step 1: NL → SQL ──────────────────────────────────────────────────────
    sql_prompt = [
        SystemMessage(content=(
            "You are a SQL expert. Given a database schema and a question, "
            "write a single valid SQLite SELECT query that answers the question. "
            "Return ONLY the SQL query — no explanation, no markdown fences."
        )),
        HumanMessage(content=f"Schema:\n{schema}\n\nQuestion: {question}"),
    ]
    raw_sql_response = llm.invoke(sql_prompt).content

    # ── Step 2: Strip code fences ─────────────────────────────────────────────
    sql = _extract_sql(raw_sql_response)
    print(f"[sql_rag] generated SQL:\n{sql}")

    # ── Step 3: Execute → NL answer ───────────────────────────────────────────
    result_text = _execute_sql(sql)
    print(f"[sql_rag] result:\n{result_text}")

    answer_prompt = [
        SystemMessage(content=(
            "You are a helpful healthcare data analyst. "
            "Given a question and the SQL query result, provide a clear, "
            "concise natural language answer. Be specific with numbers."
        )),
        HumanMessage(content=(
            f"Question: {question}\n\n"
            f"SQL query used:\n{sql}\n\n"
            f"Query result:\n{result_text}"
        )),
    ]
    answer = llm.invoke(answer_prompt).content

    return answer
