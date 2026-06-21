# MediBot — Project Knowledge Base

## Repo
https://github.com/smakireddy/medibot-project (public)

## Stack decisions (locked in)
- **Vector DB**: Qdrant Cloud — no local/Docker Qdrant. URL in `.env` as `QDRANT_URL`
- **Reranker**: `sentence_transformers.CrossEncoder` with `BAAI/bge-reranker-base` — NOT `FlagReranker` (breaks with transformers 5.8.x: `XLMRobertaTokenizer has no attribute prepare_for_model`)
- **Password hashing**: `bcrypt` directly — NOT `passlib` (passlib breaks with bcrypt>=4.x)
- **LLM**: Groq `llama-3.1-8b-instant` (default), switchable via `LLM_PROVIDER` in `.env`
- **No Docker** — user explicitly does not use Docker

## Demo credentials
| Username | Password | Role |
|---|---|---|
| dr.mehta | doctor123 | doctor |
| nurse.priya | nurse123 | nurse |
| billing.ravi | billing123 | billing_executive |
| tech.anand | tech123 | technician |
| admin.sys | admin123 | admin |

## Launch commands
```bash
# Backend
./launch.sh --api

# Frontend
./launch.sh --frontend

# Ingest documents
./launch.sh --ingest
```

## Architecture
- **Hybrid RAG**: dense (BGE-small-en-v1.5) + BM25 sparse vectors, single `query_points` call with RRF fusion
- **RBAC**: `access_roles` payload field in Qdrant, `MatchAny` filter applied server-side — restricted chunks never reach the app
- **LangGraph**: 6 nodes — `node_route → node_retrieve → node_rerank → node_generate` (or `node_sql` / `node_sql_denied`)
- **JWT**: role extracted from token only, never from request body (prevents role escalation)
- **SQL RAG**: NL→SQL→execute→NL, restricted to `billing_executive` and `admin` roles

## RBAC — role → collections
| Role | Collections |
|---|---|
| doctor | general, clinical, nursing |
| nurse | general, nursing |
| billing_executive | general, billing |
| technician | general, equipment |
| admin | all |

## Key files
- `rag/graph.py` — LangGraph pipeline, `run_query()` entry point
- `rag/retrieval.py` — hybrid Qdrant retrieval + RBAC filter
- `rag/rerank.py` — CrossEncoder reranking
- `rag/router.py` — two-stage routing (keyword regex + LLM fallback)
- `rag/sql_rag.py` — SQL RAG chain (SELECT-only, read-only SQLite connection)
- `core/access.py` — `ROLE_COLLECTIONS` map, `SQL_ALLOWED_ROLES`
- `core/config.py` — all settings via pydantic-settings + `.env`
- `api/auth.py` — bcrypt verify, JWT sign/decode
- `api/dependencies.py` — `get_current_role()` DI, rejects unknown roles with 403

## Security fixes applied
- `rag/sql_rag.py`: LLM-generated SQL validated as SELECT/WITH only; SQLite opened in read-only URI mode
- `core/config.py`: startup warning if `JWT_SECRET` is weak default or < 32 chars
- `api/dependencies.py`: 403 on unrecognised role claim in JWT
- `core/schemas.py`: `question` capped at 2000 chars
- `.gitignore`: `frontend/.env.local` and `node_modules/` excluded

## Known gaps (not yet fixed)
- README Setup & Installation still mentions Docker
- No `test_rerank.py` in test suite
- Demo passwords in README say `demo123` — actual passwords are role-specific (see table above)
