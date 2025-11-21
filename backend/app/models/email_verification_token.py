import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class EmailVerificationToken(Base):
    """
    Email verification token model.

    Tokens are hashed before storage for security.
    Default expiration: 24 hours.

    Attributes:
        id: UUID primary key
        token_hash: SHA256 hash of the verification token
        user_id: Foreign key to users table
        is_used: Whether the token has been used
        created_at: Token creation timestamp
        expires_at: Token expiration timestamp
        used_at: When the token was used (if applicable)
    """

    __tablename__ = "email_verification_tokens"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    token_hash = Column(
        String(64),  # SHA256 hex digest
        unique=True,
        index=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), default=None, nullable=True)

    @staticmethod
    def generate_token() -> str:
        """
        Generate a secure random token.

        Returns:
            URL-safe token string (32 bytes = 43 chars base64)
        """
        return secrets.token_urlsafe(32)

    def mark_as_used(self) -> None:
        """Mark this token as used."""
        self.is_used = True
        self.used_at = datetime.now(UTC)

    def is_expired(self) -> bool:
        """Check if this token has expired."""
        return datetime.now(UTC) > self.expires_at

    def is_valid(self) -> bool:
        """Check if this token is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired()

    def __repr__(self) -> str:
        return f"<EmailVerificationToken user_id={self.user_id}>"
