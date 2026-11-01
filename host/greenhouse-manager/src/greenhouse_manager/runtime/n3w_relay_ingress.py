from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


class RelayIngressRejected(ValueError):
    """Fail-closed N3-W relay ingress rejection with a stable diagnostic code."""

    def __init__(self, code: str, *, node_id: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.node_id = node_id


@dataclass(frozen=True, slots=True)
class RelayTopic:
    system_id: str
    gateway_id: str
    node_id: str


class PackagedTelemetryValidator:
    """Complete schema/Manager-owned-field validator shared by N3-W relay ingress."""

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        self.validator = Draft202012Validator(
            schema or self._load_packaged_schema(),
            format_checker=FormatChecker(),
        )

    @staticmethod
    def _load_packaged_schema() -> dict[str, Any]:
        schema_path = files("greenhouse_manager").joinpath("schemas/gh.telemetry-1.schema.json")
        with schema_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def validate(self, telemetry: dict[str, Any]) -> None:
        if "received_at" in telemetry:
            raise RelayIngressRejected("manager_owned_field_present")
        errors = sorted(
            self.validator.iter_errors(telemetry),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            raise RelayIngressRejected("telemetry_validation_rejected")


def parse_relay_topic(topic: str) -> RelayTopic:
    if not isinstance(topic, str):
        raise RelayIngressRejected("topic_invalid")
    parts = topic.split("/")
    if (
        len(parts) != 8
        or parts[:2] != ["gh", "v1"]
        or parts[3:5] != ["ingress", "gateway"]
        or parts[7] != "frame"
    ):
        raise RelayIngressRejected("topic_invalid")
    system_id, gateway_id, node_id = parts[2], parts[5], parts[6]
    if not all(_ID.fullmatch(value) for value in (system_id, gateway_id, node_id)):
        raise RelayIngressRejected("topic_identity_invalid")
    return RelayTopic(system_id=system_id, gateway_id=gateway_id, node_id=node_id)
