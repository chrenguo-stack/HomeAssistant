#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import configparser
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w.t1-os-identity-readonly-probe/1"
MAX_TEXT_BYTES = 1024 * 1024
MACHINE_ID_PATHS = (
    "etc/machine-id",
    "var/lib/dbus/machine-id",
)
IDENTITY_UNIT_NAME_TOKENS = (
    "machine-id",
    "ssh",
    "networkmanager",
    "hostname",
    "armbian-first",
    "armbian-firstrun",
)
IDENTITY_UNIT_CONTENT_TOKENS = (
    "/etc/machine-id",
    "systemd-machine-id",
    "ssh-keygen",
    "ssh_host_",
    "networkmanager",
    "/etc/hostname",
    "hostnamectl",
    "armbian-first",
    "armbian-firstrun",
)
UNIT_SUFFIXES = (
    ".service",
    ".timer",
    ".socket",
    ".path",
)
UNIT_DIRS = (
    "etc/systemd/system",
    "usr/lib/systemd/system",
    "lib/systemd/system",
)
NM_FIELDS = (
    ("connection", "type"),
    ("connection", "interface-name"),
    ("connection", "uuid"),
    ("connection", "stable-id"),
    ("connection", "autoconnect"),
    ("ethernet", "cloned-mac-address"),
    ("ethernet", "generate-mac-address-mask"),
    ("ipv4", "dhcp-client-id"),
    ("ipv4", "dhcp-iaid"),
    ("ipv6", "dhcp-duid"),
    ("ipv6", "dhcp-iaid"),
    ("ipv6", "addr-gen-mode"),
    ("802-11-wireless", "cloned-mac-address"),
    ("802-11-wireless", "generate-mac-address-mask"),
)
OS_RELEASE_FIELDS = (
    "ID",
    "VERSION_ID",
    "VERSION_CODENAME",
    "PRETTY_NAME",
)
ARMBIAN_RELEASE_FIELDS = (
    "BOARD",
    "BOARD_NAME",
    "VERSION",
    "BRANCH",
    "ARCH",
    "IMAGE_TYPE",
)


class ProbeError(RuntimeError):
    pass


def _rooted(root: Path, relative: str) -> Path:
    path = root / relative
    resolved_root = root.resolve()
    resolved_parent = path.parent.resolve()
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise ProbeError("path_escape")
    return path


def _metadata(path: Path) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"present": False}
    kind = "other"
    if stat.S_ISREG(metadata.st_mode):
        kind = "regular"
    elif stat.S_ISDIR(metadata.st_mode):
        kind = "directory"
    elif stat.S_ISLNK(metadata.st_mode):
        kind = "symlink"
    return {
        "present": True,
        "kind": kind,
        "mode": format(stat.S_IMODE(metadata.st_mode), "04o"),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "size": metadata.st_size,
    }


def _read_regular_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ProbeError(f"read_open_failed:{path.name}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ProbeError(f"read_not_regular:{path.name}")
        if metadata.st_size > MAX_TEXT_BYTES:
            raise ProbeError(f"read_too_large:{path.name}")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 65536)
            if not block:
                break
            total += len(block)
            if total > MAX_TEXT_BYTES:
                raise ProbeError(f"read_too_large:{path.name}")
            chunks.append(block)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_text(path: Path) -> str:
    try:
        return _read_regular_bytes(path).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeError(f"read_not_utf8:{path.name}") from error


def _parse_key_value(path: Path, allowed: tuple[str, ...]) -> dict[str, str]:
    metadata = _metadata(path)
    if not metadata.get("present") or metadata.get("kind") != "regular":
        return {}
    result: dict[str, str] = {}
    for raw in _read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in allowed:
            continue
        value = value.strip().strip('"').strip("'")
        result[key] = value
    return result


def _machine_id_record(path: Path) -> dict[str, Any]:
    record = _metadata(path)
    if not record.get("present"):
        return record
    if record.get("kind") == "symlink":
        record["symlink_target"] = os.readlink(path)
        return record
    if record.get("kind") != "regular":
        return record
    value = _read_text(path).strip()
    record.update(
        {
            "content_length": len(value),
            "content_sha256": hashlib.sha256(value.encode()).hexdigest(),
            "valid_hex32": len(value) == 32
            and all(char in "0123456789abcdef" for char in value.lower()),
        }
    )
    return record


def _ssh_public_fingerprint(path: Path) -> dict[str, Any]:
    record = _metadata(path)
    if not record.get("present") or record.get("kind") != "regular":
        return record
    fields = _read_text(path).strip().split()
    if len(fields) < 2:
        record["public_key_parse"] = "INVALID"
        return record
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except ValueError:
        record["public_key_parse"] = "INVALID"
        return record
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    record.update(
        {
            "public_key_parse": "PASS",
            "algorithm": fields[0],
            "fingerprint_sha256": f"SHA256:{digest}",
        }
    )
    return record


def _ssh_host_keys(root: Path) -> list[dict[str, Any]]:
    directory = _rooted(root, "etc/ssh")
    if not directory.is_dir() or directory.is_symlink():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("ssh_host_*_key*")):
        if path.name.endswith(".pub"):
            record = _ssh_public_fingerprint(path)
            record["material"] = "public"
        else:
            record = _metadata(path)
            record["material"] = "private_metadata_only"
        record["name"] = path.name
        records.append(record)
    return records


def _networkmanager_profiles(root: Path) -> list[dict[str, Any]]:
    directory = _rooted(root, "etc/NetworkManager/system-connections")
    if not directory.is_dir() or directory.is_symlink():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir()):
        metadata = _metadata(path)
        if metadata.get("kind") != "regular":
            continue
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read_string(_read_text(path))
        except configparser.Error as error:
            raise ProbeError(f"networkmanager_profile_invalid:{path.name}") from error
        selected: dict[str, str] = {}
        for section, key in NM_FIELDS:
            if parser.has_option(section, key):
                selected[f"{section}.{key}"] = parser.get(section, key)
        records.append(
            {
                "name": path.name,
                "metadata": metadata,
                "selected_identity_fields": selected,
                "secret_values_included": False,
            }
        )
    return records


def _unit_candidate_name(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in IDENTITY_UNIT_NAME_TOKENS)


def _unit_relevant_lines(text: str) -> list[str]:
    result: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if any(token in lowered for token in IDENTITY_UNIT_CONTENT_TOKENS):
            result.append(line)
            continue
        if line.startswith(("Condition", "Before=", "After=", "WantedBy=")):
            result.append(line)
    return result


def _unit_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for directory in UNIT_DIRS:
        base = _rooted(root, directory)
        if not base.exists() or not base.is_dir() or base.is_symlink():
            continue
        for path in sorted(base.rglob("*")):
            if path.name.endswith(tuple(UNIT_SUFFIXES)) is False:
                continue
            relative = path.relative_to(root).as_posix()
            if relative in seen:
                continue
            metadata = _metadata(path)
            if not metadata.get("present"):
                continue

            record: dict[str, Any] = {
                "name": path.name,
                "path": f"/{relative}",
                "metadata": metadata,
            }
            matched = _unit_candidate_name(path.name)
            if metadata.get("kind") == "symlink":
                target = os.readlink(path)
                record["symlink_target"] = target
                matched = matched or any(
                    token in target.lower()
                    for token in IDENTITY_UNIT_NAME_TOKENS
                )
            elif metadata.get("kind") == "regular":
                data = _read_regular_bytes(path)
                text = data.decode("utf-8", errors="replace")
                relevant = _unit_relevant_lines(text)
                matched = matched or bool(relevant)
                if matched:
                    record["sha256"] = hashlib.sha256(data).hexdigest()
                    record["identity_relevant_lines"] = relevant
            if matched:
                records.append(record)
                seen.add(relative)
    return records


def collect(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ProbeError("root_invalid")
    hostname_path = _rooted(root, "etc/hostname")
    hostname = None
    if hostname_path.is_file() and not hostname_path.is_symlink():
        hostname = _read_text(hostname_path).strip()
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "root": str(root),
        "os_release": _parse_key_value(
            _rooted(root, "etc/os-release"),
            OS_RELEASE_FIELDS,
        ),
        "armbian_release": _parse_key_value(
            _rooted(root, "etc/armbian-release"),
            ARMBIAN_RELEASE_FIELDS,
        ),
        "hostname": hostname,
        "machine_identity": {
            relative: _machine_id_record(_rooted(root, relative))
            for relative in MACHINE_ID_PATHS
        },
        "ssh_host_keys": _ssh_host_keys(root),
        "networkmanager_profiles": _networkmanager_profiles(root),
        "identity_related_units": _unit_records(root),
        "secret_values_included": False,
        "mutation": False,
        "production_service_start": False,
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_evidence_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/"))
    args = parser.parse_args()
    try:
        report = collect(args.root)
    except (OSError, ProbeError) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": str(error),
                    "mutation": False,
                    "production_service_start": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
