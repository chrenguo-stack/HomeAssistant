from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker

from .topics import (
    availability_topic,
    canonical_telemetry_topic,
    parse_canonical_telemetry_topic,
    parse_node_telemetry_topic,
)

ProcessStatus = Literal["accepted", "duplicate", "rejected"]
RestoreStatus = Literal["restored", "rejected"]


@dataclass(frozen=True, slots=True)
class PublishMessage:
    topic: str
    payload: dict[str, Any]
    qos: int = 1
    retain: bool = True


@dataclass(frozen=True, slots=True)
class ProcessResult:
    status: ProcessStatus
    node_id: str | None
    messages: tuple[PublishMessage, ...] = ()
    reason: str | None = None
    dedup_key: tuple[str, str, int] | None = None


@dataclass(frozen=True, slots=True)
class RestoreResult:
    status: RestoreStatus
    node_id: str | None
    reason: str | None = None
    dedup_key: tuple[str, str, int] | None = None
    last_seen: datetime | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_rfc3339(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("received_at must be an RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("received_at must be a valid RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("received_at must include a timezone")
    return parsed.astimezone(UTC)


class TelemetryProcessor:
    """Validate ingress telemetry and produce retained canonical state messages."""

    def __init__(
        self,
        *,
        system_id: str,
        dedup_capacity: int = 4096,
        stale_after_s: int = 180,
        schema: dict[str, Any] | None = None,
    ) -> None:
        if dedup_capacity < 128:
            raise ValueError("dedup_capacity must be at least 128")
        if stale_after_s < 30:
            raise ValueError("stale_after_s must be at least 30")

        self.system_id = system_id
        self.dedup_capacity = dedup_capacity
        self.stale_after = timedelta(seconds=stale_after_s)
        self.validator = Draft202012Validator(
            schema or self._load_packaged_schema(),
            format_checker=FormatChecker(),
        )
        self._seen: OrderedDict[tuple[str, str, int], None] = OrderedDict()
        self._last_seen: dict[str, datetime] = {}
        self._availability: dict[str, str] = {}

    @staticmethod
    def _load_packaged_schema() -> dict[str, Any]:
        schema_path = files("greenhouse_manager").joinpath("schemas/gh.telemetry-1.schema.json")
        with schema_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _remember_dedup_key(self, key: tuple[str, str, int]) -> None:
        self._seen[key] = None
        self._seen.move_to_end(key)
        while len(self._seen) > self.dedup_capacity:
            self._seen.popitem(last=False)

    def process(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> ProcessResult:
        now = received_at or _utc_now()

        try:
            parsed_topic = parse_node_telemetry_topic(topic)
        except ValueError as exc:
            return ProcessResult(status="rejected", node_id=None, reason=str(exc))

        if parsed_topic.system_id != self.system_id:
            return ProcessResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="topic system_id does not match manager system_id",
            )

        try:
            text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            document = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return ProcessResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason=f"invalid JSON payload: {exc}",
            )

        if not isinstance(document, dict):
            return ProcessResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="telemetry payload must be a JSON object",
            )

        if "received_at" in document:
            return ProcessResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="ingress telemetry must not contain manager-owned received_at",
            )

        errors = sorted(self.validator.iter_errors(document), key=lambda error: list(error.absolute_path))
        if errors:
            error = errors[0]
            path = ".".join(str(part) for part in error.absolute_path) or "$"
            return ProcessResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason=f"schema validation failed at {path}: {error.message}",
            )

        node_id = str(document["node_id"])
        if node_id != parsed_topic.node_id:
            return ProcessResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="payload node_id does not match topic node_id",
            )

        dedup_key = (node_id, str(document["boot_id"]), int(document["seq"]))
        if dedup_key in self._seen:
            self._seen.move_to_end(dedup_key)
            return ProcessResult(
                status="duplicate",
                node_id=node_id,
                reason="duplicate node_id + boot_id + seq",
                dedup_key=dedup_key,
            )

        self._remember_dedup_key(dedup_key)

        canonical = dict(document)
        canonical["received_at"] = _rfc3339(now)

        availability = {
            "schema": "gh.availability/1",
            "node_id": node_id,
            "state": "online",
            "last_seen": _rfc3339(now),
        }

        self._last_seen[node_id] = now
        self._availability[node_id] = "online"

        return ProcessResult(
            status="accepted",
            node_id=node_id,
            dedup_key=dedup_key,
            messages=(
                PublishMessage(
                    topic=canonical_telemetry_topic(self.system_id, node_id),
                    payload=canonical,
                ),
                PublishMessage(
                    topic=availability_topic(self.system_id, node_id),
                    payload=availability,
                ),
            ),
        )

    def restore_canonical(self, topic: str, payload: bytes | str) -> RestoreResult:
        """Restore in-memory lifecycle state from retained canonical telemetry."""
        try:
            parsed_topic = parse_canonical_telemetry_topic(topic)
        except ValueError as exc:
            return RestoreResult(status="rejected", node_id=None, reason=str(exc))

        if parsed_topic.system_id != self.system_id:
            return RestoreResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="topic system_id does not match manager system_id",
            )

        try:
            text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            document = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return RestoreResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason=f"invalid JSON payload: {exc}",
            )

        if not isinstance(document, dict):
            return RestoreResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="canonical telemetry payload must be a JSON object",
            )

        errors = sorted(self.validator.iter_errors(document), key=lambda error: list(error.absolute_path))
        if errors:
            error = errors[0]
            path = ".".join(str(part) for part in error.absolute_path) or "$"
            return RestoreResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason=f"schema validation failed at {path}: {error.message}",
            )

        node_id = str(document["node_id"])
        if node_id != parsed_topic.node_id:
            return RestoreResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="payload node_id does not match topic node_id",
            )

        if "received_at" not in document:
            return RestoreResult(
                status="rejected",
                node_id=node_id,
                reason="canonical telemetry is missing manager-owned received_at",
            )

        try:
            last_seen = _parse_rfc3339(document["received_at"])
        except ValueError as exc:
            return RestoreResult(status="rejected", node_id=node_id, reason=str(exc))

        dedup_key = (node_id, str(document["boot_id"]), int(document["seq"]))
        self._remember_dedup_key(dedup_key)

        current_last_seen = self._last_seen.get(node_id)
        if current_last_seen is None or last_seen > current_last_seen:
            self._last_seen[node_id] = last_seen
            self._availability[node_id] = "online"

        return RestoreResult(
            status="restored",
            node_id=node_id,
            dedup_key=dedup_key,
            last_seen=last_seen,
        )

    def stale_messages(self, *, now: datetime | None = None) -> tuple[PublishMessage, ...]:
        current = now or _utc_now()
        messages: list[PublishMessage] = []

        for node_id, last_seen in self._last_seen.items():
            if current - last_seen <= self.stale_after:
                continue
            if self._availability.get(node_id) == "unavailable":
                continue

            self._availability[node_id] = "unavailable"
            messages.append(
                PublishMessage(
                    topic=availability_topic(self.system_id, node_id),
                    payload={
                        "schema": "gh.availability/1",
                        "node_id": node_id,
                        "state": "unavailable",
                        "last_seen": _rfc3339(last_seen),
                        "evaluated_at": _rfc3339(current),
                    },
                )
            )

        return tuple(messages)

    def mark_unavailable_publish_failed(self, node_id: str) -> None:
        """Allow a failed unavailable publish to be retried on the next stale scan."""
        if self._availability.get(node_id) == "unavailable":
            self._availability[node_id] = "online"
