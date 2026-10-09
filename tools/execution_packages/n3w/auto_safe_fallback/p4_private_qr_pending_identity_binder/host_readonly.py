from __future__ import annotations

import ast
import hashlib
import ipaddress
import json
import re
import subprocess
from pathlib import Path
from datetime import UTC, datetime

from validator import read_private_baseline

FROZEN_PREBOOT_SHA256 = "81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c"
PRIVATE_BASELINE = (
    Path.home()
    / "N3W_PRIVATE_EVIDENCE"
    / "N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01"
    / "manager_preboot_identity_snapshot.json"
)
READ_ONLY_FUNCTIONS = (
    "sha", "reject", "_ro", "_query", "_project_once", "project_readonly"
)
FORBIDDEN_REMOTE_SOURCE = (
    "import-payload", "import_setup_secret", "OneShotImporter",
    "ImportPermission", "ssh_manager_stdin_transport",
    "capture_private_qr", "setup_secret", "authorize-repair",
    "authorize-credential-recovery", "erase_flash", "write_flash",
    "docker exec -i", "GHN3W2",
)
EXPECTED_REMOTE_SCHEMA = "n3w.p4.pending-identity-projection/1"
EXPECTED_BRIDGE_GIT_BLOB = "e277949c3db5675bd460124832a382d6a2765539"
EXPECTED_REMOTE_PROBE_GIT_BLOB = "7b3ba146583b61271b41390736b67207c8d4c14e"


def _git_blob(content: str) -> str:
    encoded = content.encode("utf-8")
    return hashlib.sha1(f"blob {len(encoded)}".encode() + bytes([0]) + encoded).hexdigest()


def private_preboot_baseline(path: Path = PRIVATE_BASELINE) -> frozenset[str]:
    if path != PRIVATE_BASELINE:
        raise ValueError("PRIVATE_SNAPSHOT_PATH_DRIFT")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("PRIVATE_SNAPSHOT_SYMLINK")
    return read_private_baseline(path, FROZEN_PREBOOT_SHA256, count=5)


def _read_only_core(bridge_source: str) -> str:
    tree = ast.parse(bridge_source)
    named = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            named[node.name] = node
    names = ("GateStop", *READ_ONLY_FUNCTIONS)
    if not all(name in named for name in names):
        raise ValueError("READONLY_CORE_MISSING")
    pieces = [
        "import contextlib",
        "import hashlib",
        "import sqlite3",
        "from datetime import UTC, datetime",
        "from pathlib import Path",
        'SCHEMA = "n3w.p4.pending-identity-projection/1"',
        'TABLES = ("registrations", "pairing_sessions", "registration_events", "registration_node_history", "node_id_leases", "retirement_outbox")',
    ]
    for name in names:
        original = ast.get_source_segment(bridge_source, named[name])
        if not original:
            raise ValueError("READONLY_CORE_EXTRACT_FAILED")
        pieces.append(original)
    core = "\n\n".join(pieces) + "\n"
    ast.parse(core)
    return core


def build_remote_program(
    bridge_source: str,
    probe_source: str,
    *,
    snapshot_path: Path = PRIVATE_BASELINE,
) -> str:
    if (
        _git_blob(bridge_source) != EXPECTED_BRIDGE_GIT_BLOB
        or _git_blob(probe_source) != EXPECTED_REMOTE_PROBE_GIT_BLOB
    ):
        raise ValueError("READONLY_SOURCE_BLOB_DRIFT")
    baseline = private_preboot_baseline(snapshot_path)
    probe = ast.parse(probe_source)
    if any(
        isinstance(node, ast.ImportFrom) and node.module == "__future__"
        for node in probe.body
    ):
        raise ValueError("REMOTE_FUTURE_IMPORT")
    core = _read_only_core(bridge_source)
    header = "\nBASELINE_HASHES = " + json.dumps(sorted(baseline)) + "\n"
    remote = core + header + "\n" + probe_source
    ast.parse(remote)
    lower = remote.lower()
    if any(token.lower() in lower for token in FORBIDDEN_REMOTE_SOURCE):
        raise ValueError("REMOTE_MUTATING_OR_SECRET_SOURCE")
    for node in ast.walk(ast.parse(remote)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"executescript", "executemany", "commit", "rollback"}:
                raise ValueError("REMOTE_SQLITE_MUTATION")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.search(r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|REPLACE|VACUUM)\b", node.value, re.I):
                raise ValueError("REMOTE_SQL_MUTATION")
    return remote


def _trusted_target_digest(probe_source: str) -> str:
    match = re.search(
        r'^EXPECTED_T1_IP_SHA = "([0-9a-f]{64})"$',
        probe_source,
        flags=re.MULTILINE,
    )
    if match is None:
        raise ValueError("TARGET_AUTHORITY_MISSING")
    return match.group(1)


def _bound_sources() -> tuple[str, str]:
    root = Path(__file__).resolve().parent
    sources = []
    for filename in ("bridge_handoff.py", "remote_projection.py"):
        path = root / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError("READONLY_SOURCE_UNAVAILABLE")
        try:
            sources.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            raise ValueError("READONLY_SOURCE_UNAVAILABLE") from None
    return sources[0], sources[1]


def _validate_readonly_result(data: object, baseline: frozenset[str]) -> dict:
    required = {
        "schema", "hardware_sha256", "pairing_sha256",
        "expires_at", "preboot_count", "preboot_hashes",
        "new_count", "read_at", "container_continuity_pass",
        "manager_socket_pass", "tls_live_reprobe_pass",
    }
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("REMOTE_RESPONSE_INVALID")
    if (
        data["schema"] != EXPECTED_REMOTE_SCHEMA
        or data["container_continuity_pass"] is not True
        or data["manager_socket_pass"] is not True
        or data["tls_live_reprobe_pass"] is not True
        or type(data["preboot_count"]) is not int
        or data["preboot_count"] != 5
        or type(data["new_count"]) is not int
        or data["new_count"] != 1
        or type(data["preboot_hashes"]) is not list
        or data["preboot_hashes"] != sorted(baseline)
    ):
        raise ValueError("REMOTE_RESPONSE_INVALID")
    for key in ("hardware_sha256", "pairing_sha256"):
        if not isinstance(data[key], str) or not re.fullmatch(r"[0-9a-f]{64}", data[key]):
            raise ValueError("REMOTE_RESPONSE_INVALID")
    if data["hardware_sha256"] in baseline:
        raise ValueError("REMOTE_RESPONSE_INVALID")
    try:
        now = datetime.now(UTC)
        observed = datetime.fromisoformat(data["read_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or expires.tzinfo is None:
            raise ValueError()
        age = (now - observed.astimezone(UTC)).total_seconds()
        remaining = (expires.astimezone(UTC) - now).total_seconds()
    except (AttributeError, TypeError, ValueError):
        raise ValueError("REMOTE_RESPONSE_INVALID") from None
    if age < 0 or age > 10 or remaining < 60:
        raise ValueError("REMOTE_PENDING_STALE_OR_SHORT")
    return data


def remote_snapshot_once(
    target: str,
    *,
    snapshot_path: Path = PRIVATE_BASELINE,
) -> dict:
    bridge_source, probe_source = _bound_sources()
    program = build_remote_program(
        bridge_source, probe_source, snapshot_path=snapshot_path
    )
    baseline = private_preboot_baseline(snapshot_path)
    try:
        user, ip = target.split("@", 1)
        address = ipaddress.IPv4Address(ip)
    except (AttributeError, TypeError, ValueError):
        raise ValueError("INVALID_TARGET") from None
    if (
        user != "root"
        or str(address) != ip
        or address.is_loopback
        or not address.is_private
        or hashlib.sha256(ip.encode("ascii")).hexdigest()
        != _trusted_target_digest(probe_source)
    ):
        raise ValueError("TARGET_BINDING_INVALID")
    cmd = [
        "ssh", "-F", "/dev/null", "-T",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "ConnectTimeout=5",
        "--", target, "python3", "-",
    ]
    try:
        result = subprocess.run(
            cmd, input=program.encode("utf-8"), capture_output=True,
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("REMOTE_READONLY_STOP") from None
    if (
        result.returncode != 0
        or len(result.stdout) > 8192
        or len(result.stderr) > 8192
    ):
        raise ValueError("REMOTE_READONLY_STOP")
    try:
        data = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise ValueError("REMOTE_RESPONSE_INVALID") from None
    return _validate_readonly_result(data, baseline)
