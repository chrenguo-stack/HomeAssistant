#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from n3w_t1_core_updater_common import SERVICES_UNIT, UpdaterError, sha256_bytes
from n3w_t1_core_updater_ha_ipc import IPC_SERVICE_UNIT, IPC_SOCKET_UNIT
from n3w_t1_core_updater_ha_recovery_startup import (
    RECOVERY_ARCHIVE,
    RECOVERY_RETRY_UNIT,
    RECOVERY_STARTUP_UNIT,
    RECOVERY_TIMER,
    cli as recovery_cli,
)
from n3w_t1_core_updater_v2_common import SHA256, TERMINAL_TX_V2
from n3w_t1_core_updater_v2_state import STATE_ROOT_V2, V2StateStore


SCHEMA = "gh.n3w-t1-ha-recovery-install/1"
MANIFEST = "manifest.json"
ARCHIVE = "ha-recovery.pyz"
GUARD = "ota-ha-recovery.conf"
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
}
MODULES = (
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
    "n3w_t1_core_updater_v2_common",
    "n3w_t1_core_updater_v2_state",
    "n3w_t1_portable_image_identity",
)


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


def install(package: Path, expected: str, *, root: Path = Path("/"), systemctl=_systemctl) -> dict:
    source_head, payload = _verified_package(package, expected)
    store = V2StateStore(root / STATE_ROOT_V2.relative_to("/"))
    with store.lock():
        for transaction, terminal in (
            (store.read(), TERMINAL_TX_V2),
            (store.read_legacy(), {"COMMITTED", "ROLLED_BACK"}),
            (store.read_ha_usb_guard(), {"COMMITTED", "ROLLED_BACK"}),
        ):
            if transaction is not None and transaction.get("status") not in terminal:
                raise UpdaterError("ha_recovery_install_transaction_active")
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
    if sys.argv[1:2] != ["install"]:
        return recovery_cli()
    parser = argparse.ArgumentParser(prog="ha-recovery.pyz install")
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(sys.argv[2:])
    if os.geteuid() != 0:
        parser.error("installation requires root")
    print(json.dumps(install(Path(sys.argv[0]).resolve().parent, args.manifest_sha256), sort_keys=True))
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
