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
    assert "STALE_BOOT" in canonical
    assert "STALE_SEQUENCE" in canonical
