from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "n3w.p4.preboot-five-identity-readonly/1"
FROZEN_SNAPSHOT_SHA256 = "81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c"
FROZEN_SNAPSHOT_SCHEMA = "n3w.kf050.runtime-identity-snapshot/1"
SOURCE_BLOBS = {
    "bridge_handoff.py": "e277949c3db5675bd460124832a382d6a2765539",
    "remote_projection.py": "7b3ba146583b61271b41390736b67207c8d4c14e",
    "host_readonly.py": "0c62bc1b006eb2feab2e89d393cd477ad0912d83",
    "validator.py": "3b7dc0d085dcda52fda0334840d75d5f8678bc1b",
}
PRIVATE_BASELINE = (
    Path.home()
    / "N3W_PRIVATE_EVIDENCE"
    / "N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01"
    / "manager_preboot_identity_snapshot.json"
)
APPROVED_R5A_SOURCE_GIT_BLOB = ""
APPROVED_KNOWN_HOSTS_SHA256 = ""
APPROVED_T1_HOST_KEY_FINGERPRINT = ""
READONLY_RUNTIME_FUNCTIONS = ("_cmd", "_container", "_env", "_path", "_assert_runtime")
RUNTIME_CONSTANTS = (
    "MANAGER_ID_SHA", "BROKER_ID_SHA", "MANAGER_STARTED", "BROKER_STARTED",
    "EXPECTED_TLS_CA", "EXPECTED_TLS_LEAF", "EXPECTED_T1_IP_SHA",
)

PREBOOT_REMOTE_BODY = '''
def _five_identity_snapshot(registration, credential, original):
    values = set()
    with contextlib.closing(_ro(registration)) as reg:
        with contextlib.closing(_ro(credential)) as cred:
            for conn, tables in ((reg, TABLES), (cred, ("credential_assignments",))):
                for table in tables:
                    rows = _query(conn, "SELECT DISTINCT hardware_id FROM " + table + " WHERE hardware_id IS NOT NULL")
                    for row in rows:
                        if not isinstance(row[0], str) or not row[0]:
                            reject("PREBOOT_SCHEMA_INVALID")
                        values.add(sha(row[0]))
            pending = _query(reg, "SELECT 1 FROM pairing_sessions WHERE state=? LIMIT 1", ("pending",))
            if pending:
                reject("PREBOOT_PENDING_PRESENT")
    result = frozenset(values)
    if len(result) != 5 or result != original:
        reject("PREBOOT_IDENTITY_CHANGED")
    return result


def main_preboot(frozen):
    if not isinstance(frozen, list) or len(frozen) != 5 or frozen != sorted(set(frozen)):
        reject("PREBOOT_AUTHORITY_INVALID")
    if not all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in frozen):
        reject("PREBOOT_AUTHORITY_INVALID")
    registration, credential = _assert_runtime()
    original = frozenset(frozen)
    first = _five_identity_snapshot(registration, credential, original)
    second = _five_identity_snapshot(registration, credential, original)
    if first != second:
        reject("PREBOOT_CHANGED_DURING_READ")
    return {
        "schema": "n3w.p4.preboot-five-identity-readonly/1",
        "preboot_count": len(second),
        "preboot_hashes": sorted(second),
        "new_count": 0,
        "pending_count": 0,
        "container_continuity_pass": True,
        "manager_socket_pass": True,
        "tls_live_reprobe_pass": True,
        "read_at": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(main_preboot(BASELINE_HASHES), sort_keys=True))
    except (GateStop, KeyError, ValueError, TypeError, sqlite3.Error, OSError):
        print(json.dumps({"status": "STOP_PREBOOT_READONLY"}))
        sys.exit(2)
'''

def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()


def _regular_pinned(path: Path, expected_sha: str, *, git: bool) -> bytes:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("SOURCE_OR_AUTHORITY_PATH_INVALID")
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError("SOURCE_OR_AUTHORITY_SYMLINK")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 131072:
                raise ValueError("SOURCE_OR_AUTHORITY_NOT_REGULAR")
            raw = os.read(fd, 131073)
        finally:
            os.close(fd)
    except OSError:
        raise ValueError("SOURCE_OR_AUTHORITY_UNAVAILABLE") from None
    digest = _git_blob(raw) if git else hashlib.sha256(raw).hexdigest()
    if not expected_sha or not hmac.compare_digest(digest, expected_sha):
        raise ValueError("SOURCE_OR_AUTHORITY_DRIFT")
    return raw


def _source_root() -> Path:
    return Path(__file__).absolute().parent


def _source_bytes() -> dict[str, bytes]:
    root = _source_root()
    return {name: _regular_pinned(root / name, digest, git=True) for name, digest in SOURCE_BLOBS.items()}


def _private_snapshot() -> frozenset[str]:
    path = PRIVATE_BASELINE
    if path.is_symlink() or any(part.is_symlink() for part in path.parents):
        raise ValueError("PRIVATE_SNAPSHOT_SYMLINK")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.getuid()
                or info.st_size < 1
                or info.st_size > 16384
            ):
                raise ValueError("PRIVATE_SNAPSHOT_AUTHORITY_INVALID")
            data = os.read(fd, 16385)
        finally:
            os.close(fd)
    except OSError:
        raise ValueError("PRIVATE_SNAPSHOT_UNAVAILABLE") from None
    if hashlib.sha256(data).hexdigest() != FROZEN_SNAPSHOT_SHA256:
        raise ValueError("PRIVATE_SNAPSHOT_DRIFT")
    try:
        obj = json.loads(data)
    except (UnicodeError, ValueError):
        raise ValueError("PRIVATE_SNAPSHOT_INVALID") from None
    if not isinstance(obj, dict) or set(obj) != {
        "schema", "hardware_id_sha256", "hardware_id_count",
        "read_only", "manager_mutation", "manager_replay_mutation",
    }:
        raise ValueError("PRIVATE_SNAPSHOT_INVALID")
    hashes = obj["hardware_id_sha256"]
    if (
        obj["schema"] != FROZEN_SNAPSHOT_SCHEMA
        or type(obj["hardware_id_count"]) is not int
        or obj["hardware_id_count"] != 5
        or obj["read_only"] is not True
        or obj["manager_mutation"] is not False
        or obj["manager_replay_mutation"] is not False
        or not isinstance(hashes, list)
        or len(hashes) != 5
        or hashes != sorted(set(hashes))
        or not all(isinstance(h, str) and re.fullmatch("[0-9a-f]{64}", h) for h in hashes)
    ):
        raise ValueError("PRIVATE_SNAPSHOT_INVALID")
    return frozenset(hashes)


def _runtime_source(source: str) -> str:
    tree = ast.parse(source)
    constants = {}
    functions = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for name in node.targets:
                if isinstance(name, ast.Name) and name.id in RUNTIME_CONSTANTS:
                    constants[name.id] = node
        if isinstance(node, ast.FunctionDef):
            functions[node.name] = node
    if set(constants) != set(RUNTIME_CONSTANTS) or not all(n in functions for n in READONLY_RUNTIME_FUNCTIONS):
        raise ValueError("RUNTIME_CORE_MISSING")
    pieces = []
    for name in RUNTIME_CONSTANTS:
        pieces.append(ast.get_source_segment(source, constants[name]))
    for name in READONLY_RUNTIME_FUNCTIONS:
        pieces.append(ast.get_source_segment(source, functions[name]))
    return "\n\n".join(pieces) + "\n"


def build_preboot_program(source_bytes: dict[str, bytes], baseline: frozenset[str]) -> str:
    for name, expected in SOURCE_BLOBS.items():
        if name not in source_bytes or _git_blob(source_bytes[name]) != expected:
            raise ValueError("READONLY_SOURCE_DRIFT")
    if len(baseline) != 5 or not all(re.fullmatch("[0-9a-f]{64}", x) for x in baseline):
        raise ValueError("PREBOOT_BASELINE_INVALID")
    bridge = source_bytes["bridge_handoff.py"].decode("utf-8")
    probe = source_bytes["remote_projection.py"].decode("utf-8")
    tree = ast.parse(bridge)
    names = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names[node.name] = node
    core_names = ("GateStop", "sha", "reject", "_ro", "_query")
    if not all(n in names for n in core_names):
        raise ValueError("READONLY_CORE_MISSING")
    imports = (
        "import contextlib\nimport hashlib\nimport json\nimport re\nimport os\nimport socket\nimport ssl\n"
        "import ipaddress\nimport stat\nimport sqlite3\nimport subprocess\nimport sys\n"
        "from datetime import UTC, datetime\nfrom pathlib import Path, PurePosixPath\n"
    )
    core = "\n\n".join(ast.get_source_segment(bridge, names[n]) for n in core_names)
    payload = (
        imports + "\nSCHEMA = " + repr(SCHEMA)
        + "\nTABLES = " + repr((
            "registrations", "pairing_sessions", "registration_events",
            "registration_node_history", "node_id_leases", "retirement_outbox",
        ))
        + "\n\n" + core + "\n\n"
        + _runtime_source(probe)
        + "\nBASELINE_HASHES = " + json.dumps(sorted(baseline)) + "\n"
        + PREBOOT_REMOTE_BODY
    )
    ast.parse(payload)
    forbidden = (
        "import-payload", "setup_secret", "OneShotImporter", "capture_private_qr",
        "authorize-repair", "authorize-credential-recovery", "erase_flash",
        "write_flash", "docker exec -i", "GHN3W2",
    )
    if any(token.lower() in payload.lower() for token in forbidden):
        raise ValueError("REMOTE_UNSAFE_SOURCE")
    for node in ast.walk(ast.parse(payload)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"executescript", "executemany", "commit", "rollback"}:
                raise ValueError("REMOTE_SQL_MUTATION")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.search(r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|REPLACE|VACUUM)\b", node.value, re.I):
                raise ValueError("REMOTE_SQL_MUTATION")
    return payload


def _trusted_target(target: str, probe: bytes) -> str:
    try:
        user, ip = target.split("@", 1)
        addr = ipaddress.IPv4Address(ip)
        source = probe.decode("utf-8")
        match = re.search(r'^EXPECTED_T1_IP_SHA = "([0-9a-f]{64})"$', source, re.M)
    except (AttributeError, UnicodeError, ValueError):
        raise ValueError("TARGET_INVALID") from None
    if (
        not match or user != "root" or str(addr) != ip
        or not addr.is_private or addr.is_loopback
        or hashlib.sha256(ip.encode("ascii")).hexdigest() != match.group(1)
    ):
        raise ValueError("TARGET_BINDING_INVALID")
    return ip


def _host_key_check(ip: str, known_hosts_path: Path) -> None:
    if not APPROVED_KNOWN_HOSTS_SHA256 or not APPROVED_T1_HOST_KEY_FINGERPRINT:
        raise ValueError("HOST_KEY_AUTHORITY_NOT_FROZEN")
    path = known_hosts_path
    if not path.is_absolute() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("HOST_KEY_FILE_INVALID")
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or (info.st_mode & 0o022):
            raise ValueError("HOST_KEY_FILE_INVALID")
    except OSError:
        raise ValueError("HOST_KEY_FILE_INVALID") from None
    _regular_pinned(path, APPROVED_KNOWN_HOSTS_SHA256, git=False)
    try:
        found = subprocess.run(
            ["ssh-keygen", "-F", ip, "-f", str(path)],
            capture_output=True, check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("HOST_KEY_LOOKUP_FAILED") from None
    if found.returncode != 0 or len(found.stdout) > 8192 or len(found.stderr) > 8192:
        raise ValueError("HOST_KEY_LOOKUP_FAILED")
    lines = [line.split() for line in found.stdout.decode("ascii").splitlines() if line and not line.startswith("#")]
    if len(lines) != 1 or len(lines[0]) < 3 or lines[0][1] not in (
        "ssh-ed25519", "ecdsa-sha2-nistp256", "ssh-rsa",
    ):
        raise ValueError("HOST_KEY_NOT_UNIQUE")
    try:
        key = base64.b64decode(lines[0][2], validate=True)
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key).digest()).decode("ascii").rstrip("=")
    except (ValueError, UnicodeError):
        raise ValueError("HOST_KEY_INVALID") from None
    if not hmac.compare_digest(fingerprint, APPROVED_T1_HOST_KEY_FINGERPRINT):
        raise ValueError("HOST_KEY_MISMATCH")


def mac_static_preflight(target: str, known_hosts_path: Path) -> tuple[str, frozenset[str], str]:
    if not APPROVED_R5A_SOURCE_GIT_BLOB:
        raise ValueError("R5A_SOURCE_NOT_INDEPENDENTLY_PINNED")
    root = _source_root()
    _regular_pinned(root / "field_preboot_readonly.py", APPROVED_R5A_SOURCE_GIT_BLOB, git=True)
    sources = _source_bytes()
    baseline = _private_snapshot()
    ip = _trusted_target(target, sources["remote_projection.py"])
    program = build_preboot_program(sources, baseline)
    _host_key_check(ip, known_hosts_path)
    return program, baseline, ip


def _validate_preboot_response(data: object, baseline: frozenset[str]) -> dict:
    required = {
        "schema", "preboot_count", "preboot_hashes", "new_count", "pending_count",
        "container_continuity_pass", "manager_socket_pass", "tls_live_reprobe_pass",
        "read_at",
    }
    if not isinstance(data, dict) or set(data) != required or data["schema"] != SCHEMA:
        raise ValueError("PREBOOT_RESPONSE_INVALID")
    if (
        type(data["preboot_count"]) is not int or data["preboot_count"] != 5
        or type(data["new_count"]) is not int or data["new_count"] != 0
        or type(data["pending_count"]) is not int or data["pending_count"] != 0
        or type(data["preboot_hashes"]) is not list
        or data["preboot_hashes"] != sorted(baseline)
        or data["container_continuity_pass"] is not True
        or data["manager_socket_pass"] is not True
        or data["tls_live_reprobe_pass"] is not True
    ):
        raise ValueError("PREBOOT_RESPONSE_INVALID")
    try:
        time = datetime.fromisoformat(data["read_at"].replace("Z", "+00:00"))
        if time.tzinfo is None:
            raise ValueError()
        age = (datetime.now(UTC) - time.astimezone(UTC)).total_seconds()
    except (AttributeError, ValueError, TypeError):
        raise ValueError("PREBOOT_RESPONSE_INVALID") from None
    if age < 0 or age > 10:
        raise ValueError("PREBOOT_READBACK_STALE")
    return {
        "stage": "P4_PREBOOT_FIVE_IDENTITY_READONLY",
        "status": "PASS_READONLY_NO_PAIRING",
        "preboot_count": 5,
        "new_count": 0,
        "pending_count": 0,
    }


def preboot_host_once(target: str, known_hosts_path: Path) -> dict:
    program, baseline, _ = mac_static_preflight(target, known_hosts_path)
    cmd = [
        "ssh", "-F", "/dev/null", "-T",
        "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "UpdateHostKeys=no", "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "UserKnownHostsFile=" + str(known_hosts_path),
        "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
        "-o", "ProxyCommand=none", "-o", "ProxyJump=none",
        "-o", "ConnectTimeout=5", "--", target, "python3", "-",
    ]
    try:
        result = subprocess.run(
            cmd, input=program.encode("utf-8"), capture_output=True,
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("PREBOOT_SSH_UNKNOWN_STOP") from None
    if (
        result.returncode != 0 or len(result.stdout) > 8192 or len(result.stderr) > 8192
    ):
        raise ValueError("PREBOOT_REMOTE_STOP")
    try:
        data = json.loads(result.stdout)
    except (UnicodeError, ValueError):
        raise ValueError("PREBOOT_RESPONSE_INVALID") from None
    return _validate_preboot_response(data, baseline)
