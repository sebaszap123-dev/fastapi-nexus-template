"""
Setup de Starlette Admin Panel.

Módulo centralizado para inicializar y configurar el panel de administración.
"""
import logging

from fastapi import FastAPI
from starlette_admin.contrib.sqla import Admin

from app.admin.auth import AdminAuthProvider
from app.admin.models import Admin as AdminModel
from app.admin.views import (
    AdminUserView,
    EmailVerificationTokenView,
    PasswordResetTokenView,
    RefreshTokenView,
    UserView,
)
from app.db.session import engine
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)


def setup_admin(app: FastAPI) -> Admin:
    """
    Configurar e inicializar el panel de administración Starlette Admin.

    Args:
        app: Instancia de FastAPI

    Returns:
        Instancia de Admin configurada
    """
    # Crear proveedor de autenticación
    auth_provider = AdminAuthProvider()

    # Crear instancia de Admin
    admin = Admin(
        engine,
        title="Suremind Admin",
        base_url="/admin",
        auth_provider=auth_provider,
        logo_url=None,  # Puedes agregar tu logo aquí
        login_logo_url=None,  # Logo para la página de login
        # templates_dir="templates/admin",  # Opcional: templates personalizados
        # statics_dir="static/admin",  # Opcional: archivos estáticos personalizados
    )

    # Registrar vistas de modelos
    admin.add_view(UserView(User))
    admin.add_view(AdminUserView(AdminModel))
    admin.add_view(RefreshTokenView(RefreshToken))
    admin.add_view(EmailVerificationTokenView(EmailVerificationToken))
    admin.add_view(PasswordResetTokenView(PasswordResetToken))

    # Montar el admin en la aplicación
    admin.mount_to(app)

    logger.info("Starlette Admin Panel configurado exitosamente en /admin")

    return admin
