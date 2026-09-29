#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import ssl
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

SCHEMA = "gh.n3w-broker-certificate-deployment-preflight/1"
EXPECTED_PROJECT = "n3wfc4"
EXPECTED_SERVICE = "broker"
EXPECTED_ACTIVATION_UNIT = "n3wfc4-broker-activation.service"
EXPECTED_GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
LIFECYCLE_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
LIFECYCLE_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"
EXPECTED_SERVER_NAME = "armbian"
EXPECTED_CA_FINGERPRINT = "b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351"
EXPECTED_SERVER_FINGERPRINT = "8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb"
EXPECTED_SYSTEM_CA_FINGERPRINT = "745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7"
SYSTEM_CA_PATH = Path("/var/lib/greenhouse-manager/system-ca.pem")
PRIVATE_MATERIALIZATION_GLOB = "/root/n3w-fc4-private-materialization.*"
MAX_FILE_BYTES = 65536
DEFAULT_MAX_FILES = 5000
DEFAULT_MAX_DEPTH = 8
PRIVATE_KEY_PEM_RE = re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
KEYLIKE_SUFFIXES = {".key", ".priv", ".p8", ".pk8"}
DEPLOYMENT_TARGETS = (
    Path("/usr/local/sbin/n3w-broker-certificate-lifecycle"),
    Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service"),
    Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer"),
    Path("/etc/n3wfc4/broker-certificate-lifecycle.env"),
)


class PreflightError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _progress(stage: str, **fields: object) -> None:
    print(
        "KF100_DEPLOY_PRECHECK "
        + json.dumps({"stage": stage, **fields}, sort_keys=True, separators=(",", ":")),
        file=os.sys.stderr,
        flush=True,
    )


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
        raise PreflightError("command_unavailable") from error
    if result.returncode != 0:
        raise PreflightError("command_failed")
    return result.stdout


def _systemctl_state(mode: str, unit: str) -> str:
    if mode not in {"is-active", "is-enabled"}:
        raise PreflightError("systemctl_mode_invalid")
    try:
        result = subprocess.run(
            ("systemctl", mode, unit),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PreflightError("systemctl_unavailable") from error
    return result.stdout.strip() or ("active" if result.returncode == 0 and mode == "is-active" else "unknown")


def _docker_json(argv: Sequence[str]) -> object:
    raw = _run(("docker", *argv))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise PreflightError("docker_json_invalid") from error


def _broker_container() -> str:
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
        raise PreflightError("broker_container_not_unique")
    return ids[0]


def _broker_inspect(container_id: str) -> dict[str, object]:
    document = _docker_json(("inspect", container_id))
    if not isinstance(document, list) or len(document) != 1:
        raise PreflightError("broker_inspect_invalid")
    item = document[0]
    if not isinstance(item, dict):
        raise PreflightError("broker_inspect_invalid")
    state = item.get("State")
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise PreflightError("broker_not_running")
    config = item.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        raise PreflightError("broker_labels_invalid")
    if labels.get("com.docker.compose.project") != EXPECTED_PROJECT:
        raise PreflightError("broker_project_invalid")
    if labels.get("com.docker.compose.service") != EXPECTED_SERVICE:
        raise PreflightError("broker_service_invalid")
    return item


def _mount_source(
    inspect: dict[str, object],
    target: str,
    *,
    require_read_only: bool,
) -> Path:
    mounts = inspect.get("Mounts")
    if not isinstance(mounts, list):
        raise PreflightError("broker_mounts_invalid")
    matches: list[Path] = []
    for mount in mounts:
        if not isinstance(mount, dict) or mount.get("Destination") != target:
            continue
        if mount.get("Type") != "bind":
            raise PreflightError("broker_tls_mount_not_bind")
        if require_read_only and mount.get("RW") is not False:
            raise PreflightError("broker_tls_mount_not_read_only")
        source = mount.get("Source")
        if not isinstance(source, str) or not source.startswith("/"):
            raise PreflightError("broker_tls_source_invalid")
        matches.append(Path(source))
    if len(matches) != 1:
        raise PreflightError("broker_tls_mount_not_unique")
    path = matches[0]
    if path.is_symlink():
        raise PreflightError("broker_tls_source_symlink")
    try:
        file_stat = path.stat()
    except OSError as error:
        raise PreflightError("broker_tls_source_unreadable") from error
    if not stat.S_ISREG(file_stat.st_mode):
        raise PreflightError("broker_tls_source_not_regular")
    return path


def _fingerprint(path: Path) -> str:
    raw = _run(("openssl", "x509", "-in", str(path), "-noout", "-fingerprint", "-sha256"))
    match = re.search(r"Fingerprint=([0-9A-Fa-f:]+)", raw)
    if match is None:
        raise PreflightError("certificate_fingerprint_missing")
    value = match.group(1).replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise PreflightError("certificate_fingerprint_invalid")
    return value


def _x509_text(path: Path, *args: str) -> str:
    return _run(("openssl", "x509", "-in", str(path), "-noout", *args))


def _is_ca(path: Path) -> bool:
    return "CA:TRUE" in _x509_text(path, "-ext", "basicConstraints")


def _not_after(path: Path) -> str:
    raw = _x509_text(path, "-enddate").strip()
    if not raw.startswith("notAfter="):
        raise PreflightError("certificate_enddate_missing")
    value = " ".join(raw.split("=", 1)[1].split())
    try:
        parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
    except ValueError as error:
        raise PreflightError("certificate_enddate_invalid") from error
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _san_contains(path: Path, server_name: str) -> bool:
    raw = _x509_text(path, "-ext", "subjectAltName")
    names = {m.group(1).rstrip(".") for m in re.finditer(r"DNS:([^,\s]+)", raw)}
    return server_name.rstrip(".") in names


def _verify_server(server_cert: Path, ca_cert: Path, server_name: str) -> None:
    _run(
        (
            "openssl",
            "verify",
            "-CAfile",
            str(ca_cert),
            "-verify_hostname",
            server_name,
            str(server_cert),
        )
    )


def _certificate_public_key_der(path: Path) -> bytes:
    pem = _run(("openssl", "x509", "-in", str(path), "-noout", "-pubkey"))
    try:
        result = subprocess.run(
            ("openssl", "pkey", "-pubin", "-outform", "DER"),
            input=pem.encode("ascii"),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PreflightError("public_key_conversion_failed") from error
    if result.returncode != 0 or not result.stdout:
        raise PreflightError("public_key_conversion_failed")
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
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def _key_mode(path: Path) -> tuple[bool, bool, str]:
    file_stat = path.stat()
    return (
        file_stat.st_uid == 0,
        (file_stat.st_mode & 0o077) == 0,
        format(stat.S_IMODE(file_stat.st_mode), "04o"),
    )


def _persistent_root(ca_source: Path) -> Path:
    root = ca_source.parent
    for _ in range(2):
        root = root.parent
    if root == Path("/") or root.is_symlink() or not root.is_dir():
        raise PreflightError("persistent_root_invalid")
    return root


def _search_roots(ca_source: Path) -> tuple[Path, ...]:
    roots = [_persistent_root(ca_source)]
    parent = Path(PRIVATE_MATERIALIZATION_GLOB).parent
    pattern = Path(PRIVATE_MATERIALIZATION_GLOB).name
    for candidate in sorted(parent.glob(pattern)):
        try:
            if candidate.is_symlink() or not candidate.is_dir():
                continue
        except OSError:
            continue
        roots.append(candidate)
    unique: list[Path] = []
    seen: set[tuple[int, int]] = set()
    for root in roots:
        file_stat = root.stat()
        identity = (file_stat.st_dev, file_stat.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(root)
    return tuple(unique)


def _walk_files(
    roots: Sequence[Path],
    *,
    max_files: int,
    max_depth: int,
) -> tuple[list[tuple[int, Path]], int]:
    files: list[tuple[int, Path]] = []
    skipped_large = 0
    for root_index, root in enumerate(roots):
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
                files.append((root_index, Path(entry.path)))
                if len(files) > max_files:
                    raise PreflightError("search_file_limit_exceeded")
    return files, skipped_large


def _looks_like_private_key(path: Path) -> bool:
    likely_name = path.suffix.lower() in KEYLIKE_SUFFIXES or "private-key" in path.name.lower()
    try:
        with path.open("rb") as stream:
            prefix = stream.read(8192)
    except (OSError, PermissionError):
        return False
    return likely_name or PRIVATE_KEY_PEM_RE.search(prefix) is not None


def _path_token(path: Path, root: Path, root_index: int) -> str:
    relative = path.relative_to(root).as_posix().encode("utf-8")
    return hashlib.sha256(str(root_index).encode("ascii") + b"\0" + relative).hexdigest()


def _tls_endpoint_fingerprint(ca_cert: Path, server_name: str) -> str:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca_cert))
    try:
        with socket.create_connection(("127.0.0.1", 8883), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname=server_name) as wrapped:
                der = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise PreflightError("live_tls_probe_failed") from error
    if not der:
        raise PreflightError("live_tls_peer_certificate_missing")
    return hashlib.sha256(der).hexdigest()


def preflight(*, max_files: int, max_depth: int) -> dict[str, object]:
    if os.geteuid() != 0:
        raise PreflightError("root_required")

    _progress("bind_runtime")
    container = _broker_container()
    inspect = _broker_inspect(container)
    ca_cert = _mount_source(inspect, "/mosquitto/tls/ca.pem", require_read_only=True)
    server_cert = _mount_source(inspect, "/mosquitto/tls/server.pem", require_read_only=True)
    server_key = _mount_source(inspect, "/mosquitto/tls/server.key", require_read_only=True)

    ca_fp = _fingerprint(ca_cert)
    server_fp = _fingerprint(server_cert)
    if ca_fp != EXPECTED_CA_FINGERPRINT:
        raise PreflightError("active_ca_fingerprint_drift")
    if server_fp != EXPECTED_SERVER_FINGERPRINT:
        raise PreflightError("active_server_fingerprint_drift")
    if not _is_ca(ca_cert):
        raise PreflightError("active_ca_not_ca")
    if _is_ca(server_cert):
        raise PreflightError("active_server_is_ca")
    if not _san_contains(server_cert, EXPECTED_SERVER_NAME):
        raise PreflightError("active_server_san_mismatch")
    _verify_server(server_cert, ca_cert, EXPECTED_SERVER_NAME)

    server_public = _certificate_public_key_der(server_cert)
    server_key_public = _private_public_key_der(server_key)
    if server_key_public is None or server_key_public != server_public:
        raise PreflightError("server_key_mismatch")
    server_key_root, server_key_safe, server_key_mode = _key_mode(server_key)
    if not server_key_root or not server_key_safe:
        raise PreflightError("server_key_permissions_invalid")

    endpoint_fp = _tls_endpoint_fingerprint(ca_cert, EXPECTED_SERVER_NAME)
    if endpoint_fp != server_fp:
        raise PreflightError("live_tls_fingerprint_mismatch")
    _progress("runtime_bound")

    if not SYSTEM_CA_PATH.is_file() or SYSTEM_CA_PATH.is_symlink():
        raise PreflightError("system_ca_missing")
    system_ca_fp = _fingerprint(SYSTEM_CA_PATH)
    if system_ca_fp != EXPECTED_SYSTEM_CA_FINGERPRINT or not _is_ca(SYSTEM_CA_PATH):
        raise PreflightError("system_ca_drift")

    roots = _search_roots(ca_cert)
    _progress("scan_ca_key", search_root_count=len(roots))
    files, skipped_large = _walk_files(roots, max_files=max_files, max_depth=max_depth)
    candidates = [(index, path) for index, path in files if _looks_like_private_key(path)]
    ca_public = _certificate_public_key_der(ca_cert)
    parseable = 0
    matches: list[tuple[int, Path]] = []
    for index, path in candidates:
        public = _private_public_key_der(path)
        if public is None:
            continue
        parseable += 1
        if public == ca_public:
            matches.append((index, path))
    if len(matches) != 1:
        raise PreflightError("ca_private_key_not_unique")
    match_index, ca_key = matches[0]
    ca_key_root, ca_key_safe, ca_key_mode = _key_mode(ca_key)
    if not ca_key_root or not ca_key_safe:
        raise PreflightError("ca_private_key_permissions_invalid")

    _progress("check_systemd")
    guard_active = _systemctl_state("is-active", EXPECTED_GUARD_UNIT)
    guard_enabled = _systemctl_state("is-enabled", EXPECTED_GUARD_UNIT)
    activation_active = _systemctl_state("is-active", EXPECTED_ACTIVATION_UNIT)
    activation_enabled = _systemctl_state("is-enabled", EXPECTED_ACTIVATION_UNIT)
    timer_active = _systemctl_state("is-active", LIFECYCLE_TIMER)
    timer_enabled = _systemctl_state("is-enabled", LIFECYCLE_TIMER)
    if guard_active != "active" or guard_enabled != "enabled":
        raise PreflightError("ingress_guard_not_ready")
    if activation_active != "active" or activation_enabled != "enabled":
        raise PreflightError("broker_activation_not_ready")
    if timer_active == "active" or timer_enabled == "enabled":
        raise PreflightError("lifecycle_timer_already_enabled")

    existing_targets = sum(int(path.exists()) for path in DEPLOYMENT_TARGETS)
    if existing_targets != 0:
        raise PreflightError("lifecycle_deployment_target_already_present")

    _progress("complete", result="PASS")
    return {
        "schema": SCHEMA,
        "read_only": True,
        "t1_mutation": False,
        "broker_mutation": False,
        "manager_mutation": False,
        "homeassistant_mutation": False,
        "certificate_mutation": False,
        "timer_enablement": False,
        "broker_running": True,
        "broker_ca_sha256_fingerprint": ca_fp,
        "broker_server_sha256_fingerprint": server_fp,
        "broker_server_not_after": _not_after(server_cert),
        "broker_ca_not_after": _not_after(ca_cert),
        "system_ca_sha256_fingerprint": system_ca_fp,
        "system_ca_not_after": _not_after(SYSTEM_CA_PATH),
        "server_name": EXPECTED_SERVER_NAME,
        "server_certificate_key_match": True,
        "server_key_root_owned": server_key_root,
        "server_key_mode_safe": server_key_safe,
        "server_key_mode": server_key_mode,
        "live_tls_verified": True,
        "live_tls_fingerprint_match": True,
        "search_root_count": len(roots),
        "search_file_count": len(files),
        "search_skipped_large_file_count": skipped_large,
        "private_key_candidate_count": len(candidates),
        "parseable_private_key_count": parseable,
        "ca_private_key_match_count": 1,
        "ca_private_key_root_owned": ca_key_root,
        "ca_private_key_mode_safe": ca_key_safe,
        "ca_private_key_mode": ca_key_mode,
        "ca_private_key_path_token": _path_token(ca_key, roots[match_index], match_index),
        "ingress_guard_active": guard_active,
        "ingress_guard_enabled": guard_enabled,
        "broker_activation_active": activation_active,
        "broker_activation_enabled": activation_enabled,
        "lifecycle_timer_active": timer_active,
        "lifecycle_timer_enabled": timer_enabled,
        "deployment_target_present_count": existing_targets,
        "result": "PASS",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.max_files <= 20000 or not 1 <= args.max_depth <= 16:
        print(json.dumps({"schema": SCHEMA, "result": "STOP", "reason": "limit_invalid"}))
        return 2
    try:
        document = preflight(max_files=args.max_files, max_depth=args.max_depth)
    except PreflightError as error:
        document = {
            "schema": SCHEMA,
            "read_only": True,
            "t1_mutation": False,
            "certificate_mutation": False,
            "timer_enablement": False,
            "result": "STOP",
            "reason": error.code,
        }
        print(json.dumps(document, sort_keys=True, separators=(",", ":")), flush=True)
        return 2
    print(json.dumps(document, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
