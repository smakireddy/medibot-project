from fastapi import APIRouter, HTTPException, status

from api.auth import verify_user, create_access_token
from core.schemas import LoginRequest, LoginResponse

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    user = verify_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(username=body.username, role=user["role"])
    return LoginResponse(
        access_token=token,
        role=user["role"],
        username=body.username,
    )
