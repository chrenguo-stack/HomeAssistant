#!/usr/bin/env python3
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Protocol

from n3w_t1_production_v2_contract import (
    canonical_sha256,
    validate_marker,
    validate_release,
)

SCHEMA = "gh.n3w-t1-production-v2-post-reboot-acceptance/1"
OBSERVATION_SECONDS = 90
REQUIRED_EXTERNAL_PROBES = (
    "TCP_8883",
    "TLS_CA",
    "TLS_HOSTNAME_SNI",
    "MANAGER_MQTT_AUTH",
    "HOMEASSISTANT_MQTT_AUTH",
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
    def observe_critical_restarts(self, seconds: int) -> dict[str, Any]: ...


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

    probes: dict[str, bool] = {}
    for name in REQUIRED_EXTERNAL_PROBES:
        report = _pass(adapter.external_probe(name), f"external_probe:{name}")
        if report.get("accepted") is not True:
            raise PostRebootAcceptanceError(f"external_probe_invalid:{name}")
        probes[name] = True

    observation = _pass(
        adapter.observe_critical_restarts(OBSERVATION_SECONDS),
        "critical_restart_observation",
    )
    if observation.get("observation_seconds") != OBSERVATION_SECONDS:
        raise PostRebootAcceptanceError("observation_window_invalid")
    deltas = observation.get("restart_deltas")
    if not isinstance(deltas, dict) or set(deltas) != set(CRITICAL_SERVICES):
        raise PostRebootAcceptanceError("critical_restart_set_invalid")
    for service in CRITICAL_SERVICES:
        value = deltas.get(service)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            raise PostRebootAcceptanceError(
                f"critical_restart_observed:{service}"
            )

    evidence = {
        "schema": SCHEMA,
        "status": "PASS",
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
