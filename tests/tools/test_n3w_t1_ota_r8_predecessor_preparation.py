from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "host/greenhouse-manager/src"))

import n3w_t1_core_updater_ha_recovery_startup as startup
from greenhouse_manager.runtime.t1_ota_manager import (
    OtaControlError,
    T1OtaManager,
    normalize_approved_manifest,
)
from n3w_t1_core_updater_ha_ipc import (
    APPROVED_MANIFEST,
    APPROVED_MANIFEST_SCHEMA,
    RELEASE_PIN,
    RELEASE_PIN_SCHEMA,
    candidate_admission,
)
from n3w_t1_core_updater_ha_usb_state import U1, HaUsbStateStore
from n3w_t1_core_updater_v2_common import ComponentTarget, canonical, sha256_bytes

TARGET_PATH = REPO / "infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation.json"
REVIEW_PATH = REPO / "infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation-compatibility-review.json"

RELEASE = "homeassistant-r8-predecessor-2026.10.0"
CURRENT = "local/n3w-homeassistant:2026.10.4-5881590f"
TARGET = "local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET_IMAGE_ID = "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879"
TARGET_ARCHIVE_SIZE = 2448553472
TARGET_ARCHIVE_SHA256 = "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663"
ARTIFACT_ID = 13070404405
ARTIFACT_DIGEST_SHA256 = "99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93"
ARTIFACT_NAME = "n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64"
REVIEW_CANONICAL_SHA256 = "69c1d8add67d445917738873329caee11f35ad5707e9ecdb5edab24c86b48cde"


def approved_envelope() -> dict:
    return {
        "schema": APPROVED_MANIFEST_SCHEMA,
        "release_identity": RELEASE,
        "version": "2026.10.0",
        "approval_status": "APPROVED",
        "signature_status": "VERIFIED",
        "validity_status": "VALID",
        "verification_status": "PASS",
        "target_archive_size_bytes": TARGET_ARCHIVE_SIZE,
        "target": json.loads(TARGET_PATH.read_text(encoding="utf-8")),
    }


def current_runtime() -> dict:
    return {
        "image_ref": CURRENT,
        "image_id": "sha256:" + "7" * 64,
        "platform": "linux/arm64",
    }


def test_exact_2026_10_0_predecessor_preparation_target_is_bound_to_archived_authority() -> None:
    target = ComponentTarget.load(TARGET_PATH)
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    review_sha = hashlib.sha256(canonical(review)).hexdigest()

    assert target.target_image_ref == TARGET
    assert target.expected_predecessor_image_ref == CURRENT
    assert target.target_archive_sha256 == TARGET_ARCHIVE_SHA256
    assert target.artifact_identity == {
        "artifact_id": ARTIFACT_ID,
        "artifact_digest_sha256": ARTIFACT_DIGEST_SHA256,
        "artifact_name": ARTIFACT_NAME,
    }
    assert target.compatibility_evidence == {
        "schema": "gh.n3w-t1-core-updater-compatibility/1",
        "mutation_profile": "IMAGE_ONLY_V1",
        "peer_contracts_compatible": True,
        "persistent_schema_compatible": True,
        "review_evidence_sha256": REVIEW_CANONICAL_SHA256,
        "predecessor_source_head": "fb7cfc857003ace3d368521d76ca2320ba399736",
        "target_source_head": "5b32e1ae82104a42f9e4e6907fe44d9172e87615",
    }
    assert review_sha == REVIEW_CANONICAL_SHA256
    assert review["reverse_preparation_source_review"] is True
    assert review["persistent_schema_compatible"] is True
    assert review["historical_2026_10_0_data_backup_required"] is False
    assert review["current_2026_10_4_protected_backup_required"] is True
    assert review["current_2026_10_4_rollback_image_required"] is True
    assert review["source_review_basis"]["canonical_sha256"] == "8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267"


def test_reverse_preparation_manifest_is_valid_but_not_exposed_as_customer_update() -> None:
    envelope = approved_envelope()
    manifest = normalize_approved_manifest(envelope)
    assert manifest.version == "2026.10.0"
    assert manifest.target_image_identity == TARGET

    class Provider:
        def get_approved_homeassistant_manifest(self):
            return envelope

    manager = T1OtaManager(installed_version="2026.10.4", manifest_provider=Provider())
    projection = manager.project()
    assert projection.status.installed_version == "2026.10.4"
    assert projection.status.latest_approved_version == "2026.10.0"
    assert projection.status.update_available is False

    payload = json.dumps({"action": "PREPARE", "target_release_id": RELEASE})
    with pytest.raises(OtaControlError, match="ota_update_not_available"):
        manager.handle_control(payload)


def test_existing_transaction_accepts_reverse_preparation_only_through_privileged_admission(tmp_path: Path) -> None:
    envelope = approved_envelope()
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    admission = candidate_admission(raw, current_runtime())
    assert admission.current_image_ref == CURRENT
    assert admission.target_image_ref == TARGET
    assert admission.target_archive_sha256 == TARGET_ARCHIVE_SHA256
    assert admission.target_archive_size == TARGET_ARCHIVE_SIZE

    store = HaUsbStateStore(tmp_path / "state")
    store.root.mkdir(mode=0o700)
    export = tmp_path / "run"
    export.mkdir()
    manifest_path = export / APPROVED_MANIFEST
    manifest_path.write_bytes(raw)
    manifest_path.chmod(0o644)
    pin = store.root / RELEASE_PIN
    pin.write_text(
        json.dumps(
            {
                "schema": RELEASE_PIN_SCHEMA,
                "manifest_sha256": sha256_bytes(raw),
                "predecessor_image_id": current_runtime()["image_id"],
                "expires_at_unix": 0x7FFFFFFF,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    pin.chmod(0o600)

    old_socket = startup.IPC_SOCKET
    try:
        startup.IPC_SOCKET = export / "ha-ota.sock"
        runtime = SimpleNamespace(_runtime=lambda _: current_runtime())
        status = startup.maintenance_submit_approved_release(
            store, runtime, action="PREPARE", release_identity=RELEASE
        )
    finally:
        startup.IPC_SOCKET = old_socket

    document = store.read()
    assert status["phase"] == "PREPARE_REQUESTED"
    assert document is not None
    assert document["phase"] == U1
    assert document["current_image_ref"] == CURRENT
    assert document["target_image_ref"] == TARGET
    assert document["target_archive_sha256"] == TARGET_ARCHIVE_SHA256
    assert document["target_archive_size"] == TARGET_ARCHIVE_SIZE
    assert document["authorization_claimed"] is False
    assert document["authorization_consumed"] is False
    assert "predecessor_start" not in document
    assert "ha_data_restore" not in document


def test_updater_owned_internal_target_spool_is_retired_but_external_source_is_preserved(tmp_path: Path) -> None:
    store = HaUsbStateStore(tmp_path / "state")
    store.root.mkdir(mode=0o700)
    document = {
        "target_archive_sha256": "a" * 64,
        "target_archive_size": 4,
    }
    owned = store.root / ("ha-target-" + document["target_archive_sha256"] + ".tar")
    owned.write_bytes(b"test")
    owned.chmod(0o600)

    assert startup._retire_owned_candidate_archive(store, document, owned) is True
    assert not owned.exists()
    # Retry after a crash between source retirement and the durable U4 write is idempotent.
    assert startup._retire_owned_candidate_archive(store, document, owned) is True

    external = tmp_path / "operator-source.tar"
    external.write_bytes(b"test")
    external.chmod(0o600)
    assert startup._retire_owned_candidate_archive(store, document, external) is False
    assert external.read_bytes() == b"test"
