"""
Utilidades para gestionar administradores de SQLAdmin.
"""
import asyncio
import logging

from sqlalchemy import select

from app.admin.models import Admin
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def create_admin_user(
    username: str,
    email: str,
    password: str,
) -> Admin:
    """
    Crear un nuevo usuario administrador.

    Args:
        username: Nombre de usuario
        email: Email del administrador
        password: Contraseña en texto plano

    Returns:
        Instancia del administrador creado

    Raises:
        ValueError: Si el administrador ya existe
        Exception: Si hay un error en la creación
    """
    # Obtener sesión de DB
    async with AsyncSessionLocal() as session:
        try:
            # Verificar si ya existe
            result = await session.execute(
                select(Admin).where(Admin.username == username)
            )
            existing = result.scalars().first()

            if existing:
                raise ValueError(f"El administrador con username '{username}' ya existe")

            # Verificar email
            result = await session.execute(
                select(Admin).where(Admin.email == email)
            )
            existing_email = result.scalars().first()

            if existing_email:
                raise ValueError(f"El administrador con email '{email}' ya existe")

            # Crear el administrador
            hashed_password = Admin.create_hashed_password(password)
            admin = Admin(
                username=username,
                email=email,
                password=hashed_password,
            )

            session.add(admin)
            await session.commit()
            await session.refresh(admin)

            logger.info(f"Administrador '{username}' creado exitosamente")
            return admin

        except Exception as e:
            await session.rollback()
            logger.error(f"Error al crear administrador: {e}")
            raise


async def list_admins() -> list[Admin]:
    """
    Listar todos los administradores.

    Returns:
        Lista de administradores
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin))
        admins = result.scalars().all()
        return list(admins)


if __name__ == "__main__":
    """
    Script para crear un administrador desde la línea de comandos.

    Uso:
        python -m app.admin.utils <username> <email> <password>
    """
    import sys

    if len(sys.argv) < 4:
        print("Uso: python -m app.admin.utils <username> <email> <password>")
        sys.exit(1)

    username = sys.argv[1]
    email = sys.argv[2]
    password = sys.argv[3]

    async def main():
        try:
            admin = await create_admin_user(username, email, password)
            print(f"✓ Administrador '{admin.username}' creado exitosamente")
            print(f"  Email: {admin.email}")
            print(f"  ID: {admin.id}")
        except Exception as e:
            print(f"✗ Error: {e}")
            sys.exit(1)

    asyncio.run(main())
