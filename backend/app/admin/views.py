"""
Vistas de Starlette Admin.

Define los ModelView que aparecerán en el panel de administración.
"""
from typing import Any

from starlette.requests import Request
from starlette_admin import PasswordField
from starlette_admin.contrib.sqla import ModelView

from app.admin.models import Admin
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User


class UserView(ModelView):
    """Vista de administración para usuarios."""

    # Configuración básica
    name = "Usuario"
    name_plural = "Usuarios"
    icon = "fa-solid fa-users"
    label = "Usuarios"

    # Campos a mostrar en la lista
    fields = [
        User.id,
        User.email,
        User.is_active,
        User.is_superuser,
        User.is_email_verified,
        User.is_deleted,
        User.created_at,
        PasswordField("password", label="Contraseña"), 
    ]
    # Importante: Excluir password de la lista y detalle para no ver el hash
    exclude_fields_from_list = ["password"]
    exclude_fields_from_detail = ["password"]
    exclude_fields_from_update = ["password"]
    # Campos excluidos de formularios (solo lectura)
    exclude_fields_from_create = [User.id, User.created_at, User.updated_at]
    exclude_fields_from_edit = [User.id, User.created_at, User.updated_at]

    # Búsqueda
    search_fields = [User.email]

    # Campos ordenables
    sortable_fields = [
        User.email,
        User.created_at,
        User.is_active,
        User.is_deleted,
    ]

    # Paginación
    page_size = 50
    page_size_options = [25, 50, 100, 200]

class AdminUserView(ModelView):
    """Vista de administración para administradores."""

    name = "Administrador"
    name_plural = "Administradores"
    icon = "fa-solid fa-user-shield"
    label = "Administradores"

    # 1. Definimos los campos explícitamente
    fields = [
        Admin.id,
        Admin.username,
        Admin.email,
        # Usamos PasswordField para que el input oculte los caracteres
        PasswordField("password", label="Contraseña"), 
        Admin.is_active,
        Admin.created_at,
    ]

    # Configuración de exclusiones
    exclude_fields_from_create = [Admin.id, Admin.created_at, Admin.updated_at]
    
    # Importante: Excluir password de la lista y detalle para no ver el hash
    exclude_fields_from_list = ["password"]
    exclude_fields_from_detail = ["password"]
    exclude_fields_from_update = ["password"]
    # En edición, si quieres permitir cambiar password, quítalo de aquí.
    # Si lo dejas aquí, no se podrá cambiar el password al editar.
    exclude_fields_from_edit = [Admin.id, Admin.created_at, Admin.updated_at]

    search_fields = [Admin.username, Admin.email]
    sortable_fields = [Admin.username, Admin.created_at]

    page_size = 50

    # 2. HOOK PARA CREACIÓN: Interceptamos antes de guardar
    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """
        Se ejecuta antes de crear el registro en la base de datos.
        Aquí tomamos el password en texto plano y lo hasheamos.
        """
        if "password" in data and data["password"]:
            # Usamos el método estático de tu modelo Admin
            data["password"] = Admin.create_hashed_password(data["password"])
        
        return await super().before_create(request, data, obj)


class RefreshTokenView(ModelView):
    """Vista de administración para refresh tokens."""

    name = "Refresh Token"
    name_plural = "Refresh Tokens"
    icon = "fa-solid fa-key"
    label = "Refresh Tokens"

    fields = [
        RefreshToken.id,
        RefreshToken.user_id,
        RefreshToken.is_revoked,
        RefreshToken.created_at,
        RefreshToken.expires_at,
    ]

    fields_default_sort = [(RefreshToken.created_at, True)]  # Descendente

    exclude_fields_from_create = [RefreshToken.id, RefreshToken.created_at]
    exclude_fields_from_edit = [RefreshToken.id, RefreshToken.token_hash, RefreshToken.created_at]

    search_fields = [RefreshToken.token_hash]
    sortable_fields = [RefreshToken.created_at, RefreshToken.expires_at]

    page_size = 50


class EmailVerificationTokenView(ModelView):
    """Vista de administración para tokens de verificación de email."""

    name = "Token de Verificación Email"
    name_plural = "Tokens de Verificación Email"
    icon = "fa-solid fa-envelope-circle-check"
    label = "Tokens Email"

    fields = [
        EmailVerificationToken.id,
        EmailVerificationToken.user_id,
        EmailVerificationToken.is_used,
        EmailVerificationToken.created_at,
        EmailVerificationToken.expires_at,
    ]

    fields_default_sort = [(EmailVerificationToken.created_at, True)]

    exclude_fields_from_create = [
        EmailVerificationToken.id,
        EmailVerificationToken.created_at,
    ]
    exclude_fields_from_edit = [
        EmailVerificationToken.id,
        EmailVerificationToken.token_hash,
        EmailVerificationToken.created_at,
    ]

    sortable_fields = [EmailVerificationToken.created_at, EmailVerificationToken.expires_at]

    page_size = 50


class PasswordResetTokenView(ModelView):
    """Vista de administración para tokens de reseteo de contraseña."""

    name = "Token de Reseteo de Contraseña"
    name_plural = "Tokens de Reseteo de Contraseña"
    icon = "fa-solid fa-lock"
    label = "Tokens Reset"

    fields = [
        PasswordResetToken.id,
        PasswordResetToken.user_id,
        PasswordResetToken.is_used,
        PasswordResetToken.created_at,
        PasswordResetToken.expires_at,
    ]

    fields_default_sort = [(PasswordResetToken.created_at, True)]

    exclude_fields_from_create = [
        PasswordResetToken.id,
        PasswordResetToken.created_at,
    ]
    exclude_fields_from_edit = [
        PasswordResetToken.id,
        PasswordResetToken.token_hash,
        PasswordResetToken.created_at,
    ]

    sortable_fields = [PasswordResetToken.created_at, PasswordResetToken.expires_at]

    page_size = 50
