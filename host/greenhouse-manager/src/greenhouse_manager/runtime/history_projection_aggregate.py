from __future__ import annotations

import hashlib
import json
import math
from functools import cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .history_projection_contract import (
    ALGORITHM_VERSION,
    MAX_PROJECTION_PAYLOAD_BYTES,
    MAX_SOURCE_RECORDS_PER_HOUR,
    MEASUREMENT_RULES,
    PROJECTION_SCHEMA,
    QUALITY_POLICY,
    MeasurementRule,
    ProjectionBatch,
    ProjectionContractError,
)
from .history_projection_store import ProjectionTask
from .history_store import _parse_timestamp, _timestamp


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _projection_hash(payload: dict[str, Any]) -> str:
    return _sha256_text(canonical_json(payload))


@cache
def _projection_validator() -> Draft202012Validator:
    schema_path = files("greenhouse_manager").joinpath("schemas/gh.c06-hourly-projection-1.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _hour(value: object) -> str:
    if not isinstance(value, str):
        raise ProjectionContractError("sampled_at must be a string")
    try:
        parsed = _parse_timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProjectionContractError(f"invalid sampled_at: {exc}") from exc
    return _timestamp(parsed.replace(minute=0, second=0, microsecond=0))


def _bounded_number(rule: MeasurementRule, value: object) -> float | None:
    if value is None or isinstance(value, bool) or (not isinstance(value, (int, float))):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ProjectionContractError(f"{rule.key} cannot be represented as a finite float") from exc
    if not math.isfinite(number):
        raise ProjectionContractError(f"{rule.key} must be finite")
    if not rule.minimum <= number <= rule.maximum:
        raise ProjectionContractError(f"{rule.key} is outside safety envelope [{rule.minimum}, {rule.maximum}]")
    return number


def _record_identity(record: dict[str, Any]) -> tuple[str, int, str]:
    boot_id = record.get("boot_id")
    seq = record.get("seq")
    if not isinstance(boot_id, str) or not boot_id:
        raise ProjectionContractError("stored record boot_id must be a non-empty string")
    if type(seq) is not int or seq < 0:
        raise ProjectionContractError("stored record seq must be a non-negative integer")
    try:
        record_json = canonical_json(record)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProjectionContractError(f"stored record is not canonical JSON: {exc}") from exc
    return (boot_id, seq, _sha256_text(record_json))


def _source_set_sha256(records: list[dict[str, Any]]) -> str:
    prepared = sorted((_record_identity(record) for record in records), key=lambda item: (item[0], item[1]))
    seen: set[tuple[str, int]] = set()
    identities: list[dict[str, Any]] = []
    for boot_id, seq, record_sha256 in prepared:
        identity = (boot_id, seq)
        if identity in seen:
            raise ProjectionContractError("duplicate source record identity in projection input")
        seen.add(identity)
        identities.append({"boot_id": boot_id, "seq": seq, "record_sha256": record_sha256})
    return _sha256_text(canonical_json(identities))


def _validate_payload(payload: dict[str, Any]) -> None:
    errors = sorted(_projection_validator().iter_errors(payload), key=lambda error: tuple((str(part) for part in error.absolute_path)))
    if errors:
        first = errors[0]
        location = ".".join((str(part) for part in first.absolute_path)) or "<root>"
        raise ProjectionContractError(f"projection payload schema violation at {location}: {first.message}")
    encoded = canonical_json(payload).encode("utf-8")
    if len(encoded) > MAX_PROJECTION_PAYLOAD_BYTES:
        raise ProjectionContractError("projection payload exceeds the 1048576-byte limit")


def aggregate_projection(task: ProjectionTask, records: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> ProjectionBatch:
    if len(records) > MAX_SOURCE_RECORDS_PER_HOUR:
        raise ProjectionContractError(f"projection hour exceeds {MAX_SOURCE_RECORDS_PER_HOUR} source records")
    try:
        task_hour = _parse_timestamp(task.sample_hour)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProjectionContractError(f"invalid projection sample_hour: {exc}") from exc
    if task_hour.minute or task_hour.second or task_hour.microsecond:
        raise ProjectionContractError("projection sample_hour must be UTC hour aligned")
    normalized_hour = _timestamp(task_hour)
    if normalized_hour != task.sample_hour:
        raise ProjectionContractError("projection sample_hour must be normalized UTC")
    normalized_records = list(records)
    source_set_sha256 = _source_set_sha256(normalized_records)
    audit: dict[str, dict[str, int]] = {rule.key: {"present": 0, "accepted": 0, "excluded_quality": 0, "invalid_or_null": 0, "missing": 0} for rule in MEASUREMENT_RULES}
    values: dict[str, list[float]] = {rule.key: [] for rule in MEASUREMENT_RULES}
    eligible_records = 0
    skipped_time_quality = 0
    for record in normalized_records:
        time_quality = record.get("time_quality")
        if time_quality not in {"trusted", "estimated"}:
            skipped_time_quality += 1
            continue
        if _hour(record.get("sampled_at")) != task.sample_hour:
            raise ProjectionContractError("stored record sampled_at does not match the claimed sample_hour")
        measurements = record.get("measurements")
        quality = record.get("quality")
        if not isinstance(measurements, dict) or not isinstance(quality, dict):
            raise ProjectionContractError("stored record measurements and quality must be objects")
        eligible_records += 1
        for rule in MEASUREMENT_RULES:
            counters = audit[rule.key]
            if rule.key not in measurements:
                counters["missing"] += 1
                continue
            counters["present"] += 1
            if quality.get(rule.key) != "ok":
                counters["excluded_quality"] += 1
                continue
            number = _bounded_number(rule, measurements.get(rule.key))
            if number is None:
                counters["invalid_or_null"] += 1
                continue
            counters["accepted"] += 1
            values[rule.key].append(number)
    series: list[dict[str, Any]] = []
    for rule in MEASUREMENT_RULES:
        samples = values[rule.key]
        if not samples:
            continue
        try:
            total = math.fsum(samples)
            mean = total / len(samples)
        except (OverflowError, ValueError) as exc:
            raise ProjectionContractError(f"{rule.key} aggregation overflowed") from exc
        if not math.isfinite(mean):
            raise ProjectionContractError(f"{rule.key} aggregation produced a non-finite mean")
        series.append({"measurement_key": rule.key, "entity_unique_id": f"{task.node_id}_{rule.key}", "name": rule.name, "unit_of_measurement": rule.unit, "device_class": rule.device_class, "unit_class_hint": rule.unit_class_hint, "state_class": "measurement", "mean_type": "arithmetic", "has_sum": False, "samples": len(samples), "mean": mean, "min": min(samples), "max": max(samples)})
    idempotency_key = f"{task.node_id}|{task.sample_hour}|v{task.projection_version}"
    payload = {"schema": PROJECTION_SCHEMA, "idempotency_key": idempotency_key, "node_id": task.node_id, "sample_hour": task.sample_hour, "projection_version": task.projection_version, "revision": task.revision, "algorithm_version": ALGORITHM_VERSION, "quality_policy": QUALITY_POLICY, "source_record_count": len(normalized_records), "source_set_sha256": source_set_sha256, "eligible_record_count": eligible_records, "skipped_time_quality": skipped_time_quality, "series": series, "audit": audit}
    _validate_payload(payload)
    return ProjectionBatch(node_id=task.node_id, sample_hour=task.sample_hour, projection_version=task.projection_version, revision=task.revision, projection_hash=_projection_hash(payload), payload=payload)
