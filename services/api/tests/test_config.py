"""Tests for Settings validation and pool configuration."""
import pytest

from app.config import Settings

_BASE = {
    "database_url": "postgresql://x",
    "database_migrate_url": "postgresql://x",
    "session_secret": "a" * 32,
    "csrf_secret": "b" * 32,
}

_SHOPIFY_FULL = {
    "shopify_api_key": "key123",
    "shopify_api_secret": "secret123",
    "shopify_app_url": "https://example.ngrok.io",
    "shopify_redirect_uri": "https://example.ngrok.io/callback",
    "kms_key_id": "arn:aws:kms:eu-west-2:1234:key/abc",
}


def test_validate_shopify_flags_missing_key_and_secret():
    s = Settings(**_BASE, **{**_SHOPIFY_FULL, "shopify_api_key": "", "shopify_api_secret": ""})
    missing = s.validate_required_for_shopify()
    assert "SHOPIFY_API_KEY" in missing
    assert "SHOPIFY_API_SECRET" in missing


def test_validate_shopify_passes_when_all_set():
    s = Settings(**_BASE, **_SHOPIFY_FULL)
    missing = s.validate_required_for_shopify()
    assert "SHOPIFY_API_KEY" not in missing
    assert "SHOPIFY_API_SECRET" not in missing


@pytest.mark.parametrize("field,expected", [
    ("shopify_api_key", "SHOPIFY_API_KEY"),
    ("shopify_api_secret", "SHOPIFY_API_SECRET"),
    ("shopify_app_url", "SHOPIFY_APP_URL"),
    ("shopify_redirect_uri", "SHOPIFY_REDIRECT_URI"),
    ("kms_key_id", "KMS_KEY_ID"),
])
def test_validate_shopify_flags_each_missing_field(field: str, expected: str):
    overrides = {**_SHOPIFY_FULL, field: ""}
    s = Settings(**_BASE, **overrides)
    missing = s.validate_required_for_shopify()
    assert expected in missing


def test_db_pool_size_defaults():
    s = Settings(**_BASE)
    assert s.db_pool_size == 10
    assert s.db_max_overflow == 20


def test_db_pool_size_overridable():
    s = Settings(**_BASE, db_pool_size=5, db_max_overflow=10)
    assert s.db_pool_size == 5
    assert s.db_max_overflow == 10
