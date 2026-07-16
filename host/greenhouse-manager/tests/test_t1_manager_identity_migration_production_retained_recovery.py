from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_production_retained_recovery import (
    RetainedRecoveryRuntimeProbe,
    wrap_manager_runtime_probe,
)
from greenhouse_manager.t1_manager_identity_migration_production_runtime_probe import (
    ManagerProductionRuntimeProbe,
    ManagerProductionRuntimeProbeError,
    ManagerRuntimeProbeFailureCode,
)

NODE_ID = "gh-n1-a9f2f8"
DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"
CANONICAL_TOPIC = f"gh/v1/greenhouse/state/{NODE_ID}/telemetry"
AVAILABILITY_TOPIC = f"gh/v1/greenhouse/state/{NODE_ID}/availability"
STARTED_AT = datetime(2026, 7, 15, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeReader:
    def __init__(self, availability_state: str = "online") -> None:
        self.availability_state = availability_state
        self.topics: list[str] = []

    def read(self, topic: str) -> bytes:
        self.topics.append(topic)
        if topic == CANONICAL_TOPIC:
            document = {"node_id": NODE_ID}
        elif topic == AVAILABILITY_TOPIC:
            document = {
                "schema": "gh.availability/1",
                "node_id": NODE_ID,
                "state": self.availability_state,
            }
        else:
            raise AssertionError(f"unexpected topic: {topic}")
        return json.dumps(document).encode()


class OuterProbe:
    def __init__(self, inner: ManagerProductionRuntimeProbe) -> None:
        self.inner = inner

    def capture_baseline(self) -> dict[str, object]:
        return {"baseline_captured": True}

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        del username, client_id

    def verify_ingress_subscription(self) -> None:
        pass

    def verify_canonical_publication(self) -> None:
        raise AssertionError("outer canonical method must be replaced")

    def verify_availability_publication(self) -> None:
        raise AssertionError("outer availability method must be replaced")

    def verify_discovery_publication(self) -> None:
        pass

    def verify_reconnect(self) -> None:
        pass

    def verify_existing_entities(self) -> None:
        pass

    def verify_legacy_anonymous_path(self) -> None:
        pass

    def postactivation_audit(self) -> dict[str, object]:
        return {"postactivation_verified": True}


def _probe(
    messages: Any,
    *,
    availability_state: str = "online",
    telemetry_timeout_s: float = 0.04,
) -> tuple[ManagerProductionRuntimeProbe, FakeReader, FakeClock]:
    clock = FakeClock()
    reader = FakeReader(availability_state)
    probe = object.__new__(ManagerProductionRuntimeProbe)
    probe.node_id = NODE_ID
    probe.discovery_topic = DISCOVERY_TOPIC
    probe.canonical_topic = CANONICAL_TOPIC
    probe.availability_topic = AVAILABILITY_TOPIC
    probe.timeout_s = 0.04
    probe.telemetry_timeout_s = telemetry_timeout_s
    probe.poll_interval_s = 0.01
    probe.monotonic = clock.monotonic
    probe.sleeper = clock.sleep
    probe.reader_factory = lambda: reader
    probe._checks = {}
    probe._inspect = lambda: {}
    probe._validate_identity_binding = lambda _document: (
        123,
        STARTED_AT,
        Path("/tmp/fake-manager.log"),
    )
    probe._log_messages = lambda *_args: tuple(messages(clock.now))
    return probe, reader, clock


def test_retained_recovery_online_availability_is_accepted() -> None:
    recovery = (
        f"Published Home Assistant discovery node={NODE_ID} topic={DISCOVERY_TOPIC}"
    )
    base, reader, clock = _probe(lambda _now: (recovery,))
    wrapped = wrap_manager_runtime_probe(OuterProbe(base))

    assert isinstance(wrapped, RetainedRecoveryRuntimeProbe)
    wrapped.verify_canonical_publication()
    wrapped.verify_availability_publication()

    assert reader.topics == [CANONICAL_TOPIC, AVAILABILITY_TOPIC]
    assert base._checks["canonical_publication_verified"] is True
    assert base._checks["availability_publication_verified"] is True
    assert clock.now == 0.0


def test_retained_recovery_waits_for_exact_unavailable_publication() -> None:
    recovery = (
        f"Published Home Assistant discovery node={NODE_ID} topic={DISCOVERY_TOPIC}"
    )
    unavailable = f"Published unavailable state topic={AVAILABILITY_TOPIC}"
    base, reader, clock = _probe(
        lambda now: (recovery, unavailable) if now >= 0.02 else (recovery,),
        availability_state="unavailable",
    )
    wrapped = wrap_manager_runtime_probe(base)

    wrapped.verify_canonical_publication()
    wrapped.verify_availability_publication()

    assert reader.topics == [
        CANONICAL_TOPIC,
        AVAILABILITY_TOPIC,
        AVAILABILITY_TOPIC,
    ]
    assert base._checks["availability_publication_verified"] is True
    assert clock.now == pytest.approx(0.02)


def test_fresh_ingress_requires_online_availability() -> None:
    accepted = f"Accepted telemetry node={NODE_ID} key=('boot', 2)"
    base, reader, _clock = _probe(
        lambda _now: (accepted,),
        availability_state="unavailable",
    )
    wrapped = wrap_manager_runtime_probe(base)

    wrapped.verify_canonical_publication()
    with pytest.raises(
        ManagerProductionRuntimeProbeError,
        match="fresh ingress did not produce online availability",
    ):
        wrapped.verify_availability_publication()

    assert reader.topics == [CANONICAL_TOPIC, AVAILABILITY_TOPIC]


def test_unrelated_unavailable_log_does_not_satisfy_binding() -> None:
    recovery = (
        f"Published Home Assistant discovery node={NODE_ID} topic={DISCOVERY_TOPIC}"
    )
    unrelated = (
        "Published unavailable state topic="
        "gh/v1/greenhouse/state/gh-n1-other/availability"
    )
    base, reader, clock = _probe(
        lambda _now: (recovery, unrelated),
        availability_state="unavailable",
    )
    wrapped = wrap_manager_runtime_probe(base)

    wrapped.verify_canonical_publication()
    with pytest.raises(ManagerProductionRuntimeProbeError):
        wrapped.verify_availability_publication()

    assert reader.topics == [CANONICAL_TOPIC, AVAILABILITY_TOPIC]
    assert clock.now == pytest.approx(0.04)


def test_fresh_ingress_log_remains_valid_fallback() -> None:
    accepted = f"Accepted telemetry node={NODE_ID} key=('boot', 2)"
    base, reader, clock = _probe(
        lambda now: (accepted,) if now >= 0.03 else (),
    )
    wrapped = wrap_manager_runtime_probe(base)

    wrapped.verify_canonical_publication()
    wrapped.verify_availability_publication()

    assert reader.topics == [CANONICAL_TOPIC, AVAILABILITY_TOPIC]
    assert base._checks["canonical_publication_verified"] is True
    assert base._checks["availability_publication_verified"] is True
    assert clock.now == pytest.approx(0.03)


def test_unrelated_discovery_log_does_not_satisfy_binding() -> None:
    unrelated = (
        "Published Home Assistant discovery node=gh-n1-other "
        "topic=homeassistant/device/gh-n1-other/config"
    )
    base, reader, clock = _probe(lambda _now: (unrelated,))
    wrapped = wrap_manager_runtime_probe(base)

    with pytest.raises(ManagerProductionRuntimeProbeError) as raised:
        wrapped.verify_canonical_publication()

    assert raised.value.failure_code == (
        ManagerRuntimeProbeFailureCode.PASSIVE_TELEMETRY_TIMED_OUT
    ).value
    assert reader.topics == []
    assert clock.now == pytest.approx(0.04)


def test_probe_without_bound_production_base_is_left_unchanged() -> None:
    class UnboundProbe:
        pass

    probe = UnboundProbe()
    assert wrap_manager_runtime_probe(probe) is probe
