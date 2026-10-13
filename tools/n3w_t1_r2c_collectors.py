from __future__ import annotations

import gzip
import hashlib
import io
import posixpath
import re
from collections.abc import Callable
from typing import Any

from n3w_t1_r2c_collectors_e5_e9 import _snapshot_units, _unit_summary
from n3w_t1_r2c_evidence_schema import REQUIREMENT_FIELDS
from n3w_t1_r2c_firstrun import (
    FIRSTRUN_RELATIVE,
    FirstrunAnalysisError,
    analyze_firstrun_config,
    analyze_firstrun_tree,
)
from n3w_t1_r2c_readonly_commands import (
    CommandResult,
    ReadonlyCommandError,
    run_contract_command,
)
from n3w_t1_r2c_readonly_files import (
    MAX_TEXT_BYTES,
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
EXPECTED_ARMBIAN_VERSION = "26.05.0"
EXPECTED_ARMBIAN_ARCH = "arm64"
EXPECTED_ARMBIAN_BOARD = "S912-Phicomm-T1"
EXPECTED_KERNEL_ARCH = "aarch64"
E4_UNITS = (
    "systemd-machine-id-commit.service",
    "systemd-firstboot.service",
)
E4_MANUAL_BASENAMES = frozenset(
    {
        "machine-id.5",
        "machine-id.5.gz",
        "systemd-firstboot.1",
        "systemd-firstboot.1.gz",
        "systemd-machine-id-setup.1",
        "systemd-machine-id-setup.1.gz",
    }
)


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
    except (OSError, ReadonlyCommandError, ReadonlyEvidenceError, R2CCollectError) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = (
            str(error)
            if isinstance(error, R2CCollectError)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", str(error))
            else "STOP_E1_COLLECTION_ERROR"
        )
        return envelope

    target_observations = (
        (armbian_release.get("VERSION"), EXPECTED_ARMBIAN_VERSION),
        (armbian_release.get("ARCH"), EXPECTED_ARMBIAN_ARCH),
        (armbian_release.get("BOARD"), EXPECTED_ARMBIAN_BOARD),
        (architecture_text or None, EXPECTED_KERNEL_ARCH),
    )
    target_drift = any(
        observed is not None and observed != expected
        for observed, expected in target_observations
    )
    target_identity_complete = all(
        observed is not None for observed, _ in target_observations
    )
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
    if target_drift:
        envelope["status"] = "ERROR"
        envelope["complete"] = False
        envelope["reason_code"] = "STOP_TARGET_DRIFT"
    else:
        complete = complete and target_identity_complete
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


def _machine_id_record(
    root: str,
    relative: str,
) -> tuple[dict[str, Any], bytes | None, str]:
    metadata = inspect_metadata(root, relative)
    if metadata["status"] == "ABSENT":
        return {"kind": "absent", "content_class": "ABSENT"}, None, "ABSENT"
    if metadata["kind"] == "symlink":
        target = read_symlink_target(root, relative)
        return (
            {
                "kind": "symlink",
                "target_kind": "ABSOLUTE" if target.startswith("/") else "RELATIVE",
            },
            None,
            "OBSERVED",
        )
    if metadata["kind"] != "regular":
        return (
            {"kind": metadata["kind"], "content_class": "UNSUPPORTED"},
            None,
            "UNKNOWN",
        )
    data = read_bounded_text(root, relative, limit=256)
    return (
        {
            "kind": "regular",
            "mode": metadata.get("mode"),
            "content_class": _machine_id_value_class(data),
        },
        data,
        "OBSERVED",
    )


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


def _read_manual_bytes(root: str, absolute_path: str) -> bytes:
    relative = absolute_path.lstrip("/")
    compressed = read_bounded_text(root, relative, limit=MAX_TEXT_BYTES)
    if not absolute_path.endswith(".gz"):
        return compressed
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            data = stream.read(MAX_TEXT_BYTES + 1)
    except (OSError, EOFError) as error:
        raise R2CCollectError("E4_MANUAL_DECOMPRESS_FAILED") from error
    if len(data) > MAX_TEXT_BYTES:
        raise R2CCollectError("E4_MANUAL_DECOMPRESSED_TOO_LARGE")
    return data


def _collect_e4_fallback_sources(
    root: str,
    runner: CommandRunner,
) -> tuple[dict[str, Any], str]:
    try:
        listing = runner(
            "C3_LIST",
            value="systemd",
            approved_packages={"systemd"},
        )
    except (OSError, ReadonlyCommandError):
        return {
            "package_file_list": "UNKNOWN",
            "sources": [],
        }, "UNKNOWN"
    if listing.returncode != 0:
        return {
            "package_file_list": "UNKNOWN",
            "sources": [],
        }, "UNKNOWN"
    try:
        text = _decode_text(listing.stdout, "SYSTEMD_PACKAGE_LIST")
    except R2CCollectError:
        return {
            "package_file_list": "UNKNOWN",
            "sources": [],
        }, "UNKNOWN"

    candidates = sorted(
        {
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("/usr/share/man/")
            and posixpath.basename(line.strip()) in E4_MANUAL_BASENAMES
        }
    )
    sources: list[dict[str, Any]] = []
    unresolved = False
    for path in candidates:
        try:
            data = _read_manual_bytes(root, path)
            decoded = data.decode("utf-8", errors="replace").lower()
        except (
            OSError,
            ReadonlyEvidenceError,
            R2CCollectError,
        ):
            unresolved = True
            continue
        sources.append(
            {
                "role": posixpath.basename(path).removesuffix(".gz"),
                "sha256": hashlib.sha256(data).hexdigest(),
                "markers": {
                    "etc_machine_id": "/etc/machine-id" in decoded,
                    "var_lib_dbus_machine_id": "/var/lib/dbus/machine-id"
                    in decoded,
                    "run_machine_id": "/run/machine-id" in decoded,
                    "uninitialized": "uninitialized" in decoded,
                    "first_boot": "first boot" in decoded
                    or "first-boot" in decoded,
                    "machine_id_setup": "systemd-machine-id-setup" in decoded,
                },
            }
        )
    has_machine_id_authority = any(
        item["role"] == "machine-id.5"
        and (
            item["markers"]["etc_machine_id"]
            or item["markers"]["uninitialized"]
        )
        for item in sources
    )
    status = (
        "OBSERVED"
        if has_machine_id_authority and not unresolved
        else "UNKNOWN"
    )
    return {
        "package_file_list": "OBSERVED",
        "source_count": len(sources),
        "sources": sources,
    }, status


def _collect_e4_boot_contract(
    root: str,
    runner: CommandRunner,
) -> tuple[dict[str, Any], str]:
    try:
        units, unresolved = _snapshot_units(
            root,
            E4_UNITS,
            runner,
        )
    except (
        OSError,
        ReadonlyCommandError,
        ReadonlyEvidenceError,
    ):
        return {"units": {}}, "UNKNOWN"
    summaries = {
        name: _unit_summary(snapshot)
        for name, snapshot in units.items()
    }
    return {
        "units": summaries,
        "unresolved": unresolved,
    }, "OBSERVED" if not unresolved else "UNKNOWN"


def collect_e4(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = empty_requirement("E4")
    try:
        etc_record, etc_value, etc_status = _machine_id_record(
            root,
            "etc/machine-id",
        )
        dbus_record, dbus_value, dbus_status = _machine_id_record(
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
    except (OSError, ReadonlyCommandError, ReadonlyEvidenceError, R2CCollectError) as error:
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

    boot_contract, boot_status = _collect_e4_boot_contract(
        root,
        runner,
    )
    fallback_sources, fallback_status = _collect_e4_fallback_sources(
        root,
        runner,
    )
    envelope["method_ids"] = ["R1", "C3", "C4", "C5"]
    envelope["fields"]["etc_machine_id"] = _field(etc_record, etc_status)
    envelope["fields"]["dbus_machine_id"] = _field(dbus_record, dbus_status)
    envelope["fields"]["path_relation"] = _field(relation, "OBSERVED")
    envelope["fields"]["mount_relation"] = _field(
        mount_relation,
        mount_status,
    )
    envelope["fields"]["contents_equal"] = _field(
        contents_equal,
        "OBSERVED" if contents_equal is not None else "UNKNOWN",
    )
    envelope["fields"]["boot_condition_contract"] = _field(
        boot_contract,
        boot_status,
    )
    envelope["fields"]["fallback_sources"] = _field(
        fallback_sources,
        fallback_status,
    )
    identity_capture_statuses = {etc_status, dbus_status}
    identity_capture_complete = not identity_capture_statuses & {"UNKNOWN", "ERROR"}
    complete = (
        identity_capture_complete
        and mount_status == "OBSERVED"
        and boot_status == "OBSERVED"
        and fallback_status == "OBSERVED"
    )
    envelope["status"] = "OBSERVED" if complete else "UNKNOWN"
    envelope["complete"] = complete
    envelope["reason_code"] = None if complete else "STOP_SEMANTICS_GAP"
    return envelope



def _owner_binding(
    runner: CommandRunner,
    absolute_path: str,
) -> tuple[str, str]:
    result = runner(
        "C3_OWNER",
        value=absolute_path,
        approved_paths={absolute_path},
    )
    if result.returncode != 0:
        return "UNKNOWN", "UNKNOWN"
    text = _decode_text(result.stdout, "PACKAGE_OWNER").strip()
    if not text:
        return "UNKNOWN", "UNKNOWN"
    return "OBSERVED", "BOUND"


def collect_e2(
    root: str,
    runner: CommandRunner = run_contract_command,
    *,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = empty_requirement("E2")
    try:
        tree = analysis if analysis is not None else analyze_firstrun_tree(root)
    except (OSError, ReadonlyEvidenceError, FirstrunAnalysisError) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = (
            str(error)
            if isinstance(error, FirstrunAnalysisError)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", str(error))
            else "STOP_E2_COLLECTION_ERROR"
        )
        return envelope

    if tree["status"] == "ABSENT":
        envelope["status"] = "ABSENT"
        envelope["reason_code"] = "STOP_UNRESOLVED_IMPLEMENTATION"
        envelope["fields"]["firstrun_body_complete"] = _field(False, "ABSENT")
        return envelope

    try:
        owner_status, owner_binding = _owner_binding(
            runner,
            "/" + FIRSTRUN_RELATIVE,
        )
    except (OSError, ReadonlyCommandError, R2CCollectError):
        owner_status, owner_binding = "UNKNOWN", "UNKNOWN"
    unresolved = list(tree["unresolved"])
    if owner_status != "OBSERVED":
        unresolved.append("PACKAGE_OWNER_UNRESOLVED")

    envelope["method_ids"] = ["R1", "C3"]
    envelope["provenance"] = [
        {
            "file_role": "armbian_firstrun",
            "package_owner": owner_binding,
        }
    ]
    envelope["fields"]["firstrun_body_complete"] = _field(
        tree["main_complete"],
        "OBSERVED",
    )
    envelope["fields"]["body_sha256"] = _field(
        tree["main_sha256"],
        "OBSERVED" if tree["main_sha256"] else "UNKNOWN",
    )
    envelope["fields"]["identity_control_flow"] = _field(
        {
            "identity_relevant_lines": tree["identity_lines"],
            "source_file_count": len(tree["files"]),
        },
        "OBSERVED",
    )
    envelope["fields"]["helper_dependencies"] = _field(
        {
            "reference_count": len(tree["helper_dependencies"]),
            "source_file_count": len(tree["files"]),
            "dependencies": tree["helper_dependencies"],
        },
        "OBSERVED",
    )
    envelope["fields"]["conditions"] = _field(
        tree["conditions"],
        "OBSERVED",
    )
    envelope["fields"]["writes_declared_by_source"] = _field(
        tree["writes"],
        "OBSERVED",
    )

    complete = tree["main_complete"] and not unresolved
    envelope["complete"] = complete
    envelope["status"] = "OBSERVED" if complete else "UNKNOWN"
    envelope["reason_code"] = (
        None if complete else "STOP_UNRESOLVED_IMPLEMENTATION"
    )
    return envelope


def collect_e3(
    root: str,
    *,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = empty_requirement("E3")
    try:
        tree = analysis if analysis is not None else analyze_firstrun_tree(root)
        config = analyze_firstrun_config(
            root,
            tree["referenced_config_keys"],
        )
    except (OSError, ReadonlyEvidenceError, FirstrunAnalysisError) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = (
            str(error)
            if isinstance(error, FirstrunAnalysisError)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", str(error))
            else "STOP_E3_COLLECTION_ERROR"
        )
        return envelope

    envelope["method_ids"] = ["R1", "R2"]
    envelope["fields"]["firstrun_config_present"] = _field(
        config["present"],
        "OBSERVED" if config["present"] else "ABSENT",
    )
    envelope["fields"]["setting_names"] = _field(
        config["setting_names"],
        "OBSERVED",
    )
    envelope["fields"]["identity_setting_classes"] = _field(
        config["classes"],
        "OBSERVED" if config["parse_complete"] else "UNKNOWN",
    )
    envelope["fields"]["config_parse_complete"] = _field(
        config["parse_complete"],
        "OBSERVED",
    )
    envelope["fields"]["source_references"] = _field(
        tree["config_source_lines"],
        "OBSERVED" if tree["config_source_lines"] else "UNKNOWN",
    )

    complete = (
        tree["main_complete"]
        and config["present"]
        and config["parse_complete"]
        and not tree["unresolved"]
        and bool(tree["config_source_lines"])
        and bool(tree["referenced_config_keys"])
    )
    envelope["complete"] = complete
    envelope["status"] = "OBSERVED" if complete else "UNKNOWN"
    envelope["reason_code"] = None if complete else "STOP_CONFIG_UNRESOLVED"
    return envelope
