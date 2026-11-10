from __future__ import annotations

import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_storage_image_lifecycle as storage


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = (
    ROOT
    / "infra"
    / "n3w-t1"
    / "updater-releases"
    / "storage-image-lifecycle-policy.json"
)


def policy() -> dict:
    return storage.load_policy(POLICY_PATH)


def test_repository_storage_lifecycle_policy_is_valid() -> None:
    value = policy()
    assert value["broad_docker_prune_allowed"] is False
    assert value["steady_state_internal_generation_count"] == {
        "manager": 1,
        "homeassistant": 1,
        "broker": 1,
    }
    assert value["runtime_min_free_requirement"] == {
        "state": "UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED",
        "maintenance_reserve_is_runtime_minimum": False,
    }


def test_reference_reserve_reproduces_accepted_1_5_gib_evidence() -> None:
    reserve = storage.derived_post_peak_reserve_bytes(
        filesystem_total_bytes=14_453_903_360,
        observed_mutable_allocated_bytes=174_047_232,
        policy=policy(),
    )
    assert reserve == 1_610_612_736


def test_clean_host_zero_mutable_allocation_uses_floor_or_fraction() -> None:
    reserve = storage.derived_post_peak_reserve_bytes(
        filesystem_total_bytes=8 * storage.GIB,
        observed_mutable_allocated_bytes=0,
        policy=policy(),
    )
    assert reserve == storage.GIB


def test_capacity_stops_before_staging_when_free_space_is_zero() -> None:
    report = storage.capacity_report(
        filesystem_total_bytes=16 * storage.GIB,
        free_bytes=0,
        observed_mutable_allocated_bytes=0,
        staged_transport_bytes=512 * 1024 * 1024,
        image_import_worst_case_bytes=2 * storage.GIB,
        policy=policy(),
    )
    assert report["capacity_pass"] is False
    assert report["stop_before_remote_staging"] is True
    assert report["post_peak_free_bytes"] < 0


def test_capacity_requires_transport_import_and_reserve_together() -> None:
    value = policy()
    reserve = storage.derived_post_peak_reserve_bytes(
        filesystem_total_bytes=16 * storage.GIB,
        observed_mutable_allocated_bytes=128 * 1024 * 1024,
        policy=value,
    )
    staged = 800 * 1024 * 1024
    image_import = 3 * storage.GIB
    required = staged + image_import + reserve

    passed = storage.capacity_report(
        filesystem_total_bytes=16 * storage.GIB,
        free_bytes=required,
        observed_mutable_allocated_bytes=128 * 1024 * 1024,
        staged_transport_bytes=staged,
        image_import_worst_case_bytes=image_import,
        policy=value,
    )
    assert passed["required_free_bytes"] == required
    assert passed["capacity_pass"] is True
    assert passed["stop_before_remote_staging"] is False

    stopped = storage.capacity_report(
        filesystem_total_bytes=16 * storage.GIB,
        free_bytes=required - 1,
        observed_mutable_allocated_bytes=128 * 1024 * 1024,
        staged_transport_bytes=staged,
        image_import_worst_case_bytes=image_import,
        policy=value,
    )
    assert stopped["capacity_pass"] is False
    assert stopped["stop_before_remote_staging"] is True


def test_archive_import_worst_case_sums_regular_members(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    with tarfile.open(archive, "w") as bundle:
        for name, payload in (("manifest.json", b"abc"), ("layer.tar", b"x" * 17)):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))

    assert storage.archive_import_worst_case_bytes(archive) == 20


def test_archive_import_worst_case_rejects_link_member(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as bundle:
        payload = b"abc"
        info = tarfile.TarInfo("manifest.json")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
        link = tarfile.TarInfo("bad-link")
        link.type = tarfile.SYMTYPE
        link.linkname = "manifest.json"
        bundle.addfile(link)

    with pytest.raises(
        storage.StorageLifecycleError,
        match="image_archive_special_member_forbidden",
    ):
        storage.archive_import_worst_case_bytes(archive)


def test_policy_rejects_broad_prune_enablement(tmp_path: Path) -> None:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    value["broad_docker_prune_allowed"] = True
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(storage.StorageLifecycleError, match="broad_prune_policy_invalid"):
        storage.load_policy(path)
