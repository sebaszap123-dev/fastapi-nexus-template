import logging
from typing import Dict, Any, Optional
from pathlib import Path

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment for email templates
template_dir = Path(__file__).parent.parent / "templates" / "emails"
jinja_env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    autoescape=select_autoescape(['html', 'xml'])
)


class EmailService:
    """
    Email service using Brevo (Sendinblue) API.

    Handles all transactional emails with modern HTML templates.
    """

    def __init__(self):
        """Initialize Brevo API client."""
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = settings.BREVO_API_KEY
        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

    def _send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send email using Brevo API.

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text fallback (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email, "name": to_name}],
            sender={"email": settings.BREVO_SENDER_EMAIL, "name": settings.BREVO_SENDER_NAME},
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

        try:
            api_response = self.api_instance.send_transac_email(send_smtp_email)
            logger.info(f"Email sent successfully to {to_email}: {api_response}")
            return True
        except ApiException as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render Jinja2 email template.

        Args:
            template_name: Template file name
            context: Template context variables

        Returns:
            Rendered HTML string
        """
        template = jinja_env.get_template(template_name)
        return template.render(**context)

    def send_welcome_email(self, email: str, name: str) -> bool:
        """
        Send welcome email to new user.

        Args:
            email: User email
            name: User name

        Returns:
            True if sent successfully
        """
        html_content = self._render_template(
            "welcome.html",
            {
                "name": name,
                "frontend_url": settings.FRONTEND_URL,
            }
        )

        return self._send_email(
            to_email=email,
            to_name=name,
            subject="Welcome to Suremind! 👋",
            html_content=html_content,
        )

    def send_verification_email(
        self,
        email: str,
        name: str,
        verification_token: str,
    ) -> bool:
        """
        Send email verification link.

        Args:
            email: User email
            name: User name
            verification_token: Verification token

        Returns:
            True if sent successfully
        """
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

        html_content = self._render_template(
            "verify_email.html",
            {
                "name": name,
                "verification_link": verification_link,
                "frontend_url": settings.FRONTEND_URL,
            }
        )

        return self._send_email(
            to_email=email,
            to_name=name,
            subject="Verify your email address",
            html_content=html_content,
        )

    def send_password_reset_email(
        self,
        email: str,
        name: str,
        reset_token: str,
    ) -> bool:
        """
        Send password reset link.

        Args:
            email: User email
            name: User name
            reset_token: Password reset token

        Returns:
            True if sent successfully
        """
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        html_content = self._render_template(
            "reset_password.html",
            {
                "name": name,
                "reset_link": reset_link,
                "expiration_minutes": settings.PASSWORD_RESET_EXPIRE_MINUTES,
                "frontend_url": settings.FRONTEND_URL,
            }
        )

        return self._send_email(
            to_email=email,
            to_name=name,
            subject="Reset your password",
            html_content=html_content,
        )

    def send_password_changed_email(self, email: str, name: str) -> bool:
        """
        Send notification that password was changed.

        Args:
            email: User email
            name: User name

        Returns:
            True if sent successfully
        """
        html_content = self._render_template(
            "password_changed.html",
            {
                "name": name,
                "frontend_url": settings.FRONTEND_URL,
            }
        )

        return self._send_email(
            to_email=email,
            to_name=name,
            subject="Your password was changed",
            html_content=html_content,
        )

    def send_deletion_scheduled_email(
        self,
        email: str,
        name: str,
        deletion_date: str,
        cancel_token: str,
    ) -> bool:
        """
        Send notification that account deletion is scheduled.

        Args:
            email: User email
            name: User name
            deletion_date: When account will be deleted
            cancel_token: Token to cancel deletion

        Returns:
            True if sent successfully
        """
        cancel_link = f"{settings.FRONTEND_URL}/cancel-deletion?token={cancel_token}"

        html_content = self._render_template(
            "deletion_scheduled.html",
            {
                "name": name,
                "deletion_date": deletion_date,
                "cancel_link": cancel_link,
                "days": settings.SOFT_DELETE_DAYS,
                "frontend_url": settings.FRONTEND_URL,
            }
        )

        return self._send_email(
            to_email=email,
            to_name=name,
            subject="Your account will be deleted",
            html_content=html_content,
        )

    def send_deletion_reminder_email(
        self,
        email: str,
        name: str,
        days_remaining: int,
        cancel_token: str,
    ) -> bool:
        """
        Send reminder that account will be deleted soon.

        Args:
            email: User email
            name: User name
            days_remaining: Days until deletion
            cancel_token: Token to cancel deletion

        Returns:
            True if sent successfully
        """
        cancel_link = f"{settings.FRONTEND_URL}/cancel-deletion?token={cancel_token}"

        html_content = self._render_template(
            "deletion_reminder.html",
            {
                "name": name,
                "days_remaining": days_remaining,
                "cancel_link": cancel_link,
                "frontend_url": settings.FRONTEND_URL,
            }
        )

        return self._send_email(
            to_email=email,
            to_name=name,
            subject=f"⚠️ Your account will be deleted in {days_remaining} days",
            html_content=html_content,
        )

    def send_logout_all_email(self, email: str, name: str) -> bool:
        """
        Send notification that all sessions were logged out.

        Args:
            email: User email
            name: User name

        Returns:
            True if sent successfully
        """
        html_content = self._render_template(
            "logout_all.html",
            {
                "name": name,
                "frontend_url": settings.FRONTEND_URL,
            }
        )

        return self._send_email(
            to_email=email,
            to_name=name,
            subject="All devices logged out",
            html_content=html_content,
        )


# Global email service instance
email_service = EmailService()
