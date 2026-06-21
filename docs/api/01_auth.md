# Authentication (`api/auth.py` + `api/routes/auth.py`)

## What it does

Handles user identity: stores demo credentials, verifies passwords with bcrypt, and issues signed JWT tokens that carry the user's role.

---

## Demo user store

```python
DEMO_USERS: dict[str, dict] = {
    "dr.mehta":     {"hashed": _hash("doctor123"),  "role": "doctor"},
    "nurse.priya":  {"hashed": _hash("nurse123"),   "role": "nurse"},
    "billing.ravi": {"hashed": _hash("billing123"), "role": "billing_executive"},
    "tech.anand":   {"hashed": _hash("tech123"),    "role": "technician"},
    "admin.sys":    {"hashed": _hash("admin123"),   "role": "admin"},
}
```

Passwords are hashed with bcrypt at **module load time** — plain-text passwords never exist after startup. The `_hash()` call runs once per user when the module is imported.

### Why bcrypt directly (not passlib)?

`passlib` wraps bcrypt but breaks with `bcrypt >= 4.x` due to an API change. Using `bcrypt` directly avoids this dependency conflict while providing the same security.

---

## Password verification — `verify_user()`

```python
def verify_user(username: str, password: str) -> dict | None:
    user = DEMO_USERS.get(username)
    if not user:
        return None                          # unknown username
    if not _verify(password, user["hashed"]):
        return None                          # wrong password
    return user                              # {"role": "doctor", "name": "Dr. Mehta"}
```

`bcrypt.checkpw()` compares the submitted password against the stored hash in constant time — no timing attack surface.

Both unknown username and wrong password return `None` (and the route returns `401`) — no difference in response that would reveal whether the username exists.

---

## JWT creation — `create_access_token()`

```python
def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=480)  # 8 hours
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
```

The JWT payload contains:

| Claim | Value | Purpose |
|---|---|---|
| `sub` | `"dr.mehta"` | Standard subject claim — identifies the user |
| `role` | `"doctor"` | Drives all RBAC decisions downstream |
| `exp` | UTC timestamp | Token expires after 8 hours |

Signed with `HS256` using `JWT_SECRET` from `.env`. The signature makes the token tamper-proof — any modification invalidates it.

---

## Login route — `POST /login`

```
POST /login
Body: { "username": "dr.mehta", "password": "doctor123" }

200 OK → { "access_token": "<jwt>", "role": "doctor", "username": "dr.mehta" }
401    → { "detail": "Invalid username or password" }
```

```python
@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    user = verify_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(username=body.username, role=user["role"])
    return LoginResponse(access_token=token, role=user["role"], username=body.username)
```

The frontend stores the token and attaches it as `Authorization: Bearer <token>` on every subsequent request.

---

## Token decoding — `decode_token()`

```python
def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
```

Raises `JWTError` if the token is expired, malformed, or the signature doesn't match. The dependency layer (`api/dependencies.py`) catches this and returns `401`.

---

## Source

- Auth helpers: [`api/auth.py`](../../api/auth.py)
- Login route: [`api/routes/auth.py`](../../api/routes/auth.py)
- Schemas: [`core/schemas.py`](../../core/schemas.py)
