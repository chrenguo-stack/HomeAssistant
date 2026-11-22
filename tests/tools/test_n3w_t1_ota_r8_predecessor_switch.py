from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PACKAGE = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8_predecessor_switch"
)
sys.path.insert(0, str(PACKAGE))

import contract
import executor


def valid_grant(**updates):
    value = {
        "schema": contract.GRANT_SCHEMA,
        "authorization_id": "N3W_T1_R8_PREDECESSOR_SWITCH_20261122_01",
        "expires_at_unix": 2000000000,
        "source_head": "1" * 40,
        "ssh_host_key_sha256": contract.EXPECTED_HOST_KEY_SHA256,
        "current_image": contract.CURRENT_IMAGE,
        "current_image_id": contract.CURRENT_IMAGE_ID,
        "rollback_transaction_sha256": contract.CURRENT_ROLLBACK_TX_SHA256,
        "rollback_archive_sha256": contract.CURRENT_ROLLBACK_ARCHIVE_SHA256,
        "rollback_archive_size": contract.CURRENT_ROLLBACK_ARCHIVE_SIZE,
        "usb_device": contract.BOUND_USB_DEVICE,
        "usb_major_minor": contract.BOUND_USB_MAJOR_MINOR,
        "predecessor_image": contract.PREDECESSOR_IMAGE,
        "predecessor_image_id": contract.PREDECESSOR_IMAGE_ID,
        "predecessor_archive_sha256": contract.PREDECESSOR_ARCHIVE_SHA256,
        "predecessor_archive_size": contract.PREDECESSOR_ARCHIVE_SIZE,
        "predecessor_import_worst_case_bytes": 2_500_000_000,
    }
    value.update(updates)
    return contract.SwitchGrant.from_document(value)


class FakeBackend:
    def __init__(
        self,
        *,
        available=5_000_000_000,
        fail_at=None,
        rollback_fails=False,
    ):
        self.available = available
        self.fail_at = fail_at
        self.rollback_fails = rollback_fails
        self.calls = []
        self.states = []

    def _call(self, name):
        self.calls.append(name)
        if self.fail_at == name:
            raise RuntimeError(name + "_failed")

    def verify_preflight(self, grant):
        self._call("verify_preflight")

    def write_state(self, document):
        self.states.append(document)
        self.calls.append("write_state:" + document["phase"])

    def quiesce_application(self, grant):
        self._call("quiesce_application")

    def create_fresh_backup_and_stage(self, grant, txid):
        self._call("create_fresh_backup_and_stage")
        return executor.BackupEvidence(
            archive_sha256="a" * 64,
            archive_size_bytes=123,
            manifest_sha256="b" * 64,
            staged_data_sha256="c" * 64,
        )

    def exchange_data_root(self, grant, txid, backup):
        self._call("exchange_data_root")

    def release_current_image(self, grant, txid):
        self._call("release_current_image")

    def measure_post_release_available_bytes(self, grant):
        self._call("measure_post_release_available_bytes")
        return self.available

    def load_predecessor_from_stream(self, grant, txid):
        self._call("load_predecessor_from_stream")

    def switch_to_predecessor_binding(self, grant, txid):
        self._call("switch_to_predecessor_binding")

    def start_and_verify_predecessor(self, grant, txid):
        self._call("start_and_verify_predecessor")

    def rollback_to_current(self, grant, txid, *, phase, backup):
        self.calls.append("rollback_to_current:" + phase)
        if self.rollback_fails:
            raise RuntimeError("rollback_failed")


def test_capacity_decision_is_post_release_and_keeps_reserve():
    report = contract.post_release_capacity(
        available_bytes=4_500_000_000,
        import_bytes=2_500_000_000,
    )
    assert report["decision_point"] == "AFTER_RELEASE_BEFORE_NEXT_IMPORT"
    assert report["required_bytes"] == (
        2_500_000_000 + contract.POST_PEAK_RESERVE_BYTES
    )
    assert report["capacity_pass"] is True


def test_capacity_failure_is_exact():
    required = 2_500_000_000 + contract.POST_PEAK_RESERVE_BYTES
    assert contract.post_release_capacity(
        available_bytes=required - 1,
        import_bytes=2_500_000_000,
    )["capacity_pass"] is False
    assert contract.post_release_capacity(
        available_bytes=required,
        import_bytes=2_500_000_000,
    )["capacity_pass"] is True


def test_success_sequence_is_single_image_ordered():
    backend = FakeBackend()
    result = executor.execute_switch(backend, valid_grant())
    assert result.status == "PREDECESSOR_SWITCH_PASS"
    assert result.phase == contract.PHASE_PREDECESSOR_HEALTHY
    assert backend.calls.index(
        "write_state:" + contract.PHASE_CURRENT_RELEASE_INTENT
    ) < backend.calls.index("release_current_image")
    assert backend.calls.index("release_current_image") < backend.calls.index(
        "measure_post_release_available_bytes"
    )
    assert backend.calls.index(
        "measure_post_release_available_bytes"
    ) < backend.calls.index("load_predecessor_from_stream")
    assert backend.calls.index(
        "create_fresh_backup_and_stage"
    ) < backend.calls.index("release_current_image")
    assert backend.calls.index(
        "exchange_data_root"
    ) < backend.calls.index("release_current_image")
    assert not any(call.startswith("rollback_to_current") for call in backend.calls)


def test_post_release_capacity_failure_rolls_back_without_import():
    required = 2_500_000_000 + contract.POST_PEAK_RESERVE_BYTES
    backend = FakeBackend(available=required - 1)
    result = executor.execute_switch(backend, valid_grant())
    assert result.status == "PREDECESSOR_SWITCH_ROLLED_BACK"
    assert result.phase == contract.PHASE_ROLLED_BACK
    assert "load_predecessor_from_stream" not in backend.calls
    assert (
        "rollback_to_current:" + contract.PHASE_CURRENT_RELEASED
        in backend.calls
    )


@pytest.mark.parametrize(
    "fail_at, expected_phase",
    [
        ("quiesce_application", contract.PHASE_PREFLIGHT),
        ("create_fresh_backup_and_stage", contract.PHASE_QUIESCED),
        ("exchange_data_root", contract.PHASE_BACKUP_VERIFIED),
        ("release_current_image", contract.PHASE_CURRENT_RELEASE_INTENT),
        ("load_predecessor_from_stream", contract.PHASE_CAPACITY_PASSED),
        ("switch_to_predecessor_binding", contract.PHASE_PREDECESSOR_LOADED),
        ("start_and_verify_predecessor", contract.PHASE_BINDING_SWITCHED),
    ],
)
def test_each_mutation_failure_enters_rollback(fail_at, expected_phase):
    backend = FakeBackend(fail_at=fail_at)
    result = executor.execute_switch(backend, valid_grant())
    assert result.status == "PREDECESSOR_SWITCH_ROLLED_BACK"
    assert "rollback_to_current:" + expected_phase in backend.calls


def test_rollback_failure_is_recovery_required_not_false_pass():
    backend = FakeBackend(
        fail_at="load_predecessor_from_stream",
        rollback_fails=True,
    )
    result = executor.execute_switch(backend, valid_grant())
    assert result.status == "PREDECESSOR_SWITCH_RECOVERY_REQUIRED"
    assert result.phase == contract.PHASE_RECOVERY_REQUIRED
    assert "rollback=rollback_failed" in result.failure


def test_grant_binds_exact_images_and_usb():
    grant = valid_grant()
    assert grant.current_image == contract.CURRENT_IMAGE
    assert grant.current_image_id == contract.CURRENT_IMAGE_ID
    assert grant.predecessor_image == contract.PREDECESSOR_IMAGE
    assert grant.predecessor_image_id == contract.PREDECESSOR_IMAGE_ID
    assert grant.usb_device == "/dev/sda1"
    with pytest.raises(contract.ContractError, match="switch_grant_binding_invalid"):
        valid_grant(current_image_id="sha256:" + "0" * 64)


def test_compatibility_authority_accepts_only_exact_10_0_to_10_4_contract():
    review = {
        "schema": "gh.n3w-t1-core-updater-homeassistant-compatibility-review/1",
        "component": "homeassistant",
        "mutation_profile": "IMAGE_ONLY_V1",
        "predecessor": {
            "version": "2026.10.0",
            "image": contract.PREDECESSOR_IMAGE,
        },
        "candidate": {"version": "2026.10.4"},
        "storage_contract": {
            "core.config_entries": {
                "predecessor": {"version": 1, "minor_version": 5},
                "candidate": {"version": 1, "minor_version": 5},
            },
            "core.device_registry": {
                "predecessor": {"version": 3, "minor_version": 4},
                "candidate": {"version": 3, "minor_version": 4},
            },
            "core.entity_registry": {
                "predecessor": {"version": 1, "minor_version": 23},
                "candidate": {"version": 1, "minor_version": 23},
            },
        },
        "peer_contracts_compatible": True,
        "persistent_schema_compatible": True,
        "rollback_compatible_source_review": True,
    }
    target = {
        "schema": "gh.n3w-t1-core-updater-target/2",
        "component": "homeassistant",
        "mutation_profile": "IMAGE_ONLY_V1",
        "target_image_ref": contract.CURRENT_IMAGE,
        "expected_predecessor_image_ref": contract.PREDECESSOR_IMAGE,
        "rollback_compatible": True,
        "compatibility_evidence": {
            "persistent_schema_compatible": True,
            "peer_contracts_compatible": True,
            "review_evidence_sha256": contract.COMPATIBILITY_REVIEW_SHA256,
        },
    }
    contract.validate_compatibility_authority(review, target)
    review["storage_contract"]["core.entity_registry"]["candidate"][
        "minor_version"
    ] = 24
    with pytest.raises(
        contract.ContractError,
        match="compatibility_storage_contract_invalid",
    ):
        contract.validate_compatibility_authority(review, target)


def test_no_global_prune_or_two_image_capacity_formula_in_source():
    source = (
        (PACKAGE / "contract.py").read_text()
        + (PACKAGE / "executor.py").read_text()
    )
    assert "docker system prune" not in source
    assert "docker image prune" not in source
    assert "install_required_bytes + recovery_required_bytes" not in source
    assert "AFTER_RELEASE_BEFORE_NEXT_IMPORT" in source
