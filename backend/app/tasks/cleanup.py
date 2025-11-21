import logging
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.sql import select

from app.db.session import AsyncSessionLocal
from app.models.refresh_token import RefreshToken
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.cleanup.cleanup_expired_refresh_tokens")
def cleanup_expired_refresh_tokens() -> dict:
    """
    Periodic task to clean up expired refresh tokens from the database.

    This task runs every 6 hours (configured in Celery Beat schedule)
    and deletes all expired refresh tokens to keep the database clean.

    Returns:
        Dictionary with cleanup statistics
    """
    import asyncio

    async def do_cleanup():
        async with AsyncSessionLocal() as session:
            # Find all expired tokens
            now = datetime.now(UTC)
            result = await session.exec(
                select(RefreshToken).where(RefreshToken.expires_at < now)
            )
            expired_tokens = result.all()
            count = len(expired_tokens)

            if count > 0:
                # Delete expired tokens
                await session.exec(
                    delete(RefreshToken).where(RefreshToken.expires_at < now)
                )
                await session.commit()
                logger.info(f"Cleaned up {count} expired refresh tokens")
            else:
                logger.info("No expired refresh tokens to clean up")

            return {"deleted_count": count, "timestamp": now.isoformat()}

    # Run async cleanup
    return asyncio.run(do_cleanup())
