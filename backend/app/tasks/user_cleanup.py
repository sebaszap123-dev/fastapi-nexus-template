"""
Celery tasks for user cleanup and maintenance.

Handles:
- Permanent deletion of soft-deleted users after grace period
- Sending deletion reminder emails
- Cleanup of expired tokens
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email import EmailService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Create async engine for tasks
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Initialize email service
email_service = EmailService()


@celery_app.task(name="user_cleanup.delete_expired_users")
def delete_expired_users():
    """
    Permanently delete users whose deletion grace period has expired.

    Runs daily to check for users whose deletion_scheduled_for date has passed.
    """
    import asyncio

    async def _delete_expired():
        async with AsyncSessionLocal() as session:
            now = datetime.now(UTC)

            # Find users scheduled for deletion whose time has come
            result = await session.execute(
                select(User)
                .where(User.is_deleted)
                .where(User.deletion_scheduled_for <= now)
            )
            users_to_delete = result.scalars().all()

            deleted_count = 0
            for user in users_to_delete:
                email = user.email
                logger.info(f"Permanently deleting user: {email}")

                # Delete user (CASCADE will handle related records)
                await session.delete(user)
                deleted_count += 1

            if deleted_count > 0:
                await session.commit()
                logger.info(f"Permanently deleted {deleted_count} user(s)")
            else:
                logger.info("No users to permanently delete")

            return deleted_count

    return asyncio.run(_delete_expired())


@celery_app.task(name="user_cleanup.send_deletion_reminders")
def send_deletion_reminders():
    """
    Send reminder emails to users 7 days before permanent deletion.

    Checks for users whose deletion is scheduled 7 days from now.
    """
    import asyncio

    async def _send_reminders():
        async with AsyncSessionLocal() as session:
            now = datetime.now(UTC)
            reminder_threshold = now + timedelta(days=7)

            # Find users scheduled for deletion in 7 days
            # We check for a 24-hour window to avoid missing anyone
            start_window = reminder_threshold - timedelta(hours=12)
            end_window = reminder_threshold + timedelta(hours=12)

            result = await session.execute(
                select(User)
                .where(User.is_deleted)
                .where(User.deletion_scheduled_for >= start_window)
                .where(User.deletion_scheduled_for <= end_window)
            )
            users = result.scalars().all()

            sent_count = 0
            for user in users:
                # Calculate days remaining (rounded)
                days_remaining = (user.deletion_scheduled_for - now).days

                try:
                    # Create cancel link
                    cancel_token = EmailVerificationToken.generate_token()
                    cancel_link = f"{settings.FRONTEND_URL}/cancel-deletion?token={cancel_token}"

                    # Send reminder email
                    email_service.send_deletion_reminder_email(
                        user.email,
                        user.email.split("@")[0],
                        days_remaining,
                        cancel_link,
                    )
                    sent_count += 1
                    logger.info(f"Sent deletion reminder to: {user.email}")
                except Exception as e:
                    logger.error(f"Failed to send deletion reminder to {user.email}: {e}")

            logger.info(f"Sent {sent_count} deletion reminder email(s)")
            return sent_count

    return asyncio.run(_send_reminders())


@celery_app.task(name="user_cleanup.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """
    Delete expired email verification and password reset tokens.

    Runs daily to clean up the database from old tokens.
    """
    import asyncio

    async def _cleanup_tokens():
        async with AsyncSessionLocal() as session:
            now = datetime.now(UTC)

            # Delete expired email verification tokens
            email_result = await session.execute(
                select(EmailVerificationToken).where(EmailVerificationToken.expires_at < now)
            )
            email_tokens = email_result.scalars().all()

            for token in email_tokens:
                await session.delete(token)

            # Delete expired password reset tokens
            password_result = await session.execute(
                select(PasswordResetToken).where(PasswordResetToken.expires_at < now)
            )
            password_tokens = password_result.scalars().all()

            for token in password_tokens:
                await session.delete(token)

            total_deleted = len(email_tokens) + len(password_tokens)

            if total_deleted > 0:
                await session.commit()
                logger.info(
                    f"Cleaned up {len(email_tokens)} email verification tokens "
                    f"and {len(password_tokens)} password reset tokens"
                )
            else:
                logger.info("No expired tokens to clean up")

            return total_deleted

    return asyncio.run(_cleanup_tokens())
