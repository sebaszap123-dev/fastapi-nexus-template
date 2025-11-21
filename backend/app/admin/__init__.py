"""
Módulo de administración con Starlette Admin.

Este módulo contiene la configuración y recursos para el panel de administración.
"""

from app.admin.auth import AdminAuthProvider
from app.admin.models import Admin
from app.admin.setup import setup_admin
from app.admin.utils import create_admin_user, list_admins
from app.admin.views import (
    AdminUserView,
    EmailVerificationTokenView,
    PasswordResetTokenView,
    RefreshTokenView,
    UserView,
)

__all__ = [
    "Admin",
    "AdminAuthProvider",
    "AdminUserView",
    "EmailVerificationTokenView",
    "PasswordResetTokenView",
    "RefreshTokenView",
    "UserView",
    "create_admin_user",
    "list_admins",
    "setup_admin",
]
