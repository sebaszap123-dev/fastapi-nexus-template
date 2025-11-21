import logging
from datetime import timedelta
from typing import Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client for token blacklist and caching.

    This implements a token blacklist for:
    - Revoked access tokens
    - Revoked refresh tokens
    - Logout functionality

    Tokens are stored with TTL matching their expiration time,
    so they automatically clean up after expiration.
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Redis client connected successfully")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis client disconnected")

    async def ping(self) -> bool:
        """
        Check if Redis is available.

        Returns:
            True if Redis responds to ping, False otherwise
        """
        try:
            if self._client:
                return await self._client.ping()
            return False
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    async def blacklist_token(
        self,
        token_hash: str,
        expires_in_seconds: int,
    ) -> bool:
        """
        Add a token to the blacklist.

        Args:
            token_hash: SHA256 hash of the token
            expires_in_seconds: Time until token expires (TTL)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._client:
                await self.connect()

            key = f"blacklist:{token_hash}"
            await self._client.setex(
                key,
                expires_in_seconds,
                "revoked",
            )
            logger.info(f"Token blacklisted: {token_hash[:16]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    async def is_token_blacklisted(self, token_hash: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token_hash: SHA256 hash of the token

        Returns:
            True if token is blacklisted, False otherwise
        """
        try:
            if not self._client:
                await self.connect()

            key = f"blacklist:{token_hash}"
            exists = await self._client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            # Fail secure: if Redis is down, reject the token
            return True

    async def revoke_all_user_tokens(self, user_id: str) -> bool:
        """
        Revoke all tokens for a user (used when token reuse is detected).

        Args:
            user_id: User ID whose tokens should be revoked

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._client:
                await self.connect()

            key = f"revoke_all:{user_id}"
            # Set with 7 days expiration (max refresh token lifetime)
            await self._client.setex(
                key,
                timedelta(days=7),
                "revoked",
            )
            logger.warning(f"All tokens revoked for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke all user tokens: {e}")
            return False

    async def are_user_tokens_revoked(self, user_id: str) -> bool:
        """
        Check if all tokens for a user have been revoked.

        Args:
            user_id: User ID to check

        Returns:
            True if all user tokens are revoked, False otherwise
        """
        try:
            if not self._client:
                await self.connect()

            key = f"revoke_all:{user_id}"
            exists = await self._client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Failed to check user token revocation: {e}")
            # Fail secure: if Redis is down, reject the token
            return True


# Global Redis client instance
redis_client = RedisClient()


async def get_redis_client() -> RedisClient:
    """
    Dependency for getting Redis client.

    Usage:
        @app.get("/some-endpoint")
        async def endpoint(redis: RedisClient = Depends(get_redis_client)):
            ...
    """
    if not redis_client._client:
        await redis_client.connect()
    return redis_client
