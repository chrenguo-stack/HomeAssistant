from __future__ import annotations

import base64
import http.client
import json
import threading
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

from greenhouse_manager.pairing_endpoint import (
    MAX_REQUEST_BYTES,
    FixedWindowRateLimiter,
    PairingEndpointApp,
    PendingOfferRegistry,
    build_claim_proof,
    make_pairing_http_server,
)
from greenhouse_manager.pairing_secure_transport import (
    MANAGER_TO_NODE,
    NODE_TO_MANAGER,
    SecureEnvelope,
    SecurePairingConflict,
    SecurePairingOffer,
    SecurePairingSnapshot,
    SecurePairingState,
)

NOW = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
SESSION_ID = "96329311-1c64-4c88-9343-04f5de69698e"
PAIRING_ID = "416ccfd2-5a5b-46e0-84d1-44c4067dbde0"
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
LOCAL_IP = "192.168.1.50"


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


PAIRING_SECRET = b64(bytes(range(32)))
NODE_NONCE = b64(bytes(reversed(range(32))))
NODE_PUBLIC_KEY = b64(bytes([0x22]) * 32)
PROOF = b64(bytes([0x33]) * 32)
CLAIM_PROOF = build_claim_proof(
    pairing_secret=PAIRING_SECRET,
    hardware_id=HARDWARE_ID,
    pairing_id=PAIRING_ID,
)


class FakeCoordinator:
    def __init__(self) -> None:
        self.offer = SecurePairingOffer(
            schema="gh.pair.secure-offer/1",
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            manager_nonce=b64(bytes([0x44]) * 32),
            manager_public_key=b64(bytes([0x55]) * 32),
            cipher_suite="X25519-HKDF-SHA256-CHACHA20-POLY1305",
            expires_at=NOW + timedelta(seconds=120),
            max_proof_attempts=3,
        )
        self.state = SecurePairingState.OFFERED
        self.open_calls = 0
        self.establish_calls = 0
        self.issue_calls = 0
        self.ack_calls = 0
        self.abort_calls = 0
        self.last_ack: Mapping[str, Any] | None = None

    def open_session(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        pairing_secret: str,
        now: datetime | None = None,
    ) -> SecurePairingOffer:
        assert (hardware_id, pairing_id, pairing_secret) == (
            HARDWARE_ID,
            PAIRING_ID,
            PAIRING_SECRET,
        )
        self.open_calls += 1
        return self.offer

    def establish_channel(
        self,
        session_id: str,
        *,
        node_nonce: str,
        node_public_key: str,
        proof: str,
        now: datetime | None = None,
    ) -> SecurePairingSnapshot:
        assert (session_id, node_nonce, node_public_key, proof) == (
            SESSION_ID,
            NODE_NONCE,
            NODE_PUBLIC_KEY,
            PROOF,
        )
        self.establish_calls += 1
        self.state = SecurePairingState.CHANNEL_ESTABLISHED
        return self.snapshot()

    def issue_encrypted_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SecureEnvelope:
        if self.state != SecurePairingState.CHANNEL_ESTABLISHED:
            raise SecurePairingConflict("credentials are not ready")
        self.issue_calls += 1
        self.state = SecurePairingState.CREDENTIALS_ENCRYPTED
        return SecureEnvelope(
            schema="gh.pair.envelope/1",
            session_id=SESSION_ID,
            direction=MANAGER_TO_NODE,
            sequence=0,
            content_type="gh.pair.credentials/1",
            nonce=b64(b"\x00\x00\x00\x01" + bytes(8)),
            ciphertext=b64(b"encrypted-credentials"),
        )

    def acknowledge_encrypted_delivery(
        self,
        session_id: str,
        envelope: SecureEnvelope | Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> SecurePairingSnapshot:
        assert session_id == SESSION_ID
        self.last_ack = (
            envelope.to_document()
            if isinstance(envelope, SecureEnvelope)
            else envelope
        )
        self.ack_calls += 1
        self.state = SecurePairingState.CONSUMED
        return self.snapshot(generation=1)

    def abort(self, session_id: str) -> SecurePairingSnapshot:
        assert session_id == SESSION_ID
        self.abort_calls += 1
        self.state = SecurePairingState.FAILED
        return self.snapshot()

    def status(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SecurePairingSnapshot:
        assert session_id == SESSION_ID
        return self.snapshot()

    def snapshot(self, *, generation: int | None = None) -> SecurePairingSnapshot:
        return SecurePairingSnapshot(
            session_id=SESSION_ID,
            state=self.state,
            expires_at=self.offer.expires_at,
            proof_attempts=0,
            credential_generation=generation,
        )


def make_app(
    *,
    limiter: FixedWindowRateLimiter | None = None,
) -> tuple[FakeCoordinator, PendingOfferRegistry, PairingEndpointApp]:
    coordinator = FakeCoordinator()
    registry = PendingOfferRegistry(coordinator)
    registry.import_scanned_pairing(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    return (
        coordinator,
        registry,
        PairingEndpointApp(
            registry,
            rate_limiter=limiter,
            clock=lambda: NOW,
        ),
    )


def request(
    app: PairingEndpointApp,
    *,
    method: str,
    path: str,
    document: Mapping[str, Any] | None = None,
    client_ip: str = LOCAL_IP,
    content_type: str = "application/json",
) -> tuple[int, dict[str, Any]]:
    body = (
        json.dumps(document, separators=(",", ":")).encode()
        if document is not None
        else b""
    )
    response = app.handle(
        method=method,
        path=path,
        headers={
            "Content-Type": content_type,
            "X-Request-ID": "d63a3f85-a022-4438-af1d-f15df342ec9c",
        },
        body=body,
        client_ip=client_ip,
    )
    return response.status, json.loads(response.body)


def claim(app: PairingEndpointApp, *, client_ip: str = LOCAL_IP) -> None:
    status, document = request(
        app,
        method="POST",
        path="/v1/pairing/claim",
        client_ip=client_ip,
        document={
            "schema": "gh.pair.claim/1",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "claim_proof": CLAIM_PROOF,
        },
    )
    assert status == 200
    assert document["session_id"] == SESSION_ID


def test_claim_never_returns_pairing_secret() -> None:
    coordinator, _registry, app = make_app()
    status, document = request(
        app,
        method="POST",
        path="/v1/pairing/claim",
        document={
            "schema": "gh.pair.claim/1",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "claim_proof": CLAIM_PROOF,
        },
    )
    assert status == 200
    assert document["schema"] == "gh.pair.secure-offer/1"
    assert "secret" not in json.dumps(document).lower()
    assert coordinator.open_calls == 1


def test_invalid_claim_proof_does_not_bind_offer() -> None:
    _coordinator, _registry, app = make_app()
    status, document = request(
        app,
        method="POST",
        path="/v1/pairing/claim",
        document={
            "schema": "gh.pair.claim/1",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "claim_proof": b64(bytes([0xFF]) * 32),
        },
    )
    assert status == 403
    assert document["error"] == "proof_rejected"

    claim(app)


def test_offer_claim_is_bound_to_first_client_ip() -> None:
    _coordinator, _registry, app = make_app()
    claim(app)
    status, document = request(
        app,
        method="POST",
        path="/v1/pairing/claim",
        client_ip="192.168.1.51",
        document={
            "schema": "gh.pair.claim/1",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "claim_proof": CLAIM_PROOF,
        },
    )
    assert status == 409
    assert document["error"] == "pairing_conflict"


def test_establish_credentials_and_ack_routes() -> None:
    coordinator, _registry, app = make_app()
    claim(app)

    status, document = request(
        app,
        method="POST",
        path=f"/v1/pairing/sessions/{SESSION_ID}/establish",
        document={
            "schema": "gh.pair.establish/1",
            "node_nonce": NODE_NONCE,
            "node_public_key": NODE_PUBLIC_KEY,
            "proof": PROOF,
        },
    )
    assert status == 200
    assert document["state"] == "channel_established"

    status, envelope = request(
        app,
        method="POST",
        path=f"/v1/pairing/sessions/{SESSION_ID}/credentials",
        document={"schema": "gh.pair.credentials-request/1"},
    )
    assert status == 200
    assert envelope["content_type"] == "gh.pair.credentials/1"

    ack = {
        "schema": "gh.pair.envelope/1",
        "session_id": SESSION_ID,
        "direction": NODE_TO_MANAGER,
        "sequence": 0,
        "content_type": "gh.pair.delivery-ack/1",
        "nonce": b64(b"\x00\x00\x00\x02" + bytes(8)),
        "ciphertext": b64(b"encrypted-ack"),
    }
    status, document = request(
        app,
        method="POST",
        path=f"/v1/pairing/sessions/{SESSION_ID}/ack",
        document=ack,
    )
    assert status == 200
    assert document["state"] == "consumed"
    assert coordinator.establish_calls == 1
    assert coordinator.issue_calls == 1
    assert coordinator.ack_calls == 1
    assert coordinator.last_ack == ack


def test_session_route_is_hidden_from_other_client() -> None:
    _coordinator, _registry, app = make_app()
    claim(app)
    status, document = request(
        app,
        method="GET",
        path=f"/v1/pairing/sessions/{SESSION_ID}/status",
        client_ip="192.168.1.51",
        document=None,
    )
    assert status == 404
    assert document["error"] == "not_found"


def test_abort_releases_terminal_offer() -> None:
    coordinator, _registry, app = make_app()
    claim(app)
    status, document = request(
        app,
        method="POST",
        path=f"/v1/pairing/sessions/{SESSION_ID}/abort",
        document={"schema": "gh.pair.abort/1"},
    )
    assert status == 200
    assert document["state"] == "failed"
    assert coordinator.abort_calls == 1

    status, _document = request(
        app,
        method="GET",
        path=f"/v1/pairing/sessions/{SESSION_ID}/status",
        document=None,
    )
    assert status == 404


def test_endpoint_rejects_public_sources_and_non_json() -> None:
    _coordinator, _registry, app = make_app()
    status, document = request(
        app,
        method="POST",
        path="/v1/pairing/claim",
        client_ip="8.8.8.8",
        document={"schema": "gh.pair.claim/1"},
    )
    assert status == 400
    assert document["error"] == "invalid_request"

    status, document = request(
        app,
        method="POST",
        path="/v1/pairing/claim",
        content_type="text/plain",
        document={"schema": "gh.pair.claim/1"},
    )
    assert status == 415
    assert document["error"] == "json_required"


def test_endpoint_enforces_request_size_and_rate_limit() -> None:
    clock = [100.0]
    limiter = FixedWindowRateLimiter(
        limit=1,
        window_s=60,
        clock=lambda: clock[0],
    )
    _coordinator, _registry, app = make_app(limiter=limiter)
    first = app.handle(
        method="GET",
        path="/healthz",
        headers={},
        body=b"",
        client_ip=LOCAL_IP,
    )
    second = app.handle(
        method="GET",
        path="/healthz",
        headers={},
        body=b"",
        client_ip=LOCAL_IP,
    )
    assert first.status == 200
    assert second.status == 429

    other_ip = "192.168.1.51"
    oversized = app.handle(
        method="POST",
        path="/v1/pairing/claim",
        headers={"Content-Type": "application/json"},
        body=b"x" * (MAX_REQUEST_BYTES + 1),
        client_ip=other_ip,
    )
    assert oversized.status == 413


def test_unknown_fields_are_rejected() -> None:
    _coordinator, _registry, app = make_app()
    status, document = request(
        app,
        method="POST",
        path="/v1/pairing/claim",
        document={
            "schema": "gh.pair.claim/1",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "claim_proof": CLAIM_PROOF,
            "pairing_secret": PAIRING_SECRET,
        },
    )
    assert status == 400
    assert document["error"] == "invalid_request"


def test_real_loopback_http_health_request() -> None:
    _coordinator, _registry, app = make_app()
    server = make_pairing_http_server(("127.0.0.1", 0), app=app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        document = json.loads(response.read())
        connection.close()
        assert response.status == 200
        assert document == {"schema": "gh.pair.health/1", "status": "ok"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
