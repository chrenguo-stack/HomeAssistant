from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

CANDIDATE_SOURCE = "3d86d6bfaf361dc3a3d7295d046f541a544d552d"
CANDIDATE_TAG = "n3w-p4-manager:" + CANDIDATE_SOURCE
MANAGER_NAME = "greenhouse-manager"
BROKER_NAME = "n3wfc4-broker-1"
RW_TARGETS = frozenset({
    "/var/lib/greenhouse-manager-registration",
    "/var/lib/greenhouse-manager/n3w",
    "/var/lib/greenhouse-manager/n3w/relay-keys",
})
RO_TARGETS = frozenset({
    "/run/secrets/provisioning_password",
    "/run/secrets/broker-ca.pem",
    "/run/secrets/gh_manager_mqtt_password",
})
ALL_TARGETS = RW_TARGETS | RO_TARGETS
CONFIG_COMPARE = (
    "Env", "User", "Entrypoint", "Cmd", "WorkingDir",
    "Healthcheck", "StopSignal", "OpenStdin", "StdinOnce", "Tty",
)
HOST_COMPARE = (
    "NetworkMode", "PortBindings", "ReadonlyRootfs", "Tmpfs",
    "CapAdd", "CapDrop", "SecurityOpt", "Privileged", "LogConfig",
    "Devices", "DeviceRequests", "PidsLimit", "Memory", "MemorySwap",
    "NanoCpus", "Ulimits", "IpcMode", "PidMode", "ShmSize",
    "CgroupnsMode", "Dns", "ExtraHosts", "Init", "OomKillDisable",
)
TRANSACTION_PHASES = (
    "PRECHECK_OLD_MANAGER_RUNNING",
    "SHADOW_CREATE_AND_COMPARE_STOPPED",
    "OLD_MANAGER_STOP",
    "FRESH_THREE_SOURCE_COLD_COPY",
    "CLONED_STATE_BUSINESS_PROOF",
    "OLD_MANAGER_PARKED_NOT_DELETED",
    "NEW_MANAGER_CREATED_WITH_ONLY_CLONED_RW_STATE",
    "NEW_MANAGER_RUN_AND_RUNTIME_PROOF",
    "SUCCESS_COMMIT_KEEP_ORIGINAL_FOR_ROLLBACK",
)


class CutoverStop(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CutoverStop(code)


def _absolute(path: object) -> str:
    require(isinstance(path, str) and path.startswith("/"), "NONABSOLUTE_PATH")
    p = PurePosixPath(path)
    require(str(p) == path and ".." not in p.parts, "NONCANONICAL_PATH")
    return path


def _same_or_nested(a: str, b: str) -> bool:
    pa = PurePosixPath(a)
    pb = PurePosixPath(b)
    return pa == pb or pa in pb.parents or pb in pa.parents


def _mounts(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    mounts = item.get("Mounts")
    require(isinstance(mounts, list) and len(mounts) == 6, "SIX_BINDS_REQUIRED")
    for mount in mounts:
        require(isinstance(mount, dict), "MOUNT_FORMAT_INVALID")
        dest = mount.get("Destination")
        require(dest in ALL_TARGETS and dest not in found, "MOUNT_DESTINATION_DRIFT")
        require(mount.get("Type") == "bind", "NON_BIND_MOUNT_FORBIDDEN")
        require(mount.get("RW") is (dest in RW_TARGETS), "MOUNT_PERMISSION_DRIFT")
        _absolute(mount.get("Source"))
        require(mount.get("Propagation") in (None, "", "rprivate"), "MOUNT_PROPAGATION_DRIFT")
        found[dest] = mount
    require(set(found) == ALL_TARGETS, "MOUNT_SET_INCOMPLETE")
    return found


def validate_source_authority(manager: dict[str, Any], broker: dict[str, Any],
                              image: dict[str, Any]) -> None:
    require(manager.get("Name") == "/" + MANAGER_NAME, "MANAGER_NAME_MISMATCH")
    require(manager.get("State", {}).get("Running") is True, "OLD_MANAGER_NOT_RUNNING")
    host = manager.get("HostConfig", {})
    require(host.get("NetworkMode") == "host", "MANAGER_NOT_HOST_NETWORK")
    require(host.get("PortBindings") in ({}, None), "MANAGER_PORT_PUBLICATION_FORBIDDEN")
    require(host.get("ReadonlyRootfs") is True, "MANAGER_ROOTFS_NOT_READONLY")
    require(host.get("RestartPolicy", {}).get("Name") == "unless-stopped",
            "OLD_MANAGER_RESTART_POLICY_DRIFT")
    require(isinstance(manager.get("Image"), str) and manager["Image"].startswith("sha256:"),
            "OLD_MANAGER_IMAGE_UNBOUND")
    require(broker.get("State", {}).get("Running") is True, "BROKER_NOT_RUNNING")
    require(image.get("Os") == "linux" and image.get("Architecture") == "arm64",
            "CANDIDATE_ARCHITECTURE_MISMATCH")
    require(image.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.revision")
            == CANDIDATE_SOURCE, "CANDIDATE_REVISION_MISMATCH")
    require(isinstance(image.get("Id"), str) and image["Id"].startswith("sha256:"),
            "CANDIDATE_IMAGE_UNBOUND")
    _mounts(manager)
    require(len(manager.get("Config", {}).get("Env", [])) > 0, "MANAGER_ENV_MISSING")


def plan_isolated_bindings(manager: dict[str, Any],
                           clones: dict[str, str]) -> dict[str, dict[str, Any]]:
    original = _mounts(manager)
    require(set(clones) == RW_TARGETS, "CLONE_BINDING_SET_MISMATCH")
    resolved = {key: _absolute(value) for key, value in clones.items()}
    orig_sources = [_absolute(m["Source"]) for m in original.values()]
    for dst, src in resolved.items():
        require(src != original[dst]["Source"], "CANDIDATE_MUST_NOT_WRITE_OLD_STATE")
        require(not any(_same_or_nested(src, existing) for existing in orig_sources),
                "CLONE_OVERLAPS_ORIGINAL_STATE")
    vals = list(resolved.values())
    for i, a in enumerate(vals):
        for other in vals[i + 1:]:
            require(not _same_or_nested(a, other), "CLONE_SOURCE_OVERLAP")
    result = {}
    for dest, mount in original.items():
        x = dict(mount)
        if dest in RW_TARGETS:
            x["Source"] = resolved[dest]
        result[dest] = x
    return result


def verify_stopped_shadow_matches_origin(
    old: dict[str, Any],
    new: dict[str, Any],
    image_id: str,
    clones: dict[str, str],
) -> None:
    require(new.get("State", {}).get("Running") is False, "SHADOW_MUST_BE_STOPPED")
    require(new.get("Image") == image_id, "SHADOW_WRONG_IMAGE")
    expected = plan_isolated_bindings(old, clones)
    actual = _mounts(new)
    for dest in ALL_TARGETS:
        for attr in ("Type", "Source", "Destination", "RW", "Propagation"):
            require(actual[dest].get(attr) == expected[dest].get(attr),
                    "SHADOW_MOUNT_PARITY_FAILED")
    old_config = old.get("Config", {})
    new_config = new.get("Config", {})
    for name in CONFIG_COMPARE:
        require(new_config.get(name) == old_config.get(name), "SHADOW_CONFIG_PARITY_FAILED")
    old_labels = dict(old_config.get("Labels") or {})
    new_labels = dict(new_config.get("Labels") or {})
    old_labels.pop("org.opencontainers.image.revision", None)
    new_labels.pop("org.opencontainers.image.revision", None)
    require(new_labels == old_labels, "SHADOW_NONREVISION_LABEL_DRIFT")
    require(
        (new_config.get("Labels") or {}).get("org.opencontainers.image.revision")
        == CANDIDATE_SOURCE, "SHADOW_CANDIDATE_REVISION_MISMATCH",
    )
    old_host = old.get("HostConfig", {})
    new_host = new.get("HostConfig", {})
    for name in HOST_COMPARE:
        require(new_host.get(name) == old_host.get(name),
                "SHADOW_HOST_SECURITY_PARITY_FAILED")
    require(new_host.get("RestartPolicy", {}).get("Name") == "no",
            "SHADOW_AUTORESTART_FORBIDDEN")


def assert_cutover_sequence(phases: list[str]) -> None:
    require(phases == list(TRANSACTION_PHASES), "CUTOVER_SEQUENCE_UNSAFE")


def classify_staged_result(manager_ok: bool, broker_unchanged: bool,
                           clone_verified: bool, secret_gate_pass: bool) -> str:
    if not manager_ok or not broker_unchanged or not clone_verified or not secret_gate_pass:
        return "STOP_RESCUE_OLD_MANAGER"
    return "RUNTIME_READY_NO_NODE_TRAFFIC_EXPECTED"
