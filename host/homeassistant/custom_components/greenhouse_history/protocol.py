from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from .const import REQUEST_SCHEMA, RESULT_SCHEMA, validate_system_id

ResultStatus = Literal["verified", "retry", "blocked"]

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z0-9_]{1,96}$")
_REQUEST_KEYS = {
    "schema",
    "request_id",
    "system_id",
    "sent_at",
    "projection_hash",
    "projection",
}
_PROJECTION_SCHEMA_PATH = Path(__file__).with_name("gh.c06-hourly-projection-1.schema.json")
_FORMAT_CHECKER = FormatChecker()


class ProtocolError(ValueError):
    """Raised when an inbound C06-B2 request is not safe to process."""


def _load_projection_schema() -> dict[str, Any]:
    try:
        document = json.loads(_PROJECTION_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("unable to load the frozen hourly projection schema") from exc
    if not isinstance(document, dict):
        raise TypeError("hourly projection schema root must be an object")
    Draft202012Validator.check_schema(document)
    return document


_PROJECTION_VALIDATOR = Draft202012Validator(
    _load_projection_schema(),
    format_checker=_FORMAT_CHECKER,
)


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def projection_hash(projection: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(projection).encode("utf-8")).hexdigest()


def _duplicate_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _finite_float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ProtocolError("non-finite JSON number")
    return value


def _invalid_constant(raw: str) -> None:
    raise ProtocolError(f"invalid JSON constant: {raw}")


def strict_json_object(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    try:
        if isinstance(payload, dict):
            encoded = canonical_json(payload)
        elif isinstance(payload, bytes):
            encoded = payload.decode("utf-8")
        elif isinstance(payload, str):
            encoded = payload
        else:
            raise ProtocolError("request payload must be bytes, text, or an object")
    except UnicodeDecodeError as exc:
        raise ProtocolError("request must contain UTF-8 JSON") from exc
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ProtocolError):
            raise
        raise ProtocolError(f"request cannot be encoded as strict JSON: {exc}") from exc

    try:
        document = json.loads(
            encoded,
            object_pairs_hook=_duplicate_guard,
            parse_float=_finite_float,
            parse_constant=_invalid_constant,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, ProtocolError):
            raise
        raise ProtocolError(f"invalid JSON request: {exc}") from exc
    if not isinstance(document, dict):
        raise ProtocolError("request root must be an object")
    return document


def validate_utc_timestamp(
    value: Any,
    field: str,
    *,
    hour_aligned: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ProtocolError(f"{field} must be a timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProtocolError(f"{field} must be RFC 3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ProtocolError(f"{field} must use UTC")
    if hour_aligned and (parsed.minute or parsed.second or parsed.microsecond):
        raise ProtocolError(f"{field} must be UTC hour aligned")
    return value


def validate_projection(projection: Any) -> dict[str, Any]:
    if not isinstance(projection, dict):
        raise ProtocolError("projection must be an object")
    try:
        _PROJECTION_VALIDATOR.validate(projection)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        suffix = f" at {location}" if location else ""
        raise ProtocolError(f"invalid hourly projection{suffix}: {exc.message}") from exc

    node_id = str(projection["node_id"])
    sample_hour = validate_utc_timestamp(
        projection["sample_hour"],
        "projection.sample_hour",
        hour_aligned=True,
    )
    projection_version = int(projection["projection_version"])
    expected_key = f"{node_id}|{sample_hour}|v{projection_version}"
    if projection["idempotency_key"] != expected_key:
        raise ProtocolError("projection.idempotency_key does not match its identity")

    seen: set[str] = set()
    for index, item in enumerate(projection["series"]):
        key = str(item["measurement_key"])
        if key in seen:
            raise ProtocolError(f"projection.series[{index}].measurement_key is duplicated")
        seen.add(key)
        if item["entity_unique_id"] != f"{node_id}_{key}":
            raise ProtocolError("series entity_unique_id does not match node and measurement")
        minimum = float(item["min"])
        mean = float(item["mean"])
        maximum = float(item["max"])
        if not all(math.isfinite(value) for value in (minimum, mean, maximum)):
            raise ProtocolError("series statistics must be finite")
        if not minimum <= mean <= maximum:
            raise ProtocolError("series min/mean/max ordering is invalid")
    return projection


@dataclass(frozen=True, slots=True)
class ProjectionRequest:
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


def parse_request(
    payload: bytes | str | dict[str, Any],
    *,
    configured_system_id: str,
) -> ProjectionRequest:
    validate_system_id(configured_system_id)
    document = strict_json_object(payload)
    if set(document) != _REQUEST_KEYS or document.get("schema") != REQUEST_SCHEMA:
        raise ProtocolError("request has an invalid top-level shape or schema")
    request_id = document["request_id"]
    if not isinstance(request_id, str) or not _REQUEST_ID_RE.fullmatch(request_id):
        raise ProtocolError("request_id is invalid")
    system_id = document["system_id"]
    if system_id != configured_system_id:
        raise ProtocolError("request system_id does not match this integration entry")
    validate_utc_timestamp(document["sent_at"], "sent_at")
    declared_hash = document["projection_hash"]
    if not isinstance(declared_hash, str) or not _HASH_RE.fullmatch(declared_hash):
        raise ProtocolError("projection_hash is invalid")
    projection = validate_projection(document["projection"])
    if projection_hash(projection) != declared_hash:
        raise ProtocolError("projection_hash does not match canonical projection payload")
    return ProjectionRequest(
        request_id=request_id,
        system_id=system_id,
        sent_at=document["sent_at"],
        projection_hash=declared_hash,
        projection=projection,
    )


def result_document(
    *,
    request: ProjectionRequest,
    status: ResultStatus,
    monotonic_revision_enforced: bool,
    verified_at: str | None,
    code: str | None,
    detail: str | None,
) -> dict[str, Any]:
    if status not in {"verified", "retry", "blocked"}:
        raise ProtocolError("result status is invalid")
    if status == "verified":
        if not monotonic_revision_enforced:
            raise ProtocolError("verified result requires monotonic enforcement")
        validate_utc_timestamp(verified_at, "verified_at")
        if code is not None:
            raise ProtocolError("verified result cannot include an error code")
    else:
        if verified_at is not None:
            raise ProtocolError("non-verified result cannot include verified_at")
        if not isinstance(code, str) or not _CODE_RE.fullmatch(code):
            raise ProtocolError("retry or blocked result requires a stable code")
    if detail is not None and (not isinstance(detail, str) or len(detail) > 512):
        raise ProtocolError("result detail is invalid")
    return {
        "schema": RESULT_SCHEMA,
        "request_id": request.request_id,
        "status": status,
        "idempotency_key": request.idempotency_key,
        "revision": request.revision,
        "projection_hash": request.projection_hash,
        "monotonic_revision_enforced": monotonic_revision_enforced,
        "verified_at": verified_at,
        "code": code,
        "detail": detail,
    }
