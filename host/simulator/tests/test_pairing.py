from __future__ import annotations

import uuid

import pytest

from greenhouse_simulator.pairing import build_pairing_hello


def test_builds_deterministic_pairing_hello_for_manager_tests() -> None:
    pairing_id = uuid.UUID("c83aeb0d-8f48-4a39-a34b-ea584a588475")

    hello = build_pairing_hello(
        hardware_id="ghw-c6-98a316a9f2f8",
        pairing_epoch=3,
        sent_at_ms=120345,
        random_bytes=lambda size: bytes(range(size)),
        new_uuid=lambda: pairing_id,
    )

    assert hello["schema"] == "gh.pair.hello/1"
    assert hello["pairing_id"] == str(pairing_id)
    assert hello["pairing_epoch"] == 3
    assert hello["node_nonce"] == "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
    assert "pairing_pop" not in hello


@pytest.mark.parametrize("epoch", [0, -1])
def test_rejects_invalid_pairing_epoch(epoch: int) -> None:
    with pytest.raises(ValueError, match="pairing_epoch"):
        build_pairing_hello(
            hardware_id="ghw-c6-98a316a9f2f8",
            pairing_epoch=epoch,
        )
