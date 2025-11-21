"""
Modelos de SQLAlchemy para Admin Panel.

Este módulo define el modelo Admin necesario para el login del panel de administración.
"""
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.security import hash_password, verify_password
from app.models.base import Base


class Admin(Base):
    """
    Modelo de administrador para el Admin Panel.

    Este modelo es independiente del modelo User
    y se usa exclusivamente para el panel de administración.
    """

    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Nombre de usuario",
    )
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Email del administrador",
    )
    password = Column(
        String(255),
        nullable=False,
        comment="Contraseña hasheada",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Usuario activo",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Fecha de creación",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Última actualización",
    )

    def __str__(self) -> str:
        return self.username

    @classmethod
    def create_hashed_password(cls, password: str) -> str:
        """
        Hashear contraseña usando Argon2id.

        Args:
            password: Contraseña en texto plano

        Returns:
            Contraseña hasheada con Argon2id
        """
        return hash_password(password)

    def verify_password(self, password: str) -> bool:
        """
        Verificar contraseña.

        Args:
            password: Contraseña en texto plano

        Returns:
            True si la contraseña es correcta
        """
        return verify_password(password, self.password)
