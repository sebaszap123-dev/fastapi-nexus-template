import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class RefreshToken(Base):
    """
    Refresh token model for tracking and rotating refresh tokens.

    This enables:
    - Token rotation: Each refresh generates a new token
    - Reuse detection: If an old token is used, we can detect and revoke all user tokens
    - Token family tracking: Tokens are linked by family_id for revocation

    Attributes:
        id: UUID primary key
        token_hash: SHA256 hash of the refresh token (never store plain tokens)
        user_id: Foreign key to users table
        family_id: UUID linking related tokens (for rotation chains)
        is_revoked: Whether this token has been revoked
        created_at: Token creation timestamp
        expires_at: Token expiration timestamp
        revoked_at: When the token was revoked (if applicable)
    """

    __tablename__ = "refresh_tokens"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    token_hash = Column(
        String(64),  # SHA256 hex digest is 64 chars
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
    family_id = Column(
        UUID(as_uuid=True),
        index=True,
        nullable=False,
    )
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=None, nullable=True)

    def revoke(self) -> None:
        """Mark this token as revoked."""
        self.is_revoked = True
        self.revoked_at = datetime.now(UTC)

    def is_expired(self) -> bool:
        """Check if this token has expired."""
        return datetime.now(UTC) > self.expires_at

    def is_valid(self) -> bool:
        """Check if this token is valid (not revoked and not expired)."""
        return not self.is_revoked and not self.is_expired()

    def __repr__(self) -> str:
        return f"<RefreshToken user_id={self.user_id} family_id={self.family_id}>"
