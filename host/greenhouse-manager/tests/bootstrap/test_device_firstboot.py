from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path

import pytest

from greenhouse_manager.bootstrap.device_firstboot import (
    COMPLETE_NAME,
    INITIALIZER_LOCK_NAME,
    PROVISIONING_CONFIRMATION,
    TRANSACTION_NAME,
    DeviceFirstbootError,
    inspect_device_provisioning,
    resume_device_provisioning,
    run_device_firstboot,
    start_device_provisioning,
    verify_device_ready,
)


class FakeAdapters:
    def __init__(
        self,
        *,
        release_id: str = "release-1",
        host_instance_id: str = "host-a",
        release_binding_verified: bool = True,
        fail_stage: str | None = None,
    ) -> None:
        self.release_id = release_id
        self.host_instance_id = host_instance_id
        self.release_binding_verified = release_binding_verified
        self.fail_stage = fail_stage
        self.calls: list[str] = []

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_stage == name:
            raise RuntimeError("adapter_failure")

    def preflight_fresh_host(self):
        self._call("preflight")
        return {
            "status": "PASS",
            "fresh_host_ready": True,
            "release_id": self.release_id,
            "release_binding_verified": self.release_binding_verified,
            "product_state_absent": True,
            "production_service_start": False,
        }

    def ensure_os_identity(self):
        self._call("ensure_os_identity")
        return self._os_identity()

    def verify_os_identity(self):
        self._call("verify_os_identity")
        return self._os_identity()

    def _os_identity(self):
        return {
            "status": "PASS",
            "host_instance_id": self.host_instance_id,
            "machine_id_ready": True,
            "ssh_host_identity_ready": True,
            "production_service_start": False,
            "network_operation": False,
        }

    def create_identity(self, candidate_root: Path):
        self._call("identity")
        candidate_root.mkdir(mode=0o700, exist_ok=True)
        candidate_root.chmod(0o700)
        return {
            "created": True,
            "system_id": "ghs-1111111111111111",
            "production_services_modified": False,
            "network_operation": False,
        }

    def create_state(self, _candidate_root: Path, system_id_sha256: str):
        self._call("state")
        return {
            "status": "PASS",
            "system_id_sha256": system_id_sha256,
            "fresh_product_state": True,
            "legacy_state_imported": False,
            "node_credential_count": 0,
            "production_service_start": False,
        }

    def create_broker(self, _candidate_root: Path, system_id: str):
        self._call("broker")
        return {
            "system_id": system_id,
            "service_count": 3,
            "node_credential_count": 0,
            "broker_transport_ca_separate_from_system_ca": True,
            "secret_values_included": False,
            "production_service_start": False,
            "network_operation": False,
        }

    def initialize_dynsec(self, _candidate_root: Path, _system_id: str):
        self._call("dynsec")
        return {
            "status": "PASS",
            "service_client_count": 3,
            "service_role_count": 3,
            "node_client_count": 0,
            "node_role_count": 0,
            "default_acl_exact": True,
            "admin_runtime_use_forbidden": True,
            "secret_values_included": False,
            "production_service_start": False,
        }

    def stage_instance_runtime(self, _candidate_root: Path, _system_id: str):
        self._call("instance_stage")
        return {
            "status": "PASS",
            "instance_only": True,
            "public_material_modified": False,
            "services_stopped": True,
            "production_service_start": False,
        }

    def commit_instance_candidate(self, _candidate_root: Path, _system_id: str):
        self._call("instance_commit")
        return {
            "status": "PASS",
            "instance_committed": True,
            "transaction_owned_only": True,
            "public_material_modified": False,
            "production_service_start": False,
        }

    def instance_stopped_postcheck(self, _system_id: str):
        self._call("instance_postcheck")
        return {
            "status": "PASS",
            "device_ready": True,
            "node_credential_count": 0,
            "product_listener_count": 0,
            "production_service_start": False,
        }


def start(
    adapters: FakeAdapters,
    transaction_root: Path,
    candidate_root: Path,
):
    return start_device_provisioning(
        adapters,
        transaction_root,
        candidate_root,
        release_id=adapters.release_id,
        confirmation=PROVISIONING_CONFIRMATION,
    )


def test_status_unprovisioned_is_read_only(tmp_path: Path) -> None:
    adapters = FakeAdapters()
    transaction_root = tmp_path / "firstboot"

    report = inspect_device_provisioning(
        adapters,
        transaction_root,
        tmp_path / "candidate",
        release_id="release-1",
    )

    assert report["state"] == "UNPROVISIONED"
    assert not transaction_root.exists()
    assert adapters.calls == []


def test_explicit_start_requires_exact_confirmation_before_mutation(
    tmp_path: Path,
) -> None:
    adapters = FakeAdapters()
    transaction_root = tmp_path / "firstboot"

    with pytest.raises(
        DeviceFirstbootError,
        match="provisioning_confirmation_invalid",
    ):
        start_device_provisioning(
            adapters,
            transaction_root,
            tmp_path / "candidate",
            release_id="release-1",
            confirmation="YES",
        )

    assert not transaction_root.exists()
    assert adapters.calls == []


def test_explicit_start_requires_fresh_release_binding_evidence(tmp_path: Path) -> None:
    adapters = FakeAdapters(release_binding_verified=False)

    with pytest.raises(
        DeviceFirstbootError,
        match="release_binding_verified_invalid",
    ):
        start(
            adapters,
            tmp_path / "firstboot",
            tmp_path / "candidate",
        )

    assert adapters.calls == ["preflight"]
    assert not (tmp_path / "firstboot").exists()


def test_explicit_start_runs_same_boot_and_writes_marker_last(tmp_path: Path) -> None:
    adapters = FakeAdapters()
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    report = start(adapters, transaction_root, candidate_root)

    assert report["state"] == "DEVICE_READY"
    assert report["already_complete"] is False
    assert report["production_service_start"] is False
    assert (transaction_root / TRANSACTION_NAME).is_file()
    assert (transaction_root / COMPLETE_NAME).is_file()

    complete = json.loads((transaction_root / COMPLETE_NAME).read_text(encoding="utf-8"))
    transaction = json.loads(
        (transaction_root / TRANSACTION_NAME).read_text(encoding="utf-8")
    )
    assert transaction["stage"] == "VERIFY"
    assert complete["system_id"] == "ghs-1111111111111111"
    assert transaction["system_id_sha256"] == hashlib.sha256(
        complete["system_id"].encode()
    ).hexdigest()
    assert adapters.calls == [
        "preflight",
        "ensure_os_identity",
        "identity",
        "state",
        "broker",
        "dynsec",
        "instance_stage",
        "instance_commit",
        "instance_postcheck",
    ]


def test_duplicate_start_never_creates_second_transaction(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    start(FakeAdapters(), transaction_root, candidate_root)

    second = FakeAdapters()
    with pytest.raises(DeviceFirstbootError, match="provisioning_already_started"):
        start(second, transaction_root, candidate_root)

    assert second.calls == []


def test_resume_requires_existing_transaction_and_does_not_create_one(
    tmp_path: Path,
) -> None:
    transaction_root = tmp_path / "firstboot"
    adapters = FakeAdapters()

    with pytest.raises(
        DeviceFirstbootError,
        match="firstboot_transaction_root_missing",
    ):
        resume_device_provisioning(
            adapters,
            transaction_root,
            tmp_path / "candidate",
            release_id="release-1",
        )

    assert not transaction_root.exists()
    assert adapters.calls == []


def test_interrupted_start_resumes_without_reensuring_host_identity(
    tmp_path: Path,
) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    with pytest.raises(RuntimeError, match="adapter_failure"):
        start(
            FakeAdapters(fail_stage="identity"),
            transaction_root,
            candidate_root,
        )

    transaction = json.loads(
        (transaction_root / TRANSACTION_NAME).read_text(encoding="utf-8")
    )
    assert transaction["stage"] == "OS_IDENTITY"

    resumed = FakeAdapters()
    report = resume_device_provisioning(
        resumed,
        transaction_root,
        candidate_root,
        release_id="release-1",
    )

    assert report["state"] == "DEVICE_READY"
    assert "ensure_os_identity" not in resumed.calls
    assert "preflight" not in resumed.calls
    assert resumed.calls[:2] == ["verify_os_identity", "identity"]


def test_resume_rejects_live_host_binding_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    with pytest.raises(RuntimeError, match="adapter_failure"):
        start(
            FakeAdapters(host_instance_id="host-a", fail_stage="identity"),
            transaction_root,
            candidate_root,
        )

    with pytest.raises(DeviceFirstbootError, match="host_binding_drift"):
        resume_device_provisioning(
            FakeAdapters(host_instance_id="host-b"),
            transaction_root,
            candidate_root,
            release_id="release-1",
        )


def test_device_ready_verify_rechecks_current_live_host(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    start(FakeAdapters(host_instance_id="host-a"), transaction_root, candidate_root)

    verifier = FakeAdapters(host_instance_id="host-a")
    report = verify_device_ready(
        verifier,
        transaction_root,
        candidate_root,
        release_id="release-1",
    )

    assert report["state"] == "DEVICE_READY"
    assert report["already_complete"] is True
    assert verifier.calls == ["verify_os_identity"]


def test_completed_disk_copied_to_other_host_fails_closed(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    start(FakeAdapters(host_instance_id="host-a"), transaction_root, candidate_root)

    with pytest.raises(DeviceFirstbootError, match="host_binding_drift"):
        verify_device_ready(
            FakeAdapters(host_instance_id="host-b"),
            transaction_root,
            candidate_root,
            release_id="release-1",
        )


def test_legacy_wrapper_cannot_start_unprovisioned_device(tmp_path: Path) -> None:
    adapters = FakeAdapters()
    transaction_root = tmp_path / "firstboot"

    with pytest.raises(
        DeviceFirstbootError,
        match="explicit_provisioning_start_required",
    ):
        run_device_firstboot(
            adapters,
            transaction_root,
            tmp_path / "candidate",
            release_id="release-1",
        )

    assert not transaction_root.exists()
    assert adapters.calls == []


def test_legacy_wrapper_resumes_existing_transaction(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    with pytest.raises(RuntimeError):
        start(
            FakeAdapters(fail_stage="identity"),
            transaction_root,
            candidate_root,
        )

    adapters = FakeAdapters()
    report = run_device_firstboot(
        adapters,
        transaction_root,
        candidate_root,
        release_id="release-1",
    )

    assert report["state"] == "DEVICE_READY"
    assert "ensure_os_identity" not in adapters.calls


def test_status_reports_conflict_for_completed_host_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    start(FakeAdapters(host_instance_id="host-a"), transaction_root, candidate_root)

    report = inspect_device_provisioning(
        FakeAdapters(host_instance_id="host-b"),
        transaction_root,
        candidate_root,
        release_id="release-1",
    )

    assert report["state"] == "CONFLICT"
    assert report["error_code"] == "firstboot_host_binding_drift"


def test_resume_rejects_release_binding_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    with pytest.raises(RuntimeError):
        start(
            FakeAdapters(release_id="release-1", fail_stage="identity"),
            transaction_root,
            candidate_root,
        )

    with pytest.raises(DeviceFirstbootError, match="transaction_binding_invalid"):
        resume_device_provisioning(
            FakeAdapters(release_id="release-2"),
            transaction_root,
            candidate_root,
            release_id="release-2",
        )


def test_contract_has_no_r8_authorization_or_docker_dependency() -> None:
    from greenhouse_manager.bootstrap import device_firstboot

    source = Path(device_firstboot.__file__).read_text(encoding="utf-8")
    assert "_08" not in source
    assert "AUTHORIZATION_ID" not in source
    assert "docker" not in source.lower()


def test_complete_rejects_transaction_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    start(FakeAdapters(), transaction_root, candidate_root)

    transaction_path = transaction_root / TRANSACTION_NAME
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    transaction["stage"] = "STATE"
    transaction_path.write_text(
        json.dumps(transaction, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    transaction_path.chmod(0o600)

    with pytest.raises(DeviceFirstbootError, match="complete_transaction_drift"):
        verify_device_ready(
            FakeAdapters(),
            transaction_root,
            candidate_root,
            release_id="release-1",
        )


def test_transaction_root_owner_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from greenhouse_manager.bootstrap import device_firstboot

    transaction_root = tmp_path / "firstboot"
    transaction_root.mkdir(mode=0o700)
    transaction_root.chmod(0o700)
    actual_uid = device_firstboot.os.geteuid()
    monkeypatch.setattr(device_firstboot.os, "geteuid", lambda: actual_uid + 1)

    with pytest.raises(DeviceFirstbootError, match="transaction_root_owner_invalid"):
        start(
            FakeAdapters(),
            transaction_root,
            tmp_path / "candidate",
        )


def test_atomic_write_rejects_preexisting_temp_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from greenhouse_manager.bootstrap import device_firstboot

    root = tmp_path / "firstboot"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    victim = tmp_path / "victim"
    victim.write_text("unchanged", encoding="utf-8")
    temporary = root / ".transaction.json.fixed.tmp"
    temporary.symlink_to(victim)
    monkeypatch.setattr(device_firstboot.secrets, "token_hex", lambda _length: "fixed")

    with pytest.raises(DeviceFirstbootError, match="firstboot_record_temp_exists"):
        device_firstboot._write_atomic(
            root / TRANSACTION_NAME,
            {"schema": "test"},
        )

    assert victim.read_text(encoding="utf-8") == "unchanged"


def test_start_rejects_candidate_symlink(tmp_path: Path) -> None:
    candidate_target = tmp_path / "candidate-target"
    candidate_target.mkdir(mode=0o700)
    candidate = tmp_path / "candidate"
    candidate.symlink_to(candidate_target, target_is_directory=True)

    with pytest.raises(DeviceFirstbootError, match="candidate_root_symlink_forbidden"):
        start(
            FakeAdapters(),
            tmp_path / "firstboot",
            candidate,
        )


def test_transaction_binds_candidate_root(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    first_candidate = tmp_path / "candidate-a"

    with pytest.raises(RuntimeError, match="adapter_failure"):
        start(
            FakeAdapters(fail_stage="state"),
            transaction_root,
            first_candidate,
        )

    with pytest.raises(DeviceFirstbootError, match="transaction_binding_invalid"):
        resume_device_provisioning(
            FakeAdapters(),
            transaction_root,
            tmp_path / "candidate-b",
            release_id="release-1",
        )


def test_resume_rejects_missing_persisted_host_binding(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    with pytest.raises(RuntimeError, match="adapter_failure"):
        start(
            FakeAdapters(fail_stage="identity"),
            transaction_root,
            candidate_root,
        )

    transaction_path = transaction_root / TRANSACTION_NAME
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    transaction["host_instance_id"] = None
    transaction_path.write_text(
        json.dumps(transaction, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    transaction_path.chmod(0o600)

    with pytest.raises(DeviceFirstbootError, match="host_binding_missing"):
        resume_device_provisioning(
            FakeAdapters(),
            transaction_root,
            candidate_root,
            release_id="release-1",
        )


def test_complete_rejects_system_hash_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    start(FakeAdapters(), transaction_root, candidate_root)

    transaction_path = transaction_root / TRANSACTION_NAME
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    transaction["system_id_sha256"] = "0" * 64
    transaction_path.write_text(
        json.dumps(transaction, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    transaction_path.chmod(0o600)

    with pytest.raises(DeviceFirstbootError, match="complete_transaction_drift"):
        verify_device_ready(
            FakeAdapters(),
            transaction_root,
            candidate_root,
            release_id="release-1",
        )


def test_complete_rejects_candidate_root_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate-a"
    start(FakeAdapters(), transaction_root, candidate_root)

    with pytest.raises(DeviceFirstbootError, match="complete_transaction_drift"):
        verify_device_ready(
            FakeAdapters(),
            transaction_root,
            tmp_path / "candidate-b",
            release_id="release-1",
        )


def test_new_transaction_claim_rejects_preexisting_claim_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from greenhouse_manager.bootstrap import device_firstboot

    transaction_root = tmp_path / "firstboot"
    transaction_root.mkdir(mode=0o700)
    transaction_root.chmod(0o700)
    victim = tmp_path / "victim"
    victim.write_text("unchanged", encoding="utf-8")
    claim = transaction_root / ".transaction.json.fixed.claim"
    claim.symlink_to(victim)
    monkeypatch.setattr(device_firstboot.secrets, "token_hex", lambda _length: "fixed")

    with pytest.raises(DeviceFirstbootError, match="firstboot_record_temp_exists"):
        start(
            FakeAdapters(),
            transaction_root,
            tmp_path / "candidate",
        )

    assert victim.read_text(encoding="utf-8") == "unchanged"
    assert not (transaction_root / TRANSACTION_NAME).exists()

def test_start_holds_exclusive_lock_during_transaction(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    class ConcurrentAdapters(FakeAdapters):
        def ensure_os_identity(self):
            concurrent = FakeAdapters()
            with pytest.raises(
                DeviceFirstbootError, match="initializer_already_running"
            ):
                resume_device_provisioning(
                    concurrent,
                    transaction_root,
                    candidate_root,
                    release_id="release-1",
                )
            assert concurrent.calls == []
            return super().ensure_os_identity()

    report = start(ConcurrentAdapters(), transaction_root, candidate_root)
    assert report["state"] == "DEVICE_READY"


def test_simultaneous_resume_cannot_advance_existing_transaction(
    tmp_path: Path,
) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    with pytest.raises(RuntimeError, match="adapter_failure"):
        start(FakeAdapters(fail_stage="identity"), transaction_root, candidate_root)

    lock_path = transaction_root / INITIALIZER_LOCK_NAME
    before = (transaction_root / TRANSACTION_NAME).read_bytes()
    with lock_path.open("rb") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        concurrent = FakeAdapters()
        with pytest.raises(DeviceFirstbootError, match="initializer_already_running"):
            resume_device_provisioning(
                concurrent,
                transaction_root,
                candidate_root,
                release_id="release-1",
            )
        assert concurrent.calls == []
        assert (transaction_root / TRANSACTION_NAME).read_bytes() == before

    resumed = FakeAdapters()
    report = resume_device_provisioning(
        resumed, transaction_root, candidate_root, release_id="release-1"
    )
    assert report["state"] == "DEVICE_READY"


def test_failed_initializer_releases_lock_without_losing_transaction(
    tmp_path: Path,
) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    with pytest.raises(RuntimeError, match="adapter_failure"):
        start(FakeAdapters(fail_stage="state"), transaction_root, candidate_root)

    assert (transaction_root / INITIALIZER_LOCK_NAME).is_file()
    resumed = FakeAdapters()
    report = resume_device_provisioning(
        resumed, transaction_root, candidate_root, release_id="release-1"
    )
    assert report["state"] == "DEVICE_READY"
    assert "identity" not in resumed.calls


def test_initializer_lock_symlink_is_rejected(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    transaction_root.mkdir(mode=0o700)
    candidate_root = tmp_path / "candidate"
    victim = tmp_path / "victim"
    victim.write_text("untouched", encoding="utf-8")
    (transaction_root / INITIALIZER_LOCK_NAME).symlink_to(victim)

    with pytest.raises((DeviceFirstbootError, OSError)):
        start(FakeAdapters(), transaction_root, candidate_root)
    assert not (transaction_root / TRANSACTION_NAME).exists()
    assert victim.read_text(encoding="utf-8") == "untouched"
