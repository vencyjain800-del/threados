from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Try .env in the current working directory first (useful when running from
    # inside services/api/), then fall back two levels to the monorepo root.
    # Pydantic-settings merges all files found; later entries win.
    # Real secrets in staging/prod come from environment variables (AWS Secrets
    # Manager injects them), so the file is only needed locally.
    model_config = SettingsConfigDict(
        env_file=[".env", "../../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    log_level: str = "info"

    # Database
    database_url: str
    database_migrate_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    session_secret: str
    session_ttl_hours: int = 336
    cookie_domain: str = "localhost"
    csrf_secret: str

    # Shopify
    shopify_api_key: str = ""
    shopify_api_secret: str = ""
    shopify_scopes: str = "read_products,read_orders,read_inventory,read_locations,read_all_orders"
    shopify_app_url: str = ""
    shopify_redirect_uri: str = ""
    shopify_api_version: str = "2025-07"

    # AWS
    aws_region: str = "eu-west-2"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    kms_key_id: str = ""
    s3_bucket_raw: str = "threados-raw-dev"

    # Email
    postmark_server_token: str = ""

    # Observability
    sentry_dsn: str = ""

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.app_env != "development"


settings = Settings()  # type: ignore[call-arg]
