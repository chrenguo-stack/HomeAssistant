from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from .const import PROJECTION_SCHEMA, REQUEST_SCHEMA, RESULT_SCHEMA, validate_system_id

ResultStatus = Literal["verified", "retry", "blocked"]

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z0-9_]{1,96}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_REQUEST_KEYS = {
    "schema",
    "request_id",
    "system_id",
    "sent_at",
    "projection_hash",
    "projection",
}
_PROJECTION_KEYS = {
    "schema",
    "idempotency_key",
    "node_id",
    "sample_hour",
    "projection_version",
    "revision",
    "algorithm_version",
    "quality_policy",
    "source_record_count",
    "source_set_sha256",
    "eligible_record_count",
    "skipped_time_quality",
    "series",
    "audit",
}
_SERIES_KEYS = {
    "measurement_key",
    "entity_unique_id",
    "name",
    "unit_of_measurement",
    "device_class",
    "unit_class_hint",
    "state_class",
    "mean_type",
    "has_sum",
    "samples",
    "mean",
    "min",
    "max",
}


class ProtocolError(ValueError):
    """Raised when an inbound C06-B2 request is not safe to process."""


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
    if isinstance(payload, dict):
        encoded = canonical_json(payload)
    elif isinstance(payload, bytes):
        try:
            encoded = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("request must contain UTF-8 JSON") from exc
    elif isinstance(payload, str):
        encoded = payload
    else:
        raise ProtocolError("request payload must be bytes, text, or an object")
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


def _utc_timestamp(value: Any, field: str, *, hour_aligned: bool = False) -> str:
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


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProtocolError(f"{field} must be an integer in {minimum}..{maximum}")
    return value


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProtocolError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolError(f"{field} must be finite")
    return result


def _validate_series(node_id: str, series: Any) -> None:
    if not isinstance(series, list) or len(series) > 13:
        raise ProtocolError("projection.series must contain at most 13 objects")
    seen: set[str] = set()
    for index, item in enumerate(series):
        if not isinstance(item, dict) or set(item) != _SERIES_KEYS:
            raise ProtocolError(f"projection.series[{index}] has an invalid shape")
        key = item["measurement_key"]
        if not isinstance(key, str) or not key or key in seen:
            raise ProtocolError(f"projection.series[{index}].measurement_key is invalid")
        seen.add(key)
        if item["entity_unique_id"] != f"{node_id}_{key}":
            raise ProtocolError("series entity_unique_id does not match node and measurement")
        for field in ("name", "unit_of_measurement"):
            if not isinstance(item[field], str) or not item[field]:
                raise ProtocolError(f"projection.series[{index}].{field} is invalid")
        for field in ("device_class", "unit_class_hint"):
            if item[field] is not None and not isinstance(item[field], str):
                raise ProtocolError(f"projection.series[{index}].{field} is invalid")
        if item["state_class"] != "measurement" or item["mean_type"] != "arithmetic":
            raise ProtocolError("series statistics semantics are not supported")
        if item["has_sum"] is not False:
            raise ProtocolError("series has_sum must be false")
        _integer(item["samples"], f"projection.series[{index}].samples", 1, 10_000)
        minimum = _finite_number(item["min"], f"projection.series[{index}].min")
        mean = _finite_number(item["mean"], f"projection.series[{index}].mean")
        maximum = _finite_number(item["max"], f"projection.series[{index}].max")
        if not minimum <= mean <= maximum:
            raise ProtocolError("series min/mean/max ordering is invalid")


def _validate_audit(audit: Any) -> None:
    if not isinstance(audit, dict) or len(audit) != 13:
        raise ProtocolError("projection.audit must contain the frozen 13 measurements")
    required = {"present", "accepted", "excluded_quality", "invalid_or_null", "missing"}
    for key, counters in audit.items():
        if not isinstance(key, str) or not isinstance(counters, dict) or set(counters) != required:
            raise ProtocolError("projection.audit entry has an invalid shape")
        for field, value in counters.items():
            _integer(value, f"projection.audit.{key}.{field}", 0, 10_000)


def validate_projection(projection: Any) -> dict[str, Any]:
    if not isinstance(projection, dict) or set(projection) != _PROJECTION_KEYS:
        raise ProtocolError("projection has an invalid top-level shape")
    if projection["schema"] != PROJECTION_SCHEMA:
        raise ProtocolError("unsupported projection schema")
    node_id = projection["node_id"]
    if not isinstance(node_id, str) or not _ID_RE.fullmatch(node_id):
        raise ProtocolError("projection.node_id is invalid")
    sample_hour = _utc_timestamp(
        projection["sample_hour"], "projection.sample_hour", hour_aligned=True
    )
    projection_version = _integer(
        projection["projection_version"], "projection.projection_version", 1, 2_147_483_647
    )
    revision = _integer(
        projection["revision"], "projection.revision", 1, 9_223_372_036_854_775_807
    )
    if revision < 1:
        raise ProtocolError("projection.revision is invalid")
    expected_key = f"{node_id}|{sample_hour}|v{projection_version}"
    if projection["idempotency_key"] != expected_key:
        raise ProtocolError("projection.idempotency_key does not match its identity")
    if projection["algorithm_version"] != 2:
        raise ProtocolError("unsupported projection algorithm_version")
    if projection["quality_policy"] != "ok-only/1":
        raise ProtocolError("unsupported projection quality_policy")
    source_count = _integer(
        projection["source_record_count"], "projection.source_record_count", 1, 10_000
    )
    eligible_count = _integer(
        projection["eligible_record_count"], "projection.eligible_record_count", 0, 10_000
    )
    skipped_count = _integer(
        projection["skipped_time_quality"], "projection.skipped_time_quality", 0, 10_000
    )
    if eligible_count + skipped_count != source_count:
        raise ProtocolError("projection source counters are inconsistent")
    source_hash = projection["source_set_sha256"]
    if not isinstance(source_hash, str) or not _HASH_RE.fullmatch(source_hash):
        raise ProtocolError("projection.source_set_sha256 is invalid")
    _validate_series(node_id, projection["series"])
    _validate_audit(projection["audit"])
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
    payload: bytes | str | dict[str, Any], *, configured_system_id: str
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
    _utc_timestamp(document["sent_at"], "sent_at")
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
    if status == "verified":
        if not monotonic_revision_enforced:
            raise ProtocolError("verified result requires monotonic enforcement")
        _utc_timestamp(verified_at, "verified_at")
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
