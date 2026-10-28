from __future__ import annotations

import base64
import ipaddress
import json
import os
import socket
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.credential_lifecycle import (
    CredentialLifecycleStore,
    CredentialState,
)
from greenhouse_manager.runtime.dynsec_api import (
    DynsecError,
    DynsecProvisioner,
    set_client_password_command,
)
from greenhouse_manager.runtime.n3w_dynamic_pairing_window import (
    DynamicPairingWindowController,
)
from greenhouse_manager.runtime.n3w_first_registration_intent import (
    FirstRegistrationIntentStore,
)
from greenhouse_manager.runtime.n3w_first_registration_ledger import (
    FirstRegistrationAttemptState,
    FirstRegistrationPhase,
)
from greenhouse_manager.runtime.n3w_first_registration_reconciliation import (
    FirstRegistrationReconciler,
)
from greenhouse_manager.runtime.n3w_first_registration_transaction import (
    FIRST_REGISTRATION_TTL_SECONDS,
    FirstRegistrationTransactionService,
)
from greenhouse_manager.runtime.n3w_node_application_keys import (
    SqliteNodeApplicationKeyAdmin,
    SqliteNodeApplicationKeyProvider,
)
from greenhouse_manager.runtime.n3w_registration_bootstrap import (
    RegistrationBootstrapApp,
    validate_bootstrap_source,
)
from greenhouse_manager.runtime.n3w_registration_discovery import (
    REGISTRATION_PROTOCOL,
    RegistrationCandidate,
    build_registration_udp_response,
)
from greenhouse_manager.runtime.n3w_simple_pairing_crypto import (
    PairingTranscript,
    build_setup_proof,
    decrypt_credential_bundle,
    derive_bootstrap_key,
    verify_setup_proof,
)
from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingState,
)
from greenhouse_manager.runtime.n3w_simplified_product_runtime import (
    build_simplified_product_config_from_settings,
    build_simplified_product_pairing_composition,
)
from greenhouse_manager.runtime.n3w_trusted_product_lan import (
    TrustedProductLanState,
)
from greenhouse_manager.runtime.pairing_discovery import (
    SlidingWindowRateLimiter,
)
from greenhouse_manager.runtime.registration import (
    NodeIdLeaseState,
    RegistrationRegistry,
    RegistrationState,
)

NOW = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
SOURCE_IP = "192.0.2.44"
T1_IP = "192.0.2.10"
TRUSTED_SUBNET = "192.0.2.0/24"
HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
PAIRING_ID_B = "7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"
HARDWARE_ID_B = "ghw-c6-00000000000b"
SETUP_SECRET = bytes(range(32))
SETUP_SECRET_B = bytes(reversed(range(32)))
TLS_FINGERPRINT = "a" * 64


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(
        value + "=" * ((4 - len(value) % 4) % 4)
    )


def trusted_state() -> TrustedProductLanState:
    return TrustedProductLanState(
        available=True,
        subnet=ipaddress.ip_network(TRUSTED_SUBNET),
        reason="unique_ipv4_subnet",
        generation="r8-synthetic-generation",
        published_at="2026-10-28T08:00:00Z",
    )


def authorize_synthetic_source(source_ip: str) -> None:
    validate_bootstrap_source(
        source_ip,
        state_loader=trusted_state,
    )


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def tcp_listener_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
            return True
    except OSError:
        return False


def wait_for(
    predicate,
    *,
    timeout_s: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("bounded asynchronous state transition did not complete")


class FakeDynsecTransport:
    def __init__(self) -> None:
        self.client: dict[str, Any] | None = None
        self.role: dict[str, Any] | None = None
        self.calls: list[str] = []

    def execute(
        self,
        commands: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        responses: list[dict[str, Any]] = []
        for command in commands:
            name = str(command["command"])
            self.calls.append(name)

            if name == "createRole":
                if self.role is not None:
                    raise DynsecError("role exists")
                self.role = {
                    "rolename": command["rolename"],
                    "acls": list(command["acls"]),
                }
                responses.append({"command": name})
                continue

            if name == "createClient":
                if self.client is not None:
                    raise DynsecError("client exists")
                self.client = {
                    "username": command["username"],
                    "clientid": command["clientid"],
                    "roles": list(command["roles"]),
                }
                responses.append({"command": name})
                continue

            if name == "setClientPassword":
                if self.client is None:
                    raise DynsecError("client missing")
                responses.append({"command": name})
                continue

            if name == "deleteClient":
                self.client = None
                responses.append({"command": name})
                continue

            if name == "deleteRole":
                self.role = None
                responses.append({"command": name})
                continue

            if name == "listClients":
                values: list[object] = []
                if self.client is not None:
                    values.append(self.client["username"])
                responses.append(
                    {
                        "command": name,
                        "data": {"clients": values},
                    }
                )
                continue

            if name == "listRoles":
                values = []
                if self.role is not None:
                    values.append(self.role["rolename"])
                responses.append(
                    {
                        "command": name,
                        "data": {"roles": values},
                    }
                )
                continue

            if name == "getClient":
                if self.client is None:
                    raise DynsecError("client missing")
                responses.append(
                    {
                        "command": name,
                        "data": dict(self.client),
                    }
                )
                continue

            if name == "getRole":
                if self.role is None:
                    raise DynsecError("role missing")
                responses.append(
                    {
                        "command": name,
                        "data": dict(self.role),
                    }
                )
                continue

            raise AssertionError(f"unsupported synthetic DynSec command: {name}")

        return tuple(responses)


class InMemoryIdentityProvisioner:
    def __init__(self) -> None:
        self.transport = FakeDynsecTransport()
        self.provisioner = DynsecProvisioner(self.transport)

    def inspect_plan(self, plan):
        return self.provisioner.inspect_plan(plan)

    def provision(self, plan, credentials) -> None:
        self.provisioner.provision(plan, credentials)

    def deprovision(self, plan) -> None:
        self.provisioner.deprovision(plan)

    def set_password(self, plan, credentials) -> None:
        self.transport.execute(
            (set_client_password_command(plan, credentials),)
        )


@dataclass
class PhoneLikeBrowser:
    visible: list[object] = field(default_factory=list)

    def record(self, value: object) -> None:
        self.visible.append(value)

    def assert_private_material_absent(
        self,
        *,
        private_values: tuple[str, ...],
    ) -> None:
        forbidden_keys = {
            "setup_secret",
            "pairing_id",
            "hardware_id",
            "manager_id",
            "system_id",
            "bootstrap_tls_sha256",
            "mqtt_password",
            "n3w_application_key",
            "system_peer_key",
            "host",
            "bootstrap_port",
        }

        def walk(value: object) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    if str(key).lower() in forbidden_keys:
                        raise AssertionError(
                            "browser projection contains a forbidden private field"
                        )
                    walk(nested)
            elif isinstance(value, list | tuple):
                for nested in value:
                    walk(nested)

        for item in self.visible:
            walk(item)

        encoded = json.dumps(
            self.visible,
            ensure_ascii=False,
            sort_keys=True,
        )
        for private in private_values:
            if private and private in encoded:
                raise AssertionError(
                    "browser projection leaked a private protocol value"
                )


class SimulatedNode:
    def __init__(
        self,
        browser: PhoneLikeBrowser,
        *,
        hardware_id: str = HARDWARE_ID,
        pairing_id: str = PAIRING_ID,
        setup_secret: bytes = SETUP_SECRET,
    ) -> None:
        self.browser = browser
        self.hardware_id = hardware_id
        self.pairing_id = pairing_id
        self.setup_secret = setup_secret
        self.scan_token = "r8-opaque-scan-token"
        self.private_candidates: dict[str, RegistrationCandidate] = {}
        self.discovery_count = 0
        self.bootstrap_count = 0

    def open_page(self) -> None:
        self.browser.record(
            {
                "page": "/register",
                "fragment_token": self.scan_token,
                "status": "idle",
            }
        )

    def discover_one(self) -> None:
        self.discovery_count += 1
        query = json.dumps(
            {
                "schema": "gh.discovery.query/1",
                "request_id": str(uuid.uuid4()),
                "nonce": b64(bytes(range(32))),
                "hardware_id": self.hardware_id,
                "protocols": [REGISTRATION_PROTOCOL],
            },
            separators=(",", ":"),
        ).encode()
        query += b" " * (1400 - len(query))
        response = build_registration_udp_response(
            query,
            source_ip=SOURCE_IP,
            candidate_for=lambda _source: RegistrationCandidate(
                manager_id="manager_lab_01",
                system_id="lab",
                system_id_hint="LAB01",
                host=T1_IP,
                bootstrap_tls_sha256=TLS_FINGERPRINT,
            ),
            state_loader=trusted_state,
            rate_limiter=SlidingWindowRateLimiter(
                limit=4,
                window_s=60,
            ),
        )
        document = json.loads(response.decode())
        candidate = RegistrationCandidate(**document["candidate"])
        self.set_candidates((candidate,))

    def set_candidates(
        self,
        candidates: tuple[RegistrationCandidate, ...],
    ) -> None:
        self.private_candidates.clear()
        safe: list[dict[str, str]] = []
        for index, candidate in enumerate(candidates):
            candidate_id = f"c{index}"
            self.private_candidates[candidate_id] = candidate
            safe.append(
                {
                    "id": candidate_id,
                    "label": f"温室主机 {candidate.system_id_hint}",
                }
            )
        self.browser.record(
            {
                "status": "wait_confirm" if safe else "no_candidate",
                "node_label": f"节点 {self.hardware_id[-6:]}",
                "candidates": safe,
            }
        )

    def select(self, candidate_id: str) -> RegistrationCandidate | None:
        candidate = self.private_candidates.get(candidate_id)
        if candidate is None:
            self.browser.record(
                {
                    "status": "candidate_stale",
                    "retry_required": True,
                }
            )
            return None
        self.browser.record(
            {
                "status": "selected_pending_bootstrap",
                "candidate_id": candidate_id,
            }
        )
        return candidate

    def bootstrap_document(
        self,
        candidate: RegistrationCandidate,
    ) -> dict[str, str]:
        self.bootstrap_count += 1
        return {
            "schema": "gh.registration.confirm/1",
            "manager_id": candidate.manager_id,
            "system_id": candidate.system_id,
            "hardware_id": self.hardware_id,
            "pairing_id": self.pairing_id,
            "setup_secret": b64(self.setup_secret),
        }


class R8Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "private"
        self.root.mkdir(mode=0o700)
        os.chmod(self.root, 0o700)
        self.http_port = free_tcp_port()
        self.settings = self._settings()
        self.identity = InMemoryIdentityProvisioner()
        self.registry = RegistrationRegistry(
            Path(self.settings.pairing_db_path)
        )
        os.chmod(self.settings.pairing_db_path, 0o600)
        self.credentials = CredentialLifecycleStore(
            self.settings.n3w_credential_lifecycle_db_path
        )
        os.chmod(
            self.settings.n3w_credential_lifecycle_db_path,
            0o600,
        )
        self.keys = SqliteNodeApplicationKeyAdmin(
            self.settings.n3w_relay_authorization_db_path,
            self.settings.n3w_relay_key_dir,
            node_state=self.registry.node_id_lease_state,
            recover_on_open=False,
        )
        self.reconciler = FirstRegistrationReconciler(
            registry=self.registry,
            credential_store=self.credentials,
            application_keys=self.keys,
            dynsec=self.identity.provisioner,
            system_id="lab",
        )
        self.compositions = []
        self.controller = DynamicPairingWindowController(
            self.settings,
            registration=self.registry,
            route_resolver=lambda _peer: T1_IP,
            composition_factory=self._composition_factory,
            clock=lambda: 100.0,
            wall_clock=lambda: NOW,
        )
        self.intents = FirstRegistrationIntentStore()
        self.transaction = FirstRegistrationTransactionService(
            registry=self.registry,
            intents=self.intents,
            window=self.controller,
            manager_id="manager_lab_01",
            system_id="lab",
            clock=lambda: NOW,
            reconciler=self.reconciler,
        )
        self.controller.set_first_registration_close_callback(
            self.transaction.window_closed
        )
        self.bootstrap = RegistrationBootstrapApp(
            manager_id="manager_lab_01",
            system_id="lab",
            state_loader=trusted_state,
            transaction_service=self.transaction,
            clock=lambda: NOW,
        )

    def _settings(self) -> Settings:
        ca = self.root / "node-ca.pem"
        ca.write_text(
            (
                "-----BEGIN CERTIFICATE-----\n"
                "TEST\n"
                "-----END CERTIFICATE-----\n"
            ),
            encoding="utf-8",
        )
        return Settings(
            system_id="lab",
            mqtt_host="127.0.0.1",
            mqtt_port=8883,
            n3w_runtime_enabled=True,
            n3w_product_pairing_enabled=False,
            n3w_pairing_manager_id="manager_lab_01",
            n3w_pairing_bind_host="127.0.0.1",
            n3w_pairing_advertised_host="auto",
            n3w_pairing_http_port=self.http_port,
            n3w_pairing_udp_port=47111,
            n3w_provisioning_username="provisioner",
            n3w_provisioning_password="private-test-password",
            n3w_provisioning_client_id="provisioner-client",
            n3w_node_broker_host=T1_IP,
            n3w_node_broker_port=8883,
            n3w_node_broker_tls_server_name="mqtt.lab.local",
            n3w_node_broker_ca_file=str(ca),
            pairing_db_path=str(self.root / "registration.sqlite3"),
            n3w_replay_db_path=str(self.root / "replay.sqlite3"),
            n3w_relay_authorization_db_path=str(
                self.root / "node-keys.sqlite3"
            ),
            n3w_relay_key_dir=str(self.root / "node-keys"),
            n3w_peer_trust_db_path=str(
                self.root / "peer-trust.sqlite3"
            ),
            n3w_credential_lifecycle_db_path=str(
                self.root / "credential-lifecycle.sqlite3"
            ),
            n3w_pairing_socket_path=str(
                self.root / "pairing.sock"
            ),
        )

    def _composition_factory(
        self,
        settings: Settings,
        config,
        **kwargs,
    ):
        composition = build_simplified_product_pairing_composition(
            settings,
            config,
            identity_provisioner_factory=(
                lambda **_identity_kwargs: self.identity
            ),
            **kwargs,
        )
        app = composition.pairing_runtime.components.endpoint_app
        app.clock = lambda: NOW
        app.first_registration_source_authorizer = (
            authorize_synthetic_source
        )
        self.compositions.append(composition)
        return composition

    @property
    def composition(self):
        assert len(self.compositions) == 1
        return self.compositions[0]

    @property
    def endpoint(self):
        return self.composition.pairing_runtime.components.endpoint_app

    def endpoint_post(
        self,
        path: str,
        document: dict[str, object],
        *,
        source_ip: str = SOURCE_IP,
    ) -> tuple[int, dict[str, object]]:
        response = self.endpoint.handle(
            method="POST",
            path=path,
            headers={},
            body=json.dumps(
                document,
                separators=(",", ":"),
            ).encode(),
            client_ip=source_ip,
        )
        return int(response.status), json.loads(response.body.decode())

    def close(self) -> None:
        try:
            self.controller.stop()
        finally:
            self.keys.close()
            self.credentials.close()
            self.registry.close()


@pytest.fixture
def harness(tmp_path: Path):
    value = R8Harness(tmp_path)
    yield value
    value.close()


def open_first_registration(
    harness: R8Harness,
    node: SimulatedNode,
):
    node.discover_one()
    selected = node.select("c0")
    assert selected is not None
    result = harness.bootstrap.handle_confirm(
        node.bootstrap_document(selected),
        source_ip=SOURCE_IP,
    )
    assert result.transaction_started is True
    return result


def pair_until_bundle(
    harness: R8Harness,
    node: SimulatedNode,
) -> tuple[str, str, dict[str, object]]:
    hello = {
        "schema": "gh.pair.hello/1",
        "pairing_id": node.pairing_id,
        "pairing_epoch": 1,
        "hardware_id": node.hardware_id,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N3W",
        "node_nonce": b64(bytes([0x31]) * 32),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": 1,
    }
    status, hello_result = harness.endpoint_post(
        "/v2/pairing/hello",
        hello,
    )
    assert status == HTTPStatus.OK
    assert hello_result["status"] in {"created", "duplicate"}

    node_nonce = bytes([0x21]) * 16
    status, offer = harness.endpoint_post(
        "/v2/pairing/begin",
        {
            "schema": "gh.pair.simple-begin/1",
            "hardware_id": node.hardware_id,
            "pairing_id": node.pairing_id,
            "node_nonce": b64(node_nonce),
        },
    )
    assert status == HTTPStatus.OK

    transcript = PairingTranscript(
        pairing_id=node.pairing_id,
        hardware_id=node.hardware_id,
        manager_id=str(offer["manager_id"]),
        node_nonce=node_nonce,
        manager_nonce=unb64(str(offer["manager_nonce"])),
    )
    assert verify_setup_proof(
        node.setup_secret,
        transcript,
        role="manager",
        proof=unb64(str(offer["manager_proof"])),
    )

    node_proof = build_setup_proof(
        node.setup_secret,
        transcript,
        role="node",
    )
    session_id = str(offer["session_id"])
    status, encrypted = harness.endpoint_post(
        f"/v2/pairing/sessions/{session_id}/establish",
        {
            "schema": "gh.pair.simple-establish/1",
            "node_proof": b64(node_proof),
        },
    )
    assert status == HTTPStatus.OK

    plaintext = decrypt_credential_bundle(
        derive_bootstrap_key(
            node.setup_secret,
            transcript,
        ),
        transcript,
        nonce=unb64(str(encrypted["nonce"])),
        ciphertext=unb64(str(encrypted["ciphertext"])),
    )
    bundle = json.loads(plaintext.decode())
    return session_id, str(encrypted["delivery_digest"]), bundle


def assert_browser_private_values_absent(
    browser: PhoneLikeBrowser,
) -> None:
    browser.assert_private_material_absent(
        private_values=(
            b64(SETUP_SECRET),
            PAIRING_ID,
            HARDWARE_ID,
            T1_IP,
            TLS_FINGERPRINT,
            "manager_lab_01",
            "lab",
        )
    )


def test_full_scan_triggered_first_registration_reaches_durable_commit(
    harness: R8Harness,
) -> None:
    browser = PhoneLikeBrowser()
    node = SimulatedNode(browser)

    assert FIRST_REGISTRATION_TTL_SECONDS == 1800
    assert harness.controller.status()["pairing_window_state"] == "CLOSED"
    assert tcp_listener_open(harness.http_port) is False
    assert harness.registry.first_registration_ledger().list_reconcilable() == ()

    node.open_page()
    assert node.discovery_count == 0
    assert node.bootstrap_count == 0
    assert harness.controller.status()["pairing_window_state"] == "CLOSED"

    result = open_first_registration(harness, node)
    attempt = harness.registry.first_registration_ledger().get(PAIRING_ID)

    assert node.discovery_count == 1
    assert node.bootstrap_count == 1
    assert attempt.state is FirstRegistrationAttemptState.ACTIVE
    assert attempt.phase is FirstRegistrationPhase.BOOTSTRAP_ACCEPTED
    assert attempt.expires_at == NOW + timedelta(seconds=1800)
    assert result.expires_in_seconds == 1800
    assert harness.controller.status()["pairing_window_state"] == "OPEN"
    assert tcp_listener_open(harness.http_port) is True

    session_id, delivery_digest, bundle = pair_until_bundle(
        harness,
        node,
    )
    staged = harness.registry.first_registration_ledger().get(PAIRING_ID)
    assert staged.phase is FirstRegistrationPhase.BUNDLE_STAGED
    assert bundle["schema"] == "gh.pair.credentials/2"
    assert bundle["system_id"] == "lab"

    status, ack = harness.endpoint_post(
        f"/v2/pairing/sessions/{session_id}/ack",
        {
            "schema": "gh.pair.simple-ack/1",
            "delivery_digest": delivery_digest,
        },
    )
    assert status == HTTPStatus.OK
    assert ack["state"] == SimplifiedPairingState.CONSUMED.value

    committed = harness.registry.first_registration_ledger().get(PAIRING_ID)
    assert committed.state is FirstRegistrationAttemptState.COMMITTED

    registration = harness.registry.get(HARDWARE_ID)
    assert registration.state is RegistrationState.APPROVED
    assert registration.node_id == bundle["node_id"]
    assert (
        harness.registry.node_id_lease_state(str(bundle["node_id"]))
        is NodeIdLeaseState.ACTIVE
    )

    lifecycle = harness.credentials.get(HARDWARE_ID)
    assert lifecycle.state is CredentialState.ACTIVE
    assert lifecycle.active_generation == 1

    with SqliteNodeApplicationKeyProvider(
        harness.settings.n3w_relay_authorization_db_path,
        harness.settings.n3w_relay_key_dir,
    ) as provider:
        assert (
            provider.resolve_key(
                node_id=str(bundle["node_id"]),
                key_epoch=int(bundle["n3w_key_epoch"]),
            )
            == unb64(str(bundle["n3w_application_key"]))
        )

    peer = harness.composition.peer_trust.get("lab")
    assert b64(peer.key) == bundle["system_peer_key"]
    assert harness.identity.transport.client is not None
    assert harness.identity.transport.role is not None

    wait_for(
        lambda: (
            harness.controller.status()["pairing_window_state"]
            == "CLOSED"
        )
    )
    assert harness.controller.status()["close_reason"] == "committed"
    assert tcp_listener_open(harness.http_port) is False
    assert harness.intents.current() is None
    assert len(harness.compositions) == 1

    browser.record({"status": "registration_complete"})
    assert_browser_private_values_absent(browser)


def test_ack_response_loss_recovers_only_exact_committed_digest(
    harness: R8Harness,
) -> None:
    node = SimulatedNode(PhoneLikeBrowser())
    open_first_registration(harness, node)
    session_id, delivery_digest, _bundle = pair_until_bundle(
        harness,
        node,
    )

    status, _discarded_ack = harness.endpoint_post(
        f"/v2/pairing/sessions/{session_id}/ack",
        {
            "schema": "gh.pair.simple-ack/1",
            "delivery_digest": delivery_digest,
        },
    )
    assert status == HTTPStatus.OK

    exact = harness.bootstrap.handle_status(
        {
            "schema": "gh.registration.status/1",
            "manager_id": "manager_lab_01",
            "system_id": "lab",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "delivery_digest": delivery_digest,
        },
        source_ip=SOURCE_IP,
    )
    wrong = harness.bootstrap.handle_status(
        {
            "schema": "gh.registration.status/1",
            "manager_id": "manager_lab_01",
            "system_id": "lab",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "delivery_digest": b64(bytes([0xEE]) * 32),
        },
        source_ip=SOURCE_IP,
    )

    assert exact["status"] == "committed"
    assert exact["transaction_disposition"] == "committed"
    assert wrong["status"] == "unknown"
    assert wrong["transaction_disposition"] == "wait"
    assert len(harness.compositions) == 1

    wait_for(
        lambda: (
            harness.controller.status()["pairing_window_state"]
            == "CLOSED"
        )
    )
    assert tcp_listener_open(harness.http_port) is False


@pytest.mark.parametrize(
    ("source_ip", "hardware_id", "pairing_id"),
    [
        ("192.0.2.45", HARDWARE_ID, PAIRING_ID),
        (SOURCE_IP, HARDWARE_ID_B, PAIRING_ID),
        (SOURCE_IP, HARDWARE_ID, PAIRING_ID_B),
    ],
)
def test_47112_binding_rejects_before_registration_mutation(
    harness: R8Harness,
    source_ip: str,
    hardware_id: str,
    pairing_id: str,
) -> None:
    node = SimulatedNode(PhoneLikeBrowser())
    open_first_registration(harness, node)

    assert harness.composition.registry.list_current() == ()
    status, _document = harness.endpoint_post(
        "/v2/pairing/hello",
        {
            "schema": "gh.pair.hello/1",
            "pairing_id": pairing_id,
            "pairing_epoch": 1,
            "hardware_id": hardware_id,
            "model": "greenhouse-wifi-c6",
            "fw_version": "F1.0-RC2-N3W",
            "node_nonce": b64(bytes([0x31]) * 32),
            "capabilities": ["simple-setup-secret"],
            "sent_at_ms": 1,
        },
        source_ip=source_ip,
    )

    assert status == HTTPStatus.FORBIDDEN
    assert harness.composition.registry.list_current() == ()
    assert harness.controller.status()["pairing_window_state"] == "OPEN"


def test_predeadline_bad_node_proof_does_not_close_or_refresh_window(
    harness: R8Harness,
) -> None:
    node = SimulatedNode(PhoneLikeBrowser())
    open_first_registration(harness, node)
    attempt_before = harness.registry.first_registration_ledger().get(
        PAIRING_ID
    )

    status, _hello = harness.endpoint_post(
        "/v2/pairing/hello",
        {
            "schema": "gh.pair.hello/1",
            "pairing_id": PAIRING_ID,
            "pairing_epoch": 1,
            "hardware_id": HARDWARE_ID,
            "model": "greenhouse-wifi-c6",
            "fw_version": "F1.0-RC2-N3W",
            "node_nonce": b64(bytes([0x31]) * 32),
            "capabilities": ["simple-setup-secret"],
            "sent_at_ms": 1,
        },
    )
    assert status == HTTPStatus.OK

    status, offer = harness.endpoint_post(
        "/v2/pairing/begin",
        {
            "schema": "gh.pair.simple-begin/1",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "node_nonce": b64(bytes([0x21]) * 16),
        },
    )
    assert status == HTTPStatus.OK

    status, _failed = harness.endpoint_post(
        (
            f"/v2/pairing/sessions/"
            f"{offer['session_id']}/establish"
        ),
        {
            "schema": "gh.pair.simple-establish/1",
            "node_proof": b64(bytes([0xFF]) * 32),
        },
    )

    attempt_after = harness.registry.first_registration_ledger().get(
        PAIRING_ID
    )
    assert status == HTTPStatus.FORBIDDEN
    assert harness.controller.status()["pairing_window_state"] == "OPEN"
    assert tcp_listener_open(harness.http_port) is True
    assert attempt_after.expires_at == attempt_before.expires_at
    assert attempt_after.state is FirstRegistrationAttemptState.ACTIVE


def test_second_node_is_busy_without_replacing_first_transaction(
    harness: R8Harness,
) -> None:
    node_a = SimulatedNode(PhoneLikeBrowser())
    open_first_registration(harness, node_a)
    first = harness.registry.first_registration_ledger().get(PAIRING_ID)

    node_b = SimulatedNode(
        PhoneLikeBrowser(),
        hardware_id=HARDWARE_ID_B,
        pairing_id=PAIRING_ID_B,
        setup_secret=SETUP_SECRET_B,
    )
    candidate = RegistrationCandidate(
        manager_id="manager_lab_01",
        system_id="lab",
        system_id_hint="LAB01",
        host=T1_IP,
        bootstrap_tls_sha256=TLS_FINGERPRINT,
    )

    with pytest.raises(RuntimeError, match="registration_busy"):
        harness.bootstrap.handle_confirm(
            node_b.bootstrap_document(candidate),
            source_ip=SOURCE_IP,
        )

    unchanged = harness.registry.first_registration_ledger().get(PAIRING_ID)
    assert unchanged.expires_at == first.expires_at
    assert unchanged.state is FirstRegistrationAttemptState.ACTIVE
    assert harness.controller.status()["pairing_window_state"] == "OPEN"
    assert len(harness.compositions) == 1


def test_phone_multi_candidate_and_recovery_never_auto_bootstrap() -> None:
    browser = PhoneLikeBrowser()
    node = SimulatedNode(browser)

    candidates = (
        RegistrationCandidate(
            manager_id="manager_lab_01",
            system_id="lab",
            system_id_hint="LAB01",
            host="192.0.2.10",
            bootstrap_tls_sha256="a" * 64,
        ),
        RegistrationCandidate(
            manager_id="manager_lab_02",
            system_id="lab2",
            system_id_hint="LAB02",
            host="192.0.2.11",
            bootstrap_tls_sha256="b" * 64,
        ),
    )
    node.set_candidates(candidates)

    assert node.bootstrap_count == 0
    assert set(node.private_candidates) == {"c0", "c1"}
    assert node.select("stale") is None
    assert node.bootstrap_count == 0

    selected = node.select("c1")
    assert selected is candidates[1]
    assert node.bootstrap_count == 0

    empty_browser = PhoneLikeBrowser()
    empty = SimulatedNode(empty_browser)
    empty.set_candidates(())
    assert empty.private_candidates == {}
    assert empty.bootstrap_count == 0

    assert_browser_private_values_absent(browser)
