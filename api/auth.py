"""
Auth helpers — JWT creation/decoding and demo user store.

Demo credentials (all roles covered):
  dr.mehta       / doctor123      → doctor
  nurse.priya    / nurse123       → nurse
  billing.ravi   / billing123     → billing_executive
  tech.anand     / tech123        → technician
  admin.sys      / admin123       → admin
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from core.config import settings


def _hash(password: str) -> bytes:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


def _verify(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode(), hashed)


# Pre-hashed at module load — never store plain text in production
DEMO_USERS: dict[str, dict] = {
    "dr.mehta":     {"hashed": _hash("doctor123"),  "role": "doctor",            "name": "Dr. Mehta"},
    "nurse.priya":  {"hashed": _hash("nurse123"),   "role": "nurse",             "name": "Nurse Priya"},
    "billing.ravi": {"hashed": _hash("billing123"), "role": "billing_executive", "name": "Ravi (Billing)"},
    "tech.anand":   {"hashed": _hash("tech123"),    "role": "technician",        "name": "Anand (Tech)"},
    "admin.sys":    {"hashed": _hash("admin123"),   "role": "admin",             "name": "System Admin"},
}


def verify_user(username: str, password: str) -> dict | None:
    user = DEMO_USERS.get(username)
    if not user:
        return None
    if not _verify(password, user["hashed"]):
        return None
    return user


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
