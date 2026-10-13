from __future__ import annotations

import pytest

from greenhouse_manager.bootstrap.golden_master_seal import (
    SEAL_CONFIRMATION,
    GoldenMasterSealError,
    audit_golden_master_seal,
    seal_golden_master,
)


class FakeAdapters:
    def __init__(
        self,
        *,
        machine_id_populated: bool = True,
        ssh_host_private_key_count: int = 3,
        network_identity_residue: bool = False,
        journal_identity_residue: bool = False,
        random_seed_residue: bool = False,
        unknown_identity_state: bool = False,
        prepare_closes: bool = True,
    ) -> None:
        self.machine_id_populated = machine_id_populated
        self.ssh_host_private_key_count = ssh_host_private_key_count
        self.network_identity_residue = network_identity_residue
        self.journal_identity_residue = journal_identity_residue
        self.random_seed_residue = random_seed_residue
        self.unknown_identity_state = unknown_identity_state
        self.prepare_closes = prepare_closes
        self.calls: list[str] = []

    def audit_public_release(self, release_id: str):
        self.calls.append("public")
        return {
            "status": "PASS",
            "release_id": release_id,
            "exact_release_binding": True,
            "release_manifest_sha256": "a" * 64,
            "image_lock_sha256": "b" * 64,
            "public_audit_sha256": "c" * 64,
            "secret_values_included": False,
            "production_service_start": False,
        }

    def audit_instance_absence(self):
        self.calls.append("instance")
        return {
            "status": "PASS",
            "instance_material_absent": True,
            "secret_values_included": False,
            "production_service_start": False,
        }

    def audit_capture_quiescence(self):
        self.calls.append("quiescence")
        return {
            "status": "PASS",
            "product_container_count": 0,
            "product_volume_count": 0,
            "product_listener_count": 0,
            "product_firewall_active": False,
            "production_service_start": False,
        }

    def inspect_os_identity(self):
        self.calls.append("identity")
        blockers = (
            self.machine_id_populated
            or self.ssh_host_private_key_count > 0
            or self.network_identity_residue
            or self.journal_identity_residue
            or self.random_seed_residue
        )
        return {
            "status": "PASS",
            "capture_neutral": not blockers,
            "machine_id_populated": self.machine_id_populated,
            "ssh_host_private_key_count": self.ssh_host_private_key_count,
            "network_identity_residue": self.network_identity_residue,
            "journal_identity_residue": self.journal_identity_residue,
            "random_seed_residue": self.random_seed_residue,
            "unknown_identity_state": self.unknown_identity_state,
            "os_identity_audit_sha256": "d" * 64,
            "secret_values_included": False,
            "production_service_start": False,
        }

    def prepare_os_identity_for_seal(self):
        self.calls.append("prepare")
        if self.prepare_closes:
            self.machine_id_populated = False
            self.ssh_host_private_key_count = 0
            self.network_identity_residue = False
            self.journal_identity_residue = False
            self.random_seed_residue = False
        return {
            "status": "PASS",
            "capture_neutral": self.prepare_closes,
            "target_specific": True,
            "secret_values_included": False,
            "production_service_start": False,
            "rebooted": False,
        }

    def write_seal_record(self, _document):
        self.calls.append("record")
        return {
            "status": "PASS",
            "marker_last": True,
            "fsync_complete": True,
            "production_service_start": False,
        }


def test_audit_classifies_known_populated_identity_as_not_capture_ready() -> None:
    adapters = FakeAdapters()

    report = audit_golden_master_seal(adapters, release_id="release-1")

    assert report["status"] == "PASS"
    assert report["disk_capture_ready"] is False
    assert report["identity_blockers"] == [
        "machine_id_populated",
        "ssh_host_private_keys_present",
    ]


def test_audit_rejects_unknown_identity_state() -> None:
    adapters = FakeAdapters(unknown_identity_state=True)

    with pytest.raises(
        GoldenMasterSealError,
        match="os_identity:unknown_identity_state",
    ):
        audit_golden_master_seal(adapters, release_id="release-1")


def test_seal_claims_before_identity_mutation_and_writes_marker_last() -> None:
    adapters = FakeAdapters()

    def claim() -> None:
        adapters.calls.append("claim")

    report = seal_golden_master(
        adapters,
        release_id="release-1",
        confirmation=SEAL_CONFIRMATION,
        claim_authorization=claim,
    )

    assert report["disk_capture_ready"] is True
    assert report["shutdown_required"] is True
    assert report["reboot_before_capture_forbidden"] is True
    assert adapters.calls.index("claim") < adapters.calls.index("prepare")
    assert adapters.calls[-1] == "record"


def test_seal_rejects_failed_identity_neutralization_before_marker() -> None:
    adapters = FakeAdapters(prepare_closes=False)

    with pytest.raises(
        GoldenMasterSealError,
        match="post_seal_capture_readiness_invalid",
    ):
        seal_golden_master(
            adapters,
            release_id="release-1",
            confirmation=SEAL_CONFIRMATION,
            claim_authorization=lambda: adapters.calls.append("claim"),
        )

    assert "record" not in adapters.calls


def test_seal_confirmation_is_checked_before_authorization_claim() -> None:
    adapters = FakeAdapters()
    claimed: list[bool] = []

    with pytest.raises(
        GoldenMasterSealError,
        match="seal_confirmation_invalid",
    ):
        seal_golden_master(
            adapters,
            release_id="release-1",
            confirmation="NO",
            claim_authorization=lambda: claimed.append(True),
        )

    assert claimed == []
    assert adapters.calls == []
