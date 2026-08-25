from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src" / "greenhouse_manager" / "runtime"
FIRMWARE = (
    ROOT.parents[1]
    / "firmware"
    / "esphome_rc"
    / "components"
    / "greenhouse_n3w_core"
)


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_device_pairing_id_is_random_transaction_state_not_epoch_derived() -> None:
    client = source(FIRMWARE / "n3w_simple_pairing_client.cpp")
    header = source(FIRMWARE / "n3w_simple_pairing_client.h")

    assert "pairing_id_from_secret" not in client
    assert 'root["pairing_epoch"]' not in client
    assert "NvsPairingEpochStore" not in header
    assert "PendingPairingIntent" in header
    assert "fill_(pairing_random.data(), pairing_random.size())" in client


def test_product_pairing_does_not_derive_security_generations_from_attempts() -> None:
    coordinator = source(RUNTIME / "n3w_simplified_pairing.py")
    credentials = source(RUNTIME / "n3w_node_credentials.py")

    assert "credential_generation=approved.pairing_epoch" not in coordinator
    assert "stage_pairing_epoch_key" not in credentials
    assert "key_epoch != credential_generation" not in credentials


def test_pairing_attempt_metadata_is_not_in_crypto_transcript() -> None:
    crypto = source(RUNTIME / "n3w_simple_pairing_crypto.py")
    assert "pairing_attempt_no" not in crypto
    assert "pairing_epoch" not in crypto


def test_product_uses_manager_owned_local_ipc_not_filesystem_inbox() -> None:
    product = source(RUNTIME / "n3w_simplified_product_runtime.py")
    wiring = source(RUNTIME / "n3w_manager_runtime_wiring.py")

    assert "ManagerOwnedPairingSocket" in product
    assert "PrivateSetupSecretInbox(" not in product
    assert ".setup_secret_inbox.start()" not in wiring
    assert "pairing_socket.start()" in wiring


def test_legacy_pairing_epoch_helpers_are_quarantined_from_product_runtime() -> None:
    product_sources = "\n".join(
        source(path)
        for path in RUNTIME.glob("*.py")
        if path.name != "n3w_pairing_recovery.py"
    )
    assert "pairing_epoch_successor_helper" not in product_sources
    assert "stage_pairing_epoch_key" not in product_sources


def test_final_delivery_receipt_and_telemetry_replay_guards_remain() -> None:
    coordinator = source(RUNTIME / "n3w_simplified_pairing.py")
    firmware = source(FIRMWARE / "n3w_simple_pairing_client.cpp")
    canonical = source(RUNTIME / "n3w_canonical_ingress.py")

    assert "delivery_digest" in coordinator
    assert "delivery_digest" in firmware
    assert "stale_boot_session" in canonical
    assert "stale_sequence" in canonical

def test_terminal_pairing_transaction_renews_random_id_without_epoch_counter() -> None:
    client = source(FIRMWARE / "n3w_simple_pairing_client.cpp")
    header = source(FIRMWARE / "n3w_simple_pairing_client.h")
    endpoint = source(RUNTIME / "n3w_simplified_pairing_endpoint.py")

    assert "transaction_disposition" in client
    assert "HelloTransactionDisposition::TERMINAL" in client
    assert "renew_pairing_intent_()" in client
    assert "SimplePairingClientError::TRANSACTION_RENEWED" in client
    assert "next_pairing_id == pairing_id_" in client

    assert '"expired"' in endpoint
    assert '"replay_detected"' in endpoint
    assert 'return "terminal"' in endpoint

    assert "pairing_epoch + 1" not in client
    assert "NvsPairingEpochStore" not in header


def test_transient_hello_failures_do_not_renew_pairing_transaction() -> None:
    client = source(FIRMWARE / "n3w_simple_pairing_client.cpp")

    http_failure = client.index(
        "return SimplePairingClientError::HTTP_FAILED;",
        client.index("SimplePairingClient::send_hello_"),
    )
    terminal_branch = client.index(
        "HelloTransactionDisposition::TERMINAL",
        client.index("SimplePairingClient::send_hello_"),
    )
    renewal = client.index(
        "renew_pairing_intent_();",
        terminal_branch,
    )

    assert http_failure < terminal_branch < renewal

def test_registered_pairing_never_implicitly_rotates_credential_or_application_key() -> None:
    coordinator = source(RUNTIME / "n3w_simplified_pairing.py")

    guard = coordinator.index(
        'if session.inherited_node_id is not None:'
    )
    recovery_required = coordinator.index(
        '"credential_recovery_required"',
        guard,
    )
    approval = coordinator.index(
        "approved = self.approver.approve(",
        recovery_required,
    )
    staging = coordinator.index(
        "staged = self.stager.stage(",
        approval,
    )

    assert guard < recovery_required < approval < staging

    # Registered pairing must stop before the only simplified staging path.
    registered_block = coordinator[
        guard:approval
    ]
    assert "self.stager.stage(" not in registered_block
    assert "credential_generation=" not in registered_block

    # First registration remains generation 1.
    assert "credential_generation=1" in coordinator

def test_repair_authority_is_ephemeral_pair_bound_and_manager_owned() -> None:
    registration = source(RUNTIME / "registration.py")
    pairing = source(RUNTIME / "n3w_simplified_pairing.py")
    ipc = source(RUNTIME / "n3w_pairing_local_ipc.py")
    pairing_cli = source(
        ROOT
        / "src"
        / "greenhouse_manager"
        / "ops"
        / "n3w_pairing_cli.py"
    )
    registration_cli = source(
        ROOT
        / "src"
        / "greenhouse_manager"
        / "ops"
        / "registration_cli.py"
    )

    assert "class RepairIntent" in registration
    assert "self._repair_intents" in registration
    assert "repair_intent_required" in registration
    assert "repair_intent_expired" in registration
    assert "intent.pairing_id != pairing_id" in registration
    assert "repair_intent.consumed = True" in registration

    assert "repair_authorized = 1" not in registration
    assert "UPDATE registrations SET repair_authorized = 1" not in registration

    assert "def authorize_repair(" in pairing
    assert 'REPAIR_SCHEMA = "gh.pair.repair-authorize/1"' in ipc
    assert "authorize_repair_over_socket" in ipc
    assert '"authorize-repair"' in pairing_cli
    assert '"authorize-repair"' not in registration_cli

def test_registered_identity_repair_gate_survives_pending_and_terminal_states() -> None:
    registration = source(RUNTIME / "registration.py")

    guard = registration.index(
        'and current["node_id"] is not None'
    )
    required = registration.index(
        '"repair_intent_required"',
        guard,
    )
    consumed = registration.index(
        "repair_intent.consumed = True",
        required,
    )

    assert guard < required < consumed

    authorize = registration.index(
        "def authorize_repair("
    )
    pending_reject = registration.index(
        '"registered repair transaction is still pending"',
        authorize,
    )
    expired_allowed = registration.index(
        "RegistrationState.EXPIRED",
        pending_reject,
    )
    rejected_allowed = registration.index(
        "RegistrationState.REJECTED",
        pending_reject,
    )

    assert pending_reject < expired_allowed
    assert pending_reject < rejected_allowed

def test_read_only_compose_has_ephemeral_private_pairing_socket_contract() -> None:
    compose = source(
        ROOT.parents[1]
        / "infra"
        / "compose"
        / "t1"
        / "docker-compose.manager.yml"
    )
    product = source(
        RUNTIME / "n3w_simplified_product_runtime.py"
    )
    pairing_cli = source(
        ROOT
        / "src"
        / "greenhouse_manager"
        / "ops"
        / "n3w_pairing_cli.py"
    )

    assert "read_only: true" in compose
    assert "/tmp:size=16m,mode=1777" in compose
    assert (
        'GH_N3W_PAIRING_SOCKET_PATH: '
        '"/tmp/greenhouse-manager/pairing.sock"'
        in compose
    )

    assert "_ensure_private_runtime_directory(" in product
    assert "pairing_runtime_directory_parent_invalid" in product
    assert "pairing_runtime_directory_permissions_invalid" in product
    assert "stat.S_ISVTX" in product
    assert "os.chmod(path, 0o700)" in product

    assert 'os.getenv("GH_N3W_PAIRING_SOCKET_PATH")' in pairing_cli

def test_mqtt_and_application_key_lifecycles_are_operationally_decoupled() -> None:
    credentials = source(
        RUNTIME / "n3w_node_credentials.py"
    )

    application_start = credentials.index(
        "class ManagedApplicationKeyLifecycle:"
    )
    mqtt_start = credentials.index(
        "class ManagedMqttCredentialLifecycle:"
    )
    composer_start = credentials.index(
        "class ManagedProductCredentialIssuer:"
    )
    bundle_start = credentials.index(
        "def _encode_base64url",
        composer_start,
    )

    application_block = credentials[
        application_start:mqtt_start
    ]
    mqtt_block = credentials[
        mqtt_start:composer_start
    ]
    composer_block = credentials[
        composer_start:bundle_start
    ]

    assert "CredentialLifecycleStore" not in application_block
    assert "credential_generation" not in application_block
    assert "mqtt_password" not in application_block

    assert "ProductApplicationKeyAdmin" not in mqtt_block
    assert "application_key" not in mqtt_block
    assert "key_epoch" not in mqtt_block

    assert "ensure_first_registration" in composer_block
    assert "stage_initial" in composer_block
    assert "activate_initial" in composer_block

    # Pairing's composer must not expose either rotation lifecycle.
    assert "begin_rotation(" not in composer_block
    assert "commit_rotation(" not in composer_block
    assert "stage_rotation(" not in composer_block
    assert "activate_rotation(" not in composer_block

def test_product_config_has_no_filesystem_setup_secret_inbox_and_uds_is_bounded() -> None:
    config = source(
        RUNTIME / "config.py"
    )
    product = source(
        RUNTIME / "n3w_simplified_product_runtime.py"
    )
    ipc = source(
        RUNTIME / "n3w_pairing_local_ipc.py"
    )

    assert (
        "GH_N3W_SETUP_SECRET_INBOX_DIR"
        not in config
    )
    assert (
        "n3w_setup_secret_inbox_dir"
        not in config
    )

    # LAB compatibility remains explicitly quarantined.
    assert "class PrivateSetupSecretInbox" in product
    assert "LAB_ONLY" in product

    assert "MAX_REQUEST_BYTES = 4096" in ipc
    assert "MAX_RESPONSE_BYTES = 4096" in ipc
    assert "SOCKET_TIMEOUT_S = 2.0" in ipc
    assert "def _read_frame(" in ipc
    assert "response_timeout" in ipc
    assert "response_too_large" in ipc
    assert "response_frame_invalid" in ipc
    assert "request_json_invalid" in ipc

    # No single-read client response path may return.
    assert (
        "response = client.recv("
        not in ipc
    )

def test_aggregate_repair_authority_and_ipc_stream_guards() -> None:
    registration = source(
        RUNTIME / "registration.py"
    )
    ipc = source(
        RUNTIME / "n3w_pairing_local_ipc.py"
    )

    # Legacy durable bit may remain in schema compatibility code but must
    # never be read as product repair correctness authority.
    assert (
        'bool(current["repair_authorized"])'
        not in registration
    )
    assert (
        "UPDATE registrations SET repair_authorized = 1"
        not in registration
    )

    # A client request is half-closed so server framing can prove EOF.
    assert "socket.SHUT_WR" in ipc

    # Reader continues after newline rather than treating recv chunk
    # boundaries as protocol boundaries.
    assert "frame_end: int | None = None" in ipc
    assert "frame_end + 1" in ipc

    # Repair rejection must retain repair result schema.
    assert (
        "response_schema = REPAIR_RESPONSE_SCHEMA"
        in ipc
    )
    assert (
        "schema=response_schema"
        in ipc
    )
