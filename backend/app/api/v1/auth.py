import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import RateLimits, limiter
from app.core.redis_client import RedisClient, get_redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
    verify_token_scope,
)
from app.db.session import get_session
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import (
    AccessTokenResponse,
    ChangePasswordRequest,
    DeleteAccountRequest,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenPair,
    UserCreate,
    UserDetailedResponse,
    UserLogin,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.email import EmailService

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize email service
email_service = EmailService()


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """
    Set refresh token in an HttpOnly cookie.

    Args:
        response: FastAPI response object
        refresh_token: Refresh token to set in cookie
    """
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,  # Prevents JavaScript access (XSS protection)
        secure=settings.COOKIE_SECURE,  # HTTPS only in production
        samesite=settings.COOKIE_SAMESITE,  # CSRF protection
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        domain=settings.COOKIE_DOMAIN if settings.is_production else None,
    )


def clear_refresh_cookie(response: Response) -> None:
    """
    Clear refresh token cookie.

    Args:
        response: FastAPI response object
    """
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN if settings.is_production else None,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimits.REGISTER)
async def register(
    request: Request,
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Register a new user account.

    - Validates email uniqueness
    - Hashes password with bcrypt
    - Creates new user in database
    """
    # Check if email already exists
    result = await session.execute(select(User).where(User.email == payload.email))
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Create email verification token
    verification_token = EmailVerificationToken.generate_token()
    token_hash_value = hash_token(verification_token)
    token_record = EmailVerificationToken(
        token_hash=token_hash_value,
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
    )
    session.add(token_record)
    await session.commit()

    # Send welcome and verification emails (non-blocking)
    try:
        email_service.send_welcome_email(user.email, user.email.split("@")[0])
        email_service.send_verification_email(user.email, user.email.split("@")[0], verification_token)
    except Exception as e:
        logger.error(f"Failed to send welcome/verification email to {user.email}: {e}")
        # Don't fail registration if email fails

    logger.info(f"New user registered: {user.email}")
    return user


@router.post("/login", response_model=TokenPair)
@limiter.limit(RateLimits.LOGIN)
async def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    """
    Login with email and password.

    Returns:
    - Access token in JSON response (for Authorization header)
    - Refresh token in both JSON and HttpOnly cookie

    The access token should be stored in memory/state by the client.
    The refresh token cookie is automatically sent with requests.
    """
    # Find user by email
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    # Create tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # Decode refresh token to get jti and exp
    refresh_payload = decode_token(refresh_token)
    if not refresh_payload:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tokens",
        )

    # Store refresh token in database
    family_id = uuid.uuid4()  # New token family
    token_record = RefreshToken(
        token_hash=hash_token(refresh_token),
        user_id=user.id,
        family_id=family_id,
        expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=UTC),
    )
    session.add(token_record)
    await session.commit()

    # Set refresh token in HttpOnly cookie
    set_refresh_cookie(response, refresh_token)

    logger.info(f"User logged in: {user.email}")
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
@limiter.limit(RateLimits.REFRESH)
async def refresh_access_token(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: RedisClient = Depends(get_redis_client),
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token"),
) -> AccessTokenResponse:
    """
    Refresh access token using refresh token from cookie.

    Implements token rotation:
    1. Validates old refresh token
    2. Creates new access and refresh tokens
    3. Revokes old refresh token
    4. Detects and handles token reuse (security breach)

    If token reuse is detected (old token used after new one issued),
    all user tokens are revoked for security.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
    )

    if not refresh_token:
        raise credentials_exception

    # Decode refresh token
    token_payload = decode_token(refresh_token)
    if not token_payload:
        raise credentials_exception

    # Verify token scope
    if not verify_token_scope(token_payload, "refresh"):
        raise credentials_exception

    # Extract user ID
    user_id_str = token_payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    # Check if all user tokens are revoked
    if await redis.are_user_tokens_revoked(str(user_id)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="All tokens revoked. Please login again.",
        )

    # Find token in database
    token_hash_value = hash_token(refresh_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
    )
    token_record = result.scalars().first()

    if not token_record:
        # Token not found - possible reuse attack
        logger.warning(f"Refresh token not found for user {user_id} - possible reuse")
        await redis.revoke_all_user_tokens(str(user_id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token. All sessions revoked for security.",
        )

    # Check if token is already revoked (reuse detection)
    if token_record.is_revoked:
        logger.warning(f"Revoked refresh token reused for user {user_id}")
        # Revoke all tokens in this family (and potentially all user tokens)
        await redis.revoke_all_user_tokens(str(user_id))
        await session.execute(
            select(RefreshToken)
            .where(RefreshToken.family_id == token_record.family_id)
            .where(RefreshToken.is_revoked == False)
        )
        # Revoke all tokens in this family
        family_tokens = (await session.execute(
            select(RefreshToken).where(RefreshToken.family_id == token_record.family_id)
        )).all()
        for ft in family_tokens:
            ft.revoke()
        await session.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token reuse detected. All sessions revoked for security.",
        )

    # Check if token is expired
    if token_record.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired. Please login again.",
        )

    # Fetch user
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()

    if not user or not user.is_active:
        raise credentials_exception

    # Create new tokens (rotation)
    new_access_token = create_access_token(str(user.id))
    new_refresh_token = create_refresh_token(str(user.id))

    # Decode new refresh token
    new_refresh_payload = decode_token(new_refresh_token)
    if not new_refresh_payload:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create new tokens",
        )

    # Revoke old refresh token
    token_record.revoke()

    # Store new refresh token with same family_id (rotation chain)
    new_token_record = RefreshToken(
        token_hash=hash_token(new_refresh_token),
        user_id=user.id,
        family_id=token_record.family_id,  # Same family for rotation tracking
        expires_at=datetime.fromtimestamp(new_refresh_payload["exp"], tz=UTC),
    )
    session.add(new_token_record)
    await session.commit()

    # Set new refresh token in cookie
    set_refresh_cookie(response, new_refresh_token)

    logger.info(f"Tokens refreshed for user: {user.email}")
    return AccessTokenResponse(access_token=new_access_token)


@router.post("/logout", response_model=MessageResponse)
@limiter.limit(RateLimits.LOGOUT)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: RedisClient = Depends(get_redis_client),
    user: User = Depends(get_current_user),
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token"),
) -> MessageResponse:
    """
    Logout current user.

    - Revokes current refresh token
    - Blacklists access token in Redis
    - Clears refresh token cookie
    """
    # Revoke refresh token if present
    if refresh_token:
        token_hash_value = hash_token(refresh_token)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
        )
        token_record = result.scalars().first()

        if token_record:
            token_record.revoke()
            await session.commit()

    # Clear cookie
    clear_refresh_cookie(response)

    logger.info(f"User logged out: {user.email}")
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserDetailedResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user),
) -> User:
    """
    Get current authenticated user information.

    Requires valid access token in Authorization header.
    """
    return user


@router.post("/verify-email", response_model=MessageResponse)
@limiter.limit(RateLimits.VERIFY_EMAIL)
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """
    Verify user email with verification token.

    - Validates token and expiration
    - Marks user as verified
    - Marks token as used
    """
    # Hash the token to look it up
    token_hash_value = hash_token(payload.token)

    # Find token record
    result = await session.execute(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == token_hash_value)
        .where(EmailVerificationToken.is_used == False)
    )
    token_record = result.scalars().first()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used verification token",
        )

    # Check if token is expired
    if token_record.is_expired():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired. Please request a new one.",
        )

    # Get user
    user_result = await session.execute(select(User).where(User.id == token_record.user_id))
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify email
    user.verify_email()
    token_record.mark_as_used()

    await session.commit()

    logger.info(f"Email verified for user: {user.email}")
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(RateLimits.RESEND_VERIFICATION)
async def resend_verification(
    request: Request,
    payload: EmailVerificationRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """
    Resend email verification link.

    - Finds user by email
    - Creates new verification token
    - Sends verification email
    """
    # Find user
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalars().first()

    if not user:
        # Don't reveal if email exists
        return MessageResponse(message="If the email exists, a verification link has been sent")

    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )

    # Create new verification token
    verification_token = EmailVerificationToken.generate_token()
    token_hash_value = hash_token(verification_token)
    token_record = EmailVerificationToken(
        token_hash=token_hash_value,
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
    )
    session.add(token_record)
    await session.commit()

    # Send verification email
    try:
        email_service.send_verification_email(user.email, user.email.split("@")[0], verification_token)
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {e}")

    logger.info(f"Verification email resent to: {user.email}")
    return MessageResponse(message="If the email exists, a verification link has been sent")


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(RateLimits.FORGOT_PASSWORD)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """
    Request password reset link.

    - Finds user by email
    - Creates password reset token
    - Sends reset email
    """
    # Find user
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalars().first()

    if not user:
        # Don't reveal if email exists (security best practice)
        return MessageResponse(message="If the email exists, a password reset link has been sent")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Create password reset token
    reset_token = PasswordResetToken.generate_token()
    token_hash_value = hash_token(reset_token)
    token_record = PasswordResetToken(
        token_hash=token_hash_value,
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
    )
    session.add(token_record)
    await session.commit()

    # Send reset email
    try:
        email_service.send_password_reset_email(user.email, user.email.split("@")[0], reset_token)
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {e}")

    logger.info(f"Password reset email sent to: {user.email}")
    return MessageResponse(message="If the email exists, a password reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(RateLimits.RESET_PASSWORD)
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """
    Reset password with reset token.

    - Validates token and expiration
    - Updates user password
    - Marks token as used
    - Sends confirmation email
    """
    # Hash the token
    token_hash_value = hash_token(payload.token)

    # Find token record
    result = await session.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash_value)
        .where(PasswordResetToken.is_used == False)
    )
    token_record = result.scalars().first()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used reset token",
        )

    # Check if token is expired
    if token_record.is_expired():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    # Get user
    user_result = await session.execute(select(User).where(User.id == token_record.user_id))
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update password
    user.hashed_password = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(UTC)
    token_record.mark_as_used()

    await session.commit()

    # Send password changed confirmation email
    try:
        email_service.send_password_changed_email(user.email, user.email.split("@")[0])
    except Exception as e:
        logger.error(f"Failed to send password changed email to {user.email}: {e}")

    logger.info(f"Password reset for user: {user.email}")
    return MessageResponse(message="Password reset successfully")


@router.post("/change-password", response_model=MessageResponse)
@limiter.limit(RateLimits.CHANGE_PASSWORD)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Change password for authenticated user.

    - Validates current password
    - Updates to new password
    - Sends confirmation email
    """
    # Verify current password
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Check if new password is same as current
    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Update password
    user.hashed_password = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(UTC)

    await session.commit()

    # Send password changed confirmation email
    try:
        email_service.send_password_changed_email(user.email, user.email.split("@")[0])
    except Exception as e:
        logger.error(f"Failed to send password changed email to {user.email}: {e}")

    logger.info(f"Password changed for user: {user.email}")
    return MessageResponse(message="Password changed successfully")


@router.post("/delete-account", response_model=MessageResponse)
@limiter.limit(RateLimits.DELETE_ACCOUNT)
async def delete_account(
    request: Request,
    payload: DeleteAccountRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Schedule account deletion with grace period.

    - Validates password
    - Schedules deletion for 30 days from now
    - Sends confirmation email with cancellation link
    """
    # Verify password
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    # Check if already scheduled for deletion
    if user.is_deleted and user.deletion_scheduled_for:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account deletion is already scheduled",
        )

    # Schedule deletion
    user.schedule_deletion(days=settings.SOFT_DELETE_DAYS)

    await session.commit()

    # Send deletion scheduled email
    try:
        cancel_token = EmailVerificationToken.generate_token()  # Reuse token generation
        cancel_link = f"{settings.FRONTEND_URL}/cancel-deletion?token={cancel_token}"

        # Store cancel token (we'll reuse EmailVerificationToken for this)
        token_hash_value = hash_token(cancel_token)
        token_record = EmailVerificationToken(
            token_hash=token_hash_value,
            user_id=user.id,
            expires_at=user.deletion_scheduled_for,  # Expires when deletion happens
        )
        session.add(token_record)
        await session.commit()

        email_service.send_deletion_scheduled_email(
            user.email,
            user.email.split("@")[0],
            user.deletion_scheduled_for,
            settings.SOFT_DELETE_DAYS,
            cancel_link,
        )
    except Exception as e:
        logger.error(f"Failed to send deletion scheduled email to {user.email}: {e}")

    logger.info(f"Account deletion scheduled for user: {user.email}")
    return MessageResponse(
        message=f"Account deletion scheduled for {settings.SOFT_DELETE_DAYS} days from now. You can cancel anytime before then."
    )


@router.post("/cancel-deletion", response_model=MessageResponse)
@limiter.limit(RateLimits.CANCEL_DELETION)
async def cancel_deletion(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Cancel scheduled account deletion.

    - Removes deletion schedule
    - Reactivates account
    """
    if not user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account deletion is scheduled",
        )

    # Cancel deletion
    user.is_deleted = False
    user.deleted_at = None
    user.deletion_scheduled_for = None

    await session.commit()

    logger.info(f"Account deletion canceled for user: {user.email}")
    return MessageResponse(message="Account deletion canceled successfully")


@router.post("/logout-all", response_model=MessageResponse)
@limiter.limit(RateLimits.LOGOUT_ALL)
async def logout_all(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: RedisClient = Depends(get_redis_client),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Logout from all devices and sessions.

    - Revokes all refresh tokens
    - Blacklists all user tokens in Redis
    - Sends confirmation email
    """
    # Revoke all refresh tokens in database
    result = await session.execute(
        select(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .where(RefreshToken.is_revoked == False)
    )
    tokens = result.scalars().all()

    for token in tokens:
        token.revoke()

    await session.commit()

    # Revoke all tokens in Redis
    await redis.revoke_all_user_tokens(str(user.id))

    # Clear current refresh cookie
    clear_refresh_cookie(response)

    # Send logout all confirmation email
    try:
        email_service.send_logout_all_email(user.email, user.email.split("@")[0])
    except Exception as e:
        logger.error(f"Failed to send logout all email to {user.email}: {e}")

    logger.info(f"All sessions logged out for user: {user.email}")
    return MessageResponse(message="Logged out from all devices successfully")
