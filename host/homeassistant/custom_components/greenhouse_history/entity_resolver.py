from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class EntityResolutionError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class EntityDescriptor:
    entity_id: str
    domain: str
    platform: str
    unique_id: str
    disabled: bool = False
    unit_of_measurement: str | None = None
    state_class: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedEntity:
    measurement_key: str
    entity_unique_id: str
    entity_id: str
    unit_of_measurement: str
    state_class: str
    mean: float
    minimum: float
    maximum: float


class EntityResolver:
    """Resolve frozen MQTT unique IDs to current Home Assistant entity IDs."""

    def __init__(self, entities: Iterable[EntityDescriptor]) -> None:
        self._by_unique_id: dict[str, list[EntityDescriptor]] = {}
        for entity in entities:
            if entity.domain == "sensor" and entity.platform == "mqtt":
                self._by_unique_id.setdefault(entity.unique_id, []).append(entity)

    def resolve_projection(self, projection: dict[str, Any]) -> tuple[ResolvedEntity, ...]:
        series = projection.get("series")
        if not isinstance(series, list):
            raise EntityResolutionError("target_projection_invalid", "projection series is invalid")
        resolved: list[ResolvedEntity] = []
        seen_entity_ids: set[str] = set()
        for item in series:
            if not isinstance(item, dict):
                raise EntityResolutionError(
                    "target_projection_invalid", "projection series item is invalid"
                )
            unique_id = item.get("entity_unique_id")
            measurement_key = item.get("measurement_key")
            if not isinstance(unique_id, str) or not isinstance(measurement_key, str):
                raise EntityResolutionError(
                    "target_projection_invalid", "projection identity fields are invalid"
                )
            matches = self._by_unique_id.get(unique_id, [])
            if not matches:
                raise EntityResolutionError(
                    "target_entity_missing",
                    f"no MQTT sensor entity exists for unique_id {unique_id}",
                )
            if len(matches) != 1:
                raise EntityResolutionError(
                    "target_entity_ambiguous",
                    f"multiple MQTT sensor entities use unique_id {unique_id}",
                )
            entity = matches[0]
            if entity.disabled:
                raise EntityResolutionError(
                    "target_entity_disabled", f"target entity {entity.entity_id} is disabled"
                )
            expected_unit = item.get("unit_of_measurement")
            if entity.unit_of_measurement != expected_unit:
                raise EntityResolutionError(
                    "target_unit_mismatch",
                    f"target entity {entity.entity_id} unit does not match projection",
                )
            if entity.state_class != "measurement" or item.get("state_class") != "measurement":
                raise EntityResolutionError(
                    "target_state_class_mismatch",
                    f"target entity {entity.entity_id} is not a measurement statistic",
                )
            if entity.entity_id in seen_entity_ids:
                raise EntityResolutionError(
                    "target_entity_ambiguous",
                    f"multiple series resolve to target entity {entity.entity_id}",
                )
            seen_entity_ids.add(entity.entity_id)
            resolved.append(
                ResolvedEntity(
                    measurement_key=measurement_key,
                    entity_unique_id=unique_id,
                    entity_id=entity.entity_id,
                    unit_of_measurement=expected_unit,
                    state_class="measurement",
                    mean=float(item["mean"]),
                    minimum=float(item["min"]),
                    maximum=float(item["max"]),
                )
            )
        return tuple(resolved)
