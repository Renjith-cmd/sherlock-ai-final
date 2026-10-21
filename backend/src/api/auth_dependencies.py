"""FastAPI dependencies for user authentication and investigation ownership validation."""

from fastapi import Depends, HTTPException, Header, Request, status
from typing import Optional
from src.core.auth_security import User, decode_access_token
from src.core.database import DatabaseRepository
from src.core.models import Investigation, Entity, Relationship

repo = DatabaseRepository()


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> User:
    """
    Extracts and verifies the authenticated user from the Authorization header or session cookie.
    Returns the User model if valid; otherwise raises HTTPException 401.
    """
    token = None

    # 1. Bearer token in Authorization header
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()

    # 2. HttpOnly Cookie fallback
    if not token and "sherlock_ai_session" in request.cookies:
        token = request.cookies.get("sherlock_ai_session")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = repo.get_user_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or disabled.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


async def get_owned_investigation(
    inv_id: str,
    current_user: User = Depends(get_current_user)
) -> Investigation:
    """
    Strict ownership check: verifies the requested investigation exists AND belongs to the current user.
    Returns 404 if not found or unauthorized to prevent disclosing other users' case IDs.
    """
    inv = repo.get_investigation(inv_id, user_id=current_user.id)
    if not inv:
        # Generic 404 so IDs cannot be enumerated
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found"
        )
    return inv


async def get_owned_entity(
    entity_id: str,
    current_user: User = Depends(get_current_user)
) -> Entity:
    """
    Verifies that the requested entity belongs to an investigation owned by the current user.
    """
    entity = repo.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    # Verify parent investigation ownership
    inv = repo.get_investigation(entity.investigation_id, user_id=current_user.id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    return entity


async def get_owned_relationship(
    rel_id: str,
    current_user: User = Depends(get_current_user)
) -> Relationship:
    """
    Verifies that the requested relationship belongs to an investigation owned by the current user.
    """
    rel = repo.get_relationship(rel_id)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")

    # Verify parent investigation ownership
    inv = repo.get_investigation(rel.investigation_id, user_id=current_user.id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")

    return rel


async def get_owned_document(
    doc_id: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Verifies that the requested document belongs to an investigation owned by the current user.
    """
    doc = repo.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Verify parent investigation ownership
    inv = repo.get_investigation(doc["investigation_id"], user_id=current_user.id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return doc
