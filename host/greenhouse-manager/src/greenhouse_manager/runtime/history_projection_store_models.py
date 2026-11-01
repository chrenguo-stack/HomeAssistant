from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .history_store import _parse_timestamp

ProjectionJobState = Literal["pending", "leased", "retry", "blocked", "completed"]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_PROJECTION_PAYLOAD_BYTES = 1_048_576


class ProjectionStoreError(RuntimeError):
    """Base class for C06-B1 projection storage failures."""


@dataclass(frozen=True, slots=True)
class ProjectionTask:
    node_id: str
    sample_hour: str
    projection_version: int
    revision: int
    attempts: int
    claimed_by: str
    lease_until: datetime


@dataclass(frozen=True, slots=True)
class ProjectionJobSnapshot:
    node_id: str
    sample_hour: str
    projection_version: int
    revision: int
    state: ProjectionJobState
    attempts: int
    claimed_by: str | None
    lease_until: datetime | None
    next_attempt_at: datetime | None
    last_error_code: str | None
    last_error: str | None
    projection_hash: str | None
    payload_json: str | None
    adapter_kind: str | None
    adapter_version: str | None
    verified_at: datetime | None
    completed_at: datetime | None
    requeue_count: int
    last_requeued_at: datetime | None
    last_requeue_reason: str | None


def optional_timestamp(value: object) -> datetime | None:
    return _parse_timestamp(str(value)) if value is not None else None


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)
