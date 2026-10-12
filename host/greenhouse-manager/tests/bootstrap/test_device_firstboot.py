from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from greenhouse_manager.bootstrap.device_firstboot import (
    COMPLETE_NAME,
    TRANSACTION_NAME,
    DeviceFirstbootError,
    run_device_firstboot,
)


class FakeAdapters:
    def __init__(
        self,
        *,
        release_id: str = "release-1",
        host_instance_id: str = "host-a",
        fail_stage: str | None = None,
    ) -> None:
        self.release_id = release_id
        self.host_instance_id = host_instance_id
        self.fail_stage = fail_stage
        self.calls: list[str] = []

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_stage == name:
            raise RuntimeError("adapter_failure")

    def preflight_clone(self):
        self._call("preflight")
        return {
            "status": "PASS",
            "sealed_image": True,
            "release_id": self.release_id,
            "production_service_start": False,
        }

    def ensure_os_identity(self):
        self._call("os_identity")
        return {
            "status": "PASS",
            "host_instance_id": self.host_instance_id,
            "machine_id_ready": True,
            "ssh_host_identity_ready": True,
            "production_service_start": False,
        }

    def create_identity(self, _candidate_root: Path):
        self._call("identity")
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


def test_firstboot_persists_marker_last_and_is_idempotent(tmp_path: Path) -> None:
    adapters = FakeAdapters()
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"

    first = run_device_firstboot(
        adapters,
        transaction_root,
        candidate_root,
        release_id="release-1",
    )
    assert first["status"] == "PASS"
    assert first["already_complete"] is False
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

    second_adapters = FakeAdapters(fail_stage="preflight")
    second = run_device_firstboot(
        second_adapters,
        transaction_root,
        candidate_root,
        release_id="release-1",
    )
    assert second["already_complete"] is True
    assert second_adapters.calls == []


def test_firstboot_resume_rejects_host_binding_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    first = FakeAdapters(host_instance_id="host-a", fail_stage="identity")

    with pytest.raises(RuntimeError, match="adapter_failure"):
        run_device_firstboot(
            first,
            transaction_root,
            candidate_root,
            release_id="release-1",
        )

    transaction = json.loads(
        (transaction_root / TRANSACTION_NAME).read_text(encoding="utf-8")
    )
    assert transaction["stage"] == "OS_IDENTITY"
    assert transaction["host_instance_id"] == "host-a"

    with pytest.raises(DeviceFirstbootError, match="host_binding_drift"):
        run_device_firstboot(
            FakeAdapters(host_instance_id="host-b"),
            transaction_root,
            candidate_root,
            release_id="release-1",
        )


def test_firstboot_rejects_release_binding_drift(tmp_path: Path) -> None:
    transaction_root = tmp_path / "firstboot"
    candidate_root = tmp_path / "candidate"
    adapters = FakeAdapters(fail_stage="identity")

    with pytest.raises(RuntimeError):
        run_device_firstboot(
            adapters,
            transaction_root,
            candidate_root,
            release_id="release-1",
        )

    with pytest.raises(DeviceFirstbootError, match="transaction_binding_invalid"):
        run_device_firstboot(
            FakeAdapters(release_id="release-2"),
            transaction_root,
            candidate_root,
            release_id="release-2",
        )


def test_firstboot_contract_has_no_r8_authorization_dependency() -> None:
    from greenhouse_manager.bootstrap import device_firstboot

    source = Path(device_firstboot.__file__).read_text(encoding="utf-8")
    assert "_08" not in source
    assert "AUTHORIZATION_ID" not in source
    assert "docker" not in source.lower()
