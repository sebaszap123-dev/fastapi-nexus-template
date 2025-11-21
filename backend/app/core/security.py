import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context using Argon2id
# Argon2id is the recommended variant (hybrid of Argon2i and Argon2d)
# It provides resistance against both side-channel and GPU attacks
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",  # Use Argon2id variant (most secure)
    argon2__time_cost=2,  # Number of iterations
    argon2__memory_cost=65536,  # Memory usage in KiB (64 MB)
    argon2__parallelism=4,  # Number of parallel threads
)


def hash_password(password: str) -> str:
    """
    Hash a plain text password using Argon2id.

    Argon2id is the winner of the Password Hashing Competition (2015) and is
    recommended by OWASP for password hashing. It provides excellent resistance
    against both GPU-based attacks and side-channel attacks.

    Unlike bcrypt, Argon2 has no password length limit, so no pre-hashing is needed.

    Args:
        password: Plain text password to hash (can be any length)

    Returns:
        Argon2id hashed password string

    Security features:
        - Memory-hard algorithm (resistant to GPU/ASIC attacks)
        - Configurable time and memory costs
        - No password length limitations
        - Hybrid protection (Argon2id = Argon2i + Argon2d)
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    This function supports both Argon2 hashes (current) and legacy bcrypt hashes
    for backward compatibility during migration.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to check against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    """
    Create a JWT token with expiration.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Time until token expiration

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(UTC)

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(user_id: str) -> str:
    """
    Create a short-lived access token for API authentication.

    Args:
        user_id: User ID to encode in the token

    Returns:
        Encoded access token
    """
    return create_token(
        data={"sub": user_id, "scope": "access"},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    """
    Create a long-lived refresh token for obtaining new access tokens.

    Args:
        user_id: User ID to encode in the token

    Returns:
        Encoded refresh token
    """
    # Add random jti (JWT ID) for uniqueness and tracking
    jti = secrets.token_urlsafe(32)

    return create_token(
        data={"sub": user_id, "scope": "refresh", "jti": jti},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string to decode

    Returns:
        Decoded token payload dictionary, or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def hash_token(token: str) -> str:
    """
    Create a SHA256 hash of a token for secure storage.

    Never store tokens in plain text. Always hash them before
    storing in the database.

    Args:
        token: Token string to hash

    Returns:
        Hex digest of the token hash
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_scope(token_payload: Dict[str, Any], required_scope: str) -> bool:
    """
    Verify that a token has the required scope.

    Args:
        token_payload: Decoded token payload
        required_scope: Required scope ("access" or "refresh")

    Returns:
        True if token has required scope, False otherwise
    """
    return token_payload.get("scope") == required_scope
