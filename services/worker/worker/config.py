"""
Worker service settings.

Loaded from environment variables and .env files.
pydantic-settings merges both; env vars take precedence over .env files.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    # Owner-role DB URL (threados_migrate / rolbypassrls=True).
    # The worker uses the owner role for all writes so it can insert with explicit
    # brand_id without needing to call set_config() before every transaction.
    # Tenant isolation is enforced at the application layer (brand_id always set).
    database_migrate_url: str = Field(
        default="postgresql+psycopg://threados_migrate:password@localhost:5432/threados"
    )

    # Redis URL used by the worker's scheduler to enqueue recurring jobs.
    # Must match the REDIS_URL used by the API service's RQ connection.
    redis_url: str = Field(default="redis://localhost:6379/0")

    shopify_api_version: str = "2025-07"

    # How many hours between automatic incremental syncs for each connected brand.
    # Lower values increase API calls; the Shopify plan's rate limit is the ceiling.
    incremental_interval_hours: int = Field(default=6)

    model_config = SettingsConfigDict(
        # Look for .env in the worker directory first, then the monorepo root
        env_file=[".env", "../../.env"],
        extra="ignore",
    )


settings = WorkerSettings()
