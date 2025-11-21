import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import RedisClient, get_redis_client
from app.core.security import decode_token, hash_token, verify_token_scope
from app.db.session import get_session
from app.models.user import User

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
    redis: RedisClient = Depends(get_redis_client),
) -> User:
    """
    Dependency to get the current authenticated user from access token.

    Validates:
    1. Token is properly formatted and signed
    2. Token has "access" scope
    3. Token is not blacklisted (logged out)
    4. All user tokens are not revoked (reuse detection)
    5. User exists and is active

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}

    Raises:
        HTTPException: 401 if authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode and verify token
    token = credentials.credentials
    token_payload = decode_token(token)

    if token_payload is None:
        raise credentials_exception

    # Verify token scope
    if not verify_token_scope(token_payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token scope",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID
    user_id_str: Optional[str] = token_payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    # Check if token is blacklisted
    token_hash_value = hash_token(token)
    if await redis.is_token_blacklisted(token_hash_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if all user tokens are revoked (reuse detection)
    if await redis.are_user_tokens_revoked(str(user_id)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="All tokens have been revoked. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get the current authenticated superuser.

    Usage:
        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: uuid.UUID,
            admin: User = Depends(get_current_superuser)
        ):
            ...

    Raises:
        HTTPException: 403 if user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user
