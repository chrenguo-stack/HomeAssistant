from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from .history_projection_store import ProjectionStore, ProjectionTask
from .history_store import _parse_timestamp, _timestamp

AdapterStatus = Literal["verified", "retry", "blocked"]
RunStatus = Literal["idle", "completed", "retry", "blocked", "stale"]


class ProjectionContractError(RuntimeError):
    """Raised when durable source data cannot form a valid projection."""


class ProjectionRetryableError(RuntimeError):
    """Raised by an adapter when the same revision should be retried."""


class ProjectionBlockedError(RuntimeError):
    """Raised by an adapter when operator or contract repair is required."""


@dataclass(frozen=True, slots=True)
class MeasurementRule:
    key: str
    name: str
    unit: str
    device_class: str | None
    unit_class_hint: str | None


MEASUREMENT_RULES: tuple[MeasurementRule, ...] = (
    MeasurementRule("air_temperature_c", "空气温度", "°C", "temperature", "temperature"),
    MeasurementRule("air_humidity_pct", "空气湿度", "%", "humidity", "unitless"),
    MeasurementRule("co2_ppm", "二氧化碳", "ppm", "carbon_dioxide", "unitless"),
    MeasurementRule("illuminance_lx", "光照度", "lx", "illuminance", None),
    MeasurementRule("soil_temperature_c", "土壤温度", "°C", "temperature", "temperature"),
    MeasurementRule("soil_moisture_pct", "土壤含水率", "%", "moisture", "unitless"),
    MeasurementRule("soil_ec_us_cm", "土壤电导率", "µS/cm", "conductivity", "conductivity"),
    MeasurementRule("vpd_kpa", "饱和水汽压差", "kPa", "pressure", "pressure"),
    MeasurementRule("dew_point_c", "露点温度", "°C", "temperature", "temperature"),
    MeasurementRule(
        "absolute_humidity_g_m3",
        "绝对湿度",
        "g/m³",
        "absolute_humidity",
        "concentration",
    ),
    MeasurementRule("ppfd_umol_m2_s", "光合光量子通量密度", "µmol/(m²·s)", None, None),
    MeasurementRule("battery_v", "电池电压", "V", "voltage", "voltage"),
    MeasurementRule("battery_pct", "电池电量", "%", "battery", "unitless"),
)

ALGORITHM_VERSION = 1
QUALITY_POLICY = "ok-only/1"
PROJECTION_SCHEMA = "gh.c06-hourly-projection/1"


@dataclass(frozen=True, slots=True)
class ProjectionBatch:
    node_id: str
    sample_hour: str
    projection_version: int
    revision: int
    projection_hash: str
    payload: dict[str, Any]

    @property
    def payload_json(self) -> str:
        return _canonical_json(self.payload)


@dataclass(frozen=True, slots=True)
class AdapterDispatchResult:
    status: AdapterStatus
    code: str | None = None
    detail: str | None = None
    verified_projection_hash: str | None = None


class ProjectionAdapter(Protocol):
    kind: str
    version: str

    def dispatch(self, batch: ProjectionBatch) -> AdapterDispatchResult:
        """Dispatch and, for success, verify the exact projection revision."""


@dataclass(slots=True)
class FakeProjectionAdapter:
    """Host-only adapter that performs no network or Home Assistant operation."""

    outcomes: list[AdapterDispatchResult] = field(default_factory=list)
    kind: str = "fake-host-only"
    version: str = "1"
    dispatched: list[ProjectionBatch] = field(default_factory=list, init=False)

    def dispatch(self, batch: ProjectionBatch) -> AdapterDispatchResult:
        self.dispatched.append(batch)
        if self.outcomes:
            result = self.outcomes.pop(0)
            if result.status == "verified" and result.verified_projection_hash is None:
                return AdapterDispatchResult(
                    status="verified",
                    code=result.code,
                    detail=result.detail,
                    verified_projection_hash=batch.projection_hash,
                )
            return result
        return AdapterDispatchResult(
            status="verified", verified_projection_hash=batch.projection_hash
        )


@dataclass(frozen=True, slots=True)
class ProjectionRunResult:
    status: RunStatus
    task: ProjectionTask | None = None
    projection_hash: str | None = None
    code: str | None = None
    detail: str | None = None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _projection_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _hour(value: object) -> str:
    if not isinstance(value, str):
        raise ProjectionContractError("sampled_at must be a string")
    parsed = _parse_timestamp(value)
    return _timestamp(parsed.replace(minute=0, second=0, microsecond=0))


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def aggregate_projection(
    task: ProjectionTask,
    records: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> ProjectionBatch:
    task_hour = _parse_timestamp(task.sample_hour)
    if task_hour.minute or task_hour.second or task_hour.microsecond:
        raise ProjectionContractError("projection sample_hour must be UTC hour aligned")
    normalized_hour = _timestamp(task_hour)
    if normalized_hour != task.sample_hour:
        raise ProjectionContractError("projection sample_hour must be normalized UTC")

    audit: dict[str, dict[str, int]] = {
        rule.key: {
            "present": 0,
            "accepted": 0,
            "excluded_quality": 0,
            "invalid_or_null": 0,
            "missing": 0,
        }
        for rule in MEASUREMENT_RULES
    }
    values: dict[str, list[float]] = {rule.key: [] for rule in MEASUREMENT_RULES}
    eligible_records = 0
    skipped_time_quality = 0

    for record in records:
        time_quality = record.get("time_quality")
        if time_quality not in {"trusted", "estimated"}:
            skipped_time_quality += 1
            continue
        if _hour(record.get("sampled_at")) != task.sample_hour:
            raise ProjectionContractError(
                "stored record sampled_at does not match the claimed sample_hour"
            )
        measurements = record.get("measurements")
        quality = record.get("quality")
        if not isinstance(measurements, dict) or not isinstance(quality, dict):
            raise ProjectionContractError(
                "stored record measurements and quality must be objects"
            )
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
            number = _finite_number(measurements.get(rule.key))
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
        series.append(
            {
                "measurement_key": rule.key,
                "entity_unique_id": f"{task.node_id}_{rule.key}",
                "name": rule.name,
                "unit_of_measurement": rule.unit,
                "device_class": rule.device_class,
                "unit_class_hint": rule.unit_class_hint,
                "state_class": "measurement",
                "mean_type": "arithmetic",
                "has_sum": False,
                "samples": len(samples),
                "mean": math.fsum(samples) / len(samples),
                "min": min(samples),
                "max": max(samples),
            }
        )

    payload = {
        "schema": PROJECTION_SCHEMA,
        "node_id": task.node_id,
        "sample_hour": task.sample_hour,
        "projection_version": task.projection_version,
        "revision": task.revision,
        "algorithm_version": ALGORITHM_VERSION,
        "quality_policy": QUALITY_POLICY,
        "source_record_count": len(records),
        "eligible_record_count": eligible_records,
        "skipped_time_quality": skipped_time_quality,
        "series": series,
        "audit": audit,
        "relative_only_reconstruction": False,
        "dli_counter_projection": False,
        "home_assistant_write_enabled": False,
        "direct_home_assistant_database_write": False,
    }
    return ProjectionBatch(
        node_id=task.node_id,
        sample_hour=task.sample_hour,
        projection_version=task.projection_version,
        revision=task.revision,
        projection_hash=_projection_hash(payload),
        payload=payload,
    )


class ProjectionRunner:
    """Claim, aggregate, dispatch, verify, and settle one C06-B1 job."""

    def __init__(
        self,
        *,
        store: ProjectionStore,
        adapter: ProjectionAdapter,
        worker_id: str,
        lease_seconds: int = 60,
        retry_base_seconds: int = 10,
        retry_max_seconds: int = 3600,
    ) -> None:
        if not 1 <= retry_base_seconds <= retry_max_seconds <= 86_400:
            raise ValueError("retry delays must satisfy 1 <= base <= max <= 86400")
        self.store = store
        self.adapter = adapter
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds

    def _retry_at(self, task: ProjectionTask, now: datetime) -> datetime:
        exponent = min(max(task.attempts - 1, 0), 30)
        delay = min(self.retry_base_seconds * (2**exponent), self.retry_max_seconds)
        return now + timedelta(seconds=delay)

    def _retry(
        self,
        task: ProjectionTask,
        *,
        code: str,
        detail: str,
        now: datetime,
        projection_hash: str | None = None,
    ) -> ProjectionRunResult:
        settled = self.store.mark_retry(
            task,
            error_code=code,
            error=detail,
            next_attempt_at=self._retry_at(task, now),
            now=now,
        )
        return ProjectionRunResult(
            status="retry" if settled else "stale",
            task=task,
            projection_hash=projection_hash,
            code=code,
            detail=detail,
        )

    def _blocked(
        self,
        task: ProjectionTask,
        *,
        code: str,
        detail: str,
        now: datetime,
        projection_hash: str | None = None,
    ) -> ProjectionRunResult:
        settled = self.store.mark_blocked(
            task, error_code=code, error=detail, now=now
        )
        return ProjectionRunResult(
            status="blocked" if settled else "stale",
            task=task,
            projection_hash=projection_hash,
            code=code,
            detail=detail,
        )

    def run_once(self, *, now: datetime | None = None) -> ProjectionRunResult:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        task = self.store.claim_next(
            worker_id=self.worker_id,
            now=current,
            lease_seconds=self.lease_seconds,
        )
        if task is None:
            return ProjectionRunResult(status="idle")

        try:
            batch = aggregate_projection(task, self.store.load_records(task))
        except ProjectionContractError as exc:
            return self._blocked(
                task,
                code="projection_contract_error",
                detail=str(exc),
                now=current,
            )
        except Exception as exc:  # noqa: BLE001 - host boundary must retain the job
            return self._retry(
                task,
                code="projection_build_failed",
                detail=f"{type(exc).__name__}: {exc}",
                now=current,
            )

        try:
            result = self.adapter.dispatch(batch)
        except ProjectionBlockedError as exc:
            return self._blocked(
                task,
                code="adapter_blocked",
                detail=str(exc),
                now=current,
                projection_hash=batch.projection_hash,
            )
        except ProjectionRetryableError as exc:
            return self._retry(
                task,
                code="adapter_retryable",
                detail=str(exc),
                now=current,
                projection_hash=batch.projection_hash,
            )
        except Exception as exc:  # noqa: BLE001 - adapter failures remain retryable
            return self._retry(
                task,
                code="adapter_dispatch_failed",
                detail=f"{type(exc).__name__}: {exc}",
                now=current,
                projection_hash=batch.projection_hash,
            )

        if result.status == "retry":
            return self._retry(
                task,
                code=result.code or "adapter_retry",
                detail=result.detail or "adapter requested retry",
                now=current,
                projection_hash=batch.projection_hash,
            )
        if result.status == "blocked":
            return self._blocked(
                task,
                code=result.code or "adapter_blocked",
                detail=result.detail or "adapter blocked the projection",
                now=current,
                projection_hash=batch.projection_hash,
            )
        if result.status != "verified":
            return self._retry(
                task,
                code="adapter_status_invalid",
                detail=f"unsupported adapter status: {result.status!r}",
                now=current,
                projection_hash=batch.projection_hash,
            )
        if result.verified_projection_hash != batch.projection_hash:
            return self._retry(
                task,
                code="adapter_hash_mismatch",
                detail="adapter did not verify the exact projection hash",
                now=current,
                projection_hash=batch.projection_hash,
            )

        completed = self.store.mark_completed(
            task,
            projection_hash=batch.projection_hash,
            payload_json=batch.payload_json,
            adapter_kind=self.adapter.kind,
            adapter_version=self.adapter.version,
            now=current,
        )
        return ProjectionRunResult(
            status="completed" if completed else "stale",
            task=task,
            projection_hash=batch.projection_hash,
        )
