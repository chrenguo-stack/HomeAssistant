from __future__ import annotations

import re
from dataclasses import dataclass

_ID = r"[A-Za-z0-9_-]{3,64}"
_NODE_TELEMETRY_RE = re.compile(
    rf"^gh/v1/(?P<system_id>{_ID})/ingress/node/(?P<node_id>{_ID})/telemetry$"
)
_CANONICAL_TELEMETRY_RE = re.compile(
    rf"^gh/v1/(?P<system_id>{_ID})/state/(?P<node_id>{_ID})/telemetry$"
)


@dataclass(frozen=True, slots=True)
class NodeTelemetryTopic:
    system_id: str
    node_id: str


def parse_node_telemetry_topic(topic: str) -> NodeTelemetryTopic:
    match = _NODE_TELEMETRY_RE.fullmatch(topic)
    if match is None:
        raise ValueError(f"Unsupported telemetry topic: {topic}")
    return NodeTelemetryTopic(
        system_id=match.group("system_id"),
        node_id=match.group("node_id"),
    )


def parse_canonical_telemetry_topic(topic: str) -> NodeTelemetryTopic:
    match = _CANONICAL_TELEMETRY_RE.fullmatch(topic)
    if match is None:
        raise ValueError(f"Unsupported canonical telemetry topic: {topic}")
    return NodeTelemetryTopic(
        system_id=match.group("system_id"),
        node_id=match.group("node_id"),
    )


def ingress_subscription(system_id: str) -> str:
    return f"gh/v1/{system_id}/ingress/node/+/telemetry"


def canonical_telemetry_subscription(system_id: str) -> str:
    return f"gh/v1/{system_id}/state/+/telemetry"


def canonical_telemetry_topic(system_id: str, node_id: str) -> str:
    return f"gh/v1/{system_id}/state/{node_id}/telemetry"


def availability_topic(system_id: str, node_id: str) -> str:
    return f"gh/v1/{system_id}/state/{node_id}/availability"


def diagnostic_topic(system_id: str, node_id: str) -> str:
    return f"gh/v1/{system_id}/state/{node_id}/diagnostic"
