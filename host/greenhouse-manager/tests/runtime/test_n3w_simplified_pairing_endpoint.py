from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
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


def test_health_schema_is_bound_to_simplified_endpoint(tmp_path) -> None:
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
            method="GET",
            path="/healthz",
            headers={},
            body=b"",
            client_ip="127.0.0.1",
        )

    assert response.status == HTTPStatus.OK
    assert json.loads(response.body.decode("utf-8")) == {
        "schema": "gh.pair.simple-health/1",
        "status": "ok",
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
        "transaction_disposition": "continue",
        "reason": None,
    }


def test_http_hello_marks_terminal_replay_for_pairing_id_renewal(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        registry.observe_hello(_hello(), now=NOW)
        registry.reject(
            HARDWARE_ID,
            PAIRING_ID,
            reason="user_rejected",
            now=NOW,
        )
        app = SimplifiedPairingEndpointApp(
            SimplifiedPairingCoordinator(
                registry,
                UnusedStager(),
                manager_id="manager_lab_01",
            ),
            clock=lambda: NOW + timedelta(seconds=1),
        )
        response = app.handle(
            method="POST",
            path="/v2/pairing/hello",
            headers={},
            body=json.dumps(_hello(), separators=(",", ":")).encode("utf-8"),
            client_ip="127.0.0.1",
        )

    assert response.status == HTTPStatus.OK
    document = json.loads(response.body.decode("utf-8"))
    assert document["status"] == "rejected"
    assert document["hardware_id"] == HARDWARE_ID
    assert document["pairing_id"] == PAIRING_ID
    assert document["transaction_disposition"] == "terminal"
    assert document["reason"] == "replay_detected"


def test_http_hello_marks_expired_transaction_terminal(tmp_path) -> None:
    with RegistrationRegistry(
        tmp_path / "registration.sqlite3",
        pending_ttl_s=1,
    ) as registry:
        registry.observe_hello(_hello(), now=NOW)
        app = SimplifiedPairingEndpointApp(
            SimplifiedPairingCoordinator(
                registry,
                UnusedStager(),
                manager_id="manager_lab_01",
            ),
            clock=lambda: NOW + timedelta(seconds=2),
        )
        response = app.handle(
            method="POST",
            path="/v2/pairing/hello",
            headers={},
            body=json.dumps(_hello(), separators=(",", ":")).encode("utf-8"),
            client_ip="127.0.0.1",
        )

    assert response.status == HTTPStatus.OK
    document = json.loads(response.body.decode("utf-8"))
    assert document["status"] == "rejected"
    assert document["pairing_id"] == PAIRING_ID
    assert document["transaction_disposition"] == "terminal"
    assert document["reason"] == "expired"

def test_http_hello_requires_bound_repair_intent_without_mutating_current_registration(
    tmp_path,
) -> None:
    repair_pairing_id = "7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"

    with RegistrationRegistry(
        tmp_path / "registration.sqlite3"
    ) as registry:
        registry.observe_hello(_hello(), now=NOW)
        registry.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id="node_endpoint_01",
            now=NOW,
        )

        app = SimplifiedPairingEndpointApp(
            SimplifiedPairingCoordinator(
                registry,
                UnusedStager(),
                manager_id="manager_lab_01",
            ),
            clock=lambda: NOW + timedelta(seconds=1),
        )

        repair_hello = _hello()
        repair_hello["pairing_id"] = repair_pairing_id

        blocked = app.handle(
            method="POST",
            path="/v2/pairing/hello",
            headers={},
            body=json.dumps(
                repair_hello,
                separators=(",", ":"),
            ).encode("utf-8"),
            client_ip="127.0.0.1",
        )

        blocked_document = json.loads(
            blocked.body.decode("utf-8")
        )
        current_before = registry.get(HARDWARE_ID)

        assert blocked.status == HTTPStatus.OK
        assert blocked_document["status"] == "rejected"
        assert blocked_document["reason"] == "repair_intent_required"
        assert (
            blocked_document["transaction_disposition"]
            == "continue"
        )
        assert blocked_document["pairing_id"] == repair_pairing_id
        assert current_before.pairing_id == PAIRING_ID
        assert current_before.state.value == "approved"

        registry.authorize_repair(
            HARDWARE_ID,
            repair_pairing_id,
            now=NOW + timedelta(seconds=1),
        )

        accepted = app.handle(
            method="POST",
            path="/v2/pairing/hello",
            headers={},
            body=json.dumps(
                repair_hello,
                separators=(",", ":"),
            ).encode("utf-8"),
            client_ip="127.0.0.1",
        )

        accepted_document = json.loads(
            accepted.body.decode("utf-8")
        )
        current_after = registry.get(HARDWARE_ID)

    assert accepted.status == HTTPStatus.OK
    assert accepted_document["status"] == "superseded"
    assert accepted_document["reason"] is None
    assert (
        accepted_document["transaction_disposition"]
        == "continue"
    )
    assert current_after.pairing_id == repair_pairing_id
    assert current_after.node_id == "node_endpoint_01"
