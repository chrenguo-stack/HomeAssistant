from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker

from .history_store import (
    HistoryCapacityExceeded,
    HistoryConflict,
    HistoryStore,
    HistoryStoreError,
)
from .ingest import PublishMessage
from .topics import history_replay_ack_topic, parse_history_replay_topic

HistoryReplayStatus = Literal["accepted", "duplicate", "rejected", "retry"]
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_ESTIMATED_CLOCK_TOLERANCE = timedelta(seconds=1)


@dataclass(frozen=True, slots=True)
class HistoryReplayResult:
    status: HistoryReplayStatus
    node_id: str | None
    batch_id: str | None = None
    page_index: int | None = None
    messages: tuple[PublishMessage, ...] = ()
    reason: str | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def _parse_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON object key: {key}")
        document[key] = value
    return document


def _canonical_payload_sha256(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HistoryReplayProcessor:
    """Validate and durably commit C-06 pages without touching canonical state."""

    def __init__(
        self,
        *,
        system_id: str,
        store: HistoryStore,
        retention_days: int = 7,
        max_future_skew_s: int = 300,
        max_records_per_page: int = 256,
        max_payload_bytes: int = 262_144,
        schema: dict[str, Any] | None = None,
    ) -> None:
        if not 1 <= retention_days <= 30:
            raise ValueError("retention_days must be between 1 and 30")
        if not 0 <= max_future_skew_s <= 86_400:
            raise ValueError("max_future_skew_s must be between 0 and 86400")
        if not 1 <= max_records_per_page <= 256:
            raise ValueError("max_records_per_page must be between 1 and 256")
        if not 4_096 <= max_payload_bytes <= 1_048_576:
            raise ValueError("max_payload_bytes must be between 4096 and 1048576")
        self.system_id = system_id
        self.store = store
        self.retention = timedelta(days=retention_days)
        self.max_future_skew = timedelta(seconds=max_future_skew_s)
        self.max_records_per_page = max_records_per_page
        self.max_payload_bytes = max_payload_bytes
        self.validator = Draft202012Validator(
            schema or self._load_packaged_schema(),
            format_checker=FormatChecker(),
        )

    @staticmethod
    def _load_packaged_schema() -> dict[str, Any]:
        package = files("greenhouse_manager")
        history_path = package.joinpath("schemas/gh.history-replay.batch-1.schema.json")
        telemetry_path = package.joinpath("schemas/gh.telemetry-1.schema.json")
        history = json.loads(history_path.read_text(encoding="utf-8"))
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        record_properties = history["$defs"]["record"]["properties"]
        for field in ("measurements", "quality", "power"):
            record_properties[field] = copy.deepcopy(telemetry["properties"][field])
        history["$defs"]["quality"] = copy.deepcopy(telemetry["$defs"]["quality"])
        return history

    @staticmethod
    def _ack_identity(document: dict[str, Any]) -> tuple[str, int, int] | None:
        batch_id = document.get("batch_id")
        page_index = document.get("page_index")
        page_count = document.get("page_count")
        if not isinstance(batch_id, str) or _BATCH_ID_RE.fullmatch(batch_id) is None:
            return None
        if type(page_index) is not int or not 0 <= page_index <= 4_095:
            return None
        if type(page_count) is not int or not 1 <= page_count <= 4_096:
            return None
        if page_index >= page_count:
            return None
        return batch_id, page_index, page_count

    def _ack(
        self,
        *,
        node_id: str,
        batch_id: str,
        page_index: int,
        page_count: int,
        status: Literal["accepted", "duplicate", "rejected"],
        processed_at: datetime,
        records_total: int,
        inserted_records: int,
        duplicate_records: int,
        next_page_index: int | None,
        reason: str | None = None,
    ) -> PublishMessage:
        payload: dict[str, Any] = {
            "schema": "gh.history-replay.ack/1",
            "node_id": node_id,
            "batch_id": batch_id,
            "page_index": page_index,
            "page_count": page_count,
            "status": status,
            "committed": status != "rejected",
            "records_total": records_total,
            "inserted_records": inserted_records,
            "duplicate_records": duplicate_records,
            "next_page_index": next_page_index,
            "processed_at": _timestamp(processed_at),
        }
        if reason is not None:
            payload["reason"] = reason[:512]
        return PublishMessage(
            topic=history_replay_ack_topic(self.system_id, node_id),
            payload=payload,
            qos=1,
            retain=False,
        )

    def _reject(
        self,
        *,
        node_id: str,
        document: dict[str, Any],
        reason: str,
        processed_at: datetime,
    ) -> HistoryReplayResult:
        identity = self._ack_identity(document)
        messages: tuple[PublishMessage, ...] = ()
        batch_id: str | None = None
        page_index: int | None = None
        if identity is not None:
            batch_id, page_index, page_count = identity
            records = document.get("records")
            records_total = len(records) if isinstance(records, list) else 0
            messages = (
                self._ack(
                    node_id=node_id,
                    batch_id=batch_id,
                    page_index=page_index,
                    page_count=page_count,
                    status="rejected",
                    processed_at=processed_at,
                    records_total=min(records_total, 256),
                    inserted_records=0,
                    duplicate_records=0,
                    next_page_index=page_index,
                    reason=reason,
                ),
            )
        return HistoryReplayResult(
            status="rejected",
            node_id=node_id,
            batch_id=batch_id,
            page_index=page_index,
            messages=messages,
            reason=reason,
        )

    def _validate_record_time(self, record: dict[str, Any], *, now: datetime) -> str | None:
        quality = str(record["time_quality"])
        sampled_raw = record.get("sampled_at")
        anchor = record.get("time_anchor")
        if quality == "relative_only":
            if sampled_raw is not None or anchor is not None:
                return "relative_only records require sampled_at=null and time_anchor=null"
            return None

        if not isinstance(sampled_raw, str):
            return "trusted or estimated records require sampled_at"
        try:
            sampled_at = _parse_timestamp(sampled_raw)
        except ValueError as error:
            return f"invalid sampled_at: {error}"
        if sampled_at > now + self.max_future_skew:
            return "sampled_at exceeds configured future clock skew"
        if sampled_at < now - self.retention:
            return "sampled_at is older than the configured raw-history retention window"

        if quality == "trusted":
            if anchor is not None:
                return "trusted records require time_anchor=null"
            return None

        if quality != "estimated" or not isinstance(anchor, dict):
            return "estimated records require a time_anchor object"
        try:
            anchor_time = _parse_timestamp(str(anchor["sampled_at"]))
            anchor_uptime = int(anchor["uptime_ms"])
            uptime = int(record["uptime_ms"])
        except (KeyError, TypeError, ValueError) as error:
            return f"invalid estimated time anchor: {error}"
        if uptime < anchor_uptime:
            return "estimated record uptime_ms precedes time anchor uptime_ms"
        expected = anchor_time + timedelta(milliseconds=uptime - anchor_uptime)
        if abs(sampled_at - expected) > _ESTIMATED_CLOCK_TOLERANCE:
            return "estimated sampled_at does not match time anchor and uptime_ms"
        return None

    def process(
        self,
        topic: str,
        payload: bytes | str,
        *,
        retained: bool = False,
        node_allowed: bool = True,
        received_at: datetime | None = None,
    ) -> HistoryReplayResult:
        now = _utc(received_at or datetime.now(UTC))
        try:
            parsed_topic = parse_history_replay_topic(topic)
        except ValueError as error:
            return HistoryReplayResult(status="rejected", node_id=None, reason=str(error))

        if parsed_topic.system_id != self.system_id:
            return HistoryReplayResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="topic system_id does not match manager system_id",
            )

        try:
            payload_bytes = (
                payload if isinstance(payload, bytes) else payload.encode("utf-8")
            )
        except UnicodeEncodeError as error:
            return HistoryReplayResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason=f"invalid UTF-8 payload: {error}",
            )
        if len(payload_bytes) > self.max_payload_bytes:
            return HistoryReplayResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="history payload exceeds configured byte limit",
            )

        try:
            document = json.loads(
                payload_bytes.decode("utf-8"),
                parse_constant=_reject_json_constant,
                parse_float=_parse_json_float,
                object_pairs_hook=_unique_json_object,
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            RecursionError,
        ) as error:
            return HistoryReplayResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason=f"invalid JSON payload: {error}",
            )
        if not isinstance(document, dict):
            return HistoryReplayResult(
                status="rejected",
                node_id=parsed_topic.node_id,
                reason="history payload must be a JSON object",
            )

        errors = sorted(
            self.validator.iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            error = errors[0]
            path = ".".join(str(part) for part in error.absolute_path) or "$"
            return self._reject(
                node_id=parsed_topic.node_id,
                document=document,
                reason=f"schema validation failed at {path}: {error.message}",
                processed_at=now,
            )

        node_id = str(document["node_id"])
        if node_id != parsed_topic.node_id:
            return self._reject(
                node_id=parsed_topic.node_id,
                document=document,
                reason="payload node_id does not match topic node_id",
                processed_at=now,
            )
        if int(document["page_index"]) >= int(document["page_count"]):
            return self._reject(
                node_id=node_id,
                document=document,
                reason="page_index must be less than page_count",
                processed_at=now,
            )
        records = document["records"]
        assert isinstance(records, list)
        if len(records) > self.max_records_per_page:
            return self._reject(
                node_id=node_id,
                document=document,
                reason="history page exceeds configured record limit",
                processed_at=now,
            )
        record_keys = {(str(record["boot_id"]), int(record["seq"])) for record in records}
        if len(record_keys) != len(records):
            return self._reject(
                node_id=node_id,
                document=document,
                reason="duplicate boot_id + seq inside one history page",
                processed_at=now,
            )
        if retained:
            return self._reject(
                node_id=node_id,
                document=document,
                reason="retained history replay pages are forbidden",
                processed_at=now,
            )
        if not node_allowed:
            return self._reject(
                node_id=node_id,
                document=document,
                reason="history replay is not allowed for retired or unassigned node",
                processed_at=now,
            )
        for index, record in enumerate(records):
            reason = self._validate_record_time(record, now=now)
            if reason is not None:
                return self._reject(
                    node_id=node_id,
                    document=document,
                    reason=f"invalid record time at records.{index}: {reason}",
                    processed_at=now,
                )

        batch_id = str(document["batch_id"])
        page_index = int(document["page_index"])
        page_count = int(document["page_count"])
        try:
            committed = self.store.commit_page(
                node_id=node_id,
                batch_id=batch_id,
                page_index=page_index,
                page_count=page_count,
                records=records,
                payload_sha256=_canonical_payload_sha256(document),
                received_at=now,
            )
        except (HistoryConflict, HistoryCapacityExceeded) as error:
            return self._reject(
                node_id=node_id,
                document=document,
                reason=str(error),
                processed_at=now,
            )
        except (sqlite3.Error, HistoryStoreError, OSError, ValueError) as error:
            return HistoryReplayResult(
                status="retry",
                node_id=node_id,
                batch_id=batch_id,
                page_index=page_index,
                reason=f"durable history commit failed: {type(error).__name__}",
            )

        status: Literal["accepted", "duplicate"] = (
            "duplicate" if committed.status == "duplicate" else "accepted"
        )
        ack = self._ack(
            node_id=node_id,
            batch_id=batch_id,
            page_index=page_index,
            page_count=page_count,
            status=status,
            processed_at=now,
            records_total=committed.record_count,
            inserted_records=committed.inserted_count,
            duplicate_records=committed.duplicate_count,
            next_page_index=committed.next_page_index,
        )
        return HistoryReplayResult(
            status=status,
            node_id=node_id,
            batch_id=batch_id,
            page_index=page_index,
            messages=(ack,),
        )
