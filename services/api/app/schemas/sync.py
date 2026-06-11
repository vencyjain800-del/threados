"""
Pydantic schemas for the sync API — Sprint 3 Phase B.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SyncRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    entities: dict[str, Any]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class SyncRunListResponse(BaseModel):
    items: list[SyncRunSchema]
    total: int


class SyncTriggerResponse(BaseModel):
    triggered: bool
    sync_run_id: uuid.UUID | None = None
    message: str
