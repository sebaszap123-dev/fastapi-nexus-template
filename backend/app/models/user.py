import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class User(Base):
    """
    User model for authentication and user management.

    Attributes:
        id: UUID primary key
        email: Unique email address
        hashed_password: Bcrypt hashed password
        is_active: Whether the user account is active
        is_superuser: Whether the user has admin privileges
        is_email_verified: Whether email has been verified
        email_verified_at: When email was verified
        is_deleted: Soft delete flag
        deleted_at: When account was marked for deletion
        deletion_scheduled_for: When account will be permanently deleted (30 days)
        password_changed_at: Last password change timestamp
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Email verification
    is_email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), default=None, nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, default=False, index=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), default=None, nullable=True)
    deletion_scheduled_for = Column(
        DateTime(timezone=True), default=None, nullable=True
    )

    # Password tracking
    password_changed_at = Column(DateTime(timezone=True), default=None, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    def verify_email(self) -> None:
        """Mark email as verified."""
        self.is_email_verified = True
        self.email_verified_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def schedule_deletion(self, days: int = 30) -> None:
        """Schedule account for deletion."""
        now = datetime.now(UTC)
        self.is_deleted = True
        self.deleted_at = now
        self.deletion_scheduled_for = now + timedelta(days=days)
        self.updated_at = now

    def cancel_deletion(self) -> None:
        """Cancel scheduled deletion."""
        self.is_deleted = False
        self.deleted_at = None
        self.deletion_scheduled_for = None
        self.updated_at = datetime.now(UTC)

    def update_password(self) -> None:
        """Update password change timestamp."""
        self.password_changed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def __repr__(self) -> str:
        return f"<User {self.email}>"
