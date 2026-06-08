set dotenv-load := true

# Print available commands
default:
    @just --list

# First-time project setup
setup:
    cp -n .env.example .env || true
    docker compose up -d postgres redis
    pnpm install
    cd services/api && uv sync
    cd services/worker && uv sync
    @just _wait-db
    @just _create-app-role
    @just db-migrate
    @echo "✅ Setup complete. Run 'just dev' to start."

# Wait for postgres to be healthy
_wait-db:
    @until docker compose exec postgres pg_isready -U threados_migrate -d threados > /dev/null 2>&1; do sleep 1; done

# Create the restricted runtime DB role (idempotent)
_create-app-role:
    psql "$DATABASE_MIGRATE_URL" -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'threados_app') THEN CREATE ROLE threados_app LOGIN PASSWORD 'password' NOSUPERUSER NOBYPASSRLS; END IF; END \$\$;"
    psql "$DATABASE_MIGRATE_URL" -c "GRANT CONNECT ON DATABASE threados TO threados_app;"
    psql "$DATABASE_MIGRATE_URL" -c "GRANT USAGE ON SCHEMA public TO threados_app;"
    psql "$DATABASE_MIGRATE_URL" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO threados_app;"

# Run Alembic migrations to latest
db-migrate:
    cd services/api && uv run alembic upgrade head

# Create a new Alembic migration
db-revision msg:
    cd services/api && uv run alembic revision --autogenerate -m "{{msg}}"

# Reset DB: drop, recreate, re-migrate
db-reset:
    docker compose exec postgres psql -U threados_migrate -c "DROP DATABASE IF EXISTS threados;"
    docker compose exec postgres psql -U threados_migrate -c "CREATE DATABASE threados;"
    @just _create-app-role
    @just db-migrate

# Start all services in dev mode (requires separate terminals or use tmux)
dev:
    @echo "Start these in separate terminals:"
    @echo "  just dev-api"
    @echo "  just dev-worker"
    @echo "  just dev-web"

dev-api:
    cd services/api && uv run uvicorn app.main:app --reload --port 8000

dev-worker:
    cd services/worker && uv run rq worker --url $REDIS_URL default

dev-web:
    pnpm --filter web dev

# Lint everything
lint:
    cd services/api && uv run ruff check .
    cd services/worker && uv run ruff check .
    pnpm turbo lint

# Type-check Python and TS
type-check:
    cd services/api && uv run mypy app
    pnpm turbo type-check

# Run all tests
test:
    cd services/api && uv run pytest
    cd services/worker && uv run pytest

# Tear down local infra
down:
    docker compose down
