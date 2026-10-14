from __future__ import annotations

import errno
import fnmatch
import hashlib
import posixpath
import re
import shlex
from collections import Counter, deque
from collections.abc import Callable
from typing import Any

from n3w_t1_r2c_evidence_schema import REQUIREMENT_FIELDS
from n3w_t1_r2c_readonly_commands import (
    CommandResult,
    ReadonlyCommandError,
    run_contract_command,
)
from n3w_t1_r2c_readonly_files import (
    ReadonlyEvidenceError,
    inspect_metadata,
    read_bounded_text,
    read_symlink_target,
    scan_bounded,
)

CommandRunner = Callable[..., CommandResult]
UNIT_RE = re.compile(
    r"[A-Za-z0-9_.@:-]+\.(?:service|socket|target|mount|path|timer)\Z"
)
HEX32_RE = re.compile(r"[0-9a-fA-F]{32}\Z")
REASON_RE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")
BACKTICK = chr(96)
SYSTEMD_FILE_ROOTS = (
    "/etc/systemd/system/",
    "/run/systemd/system/",
    "/usr/lib/systemd/system/",
    "/lib/systemd/system/",
)
SSH_DEFAULT_HOST_KEYS = {
    "/etc/ssh/ssh_host_ecdsa_key": "ECDSA",
    "/etc/ssh/ssh_host_ed25519_key": "ED25519",
    "/etc/ssh/ssh_host_rsa_key": "RSA",
}
SSH_UNITS = (
    "sshd-keygen.service",
    "ssh.service",
    "sshd.service",
    "ssh.socket",
)
E6_UNITS = (
    "NetworkManager.service",
    "NetworkManager-wait-online.service",
    "netplan-configure.service",
    "systemd-networkd.service",
)
E7_UNITS = (
    "systemd-journald.service",
    "systemd-journal-flush.service",
    "systemd-journald@.service",
)
E9_UNITS = (
    "systemd-firstboot.service",
    "systemd-machine-id-commit.service",
    "armbian-firstrun.service",
    "sshd-keygen.service",
    "ssh.service",
    "sshd.service",
    "ssh.socket",
    "NetworkManager.service",
    "NetworkManager-wait-online.service",
    "netplan-configure.service",
    "systemd-networkd.service",
    "network-pre.target",
    "network.target",
    "network-online.target",
    "systemd-journald.service",
    "systemd-journal-flush.service",
    "systemd-random-seed.service",
)
NETWORK_IDENTITY_KEYS = {
    "uuid",
    "stable-id",
    "interface-name",
    "cloned-mac-address",
    "generate-mac-address-mask",
    "dhcp-client-id",
    "dhcp-iaid",
    "dhcp-duid",
    "addr-gen-mode",
    "renderer",
    "dhcp-identifier",
    "dhcp4",
    "dhcp6",
    "macaddress",
    "set-name",
}
DHCP_KEYS = {
    "dhcp-client-id",
    "dhcp-iaid",
    "dhcp-duid",
    "dhcp-identifier",
    "dhcp4",
    "dhcp6",
}
MAC_KEYS = {
    "cloned-mac-address",
    "generate-mac-address-mask",
    "addr-gen-mode",
    "macaddress",
}
R3_TOTAL_ENTRY_LIMIT = 512


class RemainingCollectError(RuntimeError):
    pass


def _field(value: Any = None, status: str = "NOT_EXECUTED") -> dict[str, Any]:
    return {"value": value, "status": status}


def _empty_requirement(requirement_id: str) -> dict[str, Any]:
    if requirement_id not in REQUIREMENT_FIELDS:
        raise RemainingCollectError("unknown_requirement")
    return {
        "status": "NOT_EXECUTED",
        "complete": False,
        "reason_code": None,
        "method_ids": [],
        "provenance": [],
        "fields": {
            name: _field()
            for name in sorted(REQUIREMENT_FIELDS[requirement_id])
        },
    }


def _reason(error: BaseException, fallback: str) -> str:
    value = str(error)
    if isinstance(error, RemainingCollectError) and REASON_RE.fullmatch(value):
        return value
    if isinstance(error, ReadonlyEvidenceError):
        readonly_reasons = {
            "file_changed_during_read": "STOP_READONLY_FILE_CHANGED",
            "file_too_large": "STOP_READONLY_FILE_TOO_LARGE",
            "invalid_read_limit": "STOP_READONLY_INVALID_READ_LIMIT",
            "invalid_relative_path": "STOP_READONLY_INVALID_PATH",
            "invalid_scan_depth": "STOP_READONLY_INVALID_SCAN_DEPTH",
            "invalid_scan_limit": "STOP_READONLY_INVALID_SCAN_LIMIT",
            "not_regular_file": "STOP_READONLY_NOT_REGULAR",
            "not_symlink": "STOP_READONLY_NOT_SYMLINK",
            "scan_entry_limit": "STOP_TRUNCATED",
        }
        if value in readonly_reasons:
            return readonly_reasons[value]
    if isinstance(error, OSError) and error.errno in errno.errorcode:
        reason = f"STOP_FILESYSTEM_{errno.errorcode[error.errno]}"
        if REASON_RE.fullmatch(reason):
            return reason
    return fallback


def _decode(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RemainingCollectError(f"STOP_{label}_NOT_UTF8") from error


def _metadata(root: str, relative: str) -> dict[str, Any]:
    try:
        return inspect_metadata(root, relative)
    except FileNotFoundError:
        return {"status": "ABSENT", "kind": None, "size": None}


def _resolve_usr_merge_relative(
    root: str,
    relative: str,
) -> tuple[str | None, str | None]:
    if relative != "lib" and not relative.startswith("lib/"):
        return relative, None
    try:
        metadata = _metadata(root, "lib")
        if metadata["status"] == "ABSENT" or metadata["kind"] == "directory":
            return relative, None
        if metadata["kind"] != "symlink":
            return None, "USR_MERGE_ALIAS_UNRESOLVED"
        target = read_symlink_target(root, "lib")
    except (OSError, ReadonlyEvidenceError):
        return None, "USR_MERGE_ALIAS_UNREADABLE"
    if target not in {"usr/lib", "/usr/lib"}:
        return None, "USR_MERGE_ALIAS_UNAPPROVED"
    suffix = relative.removeprefix("lib").lstrip("/")
    resolved = "usr/lib"
    if suffix:
        resolved = f"{resolved}/{suffix}"
    return resolved, None


def _scan(
    root: str,
    relative: str,
    *,
    max_depth: int,
) -> tuple[list[dict[str, Any]], str]:
    metadata = _metadata(root, relative)
    if metadata["status"] == "ABSENT":
        return [], "ABSENT"
    if metadata["kind"] != "directory":
        raise RemainingCollectError("STOP_EXPECTED_DIRECTORY")
    try:
        return (
            scan_bounded(root, relative, max_depth=max_depth),
            "OBSERVED",
        )
    except FileNotFoundError:
        return [], "ABSENT"
    except ReadonlyEvidenceError as error:
        if str(error) == "scan_entry_limit":
            raise RemainingCollectError("STOP_TRUNCATED") from error
        raise


def _add_scan_count(
    current: int,
    records: list[dict[str, Any]],
) -> int:
    total = current + len(records)
    if total > R3_TOTAL_ENTRY_LIMIT:
        raise RemainingCollectError("STOP_TRUNCATED")
    return total


def _read_regular(
    root: str,
    relative: str,
    *,
    limit: int = 1024 * 1024,
) -> str:
    metadata = _metadata(root, relative)
    if metadata["status"] == "ABSENT":
        raise RemainingCollectError("STOP_REQUIRED_FILE_ABSENT")
    if metadata["kind"] != "regular":
        raise RemainingCollectError("STOP_REQUIRED_FILE_NOT_REGULAR")
    return _decode(
        read_bounded_text(root, relative, limit=limit),
        "CONFIG",
    )


def _systemd_path_class(path: str) -> str:
    if any(path.startswith(root) for root in SYSTEMD_FILE_ROOTS):
        return "APPROVED_SYSTEMD_ROOT"
    return "CUSTOM"


def _relative_absolute(path: str) -> str:
    if not path.startswith("/") or "\x00" in path:
        raise RemainingCollectError("STOP_PATH_NOT_ABSOLUTE")
    normalized = posixpath.normpath(path)
    if normalized != path or normalized == "/":
        raise RemainingCollectError("STOP_PATH_NOT_CANONICAL")
    return normalized.lstrip("/")


def _parse_unit_set(value: str) -> list[str]:
    return sorted(
        {
            token
            for token in value.split()
            if UNIT_RE.fullmatch(token)
        }
    )


def _condition_names(value: str) -> list[str]:
    return sorted(set(re.findall(r"Condition[A-Za-z0-9_]+", value)))


def _boolean(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in {"yes", "true", "1"}:
        return True
    if lowered in {"no", "false", "0"}:
        return False
    return None


def _parse_systemctl_show(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key] = value
    return values


def _unit_file_bindings(
    root: str,
    fragment_path: str,
    dropin_paths: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    bindings: list[dict[str, Any]] = []
    unresolved: list[str] = []
    paths: list[tuple[str, str]] = []
    if fragment_path:
        paths.append(("fragment", fragment_path))
    if dropin_paths:
        if any(
            marker in dropin_paths
            for marker in ("'", '"', "\\x")
        ):
            return [], ["UNIT_DROPIN_PATHS_UNRESOLVED"]
        paths.extend(
            ("dropin", item)
            for item in dropin_paths.split()
        )
    for role, path in paths:
        if _systemd_path_class(path) != "APPROVED_SYSTEMD_ROOT":
            unresolved.append("UNIT_FILE_OUTSIDE_APPROVED_ROOT")
            continue
        try:
            relative = _relative_absolute(path)
            relative, alias_unresolved = _resolve_usr_merge_relative(
                root,
                relative,
            )
            if alias_unresolved or relative is None:
                unresolved.append(
                    alias_unresolved or "USR_MERGE_ALIAS_UNRESOLVED"
                )
                continue
            metadata = _metadata(root, relative)
            if (
                metadata["status"] != "OBSERVED"
                or metadata["kind"] != "regular"
            ):
                unresolved.append("UNIT_FILE_NOT_REGULAR")
                continue
            data = read_bounded_text(root, relative)
        except (
            OSError,
            ReadonlyEvidenceError,
            RemainingCollectError,
        ):
            unresolved.append("UNIT_FILE_UNREADABLE")
            continue
        bindings.append(
            {
                "role": role,
                "path_class": "APPROVED_SYSTEMD_ROOT",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return bindings, sorted(set(unresolved))


def _unit_snapshot(
    root: str,
    unit: str,
    runner: CommandRunner,
    approved_units: set[str],
) -> dict[str, Any]:
    try:
        result = runner(
            "C4_UNIT",
            value=unit,
            approved_units=approved_units,
        )
    except (OSError, ReadonlyCommandError) as error:
        return {
            "unit": unit,
            "status": "UNKNOWN",
            "reason": "C4_UNIT_ERROR",
            "error_class": type(error).__name__,
        }
    if result.returncode != 0:
        return {
            "unit": unit,
            "status": "UNKNOWN",
            "reason": "C4_UNIT_NONZERO",
        }
    values = _parse_systemctl_show(_decode(result.stdout, "UNIT"))
    load_state = values.get("LoadState", "")
    if load_state == "not-found":
        return {
            "unit": unit,
            "status": "ABSENT",
            "load_state": "not-found",
        }
    if not load_state:
        return {
            "unit": unit,
            "status": "UNKNOWN",
            "reason": "LOAD_STATE_MISSING",
        }
    fragment_path = values.get("FragmentPath", "")
    masked_null = load_state == "masked" and fragment_path == "/dev/null"
    bindings, unresolved = _unit_file_bindings(
        root,
        "" if masked_null else fragment_path,
        values.get("DropInPaths", ""),
    )
    if masked_null:
        bindings.insert(
            0,
            {
                "role": "fragment",
                "path_class": "MASKED_NULL",
                "sha256": None,
            },
        )
    if load_state == "loaded" and not fragment_path:
        unresolved.append("UNIT_FRAGMENT_PATH_MISSING")
    timestamps: dict[str, int | None] = {}
    for key, raw in (
        (
            "active_enter",
            values.get("ActiveEnterTimestampMonotonic", ""),
        ),
        (
            "inactive_exit",
            values.get("InactiveExitTimestampMonotonic", ""),
        ),
    ):
        timestamps[key] = (
            int(raw)
            if raw.isdigit() and int(raw) > 0
            else None
        )
    exec_start = values.get("ExecStart", "")
    exec_aux_present = bool(
        values.get("ExecStartPre", "").strip()
        or values.get("ExecStartPost", "").strip()
    )
    exec_class = "OTHER"
    if (
        "ssh-keygen" in exec_start
        and re.search(r"(?:^|\s)-A(?:\s|;|$)", exec_start)
    ):
        exec_class = "SSH_KEYGEN_ALL"
    return {
        "unit": unit,
        "status": "OBSERVED" if not unresolved else "UNKNOWN",
        "load_state": load_state,
        "active_state": values.get("ActiveState") or None,
        "unit_file_state": values.get("UnitFileState") or None,
        "before": _parse_unit_set(values.get("Before", "")),
        "after": _parse_unit_set(values.get("After", "")),
        "wants": _parse_unit_set(values.get("Wants", "")),
        "requires": _parse_unit_set(values.get("Requires", "")),
        "triggered_by": _parse_unit_set(
            values.get("TriggeredBy", "")
        ),
        "triggers": _parse_unit_set(values.get("Triggers", "")),
        "condition_result": _boolean(
            values.get("ConditionResult", "")
        ),
        "condition_names": _condition_names(
            values.get("Conditions", "")
        ),
        "exec_class": exec_class,
        "exec_aux_present": exec_aux_present,
        "timestamps": timestamps,
        "unit_file_bindings": bindings,
        "unresolved": sorted(set(unresolved)),
    }


def _snapshot_units(
    root: str,
    units: tuple[str, ...],
    runner: CommandRunner,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    approved = set(units)
    snapshots = {
        unit: _unit_snapshot(root, unit, runner, approved)
        for unit in units
    }
    unresolved = sorted(
        {
            f"UNIT_UNKNOWN_{unit}"
            for unit, snapshot in snapshots.items()
            if snapshot["status"] == "UNKNOWN"
        }
    )
    return snapshots, unresolved


def _unit_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    wanted = (
        "unit",
        "status",
        "load_state",
        "active_state",
        "unit_file_state",
        "before",
        "after",
        "wants",
        "requires",
        "triggered_by",
        "triggers",
        "condition_result",
        "condition_names",
        "exec_class",
        "exec_aux_present",
        "timestamps",
        "unit_file_bindings",
    )
    return {
        key: snapshot.get(key)
        for key in wanted
        if key in snapshot
    }


def _config_value_class(value: str, key: str) -> str:
    stripped = value.strip().strip("'\"")
    lowered = stripped.lower()
    if any(
        marker in stripped
        for marker in ("$(", BACKTICK, "{{", "}}")
    ):
        return "UNKNOWN"
    if lowered in {
        "",
        "auto",
        "default",
        "yes",
        "no",
        "true",
        "false",
    }:
        return "DEFAULT"
    if (
        key in MAC_KEYS
        and lowered
        in {"random", "stable", "preserve", "permanent"}
    ):
        return "GENERATED"
    if (
        key in DHCP_KEYS
        and lowered
        in {
            "mac",
            "stable",
            "duid",
            "duid-only",
            "iaid+duid",
            "none",
        }
    ):
        return "GENERATED"
    if "$" in stripped or "%" in stripped:
        return "GENERATED"
    return "CUSTOM"


def _aggregate_classes(
    items: list[tuple[str, str]],
    wanted: set[str],
) -> dict[str, dict[str, int]]:
    per_key: dict[str, Counter[str]] = {}
    for key, classification in items:
        if key not in wanted:
            continue
        per_key.setdefault(key, Counter())[classification] += 1
    return {
        key: dict(sorted(counter.items()))
        for key, counter in sorted(per_key.items())
    }


def _parse_ini_identity(
    text: str,
) -> tuple[list[tuple[str, str]], list[str]]:
    fields: list[tuple[str, str]] = []
    unresolved: set[str] = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", ";", "[")):
            continue
        if "=" not in stripped:
            if any(
                key in stripped.lower()
                for key in NETWORK_IDENTITY_KEYS
            ):
                unresolved.add("NETWORK_CONFIG_SYNTAX_UNKNOWN")
            continue
        key, value = stripped.split("=", 1)
        key = key.strip().lower()
        if key in NETWORK_IDENTITY_KEYS:
            classification = _config_value_class(value, key)
            fields.append((key, classification))
            if classification == "UNKNOWN":
                unresolved.add("NETWORK_VALUE_UNKNOWN")
    return fields, sorted(unresolved)


def _parse_netplan_identity(
    text: str,
) -> tuple[list[tuple[str, str]], list[str]]:
    fields: list[tuple[str, str]] = []
    unresolved: set[str] = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(
            r"([A-Za-z0-9_-]+)\s*:\s*(.*)\Z",
            stripped,
        )
        if match is None:
            if any(
                key in stripped.lower()
                for key in NETWORK_IDENTITY_KEYS
            ):
                unresolved.add("NETPLAN_SYNTAX_UNKNOWN")
            continue
        key, value = match.groups()
        key = key.lower()
        if key in NETWORK_IDENTITY_KEYS:
            classification = _config_value_class(value, key)
            fields.append((key, classification))
            if classification == "UNKNOWN":
                unresolved.add("NETPLAN_VALUE_UNKNOWN")
    return fields, sorted(unresolved)


def _sshd_config_analysis(root: str) -> dict[str, Any]:
    records, status = _scan(root, "etc/ssh", max_depth=2)
    if status == "ABSENT":
        return {
            "hostkey_classes": [],
            "hostcertificate_classes": [],
            "include_count": 0,
            "port_class": "UNKNOWN",
            "unresolved": ["SSH_CONFIG_ROOT_ABSENT"],
        }
    regulars = {
        "/" + record["relative"]
        for record in records
        if record["kind"] == "regular"
    }
    main = "/etc/ssh/sshd_config"
    if main not in regulars:
        return {
            "hostkey_classes": [],
            "hostcertificate_classes": [],
            "include_count": 0,
            "port_class": "UNKNOWN",
            "unresolved": ["SSHD_CONFIG_ABSENT"],
        }
    queue: deque[str] = deque([main])
    visited: set[str] = set()
    hostkeys: list[str] = []
    hostcerts: list[str] = []
    port_classes: list[str] = []
    unresolved: set[str] = set()
    while queue:
        path = queue.popleft()
        if path in visited:
            continue
        if len(visited) >= 16:
            unresolved.add("SSH_INCLUDE_LIMIT")
            break
        visited.add(path)
        try:
            text = _read_regular(
                root,
                _relative_absolute(path),
            )
        except (
            OSError,
            ReadonlyEvidenceError,
            RemainingCollectError,
        ):
            unresolved.add("SSH_CONFIG_UNREADABLE")
            continue
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                parts = shlex.split(
                    stripped,
                    comments=True,
                    posix=True,
                )
            except ValueError:
                unresolved.add("SSH_CONFIG_SYNTAX_UNKNOWN")
                continue
            if not parts:
                continue
            keyword = parts[0].lower()
            values = parts[1:]
            if keyword == "include":
                for pattern in values:
                    if (
                        not pattern.startswith("/etc/ssh/")
                        or any(
                            marker in pattern
                            for marker in (
                                "$",
                                BACKTICK,
                                "$(",
                                "~",
                            )
                        )
                    ):
                        unresolved.add(
                            "SSH_INCLUDE_OUTSIDE_APPROVED_ROOT"
                        )
                        continue
                    matched = sorted(
                        item
                        for item in regulars
                        if fnmatch.fnmatch(item, pattern)
                    )
                    queue.extend(matched)
            elif keyword == "hostkey":
                for value in values:
                    if value in SSH_DEFAULT_HOST_KEYS:
                        hostkeys.append("DEFAULT_APPROVED")
                    elif any(
                        marker in value
                        for marker in (
                            "$",
                            "%",
                            BACKTICK,
                            "$(",
                        )
                    ):
                        hostkeys.append("UNKNOWN")
                        unresolved.add(
                            "SSH_HOSTKEY_PATH_UNKNOWN"
                        )
                    else:
                        hostkeys.append("CUSTOM")
                        unresolved.add(
                            "SSH_HOSTKEY_PATH_CUSTOM"
                        )
            elif keyword == "hostcertificate":
                for value in values:
                    if value.startswith("/etc/ssh/"):
                        hostcerts.append(
                            "APPROVED_SSH_ROOT"
                        )
                    else:
                        hostcerts.append("CUSTOM")
                        unresolved.add(
                            "SSH_HOSTCERT_PATH_CUSTOM"
                        )
            elif keyword == "port":
                for value in values:
                    if value == "22":
                        port_classes.append("DEFAULT")
                    elif value.isdigit():
                        port_classes.append("CUSTOM")
                    else:
                        port_classes.append("UNKNOWN")
                        unresolved.add(
                            "SSH_PORT_UNRESOLVED"
                        )
    if not hostkeys:
        hostkeys.append("DEFAULT_UNBOUND")
        unresolved.add("SSH_HOSTKEY_DEFAULT_SEMANTICS_UNBOUND")
    port_class = "DEFAULT"
    if "UNKNOWN" in port_classes:
        port_class = "UNKNOWN"
    elif "CUSTOM" in port_classes:
        port_class = "CUSTOM"
    return {
        "hostkey_classes": sorted(hostkeys),
        "hostcertificate_classes": sorted(hostcerts),
        "include_count": max(0, len(visited) - 1),
        "port_class": port_class,
        "unresolved": sorted(unresolved),
    }


def _listener_classification(
    result: CommandResult,
) -> dict[str, Any]:
    if result.returncode != 0:
        return {
            "status": "UNKNOWN",
            "classes": [],
            "count": 0,
        }
    classes: list[str] = []
    for raw in _decode(result.stdout, "LISTEN").splitlines():
        parts = raw.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if not local.endswith((":22", "]:22")):
            continue
        host = local.rsplit(":", 1)[0].strip("[]")
        if host in {"0.0.0.0", "::", "*"}:
            classes.append("WILDCARD")
        elif host in {"127.0.0.1", "::1", "localhost"}:
            classes.append("LOOPBACK")
        else:
            classes.append("SPECIFIC")
    return {
        "status": "OBSERVED",
        "classes": sorted(classes),
        "count": len(classes),
    }


def collect_e5(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = _empty_requirement("E5")
    try:
        records, ssh_root_status = _scan(
            root,
            "etc/ssh",
            max_depth=2,
        )
        record_map = {
            "/" + item["relative"]: item
            for item in records
        }
        key_metadata: dict[str, dict[str, Any]] = {}
        present_families: list[str] = []
        for path, family in SSH_DEFAULT_HOST_KEYS.items():
            record = record_map.get(path)
            if record is None:
                key_metadata[family] = {
                    "present": False,
                    "status": "ABSENT",
                }
                continue
            if record["kind"] != "regular":
                key_metadata[family] = {
                    "present": True,
                    "status": "UNKNOWN",
                    "kind": record["kind"],
                }
                continue
            key_metadata[family] = {
                "present": True,
                "status": "OBSERVED",
                "mode": record["mode"],
                "size_bytes": record["size"],
            }
            present_families.append(family)
        config = _sshd_config_analysis(root)
        units, unit_unresolved = _snapshot_units(
            root,
            SSH_UNITS,
            runner,
        )
        keygen = units["sshd-keygen.service"]
        try:
            owner = runner(
                "C3_OWNER",
                value="/usr/bin/ssh-keygen",
                approved_paths={"/usr/bin/ssh-keygen"},
            )
            helper_binding = (
                "BOUND"
                if owner.returncode == 0
                else "UNKNOWN"
            )
        except (OSError, ReadonlyCommandError):
            helper_binding = "UNKNOWN"
        try:
            listener = _listener_classification(
                runner("C6_LISTEN")
            )
        except (OSError, ReadonlyCommandError):
            listener = {
                "status": "UNKNOWN",
                "classes": [],
                "count": 0,
            }
    except (
        OSError,
        ReadonlyEvidenceError,
        RemainingCollectError,
    ) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = _reason(
            error,
            "STOP_E5_COLLECTION_ERROR",
        )
        return envelope

    unresolved = set(config["unresolved"]) | set(
        unit_unresolved
    )
    if ssh_root_status != "OBSERVED":
        unresolved.add("SSH_ROOT_UNRESOLVED")
    if any(
        item["status"] == "UNKNOWN"
        for item in key_metadata.values()
    ):
        unresolved.add("SSH_KEY_METADATA_UNKNOWN")
    if keygen.get("status") != "OBSERVED":
        unresolved.add("SSH_KEYGEN_UNIT_UNKNOWN")
    if keygen.get("exec_class") != "SSH_KEYGEN_ALL":
        unresolved.add("SSH_KEYGEN_EXEC_UNKNOWN")
    if helper_binding != "BOUND":
        unresolved.add("SSH_KEYGEN_PACKAGE_OWNER_UNKNOWN")
    if listener["status"] != "OBSERVED":
        unresolved.add("SSH_LISTENER_UNKNOWN")
    for unit_name in SSH_UNITS:
        snapshot = units[unit_name]
        if (
            snapshot.get("status") == "OBSERVED"
            and snapshot.get("exec_aux_present")
        ):
            unresolved.add(
                "SSH_AUX_HELPER_UNRESOLVED"
            )
    for exposure_name in (
        "ssh.service",
        "sshd.service",
        "ssh.socket",
    ):
        exposure = units[exposure_name]
        if exposure.get("status") != "OBSERVED":
            continue
        ordered_after_keygen = (
            exposure_name in keygen.get("before", [])
            or "sshd-keygen.service" in exposure.get("after", [])
        )
        ordered_before_keygen = (
            exposure_name in keygen.get("after", [])
            or "sshd-keygen.service" in exposure.get("before", [])
        )
        if ordered_before_keygen:
            unresolved.add("SSH_EXPOSURE_BEFORE_KEYGEN")
        elif not ordered_after_keygen:
            unresolved.add("SSH_KEYGEN_EXPOSURE_ORDER_UNKNOWN")

    envelope["method_ids"] = [
        "R1",
        "R2",
        "R3",
        "C3",
        "C4",
        "C6",
    ]
    envelope["fields"]["ssh_key_metadata"] = _field(
        key_metadata,
        "OBSERVED",
    )
    envelope["fields"]["key_families"] = _field(
        sorted(present_families),
        "OBSERVED",
    )
    envelope["fields"]["keygen_conditions"] = _field(
        {
            "condition_names": keygen.get(
                "condition_names",
                [],
            ),
            "condition_result": keygen.get(
                "condition_result"
            ),
            "exec_class": keygen.get("exec_class"),
        },
        (
            "OBSERVED"
            if keygen.get("status") == "OBSERVED"
            else "UNKNOWN"
        ),
    )
    envelope["fields"]["ssh_units"] = _field(
        {
            unit: _unit_summary(snapshot)
            for unit, snapshot in units.items()
        },
        (
            "OBSERVED"
            if not unit_unresolved
            else "UNKNOWN"
        ),
    )
    envelope["fields"]["hostkey_path_classes"] = _field(
        {
            "hostkey": config["hostkey_classes"],
            "hostcertificate": config[
                "hostcertificate_classes"
            ],
            "include_count": config["include_count"],
            "port_class": config["port_class"],
        },
        (
            "OBSERVED"
            if not config["unresolved"]
            else "UNKNOWN"
        ),
    )
    envelope["fields"]["package_helpers"] = _field(
        {"ssh_keygen_owner": helper_binding},
        (
            "OBSERVED"
            if helper_binding == "BOUND"
            else "UNKNOWN"
        ),
    )
    envelope["fields"]["socket_activation"] = _field(
        {
            "ssh_socket": _unit_summary(
                units["ssh.socket"]
            ),
            "listener": listener,
        },
        (
            "OBSERVED"
            if listener["status"] == "OBSERVED"
            else "UNKNOWN"
        ),
    )
    complete = not unresolved
    envelope["status"] = (
        "OBSERVED" if complete else "UNKNOWN"
    )
    envelope["complete"] = complete
    envelope["reason_code"] = (
        None
        if complete
        else "STOP_SSH_IDENTITY_UNKNOWN"
    )
    return envelope


def _network_role(relative: str) -> str:
    lowered = relative.lower()
    if "system-connections/" in lowered:
        return "PROFILE"
    if (
        lowered.endswith((".yaml", ".yml"))
        or "/netplan/" in lowered
    ):
        return "NETPLAN"
    if (
        lowered.endswith(".network")
        or "/systemd/network/" in lowered
    ):
        return "SYSTEMD_NETWORK"
    if lowered.endswith((".conf", "networkmanager.conf")):
        return "NM_CONFIG"
    if "secret_key" in lowered:
        return "SECRET_KEY_METADATA"
    if "lease" in lowered:
        return "LEASE_METADATA"
    return "STATE_METADATA"


def collect_e6(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = _empty_requirement("E6")
    roots = (
        ("NM_VAR", "var/lib/NetworkManager", 2),
        ("NM_ETC", "etc/NetworkManager", 3),
        ("NM_RUN", "run/NetworkManager", 3),
        (
            "NM_USR_CONF",
            "usr/lib/NetworkManager/conf.d",
            2,
        ),
        ("NETPLAN_ETC", "etc/netplan", 2),
        ("NETPLAN_RUN", "run/netplan", 2),
        ("NETPLAN_LIB", "lib/netplan", 2),
        (
            "SYSTEMD_NETWORK_RUN",
            "run/systemd/network",
            2,
        ),
    )
    inventory: dict[str, dict[str, Any]] = {}
    profile_records: list[dict[str, Any]] = []
    netplan_records: list[dict[str, Any]] = []
    identity_fields: list[tuple[str, str]] = []
    unresolved: set[str] = set()
    total_entries = 0
    try:
        for role, relative, depth in roots:
            scan_relative, alias_unresolved = _resolve_usr_merge_relative(
                root,
                relative,
            )
            if alias_unresolved or scan_relative is None:
                unresolved.add(
                    alias_unresolved or "USR_MERGE_ALIAS_UNRESOLVED"
                )
                inventory[role] = {
                    "status": "UNKNOWN",
                    "entry_count": 0,
                    "role_counts": {},
                }
                continue
            records, status = _scan(
                root,
                scan_relative,
                max_depth=depth,
            )
            total_entries = _add_scan_count(
                total_entries,
                records,
            )
            role_counts = Counter(
                _network_role(item["relative"])
                for item in records
            )
            inventory[role] = {
                "status": status,
                "entry_count": len(records),
                "role_counts": dict(
                    sorted(role_counts.items())
                ),
            }
            for item in records:
                file_role = _network_role(
                    item["relative"]
                )
                if item["kind"] == "symlink":
                    unresolved.add(
                        "NETWORK_STATE_SYMLINK"
                    )
                    continue
                if item["kind"] != "regular":
                    continue
                if (
                    file_role == "STATE_METADATA"
                    and role in {"NM_VAR", "NM_RUN"}
                ):
                    unresolved.add(
                        "NETWORK_STATE_UNCLASSIFIED"
                    )
                    continue
                if file_role not in {
                    "PROFILE",
                    "NETPLAN",
                    "NM_CONFIG",
                    "SYSTEMD_NETWORK",
                }:
                    continue
                try:
                    text = _decode(
                        read_bounded_text(
                            root,
                            item["relative"],
                        ),
                        "NETWORK_CONFIG",
                    )
                except (
                    OSError,
                    ReadonlyEvidenceError,
                    RemainingCollectError,
                ):
                    unresolved.add(
                        "NETWORK_CONFIG_UNREADABLE"
                    )
                    continue
                if file_role == "NETPLAN":
                    fields, parse_unresolved = (
                        _parse_netplan_identity(text)
                    )
                else:
                    fields, parse_unresolved = (
                        _parse_ini_identity(text)
                    )
                identity_fields.extend(fields)
                unresolved.update(parse_unresolved)
                summary = {
                    "role": file_role,
                    "identity_field_count": len(fields),
                    "field_names": sorted(
                        {key for key, _ in fields}
                    ),
                }
                if file_role == "PROFILE":
                    profile_records.append(summary)
                if file_role == "NETPLAN":
                    netplan_records.append(summary)
        units, unit_unresolved = _snapshot_units(
            root,
            E6_UNITS,
            runner,
        )
        unresolved.update(unit_unresolved)
        renderer_units = {
            unit
            for unit in (
                "NetworkManager.service",
                "systemd-networkd.service",
                "netplan-configure.service",
            )
            if units[unit].get("status") == "OBSERVED"
        }
        if not renderer_units:
            unresolved.add("NETWORK_RENDERER_UNRESOLVED")
        if renderer_units and not identity_fields:
            unresolved.add(
                "NETWORK_DEFAULT_SEMANTICS_UNBOUND"
            )
    except (
        OSError,
        ReadonlyEvidenceError,
        RemainingCollectError,
    ) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = _reason(
            error,
            "STOP_E6_COLLECTION_ERROR",
        )
        return envelope

    dhcp_classes = _aggregate_classes(
        identity_fields,
        DHCP_KEYS,
    )
    mac_classes = _aggregate_classes(
        identity_fields,
        MAC_KEYS,
    )
    if identity_fields:
        unresolved.add("NETWORK_PRECEDENCE_UNBOUND")
    effective = {
        "source_roles": sorted(
            role
            for role, item in inventory.items()
            if item["status"] == "OBSERVED"
        ),
        "identity_field_names": sorted(
            {key for key, _ in identity_fields}
        ),
        "identity_field_count": len(identity_fields),
        "precedence_binding": (
            "UNBOUND_TO_INSTALLED_SEMANTICS"
            if identity_fields
            else "NO_IDENTITY_FIELDS_OBSERVED"
        ),
        "unit_statuses": {
            unit: snapshot.get("status")
            for unit, snapshot in sorted(units.items())
        },
    }
    unknown = bool(unresolved)
    envelope["method_ids"] = ["R2", "R3", "C4"]
    envelope["fields"]["nm_state_inventory"] = _field(
        inventory,
        "OBSERVED",
    )
    envelope["fields"]["profile_inventory"] = _field(
        {
            "count": len(profile_records),
            "profiles": [
                {**item, "ordinal": index + 1}
                for index, item in enumerate(
                    profile_records
                )
            ],
        },
        "OBSERVED",
    )
    envelope["fields"]["netplan_inventory"] = _field(
        {
            "count": len(netplan_records),
            "documents": [
                {**item, "ordinal": index + 1}
                for index, item in enumerate(
                    netplan_records
                )
            ],
        },
        "OBSERVED",
    )
    envelope["fields"][
        "effective_identity_sources"
    ] = _field(effective, "OBSERVED")
    envelope["fields"]["dhcp_identity_classes"] = (
        _field(dhcp_classes, "OBSERVED")
    )
    envelope["fields"]["mac_identity_classes"] = (
        _field(mac_classes, "OBSERVED")
    )
    envelope["fields"]["unknown_identity_state"] = (
        _field(unknown, "OBSERVED")
    )
    envelope["complete"] = not unknown
    envelope["status"] = (
        "OBSERVED" if not unknown else "UNKNOWN"
    )
    envelope["reason_code"] = (
        None
        if not unknown
        else "STOP_NETWORK_IDENTITY_UNKNOWN"
    )
    return envelope


def _current_machine_id(root: str) -> str | None:
    try:
        metadata = _metadata(root, "etc/machine-id")
        if (
            metadata["status"] != "OBSERVED"
            or metadata["kind"] != "regular"
        ):
            return None
        value = _decode(
            read_bounded_text(
                root,
                "etc/machine-id",
                limit=256,
            ),
            "MACHINE_ID",
        ).strip()
    except (
        OSError,
        ReadonlyEvidenceError,
        RemainingCollectError,
    ):
        return None
    return (
        value.lower()
        if HEX32_RE.fullmatch(value)
        else None
    )


def _journald_policy(
    root: str,
) -> tuple[dict[str, Any], list[str]]:
    candidates: list[str] = []
    main = "etc/systemd/journald.conf"
    if _metadata(root, main)["status"] == "OBSERVED":
        candidates.append(main)
    for directory in (
        "usr/lib/systemd/journald.conf.d",
        "run/systemd/journald.conf.d",
        "etc/systemd/journald.conf.d",
    ):
        records, _ = _scan(
            root,
            directory,
            max_depth=0,
        )
        candidates.extend(
            item["relative"]
            for item in records
            if (
                item["kind"] == "regular"
                and item["relative"].endswith(".conf")
            )
        )
    observed: dict[str, list[str]] = {
        "Storage": [],
        "SplitMode": [],
    }
    unresolved: set[str] = set()
    for relative in candidates:
        try:
            text = _decode(
                read_bounded_text(root, relative),
                "JOURNALD_CONFIG",
            )
        except (
            OSError,
            ReadonlyEvidenceError,
            RemainingCollectError,
        ):
            unresolved.add(
                "JOURNALD_CONFIG_UNREADABLE"
            )
            continue
        section = ""
        for raw in text.splitlines():
            stripped = raw.strip()
            if (
                not stripped
                or stripped.startswith(("#", ";"))
            ):
                continue
            if (
                stripped.startswith("[")
                and stripped.endswith("]")
            ):
                section = stripped[1:-1]
                continue
            if (
                section not in {"", "Journal"}
                or "=" not in stripped
            ):
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key in observed:
                observed[key].append(
                    value.strip().lower()
                )
    result: dict[str, Any] = {
        "source_count": len(candidates)
    }
    for key, values in observed.items():
        distinct = sorted(set(values))
        if len(distinct) == 1:
            result[key.lower()] = {
                "class": "EXPLICIT",
                "value_class": distinct[0].upper(),
            }
        elif not distinct:
            result[key.lower()] = {
                "class": "DEFAULT_UNBOUND",
                "value_class": None,
            }
            unresolved.add(
                "JOURNALD_DEFAULT_SEMANTICS_UNBOUND"
            )
        else:
            result[key.lower()] = {
                "class": "CONFLICTING",
                "value_class": None,
            }
            unresolved.add(
                "JOURNALD_POLICY_CONFLICT"
            )
    return result, sorted(unresolved)


def collect_e7(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = _empty_requirement("E7")
    current_id = _current_machine_id(root)
    roots: dict[str, Any] = {}
    relation = Counter()
    unresolved: set[str] = set()
    total_entries = 0
    try:
        for role, relative in (
            ("PERSISTENT", "var/log/journal"),
            ("RUNTIME", "run/log/journal"),
        ):
            root_metadata = _metadata(root, relative)
            if (
                root_metadata["status"] == "OBSERVED"
                and root_metadata["kind"] != "directory"
            ):
                roots[role] = {
                    "status": "UNKNOWN",
                    "kind": root_metadata["kind"],
                    "entry_count": 0,
                }
                unresolved.add("JOURNAL_ROOT_NOT_DIRECTORY")
                continue
            records, status = _scan(
                root,
                relative,
                max_depth=1,
            )
            total_entries = _add_scan_count(
                total_entries,
                records,
            )
            roots[role] = {
                "status": status,
                "kind": (
                    "directory"
                    if status == "OBSERVED"
                    else None
                ),
                "entry_count": len(records),
            }
            prefix_depth = len(relative.split("/"))
            for item in records:
                parts = item["relative"].split("/")
                if (
                    item["kind"] != "directory"
                    or len(parts) != prefix_depth + 1
                ):
                    continue
                leaf = parts[-1]
                if (
                    current_id is not None
                    and leaf.lower() == current_id
                ):
                    relation["matches_current"] += 1
                elif HEX32_RE.fullmatch(leaf):
                    relation["other_machine_id"] += 1
                elif re.fullmatch(
                    r"[0-9a-fA-F]{32}\.[A-Za-z0-9_.-]+",
                    leaf,
                ):
                    relation["namespace"] += 1
                else:
                    relation["unknown"] += 1
        if (
            current_id is None
            and sum(relation.values())
        ):
            unresolved.add(
                "CURRENT_MACHINE_ID_UNAVAILABLE_FOR_JOURNAL_COMPARE"
            )
        if relation["unknown"]:
            unresolved.add(
                "JOURNAL_DIRECTORY_IDENTITY_UNKNOWN"
            )
        policy, policy_unresolved = (
            _journald_policy(root)
        )
        unresolved.update(policy_unresolved)
        units, unit_unresolved = _snapshot_units(
            root,
            E7_UNITS,
            runner,
        )
        unresolved.update(unit_unresolved)
        for critical_unit in (
            "systemd-journald.service",
            "systemd-journal-flush.service",
        ):
            if (
                units[critical_unit].get("status")
                != "OBSERVED"
            ):
                unresolved.add(
                    "JOURNAL_CRITICAL_UNIT_UNRESOLVED"
                )
    except (
        OSError,
        ReadonlyEvidenceError,
        RemainingCollectError,
    ) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = _reason(
            error,
            "STOP_E7_COLLECTION_ERROR",
        )
        return envelope

    envelope["method_ids"] = [
        "R1",
        "R2",
        "R3",
        "C4",
    ]
    envelope["fields"]["journal_roots"] = _field(
        roots,
        "OBSERVED",
    )
    envelope["fields"][
        "directory_identity_relation"
    ] = _field(
        dict(sorted(relation.items())),
        (
            "OBSERVED"
            if not relation["unknown"]
            else "UNKNOWN"
        ),
    )
    envelope["fields"][
        "journal_storage_policy"
    ] = _field(
        policy,
        (
            "OBSERVED"
            if not policy_unresolved
            else "UNKNOWN"
        ),
    )
    envelope["fields"]["namespace_units"] = _field(
        {
            unit: _unit_summary(snapshot)
            for unit, snapshot in units.items()
            if "journald@" in unit
        },
        "OBSERVED",
    )
    journald = units["systemd-journald.service"]
    flush = units["systemd-journal-flush.service"]
    envelope["fields"]["journal_boot_order"] = _field(
        {
            "journald_before": journald.get(
                "before",
                [],
            ),
            "journald_after": journald.get(
                "after",
                [],
            ),
            "flush_before": flush.get("before", []),
            "flush_after": flush.get("after", []),
        },
        (
            "OBSERVED"
            if journald.get("status") == "OBSERVED"
            else "UNKNOWN"
        ),
    )
    complete = not unresolved
    envelope["status"] = (
        "OBSERVED" if complete else "UNKNOWN"
    )
    envelope["complete"] = complete
    envelope["reason_code"] = (
        None
        if complete
        else "STOP_JOURNAL_CLASSIFICATION"
    )
    return envelope


def _find_record(
    records: list[dict[str, Any]],
    relative: str,
) -> dict[str, Any] | None:
    for record in records:
        if record["relative"] == relative:
            return record
    return None


def collect_e8(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = _empty_requirement("E8")
    unresolved: set[str] = set()
    try:
        records, parent_status = _scan(
            root,
            "var/lib/systemd",
            max_depth=0,
        )
        seed = _find_record(
            records,
            "var/lib/systemd/random-seed",
        )
        if seed is None:
            seed_metadata = {
                "present": False,
                "status": "ABSENT",
            }
        elif seed["kind"] != "regular":
            seed_metadata = {
                "present": True,
                "status": "UNKNOWN",
                "kind": seed["kind"],
            }
            unresolved.add(
                "RANDOM_SEED_NOT_REGULAR"
            )
        else:
            seed_metadata = {
                "present": True,
                "status": "OBSERVED",
                "mode": seed["mode"],
                "size_bytes": seed["size"],
            }
        units, unit_unresolved = _snapshot_units(
            root,
            ("systemd-random-seed.service",),
            runner,
        )
        unresolved.update(unit_unresolved)
        try:
            package = runner(
                "C3_LIST",
                value="systemd",
                approved_packages={"systemd"},
            )
            if package.returncode == 0:
                package_text = _decode(
                    package.stdout,
                    "SYSTEMD_PACKAGE_LIST",
                )
                package_seed_paths = [
                    line.strip()
                    for line in package_text.splitlines()
                    if "random-seed" in line.lower()
                ]
                package_seed_path_count = len(
                    package_seed_paths
                )
                unknown_seed_owner_count = sum(
                    1
                    for path in package_seed_paths
                    if (
                        (
                            path.endswith(".service")
                            or "/bin/" in path
                            or "/sbin/" in path
                        )
                        and not path.endswith(
                            "/systemd-random-seed.service"
                        )
                    )
                )
                if unknown_seed_owner_count:
                    unresolved.add(
                        "ALTERNATE_SEED_OWNER_UNBOUND"
                    )
            else:
                package_seed_path_count = 0
                unknown_seed_owner_count = 0
                unresolved.add(
                    "RANDOM_SEED_PACKAGE_LIST_UNKNOWN"
                )
        except (OSError, ReadonlyCommandError):
            package_seed_path_count = 0
            unknown_seed_owner_count = 0
            unresolved.add(
                "RANDOM_SEED_PACKAGE_LIST_UNKNOWN"
            )
        alternatives = []
        for relative in (
            "var/lib/random-seed",
            "var/lib/urandom/random-seed",
        ):
            metadata = _metadata(root, relative)
            alternatives.append(
                {
                    "role": "ALTERNATE_SEED_CANDIDATE",
                    "status": metadata["status"],
                    "kind": metadata.get("kind"),
                }
            )
            if metadata["status"] == "OBSERVED":
                unresolved.add(
                    "ALTERNATE_SEED_STATE_PRESENT"
                )
    except (
        OSError,
        ReadonlyEvidenceError,
        RemainingCollectError,
    ) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = _reason(
            error,
            "STOP_E8_COLLECTION_ERROR",
        )
        return envelope

    seed_unit = units[
        "systemd-random-seed.service"
    ]
    if parent_status == "ABSENT":
        unresolved.add(
            "SYSTEMD_STATE_ROOT_ABSENT"
        )
    if seed_unit.get("status") != "OBSERVED":
        unresolved.add(
            "RANDOM_SEED_OWNER_UNIT_UNKNOWN"
        )
    envelope["method_ids"] = [
        "R1",
        "R3",
        "C3",
        "C4",
    ]
    envelope["fields"]["seed_metadata"] = _field(
        seed_metadata,
        seed_metadata["status"],
    )
    envelope["fields"]["seed_owner_unit"] = _field(
        _unit_summary(seed_unit),
        (
            "OBSERVED"
            if seed_unit.get("status") == "OBSERVED"
            else "UNKNOWN"
        ),
    )
    envelope["fields"]["seed_load_save_order"] = (
        _field(
            {
                "before": seed_unit.get(
                    "before",
                    [],
                ),
                "after": seed_unit.get("after", []),
                "condition_names": seed_unit.get(
                    "condition_names",
                    [],
                ),
            },
            (
                "OBSERVED"
                if seed_unit.get("status")
                == "OBSERVED"
                else "UNKNOWN"
            ),
        )
    )
    envelope["fields"][
        "alternate_seed_mechanisms"
    ] = _field(
        {
            "fixed_candidates": alternatives,
            "systemd_package_random_seed_path_count": (
                package_seed_path_count
            ),
            "unknown_seed_owner_count": (
                unknown_seed_owner_count
            ),
        },
        (
            "OBSERVED"
            if "RANDOM_SEED_PACKAGE_LIST_UNKNOWN"
            not in unresolved
            else "UNKNOWN"
        ),
    )
    envelope["fields"]["boot_entropy_limit"] = _field(
        {
            "clone_entropy_independence": (
                "NOT_PROVEN_BY_READONLY_EVIDENCE"
            ),
            "seed_body_read": False,
            "seed_body_hashed": False,
        },
        "OBSERVED",
    )
    complete = not unresolved
    envelope["status"] = (
        "OBSERVED" if complete else "UNKNOWN"
    )
    envelope["complete"] = complete
    envelope["reason_code"] = (
        None
        if complete
        else "STOP_SEED_MECHANISM_UNKNOWN"
    )
    return envelope


def _unit_link_edges(
    root: str,
    units: tuple[str, ...],
) -> tuple[list[dict[str, str]], list[str]]:
    edges: list[dict[str, str]] = []
    unresolved: set[str] = set()
    total_entries = 0
    bases: list[str] = []
    for candidate in (
        "etc/systemd/system",
        "run/systemd/system",
        "usr/lib/systemd/system",
        "lib/systemd/system",
    ):
        resolved, alias_unresolved = _resolve_usr_merge_relative(
            root,
            candidate,
        )
        if alias_unresolved or resolved is None:
            unresolved.add(
                alias_unresolved or "USR_MERGE_ALIAS_UNRESOLVED"
            )
            continue
        if resolved not in bases:
            bases.append(resolved)
    for unit in units:
        for relation in ("wants", "requires"):
            suffix = f"{unit}.{relation}"
            for base in bases:
                relative = f"{base}/{suffix}"
                metadata = _metadata(root, relative)
                if metadata["status"] == "ABSENT":
                    continue
                if metadata["kind"] != "directory":
                    unresolved.add(
                        "UNIT_RELATION_DIR_NOT_DIRECTORY"
                    )
                    continue
                try:
                    records, _ = _scan(
                        root,
                        relative,
                        max_depth=0,
                    )
                    total_entries = _add_scan_count(
                        total_entries,
                        records,
                    )
                except (
                    OSError,
                    ReadonlyEvidenceError,
                ):
                    unresolved.add(
                        "UNIT_RELATION_DIR_UNREADABLE"
                    )
                    continue
                for record in records:
                    if record["kind"] != "symlink":
                        unresolved.add(
                            "UNIT_RELATION_ENTRY_NOT_SYMLINK"
                        )
                        continue
                    try:
                        target = read_symlink_target(
                            root,
                            record["relative"],
                        )
                    except (
                        OSError,
                        ReadonlyEvidenceError,
                    ):
                        unresolved.add(
                            "UNIT_RELATION_TARGET_UNREADABLE"
                        )
                        continue
                    target_unit = posixpath.basename(
                        target
                    )
                    if not UNIT_RE.fullmatch(target_unit):
                        unresolved.add(
                            "UNIT_RELATION_TARGET_INVALID"
                        )
                        continue
                    edges.append(
                        {
                            "source": unit,
                            "relation": relation.upper(),
                            "target": target_unit,
                        }
                    )
    edges.sort(
        key=lambda item: (
            item["source"],
            item["relation"],
            item["target"],
        )
    )
    return edges, sorted(unresolved)


def _ordering_graph(
    snapshots: dict[str, dict[str, Any]],
) -> tuple[
    dict[str, set[str]],
    list[dict[str, str]],
    list[str],
]:
    graph = {
        unit: set()
        for unit in snapshots
    }
    edges: list[dict[str, str]] = []
    unresolved: set[str] = set()
    relevant_tokens = (
        "ssh",
        "network",
        "machine",
        "firstboot",
        "random",
        "journal",
        "armbian",
    )
    for unit, snapshot in snapshots.items():
        if snapshot.get("status") != "OBSERVED":
            continue
        for target in snapshot.get("before", []):
            if target in graph:
                graph[unit].add(target)
                edges.append(
                    {
                        "source": unit,
                        "relation": "BEFORE",
                        "target": target,
                    }
                )
            elif any(
                token in target.lower()
                for token in relevant_tokens
            ):
                unresolved.add(
                    f"EXTERNAL_BEFORE_{target}"
                )
        for target in snapshot.get("after", []):
            if target in graph:
                graph[target].add(unit)
                edges.append(
                    {
                        "source": target,
                        "relation": "BEFORE",
                        "target": unit,
                    }
                )
            elif any(
                token in target.lower()
                for token in relevant_tokens
            ):
                unresolved.add(
                    f"EXTERNAL_AFTER_{target}"
                )
    edges.sort(
        key=lambda item: (
            item["source"],
            item["target"],
        )
    )
    return graph, edges, sorted(unresolved)


def _reachable(
    graph: dict[str, set[str]],
    source: str,
    target: str,
) -> bool:
    queue: deque[str] = deque([source])
    visited: set[str] = set()
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        queue.extend(
            sorted(
                graph.get(current, set())
                - visited
            )
        )
    return False


def _order_classification(
    graph: dict[str, set[str]],
    snapshots: dict[str, dict[str, Any]],
    sources: set[str],
    targets: set[str],
) -> dict[str, Any]:
    observed_sources = [
        unit
        for unit in sorted(sources)
        if snapshots.get(unit, {}).get("status")
        == "OBSERVED"
    ]
    observed_targets = [
        unit
        for unit in sorted(targets)
        if snapshots.get(unit, {}).get("status")
        == "OBSERVED"
    ]
    if not observed_sources or not observed_targets:
        return {
            "classification": "UNKNOWN",
            "proven_pair_count": 0,
        }
    if any(
        snapshots[unit].get("condition_result")
        is not True
        for unit in observed_sources
    ):
        return {
            "classification": "UNKNOWN",
            "proven_pair_count": 0,
        }
    proven = 0
    unknown = 0
    for source in observed_sources:
        for target in observed_targets:
            if _reachable(
                graph,
                source,
                target,
            ):
                proven += 1
            elif _reachable(
                graph,
                target,
                source,
            ):
                return {
                    "classification": "CONTRADICTED",
                    "proven_pair_count": proven,
                }
            else:
                unknown += 1
    return {
        "classification": (
            "SUPPORTED"
            if unknown == 0
            else "UNKNOWN"
        ),
        "proven_pair_count": proven,
    }


def collect_e9(
    root: str,
    runner: CommandRunner = run_contract_command,
) -> dict[str, Any]:
    envelope = _empty_requirement("E9")
    try:
        snapshots, unit_unresolved = _snapshot_units(
            root,
            E9_UNITS,
            runner,
        )
        link_edges, link_unresolved = (
            _unit_link_edges(root, E9_UNITS)
        )
        (
            graph,
            order_edges,
            external_unresolved,
        ) = _ordering_graph(snapshots)
        try:
            listener = _listener_classification(
                runner("C6_LISTEN")
            )
        except (OSError, ReadonlyCommandError):
            listener = {
                "status": "UNKNOWN",
                "classes": [],
                "count": 0,
            }
    except (
        OSError,
        ReadonlyEvidenceError,
        RemainingCollectError,
    ) as error:
        envelope["status"] = "ERROR"
        envelope["reason_code"] = _reason(
            error,
            "STOP_E9_COLLECTION_ERROR",
        )
        return envelope

    unresolved = (
        set(unit_unresolved)
        | set(link_unresolved)
        | set(external_unresolved)
    )
    identity_sources = {
        "systemd-firstboot.service",
        "systemd-machine-id-commit.service",
        "armbian-firstrun.service",
    }
    network_targets = {
        "NetworkManager.service",
        "netplan-configure.service",
        "systemd-networkd.service",
        "network-pre.target",
        "network.target",
        "network-online.target",
    }
    ssh_sources = identity_sources | {
        "sshd-keygen.service"
    }
    ssh_targets = {
        "ssh.service",
        "sshd.service",
        "ssh.socket",
    }
    before_network = _order_classification(
        graph,
        snapshots,
        identity_sources,
        network_targets,
    )
    before_ssh = _order_classification(
        graph,
        snapshots,
        ssh_sources,
        ssh_targets,
    )
    if (
        before_network["classification"]
        == "UNKNOWN"
    ):
        unresolved.add(
            "IDENTITY_BEFORE_NETWORK_UNKNOWN"
        )
    if before_ssh["classification"] == "UNKNOWN":
        unresolved.add(
            "IDENTITY_BEFORE_SSH_UNKNOWN"
        )
    conditions = {
        unit: {
            "condition_result": snapshot.get(
                "condition_result"
            ),
            "condition_names": snapshot.get(
                "condition_names",
                [],
            ),
        }
        for unit, snapshot in snapshots.items()
        if snapshot.get("status") == "OBSERVED"
    }
    timestamps = {
        unit: snapshot.get("timestamps", {})
        for unit, snapshot in snapshots.items()
        if snapshot.get("status") == "OBSERVED"
    }
    timestamp_unknown = any(
        value is None
        for values in timestamps.values()
        for value in values.values()
    )
    if timestamp_unknown:
        unresolved.add("CURRENT_BOOT_TIMESTAMP_UNKNOWN")
    if listener["status"] != "OBSERVED":
        unresolved.add("SSH_LISTENER_UNKNOWN")
    dependency_graph = {
        "ordering_edges": order_edges,
        "unit_statuses": {
            unit: snapshot.get("status")
            for unit, snapshot in snapshots.items()
        },
    }
    activation_tokens = (
        "ssh",
        "network",
        "machine",
        "firstboot",
        "random",
        "journal",
        "armbian",
    )
    property_activation_edges: list[dict[str, str]] = []
    trigger_edges: list[dict[str, str]] = []
    for unit, snapshot in snapshots.items():
        if snapshot.get("status") != "OBSERVED":
            continue
        for relation in ("wants", "requires"):
            for target in snapshot.get(relation, []):
                if target in snapshots:
                    property_activation_edges.append(
                        {
                            "source": unit,
                            "relation": relation.upper(),
                            "target": target,
                        }
                    )
                elif any(
                    token in target.lower()
                    for token in activation_tokens
                ):
                    unresolved.add(
                        f"EXTERNAL_{relation.upper()}_{target}"
                    )
        for relation in ("triggers", "triggered_by"):
            for target in snapshot.get(relation, []):
                if target in snapshots:
                    trigger_edges.append(
                        {
                            "source": unit,
                            "relation": relation.upper(),
                            "target": target,
                        }
                    )
                elif any(
                    token in target.lower()
                    for token in activation_tokens
                ):
                    unresolved.add(
                        f"EXTERNAL_{relation.upper()}_{target}"
                    )
    activation_edges = {
        "property_edges": sorted(
            property_activation_edges,
            key=lambda item: (
                item["source"],
                item["relation"],
                item["target"],
            ),
        ),
        "trigger_edges": sorted(
            trigger_edges,
            key=lambda item: (
                item["source"],
                item["relation"],
                item["target"],
            ),
        ),
        "wants_requires_symlinks": link_edges,
        "listener": listener,
        "ordering_semantics_excluded": [
            "WANTS",
            "REQUIRES",
            "TRIGGERS",
            "TRIGGERED_BY",
        ],
    }
    envelope["method_ids"] = ["R3", "C4", "C6"]
    envelope["fields"]["unit_dependency_graph"] = (
        _field(dependency_graph, "OBSERVED")
    )
    envelope["fields"]["condition_evaluation"] = (
        _field(conditions, "OBSERVED")
    )
    envelope["fields"]["activation_edges"] = _field(
        activation_edges,
        "OBSERVED",
    )
    envelope["fields"]["current_boot_timestamps"] = (
        _field(
            timestamps,
            "UNKNOWN" if timestamp_unknown else "OBSERVED",
        )
    )
    envelope["fields"]["identity_before_network"] = (
        _field(
            before_network,
            (
                "OBSERVED"
                if before_network["classification"]
                != "UNKNOWN"
                else "UNKNOWN"
            ),
        )
    )
    envelope["fields"]["identity_before_ssh"] = (
        _field(
            before_ssh,
            (
                "OBSERVED"
                if before_ssh["classification"]
                != "UNKNOWN"
                else "UNKNOWN"
            ),
        )
    )
    envelope["fields"]["unresolved_edges"] = _field(
        sorted(unresolved),
        "OBSERVED",
    )
    capture_errors = bool(
        unit_unresolved
        or link_unresolved
        or listener["status"] != "OBSERVED"
    )
    envelope["complete"] = not capture_errors
    envelope["status"] = (
        "OBSERVED"
        if not capture_errors
        else "UNKNOWN"
    )
    envelope["reason_code"] = (
        None
        if not capture_errors
        else "STOP_BOOT_ORDER_CAPTURE_GAP"
    )
    return envelope
