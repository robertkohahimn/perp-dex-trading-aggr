.PHONY: help install install-dev run dev test clean lint format db-init db-migrate db-reset docker-build docker-up docker-down

# Variables
PYTHON := python3
PIP := pip3
APP := app.main:app
HOST := 0.0.0.0
PORT := 8000

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	$(PIP) install -r requirements-dev.txt
	pre-commit install

run: ## Run the application in production mode
	uvicorn $(APP) --host $(HOST) --port $(PORT) --workers 4

dev: ## Run the application in development mode with auto-reload
	uvicorn $(APP) --host $(HOST) --port $(PORT) --reload

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit -v -m unit

test-integration: ## Run integration tests only
	pytest tests/integration -v -m integration

test-fast: ## Run fast tests (exclude slow)
	pytest tests/ -v -m "not slow"

test-cov: ## Run tests with coverage report
	pytest tests/ --cov=app --cov=connectors --cov=services --cov-report=html --cov-report=term

test-watch: ## Run tests in watch mode
	pytest-watch tests/ -v

test-debug: ## Run tests with debug output
	pytest tests/ -vvs --tb=long --log-cli-level=DEBUG

test-parallel: ## Run tests in parallel
	pytest tests/ -v -n auto

lint: ## Run linters
	flake8 app/ connectors/ services/ models/
	mypy app/ connectors/ services/ models/
	black --check app/ connectors/ services/ models/
	isort --check-only app/ connectors/ services/ models/

format: ## Format code
	black app/ connectors/ services/ models/ tests/
	isort app/ connectors/ services/ models/ tests/

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true

db-init: ## Initialize database (create tables)
	$(PYTHON) -c "import asyncio; from database.session import init_database; asyncio.run(init_database())"

db-migrate: ## Run database migrations
	alembic upgrade head

db-rollback: ## Rollback last migration
	alembic downgrade -1

db-reset: ## Reset database (drop and recreate)
	$(PYTHON) -c "import asyncio; from database.session import drop_tables, create_tables; asyncio.run(drop_tables()); asyncio.run(create_tables())"

redis-start: ## Start Redis server
	redis-server

postgres-start: ## Start PostgreSQL
	pg_ctl -D /usr/local/var/postgres start

postgres-stop: ## Stop PostgreSQL
	pg_ctl -D /usr/local/var/postgres stop

docker-build: ## Build Docker image
	docker build -t perp-dex-backend .

docker-up: ## Start Docker containers
	docker-compose up -d

docker-down: ## Stop Docker containers
	docker-compose down

docker-logs: ## Show Docker logs
	docker-compose logs -f

docker-shell: ## Open shell in Docker container
	docker-compose exec app bash

env-setup: ## Set up environment file
	cp .env.example .env
	@echo "Environment file created. Please edit .env with your configuration."

check: lint test ## Run linters and tests

ci: install lint test ## Run CI pipeline

setup: install-dev env-setup db-init ## Initial project setup

update-deps: ## Update dependencies
	$(PIP) list --outdated
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install --upgrade -r requirements.txt

freeze: ## Freeze current dependencies
	$(PIP) freeze > requirements.txt