"""
FastAPI dependency injection.

get_current_role() is added to any route that needs authentication.
It extracts the role from the JWT token — callers cannot spoof their role
by passing it in the request body.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from api.auth import decode_token

_bearer = HTTPBearer()


def get_current_role(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Extract and validate JWT; return the role claim."""
    try:
        payload = decode_token(credentials.credentials)
        role: str | None = payload.get("role")
        if not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing role claim",
            )
        return role
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_username(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Extract the username (sub) claim from the JWT."""
    try:
        payload = decode_token(credentials.credentials)
        return payload.get("sub", "unknown")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
