# JWT Dependency Injection (`api/dependencies.py`)

## What it does

Provides FastAPI dependencies that extract and validate the JWT on every protected request. Routes declare these as parameters — FastAPI calls them automatically before the route handler runs.

---

## `get_current_role()` — the primary dependency

```python
_bearer = HTTPBearer()

def get_current_role(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    try:
        payload = decode_token(credentials.credentials)
        role: str | None = payload.get("role")
        if not role:
            raise HTTPException(status_code=401, detail="Token missing role claim")
        return role
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
```

**What it does step by step:**
1. `HTTPBearer()` extracts the `Authorization: Bearer <token>` header — returns `401` automatically if the header is absent
2. `decode_token()` verifies the JWT signature and expiry — raises `JWTError` if invalid
3. Extracts the `role` claim from the payload
4. Returns the role string to the route handler

---

## Why role comes from the token, not the request body

The `/chat` route receives a `ChatRequest` body that has a `role` field (for schema completeness), but the route handler ignores it entirely:

```python
@router.post("/chat")
def chat(body: ChatRequest, role: str = Depends(get_current_role)):
    # role = from JWT, always
    # body.role = ignored
    return run_query(question=body.question.strip(), role=role)
```

A client that sends `{"question": "...", "role": "admin"}` while holding a nurse token will have their `role` claim read as `"nurse"` — the body field is silently discarded.

This is the **role escalation prevention** mechanism. The role is cryptographically bound to the token; the body is untrusted input.

---

## `get_current_username()` — secondary dependency

```python
def get_current_username(credentials: ...) -> str:
    payload = decode_token(credentials.credentials)
    return payload.get("sub", "unknown")
```

Returns the `sub` claim (username). Used where the username is needed alongside the role — e.g., audit logging.

---

## HTTP status codes

| Scenario | Code | Why |
|---|---|---|
| No `Authorization` header | `401` | `HTTPBearer` returns 401 for missing credentials |
| Expired token | `401` | `JWTError` from `decode_token` |
| Invalid signature | `401` | `JWTError` from `decode_token` |
| Valid token, wrong role for endpoint | `403` | Route handler logic (e.g., `/collections/{role}`) |

`401` = unauthenticated (no valid identity established).
`403` = authenticated but not authorised for the specific resource.

---

## Source

- Dependency: [`api/dependencies.py`](../../api/dependencies.py)
- Used in: [`api/routes/chat.py`](../../api/routes/chat.py), [`api/routes/collections.py`](../../api/routes/collections.py)
