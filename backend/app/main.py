import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.admin.setup import setup_admin
from app.api.v1 import auth
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting up Suremind API...")
    logger.info(f"Environment: {settings.ENV}")

    # Connect to Redis
    await redis_client.connect()
    if await redis_client.ping():
        logger.info("Redis connection established")
    else:
        logger.warning("Redis connection failed - some features may not work")

    logger.info("Admin panel configured successfully")

    yield

    # Shutdown
    logger.info("Shutting down Suremind API...")

    await redis_client.disconnect()
    logger.info("Redis connection closed")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    # Set up structured logging
    setup_logging()

    # Create FastAPI app
    app = FastAPI(
        title="Suremind API",
        description="Production-ready FastAPI template with async SQLAlchemy, JWT auth, Celery, and Redis",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENV != "production" else None,
        redoc_url="/redoc" if settings.ENV != "production" else None,
    )

    # Configure rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,  # Required for cookies
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Add session middleware for Admin Panel authentication
    # IMPORTANT: This must be added BEFORE mounting the admin panel
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.JWT_SECRET,  # Reutilizamos el secret de JWT
        max_age=3600 * 24,  # 24 horas
        same_site="lax",
        https_only=settings.ENV == "production",
    )

    # Setup Starlette Admin Panel (solo en desarrollo o si está habilitado)
    if settings.ENV != "production" or getattr(settings, "ENABLE_ADMIN", False):
        setup_admin(app)
        logger.info("Starlette Admin Panel mounted at /admin")

    # Include routers
    app.include_router(
        auth.router,
        prefix="/api/v1/auth",
        tags=["Authentication"],
    )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint.

        Returns:
            Health status and Redis connectivity
        """
        redis_status = "connected" if await redis_client.ping() else "disconnected"

        return {
            "status": "ok",
            "environment": settings.ENV,
            "redis": redis_status,
        }

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """
        Root endpoint with API information.
        """
        return {
            "message": "Suremind API",
            "version": "0.1.0",
            "docs": "/docs" if settings.ENV != "production" else None,
        }

    logger.info(f"FastAPI application created - CORS origins: {settings.cors_origins_list}")
    return app


# Create the app instance
app = create_app()
