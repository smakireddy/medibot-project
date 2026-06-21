# Question Router (`rag/router.py`)

## What it does

Classifies every incoming question as one of three routing decisions before any retrieval happens:

| Decision | Meaning |
|---|---|
| `"rag"` | Knowledge question — go to hybrid retrieval |
| `"sql"` | Analytical question — go to SQL RAG chain |
| `"sql_denied"` | Analytical question, but role lacks SQL permission |

---

## Two-stage classification

### Stage 1 — Keyword regex (< 1ms, no LLM call)

```python
_SQL_KEYWORDS = re.compile(
    r"\b(how many|count|total|sum|average|avg|percentage|ratio|"
    r"most|least|top \d|highest|lowest|breakdown|distribution|"
    r"how much|statistics|stat|report|trend|compare|versus|vs\.?)\b",
    re.IGNORECASE,
)

def _keyword_route(question: str) -> Literal["sql", "rag", "unclear"]:
    if _SQL_KEYWORDS.search(question):
        return "sql"
    return "unclear"
```

If any keyword matches → immediately route to `sql` without calling the LLM. This handles the common analytical questions cheaply and fast.

### Stage 2 — LLM classification (only if unclear)

```python
def _llm_route(question: str) -> Literal["sql", "rag"]:
    llm = get_llm()
    messages = [
        SystemMessage(content=(
            "SQL: questions about counts, totals, statistics, trends, or specific records.\n"
            "RAG: questions about procedures, policies, guidelines, or medical knowledge.\n"
            "Reply with exactly one word: SQL or RAG"
        )),
        HumanMessage(content=question),
    ]
    response = llm.invoke(messages).content.strip().upper()
    return "sql" if "SQL" in response else "rag"
```

The LLM is given a minimal prompt with strict output format. Any response containing "SQL" routes to SQL; everything else routes to RAG. This handles ambiguous phrasing that keywords miss — e.g. "give me the figures for pending claims" has no keyword but the LLM correctly classifies it as SQL.

---

## RBAC check on SQL routing

```python
def route_question(question: str, role: str) -> RouteDecision:
    keyword_result = _keyword_route(question)
    decision = _llm_route(question) if keyword_result == "unclear" else keyword_result

    if decision == "sql" and role not in SQL_ALLOWED_ROLES:
        return "sql_denied"

    return decision
```

`SQL_ALLOWED_ROLES = {"billing_executive", "admin"}` — defined in `core/access.py`.

If a nurse or doctor asks "how many claims are pending?", the keyword stage correctly identifies it as SQL, but then `sql_denied` is returned — the question is never executed against the database.

---

## Routing decision examples

| Question | Stage 1 | Stage 2 | Role | Final |
|---|---|---|---|---|
| "How many claims are pending?" | `sql` (keyword: "how many") | — | billing_executive | `sql` |
| "How many claims are pending?" | `sql` (keyword: "how many") | — | nurse | `sql_denied` |
| "What is the ECG interpretation?" | `unclear` | LLM → `rag` | doctor | `rag` |
| "Give me the figures for escalated claims" | `unclear` | LLM → `sql` | admin | `sql` |
| "What are the nursing infection control procedures?" | `unclear` | LLM → `rag` | nurse | `rag` |

---

## Source

- Router: [`rag/router.py`](../../rag/router.py)
- SQL role permissions: [`core/access.py`](../../core/access.py)
- LangGraph node: `node_route` in [`rag/graph.py`](../../rag/graph.py)
