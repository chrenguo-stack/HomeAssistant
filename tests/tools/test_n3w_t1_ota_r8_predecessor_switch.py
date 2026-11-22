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
            staged_manifest_sha256="c" * 64,
            filesystem_id=100,
            original_data_inode=200,
            staged_data_inode=300,
            preserved_path="/var/lib/.n3w-r8-preserved-test",
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


def test_state_journal_contains_data_exchange_identities():
    backend = FakeBackend()
    result = executor.execute_switch(backend, valid_grant())
    assert result.status == "PREDECESSOR_SWITCH_PASS"
    backup_states = [
        state for state in backend.states
        if state["phase"] == contract.PHASE_BACKUP_VERIFIED
    ]
    assert len(backup_states) == 1
    backup = backup_states[0]["backup"]
    assert backup["filesystem_id"] == 100
    assert backup["original_data_inode"] == 200
    assert backup["staged_data_inode"] == 300
    assert backup["preserved_path"] == "/var/lib/.n3w-r8-preserved-test"


def test_remote_backend_uses_fresh_backup_isolated_restore_and_direct_stream():
    source = (PACKAGE / "remote_live.py").read_text()
    assert "ProtectedHaDataBackup" in source
    assert ".create(backup_fd, txid)" in source
    assert ".verify(backup_fd, txid, record)" in source
    assert "restore_to_stage(backup_fd, txid, record, preserved)" in source
    assert "exchange_directories(HA_DATA_ROOT, preserved)" in source
    assert "sys.stdin.buffer.read" in source
    assert '("docker", "load")' in source
    assert '("docker", "image", "rm", "--no-prune", image_id)' in source
    assert "docker system prune" not in source
    assert "docker image prune" not in source


def test_remote_preflight_is_readonly_no_journal_replay():
    source = (PACKAGE / "remote_live.py").read_text()
    assert '"ro,noload,nodev,nosuid,noexec"' in source
    assert "R8_PREDECESSOR_SWITCH_READONLY_PREFLIGHT_PASS" in source
    assert '"capacity_decision": "DEFER_UNTIL_POST_RELEASE_MEASUREMENT"' in source


def test_operator_readonly_path_is_memory_only(tmp_path):
    import operator as python_operator

    # The stdlib module name is already occupied, so load the package entrypoint
    # by file path under a distinct name.
    source = PACKAGE / "operator.py"
    spec = importlib.util.spec_from_file_location("r8_switch_operator", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    recovery = tmp_path / "ha-recovery.pyz"
    recovery.write_bytes(b"synthetic")
    payload = module.readonly_bootstrap(
        recovery_pyz=recovery,
        mode="preflight",
        source_head="1" * 40,
    )
    assert "os.memfd_create" in payload
    assert "unshare" not in payload
    assert "scp" not in payload
    assert "docker load" not in payload


def test_operator_execute_streams_cache_without_remote_archive_staging():
    source = (PACKAGE / "operator.py").read_text()
    assert 'with cache_path.open("rb") as source:' in source
    assert "input_file=source" in source
    assert "homeassistant-arm64.tar" not in source.split("def stage_execute_bundle", 1)[1].split("def execute_live", 1)[0]


def test_live_grant_is_not_committed_in_package():
    source = "\n".join(
        (PACKAGE / name).read_text()
        for name in ("contract.py", "executor.py", "remote_live.py", "operator.py")
    )
    assert '"schema": contract.GRANT_SCHEMA' not in source
    assert "LIVE_WRITE_AUTHORIZATION=true" not in source


def test_recovery_state_binds_exact_restore_authority():
    backend = FakeBackend()
    result = executor.execute_switch(backend, valid_grant())
    assert result.status == "PREDECESSOR_SWITCH_PASS"
    state = backend.states[-1]
    validated = contract.validate_recovery_state(
        state,
        expected_source_head="1" * 40,
    )
    assert validated["rollback_archive_sha256"] == contract.CURRENT_ROLLBACK_ARCHIVE_SHA256
    assert validated["usb_device"] == contract.BOUND_USB_DEVICE
    assert validated["predecessor_archive_sha256"] == contract.PREDECESSOR_ARCHIVE_SHA256
    assert validated["predecessor_import_worst_case_bytes"] == 2_500_000_000


@pytest.mark.parametrize(
    "field,value",
    [
        ("rollback_archive_sha256", "0" * 64),
        ("usb_device", "/dev/sdz1"),
        ("predecessor_archive_size", 1),
        ("predecessor_import_worst_case_bytes", 0),
    ],
)
def test_recovery_state_rejects_authority_drift(field, value):
    backend = FakeBackend()
    executor.execute_switch(backend, valid_grant())
    state = dict(backend.states[-1])
    state[field] = value
    with pytest.raises(
        contract.ContractError,
        match="switch_recovery_state_authority_invalid",
    ):
        contract.validate_recovery_state(
            state,
            expected_source_head="1" * 40,
        )


def test_recovery_state_requires_backup_after_backup_phase():
    backend = FakeBackend()
    executor.execute_switch(backend, valid_grant())
    state = dict(backend.states[-1])
    state["backup"] = None
    with pytest.raises(
        contract.ContractError,
        match="switch_recovery_backup_missing",
    ):
        contract.validate_recovery_state(
            state,
            expected_source_head="1" * 40,
        )


def test_remote_recovery_is_journal_driven_and_exact_only():
    source = (PACKAGE / "remote_live.py").read_text()
    assert "def recover_to_current" in source
    assert "contract.validate_recovery_state" in source
    assert "remove_predecessor_if_exact" in source
    assert "restore_original_data_from_evidence" in source
    assert "restore_current_image_if_needed" in source
    assert "PREDECESSOR_SWITCH_RECOVERED_TO_CURRENT" in source
    assert "PREDECESSOR_SWITCH_RECOVERY_REQUIRED" in source
    assert "docker system prune" not in source
    assert "docker image prune" not in source


def test_recovery_does_not_require_new_grant_or_predecessor_cache_stream():
    source = (PACKAGE / "operator.py").read_text()
    recover = source.split("def recover_live", 1)[1].split("def main", 1)[0]
    assert "grant.json" not in recover
    assert "cache_path" not in recover
    assert "input_file" not in recover
    assert "--mode recover" in recover


def test_status_and_recover_do_not_require_mac_predecessor_cache():
    source = (PACKAGE / "operator.py").read_text()
    assert 'if args.mode in {"source-check", "preflight", "execute"}' in source


def test_midstream_load_ambiguity_is_not_hidden_by_global_cleanup():
    source = (PACKAGE / "remote_live.py").read_text()
    assert "docker_load_failed" in source
    assert "predecessor_cleanup_identity_drift" in source
    assert "current_image_restore_failed" in source
    assert "RECOVERY_REQUIRED" in source
    assert "docker system prune" not in source
    assert "docker image prune" not in source
