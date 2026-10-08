from __future__ import annotations

import ast
import hashlib
import ipaddress
import json
import re
import subprocess
from pathlib import Path

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


def remote_snapshot_once(
    target: str,
    expected_target_sha: str,
    program: str,
    *,
    runner=subprocess.run,
) -> dict:
    try:
        user, ip = target.split("@", 1)
        addr = ipaddress.IPv4Address(ip)
    except (ValueError, TypeError):
        raise ValueError("INVALID_TARGET")
    if (
        user != "root"
        or addr.is_loopback
        or not addr.is_private
        or hashlib.sha256(target.encode()).hexdigest() != expected_target_sha
    ):
        raise ValueError("TARGET_BINDING_INVALID")
    if any(token.lower() in program.lower() for token in FORBIDDEN_REMOTE_SOURCE):
        raise ValueError("REMOTE_SOURCE_UNSAFE")
    cmd = [
        "ssh", "-T", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
        target, "python3", "-",
    ]
    result = runner(
        cmd, input=program.encode(), capture_output=True,
        timeout=15, check=False,
    )
    if result.returncode != 0 or len(result.stdout) > 8192:
        raise ValueError("REMOTE_READONLY_STOP")
    try:
        data = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise ValueError("REMOTE_RESPONSE_INVALID")
    required = {
        "schema", "hardware_sha256", "pairing_sha256",
        "expires_at", "preboot_count", "preboot_hashes",
        "new_count", "read_at", "container_continuity_pass",
        "manager_socket_pass", "tls_live_reprobe_pass",
    }
    if (
        not isinstance(data, dict)
        or set(data) != required
        or data["schema"] != EXPECTED_REMOTE_SCHEMA
        or data["container_continuity_pass"] is not True
        or data["manager_socket_pass"] is not True
        or data["tls_live_reprobe_pass"] is not True
    ):
        raise ValueError("REMOTE_AUTHORITY_INVALID")
    return data
