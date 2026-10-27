from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from greenhouse_manager.runtime.n3w_first_registration_intent import (
    FirstRegistrationIntent,
    FirstRegistrationIntentStore,
)
from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingCoordinator,
)
from greenhouse_manager.runtime.n3w_simplified_pairing_endpoint import (
    SimplifiedPairingEndpointApp,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
SECRET = bytes(range(32))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def hello(*, hardware_id=HARDWARE_ID, pairing_id=PAIRING_ID):
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": 1,
        "hardware_id": hardware_id,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-simple",
        "node_nonce": _b64(bytes([0x31]) * 32),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": 1,
    }


class UnusedStager:
    def stage(self, **kwargs):
        raise AssertionError(f"staging not expected: {kwargs}")


def make_app(tmp_path):
    registry = RegistrationRegistry(tmp_path / "registration.sqlite3")
    deadline = NOW + timedelta(seconds=1800)
    ledger = registry.first_registration_ledger()
    ledger.create_active(
        pairing_id=PAIRING_ID,
        hardware_id_sha256=hashlib.sha256(
            HARDWARE_ID.encode()
        ).hexdigest(),
        opened_at=NOW,
        expires_at=deadline,
    )
    intent = FirstRegistrationIntent.prepare(
        hardware_id=HARDWARE_ID,
        pairing_id=PAIRING_ID,
        source_ip="192.168.10.44",
        manager_id="manager_lab_01",
        system_id="greenhouse",
        setup_secret=SECRET,
        opened_at=NOW,
        expires_at=deadline,
    )
    FirstRegistrationIntentStore().activate(intent)
    coordinator = SimplifiedPairingCoordinator(
        registry,
        UnusedStager(),
        manager_id="manager_lab_01",
    )
    endpoint = SimplifiedPairingEndpointApp(
        coordinator,
        clock=lambda: NOW,
        first_registration_intent=intent,
        first_registration_ledger=ledger,
    )
    return registry, coordinator, endpoint


def post_hello(endpoint, document, source="192.168.10.44"):
    return endpoint.handle(
        method="POST",
        path="/v2/pairing/hello",
        headers={},
        body=json.dumps(document, separators=(",", ":")).encode(),
        client_ip=source,
    )


def test_binding_mismatch_rejects_before_registration_mutation(tmp_path) -> None:
    registry, _, endpoint = make_app(tmp_path)
    try:
        wrong_source = post_hello(
            endpoint,
            hello(),
            source="192.168.10.45",
        )
        wrong_hardware = post_hello(
            endpoint,
            hello(hardware_id="ghw-c6-00000000000b"),
        )
        wrong_pairing = post_hello(
            endpoint,
            hello(pairing_id="7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"),
        )

        assert wrong_source.status == HTTPStatus.FORBIDDEN
        assert wrong_hardware.status == HTTPStatus.FORBIDDEN
        assert wrong_pairing.status == HTTPStatus.FORBIDDEN
        assert registry.list_current() == ()
    finally:
        registry.close()


def test_exact_hello_uses_shared_deadline_and_imports_secret(tmp_path) -> None:
    registry, coordinator, endpoint = make_app(tmp_path)
    try:
        response = post_hello(endpoint, hello())
        record = registry.get(HARDWARE_ID)
        attempt = registry.first_registration_ledger().get(PAIRING_ID)

        assert response.status == HTTPStatus.OK
        assert record.expires_at == NOW + timedelta(seconds=1800)
        assert attempt.phase.value == "HELLO_OBSERVED"

        offer = coordinator.begin(
            HARDWARE_ID,
            PAIRING_ID,
            node_nonce=_b64(bytes([0x42]) * 16),
            now=NOW + timedelta(seconds=1700),
        )
        assert offer.expires_at == NOW + timedelta(seconds=1800)
    finally:
        registry.close()
