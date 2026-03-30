"""
Supabase Auth JWT verification for FastAPI.

Usage in routers:
    from app.auth import get_current_user_id

    @router.get("/something")
    async def endpoint(user_id: uuid.UUID = Depends(get_current_user_id)):
        ...
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def _ensure_user_exists(user_id: uuid.UUID, email: str, db: AsyncSession) -> None:
    """Create a users row if one doesn't exist yet (first login after Supabase signup)."""
    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        db.add(User(id=user_id, email=email))
        await db.commit()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Validate the Supabase JWT from the Authorization header
    and return the user's UUID.

    Falls back to DEV_USER_ID when no auth header is present
    and no JWT_SECRET is configured (local dev convenience).
    """
    DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Dev mode: if no credentials and secret is the default, allow through
    if credentials is None:
        if settings.jwt_secret == "change-me-in-production":
            return DEV_USER_ID
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience="authenticated",
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    # Auto-create user row on first authenticated request
    email = payload.get("email", f"{sub}@unknown")
    await _ensure_user_exists(user_id, email, db)

    return user_id
