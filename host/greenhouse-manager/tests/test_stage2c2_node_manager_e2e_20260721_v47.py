from __future__ import annotations

import base64
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.pairing_endpoint import PairingEndpointApp, PendingOfferRegistry
from greenhouse_manager.pairing_secure_transport import SecurePairingCoordinator
from greenhouse_manager.pairing_service import (
    CredentialBundle,
    PairingOffer,
    PairingSessionSnapshot,
    PairingSessionState,
)

NOW = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)
SESSION_ID = "96329311-1c64-4c88-9343-04f5de69698e"
PAIRING_ID = "416ccfd2-5a5b-46e0-84d1-44c4067dbde0"
HARDWARE_ID = "ghw-c6-stage2c2-e2e"
NODE_ID = "gh-n1-stage2c2-e2e"
CLIENT_IP = "127.0.0.2"
MANAGER_ID = "manager-stage2c2"


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


PAIRING_SECRET = b64(bytes(range(32)))
MANAGER_NONCE = b64(bytes([0xA5]) * 32)


class IntegrationPairingCore:
    def __init__(self) -> None:
        self.offer = PairingOffer(
            schema="gh.pair.offer/1",
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            manager_nonce=MANAGER_NONCE,
            expires_at=NOW + timedelta(seconds=120),
            max_proof_attempts=3,
        )
        self.state = PairingSessionState.OPEN
        self.issue_calls = 0
        self.ack_calls = 0
        self.abort_calls = 0
        self.bundle = CredentialBundle(
            schema="gh.pair.credentials/1",
            system_id="greenhouse",
            node_id=NODE_ID,
            broker_host="mqtt.greenhouse.local",
            broker_port=8883,
            broker_tls_server_name="mqtt.greenhouse.local",
            ca_pem="-----BEGIN CERTIFICATE-----\nSTAGE2C2\n-----END CERTIFICATE-----\n",
            mqtt_username="ghn_stage2c2_e2e",
            mqtt_client_id=NODE_ID,
            credential_generation=7,
            mqtt_password="stage2c2-e2e-ram-only-password",
        )

    def open_session(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        pairing_secret: str,
        now: datetime | None = None,
    ) -> PairingOffer:
        assert (hardware_id, pairing_id, pairing_secret, now) == (
            HARDWARE_ID,
            PAIRING_ID,
            PAIRING_SECRET,
            NOW,
        )
        return self.offer

    def verify_proof(
        self,
        session_id: str,
        *,
        proof: str,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        assert isinstance(proof, str) and len(proof) == 43
        self.state = PairingSessionState.PROOF_VERIFIED
        return self.snapshot()

    def issue_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> CredentialBundle:
        assert session_id == SESSION_ID
        self.issue_calls += 1
        self.state = PairingSessionState.CREDENTIALS_ISSUED
        return self.bundle

    def acknowledge_delivery(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        self.ack_calls += 1
        self.state = PairingSessionState.CONSUMED
        return self.snapshot()

    def abort(self, session_id: str) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        self.abort_calls += 1
        self.state = PairingSessionState.FAILED
        return self.snapshot()

    def expire_sessions(self, *, now: datetime | None = None) -> int:
        if now is not None and now > self.offer.expires_at:
            self.state = PairingSessionState.EXPIRED
            return 1
        return 0

    def status(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        return self.snapshot()

    def snapshot(self) -> PairingSessionSnapshot:
        generation = (
            self.bundle.credential_generation
            if self.state
            in {
                PairingSessionState.CREDENTIALS_ISSUED,
                PairingSessionState.CONSUMED,
            }
            else None
        )
        return PairingSessionSnapshot(
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            state=self.state,
            expires_at=self.offer.expires_at,
            proof_attempts=0,
            credential_generation=generation,
        )


def post(
    app: PairingEndpointApp,
    path: str,
    document: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    response = app.handle(
        method="POST",
        path=path,
        headers={"Content-Type": "application/json"},
        body=json.dumps(document, separators=(",", ":")).encode("utf-8"),
        client_ip=CLIENT_IP,
    )
    decoded = json.loads(response.body.decode("utf-8"))
    assert isinstance(decoded, dict)
    return response.status, decoded


def exchange(
    process: subprocess.Popen[str], command: str, expected_prefix: str
) -> str:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(command + "\n")
    process.stdin.flush()
    response = process.stdout.readline().rstrip("\n")
    prefix = expected_prefix + "\t"
    assert response.startswith(prefix), response
    return response[len(prefix) :]


def test_stage2c2_cpp_node_closes_manager_endpoint_roundtrip_in_ram() -> None:
    peer_path = Path(os.environ["STAGE2C2_NODE_PEER"])
    assert peer_path.is_file()

    core = IntegrationPairingCore()
    coordinator = SecurePairingCoordinator(
        core,
        private_key_factory=lambda: X25519PrivateKey.from_private_bytes(
            bytes([0x11]) * 32
        ),
    )
    registry = PendingOfferRegistry(coordinator, manager_id=MANAGER_ID)
    registry.import_scanned_pairing(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    app = PairingEndpointApp(registry, clock=lambda: NOW)

    process = subprocess.Popen(
        [str(peer_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        claim_text = exchange(
            process,
            "\t".join(
                ("INIT", MANAGER_ID, HARDWARE_ID, PAIRING_ID, PAIRING_SECRET)
            ),
            "CLAIM",
        )
        assert PAIRING_SECRET not in claim_text
        status, offer = post(app, "/v1/pairing/claim", json.loads(claim_text))
        assert status == 200
        assert "pairing_secret" not in offer

        establish_text = exchange(
            process,
            "\t".join(
                (
                    "OFFER",
                    offer["schema"],
                    offer["session_id"],
                    offer["hardware_id"],
                    offer["pairing_id"],
                    offer["manager_nonce"],
                    offer["manager_public_key"],
                    offer["cipher_suite"],
                    offer["expires_at"],
                    str(offer["max_proof_attempts"]),
                )
            ),
            "ESTABLISH",
        )
        assert PAIRING_SECRET not in establish_text
        status, established = post(
            app,
            f"/v1/pairing/sessions/{SESSION_ID}/establish",
            json.loads(establish_text),
        )
        assert status == 200
        assert established["state"] == "channel_established"

        status, envelope = post(
            app,
            f"/v1/pairing/sessions/{SESSION_ID}/credentials",
            {"schema": "gh.pair.credentials-request/1"},
        )
        assert status == 200
        assert core.bundle.mqtt_password not in json.dumps(envelope)

        ack_text = exchange(
            process,
            "\t".join(
                (
                    "CREDENTIALS",
                    envelope["schema"],
                    envelope["session_id"],
                    envelope["direction"],
                    str(envelope["sequence"]),
                    envelope["content_type"],
                    envelope["nonce"],
                    envelope["ciphertext"],
                )
            ),
            "ACK",
        )
        assert core.bundle.mqtt_password not in ack_text
        status, consumed = post(
            app,
            f"/v1/pairing/sessions/{SESSION_ID}/ack",
            json.loads(ack_text),
        )
        assert status == 200
        assert consumed["state"] == "consumed"
        assert consumed["credential_generation"] == 7

        committed = exchange(
            process,
            "\t".join(("COMMIT", NODE_ID, "7")),
            "COMMITTED",
        )
        assert committed == f"{NODE_ID}\t7\tRAM_ONLY"
        assert core.issue_calls == 1
        assert core.ack_calls == 1
        assert core.abort_calls == 0
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            return_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            return_code = process.wait(timeout=5)
        stderr = process.stderr.read() if process.stderr is not None else ""
        assert return_code == 0, stderr
