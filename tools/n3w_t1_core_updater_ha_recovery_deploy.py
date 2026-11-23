#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO

from n3w_t1_core_updater_common import COMPOSE, COMPOSE_ENV, PROJECT, SERVICES_UNIT, UpdaterError, sha256_bytes
from n3w_t1_core_updater_ha_acceptance import monitoring_self_test_qualified
from n3w_t1_core_updater_ha_ipc import (
    APPROVED_MANIFEST, IPC_SERVICE_UNIT, IPC_SOCKET, IPC_SOCKET_UNIT, MANAGER_PEER_UID, RELEASE_PIN, RELEASE_PIN_SCHEMA,
    SIGNED_INDEX_STATE, HostOtaAdmission, candidate_admission, ha_image_version, read_local_release_input,
    read_signed_index,
)
from n3w_t1_core_updater_ha_recovery_startup import (
    RECOVERY_ARCHIVE,
    RECOVERY_RETRY_UNIT,
    RECOVERY_STARTUP_UNIT,
    RECOVERY_TIMER,
    LocalHaPredecessorRuntime,
    cli as recovery_cli,
)
from n3w_t1_core_updater_signed_release import (
    VerifiedHaRelease, check_signed_release, open_signed_archive, verify_signed_release,
)
from n3w_t1_core_updater_host import HOMEASSISTANT_SERVICES_READINESS_TIMEOUT_SECONDS
from n3w_t1_core_updater_v2_common import SHA256, TERMINAL_TX_V2, canonical
from n3w_t1_core_updater_v2_state import STATE_ROOT_V2, V2StateStore
from n3w_t1_portable_image_identity import parse_verified_load_archive


SCHEMA = "gh.n3w-t1-ha-recovery-install/1"
MANIFEST = "manifest.json"
ARCHIVE = "ha-recovery.pyz"
GUARD = "ota-ha-recovery.conf"
CANDIDATE_COMPOSE = "ha-ota-candidate.compose.yml"
MONITORING_CONFIG = "ha-ota-monitoring.configuration.yaml"
MONITORING_MODULE = "ha-ota-monitoring.py"
MONITORING_MANIFEST = "ha-ota-monitoring.manifest.json"
MONITORING_SOURCE = "infra/n3w-t1/homeassistant/custom_components/n3w_ota_monitoring"
MONITORING_DESTINATION = Path(RECOVERY_ARCHIVE).parent / "n3w_ota_monitoring"
MONITORING_TARGET = str(Path("/config/custom_components") / MONITORING_DESTINATION.name)
BASE_HA_CONFIG = "infra/n3w-t1/production/homeassistant-configuration.yaml"
ACTIVE_HA_CONFIG = "/opt/HomeAssistant/" + BASE_HA_CONFIG
HA_CONFIG_TARGET = "/config/configuration.yaml"
MONITORING_CONFIGURATION = b"\nn3w_ota_monitoring:\n  system_id: !env_var GH_SYSTEM_ID\n"
CANDIDATE_DOWNLOAD_LOCK = ".ha-candidate-download.lock"
CANDIDATE_DOWNLOAD_PART = ".ha-candidate-download.part"
BASE_COMPOSE = "infra/n3w-t1/production/docker-compose.fresh.yml"
PERSISTENT_UNITS = (RECOVERY_STARTUP_UNIT, RECOVERY_TIMER, IPC_SOCKET_UNIT)
ENABLEMENT_DIRS = ("multi-user.target.wants", "timers.target.wants", "sockets.target.wants")
DESTINATIONS = {
    ARCHIVE: RECOVERY_ARCHIVE.removeprefix("/"),
    RECOVERY_STARTUP_UNIT: f"etc/systemd/system/{RECOVERY_STARTUP_UNIT}",
    RECOVERY_RETRY_UNIT: f"etc/systemd/system/{RECOVERY_RETRY_UNIT}",
    RECOVERY_TIMER: f"etc/systemd/system/{RECOVERY_TIMER}",
    IPC_SOCKET_UNIT: f"etc/systemd/system/{IPC_SOCKET_UNIT}",
    IPC_SERVICE_UNIT: f"etc/systemd/system/{IPC_SERVICE_UNIT}",
    GUARD: f"etc/systemd/system/{SERVICES_UNIT}.d/{GUARD}",
    CANDIDATE_COMPOSE: str(Path(RECOVERY_ARCHIVE).with_name(CANDIDATE_COMPOSE)).removeprefix("/"),
    MONITORING_CONFIG: str(Path(RECOVERY_ARCHIVE).with_name(MONITORING_CONFIG)).removeprefix("/"),
    MONITORING_MODULE: str(MONITORING_DESTINATION / "__init__.py").removeprefix("/"),
    MONITORING_MANIFEST: str(MONITORING_DESTINATION / "manifest.json").removeprefix("/"),
}
MODULES = (
    "n3w_t1_core_stack_release",
    "n3w_t1_core_updater_common",
    "n3w_t1_core_updater_ha_acceptance",
    "n3w_t1_core_updater_ha_backup",
    "n3w_t1_core_updater_ha_data_evidence",
    "n3w_t1_core_updater_ha_ipc",
    "n3w_t1_core_updater_ha_monitoring_evidence",
    "n3w_t1_core_updater_ha_mounted_media",
    "n3w_t1_core_updater_ha_recovery",
    "n3w_t1_core_updater_ha_recovery_deploy",
    "n3w_t1_core_updater_ha_recovery_startup",
    "n3w_t1_core_updater_ha_usb",
    "n3w_t1_core_updater_ha_usb_media",
    "n3w_t1_core_updater_ha_usb_state",
    "n3w_t1_core_updater_host",
    "n3w_t1_core_updater_signed_release",
    "n3w_t1_core_updater_v2_common",
    "n3w_t1_core_updater_v2_state",
    "n3w_t1_portable_image_identity",
)


def _candidate_settings(version: str) -> dict[str, str]:
    return {
        "GH_N3W_T1_OTA_ENABLED": "true",
        "GH_N3W_T1_OTA_INSTALLED_VERSION": version,
        "GH_N3W_T1_OTA_MANIFEST_PATH": str(IPC_SOCKET.with_name(APPROVED_MANIFEST)),
        "GH_N3W_T1_OTA_SOCKET_PATH": str(IPC_SOCKET),
    }


def _candidate_compose(base: bytes) -> bytes:
    """Create the opt-in candidate from the exact fresh stack Compose template."""
    prefix, manager_header, rest = base.decode().partition("\n  manager:\n")
    manager, ha_header, suffix = rest.partition("\n  homeassistant:\n")
    environment = "    environment:\n"
    volumes = "    volumes:\n"
    if (
        not manager_header or not ha_header or manager.count(environment) != 1 or manager.count(volumes) != 1
        or "GH_N3W_T1_OTA_" in manager or str(IPC_SOCKET.parent) in manager
    ):
        raise UpdaterError("ha_recovery_candidate_compose_template_drift")
    manager = manager.replace(environment, environment + "".join(
        f'      {key}: "{value}"\n' for key, value in _candidate_settings(
            "${GH_N3W_T1_OTA_INSTALLED_VERSION:?HA predecessor version required}"
        ).items()
    ))
    manager = manager.replace(volumes, volumes + (
        "      - type: bind\n"
        f"        source: {IPC_SOCKET.parent}\n"
        f"        target: {IPC_SOCKET.parent}\n"
        "        read_only: true\n"
        "        bind:\n"
        "          create_host_path: false\n"
    ))
    config = f"        source: {ACTIVE_HA_CONFIG}\n        target: {HA_CONFIG_TARGET}\n        read_only: true\n"
    if suffix.count(volumes) != 1 or suffix.count(config) != 1 or environment in suffix or MONITORING_TARGET in suffix:
        raise UpdaterError("ha_recovery_candidate_ha_template_drift")
    suffix = suffix.replace(volumes, (
        "    environment:\n"
        '      GH_SYSTEM_ID: "${GH_SYSTEM_ID:?GH_SYSTEM_ID required}"\n'
        "    volumes:\n"
        "      - type: bind\n"
        f"        source: {MONITORING_DESTINATION}\n"
        f"        target: {MONITORING_TARGET}\n"
        "        read_only: true\n"
        "        bind:\n"
        "          create_host_path: false\n"
    ))
    suffix = suffix.replace(config, (
        f"        source: /{DESTINATIONS[MONITORING_CONFIG]}\n"
        f"        target: {HA_CONFIG_TARGET}\n"
        "        read_only: true\n"
        "        bind:\n"
        "          create_host_path: false\n"
    ))
    return (prefix + manager_header + manager + ha_header + suffix).encode()


def build(repo: Path, source_head: str, destination: Path) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        raise UpdaterError("ha_recovery_install_source_invalid")

    def source(path: str) -> bytes:
        return subprocess.check_output(("git", "show", f"{source_head}:{path}"), cwd=repo)

    modules = {f"{name}.py": source(f"tools/{name}.py") for name in MODULES}
    modules["__main__.py"] = (
        b"from n3w_t1_core_updater_ha_recovery_deploy import bundle_main\n"
        b"raise SystemExit(bundle_main())\n"
    )
    unit_source = "infra/n3w-t1/systemd"
    payload = {unit: source(f"{unit_source}/{unit}") for unit in (*PERSISTENT_UNITS, RECOVERY_RETRY_UNIT, IPC_SERVICE_UNIT)}
    payload[GUARD] = source(f"{unit_source}/{SERVICES_UNIT}.d/{GUARD}")
    payload[CANDIDATE_COMPOSE] = _candidate_compose(source(BASE_COMPOSE))
    base_config = source(BASE_HA_CONFIG)
    if not base_config.endswith(b"\n") or b"n3w_ota_monitoring" in base_config:
        raise UpdaterError("ha_recovery_candidate_ha_config_template_drift")
    payload[MONITORING_CONFIG] = base_config + MONITORING_CONFIGURATION
    payload[MONITORING_MODULE] = source(f"{MONITORING_SOURCE}/__init__.py")
    payload[MONITORING_MANIFEST] = source(f"{MONITORING_SOURCE}/manifest.json")
    destination.mkdir(mode=0o700)
    with zipfile.ZipFile(destination / ARCHIVE, "w") as archive:
        for name, content in sorted(modules.items()):
            archive.writestr(zipfile.ZipInfo(name), content)
    for name, content in payload.items():
        (destination / name).write_bytes(content)
    files = {name: sha256_bytes((destination / name).read_bytes()) for name in DESTINATIONS}
    manifest = json.dumps(
        {"schema": SCHEMA, "source_head": source_head, "files": files}, sort_keys=True, indent=2,
    ).encode() + b"\n"
    (destination / MANIFEST).write_bytes(manifest)
    return sha256_bytes(manifest)


def _verified_package(package: Path, expected: str) -> tuple[str, dict[str, bytes]]:
    if SHA256.fullmatch(expected) is None:
        raise UpdaterError("ha_recovery_install_manifest_digest_invalid")
    if package.is_symlink() or {path.name for path in package.iterdir()} != {*DESTINATIONS, MANIFEST}:
        raise UpdaterError("ha_recovery_install_file_set_invalid")

    def read(name: str) -> bytes:
        path = package / name
        if not stat.S_ISREG(path.lstat().st_mode):
            raise UpdaterError("ha_recovery_install_package_file_invalid")
        return path.read_bytes()

    manifest = read(MANIFEST)
    if sha256_bytes(manifest) != expected:
        raise UpdaterError("ha_recovery_install_manifest_digest_mismatch")
    document = json.loads(manifest)
    if (
        not isinstance(document, dict) or document.get("schema") != SCHEMA
        or not isinstance(document.get("source_head"), str)
        or re.fullmatch(r"[0-9a-f]{40}", document["source_head"]) is None
    ):
        raise UpdaterError("ha_recovery_install_manifest_invalid")
    payload = {name: read(name) for name in DESTINATIONS}
    if {name: sha256_bytes(value) for name, value in payload.items()} != document.get("files"):
        raise UpdaterError("ha_recovery_install_payload_digest_mismatch")
    return document["source_head"], payload


def _validate_path(root: Path, target: Path, content: bytes) -> bool:
    for path in (root, *(root / parent for parent in target.relative_to(root).parents if parent.parts)):
        if not os.path.lexists(path):
            continue
        entry = path.lstat()
        if not stat.S_ISDIR(entry.st_mode) or entry.st_uid != os.geteuid() or entry.st_mode & 0o022:
            raise UpdaterError("ha_recovery_install_directory_invalid")
    if not os.path.lexists(target):
        return False
    entry = target.lstat()
    if (
        not stat.S_ISREG(entry.st_mode) or entry.st_uid != os.geteuid()
        or stat.S_IMODE(entry.st_mode) != 0o644 or target.read_bytes() != content
    ):
        raise UpdaterError("ha_recovery_install_existing_file_drift")
    return True


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(target: Path, content: bytes, created: list[Path]) -> None:
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
        created.append(target)
        _sync_directory(target.parent)
        _sync_directory(target.parent.parent)
    finally:
        Path(temporary).unlink()


def _systemctl(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ("/usr/bin/systemctl", *args), capture_output=True, text=True, check=check, timeout=30,
    ).stdout.strip()


def _render_candidate_compose(path: Path, *, predecessor_version: str | None = None) -> dict:
    environment = {"PATH": os.defpath}
    if predecessor_version is not None:
        if re.fullmatch(r"[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,3}", predecessor_version) is None:
            raise UpdaterError("ha_recovery_candidate_predecessor_version_invalid")
        environment["GH_N3W_T1_OTA_INSTALLED_VERSION"] = predecessor_version
    result = subprocess.run(
        ("/usr/bin/docker", "compose", "--project-name", PROJECT,
         "--project-directory", str(COMPOSE.parent), "--env-file", str(COMPOSE_ENV),
         "-f", str(path), "--profile", "application", "config", "--format", "json"),
        cwd=COMPOSE.parent, env=environment, capture_output=True, timeout=120,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        missing = re.search(r"required variable ([A-Z][A-Z0-9_]*) is missing a value", stderr)
        if missing is not None:
            raise UpdaterError(
                f"ha_recovery_candidate_compose_required_variable_missing:{missing.group(1)}"
            )
        raise UpdaterError("ha_recovery_candidate_compose_render_failed")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise UpdaterError("ha_recovery_candidate_compose_render_invalid") from error
    if not isinstance(document, dict):
        raise UpdaterError("ha_recovery_candidate_compose_render_invalid")
    return document


def _matching_read_only_bind(volumes: list, source: str, target: str, reason: str) -> dict:
    mount = {"type": "bind", "source": source, "target": target, "read_only": True}
    matches = [v for v in volumes if isinstance(v, dict) and v.get("target") == target]
    # Compose may retain an empty bind object after omitting a false option.
    if len(matches) != 1 or matches[0] not in (
        mount, {**mount, "bind": {}}, {**mount, "bind": {"create_host_path": False}},
    ):
        raise UpdaterError(reason)
    return matches[0]


def _verify_candidate_delta(active: dict, staged: dict, version: str) -> None:
    services = staged.get("services")
    manager = services.get("manager") if isinstance(services, dict) else None
    environment = manager.get("environment") if isinstance(manager, dict) else None
    volumes = manager.get("volumes") if isinstance(manager, dict) else None
    if not isinstance(environment, dict) or not isinstance(volumes, list):
        raise UpdaterError("ha_recovery_candidate_manager_invalid")
    expected = _candidate_settings(version)
    if {key: environment.get(key) for key in expected} != expected:
        raise UpdaterError("ha_recovery_candidate_manager_settings_drift")
    volumes.remove(_matching_read_only_bind(
        volumes, str(IPC_SOCKET.parent), str(IPC_SOCKET.parent), "ha_recovery_candidate_manager_mount_drift",
    ))
    for key in expected:
        environment.pop(key)

    ha = services.get("homeassistant")
    active_ha = active["services"].get("homeassistant")
    system_id = environment.get("GH_SYSTEM_ID")
    if (
        not isinstance(system_id, str) or re.fullmatch(r"[a-zA-Z0-9_-]{3,64}", system_id) is None
        or not isinstance(ha, dict) or ha.get("environment") != {"GH_SYSTEM_ID": system_id}
        or not isinstance(ha.get("volumes"), list) or not isinstance(active_ha, dict)
        or not isinstance(active_ha.get("volumes"), list) or "environment" in active_ha
    ):
        raise UpdaterError("ha_recovery_candidate_ha_environment_drift")
    ha_volumes = ha["volumes"]
    config = _matching_read_only_bind(
        ha_volumes, f"/{DESTINATIONS[MONITORING_CONFIG]}", HA_CONFIG_TARGET,
        "ha_recovery_candidate_ha_config_mount_drift",
    )
    active_config = _matching_read_only_bind(
        active_ha["volumes"], ACTIVE_HA_CONFIG, HA_CONFIG_TARGET, "ha_recovery_candidate_active_ha_config_drift",
    )
    ha_volumes.remove(_matching_read_only_bind(
        ha_volumes, str(MONITORING_DESTINATION), MONITORING_TARGET, "ha_recovery_candidate_ha_monitoring_mount_drift",
    ))
    ha_volumes[ha_volumes.index(config)] = active_config
    del ha["environment"]
    if staged != active:
        raise UpdaterError("ha_recovery_candidate_unexpected_compose_change")


def check_candidate_activation(
    package: Path, expected: str, *, root: Path = Path("/"),
    runtime=None, systemctl=_systemctl, render=_render_candidate_compose,
) -> dict:
    source_head, payload = _verified_package(package, expected)
    store = V2StateStore(root / STATE_ROOT_V2.relative_to("/"))
    if not store.root.is_dir():
        raise UpdaterError("ha_recovery_candidate_install_incomplete")
    with store.lock():
        _require_idle(store)
        for name, destination in DESTINATIONS.items():
            if not _validate_path(root, root / destination, payload[name]):
                raise UpdaterError("ha_recovery_candidate_install_incomplete")
        socket = root / IPC_SOCKET.relative_to("/")
        metadata = socket.lstat()
        directory = socket.parent.lstat()
        if (
            socket.resolve(strict=True) != socket
            or not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.geteuid()
            or directory.st_mode & 0o022 or directory.st_mode & 0o005 != 0o005
            or not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.geteuid()
            or metadata.st_gid != MANAGER_PEER_UID or stat.S_IMODE(metadata.st_mode) != 0o660
            or systemctl("is-enabled", IPC_SOCKET_UNIT) != "enabled"
            or systemctl("show", "--property=SubState", "--value", IPC_SOCKET_UNIT) not in {"listening", "running"}
        ):
            raise UpdaterError("ha_recovery_candidate_socket_unavailable")
        runtime = LocalHaPredecessorRuntime() if runtime is None else runtime
        observed = runtime._runtime("homeassistant")
        version = ha_image_version(observed["image_ref"])
        if version is None:
            raise UpdaterError("ha_recovery_candidate_predecessor_version_unknown")
        binding = runtime.capture_start_binding({
            "current_image_ref": observed["image_ref"],
            "current_image_identity": {"runtime_image_id": observed["image_id"]},
        })
        active = render(root / COMPOSE.relative_to("/"))
        services = active.get("services")
        if not isinstance(services, dict) or any(
            not isinstance(services.get(name), dict) or services[name].get("image") != image["reference"]
            for name, image in binding["images"].items()
        ):
            raise UpdaterError("ha_recovery_candidate_active_compose_image_drift")
        if runtime.image_binding_modes_v2().get("homeassistant") != "dynamic":
            raise UpdaterError("ha_recovery_candidate_predecessor_binding_not_dynamic")
        active_path = root / COMPOSE.relative_to("/")
        if active_path.is_symlink() or not active_path.is_file():
            raise UpdaterError("ha_recovery_candidate_active_compose_invalid")
        candidate_payload = _candidate_compose(active_path.read_bytes())
        with tempfile.TemporaryDirectory(prefix="n3w-ha-activation-preflight-") as raw:
            candidate = Path(raw) / CANDIDATE_COMPOSE
            candidate.write_bytes(candidate_payload)
            candidate.chmod(0o600)
            _verify_candidate_delta(
                active,
                render(candidate, predecessor_version=version),
                version,
            )
        config = payload[MONITORING_CONFIG]
        if not config.endswith(MONITORING_CONFIGURATION):
            raise UpdaterError("ha_recovery_candidate_ha_config_template_drift")
        active_config = root / ACTIVE_HA_CONFIG.removeprefix("/")
        if not _validate_path(root, active_config, config.removesuffix(MONITORING_CONFIGURATION)):
            raise UpdaterError("ha_recovery_candidate_active_ha_config_missing")
        manager_self_test = runtime.candidate_manager_monitoring_self_test_available()
        if manager_self_test is not True:
            raise UpdaterError("ha_recovery_candidate_manager_monitoring_self_test_required")
    return {
        "source_head": source_head,
        "status": "CANDIDATE_ACTIVATION_PREFLIGHT_PASS",
        "predecessor_version": version,
        "manager_monitoring_self_test_available": True,
        "monitoring_mode": "natural_with_self_test_fallback",
    }


def activate_candidate_runtime(
    package: Path, expected: str, *, root: Path = Path("/"),
    runtime: LocalHaPredecessorRuntime | None = None,
    systemctl=_systemctl,
    render=_render_candidate_compose,
) -> dict[str, object]:
    """Activate the exact monitoring/OTA runtime before a business HA transaction exists."""
    preflight = check_candidate_activation(
        package, expected, root=root, runtime=runtime, systemctl=systemctl, render=render,
    )
    source_head, payload = _verified_package(package, expected)
    runtime = LocalHaPredecessorRuntime() if runtime is None else runtime
    store = V2StateStore(root / STATE_ROOT_V2.relative_to("/"))
    active_path = root / COMPOSE.relative_to("/")

    with store.lock():
        _require_idle(store)
        for name, destination in DESTINATIONS.items():
            if not _validate_path(root, root / destination, payload[name]):
                raise UpdaterError("ha_recovery_candidate_install_incomplete")
        if runtime.candidate_manager_monitoring_self_test_available() is not True:
            raise UpdaterError("ha_recovery_candidate_manager_monitoring_self_test_required")

        observed = runtime._runtime("homeassistant")
        version = ha_image_version(observed["image_ref"])
        if version is None:
            raise UpdaterError("ha_recovery_candidate_predecessor_version_unknown")
        before_binding = runtime.capture_start_binding({
            "current_image_ref": observed["image_ref"],
            "current_image_identity": {"runtime_image_id": observed["image_id"]},
        })
        if active_path.is_symlink() or not active_path.is_file():
            raise UpdaterError("ha_recovery_candidate_active_compose_invalid")
        original = active_path.read_bytes()
        candidate_payload = _candidate_compose(original)

        active = render(active_path)
        with tempfile.TemporaryDirectory(prefix="n3w-ha-activation-live-") as raw:
            candidate_path = Path(raw) / CANDIDATE_COMPOSE
            candidate_path.write_bytes(candidate_payload)
            candidate_path.chmod(0o600)
            staged = render(candidate_path, predecessor_version=version)
            expected_runtime = copy.deepcopy(staged)
            _verify_candidate_delta(active, copy.deepcopy(staged), version)

        stopped = False
        candidate_written = False
        try:
            runtime.stop_services()
            stopped = True
            runtime._replace_product_file(
                active_path,
                candidate_payload,
                verify_error="ha_recovery_candidate_active_compose_replace_failed",
            )
            candidate_written = True
            runtime.start_services(
                readiness_timeout=HOMEASSISTANT_SERVICES_READINESS_TIMEOUT_SECONDS,
            )

            after = render(active_path)
            if after != expected_runtime:
                raise UpdaterError("ha_recovery_candidate_active_compose_runtime_drift")
            after_binding = runtime.capture_start_binding({
                "current_image_ref": observed["image_ref"],
                "current_image_identity": {"runtime_image_id": observed["image_id"]},
            })
            if after_binding["images"] != before_binding["images"]:
                raise UpdaterError("ha_recovery_candidate_runtime_image_drift")
            if runtime.candidate_manager_monitoring_self_test_available() is not True:
                raise UpdaterError("ha_recovery_candidate_manager_monitoring_self_test_unavailable")
            proof = runtime.acceptance_observer().run_monitoring_self_test()
            if not monitoring_self_test_qualified(proof):
                raise UpdaterError("ha_recovery_candidate_monitoring_self_test_failed")
        except Exception as error:
            if candidate_written:
                try:
                    runtime.stop_services()
                    runtime._replace_product_file(
                        active_path,
                        original,
                        verify_error="ha_recovery_candidate_original_compose_restore_failed",
                    )
                    runtime.start_services(
                        readiness_timeout=HOMEASSISTANT_SERVICES_READINESS_TIMEOUT_SECONDS,
                    )
                    restored = runtime.capture_start_binding({
                        "current_image_ref": observed["image_ref"],
                        "current_image_identity": {"runtime_image_id": observed["image_id"]},
                    })
                    if restored != before_binding:
                        raise UpdaterError("ha_recovery_candidate_original_runtime_restore_drift")
                except Exception as restore_error:
                    raise UpdaterError("ha_recovery_candidate_activation_rollback_failed") from restore_error
            elif stopped:
                try:
                    runtime.start_services(
                        readiness_timeout=HOMEASSISTANT_SERVICES_READINESS_TIMEOUT_SECONDS,
                    )
                except Exception as restore_error:
                    raise UpdaterError("ha_recovery_candidate_activation_rollback_failed") from restore_error
            raise error

    return {
        **preflight,
        "source_head": source_head,
        "status": "CANDIDATE_RUNTIME_ACTIVATED",
        "monitoring_self_test_sha256": proof,
        "runtime_images_unchanged": True,
        "broker_mutation": False,
    }


def _require_idle(store: V2StateStore) -> None:
    for transaction, terminal in (
        (store.read(), TERMINAL_TX_V2),
        (store.read_legacy(), {"COMMITTED", "ROLLED_BACK"}),
        (store.read_ha_usb_guard(), {"COMMITTED", "ROLLED_BACK"}),
    ):
        if transaction is not None and transaction.get("status") not in terminal:
            raise UpdaterError("ha_recovery_install_transaction_active")


def _stage_target_archive(
    runtime: LocalHaPredecessorRuntime, open_archive: Callable[[int], AbstractContextManager[BinaryIO]],
    target: Path, admission: HostOtaAdmission,
) -> None:
    lock = target.parent / CANDIDATE_DOWNLOAD_LOCK
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.geteuid():
            raise UpdaterError("ha_recovery_candidate_download_lock_invalid")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise UpdaterError("ha_recovery_candidate_download_busy") from error
        partial = target.parent / CANDIDATE_DOWNLOAD_PART
        # The previous downloader may have lost power before it could remove this file.
        partial.unlink(missing_ok=True)
        _stage_locked_target_archive(runtime, open_archive, target, admission, partial)
    finally:
        os.close(descriptor)


def _stage_locked_target_archive(
    runtime: LocalHaPredecessorRuntime, open_archive: Callable[[int], AbstractContextManager[BinaryIO]],
    target: Path, admission: HostOtaAdmission, partial: Path,
) -> None:
    size = admission.target_archive_size
    digest = admission.target_archive_sha256
    if os.path.lexists(target):
        if stat.S_IMODE(target.lstat().st_mode) != 0o600:
            raise UpdaterError("ha_recovery_candidate_staged_archive_invalid")
        with runtime._open_target_source(target, size) as staged:
            if hashlib.file_digest(staged, "sha256").hexdigest() != digest:
                raise UpdaterError("ha_recovery_candidate_staged_archive_invalid")
            staged.seek(0)
            parse_verified_load_archive(
                staged, archive_sha256=digest, archive_size_bytes=size, expected_tag=admission.target_image_ref,
            )
        return

    with open_archive(size) as incoming:
        fd = os.open(partial, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            observed = hashlib.sha256()
            remaining = size
            with os.fdopen(fd, "w+b") as staged:
                while remaining:
                    block = incoming.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    staged.write(block)
                    observed.update(block)
                    remaining -= len(block)
                if remaining or incoming.read(1) or observed.hexdigest() != digest:
                    raise UpdaterError("ha_recovery_candidate_archive_digest_mismatch")
                staged.flush()
                staged.seek(0)
                parse_verified_load_archive(
                    staged, archive_sha256=digest, archive_size_bytes=size, expected_tag=admission.target_image_ref,
                )
                os.fsync(staged.fileno())
            os.link(partial, target)
            _sync_directory(target.parent)
        finally:
            partial.unlink(missing_ok=True)


def _write_candidate_record(path: Path, content: bytes, mode: int) -> None:
    fd, temporary_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_path)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def materialize_candidate(
    manifest: Path, manifest_sha256: str, archive: Path, expires_at_unix: int,
    *, root: Path = Path("/"), runtime: LocalHaPredecessorRuntime | None = None,
) -> dict:
    if SHA256.fullmatch(manifest_sha256) is None:
        raise UpdaterError("ha_recovery_candidate_approval_digest_invalid")
    raw = read_local_release_input(manifest, limit=32768, private=False)
    if sha256_bytes(raw) != manifest_sha256:
        raise UpdaterError("ha_recovery_candidate_approval_digest_mismatch")
    runtime = LocalHaPredecessorRuntime() if runtime is None else runtime
    return _materialize_candidate(
        raw, expires_at_unix, lambda size: runtime._open_target_source(archive, size), root=root, runtime=runtime,
    )


def materialize_signed_candidate(
    trust_policy: Path, *, root: Path = Path("/"), runtime: LocalHaPredecessorRuntime | None = None,
) -> dict:
    release = verify_signed_release(trust_policy)
    runtime = LocalHaPredecessorRuntime() if runtime is None else runtime
    return _materialize_candidate(
        release.approved_manifest, release.expires_at_unix, lambda _: open_signed_archive(release),
        root=root, runtime=runtime, signed_release=release,
    )


def _validate_signed_index(path: Path, release: VerifiedHaRelease) -> dict:
    signed_index = {"sequence": release.index_sequence, "sha256": release.index_sha256}
    if os.path.lexists(path):
        previous = read_signed_index(path)
        if release.index_sequence < previous["sequence"]:
            raise UpdaterError("ha_recovery_signed_index_replay")
        if release.index_sequence == previous["sequence"] and signed_index != previous:
            raise UpdaterError("ha_recovery_signed_index_sequence_conflict")
    return signed_index


def _materialize_candidate(
    raw: bytes, expires_at_unix: int, open_archive: Callable[[int], AbstractContextManager[BinaryIO]],
    *, root: Path, runtime: LocalHaPredecessorRuntime, signed_release: VerifiedHaRelease | None = None,
) -> dict:
    if type(expires_at_unix) is not int or expires_at_unix <= time.time():
        raise UpdaterError("ha_recovery_candidate_approval_expired")

    store = V2StateStore(root / STATE_ROOT_V2.relative_to("/"))
    export = root / IPC_SOCKET.parent.relative_to("/")
    index_path = store.root / SIGNED_INDEX_STATE
    with store.lock():
        _require_idle(store)
        directory = export.lstat()
        if (
            export.resolve(strict=True) != export or not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != os.geteuid() or directory.st_mode & 0o022
            or directory.st_mode & 0o005 != 0o005
        ):
            raise UpdaterError("ha_recovery_candidate_export_directory_invalid")
        if signed_release is not None:
            _validate_signed_index(index_path, signed_release)
        admission = candidate_admission(raw, runtime._runtime("homeassistant"))
        predecessor = {
            "current_image_ref": admission.current_image_ref,
            "current_image_identity": admission.current_image_identity,
        }
        binding = runtime.capture_start_binding(predecessor)
        if signed_release is not None and binding["images"] != signed_release.predecessor_images:
            raise UpdaterError("ha_recovery_signed_predecessor_identity_mismatch")

    # Let startup and IPC acquire the state lock during the potentially long transfer.
    target = store.root / f"ha-target-{admission.target_archive_sha256}.tar"
    _stage_target_archive(runtime, open_archive, target, admission)

    with store.lock():
        _require_idle(store)
        if binding != runtime.capture_start_binding(predecessor):
            raise UpdaterError("ha_recovery_candidate_predecessor_changed")
        if expires_at_unix <= time.time():
            raise UpdaterError("ha_recovery_candidate_approval_expired")

        pin = {
            "schema": RELEASE_PIN_SCHEMA, "manifest_sha256": sha256_bytes(raw),
            "predecessor_image_id": admission.current_image_identity["runtime_image_id"],
            "expires_at_unix": expires_at_unix,
        }
        if signed_release is not None:
            signed_index = _validate_signed_index(index_path, signed_release)
            pin["signed_index"] = signed_index
            pin["predecessor_binding_sha256"] = sha256_bytes(canonical(binding))
            _write_candidate_record(index_path, canonical(signed_index), 0o600)
        # PREPARE checks all records under this lock and refuses an incomplete publication.
        _write_candidate_record(store.root / RELEASE_PIN, canonical(pin), 0o600)
        _write_candidate_record(export / APPROVED_MANIFEST, raw, 0o644)
    result = {"status": "CANDIDATE_MATERIALIZED", "release_identity": admission.release_identity, "target_source": str(target)}
    if signed_release is not None:
        result.update(index_sequence=signed_release.index_sequence, index_sha256=signed_release.index_sha256)
    return result


def install(package: Path, expected: str, *, root: Path = Path("/"), systemctl=_systemctl) -> dict:
    source_head, payload = _verified_package(package, expected)
    store = V2StateStore(root / STATE_ROOT_V2.relative_to("/"))
    with store.lock():
        _require_idle(store)
        targets = {name: root / relative for name, relative in DESTINATIONS.items()}
        existing = {name: _validate_path(root, target, payload[name]) for name, target in targets.items()}
        created: list[Path] = []
        to_enable: list[str] = []
        enable_attempted = False
        try:
            for name, target in targets.items():
                if name != GUARD and not existing[name]:
                    _publish(target, payload[name], created)
            for unit in PERSISTENT_UNITS:
                state = systemctl("is-enabled", unit, check=False)
                if state not in {"enabled", "disabled"}:
                    raise UpdaterError("ha_recovery_install_unit_state_invalid")
                if state == "disabled":
                    to_enable.append(unit)
            if to_enable:
                enable_attempted = True
                systemctl("--no-reload", "enable", *to_enable)
            if any(systemctl("is-enabled", unit) != "enabled" for unit in PERSISTENT_UNITS):
                raise UpdaterError("ha_recovery_install_enablement_unverified")
            for directory in ENABLEMENT_DIRS:
                _sync_directory(targets[RECOVERY_TIMER].parent / directory)
            _sync_directory(targets[RECOVERY_TIMER].parent)
            if not existing[GUARD]:
                _publish(targets[GUARD], payload[GUARD], created)
            systemctl("daemon-reload")
            if not all(_validate_path(root, target, payload[name]) for name, target in targets.items()):
                raise UpdaterError("ha_recovery_install_readback_failed")
        except Exception:
            if targets[GUARD] in created:
                targets[GUARD].unlink()
                _sync_directory(targets[GUARD].parent)
                created.remove(targets[GUARD])
            if enable_attempted:
                systemctl("--no-reload", "disable", *to_enable)
            for path in reversed(created):
                path.unlink()
                _sync_directory(path.parent)
            systemctl("daemon-reload")
            raise
    return {"schema": SCHEMA, "source_head": source_head, "installed": True, "units_started": False}


def bundle_main() -> int:
    action = sys.argv[1:2]
    if action not in (
        ["install"], ["check-candidate-activation"], ["activate-candidate-runtime"],
        ["materialize-candidate"], ["check-signed-release"], ["materialize-signed-candidate"],
    ):
        return recovery_cli()
    parser = argparse.ArgumentParser(prog=f"ha-recovery.pyz {action[0]}")
    if action in (["check-signed-release"], ["materialize-signed-candidate"]):
        parser.add_argument("--trust-policy", type=Path, required=True)
    elif action == ["materialize-candidate"]:
        parser.add_argument("--approved-manifest", type=Path, required=True)
        parser.add_argument("--approved-manifest-sha256", required=True)
        parser.add_argument("--target-archive", type=Path, required=True)
        parser.add_argument("--expires-at-unix", type=int, required=True)
    else:
        parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(sys.argv[2:])
    if os.geteuid() != 0:
        parser.error("this command requires root")
    if action == ["check-signed-release"]:
        result = check_signed_release(args.trust_policy)
    elif action == ["materialize-signed-candidate"]:
        result = materialize_signed_candidate(args.trust_policy)
    elif action == ["materialize-candidate"]:
        result = materialize_candidate(
            args.approved_manifest, args.approved_manifest_sha256, args.target_archive, args.expires_at_unix,
        )
    else:
        operation = {
            "install": install,
            "check-candidate-activation": check_candidate_activation,
            "activate-candidate-runtime": activate_candidate_runtime,
        }[action[0]]
        result = operation(Path(sys.argv[0]).resolve().parent, args.manifest_sha256)
    print(json.dumps(result, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(build(Path(__file__).resolve().parents[1], args.source_head, args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
