from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from greenhouse_manager.bootstrap import device_provisioning_runtime as runtime
from greenhouse_manager.bootstrap.device_provisioning_runtime import (
    FACTORY_ACCEPTED_SCHEMA,
    DeviceProvisioningRuntimeError,
    evaluate_product_activation,
    reconcile_boot_device_provisioning,
)


class FakeAdapters:
    pass


def test_unprovisioned_boot_is_noop_and_never_resumes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        runtime,
        "inspect_device_provisioning",
        lambda *_args, **_kwargs: {"state": "UNPROVISIONED"},
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("mutation path must not run")

    monkeypatch.setattr(runtime, "resume_device_provisioning", forbidden)
    monkeypatch.setattr(runtime, "verify_device_ready", forbidden)

    report = reconcile_boot_device_provisioning(
        FakeAdapters(),
        tmp_path / "transaction",
        tmp_path / "candidate",
        release_id="release-1",
    )

    assert report["state"] == "UNPROVISIONED"
    assert report["boot_action"] == "NOOP"
    assert report["activation_eligible"] is False
    assert report["production_service_start"] is False


def test_initializing_boot_resumes_existing_transaction_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        runtime,
        "inspect_device_provisioning",
        lambda *_args, **_kwargs: {"state": "INITIALIZING"},
    )

    def resume(*_args, **_kwargs):
        calls.append("resume")
        return {
            "status": "PASS",
            "state": "DEVICE_READY",
            "release_id": "release-1",
        }

    monkeypatch.setattr(runtime, "resume_device_provisioning", resume)
    report = reconcile_boot_device_provisioning(
        FakeAdapters(),
        tmp_path / "transaction",
        tmp_path / "candidate",
        release_id="release-1",
    )

    assert calls == ["resume"]
    assert report["boot_action"] == "RESUME_EXISTING"
    assert report["activation_eligible"] is False


def test_device_ready_boot_is_verify_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        runtime,
        "inspect_device_provisioning",
        lambda *_args, **_kwargs: {"state": "DEVICE_READY"},
    )

    def verify(*_args, **_kwargs):
        calls.append("verify")
        return {
            "status": "PASS",
            "state": "DEVICE_READY",
            "release_id": "release-1",
            "host_instance_id": "host-a",
            "system_id": "system-a",
        }

    monkeypatch.setattr(runtime, "verify_device_ready", verify)
    report = reconcile_boot_device_provisioning(
        FakeAdapters(),
        tmp_path / "transaction",
        tmp_path / "candidate",
        release_id="release-1",
    )

    assert calls == ["verify"]
    assert report["boot_action"] == "VERIFY_ONLY"
    assert report["activation_eligible"] is False


def test_conflict_boot_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        runtime,
        "inspect_device_provisioning",
        lambda *_args, **_kwargs: {
            "state": "CONFLICT",
            "error_code": "host_binding_drift",
        },
    )

    with pytest.raises(
        DeviceProvisioningRuntimeError,
        match="provisioning_state_conflict:host_binding_drift",
    ):
        reconcile_boot_device_provisioning(
            FakeAdapters(),
            tmp_path / "transaction",
            tmp_path / "candidate",
            release_id="release-1",
        )


def _ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runtime,
        "verify_device_ready",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "state": "DEVICE_READY",
            "release_id": "release-1",
            "host_instance_id": "host-a",
            "system_id": "system-a",
        },
    )


def test_device_ready_without_factory_acceptance_is_not_activation_eligible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(monkeypatch)
    report = evaluate_product_activation(
        FakeAdapters(),
        tmp_path / "transaction",
        tmp_path / "candidate",
        tmp_path / "FACTORY_ACCEPTED.json",
        release_id="release-1",
    )

    assert report["state"] == "DEVICE_READY"
    assert report["factory_accepted"] is False
    assert report["activation_eligible"] is False
    assert report["reason"] == "factory_acceptance_missing"
    assert report["production_service_start"] is False


def test_exact_factory_acceptance_binding_becomes_eligible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(monkeypatch)
    marker = tmp_path / "FACTORY_ACCEPTED.json"
    marker.write_text(
        json.dumps(
            {
                "schema": FACTORY_ACCEPTED_SCHEMA,
                "status": "PASS",
                "factory_accepted": True,
                "release_id": "release-1",
                "host_instance_id": "host-a",
                "system_id": "system-a",
                "system_id_sha256": hashlib.sha256(b"system-a").hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    marker.chmod(0o600)

    report = evaluate_product_activation(
        FakeAdapters(),
        tmp_path / "transaction",
        tmp_path / "candidate",
        marker,
        release_id="release-1",
    )

    assert report["state"] == "FACTORY_ACCEPTED"
    assert report["factory_accepted"] is True
    assert report["activation_eligible"] is True
    assert report["production_service_start"] is False


def test_factory_acceptance_reader_uses_one_validated_descriptor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(monkeypatch)
    marker = tmp_path / "FACTORY_ACCEPTED.json"
    marker.write_text(
        json.dumps(
            {
                "schema": FACTORY_ACCEPTED_SCHEMA,
                "status": "PASS",
                "factory_accepted": True,
                "release_id": "release-1",
                "host_instance_id": "host-a",
                "system_id": "system-a",
                "system_id_sha256": hashlib.sha256(b"system-a").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    marker.chmod(0o600)

    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("validated pathname must not be reopened")
        ),
    )

    report = evaluate_product_activation(
        FakeAdapters(),
        tmp_path / "transaction",
        tmp_path / "candidate",
        marker,
        release_id="release-1",
    )

    assert report["activation_eligible"] is True


def test_factory_acceptance_binding_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(monkeypatch)
    marker = tmp_path / "FACTORY_ACCEPTED.json"
    marker.write_text(
        json.dumps(
            {
                "schema": FACTORY_ACCEPTED_SCHEMA,
                "status": "PASS",
                "factory_accepted": True,
                "release_id": "release-1",
                "host_instance_id": "host-b",
                "system_id": "system-a",
                "system_id_sha256": hashlib.sha256(b"system-a").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    marker.chmod(0o600)

    with pytest.raises(
        DeviceProvisioningRuntimeError,
        match="factory_acceptance_binding_invalid:host_instance_id",
    ):
        evaluate_product_activation(
            FakeAdapters(),
            tmp_path / "transaction",
            tmp_path / "candidate",
            marker,
            release_id="release-1",
        )


def test_factory_acceptance_symlink_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(monkeypatch)
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    marker = tmp_path / "FACTORY_ACCEPTED.json"
    marker.symlink_to(target)

    with pytest.raises(
        DeviceProvisioningRuntimeError,
        match="factory_acceptance_record_unsafe",
    ):
        evaluate_product_activation(
            FakeAdapters(),
            tmp_path / "transaction",
            tmp_path / "candidate",
            marker,
            release_id="release-1",
        )


def test_runtime_contract_has_no_start_authority() -> None:
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    assert "start_device_provisioning" not in source


def test_resume_unit_is_source_only_and_cannot_start_product_activation() -> None:
    root = Path(__file__).resolve().parents[4]
    unit = (
        root / "infra/n3w-t1/systemd/n3wfc4-provision-resume.service"
    ).read_text(encoding="utf-8")
    legacy_installer = (
        root / "infra/n3w-t1/install-systemd-persistence.sh"
    ).read_text(encoding="utf-8")

    assert "Type=oneshot" in unit
    assert "Requires=docker.service" in unit
    assert "After=docker.service" in unit
    assert (
        "Before=n3wfc4-broker-activation.service "
        "n3wfc4-services-activation.service"
        in unit
    )
    assert "ExecStart=/usr/local/sbin/n3w-t1-provision resume-if-needed" in unit
    assert "start n3wfc4-broker-activation.service" not in unit
    assert "start n3wfc4-services-activation.service" not in unit
    assert "n3wfc4-provision-resume.service" not in legacy_installer
