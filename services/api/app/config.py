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

    # Database pool (main runtime engine only; auth engine is hardcoded at 5/10)
    db_pool_size: int = 10
    db_max_overflow: int = 20

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

    def validate_required_for_shopify(self) -> list[str]:
        """Return a list of missing env var names required for Shopify OAuth."""
        missing: list[str] = []
        if not self.shopify_api_key:
            missing.append("SHOPIFY_API_KEY")
        if not self.shopify_api_secret:
            missing.append("SHOPIFY_API_SECRET")
        if not self.shopify_app_url:
            missing.append("SHOPIFY_APP_URL")
        if not self.shopify_redirect_uri:
            missing.append("SHOPIFY_REDIRECT_URI")
        if not self.kms_key_id:
            missing.append("KMS_KEY_ID")
        return missing

    def validate_required_for_auth(self) -> list[str]:
        """Return a list of missing env var names required for auth security."""
        missing: list[str] = []
        # Minimum 32-char entropy for secret values.
        if len(self.session_secret) < 32:
            missing.append("SESSION_SECRET (must be ≥32 chars)")
        if len(self.csrf_secret) < 32:
            missing.append("CSRF_SECRET (must be ≥32 chars)")
        return missing


settings = Settings()  # type: ignore[call-arg]
