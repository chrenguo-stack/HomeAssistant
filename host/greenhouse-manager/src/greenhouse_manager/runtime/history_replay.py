from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker

from .history_store import HistoryConflict, HistoryStore, HistoryStoreError
from .ingest import PublishMessage
from .topics import history_replay_ack_topic, parse_history_replay_topic

HistoryReplayStatus = Literal["accepted", "duplicate", "rejected", "retry"]
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


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
        max_records_per_page: int = 256,
        max_payload_bytes: int = 262_144,
        schema: dict[str, Any] | None = None,
    ) -> None:
        if not 1 <= max_records_per_page <= 256:
            raise ValueError("max_records_per_page must be between 1 and 256")
        if not 4096 <= max_payload_bytes <= 1_048_576:
            raise ValueError("max_payload_bytes must be between 4096 and 1048576")
        self.system_id = system_id
        self.store = store
        self.max_records_per_page = max_records_per_page
        self.max_payload_bytes = max_payload_bytes
        self.validator = Draft202012Validator(
            schema or self._load_packaged_schema(),
            format_checker=FormatChecker(),
        )

    @staticmethod
    def _load_packaged_schema() -> dict[str, Any]:
        path = files("greenhouse_manager").joinpath(
            "schemas/gh.history-replay.batch-1.schema.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _ack_identity(document: dict[str, Any]) -> tuple[str, int, int] | None:
        batch_id = document.get("batch_id")
        page_index = document.get("page_index")
        page_count = document.get("page_count")
        if not isinstance(batch_id, str) or _BATCH_ID_RE.fullmatch(batch_id) is None:
            return None
        if type(page_index) is not int or not 0 <= page_index <= 4095:
            return None
        if type(page_count) is not int or not 1 <= page_count <= 4096:
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
        reason: str | None = None,
    ) -> PublishMessage:
        if status == "rejected":
            next_page_index: int | None = page_index
        else:
            next_page_index = page_index + 1 if page_index + 1 < page_count else None
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
        except HistoryConflict as error:
            return self._reject(
                node_id=node_id,
                document=document,
                reason=str(error),
                processed_at=now,
            )
        except (sqlite3.Error, HistoryStoreError, OSError) as error:
            return HistoryReplayResult(
                status="retry",
                node_id=node_id,
                batch_id=batch_id,
                page_index=page_index,
                reason=f"durable history commit failed: {type(error).__name__}",
            )

        ack = self._ack(
            node_id=node_id,
            batch_id=batch_id,
            page_index=page_index,
            page_count=page_count,
            status="duplicate" if committed.status == "duplicate" else "accepted",
            processed_at=now,
            records_total=committed.record_count,
            inserted_records=committed.inserted_count,
            duplicate_records=committed.duplicate_count,
        )
        return HistoryReplayResult(
            status="duplicate" if committed.status == "duplicate" else "accepted",
            node_id=node_id,
            batch_id=batch_id,
            page_index=page_index,
            messages=(ack,),
        )
