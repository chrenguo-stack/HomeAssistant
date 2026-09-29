#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

SCHEMA = "gh.n3w-broker-ca-private-key-authority-probe/1"
EXPECTED_PROJECT = "n3wfc4"
EXPECTED_SERVICE = "broker"
EXPECTED_CA_TARGET = "/mosquitto/tls/ca.pem"
MAX_FILE_BYTES = 65536
DEFAULT_MAX_FILES = 5000
DEFAULT_MAX_DEPTH = 8


class ProbeError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _run(argv: Sequence[str], *, timeout: int = 20) -> str:
    try:
        result = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeError("command_unavailable") from error
    if result.returncode != 0:
        raise ProbeError("command_failed")
    return result.stdout


def _docker_json(argv: Sequence[str]) -> object:
    raw = _run(("docker", *argv))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProbeError("docker_json_invalid") from error


def _running_broker_container() -> str:
    raw = _run(
        (
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={EXPECTED_PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={EXPECTED_SERVICE}",
            "--format",
            "{{.ID}}",
        )
    )
    ids = tuple(line.strip() for line in raw.splitlines() if line.strip())
    if len(ids) != 1:
        raise ProbeError("broker_container_not_unique")
    return ids[0]


def _broker_inspect(container_id: str) -> dict[str, object]:
    document = _docker_json(("inspect", container_id))
    if not isinstance(document, list) or len(document) != 1:
        raise ProbeError("broker_inspect_invalid")
    item = document[0]
    if not isinstance(item, dict):
        raise ProbeError("broker_inspect_invalid")
    state = item.get("State")
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise ProbeError("broker_not_running")
    config = item.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        raise ProbeError("broker_labels_invalid")
    if labels.get("com.docker.compose.project") != EXPECTED_PROJECT:
        raise ProbeError("broker_project_identity_invalid")
    if labels.get("com.docker.compose.service") != EXPECTED_SERVICE:
        raise ProbeError("broker_service_identity_invalid")
    return item


def _active_ca_source(inspect: dict[str, object]) -> Path:
    mounts = inspect.get("Mounts")
    if not isinstance(mounts, list):
        raise ProbeError("broker_mounts_invalid")
    matches: list[Path] = []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        if mount.get("Destination") != EXPECTED_CA_TARGET:
            continue
        if mount.get("Type") != "bind":
            raise ProbeError("broker_ca_mount_not_bind")
        if mount.get("RW") is not False:
            raise ProbeError("broker_ca_mount_not_read_only")
        source = mount.get("Source")
        if not isinstance(source, str) or not source.startswith("/"):
            raise ProbeError("broker_ca_source_invalid")
        matches.append(Path(source))
    if len(matches) != 1:
        raise ProbeError("broker_ca_mount_not_unique")
    path = matches[0]
    if path.is_symlink():
        raise ProbeError("broker_ca_source_symlink")
    try:
        file_stat = path.stat()
    except OSError as error:
        raise ProbeError("broker_ca_source_unreadable") from error
    if not stat.S_ISREG(file_stat.st_mode):
        raise ProbeError("broker_ca_source_not_regular")
    return path


def _certificate_fingerprint(path: Path) -> str:
    raw = _run(
        (
            "openssl",
            "x509",
            "-in",
            str(path),
            "-noout",
            "-fingerprint",
            "-sha256",
        )
    )
    match = re.search(r"Fingerprint=([0-9A-Fa-f:]+)", raw)
    if match is None:
        raise ProbeError("ca_fingerprint_missing")
    fingerprint = match.group(1).replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ProbeError("ca_fingerprint_invalid")
    return fingerprint


def _certificate_is_ca(path: Path) -> bool:
    raw = _run(
        (
            "openssl",
            "x509",
            "-in",
            str(path),
            "-noout",
            "-ext",
            "basicConstraints",
        )
    )
    return "CA:TRUE" in raw


def _certificate_public_key_der(path: Path) -> bytes:
    pem = _run(
        (
            "openssl",
            "x509",
            "-in",
            str(path),
            "-noout",
            "-pubkey",
        )
    )
    try:
        result = subprocess.run(
            (
                "openssl",
                "pkey",
                "-pubin",
                "-outform",
                "DER",
            ),
            input=pem.encode("ascii"),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeError("openssl_public_key_unavailable") from error
    if result.returncode != 0 or not result.stdout:
        raise ProbeError("ca_public_key_invalid")
    return result.stdout


def _private_public_key_der(path: Path) -> bytes | None:
    try:
        result = subprocess.run(
            (
                "openssl",
                "pkey",
                "-in",
                str(path),
                "-pubout",
                "-outform",
                "DER",
                "-passin",
                "pass:",
            ),
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def _derived_search_root(ca_source: Path) -> Path:
    root = ca_source.parent
    for _ in range(2):
        if root.parent == root:
            break
        root = root.parent
    if root == Path("/"):
        raise ProbeError("derived_search_root_too_broad")
    try:
        root_stat = root.stat()
    except OSError as error:
        raise ProbeError("derived_search_root_unreadable") from error
    if not stat.S_ISDIR(root_stat.st_mode) or root.is_symlink():
        raise ProbeError("derived_search_root_invalid")
    return root


def _walk_files(
    root: Path,
    *,
    max_files: int,
    max_depth: int,
) -> tuple[list[Path], int]:
    files: list[Path] = []
    skipped_large = 0
    root_depth = len(root.parts)
    stack = [root]
    while stack:
        directory = stack.pop()
        depth = len(directory.parts) - root_depth
        if depth > max_depth:
            continue
        try:
            entries = list(os.scandir(directory))
        except (OSError, PermissionError):
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if depth < max_depth:
                        stack.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                file_stat = entry.stat(follow_symlinks=False)
            except (OSError, PermissionError):
                continue
            if file_stat.st_size > MAX_FILE_BYTES:
                skipped_large += 1
                continue
            files.append(Path(entry.path))
            if len(files) > max_files:
                raise ProbeError("search_file_limit_exceeded")
    return files, skipped_large


def _path_token(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix().encode("utf-8")
    return hashlib.sha256(relative).hexdigest()


def _mode_safe(path: Path) -> tuple[bool, int, int, str]:
    file_stat = path.stat()
    safe = (file_stat.st_mode & 0o077) == 0
    return (
        safe,
        file_stat.st_uid,
        file_stat.st_gid,
        format(stat.S_IMODE(file_stat.st_mode), "04o"),
    )


def _relative_to_active_tls(path: Path, ca_source: Path) -> bool:
    try:
        path.relative_to(ca_source.parent)
    except ValueError:
        return False
    return True


def probe(*, max_files: int, max_depth: int) -> dict[str, object]:
    if os.geteuid() != 0:
        raise ProbeError("root_required")
    container_id = _running_broker_container()
    inspect = _broker_inspect(container_id)
    ca_source = _active_ca_source(inspect)
    fingerprint = _certificate_fingerprint(ca_source)
    if not _certificate_is_ca(ca_source):
        raise ProbeError("active_broker_certificate_not_ca")
    ca_public = _certificate_public_key_der(ca_source)
    root = _derived_search_root(ca_source)
    files, skipped_large = _walk_files(
        root,
        max_files=max_files,
        max_depth=max_depth,
    )

    parseable_keys = 0
    matches: list[Path] = []
    for path in files:
        public = _private_public_key_der(path)
        if public is None:
            continue
        parseable_keys += 1
        if public == ca_public:
            matches.append(path)

    safe_matches = 0
    root_owned_matches = 0
    active_tls_tree_matches = 0
    match_tokens: list[str] = []
    match_modes: list[str] = []
    for path in matches:
        safe, uid, _gid, mode = _mode_safe(path)
        safe_matches += int(safe)
        root_owned_matches += int(uid == 0)
        active_tls_tree_matches += int(_relative_to_active_tls(path, ca_source))
        match_tokens.append(_path_token(path, root))
        match_modes.append(mode)

    exact_authority = (
        len(matches) == 1
        and safe_matches == 1
        and root_owned_matches == 1
    )

    return {
        "schema": SCHEMA,
        "read_only": True,
        "t1_mutation": False,
        "broker_mutation": False,
        "manager_mutation": False,
        "homeassistant_mutation": False,
        "broker_container_unique": True,
        "broker_running": True,
        "broker_ca_mount_unique": True,
        "broker_ca_mount_read_only": True,
        "broker_ca_certificate_parseable": True,
        "broker_ca_certificate_is_ca": True,
        "broker_ca_sha256_fingerprint": fingerprint,
        "derived_search_root_token": hashlib.sha256(
            root.as_posix().encode("utf-8")
        ).hexdigest(),
        "search_file_count": len(files),
        "search_skipped_large_file_count": skipped_large,
        "parseable_private_key_count": parseable_keys,
        "ca_private_key_match_count": len(matches),
        "ca_private_key_safe_permission_match_count": safe_matches,
        "ca_private_key_root_owned_match_count": root_owned_matches,
        "ca_private_key_active_tls_tree_match_count": active_tls_tree_matches,
        "ca_private_key_match_path_tokens": sorted(match_tokens),
        "ca_private_key_match_modes": sorted(match_modes),
        "ca_private_key_authority_exact_unique": exact_authority,
        "result": "PASS" if exact_authority else "STOP",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.max_files <= 20000:
        print(json.dumps({"schema": SCHEMA, "result": "STOP", "reason": "max_files_invalid"}))
        return 2
    if not 1 <= args.max_depth <= 16:
        print(json.dumps({"schema": SCHEMA, "result": "STOP", "reason": "max_depth_invalid"}))
        return 2
    try:
        document = probe(
            max_files=args.max_files,
            max_depth=args.max_depth,
        )
    except ProbeError as error:
        document = {
            "schema": SCHEMA,
            "read_only": True,
            "t1_mutation": False,
            "broker_mutation": False,
            "manager_mutation": False,
            "homeassistant_mutation": False,
            "result": "STOP",
            "reason": error.code,
        }
        print(json.dumps(document, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))
    return 0 if document["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
