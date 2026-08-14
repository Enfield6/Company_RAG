.PHONY: up down logs backend-dev frontend-dev migrate test lint build

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

backend-dev:
	cd backend && uvicorn app.main:app --reload

frontend-dev:
	cd frontend && npm run dev

migrate:
	cd backend && alembic upgrade head

test:
	cd backend && pytest

lint:
	cd backend && ruff check app tests
	cd frontend && npm run type-check

build:
	cd frontend && npm run build
