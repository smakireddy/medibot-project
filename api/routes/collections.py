from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_role
from core.access import ROLE_COLLECTIONS, collections_for_role

router = APIRouter(tags=["collections"])


@router.get("/collections/{role}")
def get_collections(role: str, current_role: str = Depends(get_current_role)) -> dict:
    """
    Return the document collections accessible to a given role.
    A non-admin user can only query their own role's collections.
    """
    if role not in ROLE_COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown role '{role}'",
        )
    # Non-admin users cannot inspect other roles' access
    if current_role != "admin" and current_role != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own collections",
        )
    return {
        "role": role,
        "collections": collections_for_role(role),
    }
