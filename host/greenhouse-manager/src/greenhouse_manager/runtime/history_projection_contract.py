from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from .history_projection_store import ProjectionTask

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
    minimum: float
    maximum: float


# Safety envelopes, not agronomic plausibility thresholds.
MEASUREMENT_RULES: tuple[MeasurementRule, ...] = (
    MeasurementRule(
        "air_temperature_c",
        "空气温度",
        "°C",
        "temperature",
        "temperature",
        -1_000.0,
        1_000.0,
    ),
    MeasurementRule(
        "air_humidity_pct", "空气湿度", "%", "humidity", "unitless", 0.0, 100.0
    ),
    MeasurementRule(
        "co2_ppm",
        "二氧化碳",
        "ppm",
        "carbon_dioxide",
        "unitless",
        0.0,
        10_000_000.0,
    ),
    MeasurementRule(
        "illuminance_lx",
        "光照度",
        "lx",
        "illuminance",
        None,
        0.0,
        1_000_000_000_000.0,
    ),
    MeasurementRule(
        "soil_temperature_c",
        "土壤温度",
        "°C",
        "temperature",
        "temperature",
        -1_000.0,
        1_000.0,
    ),
    MeasurementRule(
        "soil_moisture_pct", "土壤含水率", "%", "moisture", "unitless", 0.0, 100.0
    ),
    MeasurementRule(
        "soil_ec_us_cm",
        "土壤电导率",
        "µS/cm",
        "conductivity",
        "conductivity",
        0.0,
        1_000_000_000_000.0,
    ),
    MeasurementRule(
        "vpd_kpa",
        "饱和水汽压差",
        "kPa",
        "pressure",
        "pressure",
        0.0,
        1_000_000.0,
    ),
    MeasurementRule(
        "dew_point_c",
        "露点温度",
        "°C",
        "temperature",
        "temperature",
        -1_000.0,
        1_000.0,
    ),
    MeasurementRule(
        "absolute_humidity_g_m3",
        "绝对湿度",
        "g/m³",
        "absolute_humidity",
        "concentration",
        0.0,
        1_000_000_000.0,
    ),
    MeasurementRule(
        "ppfd_umol_m2_s",
        "光合光量子通量密度",
        "µmol/(m²·s)",
        None,
        None,
        0.0,
        1_000_000_000.0,
    ),
    MeasurementRule(
        "battery_v", "电池电压", "V", "voltage", "voltage", 0.0, 1_000_000.0
    ),
    MeasurementRule(
        "battery_pct", "电池电量", "%", "battery", "unitless", 0.0, 100.0
    ),
)

ALGORITHM_VERSION = 2
QUALITY_POLICY = "ok-only/1"
PROJECTION_SCHEMA = "gh.c06-hourly-projection/1"
MAX_SOURCE_RECORDS_PER_HOUR = 10_000
MAX_PROJECTION_PAYLOAD_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class ProjectionBatch:
    node_id: str
    sample_hour: str
    projection_version: int
    revision: int
    projection_hash: str
    payload: dict[str, object]

    @property
    def payload_json(self) -> str:
        from .history_projection_aggregate import canonical_json

        return canonical_json(self.payload)

    @property
    def idempotency_key(self) -> str:
        return str(self.payload["idempotency_key"])


@dataclass(frozen=True, slots=True)
class AdapterDispatchResult:
    status: AdapterStatus
    code: str | None = None
    detail: str | None = None
    verified_projection_hash: str | None = None
    verified_revision: int | None = None
    verified_idempotency_key: str | None = None
    monotonic_revision_enforced: bool | None = None


class ProjectionAdapter(Protocol):
    kind: str
    version: str

    def dispatch(self, batch: ProjectionBatch) -> AdapterDispatchResult:
        """Dispatch and verify the exact monotonic projection revision."""


@dataclass(slots=True)
class FakeProjectionAdapter:
    """Host-only adapter with no network or Home Assistant operation."""

    outcomes: list[AdapterDispatchResult] = field(default_factory=list)
    kind: str = "fake-host-only"
    version: str = "2"
    dispatched: list[ProjectionBatch] = field(default_factory=list, init=False)

    def dispatch(self, batch: ProjectionBatch) -> AdapterDispatchResult:
        self.dispatched.append(batch)
        result = (
            self.outcomes.pop(0)
            if self.outcomes
            else AdapterDispatchResult(status="verified")
        )
        if result.status != "verified":
            return result
        return AdapterDispatchResult(
            status="verified",
            code=result.code,
            detail=result.detail,
            verified_projection_hash=(
                result.verified_projection_hash or batch.projection_hash
            ),
            verified_revision=(
                result.verified_revision
                if result.verified_revision is not None
                else batch.revision
            ),
            verified_idempotency_key=(
                result.verified_idempotency_key or batch.idempotency_key
            ),
            monotonic_revision_enforced=(
                True
                if result.monotonic_revision_enforced is None
                else result.monotonic_revision_enforced
            ),
        )


@dataclass(frozen=True, slots=True)
class ProjectionRunResult:
    status: RunStatus
    task: ProjectionTask | None = None
    projection_hash: str | None = None
    code: str | None = None
    detail: str | None = None
