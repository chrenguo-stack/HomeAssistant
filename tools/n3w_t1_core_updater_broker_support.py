#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-core-updater-broker-recovery-support-package/1"
MANIFEST = "manifest.json"
UPDATER = "t1-core-updater.pyz"
UNIT = "n3wfc4-core-updater-broker-recovery.service"
UNIT_SOURCE = f"infra/n3w-t1/systemd/{UNIT}"
UPDATER_INSTALL = Path("/opt/n3w-t1-core-updater/t1-core-updater.pyz")
UNIT_INSTALL = Path("/etc/systemd/system") / UNIT
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MODULES = (
    "n3w_t1_core_updater",
    "n3w_t1_core_updater_common",
    "n3w_t1_core_updater_core",
    "n3w_t1_core_updater_host",
    "n3w_t1_core_updater_state",
    "n3w_t1_core_updater_v2",
    "n3w_t1_core_updater_v2_common",
    "n3w_t1_core_updater_v2_state",
    "n3w_t1_core_updater_components",
    "n3w_t1_core_updater_a1_policy",
    "n3w_t1_core_updater_broker_recovery",
    "n3w_t1_portable_image_identity",
)
PACKAGE_FILES = frozenset({MANIFEST, UPDATER, UNIT})


class BrokerSupportError(RuntimeError):
    pass


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_source(repo: Path, source_head: str, relative: str) -> bytes:
    try:
        return subprocess.check_output(
            ("git", "show", f"{source_head}:{relative}"),
            cwd=repo,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise BrokerSupportError(
            f"broker_support_source_missing:{Path(relative).name}"
        ) from error


def _zip_entry(name: str, payload: bytes) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (0o100644 & 0xFFFF) << 16
    info.file_size = len(payload)
    return info


def _build_pyz(repo: Path, source_head: str) -> bytes:
    from io import BytesIO

    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name in MODULES:
            payload = _git_source(repo, source_head, f"tools/{name}.py")
            archive.writestr(_zip_entry(f"{name}.py", payload), payload)
        main = (
            b"from n3w_t1_core_updater import main\n"
            b"raise SystemExit(main())\n"
        )
        archive.writestr(_zip_entry("__main__.py", main), main)
    return b"#!/usr/bin/env python3\n" + output.getvalue()


def build(repo: Path, source_head: str, destination: Path) -> dict[str, Any]:
    repo = repo.resolve()
    if GIT_SHA.fullmatch(source_head) is None:
        raise BrokerSupportError("broker_support_source_head_invalid")
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise BrokerSupportError("broker_support_destination_invalid")
        if any(destination.iterdir()):
            raise BrokerSupportError("broker_support_destination_not_empty")
    else:
        destination.mkdir(parents=True, mode=0o700)

    updater = _build_pyz(repo, source_head)
    unit = _git_source(repo, source_head, UNIT_SOURCE)
    if (
        f"ExecStart={UPDATER_INSTALL} recover-broker-pending".encode()
        not in unit
        or b"Before=n3wfc4-broker-activation.service" in unit
        or b"Before=n3wfc4-services-activation.service" in unit
    ):
        raise BrokerSupportError("broker_support_unit_contract_invalid")

    payloads = {
        UPDATER: (updater, 0o755, str(UPDATER_INSTALL)),
        UNIT: (unit, 0o644, str(UNIT_INSTALL)),
    }
    for name, (payload, mode, _target) in payloads.items():
        path = destination / name
        path.write_bytes(payload)
        path.chmod(mode)

    manifest = {
        "schema": SCHEMA,
        "source_head": source_head,
        "files": {
            name: {
                "sha256": _sha256_bytes(payload),
                "size": len(payload),
                "install_mode": mode,
                "install_path": target,
            }
            for name, (payload, mode, target) in sorted(payloads.items())
        },
        "module_set": [f"{name}.py" for name in MODULES] + ["__main__.py"],
        "t1_access": False,
        "production_service_start": False,
        "board_access": False,
    }
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n"
    )
    (destination / MANIFEST).write_bytes(manifest_bytes)
    (destination / MANIFEST).chmod(0o600)
    verify(
        destination,
        expected_manifest_sha256=_sha256_bytes(manifest_bytes),
        expected_source_head=source_head,
    )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "source_head": source_head,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "updater_sha256": manifest["files"][UPDATER]["sha256"],
        "unit_sha256": manifest["files"][UNIT]["sha256"],
        "package_file_count": len(PACKAGE_FILES),
        "t1_access": False,
        "production_service_start": False,
        "board_access": False,
    }


def _read_manifest(package: Path) -> tuple[dict[str, Any], bytes]:
    if package.is_symlink() or not package.is_dir():
        raise BrokerSupportError("broker_support_package_invalid")
    if {path.name for path in package.iterdir()} != PACKAGE_FILES:
        raise BrokerSupportError("broker_support_package_file_set_invalid")
    path = package / MANIFEST
    if path.is_symlink() or not path.is_file():
        raise BrokerSupportError("broker_support_manifest_invalid")
    payload = path.read_bytes()
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise BrokerSupportError("broker_support_manifest_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != SCHEMA
        or GIT_SHA.fullmatch(str(document.get("source_head") or "")) is None
        or document.get("t1_access") is not False
        or document.get("production_service_start") is not False
        or document.get("board_access") is not False
    ):
        raise BrokerSupportError("broker_support_manifest_invalid")
    return document, payload


def verify(
    package: Path,
    *,
    expected_manifest_sha256: str | None = None,
    expected_source_head: str | None = None,
) -> dict[str, Any]:
    manifest, manifest_bytes = _read_manifest(package)
    manifest_sha = _sha256_bytes(manifest_bytes)
    if (
        expected_manifest_sha256 is not None
        and (
            SHA256.fullmatch(expected_manifest_sha256) is None
            or manifest_sha != expected_manifest_sha256
        )
    ):
        raise BrokerSupportError("broker_support_manifest_digest_mismatch")
    if (
        expected_source_head is not None
        and manifest["source_head"] != expected_source_head
    ):
        raise BrokerSupportError("broker_support_source_head_mismatch")

    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {UPDATER, UNIT}:
        raise BrokerSupportError("broker_support_manifest_file_set_invalid")
    expected_install = {
        UPDATER: (0o755, str(UPDATER_INSTALL)),
        UNIT: (0o644, str(UNIT_INSTALL)),
    }
    expected_modules = [f"{name}.py" for name in MODULES] + ["__main__.py"]
    if manifest.get("module_set") != expected_modules:
        raise BrokerSupportError("broker_support_manifest_module_set_invalid")
    for name in (UPDATER, UNIT):
        row = files.get(name)
        path = package / name
        if (
            not isinstance(row, dict)
            or path.is_symlink()
            or not path.is_file()
            or not isinstance(row.get("size"), int)
            or not isinstance(row.get("sha256"), str)
            or SHA256.fullmatch(row["sha256"]) is None
            or row.get("install_mode") != expected_install[name][0]
            or row.get("install_path") != expected_install[name][1]
            or path.stat().st_size != row["size"]
            or _sha256_file(path) != row["sha256"]
        ):
            raise BrokerSupportError("broker_support_payload_digest_mismatch")

    expected_module_names = set(expected_modules)
    try:
        with zipfile.ZipFile(package / UPDATER, "r") as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as error:
        raise BrokerSupportError("broker_support_updater_invalid") from error
    if names != expected_module_names:
        raise BrokerSupportError("broker_support_updater_module_set_invalid")
    if "n3w_t1_core_updater_broker_recovery.py" not in names:
        raise BrokerSupportError("broker_support_broker_module_missing")

    unit = (package / UNIT).read_bytes()
    if (
        f"ExecStart={UPDATER_INSTALL} recover-broker-pending".encode()
        not in unit
        or b"Restart=on-failure" not in unit
        or b"StartLimitBurst=3" not in unit
        or b"Before=n3wfc4-broker-activation.service" in unit
        or b"Before=n3wfc4-services-activation.service" in unit
    ):
        raise BrokerSupportError("broker_support_unit_contract_invalid")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "source_head": manifest["source_head"],
        "manifest_sha256": manifest_sha,
        "updater_sha256": files[UPDATER]["sha256"],
        "unit_sha256": files[UNIT]["sha256"],
        "package_file_count": len(PACKAGE_FILES),
        "t1_access": False,
        "production_service_start": False,
        "board_access": False,
    }


def _systemctl(action: str, unit: str | None = None) -> str:
    argv = ["systemctl", action]
    if unit is not None:
        argv.append(unit)
    try:
        result = subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BrokerSupportError("broker_support_systemctl_unavailable") from error
    if action in {"is-active", "is-enabled"}:
        return result.stdout.strip() or "unknown"
    if result.returncode != 0:
        raise BrokerSupportError(f"broker_support_systemctl_{action}_failed")
    return result.stdout.strip()


def _owner_uid(path: Path) -> int:
    return path.stat().st_uid


def _validate_parent(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise BrokerSupportError("broker_support_install_parent_invalid")
    if _owner_uid(path) != 0 or stat.S_IMODE(path.stat().st_mode) & 0o022:
        raise BrokerSupportError("broker_support_install_parent_metadata_invalid")


def _atomic_publish(target: Path, payload: bytes, mode: int) -> None:
    fd, raw = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(raw)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, 0, 0)
        os.chmod(temporary, mode)
        os.replace(temporary, target)
        directory = os.open(
            target.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _installed_exact(target: Path, payload: bytes, mode: int) -> bool:
    if not target.exists() and not target.is_symlink():
        return False
    if target.is_symlink() or not target.is_file():
        raise BrokerSupportError("broker_support_install_target_invalid")
    metadata = target.stat()
    if (
        _owner_uid(target) != 0
        or stat.S_IMODE(metadata.st_mode) != mode
        or target.read_bytes() != payload
    ):
        raise BrokerSupportError("broker_support_install_target_drift")
    return True


def _rooted(root: Path, target: Path) -> Path:
    return root / target.relative_to("/")


def install(
    package: Path,
    expected_manifest_sha256: str,
    *,
    root: Path = Path("/"),
    systemctl: Callable[[str, str | None], str] = _systemctl,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BrokerSupportError("root_required")
    verified = verify(
        package,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    manifest, _manifest_bytes = _read_manifest(package)
    root = root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise BrokerSupportError("broker_support_install_root_invalid")

    opt = _rooted(root, Path("/opt"))
    systemd = _rooted(root, Path("/etc/systemd/system"))
    _validate_parent(opt)
    _validate_parent(systemd)
    updater_dir = _rooted(root, UPDATER_INSTALL.parent)
    updater_target = _rooted(root, UPDATER_INSTALL)
    unit_target = _rooted(root, UNIT_INSTALL)
    updater_payload = (package / UPDATER).read_bytes()
    unit_payload = (package / UNIT).read_bytes()

    if updater_dir.exists() or updater_dir.is_symlink():
        _validate_parent(updater_dir)
    updater_exists = _installed_exact(updater_target, updater_payload, 0o755)
    unit_exists = _installed_exact(unit_target, unit_payload, 0o644)
    if updater_exists != unit_exists:
        raise BrokerSupportError("broker_support_install_partial_state")

    active_before = systemctl("is-active", UNIT)
    enabled_before = systemctl("is-enabled", UNIT)
    if active_before in {"active", "activating", "reloading"}:
        raise BrokerSupportError("broker_support_recovery_unit_active")
    if not updater_exists and enabled_before == "enabled":
        raise BrokerSupportError("broker_support_enablement_without_payload")

    created: list[Path] = []
    created_updater_dir = False
    enable_attempted = False
    try:
        if not updater_dir.exists():
            updater_dir.mkdir(mode=0o755)
            os.chmod(updater_dir, 0o755)
            os.chown(updater_dir, 0, 0)
            _validate_parent(updater_dir)
            created_updater_dir = True

        if not updater_exists:
            _atomic_publish(updater_target, updater_payload, 0o755)
            created.append(updater_target)
            _atomic_publish(unit_target, unit_payload, 0o644)
            created.append(unit_target)

        systemctl("daemon-reload", None)
        if enabled_before != "enabled":
            enable_attempted = True
            systemctl("enable", UNIT)
        if systemctl("is-enabled", UNIT) != "enabled":
            raise BrokerSupportError("broker_support_enable_verify_failed")
        if systemctl("is-active", UNIT) in {
            "active",
            "activating",
            "reloading",
        }:
            raise BrokerSupportError("broker_support_install_started_unit")
    except Exception:
        rollback_ok = True
        if enable_attempted:
            try:
                systemctl("disable", UNIT)
            except Exception:
                rollback_ok = False
        for target in reversed(created):
            try:
                target.unlink(missing_ok=True)
            except OSError:
                rollback_ok = False
        if created_updater_dir:
            try:
                updater_dir.rmdir()
            except OSError:
                rollback_ok = False
        try:
            systemctl("daemon-reload", None)
        except Exception:
            rollback_ok = False
        if not rollback_ok:
            raise BrokerSupportError(
                "broker_support_install_rollback_failed"
            )
        raise

    return {
        **verified,
        "operation": "install-broker-recovery-support",
        "installed": True,
        "reinstall": updater_exists,
        "unit_enabled": True,
        "unit_started": False,
        "product_service_mutation": False,
        "t1_access": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build_command = sub.add_parser("build")
    build_command.add_argument("--repo", type=Path, required=True)
    build_command.add_argument("--source-head", required=True)
    build_command.add_argument("--destination", type=Path, required=True)
    verify_command = sub.add_parser("verify")
    verify_command.add_argument("--package", type=Path, required=True)
    verify_command.add_argument("--manifest-sha256")
    verify_command.add_argument("--source-head")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "build":
            result = build(args.repo, args.source_head, args.destination)
        else:
            result = verify(
                args.package,
                expected_manifest_sha256=args.manifest_sha256,
                expected_source_head=args.source_head,
            )
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "operation": args.command,
                    "reason": str(error)[:200],
                    "t1_access": False,
                    "production_service_start": False,
                    "board_access": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
