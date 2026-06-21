# SQL RAG Chain (`rag/sql_rag.py`)

## What it does

Answers analytical questions by translating natural language to SQL, executing it against a live SQLite database, and converting the result back to natural language. Available only to `billing_executive` and `admin` roles.

---

## Three explicit steps

```
Question: "How many claims are pending?"
    │
    ▼  Step 1 — NL → SQL (LLM)
    SELECT COUNT(*) FROM claims WHERE status = 'pending';
    │
    ▼  Step 2 — Strip fences (_extract_sql)
    SELECT COUNT(*) FROM claims WHERE status = 'pending';
    │
    ▼  Step 3 — Execute → NL (LLM)
    "There are 17 claims currently pending."
```

---

## Step 1 — Natural language to SQL

```python
sql_prompt = [
    SystemMessage(content=(
        "You are a SQL expert. Write a single valid SQLite SELECT query. "
        "Return ONLY the SQL — no explanation, no markdown fences."
    )),
    HumanMessage(content=f"Schema:\n{schema}\n\nQuestion: {question}"),
]
raw_sql_response = llm.invoke(sql_prompt).content
```

The schema context is passed with every call so the LLM knows the exact table names, column names, and enum values. It is built once and cached — see schema introspection below.

---

## Step 2 — Strip code fences

LLMs frequently wrap SQL in markdown even when told not to. `_extract_sql()` handles all variants:

```python
def _extract_sql(raw: str) -> str:
    # Remove ```sql ... ``` or ``` ... ```
    fenced = re.search(r"```(?:sql)?\s*([\s\S]+?)```", raw, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # Find first SELECT or WITH if no fences
    match = re.search(r"(SELECT|WITH)\b[\s\S]+", raw, re.IGNORECASE)
    if match:
        return match.group(0).strip()

    return raw.strip()
```

The extracted SQL is printed to the log:
```
[sql_rag] generated SQL:
SELECT COUNT(*) FROM claims WHERE status = 'pending';
```

---

## Step 3 — Execute and convert to natural language

```python
result_text = _execute_sql(sql)   # → "COUNT(*)\n-------\n17"

answer_prompt = [
    SystemMessage(content="Given a question and SQL result, provide a clear natural language answer."),
    HumanMessage(content=f"Question: {question}\n\nSQL:\n{sql}\n\nResult:\n{result_text}"),
]
answer = llm.invoke(answer_prompt).content
```

The raw SQL result (a plain text table) and the original question are both given to the LLM — it produces a natural language answer with the exact numbers from the result.

The result is also printed to the log:
```
[sql_rag] result:
COUNT(*)
--------
17
```

---

## Schema introspection — `_build_schema_context()`

The LLM needs to know what tables, columns, and valid enum values exist. Rather than hardcoding a schema string, it is **introspected from the live database** on first call and cached:

```python
@lru_cache(maxsize=1)
def _build_schema_context() -> str:
    # PRAGMA table_info(table) → column names and types
    # SELECT DISTINCT col FROM table → valid enum values for key columns
```

Example output passed to the LLM:

```
Table: claims (85 rows)
  claim_id TEXT
  status TEXT  -- values: approved, escalated, pending, rejected, submitted
  department TEXT  -- values: cardiology, emergency, general_medicine, ...
  claimed_amount REAL
  ...

Table: maintenance_tickets (78 rows)
  status TEXT  -- values: escalated, in_progress, open, resolved
  category TEXT  -- values: infusion, laboratory, monitoring, radiology, ...
```

The `-- values:` comments tell the LLM the exact string literals to use in `WHERE` clauses. Without them, the LLM might write `WHERE status = 'Pending'` (wrong case) or `WHERE status = 'in progress'` (wrong format).

Because it is `@lru_cache(maxsize=1)`, the introspection query runs once per process lifetime — restart the API to pick up schema changes.

---

## Database

| Table | Rows | Contains |
|---|---|---|
| `claims` | 85 | Patient insurance claims — amounts, status, department, insurer |
| `maintenance_tickets` | 78 | Equipment maintenance — category, campus, issue type, status |

Path: `data/db/mediassist.db` (SQLite, local file).

---

## Source

- SQL RAG chain: [`rag/sql_rag.py`](../../rag/sql_rag.py)
- LangGraph node: `node_sql` in [`rag/graph.py`](../../rag/graph.py)
- Config (db path): [`core/config.py`](../../core/config.py)
