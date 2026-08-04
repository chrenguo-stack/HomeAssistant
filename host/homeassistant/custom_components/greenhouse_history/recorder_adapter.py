from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

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
    unit_class: str | None
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
    async def async_import_statistics(
        self,
        statistics: tuple[StatisticWrite, ...],
    ) -> None:
        """Queue statistics through the supported Recorder API."""

    async def async_read_statistics(
        self,
        statistic_ids: tuple[str, ...],
        *,
        start: str,
    ) -> tuple[StatisticReadback, ...]:
        """Read one target hour through the supported Recorder query API."""


def _utc_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecorderAdapterError(
            "target_timestamp_invalid",
            f"{field} is not an RFC 3339 timestamp",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise RecorderAdapterError(
            "target_timestamp_invalid",
            f"{field} must use UTC",
        )
    return parsed.astimezone(UTC)


def _recorder_utc_datetime(value: Any) -> datetime:
    if isinstance(value, bool):
        raise RecorderAdapterError(
            "target_readback_invalid",
            "Recorder returned an invalid start timestamp",
        )
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise RecorderAdapterError(
                "target_readback_invalid",
                "Recorder returned a naive timestamp",
            )
        return value.astimezone(UTC)
    raise RecorderAdapterError(
        "target_readback_invalid",
        "Recorder returned an unsupported start timestamp",
    )


class HomeAssistantRecorderAdapter:
    """Supported Recorder API adapter; it never opens or writes the HA database."""

    def __init__(
        self,
        hass: Any,
        *,
        readback_timeout_seconds: float = 10.0,
        readback_poll_seconds: float = 0.25,
    ) -> None:
        if readback_timeout_seconds <= 0 or readback_poll_seconds <= 0:
            raise ValueError("Recorder readback timing must be positive")
        self.hass = hass
        self.readback_timeout_seconds = readback_timeout_seconds
        self.readback_poll_seconds = readback_poll_seconds
        self._expected_statistics: tuple[StatisticWrite, ...] | None = None

    async def async_import_statistics(
        self,
        statistics: tuple[StatisticWrite, ...],
    ) -> None:
        try:
            from homeassistant.components.recorder.const import (
                DOMAIN as RECORDER_DOMAIN,
            )
            from homeassistant.components.recorder.models import StatisticMeanType
            from homeassistant.components.recorder.statistics import (
                async_import_statistics,
            )
        except ImportError as exc:
            raise RecorderAdapterError(
                "recorder_api_unavailable",
                "Home Assistant Recorder API is unavailable",
            ) from exc

        for item in statistics:
            if ":" in item.statistic_id or "." not in item.statistic_id:
                raise RecorderAdapterError(
                    "target_statistic_id_invalid",
                    "projection must target an existing Home Assistant entity statistic",
                )
            if item.mean_type != "arithmetic" or item.has_sum:
                raise RecorderAdapterError(
                    "target_statistic_shape_invalid",
                    "hourly projection requires arithmetic mean and has_sum=false",
                )
            metadata = {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "name": None,
                "source": RECORDER_DOMAIN,
                "statistic_id": item.statistic_id,
                "unit_class": item.unit_class,
                "unit_of_measurement": item.unit_of_measurement,
            }
            statistic = {
                "start": _utc_datetime(item.start, "statistics.start"),
                "mean": item.mean,
                "min": item.minimum,
                "max": item.maximum,
            }
            try:
                async_import_statistics(self.hass, metadata, (statistic,))
            except Exception as exc:
                raise RecorderAdapterError(
                    "recorder_import_failed",
                    (
                        f"Recorder import failed for {item.statistic_id}: "
                        f"{type(exc).__name__}"
                    ),
                ) from exc
        self._expected_statistics = tuple(statistics)

    async def _async_query_statistics(
        self,
        statistic_ids: tuple[str, ...],
        *,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, list[dict[str, Any]]]:
        try:
            from homeassistant.components.recorder.statistics import (
                statistics_during_period,
            )
            from homeassistant.components.recorder.util import get_instance
        except ImportError as exc:
            raise RecorderAdapterError(
                "recorder_api_unavailable",
                "Home Assistant Recorder API is unavailable",
            ) from exc

        try:
            return await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_time,
                end_time,
                set(statistic_ids),
                "hour",
                None,
                {"mean", "min", "max"},
            )
        except Exception as exc:
            raise RecorderAdapterError(
                "recorder_read_failed",
                f"Recorder statistics query failed: {type(exc).__name__}",
            ) from exc

    def _readback_from_rows(
        self,
        statistic_ids: tuple[str, ...],
        *,
        start: str,
        rows_by_id: dict[str, list[dict[str, Any]]],
    ) -> tuple[StatisticReadback, ...]:
        target_start = _utc_datetime(start, "statistics.start")
        readback: list[StatisticReadback] = []
        for statistic_id in statistic_ids:
            rows = rows_by_id.get(statistic_id, ())
            exact = [
                row
                for row in rows
                if _recorder_utc_datetime(row.get("start")) == target_start
            ]
            if len(exact) != 1:
                continue
            row = exact[0]
            state = self.hass.states.get(statistic_id)
            unit = None if state is None else state.attributes.get("unit_of_measurement")
            if not isinstance(unit, str) or not unit:
                raise RecorderAdapterError(
                    "target_unit_missing",
                    f"target entity {statistic_id} has no unit of measurement",
                )
            values = (row.get("mean"), row.get("min"), row.get("max"))
            if any(
                isinstance(value, bool) or not isinstance(value, int | float)
                for value in values
            ):
                raise RecorderAdapterError(
                    "target_readback_invalid",
                    f"Recorder returned incomplete values for {statistic_id}",
                )
            mean, minimum, maximum = (float(value) for value in values)
            readback.append(
                StatisticReadback(
                    statistic_id=statistic_id,
                    start=start,
                    unit_of_measurement=unit,
                    mean=mean,
                    minimum=minimum,
                    maximum=maximum,
                )
            )
        return tuple(readback)

    async def async_read_statistics(
        self,
        statistic_ids: tuple[str, ...],
        *,
        start: str,
    ) -> tuple[StatisticReadback, ...]:
        start_time = _utc_datetime(start, "statistics.start")
        expected = self._expected_statistics
        if expected is None:
            raise RecorderAdapterError(
                "target_readback_expected_missing",
                "Recorder readback has no bound expected projection",
            )
        if (
            tuple(item.statistic_id for item in expected) != statistic_ids
            or any(
                _utc_datetime(item.start, "statistics.start") != start_time
                for item in expected
            )
        ):
            raise RecorderAdapterError(
                "target_readback_expected_mismatch",
                "Recorder readback request does not match the imported projection",
            )

        end_time = start_time + timedelta(hours=1)
        deadline = time.monotonic() + self.readback_timeout_seconds
        saw_complete_stale_values = False
        while True:
            rows_by_id = await self._async_query_statistics(
                statistic_ids,
                start_time=start_time,
                end_time=end_time,
            )
            readback = self._readback_from_rows(
                statistic_ids,
                start=start,
                rows_by_id=rows_by_id,
            )
            try:
                verify_readback(expected, readback)
            except RecorderAdapterError as exc:
                if exc.code == "target_readback_mismatch":
                    saw_complete_stale_values = True
                elif exc.code != "target_readback_incomplete":
                    raise
                if time.monotonic() >= deadline:
                    if saw_complete_stale_values:
                        raise RecorderAdapterError(
                            "target_readback_mismatch",
                            (
                                "Recorder values did not reach the expected projection "
                                "before timeout"
                            ),
                        ) from exc
                    raise RecorderAdapterError(
                        "target_readback_incomplete",
                        "Recorder readback keys did not become complete before timeout",
                    ) from exc
                await asyncio.sleep(self.readback_poll_seconds)
                continue
            return readback


def projection_writes(
    *,
    sample_hour: str,
    resolved: tuple[ResolvedEntity, ...],
) -> tuple[StatisticWrite, ...]:
    return tuple(
        StatisticWrite(
            statistic_id=item.entity_id,
            start=sample_hour,
            unit_of_measurement=item.unit_of_measurement,
            unit_class=item.unit_class_hint,
            mean=item.mean,
            minimum=item.minimum,
            maximum=item.maximum,
        )
        for item in resolved
    )


def verify_readback(
    writes: tuple[StatisticWrite, ...],
    readback: tuple[StatisticReadback, ...],
) -> None:
    expected = {(item.statistic_id, item.start): item for item in writes}
    actual = {(item.statistic_id, item.start): item for item in readback}
    if set(actual) != set(expected):
        raise RecorderAdapterError(
            "target_readback_incomplete",
            "Recorder readback keys do not match the projection",
        )
    for key, write in expected.items():
        observed = actual[key]
        if observed.unit_of_measurement != write.unit_of_measurement:
            raise RecorderAdapterError(
                "target_unit_mismatch",
                f"Recorder unit mismatch for {write.statistic_id}",
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
