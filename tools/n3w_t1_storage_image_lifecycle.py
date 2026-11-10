#!/usr/bin/env python3
from __future__ import annotations

import json
import tarfile
from pathlib import Path
from typing import Any

POLICY_SCHEMA = "gh.n3w-t1-storage-image-lifecycle-policy/1"
COMPONENTS = ("manager", "homeassistant", "broker")
GIB = 1024 * 1024 * 1024


class StorageLifecycleError(RuntimeError):
    pass


def _positive_int(value: Any, reason: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise StorageLifecycleError(reason)
    return value


def _nonnegative_int(value: Any, reason: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StorageLifecycleError(reason)
    return value


def load_policy(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise StorageLifecycleError("policy_file_invalid")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StorageLifecycleError("policy_json_invalid") from error
    if not isinstance(policy, dict) or policy.get("schema") != POLICY_SCHEMA:
        raise StorageLifecycleError("policy_schema_invalid")
    if policy.get("target_hardware_class") != "16GB-class T1":
        raise StorageLifecycleError("policy_hardware_class_invalid")
    if policy.get("broad_docker_prune_allowed") is not False:
        raise StorageLifecycleError("broad_prune_policy_invalid")
    generations = policy.get("steady_state_internal_generation_count")
    if generations != {name: 1 for name in COMPONENTS}:
        raise StorageLifecycleError("steady_state_generation_policy_invalid")

    capacity = policy.get("pre_transfer_capacity")
    if not isinstance(capacity, dict):
        raise StorageLifecycleError("capacity_policy_invalid")
    if (
        capacity.get("fresh_probe_required") is not True
        or capacity.get("same_device_staging_docker_image_store_required") is not True
        or capacity.get("staged_transport_bytes_must_be_exact") is not True
        or capacity.get("stop_before_remote_staging_on_failure") is not True
        or capacity.get("required_formula")
        != (
            "free_bytes >= staged_transport_bytes + "
            "image_import_worst_case_bytes + derived_post_peak_reserve_bytes"
        )
        or capacity.get("image_import_worst_case_source")
        != "sum_regular_file_member_sizes_of_exact_docker_save_archive"
    ):
        raise StorageLifecycleError("capacity_policy_contract_invalid")
    for key in (
        "absolute_floor_bytes",
        "filesystem_fraction_numerator",
        "filesystem_fraction_denominator",
        "observed_mutable_multiplier",
        "round_up_quantum_bytes",
        "evidence_bound_reference_reserve_bytes",
    ):
        _positive_int(capacity.get(key), f"capacity_policy_{key}_invalid")
    if capacity["filesystem_fraction_numerator"] >= capacity["filesystem_fraction_denominator"]:
        raise StorageLifecycleError("capacity_fraction_invalid")

    runtime = policy.get("runtime_min_free_requirement")
    if runtime != {
        "state": "UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED",
        "maintenance_reserve_is_runtime_minimum": False,
    }:
        raise StorageLifecycleError("runtime_minimum_boundary_invalid")

    cleanup = policy.get("cleanup")
    if not isinstance(cleanup, dict) or cleanup != {
        "exact_image_id_only": True,
        "require_no_container_reference": True,
        "require_target_and_peer_health_before_and_after": True,
        "retain_transaction_metadata": True,
        "wildcard_delete_allowed": False,
        "delete_by_age_allowed": False,
        "docker_system_prune_allowed": False,
        "docker_image_prune_all_allowed": False,
    }:
        raise StorageLifecycleError("cleanup_policy_invalid")
    return policy


def round_up(value: int, quantum: int) -> int:
    _positive_int(value, "round_value_invalid")
    _positive_int(quantum, "round_quantum_invalid")
    return ((value + quantum - 1) // quantum) * quantum


def derived_post_peak_reserve_bytes(
    *,
    filesystem_total_bytes: int,
    observed_mutable_allocated_bytes: int,
    policy: dict[str, Any],
) -> int:
    total = _positive_int(filesystem_total_bytes, "filesystem_total_bytes_invalid")
    mutable = _nonnegative_int(
        observed_mutable_allocated_bytes,
        "observed_mutable_allocated_bytes_invalid",
    )
    capacity = policy["pre_transfer_capacity"]
    fraction = (
        total * capacity["filesystem_fraction_numerator"]
        // capacity["filesystem_fraction_denominator"]
    )
    raw = max(
        capacity["absolute_floor_bytes"],
        fraction,
        mutable * capacity["observed_mutable_multiplier"],
    )
    return round_up(raw, capacity["round_up_quantum_bytes"])


def archive_import_worst_case_bytes(path: Path) -> int:
    if path.is_symlink() or not path.is_file():
        raise StorageLifecycleError("image_archive_invalid")
    try:
        with tarfile.open(path, "r:*") as bundle:
            members = bundle.getmembers()
    except (tarfile.TarError, OSError) as error:
        raise StorageLifecycleError("image_archive_invalid") from error
    if not members:
        raise StorageLifecycleError("image_archive_empty")
    total = 0
    for member in members:
        if member.isfile():
            if member.size < 0:
                raise StorageLifecycleError("image_archive_member_size_invalid")
            total += member.size
        elif member.issym() or member.islnk() or member.isdev():
            raise StorageLifecycleError("image_archive_special_member_forbidden")
    if total <= 0:
        raise StorageLifecycleError("image_archive_regular_bytes_missing")
    return total


def validate_storage_topology(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise StorageLifecycleError("storage_topology_invalid")
    backend = report.get("image_store_backend")
    if backend not in {"classic", "containerd"}:
        raise StorageLifecycleError("image_store_backend_unresolved")
    if report.get("staging_fstype") in {"tmpfs", "ramfs"}:
        raise StorageLifecycleError("staging_memory_filesystem_forbidden")
    if report.get("image_store_fstype") in {"tmpfs", "ramfs"}:
        raise StorageLifecycleError("image_store_memory_filesystem_forbidden")
    devices = (
        report.get("staging_device"),
        report.get("docker_device"),
        report.get("image_store_device"),
    )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in devices
    ):
        raise StorageLifecycleError("storage_device_identity_invalid")
    if len(set(devices)) != 1:
        raise StorageLifecycleError("staging_docker_image_store_filesystems_differ")
    image_store_root = report.get("image_store_root")
    if not isinstance(image_store_root, str) or not image_store_root.startswith("/"):
        raise StorageLifecycleError("image_store_root_unresolved")
    root_source = report.get("image_store_root_source")
    if backend == "classic":
        if root_source != "docker_root":
            raise StorageLifecycleError("classic_image_store_authority_invalid")
    elif root_source not in {
        "embedded_containerd",
        "containerd_cli_root",
        "containerd_config_root",
        "containerd_default_root",
    }:
        raise StorageLifecycleError("containerd_root_authority_unresolved")
    for key in ("staging_free_bytes", "docker_free_bytes", "image_store_free_bytes"):
        _nonnegative_int(report.get(key), f"{key}_invalid")
    return {
        "image_store_backend": backend,
        "image_store_root": image_store_root,
        "image_store_root_source": root_source,
        "shared_device": devices[0],
        "free_bytes": min(
            report["staging_free_bytes"],
            report["docker_free_bytes"],
            report["image_store_free_bytes"],
        ),
    }


def capacity_report(
    *,
    filesystem_total_bytes: int,
    free_bytes: int,
    observed_mutable_allocated_bytes: int,
    staged_transport_bytes: int,
    image_import_worst_case_bytes: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    total = _positive_int(filesystem_total_bytes, "filesystem_total_bytes_invalid")
    free = _nonnegative_int(free_bytes, "free_bytes_invalid")
    mutable = _nonnegative_int(
        observed_mutable_allocated_bytes,
        "observed_mutable_allocated_bytes_invalid",
    )
    staged = _positive_int(staged_transport_bytes, "staged_transport_bytes_invalid")
    image_import = _positive_int(
        image_import_worst_case_bytes,
        "image_import_worst_case_bytes_invalid",
    )
    reserve = derived_post_peak_reserve_bytes(
        filesystem_total_bytes=total,
        observed_mutable_allocated_bytes=mutable,
        policy=policy,
    )
    required = staged + image_import + reserve
    return {
        "schema": "gh.n3w-t1-storage-capacity-report/1",
        "filesystem_total_bytes": total,
        "free_bytes": free,
        "observed_mutable_allocated_bytes": mutable,
        "staged_transport_bytes": staged,
        "image_import_worst_case_bytes": image_import,
        "derived_post_peak_reserve_bytes": reserve,
        "required_free_bytes": required,
        "post_peak_free_bytes": free - staged - image_import,
        "capacity_pass": free >= required,
        "stop_before_remote_staging": free < required,
    }
