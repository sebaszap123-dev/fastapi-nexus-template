"""
Autenticación para Starlette Admin Panel.

Este módulo maneja la autenticación de administradores usando sesiones.
"""
import logging

from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin.exceptions import FormValidationError, LoginFailed

from app.admin.models import Admin
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class AdminAuthProvider(AuthProvider):
    """
    Proveedor de autenticación para el Admin Panel.

    Usa sesiones de Starlette para mantener el estado de autenticación.
    Verifica credenciales contra la tabla `admins` en la base de datos.
    """

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        """
        Procesar login de administrador.

        Args:
            username: Nombre de usuario
            password: Contraseña en texto plano
            remember_me: Si se debe recordar la sesión (no implementado)
            request: Request de Starlette
            response: Response de Starlette

        Returns:
            Response con redirect si exitoso

        Raises:
            LoginFailed: Si las credenciales son inválidas
            FormValidationError: Si faltan datos
        """
        if not username or not password:
            raise FormValidationError(
                {"username": "Username y password son requeridos"}
            )

        # Obtener sesión de DB
        async with AsyncSessionLocal() as session:
            # Buscar admin por username
            result = await session.execute(
                select(Admin).where(Admin.username == username)
            )
            admin = result.scalars().first()

            if not admin:
                logger.warning(f"Intento de login fallido: usuario '{username}' no encontrado")
                raise LoginFailed("Credenciales inválidas")

            if not admin.is_active:
                logger.warning(f"Intento de login fallido: usuario '{username}' inactivo")
                raise LoginFailed("Cuenta desactivada")

            if not admin.verify_password(password):
                logger.warning(
                    f"Intento de login fallido: contraseña incorrecta para '{username}'"
                )
                raise LoginFailed("Credenciales inválidas")

            # Guardar información en la sesión
            request.session.update(
                {
                    "admin_id": admin.id,
                    "admin_username": admin.username,
                    "admin_email": admin.email,
                }
            )

            logger.info(f"Login exitoso: {admin.username}")
            return response

    async def is_authenticated(self, request: Request) -> bool:
        """
        Verificar si el usuario está autenticado.

        Args:
            request: Request de Starlette

        Returns:
            True si está autenticado y activo
        """
        admin_id = request.session.get("admin_id")
        if not admin_id:
            return False

        # Verificar que el admin todavía existe y está activo
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Admin).where(Admin.id == admin_id))
            admin = result.scalars().first()

            if not admin or not admin.is_active:
                # Limpiar sesión si el admin no existe o está inactivo
                request.session.clear()
                return False

        return True

    def get_admin_config(self, request: Request) -> AdminConfig:
        """
        Obtener configuración del admin panel.

        Args:
            request: Request de Starlette

        Returns:
            AdminConfig con info del usuario actual
        """
        # TODO: Implementar la lógica para obtener la información del administrador actual SI ES QUE SE NECESITA
        # admin_username = request.session.get("admin_username", "Admin")
        # admin_email = request.session.get("admin_email")

        return AdminConfig(
            app_title="Suremind Admin",
            logo_url=None,  # Puedes agregar tu logo aquí
        )

    def get_admin_user(self, request: Request) -> AdminUser:
        """
        Obtener información del admin actual.

        Args:
            request: Request de Starlette

        Returns:
            AdminUser con datos de sesión
        """
        return AdminUser(
            username=request.session.get("admin_username", ""),
            photo_url=None,  # Opcional: URL de foto de perfil
        )

    async def logout(self, request: Request, response: Response) -> Response:
        """
        Procesar logout de administrador.

        Args:
            request: Request de Starlette
            response: Response de Starlette

        Returns:
            Response con redirect
        """
        admin_username = request.session.get("admin_username")
        request.session.clear()

        if admin_username:
            logger.info(f"Logout: {admin_username}")

        return response
