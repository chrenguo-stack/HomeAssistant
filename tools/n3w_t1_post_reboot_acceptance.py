#!/usr/bin/env python3
from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any, Protocol

from n3w_t1_production_v2_contract import (
    canonical_sha256,
    validate_marker,
    validate_release,
)

SCHEMA = "gh.n3w-t1-production-v2-post-reboot-acceptance/2"
OBSERVATION_SECONDS = 90
SAMPLE_INTERVAL_SECONDS = 2
MAX_SAMPLE_GAP_SECONDS = 15
SNAPSHOT_SCHEMA = "gh.n3w-t1-runtime-snapshot/2"
REQUIRED_EXTERNAL_PROBES = (
    "TCP_8883",
    "TLS_CA",
    "TLS_HOSTNAME_SNI",
    "INVALID_CREDENTIAL_REJECTED",
    "HOMEASSISTANT_HTTP_READY",
)
CRITICAL_SERVICES = ("broker", "manager", "homeassistant")
BINDING_KEYS = (
    "run_id",
    "release_id",
    "release_sha256",
    "source_head",
    "target_binding_sha256",
    "ssh_host_key_sha256",
    "plan_sha256",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class PostRebootAcceptanceError(RuntimeError):
    pass


class AcceptanceAdapter(Protocol):
    def read_started_marker(self) -> dict[str, Any]: ...
    def target_local_reboot_verify(self) -> dict[str, Any]: ...
    def external_probe(self, name: str) -> dict[str, Any]: ...
    def runtime_snapshot(self) -> dict[str, Any]: ...
    def observe_runtime(self, seconds: int, baseline: dict[str, Any]) -> dict[str, Any]: ...


def _pass(document: Any, name: str) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("status") != "PASS":
        raise PostRebootAcceptanceError(f"{name}_not_pass")
    return document


def _validate_started_binding(
    marker_document: Any,
    binding: dict[str, str],
    release_document: Any,
) -> dict[str, Any]:
    marker = validate_marker(deepcopy(marker_document))
    release = validate_release(deepcopy(release_document))
    if marker["state"] != "STARTED":
        raise PostRebootAcceptanceError("marker_not_started")
    if set(binding) != set(BINDING_KEYS):
        raise PostRebootAcceptanceError("marker_binding_keys_invalid")
    for key in BINDING_KEYS:
        if marker.get(key) != binding.get(key):
            raise PostRebootAcceptanceError(f"marker_binding_mismatch:{key}")
    if marker["release_id"] != release["release_id"]:
        raise PostRebootAcceptanceError("release_id_binding_mismatch")
    if marker["release_sha256"] != canonical_sha256(release):
        raise PostRebootAcceptanceError("release_sha256_binding_mismatch")
    if marker["source_head"] != release["source_head"]:
        raise PostRebootAcceptanceError("source_head_binding_mismatch")
    return marker


def _digest(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_snapshot(document: Any) -> dict[str, Any]:
    snapshot = _pass(document, "runtime_snapshot")
    if (
        snapshot.get("schema") != SNAPSHOT_SCHEMA
        or not _digest(snapshot.get("boot_id_sha256"))
        or re.fullmatch(r"[0-9a-f]{40}", str(snapshot.get("source_head"))) is None
        or not _digest(snapshot.get("control_manifest_sha256"))
        or snapshot.get("homeassistant_http_ready") is not True
        or not _digest(snapshot.get("systemd_state_sha256"))
        or not _digest(snapshot.get("critical_errors_sha256"))
    ):
        raise PostRebootAcceptanceError("runtime_snapshot_evidence_invalid")
    containers = snapshot.get("containers")
    if not isinstance(containers, dict) or set(containers) != set(CRITICAL_SERVICES):
        raise PostRebootAcceptanceError("runtime_container_set_invalid")
    for name, record in containers.items():
        if (
            not isinstance(record, dict)
            or not _digest(record.get("identity_sha256"))
            or type(record.get("restart_count")) is not int
            or record["restart_count"] < 0
            or record.get("running") is not True
        ):
            raise PostRebootAcceptanceError(f"runtime_container_invalid:{name}")
    auth = snapshot.get("runtime_service_auth")
    if not isinstance(auth, dict) or set(auth) != {"manager", "homeassistant"}:
        raise PostRebootAcceptanceError("runtime_service_auth_set_invalid")
    for name, record in auth.items():
        count = record.get("owned_socket_count") if isinstance(record, dict) else None
        if (
            not isinstance(record, dict)
            or record.get("authenticated") is not True
            or record.get("endpoint_port") != (8883 if name == "manager" else 1883)
            or type(count) is not int
            or (name == "manager" and count != 1)
            or (name == "homeassistant" and count < 1)
            or any(not _digest(record.get(key)) for key in (
                "identity_sha256",
                "owned_socket_sha256",
                "authenticated_connection_sha256",
            ))
        ):
            raise PostRebootAcceptanceError(f"runtime_service_auth_invalid:{name}")
    return snapshot


def _continuity_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": snapshot["schema"],
        "boot_id_sha256": snapshot["boot_id_sha256"],
        "source_head": snapshot["source_head"],
        "control_manifest_sha256": snapshot["control_manifest_sha256"],
        "containers": snapshot["containers"],
        "runtime_service_auth": {
            name: {
                "authenticated": record["authenticated"],
                "endpoint_port": record["endpoint_port"],
                "identity_sha256": record["identity_sha256"],
                "owned_socket_count": record["owned_socket_count"],
                "owned_socket_sha256": record["owned_socket_sha256"],
            }
            for name, record in snapshot["runtime_service_auth"].items()
        },
        "systemd_state_sha256": snapshot["systemd_state_sha256"],
        "critical_errors_sha256": snapshot["critical_errors_sha256"],
        "homeassistant_http_ready": snapshot["homeassistant_http_ready"],
    }


def require_continuity(baseline: dict[str, Any], document: Any) -> dict[str, Any]:
    baseline_snapshot = validate_snapshot(baseline)
    snapshot = validate_snapshot(document)
    if _continuity_projection(snapshot) != _continuity_projection(baseline_snapshot):
        raise PostRebootAcceptanceError("runtime_continuity_changed")
    return snapshot


def run_acceptance(
    adapter: AcceptanceAdapter,
    release_document: Any,
    binding: dict[str, str],
) -> dict[str, Any]:
    release = validate_release(deepcopy(release_document))
    _validate_started_binding(adapter.read_started_marker(), binding, release)

    local = _pass(
        adapter.target_local_reboot_verify(),
        "target_local_reboot_verify",
    )
    if (
        local.get("state") != "REBOOT_ACCEPTED"
        or local.get("reboot_acceptance_passed") is not True
    ):
        raise PostRebootAcceptanceError("target_local_reboot_acceptance_invalid")
    pre_boot = local.get("pre_boot_id_sha256")
    post_boot = local.get("post_boot_id_sha256")
    if (
        not isinstance(pre_boot, str)
        or SHA256_RE.fullmatch(pre_boot) is None
        or not isinstance(post_boot, str)
        or SHA256_RE.fullmatch(post_boot) is None
        or pre_boot == post_boot
    ):
        raise PostRebootAcceptanceError("real_boot_change_not_proven")

    baseline = validate_snapshot(adapter.runtime_snapshot())
    if baseline["boot_id_sha256"] != post_boot or baseline["source_head"] != release["source_head"]:
        raise PostRebootAcceptanceError("runtime_snapshot_binding_mismatch")
    probes: dict[str, bool] = {}
    for name in REQUIRED_EXTERNAL_PROBES:
        report = _pass(adapter.external_probe(name), f"external_probe:{name}")
        if report.get("accepted") is not True:
            raise PostRebootAcceptanceError(f"external_probe_invalid:{name}")
        if name == "INVALID_CREDENTIAL_REJECTED" and (
            type(report.get("connack_reason")) is not int
            or report["connack_reason"] not in {0x86, 0x87}
        ):
            raise PostRebootAcceptanceError("authentication_refusal_not_proven")
        require_continuity(baseline, adapter.runtime_snapshot())
        probes[name] = True

    observation = _pass(
        adapter.observe_runtime(OBSERVATION_SECONDS, baseline),
        "runtime_observation",
    )
    if observation.get("observation_seconds") != OBSERVATION_SECONDS:
        raise PostRebootAcceptanceError("observation_window_invalid")
    samples = observation.get("samples")
    if not isinstance(samples, list) or len(samples) < 7:
        raise PostRebootAcceptanceError("observation_samples_insufficient")
    previous = 0.0
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise PostRebootAcceptanceError("observation_sample_invalid")
        elapsed = sample.get("elapsed_seconds")
        if (
            type(elapsed) not in {int, float} or not math.isfinite(elapsed)
            or elapsed < 0 or (index > 0 and elapsed <= previous)
            or elapsed - previous > MAX_SAMPLE_GAP_SECONDS
        ):
            raise PostRebootAcceptanceError("observation_coverage_invalid")
        require_continuity(baseline, sample.get("snapshot"))
        previous = elapsed
    if not OBSERVATION_SECONDS <= previous <= OBSERVATION_SECONDS + MAX_SAMPLE_GAP_SECONDS:
        raise PostRebootAcceptanceError("observation_duration_invalid")

    evidence = {
        "schema": SCHEMA,
        "status": "PASS",
        "run_id": binding["run_id"],
        "ssh_host_key_sha256": binding["ssh_host_key_sha256"],
        "release_id": release["release_id"],
        "release_sha256": canonical_sha256(release),
        "source_head": release["source_head"],
        "source_tree": release["source_tree"],
        "target_binding_sha256": binding["target_binding_sha256"],
        "plan_sha256": binding["plan_sha256"],
        "pre_boot_id_sha256": pre_boot,
        "post_boot_id_sha256": post_boot,
        "target_local_reboot_verify": True,
        "external_probes": probes,
        "runtime_service_auth": baseline["runtime_service_auth"],
        "runtime_baseline_sha256": canonical_sha256(baseline),
        "runtime_observation_sha256": canonical_sha256(observation),
        "runtime_sample_count": len(samples),
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
        "max_sample_gap_seconds": MAX_SAMPLE_GAP_SECONDS,
        "runtime_continuity_verified": True,
        "observation_seconds": OBSERVATION_SECONDS,
        "no_critical_restart": True,
        "secret_values_included": False,
        "board_access": False,
    }
    acceptance_sha256 = canonical_sha256(evidence)
    return {
        **evidence,
        "acceptance_sha256": acceptance_sha256,
    }
