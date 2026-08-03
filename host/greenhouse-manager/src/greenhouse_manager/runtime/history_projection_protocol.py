from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from .history_projection_aggregate import canonical_json
from .history_projection_contract import ProjectionBatch

REQUEST_SCHEMA = "gh.c06b2-ha-projection-request/1"
RESULT_SCHEMA = "gh.c06b2-ha-projection-result/1"
PROJECTION_SCHEMA = "gh.c06-hourly-projection/1"
ResultStatus = Literal["verified", "retry", "blocked"]

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_REQUEST_SCHEMA_FILE = "gh.c06b2-ha-projection-request-1.schema.json"
_RESULT_SCHEMA_FILE = "gh.c06b2-ha-projection-result-1.schema.json"
_PROJECTION_SCHEMA_FILE = "gh.c06-hourly-projection-1.schema.json"
_FORMAT_CHECKER = FormatChecker()


class ProjectionProtocolError(ValueError):
    """Raised when a C06-B2 MQTT RPC document violates the frozen contract."""


def _load_schema(name: str) -> dict[str, Any]:
    raw = files("greenhouse_manager.schemas").joinpath(name).read_text(encoding="utf-8")
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise RuntimeError(f"schema {name} is not a JSON object")
    Draft202012Validator.check_schema(document)
    return document


_REQUEST_VALIDATOR = Draft202012Validator(
    _load_schema(_REQUEST_SCHEMA_FILE), format_checker=_FORMAT_CHECKER
)
_RESULT_VALIDATOR = Draft202012Validator(
    _load_schema(_RESULT_SCHEMA_FILE), format_checker=_FORMAT_CHECKER
)
_PROJECTION_VALIDATOR = Draft202012Validator(
    _load_schema(_PROJECTION_SCHEMA_FILE), format_checker=_FORMAT_CHECKER
)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProjectionProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_finite_float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ProjectionProtocolError("non-finite JSON number")
    return value


def _reject_constant(raw: str) -> None:
    raise ProjectionProtocolError(f"invalid JSON constant: {raw}")


def strict_json_document(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        encoded = canonical_json(payload)
    elif isinstance(payload, bytes):
        try:
            encoded = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProjectionProtocolError("payload must contain UTF-8 JSON") from exc
    elif isinstance(payload, str):
        encoded = payload
    else:
        raise ProjectionProtocolError("payload must be bytes, text, or an object")
    try:
        document = json.loads(
            encoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_parse_finite_float,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, ProjectionProtocolError):
            raise
        raise ProjectionProtocolError(f"invalid JSON document: {exc}") from exc
    if not isinstance(document, dict):
        raise ProjectionProtocolError("payload root must be a JSON object")
    return document


def _validate(validator: Draft202012Validator, document: dict[str, Any], label: str) -> None:
    try:
        validator.validate(document)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        suffix = f" at {location}" if location else ""
        raise ProjectionProtocolError(f"invalid {label}{suffix}: {exc.message}") from exc


def _validate_system_id(system_id: str) -> None:
    if not _ID_RE.fullmatch(system_id):
        raise ProjectionProtocolError("system_id must match [A-Za-z0-9_-]{3,64}")


def _validate_utc_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectionProtocolError(f"{field} must be an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ProjectionProtocolError(f"{field} must use UTC")


def projection_request_topic(system_id: str) -> str:
    _validate_system_id(system_id)
    return f"gh/v1/{system_id}/out/homeassistant/history/projection"


def projection_result_topic(system_id: str) -> str:
    _validate_system_id(system_id)
    return f"gh/v1/{system_id}/ingress/homeassistant/history/projection/result"


def projection_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_projection_payload(payload: dict[str, Any]) -> None:
    _validate(_PROJECTION_VALIDATOR, payload, "hourly projection")
    node_id = str(payload["node_id"])
    sample_hour = str(payload["sample_hour"])
    projection_version = int(payload["projection_version"])
    expected_key = f"{node_id}|{sample_hour}|v{projection_version}"
    if payload["idempotency_key"] != expected_key:
        raise ProjectionProtocolError("projection idempotency_key does not match its identity")
    _validate_utc_timestamp(sample_hour, "projection.sample_hour")


@dataclass(frozen=True, slots=True)
class HomeAssistantProjectionRequest:
    request_id: str
    system_id: str
    sent_at: str
    projection_hash: str
    projection: dict[str, Any]

    @property
    def idempotency_key(self) -> str:
        return str(self.projection["idempotency_key"])

    @property
    def revision(self) -> int:
        return int(self.projection["revision"])

    def as_document(self) -> dict[str, Any]:
        return {
            "schema": REQUEST_SCHEMA,
            "request_id": self.request_id,
            "system_id": self.system_id,
            "sent_at": self.sent_at,
            "projection_hash": self.projection_hash,
            "projection": self.projection,
        }

    def as_payload(self) -> bytes:
        return canonical_json(self.as_document()).encode("utf-8")


@dataclass(frozen=True, slots=True)
class HomeAssistantProjectionResult:
    request_id: str
    status: ResultStatus
    idempotency_key: str
    revision: int
    projection_hash: str
    monotonic_revision_enforced: bool
    verified_at: str | None
    code: str | None
    detail: str | None

    def as_document(self) -> dict[str, Any]:
        return {
            "schema": RESULT_SCHEMA,
            "request_id": self.request_id,
            "status": self.status,
            "idempotency_key": self.idempotency_key,
            "revision": self.revision,
            "projection_hash": self.projection_hash,
            "monotonic_revision_enforced": self.monotonic_revision_enforced,
            "verified_at": self.verified_at,
            "code": self.code,
            "detail": self.detail,
        }

    def as_payload(self) -> bytes:
        return canonical_json(self.as_document()).encode("utf-8")


def build_projection_request(
    *,
    batch: ProjectionBatch,
    system_id: str,
    request_id: str,
    sent_at: datetime,
) -> HomeAssistantProjectionRequest:
    _validate_system_id(system_id)
    if sent_at.tzinfo is None or sent_at.utcoffset() != UTC.utcoffset(sent_at):
        raise ProjectionProtocolError("sent_at must use UTC")
    sent_at_text = sent_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    request = HomeAssistantProjectionRequest(
        request_id=request_id,
        system_id=system_id,
        sent_at=sent_at_text,
        projection_hash=batch.projection_hash,
        projection=dict(batch.payload),
    )
    return parse_projection_request(request.as_document(), expected_system_id=system_id)


def parse_projection_request(
    payload: bytes | str | dict[str, Any], *, expected_system_id: str
) -> HomeAssistantProjectionRequest:
    _validate_system_id(expected_system_id)
    document = strict_json_document(payload)
    _validate(_REQUEST_VALIDATOR, document, "Home Assistant projection request")
    if document["system_id"] != expected_system_id:
        raise ProjectionProtocolError("request system_id does not match the configured system")
    _validate_utc_timestamp(str(document["sent_at"]), "sent_at")
    projection = document["projection"]
    if not isinstance(projection, dict):
        raise ProjectionProtocolError("projection must be an object")
    validate_projection_payload(projection)
    calculated_hash = projection_hash(projection)
    if document["projection_hash"] != calculated_hash:
        raise ProjectionProtocolError("projection_hash does not match canonical projection payload")
    return HomeAssistantProjectionRequest(
        request_id=str(document["request_id"]),
        system_id=str(document["system_id"]),
        sent_at=str(document["sent_at"]),
        projection_hash=str(document["projection_hash"]),
        projection=projection,
    )


def build_projection_result(
    *,
    request: HomeAssistantProjectionRequest,
    status: ResultStatus,
    monotonic_revision_enforced: bool,
    verified_at: datetime | None = None,
    code: str | None = None,
    detail: str | None = None,
) -> HomeAssistantProjectionResult:
    verified_at_text = None
    if verified_at is not None:
        if verified_at.tzinfo is None or verified_at.utcoffset() != UTC.utcoffset(verified_at):
            raise ProjectionProtocolError("verified_at must use UTC")
        verified_at_text = verified_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    result = HomeAssistantProjectionResult(
        request_id=request.request_id,
        status=status,
        idempotency_key=request.idempotency_key,
        revision=request.revision,
        projection_hash=request.projection_hash,
        monotonic_revision_enforced=monotonic_revision_enforced,
        verified_at=verified_at_text,
        code=code,
        detail=detail,
    )
    return parse_projection_result(result.as_document())


def parse_projection_result(
    payload: bytes | str | dict[str, Any],
) -> HomeAssistantProjectionResult:
    document = strict_json_document(payload)
    _validate(_RESULT_VALIDATOR, document, "Home Assistant projection result")
    verified_at = document.get("verified_at")
    if isinstance(verified_at, str):
        _validate_utc_timestamp(verified_at, "verified_at")
    return HomeAssistantProjectionResult(
        request_id=str(document["request_id"]),
        status=document["status"],
        idempotency_key=str(document["idempotency_key"]),
        revision=int(document["revision"]),
        projection_hash=str(document["projection_hash"]),
        monotonic_revision_enforced=bool(document["monotonic_revision_enforced"]),
        verified_at=verified_at,
        code=document.get("code"),
        detail=document.get("detail"),
    )
