"""Pydantic contract models for idempotent event sync."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    NEEDS_MASTER_REVIEW = "needs_master_review"
    PENDING_MASTER_APPROVAL = "pending_master_approval"


class EventSyncEvent(BaseModel):
    event_id: str = Field(min_length=1)
    client_sequence: int = Field(ge=0)
    created_at: str | int | float
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventSyncRequest(BaseModel):
    device_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    actor_type: str = Field(min_length=1)
    events: list[EventSyncEvent] = Field(default_factory=list)


class EventSyncResult(BaseModel):
    event_id: str
    status: EventStatus
    reason: str | None = None
    server_event_id: int | None = None


class EventSyncResponse(BaseModel):
    server_time: str
    snapshot_version: str | None
    results: list[EventSyncResult]
