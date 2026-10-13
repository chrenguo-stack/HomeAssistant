from __future__ import annotations

import posixpath
import re
from collections.abc import Callable
from typing import Any

from n3w_t1_r2c_evidence_schema import REQUIREMENT_FIELDS
from n3w_t1_r2c_readonly_commands import CommandResult, run_contract_command
from n3w_t1_r2c_readonly_files import (
    ReadonlyEvidenceError,
    inspect_metadata,
    read_bounded_text,
    read_symlink_target,
)

OS_RELEASE_KEYS = ("ID", "VERSION_ID", "VERSION_CODENAME", "PRETTY_NAME")
ARMBIAN_RELEASE_KEYS = (
    "BOARD",
    "BOARD_NAME",
    "VERSION",
    "BRANCH",
    "ARCH",
    "IMAGE_TYPE",
)
MACHINE_ID_RE = re.compile(r"[0-9a-fA-F]{32}\Z")
CommandRunner = Callable[..., CommandResult]


class R2CCollectError(RuntimeError):
    pass


def _field(value: Any = None, status: str = "NOT_EXECUTED") -> dict[str, Any]:
    return {"value": value, "status": status}


def empty_requirement(requirement_id: str) -> dict[str, Any]:
    if requirement_id not in REQUIREMENT_FIELDS:
        raise R2CCollectError("unknown_requirement")
    return {
        "status": "NOT_EXECUTED",
        "complete": False,
        "reason_code": None,
        "method_ids": [],
        "provenance": [],
        "fields": {
            name: _field() for name in sorted(REQUIREMENT_FIELDS[requirement_id])
        },
    }


def _decode_text(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise R2CCollectError(f"{label}_NOT_UTF8") from error


def _parse_assignment_file(
    root: str,
    relative: str,
    allowed_keys: tuple[str, ...],
) -> tuple[dict[str, str], str]:
    metadata = inspect_metadata(root, relative)
    if metadata["status"] == "ABSENT":
        return {}, "ABSENT"
    if metadata["kind"] != "regular":
        raise R2CCollectError("STOP_CONFIG_NOT_REGULAR")
    text = _decode_text(read_bounded_text(root, relative), "CONFIG")
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in allowed_keys:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result, "OBSERVED"


def _command_text(result: CommandResult, label: str) -> str:
    if result.returncode != 0:
        raise R2CCollectError(f"{label}_COMMAND_FAILED")
    return _decode_text(result.stdout or result.stderr, label).strip()


def _parse_package_versions(text: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not all(parts):
            raise R2CCollectError("PACKAGE_OUTPUT_INVALID")
        package, version, architecture = parts
        result[package] = {"version": version, "architecture": architecture}
    return result


def collect_e1(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = empty_requirement("E1")
    try:
        os_release, os_status = _parse_assignment_file(
            root,
            "etc/os-release",
            OS_RELEASE_KEYS,
        )
        armbian_release, armbian_status = _parse_assignment_file(
            root,
            "etc/armbian-release",
            ARMBIAN_RELEASE_KEYS,
        )
        systemd = runner("C1_SYSTEMD")
        architecture = runner("C1_ARCH")
        python = runner("C2_PYTHON")
        packages = runner("C3_PACKAGES")
        systemd_text = _command_text(systemd, "SYSTEMD")
        architecture_text = _command_text(architecture, "ARCH")
        python_text = _command_text(python, "PYTHON")
        package_versions = _parse_package_versions(
            _command_text(packages, "PACKAGES")
        )
    except (OSError, ReadonlyEvidenceError, R2CCollectError) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = (
            str(error)
            if isinstance(error, R2CCollectError)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", str(error))
            else "STOP_E1_COLLECTION_ERROR"
        )
        return envelope

    envelope["method_ids"] = ["R1", "R2", "C1", "C2", "C3"]
    envelope["fields"]["os_release"] = _field(os_release, os_status)
    envelope["fields"]["armbian_release"] = _field(
        armbian_release,
        armbian_status,
    )
    envelope["fields"]["architecture"] = _field(
        architecture_text,
        "OBSERVED",
    )
    envelope["fields"]["systemd_version"] = _field(
        systemd_text.splitlines()[0] if systemd_text else None,
        "OBSERVED" if systemd_text else "UNKNOWN",
    )
    envelope["fields"]["package_versions"] = _field(
        package_versions,
        "OBSERVED",
    )
    envelope["fields"]["executable_binding"] = _field(
        {
            "systemd": systemd.executable,
            "uname": architecture.executable,
            "python": python.executable,
            "dpkg_query": packages.executable,
            "python_version": python_text,
        },
        "OBSERVED",
    )
    complete = (
        os_status == "OBSERVED"
        and armbian_status == "OBSERVED"
        and bool(systemd_text)
        and bool(architecture_text)
        and bool(package_versions)
    )
    envelope["status"] = "OBSERVED" if complete else "UNKNOWN"
    envelope["complete"] = complete
    envelope["reason_code"] = None if complete else "STOP_EVIDENCE_GAP"
    return envelope


def _machine_id_value_class(data: bytes) -> str:
    text = _decode_text(data, "MACHINE_ID").strip()
    if text == "":
        return "EMPTY"
    if text == "uninitialized":
        return "UNINITIALIZED"
    if MACHINE_ID_RE.fullmatch(text):
        return "VALID_HEX32"
    return "INVALID"


def _machine_id_record(root: str, relative: str) -> tuple[dict[str, Any], bytes | None]:
    metadata = inspect_metadata(root, relative)
    if metadata["status"] == "ABSENT":
        return {"kind": "absent", "content_class": "ABSENT"}, None
    if metadata["kind"] == "symlink":
        target = read_symlink_target(root, relative)
        return {
            "kind": "symlink",
            "target_kind": "ABSOLUTE" if target.startswith("/") else "RELATIVE",
        }, None
    if metadata["kind"] != "regular":
        return {"kind": metadata["kind"], "content_class": "UNSUPPORTED"}, None
    data = read_bounded_text(root, relative, limit=256)
    return {
        "kind": "regular",
        "mode": metadata.get("mode"),
        "content_class": _machine_id_value_class(data),
    }, data


def _lexical_symlink_points_to(
    link_relative: str,
    target: str,
    expected_relative: str,
) -> bool:
    if target.startswith("/"):
        normalized = posixpath.normpath(target).lstrip("/")
    else:
        parent = posixpath.dirname(link_relative)
        normalized = posixpath.normpath(posixpath.join(parent, target))
    return normalized == expected_relative


def collect_e4(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = empty_requirement("E4")
    try:
        etc_record, etc_value = _machine_id_record(root, "etc/machine-id")
        dbus_record, dbus_value = _machine_id_record(
            root,
            "var/lib/dbus/machine-id",
        )
        relation: dict[str, Any] = {
            "etc_kind": etc_record["kind"],
            "dbus_kind": dbus_record["kind"],
            "dbus_points_to_etc": None,
        }
        dbus_metadata = inspect_metadata(root, "var/lib/dbus/machine-id")
        if dbus_metadata["status"] == "OBSERVED" and dbus_metadata["kind"] == "symlink":
            target = read_symlink_target(root, "var/lib/dbus/machine-id")
            relation["dbus_points_to_etc"] = _lexical_symlink_points_to(
                "var/lib/dbus/machine-id",
                target,
                "etc/machine-id",
            )
        contents_equal = (
            etc_value == dbus_value
            if etc_value is not None and dbus_value is not None
            else None
        )
        mount = runner("C5_MACHINE_ID_MOUNT")
    except (OSError, ReadonlyEvidenceError, R2CCollectError) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = (
            str(error)
            if isinstance(error, R2CCollectError)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", str(error))
            else "STOP_E4_COLLECTION_ERROR"
        )
        return envelope

    if mount.returncode == 0:
        mount_relation = {
            "is_mountpoint": True,
            "classification": "OBSERVED",
        }
        mount_status = "OBSERVED"
    elif mount.returncode == 1:
        mount_relation = {
            "is_mountpoint": False,
            "classification": "OBSERVED",
        }
        mount_status = "OBSERVED"
    else:
        mount_relation = {
            "is_mountpoint": None,
            "classification": "UNKNOWN",
        }
        mount_status = "UNKNOWN"

    envelope["method_ids"] = ["R1", "C5"]
    envelope["fields"]["etc_machine_id"] = _field(etc_record, "OBSERVED")
    envelope["fields"]["dbus_machine_id"] = _field(dbus_record, "OBSERVED")
    envelope["fields"]["path_relation"] = _field(relation, "OBSERVED")
    envelope["fields"]["mount_relation"] = _field(
        mount_relation,
        mount_status,
    )
    envelope["fields"]["contents_equal"] = _field(
        contents_equal,
        "OBSERVED" if contents_equal is not None else "UNKNOWN",
    )
    envelope["fields"]["boot_condition_contract"] = _field(None, "NOT_EXECUTED")
    envelope["fields"]["fallback_sources"] = _field(None, "NOT_EXECUTED")
    envelope["status"] = "UNKNOWN"
    envelope["complete"] = False
    envelope["reason_code"] = "STOP_SEMANTICS_GAP"
    return envelope
