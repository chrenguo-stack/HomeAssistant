from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from greenhouse_manager.runtime.n3w_auto_node_id import (
    AutomaticNodeIdApprover,
    AutomaticNodeIdExhausted,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry, RegistrationState

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"


def valid_hello(*, pairing_id: str = PAIRING_ID, epoch: int = 3) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": epoch,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


class FixedRandom:
    def __init__(self, *values: bytes) -> None:
        self.values = list(values)

    def __call__(self, size: int) -> bytes:
        assert size == 16
        return self.values.pop(0)


def test_first_approval_allocates_node_id_without_operator_input(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        registry.observe_hello(valid_hello(), now=NOW)
        approved = AutomaticNodeIdApprover(
            registry,
            random_bytes=FixedRandom(b"\x01" * 16),
        ).approve(HARDWARE_ID, PAIRING_ID, now=NOW)

    assert approved.state is RegistrationState.APPROVED
    assert approved.node_id == "node_" + "01" * 16
    assert HARDWARE_ID not in approved.node_id


def test_repair_preserves_existing_node_id(tmp_path) -> None:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(database) as registry:
        registry.observe_hello(valid_hello(), now=NOW)
        approver = AutomaticNodeIdApprover(
            registry,
            random_bytes=FixedRandom(b"\x02" * 16),
        )
        first = approver.approve(HARDWARE_ID, PAIRING_ID, now=NOW)
        next_pairing = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
        registry.authorize_repair(
            HARDWARE_ID,
            next_pairing,
            now=NOW,
        )
        registry.observe_hello(
            valid_hello(pairing_id=next_pairing, epoch=4),
            now=NOW + timedelta(seconds=1),
        )
        second = approver.approve(
            HARDWARE_ID,
            next_pairing,
            now=NOW + timedelta(seconds=2),
        )

    assert second.node_id == first.node_id


def test_retired_or_existing_candidates_are_never_reused() -> None:
    first = "node_" + "01" * 16
    second = "node_" + "02" * 16

    class FakeRegistry:
        def get(self, hardware_id: str):
            assert hardware_id == HARDWARE_ID
            return SimpleNamespace(node_id=None)

        def node_id_lease_state(self, node_id: str):
            return "retired" if node_id == first else None

        def approve(self, hardware_id: str, pairing_id: str, **kwargs):
            assert hardware_id == HARDWARE_ID
            assert pairing_id == PAIRING_ID
            assert kwargs["node_id"] == second
            return SimpleNamespace(node_id=second)

    result = AutomaticNodeIdApprover(
        FakeRegistry(),  # type: ignore[arg-type]
        random_bytes=FixedRandom(b"\x01" * 16, b"\x02" * 16),
    ).approve(HARDWARE_ID, PAIRING_ID)
    assert result.node_id == second


def test_invalid_generator_or_collision_exhaustion_fails_closed() -> None:
    class ExhaustedRegistry:
        def get(self, _hardware_id: str):
            return SimpleNamespace(node_id=None)

        def node_id_lease_state(self, _node_id: str):
            return "retired"

    with pytest.raises(AutomaticNodeIdExhausted, match="allocation exhausted"):
        AutomaticNodeIdApprover(
            ExhaustedRegistry(),  # type: ignore[arg-type]
            random_bytes=FixedRandom(b"\x01" * 16),
            max_attempts=1,
        ).approve(HARDWARE_ID, PAIRING_ID)
