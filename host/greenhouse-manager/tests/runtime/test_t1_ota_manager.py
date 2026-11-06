from __future__ import annotations

import copy
import json

import pytest

from greenhouse_manager.runtime.t1_ota_manager import (
    OtaControlError,
    OtaRuntimeSnapshot,
    T1OtaManager,
    compare_versions,
    normalize_approved_manifest,
)

TARGET = {
    "schema": "gh.n3w-t1-core-updater-target/2",
    "component": "homeassistant",
    "mutation_profile": "IMAGE_ONLY_V1",
    "target_image_ref": "local/n3w-homeassistant:2026.10.4-5881590f",
    "target_platform": "linux/arm64",
    "target_archive_sha256": (
        "eba1da958fc9c759c30d1cb34445c364"
        "e895bcd8d5e6c0d8392ab6849ece9973"
    ),
    "artifact_identity": {
        "artifact_id": 13391983948,
        "artifact_digest_sha256": (
            "df95749cec1e48796d2cf3241d197396"
            "01fe7be78c48638284d10eec786e4fd2"
        ),
        "artifact_name": (
            "n3w-t1-core-updater-homeassistant-2026.10.4-arm64-"
            "fb7cfc857003ace3d368521d76ca2320ba399736"
        ),
    },
    "expected_predecessor_image_ref": (
        "local/n3w-homeassistant:2026.10.0-0c73235a"
    ),
    "rollback_compatible": True,
    "compatibility_evidence": {
        "schema": "gh.n3w-t1-core-updater-compatibility/1",
        "mutation_profile": "IMAGE_ONLY_V1",
        "peer_contracts_compatible": True,
        "persistent_schema_compatible": True,
        "review_evidence_sha256": (
            "8b02e9bb0143fc4fc7900c4c0e4c52b"
            "27f92725cd41f1f03b82ba67ffb9e0267"
        ),
        "predecessor_source_head": (
            "5b32e1ae82104a42f9e4e6907fe44d9172e87615"
        ),
        "target_source_head": (
            "fb7cfc857003ace3d368521d76ca2320ba399736"
        ),
    },
    "a1_classification_sha256": (
        "e664ced300ea2bb743b116550b7a3e222"
        "37e7f556f54400a060eef30671d30e7"
    ),
}


def envelope() -> dict:
    return {
        "schema": "gh.n3w-t1-ota-approved-manifest/1",
        "approval_status": "APPROVED",
        "signature_status": "VERIFIED",
        "validity_status": "VALID",
        "verification_status": "PASS",
        "version": "2026.10.4",
        "release_identity": "homeassistant-2026.10.4",
        "target_archive_size_bytes": 835309535,
        "target": copy.deepcopy(TARGET),
    }


class Provider:
    def __init__(self, document: dict | None = None) -> None:
        self.document = envelope() if document is None else document

    def get_approved_homeassistant_manifest(self):
        return self.document


class Runtime:
    def __init__(self, phase: str = "DISCOVERED", progress: int | None = None) -> None:
        self.phase = phase
        self.progress = progress

    def get_homeassistant_ota_runtime_state(self) -> OtaRuntimeSnapshot:
        return OtaRuntimeSnapshot(
            phase=self.phase,
            progress_percent=self.progress,
        )


class Sink:
    def __init__(self) -> None:
        self.intents = []

    def submit_homeassistant_ota_intent(self, intent) -> None:
        self.intents.append(intent)


def manager(*, phase: str = "DISCOVERED"):
    runtime = Runtime(phase)
    sink = Sink()
    return (
        T1OtaManager(
            installed_version="2026.10.0",
            manifest_provider=Provider(),
            intent_sink=sink,
            runtime_state_provider=runtime,
        ),
        runtime,
        sink,
    )


def payload(action: str, release: str = "homeassistant-2026.10.4") -> bytes:
    return json.dumps(
        {
            "action": action,
            "target_release_id": release,
        }
    ).encode()


def test_normalizes_frozen_homeassistant_target_into_approved_projection() -> None:
    manifest = normalize_approved_manifest(envelope())

    assert manifest.manifest_schema_supported is True
    assert manifest.approval_status == "APPROVED"
    assert manifest.component == "homeassistant"
    assert manifest.version == "2026.10.4"
    assert manifest.platform == "linux/arm64"
    assert manifest.target_archive_size_bytes == 835309535
    assert manifest.target_archive_sha256 == TARGET["target_archive_sha256"]
    assert manifest.target_image_identity == TARGET["target_image_ref"]
    assert manifest.release_identity == "homeassistant-2026.10.4"
    assert manifest.verification_status == "PASS"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("schema", "unsupported", "approved_manifest_schema_unsupported"),
        ("approval_status", "PENDING", "approved_manifest_not_approved"),
        ("signature_status", "UNVERIFIED", "approved_manifest_signature_unverified"),
        ("validity_status", "EXPIRED", "approved_manifest_expired_or_invalid"),
        ("verification_status", "FAIL", "approved_manifest_verification_failed"),
    ),
)
def test_manifest_envelope_fails_closed(field: str, value: str, code: str) -> None:
    document = envelope()
    document[field] = value
    with pytest.raises(OtaControlError, match=code):
        normalize_approved_manifest(document)


def test_manifest_rejects_unknown_fields_and_wrong_target_contract() -> None:
    document = envelope()
    document["host_path"] = "/var/lib/private"
    with pytest.raises(OtaControlError, match="approved_manifest_fields_invalid"):
        normalize_approved_manifest(document)

    document = envelope()
    document["target"]["target_platform"] = "linux/amd64"
    with pytest.raises(OtaControlError, match="approved_manifest_platform_invalid"):
        normalize_approved_manifest(document)


def test_version_comparison_is_numeric_not_lexical() -> None:
    assert compare_versions("2026.10.10", "2026.10.4") == 1
    assert compare_versions("2026.10.4", "2026.10.4") == 0
    assert compare_versions("2026.9.9", "2026.10.0") == -1


def test_projection_exposes_required_public_state_only() -> None:
    ota, runtime, _sink = manager()
    runtime.phase = "TARGET_DOWNLOADING_VERIFYING"
    runtime.progress = 42

    projection = ota.project()

    assert projection.manifest is not None
    assert projection.status.installed_version == "2026.10.0"
    assert projection.status.latest_approved_version == "2026.10.4"
    assert projection.status.update_available is True
    assert projection.status.ota_phase == "TARGET_DOWNLOADING_VERIFYING"
    assert projection.status.progress_percent_or_null == 42
    assert projection.status.ready_to_install is False
    assert projection.status.in_progress is True
    assert projection.status.error_code_or_null is None


def test_invalid_manifest_projects_non_installable_safe_error() -> None:
    document = envelope()
    document["approval_status"] = "PENDING"
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(document),
    )

    projection = ota.project()

    assert projection.manifest is None
    assert projection.status.latest_approved_version == "2026.10.0"
    assert projection.status.update_available is False
    assert projection.status.ota_phase == "ERROR"
    assert projection.status.error_code_or_null == "approved_manifest_not_approved"


def test_prepare_and_install_are_distinct_and_install_requires_ready() -> None:
    ota, runtime, sink = manager()

    with pytest.raises(OtaControlError, match="ota_install_not_ready"):
        ota.handle_control(payload("INSTALL"))
    assert sink.intents == []

    prepared = ota.handle_control(payload("PREPARE"))
    assert prepared.action == "PREPARE"
    assert [item.action for item in sink.intents] == ["PREPARE"]

    runtime.phase = "READY_TO_INSTALL"
    installed = ota.handle_control(payload("INSTALL"))
    assert installed.action == "INSTALL"
    assert [item.action for item in sink.intents] == ["PREPARE", "INSTALL"]


def test_status_is_read_only_and_requires_exact_release_binding() -> None:
    ota, _runtime, sink = manager()

    status = ota.handle_control(payload("STATUS"))
    assert status.action == "STATUS"
    assert sink.intents == []

    with pytest.raises(OtaControlError, match="ota_intent_release_mismatch"):
        ota.handle_control(payload("PREPARE", "homeassistant-2026.10.5"))
    assert sink.intents == []


@pytest.mark.parametrize(
    "field",
    (
        "path",
        "block_device",
        "docker_args",
        "shell",
        "authorization_id",
        "transaction_token",
        "private_value",
    ),
)
def test_control_intent_rejects_privileged_or_private_extra_fields(field: str) -> None:
    ota, _runtime, sink = manager()
    document = {
        "action": "PREPARE",
        "target_release_id": "homeassistant-2026.10.4",
        field: "/dev/sda; docker rm -f homeassistant",
    }

    with pytest.raises(OtaControlError, match="ota_intent_fields_invalid"):
        ota.handle_control(json.dumps(document).encode())
    assert sink.intents == []


def test_control_intent_rejects_duplicate_json_fields() -> None:
    ota, _runtime, sink = manager()
    duplicate = (
        b'{"action":"PREPARE","action":"INSTALL",'
        b'"target_release_id":"homeassistant-2026.10.4"}'
    )

    with pytest.raises(OtaControlError, match="ota_intent_duplicate_field"):
        ota.handle_control(duplicate)
    assert sink.intents == []
