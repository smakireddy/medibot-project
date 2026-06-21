# API Routes (`api/routes/`)

## Overview

Four route modules, each mounted on the main FastAPI app in `api/main.py`. The app also calls `ensure_collection()` at startup via a lifespan hook to guarantee the Qdrant collection exists before the first request arrives.

```python
# api/main.py — startup hook
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_collection()   # creates Qdrant collection + access_roles index if missing
    yield
```

---

## `POST /login` — `api/routes/auth.py`

**Auth required:** No

```
POST /login
Body: { "username": "dr.mehta", "password": "doctor123" }

200 → { "access_token": "<jwt>", "role": "doctor", "username": "dr.mehta" }
401 → { "detail": "Invalid username or password" }
```

Calls `verify_user()` (bcrypt check) then `create_access_token()` (JWT sign). Both wrong username and wrong password return the same `401` response — no information leakage about whether the username exists.

---

## `POST /chat` — `api/routes/chat.py`

**Auth required:** Yes — `get_current_role()` dependency

```
POST /chat
Headers: Authorization: Bearer <jwt>
Body: { "question": "What is the ECG interpretation procedure?" }

200 → {
    "answer": "According to [1]...",
    "sources": [{ "source_document": "...", "section_title": "...", "collection": "..." }],
    "retrieval_type": "hybrid_rag" | "sql_rag",
    "role": "doctor"
}
401 → missing or invalid token
422 → empty question
```

```python
@router.post("/chat")
def chat(body: ChatRequest, role: str = Depends(get_current_role)):
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    return run_query(question=body.question.strip(), role=role)
```

The role is **always taken from the JWT** — `body.role` is ignored even if provided. This is the primary role-escalation prevention point. The entire RAG pipeline (`run_query`) executes in a thread pool via `run_in_threadpool` since it is synchronous.

---

## `GET /collections/{role}` — `api/routes/collections.py`

**Auth required:** Yes — `get_current_role()` dependency

```
GET /collections/nurse
Headers: Authorization: Bearer <jwt with role=nurse>

200 → { "role": "nurse", "collections": ["general", "nursing"] }
403 → nurse trying to inspect billing_executive's collections
404 → unknown role name
```

```python
@router.get("/collections/{role}")
def get_collections(role: str, current_role: str = Depends(get_current_role)):
    if role not in ROLE_COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown role '{role}'")
    if current_role != "admin" and current_role != role:
        raise HTTPException(status_code=403, detail="You can only view your own collections")
    return {"role": role, "collections": collections_for_role(role)}
```

A non-admin user can only query their **own** role — a nurse cannot inspect what collections a billing executive has. Admin can inspect any role. This prevents information gathering about the access matrix.

---

## `GET /health` — `api/routes/health.py`

**Auth required:** No

```
GET /health

200 → {
    "status": "ok",
    "qdrant": "ok",
    "collection": "medibot",
    "collections_found": ["medibot"],
    "llm_provider": "groq"
}
```

Calls `get_qdrant_client().get_collections()` to verify Qdrant is reachable. Returns `"status": "degraded"` (still HTTP 200) if Qdrant is down so the frontend can display a warning without breaking. Used by `launch.sh` to poll until the API is ready.

---

## CORS configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Permits the Next.js frontend on port 3000 to make cross-origin requests including the `Authorization` header. Restricted to localhost — no external origin is allowed.

---

## Source

- App factory + lifespan: [`api/main.py`](../../api/main.py)
- Login route: [`api/routes/auth.py`](../../api/routes/auth.py)
- Chat route: [`api/routes/chat.py`](../../api/routes/chat.py)
- Collections route: [`api/routes/collections.py`](../../api/routes/collections.py)
- Health route: [`api/routes/health.py`](../../api/routes/health.py)
