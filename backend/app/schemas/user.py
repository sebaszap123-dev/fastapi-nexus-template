import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength.

        Requirements:
        - Minimum 8 characters
        - At least one number or special character
        """
        if not any(char.isdigit() or not char.isalnum() for char in v):
            raise ValueError(
                "Password must contain at least one number or special character"
            )
        return v


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class TokenPair(BaseModel):
    """
    Schema for access and refresh token pair.

    Note: The refresh_token is also set in an HttpOnly cookie,
    but we return it here for flexibility in client implementations.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    """Schema for access token only (used in refresh endpoint)."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Schema for user data in responses."""

    id: uuid.UUID
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class EmailVerificationRequest(BaseModel):
    """Schema for requesting email verification resend."""

    email: EmailStr


class VerifyEmailRequest(BaseModel):
    """Schema for verifying email with token."""

    token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    """Schema for requesting password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for resetting password with token."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength.

        Requirements:
        - Minimum 8 characters
        - At least one number or special character
        """
        if not any(char.isdigit() or not char.isalnum() for char in v):
            raise ValueError(
                "Password must contain at least one number or special character"
            )
        return v


class ChangePasswordRequest(BaseModel):
    """Schema for changing password when authenticated."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength.

        Requirements:
        - Minimum 8 characters
        - At least one number or special character
        """
        if not any(char.isdigit() or not char.isalnum() for char in v):
            raise ValueError(
                "Password must contain at least one number or special character"
            )
        return v


class DeleteAccountRequest(BaseModel):
    """Schema for requesting account deletion."""

    password: str
    confirm: bool = Field(
        description="User must confirm they understand account will be deleted"
    )

    @field_validator("confirm")
    @classmethod
    def validate_confirm(cls, v: bool) -> bool:
        """Ensure user confirmed deletion."""
        if not v:
            raise ValueError("You must confirm account deletion")
        return v


class UserDetailedResponse(UserResponse):
    """Extended user response with verification and deletion status."""

    is_email_verified: bool
    email_verified_at: Optional[datetime] = None
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    deletion_scheduled_for: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
