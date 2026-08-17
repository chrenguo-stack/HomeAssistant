from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from http import HTTPStatus

from greenhouse_manager.runtime.n3w_simplified_pairing import SimplifiedPairingCoordinator
from greenhouse_manager.runtime.n3w_simplified_pairing_endpoint import (
    SimplifiedPairingEndpointApp,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class UnusedStager:
    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> None:
        raise AssertionError(
            "hello endpoint must not stage credentials "
            f"{hardware_id=} {pairing_id=} {node_id=} {credential_generation=}"
        )


def _hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-simple",
        "node_nonce": _b64(bytes([0x31]) * 32),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": 1,
    }


def test_http_hello_maps_registration_observe_result(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        app = SimplifiedPairingEndpointApp(
            SimplifiedPairingCoordinator(
                registry,
                UnusedStager(),
                manager_id="manager_lab_01",
            ),
            clock=lambda: NOW,
        )
        response = app.handle(
            method="POST",
            path="/v2/pairing/hello",
            headers={},
            body=json.dumps(_hello(), separators=(",", ":")).encode("utf-8"),
            client_ip="127.0.0.1",
        )

    assert response.status == HTTPStatus.OK
    assert json.loads(response.body.decode("utf-8")) == {
        "schema": "gh.pair.simple-hello-result/1",
        "status": "created",
        "hardware_id": HARDWARE_ID,
        "pairing_id": PAIRING_ID,
    }
