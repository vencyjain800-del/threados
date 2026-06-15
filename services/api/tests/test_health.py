"""
Health endpoint tests — O-03.

Covers:
  H1  GET /health/live     → always 200 {"status": "ok"}
  H2  GET /health/ready    → 200 when DB reachable
  H3  GET /health/staleness
      - returns 200 with correct envelope fields
      - empty brands list when no active Shopify connections
      - brand with recent run_at is NOT stale
      - brand with run_at > 24h ago IS stale
      - brand with active connection but no recommendations IS stale (never ran)
      - stale_count and any_stale are consistent with brands list
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient  # noqa: TC002

pytestmark = pytest.mark.asyncio

_BRAND_A = str(uuid.uuid4())
_BRAND_B = str(uuid.uuid4())


def _mock_system_session(rows: list[MagicMock]):
    """Return a context-manager patch for system_session that replays *rows*."""

    @asynccontextmanager
    async def _cm():
        db = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = rows
        db.execute.return_value = result
        yield db

    return patch("app.routers.health.system_session", side_effect=_cm)


def _row(brand_id: str, last_run_at: datetime | None) -> MagicMock:
    r = MagicMock()
    r.brand_id = brand_id
    r.last_run_at = last_run_at
    return r


# ── H1: liveness ──────────────────────────────────────────────────────────────

async def test_liveness(client: AsyncClient) -> None:
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── H2: readiness ─────────────────────────────────────────────────────────────

async def test_readiness(client: AsyncClient) -> None:
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── H3: staleness ─────────────────────────────────────────────────────────────

async def test_staleness_envelope(client: AsyncClient) -> None:
    """Response always contains the required top-level keys."""
    with _mock_system_session([]):
        resp = await client.get("/health/staleness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["threshold_hours"] == 24
    assert "checked_at" in body
    assert "total_count" in body
    assert "stale_count" in body
    assert "any_stale" in body
    assert "brands" in body
    assert isinstance(body["brands"], list)


async def test_staleness_no_active_connections(client: AsyncClient) -> None:
    """No active Shopify connections → empty brands list, any_stale=False."""
    with _mock_system_session([]):
        resp = await client.get("/health/staleness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 0
    assert body["stale_count"] == 0
    assert body["any_stale"] is False
    assert body["brands"] == []


async def test_staleness_fresh_brand(client: AsyncClient) -> None:
    """Brand whose recs ran <24h ago is NOT stale."""
    recent = datetime.now(tz=UTC) - timedelta(hours=1)
    rows = [_row(_BRAND_A, recent)]

    with _mock_system_session(rows):
        resp = await client.get("/health/staleness")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 1
    assert body["stale_count"] == 0
    assert body["any_stale"] is False
    entry = body["brands"][0]
    assert entry["brand_id"] == _BRAND_A
    assert entry["is_stale"] is False
    assert entry["hours_since_last_run"] is not None
    assert entry["hours_since_last_run"] < 24


async def test_staleness_stale_brand(client: AsyncClient) -> None:
    """Brand whose recs ran >24h ago IS stale."""
    old = datetime.now(tz=UTC) - timedelta(hours=30)
    rows = [_row(_BRAND_A, old)]

    with _mock_system_session(rows):
        resp = await client.get("/health/staleness")

    assert resp.status_code == 200
    body = resp.json()
    assert body["stale_count"] == 1
    assert body["any_stale"] is True
    entry = body["brands"][0]
    assert entry["is_stale"] is True
    assert entry["hours_since_last_run"] > 24


async def test_staleness_never_ran(client: AsyncClient) -> None:
    """Brand with active connection but no recs rows IS stale (last_run_at=null)."""
    rows = [_row(_BRAND_A, None)]

    with _mock_system_session(rows):
        resp = await client.get("/health/staleness")

    assert resp.status_code == 200
    body = resp.json()
    entry = body["brands"][0]
    assert entry["is_stale"] is True
    assert entry["last_run_at"] is None
    assert entry["hours_since_last_run"] is None


async def test_staleness_counts_consistent(client: AsyncClient) -> None:
    """stale_count == count of stale brands; any_stale is correct."""
    recent = datetime.now(tz=UTC) - timedelta(hours=2)
    old = datetime.now(tz=UTC) - timedelta(hours=48)
    rows = [_row(_BRAND_A, recent), _row(_BRAND_B, old)]

    with _mock_system_session(rows):
        resp = await client.get("/health/staleness")

    assert resp.status_code == 200
    body = resp.json()
    computed_stale = sum(1 for b in body["brands"] if b["is_stale"])
    assert body["stale_count"] == computed_stale
    assert body["any_stale"] == (computed_stale > 0)
    assert body["total_count"] == 2
    assert body["stale_count"] == 1
