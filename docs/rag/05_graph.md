# LangGraph Orchestration (`rag/graph.py`)

## What it does

Defines the complete query pipeline as a stateful directed graph. Every chat request flows through this graph — routing, retrieval, reranking, and generation are explicit named nodes connected by edges.

---

## State — `MediBotState`

```python
class MediBotState(TypedDict):
    question:       str
    role:           str
    route:          str             # "rag" | "sql" | "sql_denied"
    documents:      list[Document]  # retrieved + reranked docs
    answer:         str
    sources:        list[dict]
    retrieval_type: str             # "hybrid_rag" | "sql_rag"
```

State is a plain `TypedDict` — each node receives the full state and returns an updated copy. No mutation; no shared mutable objects between nodes.

---

## Graph structure

```
START
  │
  ▼
node_route ──────────────────────────────────────────
  │                    │                    │
  ▼ (rag)             ▼ (sql)             ▼ (sql_denied)
node_retrieve      node_sql           node_sql_denied
  │                    │                    │
  ▼                   END                  END
node_rerank
  │
  ▼
node_generate
  │
 END
```

---

## Nodes

### `node_route`
Calls `route_question(question, role)` → sets `state["route"]`.
See [router documentation](01_router.md) for classification logic.

### `node_sql`
Calls `sql_rag_chain(question)` → LLM generates SQL, executes it, converts result to natural language.
Sets `retrieval_type = "sql_rag"`, `sources = []`.
See [SQL RAG documentation](04_sql_rag.md).

### `node_sql_denied`
No retrieval — returns a polite access refusal message listing the role's permitted collections:
```
"As a nurse, you don't have access to analytical database queries.
I can answer questions from the general, nursing document collections."
```

### `node_retrieve`
Calls `hybrid_retrieve(question, role)` → returns top-10 `Document` objects from Qdrant with RBAC filter applied.
See [retrieval documentation](02_retrieval.md).

### `node_rerank`
Calls `rerank(question, documents)` → scores all 10 with cross-encoder, returns top-3.
Each returned doc has `metadata["rerank_score"]` set.
See [reranking documentation](03_rerank.md).

### `node_generate`
Assembles the top-3 chunks into a context block and calls the LLM:

```python
SystemMessage: (
    f"You are MediBot. The current user is a {role} with access to: {permitted_collections}. "
    f"Answer using ONLY the provided context. "
    f"If the context does not contain the answer, respond: "
    f"'As a {role}, your accessible collections are: {permitted}. "
    f"The information you are asking about is not available in these collections...'"
)
HumanMessage: f"Context:\n{context}\n\nQuestion: {question}"
```

The system prompt includes the role's permitted collections so the LLM produces an access-aware message (not a generic "I don't know") when the retrieved chunks don't contain the answer.

**Out-of-scope detection:** If the top rerank score is below `0.05`, the node skips the LLM entirely and returns the access-aware message directly — avoids a redundant LLM call when no chunk is relevant.

---

## Conditional edge — `edge_after_route`

```python
def edge_after_route(state) -> Literal["node_sql", "node_sql_denied", "node_retrieve"]:
    route = state["route"]
    if route == "sql":        return "node_sql"
    if route == "sql_denied": return "node_sql_denied"
    return "node_retrieve"
```

This is the branching point. LangGraph calls this function after `node_route` and uses the return value to select the next node.

---

## Graph compilation and entry point

```python
medibot_graph = build_graph()   # module-level compiled graph

def run_query(question: str, role: str) -> ChatResponse:
    initial_state = {
        "question": question, "role": role,
        "route": "", "documents": [], "answer": "",
        "sources": [], "retrieval_type": "hybrid_rag",
    }
    final_state = medibot_graph.invoke(initial_state)
    return ChatResponse(
        answer=final_state["answer"],
        sources=[SourceCitation(**s) for s in final_state["sources"]],
        retrieval_type=final_state["retrieval_type"],
        role=role,
    )
```

`run_query()` is the single entry point called by `api/routes/chat.py`. The graph is compiled once at module import and reused across all requests.

---

## Why LangGraph?

A plain function calling other functions would work but the flow becomes implicit. LangGraph makes routing, branching, and state passing **explicit and inspectable**:

- Each node is a named, testable unit
- The graph topology is declared separately from node logic
- The `sql_denied` path is a first-class node, not a buried `if` inside a helper
- Future extensions (e.g. adding a clarification node, a guardrails node) are additive — no refactoring of existing nodes

---

## Source

- Graph: [`rag/graph.py`](../../rag/graph.py)
- Entry point: `run_query()` called from [`api/routes/chat.py`](../../api/routes/chat.py)
