from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_role
from core.schemas import ChatRequest, ChatResponse
from rag.graph import run_query

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, role: str = Depends(get_current_role)) -> ChatResponse:
    """
    Main RAG endpoint.
    Role is always taken from the JWT token — body.role is ignored
    so clients cannot escalate their own privileges.
    """
    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty",
        )
    return run_query(question=body.question.strip(), role=role)
