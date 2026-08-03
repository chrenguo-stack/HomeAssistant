from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .entity_resolver import ResolvedEntity


class RecorderAdapterError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class StatisticWrite:
    statistic_id: str
    start: str
    unit_of_measurement: str
    mean: float
    minimum: float
    maximum: float
    mean_type: str = "arithmetic"
    has_sum: bool = False


@dataclass(frozen=True, slots=True)
class StatisticReadback:
    statistic_id: str
    start: str
    unit_of_measurement: str
    mean: float
    minimum: float
    maximum: float


class RecorderAdapter(Protocol):
    async def async_import_statistics(self, statistics: tuple[StatisticWrite, ...]) -> None:
        """Queue or import statistics through supported Home Assistant Recorder APIs."""

    async def async_read_statistics(
        self, statistic_ids: tuple[str, ...], *, start: str
    ) -> tuple[StatisticReadback, ...]:
        """Read the target hour through supported Home Assistant Recorder APIs."""


def projection_writes(
    *, sample_hour: str, resolved: tuple[ResolvedEntity, ...]
) -> tuple[StatisticWrite, ...]:
    return tuple(
        StatisticWrite(
            statistic_id=item.entity_id,
            start=sample_hour,
            unit_of_measurement=item.unit_of_measurement,
            mean=item.mean,
            minimum=item.minimum,
            maximum=item.maximum,
        )
        for item in resolved
    )


def verify_readback(
    writes: tuple[StatisticWrite, ...], readback: tuple[StatisticReadback, ...]
) -> None:
    expected = {(item.statistic_id, item.start): item for item in writes}
    actual = {(item.statistic_id, item.start): item for item in readback}
    if set(actual) != set(expected):
        raise RecorderAdapterError(
            "target_readback_incomplete", "Recorder readback keys do not match the projection"
        )
    for key, write in expected.items():
        observed = actual[key]
        if observed.unit_of_measurement != write.unit_of_measurement:
            raise RecorderAdapterError(
                "target_unit_mismatch", f"Recorder unit mismatch for {write.statistic_id}"
            )
        if (
            observed.mean != write.mean
            or observed.minimum != write.minimum
            or observed.maximum != write.maximum
        ):
            raise RecorderAdapterError(
                "target_readback_mismatch",
                f"Recorder values do not match the projection for {write.statistic_id}",
            )
