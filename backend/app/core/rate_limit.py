"""
Rate limiting configuration using slowapi and Redis.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.redis_client import RedisClient


def get_redis_storage():
    """
    Get Redis storage backend for rate limiting.
    Uses the same Redis instance as token blacklist.
    """
    # slowapi expects a redis-py client, not aioredis
    # We'll use the synchronous redis client for rate limiting
    import redis
    
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


# Create limiter instance with Redis storage
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=["200/minute"],  # Global rate limit
    enabled=True,
)


# Predefined rate limit decorators for common use cases
class RateLimits:
    """Centralized rate limit definitions"""

    # Authentication endpoints
    REGISTER = "5/hour"  # Prevent mass account creation
    LOGIN = "10/hour"  # Prevent brute force
    LOGOUT = "20/hour"  # Normal usage
    REFRESH = "30/hour"  # Token refresh

    # Password management
    FORGOT_PASSWORD = "3/hour"  # Prevent abuse
    RESET_PASSWORD = "5/hour"  # Limited attempts
    CHANGE_PASSWORD = "5/hour"  # Limited changes

    # Email verification
    VERIFY_EMAIL = "10/day"  # Limited verifications
    RESEND_VERIFICATION = "3/hour"  # Prevent spam

    # Account management
    DELETE_ACCOUNT = "2/day"  # Prevent accidental deletions
    CANCEL_DELETION = "5/day"  # Allow cancellation
    LOGOUT_ALL = "3/hour"  # Prevent abuse

    # General API
    DEFAULT = "60/minute"  # Default for most endpoints
    STRICT = "10/minute"  # Strict limit for sensitive ops
