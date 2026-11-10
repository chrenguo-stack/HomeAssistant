from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_kf147_fresh_capacity as m


def manager_tar(path: Path) -> Path:
    payload = b"manager-image-layer" * 128
    with tarfile.open(path, "w") as bundle:
        info = tarfile.TarInfo("layer.tar")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    return path


def patch_candidate(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(m, "EXPECTED_MANAGER_TAR_SIZE_BYTES", path.stat().st_size)
    monkeypatch.setattr(
        m,
        "EXPECTED_MANAGER_TAR_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def storage_report(*, free: int = 6 * 1024**3) -> dict:
    return {
        "image_store_backend": "containerd",
        "image_store_root": "/var/lib/docker/containerd/daemon",
        "image_store_root_source": "embedded_containerd",
        "staging_device": 1,
        "docker_device": 1,
        "image_store_device": 1,
        "staging_free_bytes": free,
        "docker_free_bytes": free,
        "image_store_free_bytes": free,
        "staging_fstype": "ext4",
        "image_store_fstype": "ext4",
        "staging_total_bytes": 14453903360,
    }


def remote_report(*, mutable: int = 174047232) -> dict:
    units = {
        "n3wfc4-broker-activation.service": {
            "ActiveState": "active",
            "SubState": "running",
            "NRestarts": "0",
        },
        "n3wfc4-services-activation.service": {
            "ActiveState": "active",
            "SubState": "running",
            "NRestarts": "0",
        },
    }
    containers = {}
    for component in ("broker", "manager", "homeassistant"):
        containers[component] = {
            "image_ref": m.EXPECTED_LIVE_IMAGES[component],
            "image_id": m.EXPECTED_LIVE_IMAGE_IDS[component],
            "running": True,
            "restart_count": 0,
            "size_rw_bytes": 1,
        }
    return {
        "schema": "gh.n3w-t1-kf147-fresh-capacity-remote/1",
        "runtime_stable": True,
        "units": units,
        "containers": containers,
        "selected_persistent_and_maintenance_allocated_bytes": mutable - 3,
        "container_writable_layer_allocated_bytes": 3,
        "observed_mutable_allocated_bytes": mutable,
        "transaction": {
            "sha256": "1" * 64,
            "status": "ACTIVE",
            "phase": m.EXPECTED_U1_PHASE,
            "confirmation_required": None,
            "confirmation_consumed": None,
        },
        "prepare": {
            "sha256": "2" * 64,
            "status": "ACTIVE",
            "phase": m.EXPECTED_U1_PHASE,
            "confirmation_required": True,
            "confirmation_consumed": False,
            "candidate_model": m.EXPECTED_USB_MODEL,
            "candidate_capacity_bytes": m.EXPECTED_USB_CAPACITY_BYTES,
        },
    }


def policy_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "infra/n3w-t1/updater-releases/storage-image-lifecycle-policy.json"
    )


def test_live_runtime_image_ids_match_accepted_t1_evidence():
    assert m.EXPECTED_LIVE_IMAGE_IDS == {
        "manager": "sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b",
        "homeassistant": "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306",
        "broker": "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563",
    }


def test_candidate_material_uses_exact_tar_and_regular_member_sum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)

    result = m.candidate_material(path)

    assert result["manager_tar_size_bytes"] == path.stat().st_size
    assert result["staged_transport_bytes"] == path.stat().st_size
    assert result["image_import_worst_case_bytes"] == len(b"manager-image-layer" * 128)
    assert result["persistent_control_source_staged"] is False


def test_fresh_capacity_passes_with_sufficient_headroom(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)

    result = m.evaluate(
        manager_tar=path,
        storage_report=storage_report(),
        remote_report=remote_report(),
        policy_path=policy_path(),
    )

    assert result["status"] == "PASS"
    assert result["capacity"]["capacity_pass"] is True
    assert result["remote_staging"] is False
    assert result["manager_tar_streamed_to_t1"] is False
    assert result["next_action"] == "NEW_PACKAGE_MANIFEST_BINDING"


def test_last_emergency_headroom_would_stop_under_new_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)

    result = m.evaluate(
        manager_tar=path,
        storage_report=storage_report(free=592_859_136),
        remote_report=remote_report(),
        policy_path=policy_path(),
    )

    assert result["status"] == "STOP"
    assert result["capacity"]["capacity_pass"] is False
    assert result["capacity"]["stop_before_remote_staging"] is True
    assert result["next_action"] == "STOP_CAPACITY_INSUFFICIENT"


def test_live_manager_drift_stops_before_capacity_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)
    remote = remote_report()
    remote["containers"]["manager"]["image_ref"] = "local/greenhouse-manager:fresh-drift"

    with pytest.raises(m.CapacityPreflightError, match="live_image_ref_drift:manager"):
        m.evaluate(
            manager_tar=path,
            storage_report=storage_report(),
            remote_report=remote,
            policy_path=policy_path(),
        )


def test_live_image_id_drift_stops_before_capacity_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)
    remote = remote_report()
    remote["containers"]["manager"]["image_id"] = "sha256:" + "f" * 64

    with pytest.raises(m.CapacityPreflightError, match="live_image_id_drift:manager"):
        m.evaluate(
            manager_tar=path,
            storage_report=storage_report(),
            remote_report=remote,
            policy_path=policy_path(),
        )


def test_u1_confirmation_drift_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)
    remote = remote_report()
    remote["prepare"]["confirmation_consumed"] = True

    with pytest.raises(m.CapacityPreflightError, match="usb_confirmation_already_consumed"):
        m.evaluate(
            manager_tar=path,
            storage_report=storage_report(),
            remote_report=remote,
            policy_path=policy_path(),
        )


def test_split_storage_device_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)
    storage = storage_report()
    storage["image_store_device"] = 2

    with pytest.raises(
        m.CapacityPreflightError,
        match="staging_docker_image_store_filesystems_differ",
    ):
        m.evaluate(
            manager_tar=path,
            storage_report=storage,
            remote_report=remote_report(),
            policy_path=policy_path(),
        )


def test_remote_probe_contains_no_mutating_runtime_operations():
    source = m.MUTABLE_RUNTIME_PROBE
    forbidden = (
        "docker rm",
        "docker image rm",
        "docker system prune",
        "docker image prune",
        "systemctl restart",
        "systemctl start",
        "systemctl stop",
        "mkfs",
        "mount ",
        "umount",
        "dd if=",
    )
    for token in forbidden:
        assert token not in source


def test_reclaim_audit_probe_is_read_only_and_collects_reference_evidence():
    source = m.STORAGE_RECLAIM_AUDIT_PROBE
    compile(source, "<storage-reclaim-audit>", "exec")
    forbidden = (
        "docker rm",
        "docker image rm",
        "docker system prune",
        "docker image prune",
        "systemctl restart",
        "systemctl start",
        "systemctl stop",
        "apt clean",
        "journalctl --vacuum",
        "truncate",
        "unlink",
        "shutil.rmtree",
    )
    for token in forbidden:
        assert token not in source
    for required in (
        '"docker", "container", "inspect"',
        '"docker", "image", "inspect"',
        '"docker", "system", "df", "-v"',
        '"journalctl", "--disk-usage"',
        '"du", "-s", "-x", "-B1"',
    ):
        assert required in source
    assert "except subprocess.TimeoutExpired" in source
    assert '"{{.ID}}\\\\t{{.Image}}\\\\t{{.State}}"' in source
    assert '"{{.ID}}\\\\t{{.Image}}\\\\t{{.Status}}"' not in source


def test_main_writes_private_reclaim_audit_for_capacity_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = manager_tar(tmp_path / "manager.tar")
    patch_candidate(monkeypatch, path)
    audit = {
        "schema": "gh.n3w-t1-kf147-storage-reclaim-audit/1",
        "read_only": True,
        "mutation": False,
        "runtime_stable": True,
        "images": {"records": []},
        "containers": {"records": []},
    }

    def fake_probe_t1(**kwargs):
        assert kwargs["collect_reclaim_audit"] is True
        return storage_report(free=592_859_136), remote_report(), audit

    monkeypatch.setattr(m, "probe_t1", fake_probe_t1)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    evidence = tmp_path / "evidence"

    rc = m.main(
        [
            "--manager-tar",
            str(path),
            "--t1-ssh-target",
            "root@example.invalid",
            "--known-hosts",
            str(tmp_path / "known_hosts"),
            "--expected-host-key-sha256",
            "a" * 64,
            "--evidence-root",
            str(evidence),
            "--reclaim-audit-on-stop",
        ]
    )

    assert rc == 2
    assert json.loads((evidence / "storage-reclaim-audit.json").read_text()) == audit
    assert json.loads((evidence / "capacity-result.json").read_text())["status"] == "STOP"


def test_stop_result_is_public_safe_for_bad_tar(tmp_path: Path):
    path = tmp_path / "bad.tar"
    path.write_bytes(b"bad")
    with pytest.raises(m.CapacityPreflightError, match="manager_tar_size_mismatch"):
        m.candidate_material(path)


def test_mutable_runtime_probe_uses_stable_container_identity() -> None:
    source = m.MUTABLE_RUNTIME_PROBE
    assert '"id": item.get("Id")' in source
    assert '"started_at": state.get("StartedAt")' in source
    assert '"containers": stable_containers(before["containers"])' in source
    stable_block = source.split("def stable_containers", 1)[1].split("before = {", 1)[0]
    assert "size_rw_bytes" not in stable_block
