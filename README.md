# FastAPI Nexus Template

**Production-ready FastAPI boilerplate with best practices for authentication, async task processing, Docker orchestration, and comprehensive testing.**

> Battle-tested template for building scalable REST APIs. Features JWT authentication with token rotation, Celery background workers, Redis caching, PostgreSQL with async SQLAlchemy, and complete CI/CD pipeline setup.

---

## Why Use This Template

Skip the boilerplate and start with production-grade foundations:

✅ **Secure by default** - JWT with refresh token rotation, Redis blacklist, HttpOnly cookies
✅ **Async-first** - AsyncIO throughout (SQLAlchemy, FastAPI, Celery tasks)
✅ **Docker-ready** - Multi-stage builds, docker-compose orchestration
✅ **Type-safe** - Pydantic schemas, mypy strict mode
✅ **Test coverage** - Pytest with async fixtures, 80%+ coverage baseline
✅ **Migrations** - Alembic auto-generation from models
✅ **Monitoring-ready** - Structured JSON logging, health checks

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Next.js   │─────▶│   FastAPI    │─────▶│ PostgreSQL  │
│   Frontend  │      │   (API)      │      │   Database  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ├──────▶ Redis (Cache + Token Blacklist)
                            │
                            └──────▶ Celery Workers (Background Tasks)
```

**Key Components**
- **FastAPI** - Async REST API with auto-generated OpenAPI docs
- **PostgreSQL** - Primary data store with async SQLAlchemy ORM
- **Redis** - Token blacklist, session cache, Celery broker
- **Celery** - Distributed task queue for background jobs
- **Alembic** - Schema migration management
- **Pytest** - Async test suite with database fixtures

## Quick Start

### 1. Clone Template

```bash
git clone https://github.com/sebaszap123-dev/fastapi-nexus-template.git my-api
cd my-api
```

### 2. Configure Environment

```bash
cp .env.example .env
```

**Edit `.env` - Required settings:**
```bash
# Security (CRITICAL: Use strong random values in production)
JWT_SECRET=<32+ random characters>
POSTGRES_PASSWORD=<strong password>

# CORS (Update with your frontend URL)
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Database
POSTGRES_DB=myapp
POSTGRES_USER=postgres
```

### 3. Start Services

```bash
docker-compose up -d
```

**Services running:**
- FastAPI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432 (internal)
- Redis: localhost:6379 (internal)

### 4. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Interactive API documentation
open http://localhost:8000/docs
```

## Authentication Flow

### Standard Flow
1. **Register** → Create user account
2. **Login** → Receive access token (30min) + refresh token (7 days)
3. **Access protected endpoints** → Use access token in Authorization header
4. **Refresh** → Exchange refresh token for new access token when expired
5. **Logout** → Revoke tokens (added to Redis blacklist)

### Security Features

| Feature | Implementation |
|---------|----------------|
| Password hashing | Bcrypt with configurable rounds |
| Token rotation | New refresh token on each refresh, old one invalidated |
| Reuse detection | Automatic session revocation on token reuse |
| XSS protection | HttpOnly cookies for refresh tokens |
| CSRF mitigation | SameSite cookie policy |
| Token blacklist | Redis-based instant revocation |

### API Examples

**Register User**
```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Login**
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

# Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
# Sets HttpOnly cookie: refresh_token
```

**Access Protected Endpoint**
```bash
GET /api/v1/auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Response:
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "created_at": "2025-01-15T12:00:00Z"
}
```

**Refresh Token**
```bash
POST /api/v1/auth/refresh
Cookie: refresh_token=eyJ...

# Response: New access token + rotated refresh token
```

## Local Development

**Without Docker (useful for debugging):**

```bash
# 1. Create virtual environment
cd backend
python3.12 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -e .

# 3. Start databases (Docker)
docker-compose up db redis -d

# 4. Update .env for local connection
# POSTGRES_HOST=localhost
# REDIS_URL=redis://localhost:6379/0

# 5. Run migrations
alembic upgrade head

# 6. Start FastAPI with hot reload
uvicorn app.main:app --reload --port 8000

# 7. Start Celery worker (separate terminal)
celery -A app.tasks.celery_app worker --loglevel=INFO

# 8. Start Celery beat scheduler (separate terminal)
celery -A app.tasks.celery_app beat --loglevel=INFO
```

## Database Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add user_preferences table"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history
```

## Background Tasks with Celery

### Define Task

```python
# app/tasks/example.py
from app.tasks.celery_app import celery_app

@celery_app.task
def send_welcome_email(user_email: str):
    # Email sending logic
    return f"Email sent to {user_email}"
```

### Trigger Task

```python
# In your API endpoint
from app.tasks.example import send_welcome_email

@router.post("/register")
async def register_user(user: UserCreate):
    # Create user...

    # Trigger async task
    send_welcome_email.delay(user.email)

    return {"message": "Registration successful"}
```

### Scheduled Tasks

```python
# app/tasks/celery_app.py
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-expired-tokens': {
        'task': 'app.tasks.cleanup.cleanup_expired_refresh_tokens',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
}
```

## Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/test_auth.py -v

# Run only authentication tests
pytest -m auth
```

**Test Structure:**
```
tests/
├── conftest.py           # Fixtures (test client, test DB)
├── test_auth.py          # Authentication endpoints
├── test_users.py         # User CRUD operations
└── test_tasks.py         # Celery task testing
```

## Project Structure

```
fastapi-nexus-template/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py          # Dependencies (auth, DB session)
│   │   │   └── v1/
│   │   │       └── auth.py      # Auth endpoints
│   │   ├── core/
│   │   │   ├── config.py        # Settings (env variables)
│   │   │   ├── security.py      # JWT, password hashing
│   │   │   └── redis_client.py  # Token blacklist
│   │   ├── db/
│   │   │   └── session.py       # Database connection
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   └── refresh_token.py
│   │   ├── schemas/
│   │   │   └── user.py          # Pydantic models
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   └── cleanup.py
│   │   └── main.py              # FastAPI app instance
│   ├── alembic/                 # Database migrations
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── docker-compose.yml
├── .env.example
└── README.md
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment mode | `dev` |
| `JWT_SECRET` | JWT signing secret (32+ chars) | **Required** |
| `POSTGRES_HOST` | PostgreSQL host | `db` |
| `POSTGRES_DB` | Database name | `myapp` |
| `POSTGRES_PASSWORD` | Database password | **Required** |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `http://localhost:3000` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |

## Production Deployment

### Pre-Deployment Checklist

- [ ] Set strong `JWT_SECRET` (use `openssl rand -hex 32`)
- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Set `COOKIE_SECURE=true` (requires HTTPS)
- [ ] Restrict `CORS_ORIGINS` to production domains only
- [ ] Set `ENV=production` (disables /docs endpoint)
- [ ] Use managed PostgreSQL (AWS RDS, Google Cloud SQL)
- [ ] Use managed Redis (ElastiCache, Redis Cloud)
- [ ] Configure reverse proxy with HTTPS (nginx, Caddy, Traefik)
- [ ] Set up log aggregation (Sentry, Datadog, CloudWatch)
- [ ] Configure database backups and retention policy
- [ ] Set up monitoring and alerting (uptime, error rate, latency)

### Docker Production Build

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Customization Guide

### Add New Endpoint

1. **Create model** (`app/models/item.py`)
2. **Create schema** (`app/schemas/item.py`)
3. **Create migration** (`alembic revision --autogenerate -m "Add items"`)
4. **Apply migration** (`alembic upgrade head`)
5. **Create router** (`app/api/v1/items.py`)
6. **Register router** (in `app/main.py`)

### Add New Background Task

1. **Define task** (`app/tasks/my_task.py`)
2. **Import in `celery_app.py`**
3. **Trigger from endpoint** (`.delay()` or `.apply_async()`)

## Troubleshooting

**Database connection refused**
```bash
# Check PostgreSQL is running
docker-compose ps db

# View logs
docker-compose logs db
```

**Redis connection error**
```bash
# Test Redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG
```

**Migrations failing**
```bash
# Reset database (WARNING: destroys all data)
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

---

**License:** MIT

**Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Redis, Celery, Docker, Pytest

**Author:** Sebastian Frausto · [GitHub](https://github.com/sebaszap123-dev)
