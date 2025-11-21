SHELL := /bin/bash

.PHONY: help build up down restart logs clean clean-pycache test migrate upgrade downgrade shell create-admin

help:
	@echo "Suremind FastAPI - Available Commands:"
	@echo ""
	@echo "  make build      - Build Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs (Ctrl+C to exit)"
	@echo "  make clean      - Remove containers and volumes (DESTRUCTIVE)"
	@echo "  make clean-pycache - Remove all __pycache__ directories"
	@echo "  make test       - Run tests"
	@echo "  make migrate    - Create and run new migration"
	@echo "  make upgrade    - Run pending migrations (upgrade head)"
	@echo "  make downgrade  - Rollback migrations (prompts for number)"
	@echo "  make shell      - Open backend shell"
	@echo "  make worker     - View Celery worker logs"
	@echo "  make create-admin - Create a new admin user (prompts for credentials)"
	@echo ""

build:
	docker compose build

up:
	docker compose up -d
	@echo ""
	@echo "✅ Services started!"
	@echo "   API: http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"
	@echo ""

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

clean:
	@echo "⚠️  This will remove all containers and volumes (data will be lost)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		echo "✅ Cleaned up"; \
	fi

clean-pycache:
	@echo "🧹 Removing all __pycache__ directories..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "✅ All __pycache__ directories and .pyc files removed"

test:
	@if docker compose ps backend | grep -q "Up"; then \
		docker compose exec backend pytest -v; \
	else \
		echo "⚠️  Backend service is not running. Starting it temporarily..."; \
		docker compose run --rm backend pytest -v; \
	fi

migrate:
	@read -p "Migration description: " desc; \
	if docker compose ps backend | grep -q "Up"; then \
		docker compose exec backend alembic revision --autogenerate -m "$$desc"; \
		docker compose exec backend alembic upgrade head; \
	else \
		echo "⚠️  Backend service is not running. Starting it temporarily..."; \
		docker compose run --rm backend alembic revision --autogenerate -m "$$desc"; \
		docker compose run --rm backend alembic upgrade head; \
	fi

upgrade:
	@if docker compose ps backend | grep -q "Up"; then \
		docker compose exec backend alembic upgrade head; \
	else \
		echo "⚠️  Backend service is not running. Starting it temporarily..."; \
		docker compose run --rm backend alembic upgrade head; \
	fi

downgrade:
	@read -p "How many revisions to downgrade? (default: 1) " revs; \
	revs=$${revs:-1}; \
	if docker compose ps backend | grep -q "Up"; then \
		docker compose exec backend alembic downgrade -$$revs; \
	else \
		echo "⚠️  Backend service is not running. Starting it temporarily..."; \
		docker compose run --rm backend alembic downgrade -$$revs; \
	fi

shell:
	@if docker compose ps backend | grep -q "Up"; then \
		docker compose exec backend /bin/bash; \
	else \
		echo "⚠️  Backend service is not running. Starting it temporarily..."; \
		docker compose run --rm backend /bin/bash; \
	fi

worker:
	docker compose logs -f worker

create-admin:
	@bash -c 'read -p "Username: " username; \
	read -p "Email: " email; \
	read -sp "Password: " password; \
	echo ""; \
	if docker compose ps backend | grep -q "Up"; then \
		docker compose exec backend python -m app.admin.utils "$$username" "$$email" "$$password"; \
	else \
		echo "⚠️  Backend service is not running. Starting it temporarily..."; \
		docker compose run --rm backend python -m app.admin.utils "$$username" "$$email" "$$password"; \
	fi'
