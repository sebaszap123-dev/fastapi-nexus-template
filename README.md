# Suremind FastAPI Template

Production-ready FastAPI template with async SQLAlchemy, JWT authentication with token rotation, Celery background tasks, and Redis caching.

## Features

- **FastAPI** - Modern, fast web framework with automatic API documentation
- **SQLAlchemy** - SQL databases with Python type hints (async)
- **Alembic** - Database migrations
- **JWT Authentication** - Secure token-based auth with rotation and HttpOnly cookies
- **Token Security** - Refresh token rotation, reuse detection, Redis blacklist
- **Celery + Redis** - Background task processing and scheduling
- **Docker** - Containerized development and deployment
- **Pytest** - Async test suite with fixtures
- **Structured Logging** - JSON logging for production monitoring

## Security Highlights

✅ **Refresh token rotation** - New token on each refresh, old one invalidated
✅ **Token reuse detection** - Automatic revocation of all sessions on breach
✅ **Redis-based blacklist** - Instant token revocation with TTL
✅ **HttpOnly cookies** - XSS protection for refresh tokens
✅ **Short-lived access tokens** - 30-minute expiration
✅ **CSRF protection** - SameSite cookie policy
✅ **Bcrypt password hashing** - Industry-standard encryption
✅ **Secrets in environment** - Never commit credentials

## Project Structure

```
suremind-fastapi/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py          # Dependencies (get_current_user)
│   │   │   └── v1/
│   │   │       └── auth.py      # Auth endpoints
│   │   ├── core/
│   │   │   ├── config.py        # Settings and configuration
│   │   │   ├── security.py      # Password hashing, JWT
│   │   │   ├── redis_client.py  # Token blacklist
│   │   │   └── logging_config.py
│   │   ├── db/
│   │   │   └── session.py       # Database connection
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   └── refresh_token.py
│   │   ├── schemas/
│   │   │   └── user.py          # Pydantic schemas
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   ├── example.py
│   │   │   └── cleanup.py
│   │   └── main.py              # FastAPI app
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Test suite
│   ├── Dockerfile
│   └── pyproject.toml
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo>
cd suremind-fastapi
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and set secure values:
# - JWT_SECRET (use 32+ random characters)
# - POSTGRES_PASSWORD
# - CORS_ORIGINS (your Next.js URL)
```

### 3. Start with Docker Compose

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** on port 5432 (internal)
- **Redis** on port 6379 (internal)
- **FastAPI** on port 8000
- **Celery Worker** for background tasks
- **Celery Beat** for scheduled tasks

### 4. Verify Installation

```bash
# Check health
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs
```

## Local Development (Without Docker)

### 1. Install Dependencies

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### 2. Start PostgreSQL and Redis

```bash
# Install and start PostgreSQL and Redis locally
# Or use Docker for just the databases:
docker-compose up db redis -d
```

### 3. Configure Environment

```bash
cp .env.example .env
# Update POSTGRES_HOST=localhost and REDIS_URL=redis://localhost:6379/0
```

### 4. Run Migrations

```bash
cd backend
alembic upgrade head
```

### 5. Start FastAPI

```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Start Celery Worker (separate terminal)

```bash
celery -A app.tasks.celery_app worker --loglevel=INFO
```

### 7. Start Celery Beat (separate terminal)

```bash
celery -A app.tasks.celery_app beat --loglevel=INFO
```

## API Endpoints

### Authentication

#### Register
```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

#### Login
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

# Also sets HttpOnly cookie: refresh_token
```

#### Refresh Token
```bash
POST /api/v1/auth/refresh
Cookie: refresh_token=eyJ...

# Response:
{
  "access_token": "eyJ...",  # New access token
  "token_type": "bearer"
}

# Also sets new HttpOnly cookie
```

#### Get Current User
```bash
GET /api/v1/auth/me
Authorization: Bearer eyJ...

# Response:
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-01-15T12:00:00Z"
}
```

#### Logout
```bash
POST /api/v1/auth/logout
Authorization: Bearer eyJ...
Cookie: refresh_token=eyJ...

# Revokes tokens and clears cookie
```

## Next.js Integration

### Setup Axios with Interceptors

```typescript
// lib/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  withCredentials: true, // Important for cookies
});

// Store access token in memory (more secure than localStorage)
let accessToken: string | null = null;

export const setAccessToken = (token: string) => {
  accessToken = token;
};

export const getAccessToken = () => accessToken;

// Add access token to requests
api.interceptors.request.use(
  (config) => {
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Refresh token (cookie sent automatically)
        const { data } = await axios.post(
          `${api.defaults.baseURL}/api/v1/auth/refresh`,
          {},
          { withCredentials: true }
        );

        setAccessToken(data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;

        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed - redirect to login
        setAccessToken(null);
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

### Auth Hook

```typescript
// hooks/useAuth.ts
import { useState } from 'react';
import api, { setAccessToken, getAccessToken } from '@/lib/api';

interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
}

export const useAuth = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);

  const register = async (email: string, password: string) => {
    setLoading(true);
    try {
      await api.post('/api/v1/auth/register', { email, password });
      // Auto-login after registration
      await login(email, password);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    setLoading(true);
    try {
      const { data } = await api.post('/api/v1/auth/login', {
        email,
        password,
      });

      setAccessToken(data.access_token);
      // Refresh token automatically stored in HttpOnly cookie

      // Fetch user info
      const userResponse = await api.get('/api/v1/auth/me');
      setUser(userResponse.data);
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.post('/api/v1/auth/logout');
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  };

  const fetchUser = async () => {
    if (!getAccessToken()) return;

    try {
      const { data } = await api.get('/api/v1/auth/me');
      setUser(data);
    } catch (error) {
      setUser(null);
    }
  };

  return { user, loading, register, login, logout, fetchUser };
};
```

### Usage in Components

```typescript
// app/login/page.tsx
'use client';

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login, loading } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      router.push('/dashboard');
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Loading...' : 'Login'}
      </button>
    </form>
  );
}
```

## Database Migrations

### Create a new migration

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
```

### Apply migrations

```bash
alembic upgrade head
```

### Rollback

```bash
alembic downgrade -1  # Go back one migration
```

## Testing

```bash
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment (dev/production) | `dev` |
| `POSTGRES_HOST` | PostgreSQL host | `db` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `suremind` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | Required |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `JWT_SECRET` | Secret for JWT signing | Required (32+ chars) |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `http://localhost:3000` |
| `COOKIE_DOMAIN` | Cookie domain | `localhost` |
| `COOKIE_SECURE` | Use secure cookies (HTTPS) | `false` |
| `COOKIE_SAMESITE` | SameSite policy | `lax` |

## Production Deployment

### Security Checklist

- [ ] Set strong `JWT_SECRET` (32+ random characters)
- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Set `COOKIE_SECURE=true` for HTTPS
- [ ] Restrict `CORS_ORIGINS` to your domains only
- [ ] Set `ENV=production` to disable docs
- [ ] Use managed PostgreSQL and Redis services
- [ ] Enable HTTPS at reverse proxy level
- [ ] Set up log aggregation (JSON logs)
- [ ] Configure backup strategy for PostgreSQL
- [ ] Monitor Redis memory usage

### Docker Production Build

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Celery Tasks

### Running a Task

```python
from app.tasks.example import add_numbers

# Async execution
result = add_numbers.delay(5, 10)
print(result.get())  # 15
```

### Scheduled Tasks

Configured in `app/tasks/celery_app.py`:

- **cleanup_expired_refresh_tokens** - Runs every 6 hours

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps db

# View logs
docker-compose logs db
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
```

### Migration Issues

```bash
# Reset database (WARNING: destroys data)
docker-compose down -v
docker-compose up -d
```

## License

MIT

## Contributing

Pull requests welcome! Please ensure tests pass and follow the existing code style.
