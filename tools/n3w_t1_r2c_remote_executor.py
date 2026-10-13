from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from n3w_t1_r2c_evidence_schema import (
    EvidenceSchemaError,
    public_requirement_projection,
    validate_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = "READONLY R2C TARGET ARMBIAN EVIDENCE: YES"
GATE_ID = "N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE"
EXECUTION_SCHEMA = "gh.n3w.t1-r2c-readonly-evidence-execution/1"
PUBLIC_SCHEMA = "gh.n3w.t1-r2c-readonly-evidence-public/1"
PROBE_SCHEMA = "gh.n3w.t1-r2c-readonly-probe/1"
CONTRACT_RELATIVE = (
    "docs/development/"
    "N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_PREPARATION_20261013.md"
)
EXPECTED_CONTRACT_BLOB_SHA = "b575e33be67676f8b5e61fac6bc4a94a3dce37ff"
EXECUTOR_RELATIVE = "tools/n3w_t1_r2c_remote_executor.py"
MODULE_BINDINGS = (
    (
        "n3w_t1_r2c_readonly_files",
        "tools/n3w_t1_r2c_readonly_files.py",
        "79ff9f8e9ceeca504d4b190120c69c9a981aa044",
    ),
    (
        "n3w_t1_r2c_readonly_commands",
        "tools/n3w_t1_r2c_readonly_commands.py",
        "6bc8cf35029955d4168a8077a13059a39a1c6218",
    ),
    (
        "n3w_t1_r2c_evidence_schema",
        "tools/n3w_t1_r2c_evidence_schema.py",
        "84e8c0249c439beaf54ae09d8c5e2e6388621544",
    ),
    (
        "n3w_t1_r2c_firstrun",
        "tools/n3w_t1_r2c_firstrun.py",
        "3bca46f0f2b741586439c5d7302fdf96bec62fc8",
    ),
    (
        "n3w_t1_r2c_collectors",
        "tools/n3w_t1_r2c_collectors.py",
        "0856dd53b4f09b37fa52abe1fa129255957ed9ec",
    ),
    (
        "n3w_t1_r2c_collectors_e5_e9",
        "tools/n3w_t1_r2c_collectors_e5_e9.py",
        "8041c776f2e49018639bd9d5bef33c7403f5792f",
    ),
    (
        "n3w_t1_r2c_remote_probe",
        "tools/n3w_t1_r2c_remote_probe.py",
        "3962f4f4b486f74b2d1f1e09cc7e43da6120df2d",
    ),
)
PLACEHOLDERS = (
    "placeholder",
    "<t1>",
    "example.invalid",
    "user@host",
)
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
HEX40_RE = re.compile(r"[0-9a-f]{40}\Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")
MIN_TIMEOUT_SECONDS = 130
MAX_TIMEOUT_SECONDS = 180
MAX_TRANSPORT_OUTPUT_BYTES = 8 * 1024 * 1024


class StopExecution(RuntimeError):
    pass


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _validate_token(value: str, label: str) -> str:
    if TOKEN_RE.fullmatch(value) is None:
        raise StopExecution(f"{label}_invalid")
    return value


def validate_target(target: str) -> None:
    if not target or target.strip() != target or any(ch.isspace() for ch in target):
        raise StopExecution("t1_ssh_target_invalid")
    if target.startswith("-"):
        raise StopExecution("t1_ssh_target_invalid")
    try:
        target.encode("ascii")
    except UnicodeEncodeError as error:
        raise StopExecution("t1_ssh_target_invalid") from error
    folded = target.casefold()
    if any(marker.casefold() in folded for marker in PLACEHOLDERS):
        raise StopExecution("t1_ssh_target_placeholder")


def validate_timeout(timeout_seconds: int) -> None:
    if (
        isinstance(timeout_seconds, bool)
        or timeout_seconds < MIN_TIMEOUT_SECONDS
        or timeout_seconds > MAX_TIMEOUT_SECONDS
    ):
        raise StopExecution("timeout_seconds_invalid")


def validate_expiry(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        raise StopExecution("authorization_expiry_invalid") from error
    if parsed <= datetime.now(timezone.utc):
        raise StopExecution("authorization_expired")
    return value


def _git_text(*arguments: str) -> str:
    try:
        completed = subprocess.run(
            ("git", "-C", str(REPO_ROOT), *arguments),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StopExecution("local_git_unavailable") from error
    if completed.returncode != 0:
        raise StopExecution("local_git_failed")
    return completed.stdout.strip()


def validate_local_source_authority(expected_source_head: str) -> dict[str, Any]:
    if HEX40_RE.fullmatch(expected_source_head) is None:
        raise StopExecution("expected_source_head_invalid")
    observed_head = _git_text("rev-parse", "HEAD")
    if observed_head != expected_source_head:
        raise StopExecution("local_source_head_mismatch")
    if _git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("local_tracked_worktree_dirty")
    observed: dict[str, str] = {}
    for _, relative, expected_blob in MODULE_BINDINGS:
        blob = _git_text("rev-parse", f"{expected_source_head}:{relative}")
        if blob != expected_blob:
            raise StopExecution(f"source_binding_mismatch:{relative}")
        observed[relative] = blob
    contract_blob = _git_text(
        "rev-parse",
        f"{expected_source_head}:{CONTRACT_RELATIVE}",
    )
    if contract_blob != EXPECTED_CONTRACT_BLOB_SHA:
        raise StopExecution("contract_blob_mismatch")
    executor_blob = _git_text(
        "rev-parse",
        f"{expected_source_head}:{EXECUTOR_RELATIVE}",
    )
    return {
        "expected_source_head": expected_source_head,
        "observed_source_head": observed_head,
        "tracked_worktree_clean": True,
        "module_blobs": observed,
        "contract_blob": contract_blob,
        "executor_blob": executor_blob,
    }


def _read_bound_file(relative: str, expected_blob: str) -> bytes:
    path = REPO_ROOT / relative
    if not path.is_file() or path.is_symlink():
        raise StopExecution(f"bound_source_missing:{relative}")
    data = path.read_bytes()
    if git_blob_sha(data) != expected_blob:
        raise StopExecution(f"bound_source_content_mismatch:{relative}")
    return data


def build_remote_program() -> bytes:
    encoded_modules = []
    for name, relative, expected_blob in MODULE_BINDINGS:
        data = _read_bound_file(relative, expected_blob)
        encoded_modules.append((name, base64.b64encode(data).decode("ascii")))
    bootstrap = [
        "import base64, sys, types",
        f"_modules={encoded_modules!r}",
        "for _name, _encoded in _modules:",
        "    _module = types.ModuleType(_name)",
        "    _module.__file__ = '<r2c-bundle:' + _name + '>'",
        "    sys.modules[_name] = _module",
        "    _source = base64.b64decode(_encoded)",
        "    exec(compile(_source, _module.__file__, 'exec'), _module.__dict__)",
        "raise SystemExit(sys.modules['n3w_t1_r2c_remote_probe'].main())",
        "",
    ]
    return "\n".join(bootstrap).encode()


def contract_sha256() -> str:
    data = _read_bound_file(CONTRACT_RELATIVE, EXPECTED_CONTRACT_BLOB_SHA)
    return sha256_bytes(data)


def validate_evidence_root(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise StopExecution("evidence_root_symlink_forbidden")
    try:
        resolved = expanded.resolve()
        repo = REPO_ROOT.resolve()
        if resolved == repo or repo in resolved.parents:
            raise StopExecution("evidence_root_inside_repository")
        if resolved.exists():
            if not resolved.is_dir():
                raise StopExecution("evidence_root_not_directory")
            metadata = resolved.stat()
            if metadata.st_uid != os.geteuid():
                raise StopExecution("evidence_root_owner_invalid")
            if stat.S_IMODE(metadata.st_mode) != 0o700:
                raise StopExecution("evidence_root_mode_invalid")
            if any(resolved.iterdir()):
                raise StopExecution("evidence_root_not_empty")
        else:
            resolved.mkdir(parents=True, mode=0o700)
        metadata = resolved.stat()
        if metadata.st_uid != os.geteuid():
            raise StopExecution("evidence_root_owner_invalid")
        if stat.S_IMODE(metadata.st_mode) != 0o700:
            raise StopExecution("evidence_root_mode_invalid")
        return resolved
    except StopExecution:
        raise
    except OSError as error:
        raise StopExecution("evidence_root_access_failed") from error


def write_private(path: Path, data: bytes) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise StopExecution("local_evidence_write_failed") from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
        ):
            raise StopExecution("local_evidence_file_metadata_invalid")
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remote_command(
    *,
    execution_id: str,
    source_head: str,
    probe_sha256: str,
    contract_digest: str,
    grant_id: str,
    target_binding_token_sha256: str,
) -> str:
    argv = (
        "sudo",
        "-n",
        "python3",
        "-B",
        "-",
        "--root",
        "/",
        "--execution-id",
        execution_id,
        "--source-head",
        source_head,
        "--probe-sha256",
        probe_sha256,
        "--contract-sha256",
        contract_digest,
        "--grant-id",
        grant_id,
        "--target-binding-token-sha256",
        target_binding_token_sha256,
    )
    return shlex.join(argv)


def ssh_argv(target: str, remote_command: str) -> list[str]:
    validate_target(target)
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "RequestTTY=no",
        target,
        remote_command,
    ]


def _stop_result(
    *,
    error_code: str,
    stdout: bytes,
    stderr: bytes,
    returncode: int | None,
    timed_out: bool,
    authorization_consumed: bool,
) -> dict[str, Any]:
    return {
        "schema": EXECUTION_SCHEMA,
        "status": "STOP",
        "error_code": error_code,
        "returncode": returncode,
        "timed_out": timed_out,
        "authorization_consumed": authorization_consumed,
        "replay_permitted": False,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "t1_access": authorization_consumed,
        "intentional_target_write": False,
        "service_mutation": False,
        "board_access": False,
        "merge": False,
    }


def _persist_transport_outputs(root: Path, stdout: bytes, stderr: bytes) -> None:
    total = len(stdout) + len(stderr)
    if total > MAX_TRANSPORT_OUTPUT_BYTES:
        write_private(
            root / "transport-output-summary.json",
            _json_bytes(
                {
                    "status": "STOP_TRUNCATED",
                    "stdout_bytes": len(stdout),
                    "stderr_bytes": len(stderr),
                    "stdout_sha256": sha256_bytes(stdout),
                    "stderr_sha256": sha256_bytes(stderr),
                }
            ),
        )
        raise StopExecution("transport_output_limit")
    write_private(root / "stdout.bin", stdout)
    write_private(root / "stderr.bin", stderr)


def validate_probe_response(
    document: Any,
    *,
    execution_id: str,
    source_head: str,
    probe_sha256: str,
    contract_digest: str,
    grant_id: str,
    target_binding_token_sha256: str,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise StopExecution("probe_response_invalid")
    if document.get("schema") != PROBE_SCHEMA or document.get("status") != "PASS":
        raise StopExecution("probe_response_not_pass")
    report = document.get("report")
    if not isinstance(report, dict):
        raise StopExecution("probe_report_invalid")
    try:
        validate_report(report)
    except EvidenceSchemaError as error:
        raise StopExecution("probe_report_schema_invalid") from error
    expected = {
        "execution_id": execution_id,
        "source_head": source_head,
        "probe_sha256": probe_sha256,
        "contract_sha256": contract_digest,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise StopExecution(f"probe_report_binding_invalid:{key}")
    authorization = report["authorization"]
    if authorization != {
        "grant_id": grant_id,
        "granted": True,
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }:
        raise StopExecution("probe_report_authorization_invalid")
    binding = report["target_binding"]
    if binding.get("binding_token_sha256") != target_binding_token_sha256:
        raise StopExecution("probe_report_target_binding_invalid")
    if binding.get("strict_host_key_checking_required") is not True:
        raise StopExecution("probe_report_host_key_policy_invalid")
    if not isinstance(binding.get("same_boot"), bool):
        raise StopExecution("probe_report_same_boot_invalid")
    boundaries = report["boundaries"]
    if boundaries != {
        "t1_access": True,
        "intentional_target_write": False,
        "service_mutation": False,
        "board_access": False,
        "merge": False,
    }:
        raise StopExecution("probe_report_boundary_invalid")
    return report


def build_public_candidate(report: dict[str, Any]) -> dict[str, Any]:
    requirements = {
        requirement_id: public_requirement_projection(
            requirement_id,
            report["requirements"][requirement_id],
        )
        for requirement_id in sorted(report["requirements"])
    }
    return {
        "schema": PUBLIC_SCHEMA,
        "execution_id": report["execution_id"],
        "source_head": report["source_head"],
        "probe_sha256": report["probe_sha256"],
        "contract_sha256": report["contract_sha256"],
        "requirements": requirements,
        "capture_status": report["capture_status"],
        "static_review_status": report["static_review_status"],
        "stop_reasons": list(report["stop_reasons"]),
        "boundaries": dict(report["boundaries"]),
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_required": True,
        "disk_capture_ready": False,
        "public_projection_review": "NOT_REVIEWED",
    }


def _persist_result(root: Path, result: dict[str, Any]) -> None:
    write_private(root / "result.json", _json_bytes(result))


def execute(
    *,
    target: str,
    target_binding_id: str,
    evidence_root: Path,
    confirmation: str,
    grant_id: str,
    authorization_expires_at: str,
    execution_id: str,
    expected_source_head: str,
    timeout_seconds: int = 150,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    validate_target(target)
    _validate_token(target_binding_id, "target_binding_id")
    _validate_token(grant_id, "grant_id")
    _validate_token(execution_id, "execution_id")
    validate_expiry(authorization_expires_at)
    validate_timeout(timeout_seconds)
    authority = validate_local_source_authority(expected_source_head)
    program = build_remote_program()
    probe_digest = sha256_bytes(program)
    contract_digest = contract_sha256()
    binding_digest = sha256_bytes(target_binding_id.encode())
    root = validate_evidence_root(evidence_root)

    write_private(
        root / "start.json",
        _json_bytes(
            {
                "schema": EXECUTION_SCHEMA,
                "status": "STARTED",
                "gate_id": GATE_ID,
                "execution_id": execution_id,
                "expected_source_head": expected_source_head,
                "observed_source_head": authority["observed_source_head"],
                "executor_blob": authority["executor_blob"],
                "probe_sha256": probe_digest,
                "contract_sha256": contract_digest,
                "target_binding_token_sha256": binding_digest,
                "authorization_grant_id": grant_id,
                "authorization_expires_at": authorization_expires_at,
                "replay_permitted": False,
            }
        ),
    )
    write_private(
        root / "authorization-claim.json",
        _json_bytes(
            {
                "schema": EXECUTION_SCHEMA,
                "gate_id": GATE_ID,
                "execution_id": execution_id,
                "grant_id": grant_id,
                "granted": True,
                "claimed": True,
                "consumed": False,
                "replay_permitted": False,
                "expected_source_head": expected_source_head,
                "probe_sha256": probe_digest,
                "contract_sha256": contract_digest,
                "target_binding_token_sha256": binding_digest,
                "authorization_expires_at": authorization_expires_at,
            }
        ),
    )

    remote_command = _remote_command(
        execution_id=execution_id,
        source_head=expected_source_head,
        probe_sha256=probe_digest,
        contract_digest=contract_digest,
        grant_id=grant_id,
        target_binding_token_sha256=binding_digest,
    )
    argv = ssh_argv(target, remote_command)
    write_private(
        root / "command.json",
        _json_bytes(
            {
                "schema": EXECUTION_SCHEMA,
                "execution_id": execution_id,
                "expected_source_head": expected_source_head,
                "tracked_worktree_clean": authority["tracked_worktree_clean"],
                "module_blobs": authority["module_blobs"],
                "contract_blob": authority["contract_blob"],
                "executor_blob": authority["executor_blob"],
                "probe_sha256": probe_digest,
                "contract_sha256": contract_digest,
                "target_locator_sha256": sha256_bytes(target.encode()),
                "target_binding_token_sha256": binding_digest,
                "remote_command": remote_command,
                "strict_host_key_checking": True,
                "python_bytecode_write_disabled": True,
                "remote_probe_file_created": False,
                "replay_permitted": False,
            }
        ),
    )

    authorization_consumed = True
    try:
        completed = subprocess.run(
            argv,
            input=program,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode()
        if isinstance(stderr, str):
            stderr = stderr.encode()
        try:
            _persist_transport_outputs(root, stdout, stderr)
        except StopExecution:
            pass
        result = _stop_result(
            error_code="readonly_probe_timeout",
            stdout=stdout,
            stderr=stderr,
            returncode=None,
            timed_out=True,
            authorization_consumed=authorization_consumed,
        )
        _persist_result(root, result)
        raise StopExecution("readonly_probe_timeout") from error
    except OSError as error:
        stdout = b""
        stderr = b""
        _persist_transport_outputs(root, stdout, stderr)
        result = _stop_result(
            error_code="ssh_transport_error",
            stdout=stdout,
            stderr=stderr,
            returncode=None,
            timed_out=False,
            authorization_consumed=authorization_consumed,
        )
        _persist_result(root, result)
        raise StopExecution("ssh_transport_error") from error

    try:
        _persist_transport_outputs(root, completed.stdout, completed.stderr)
    except StopExecution:
        result = _stop_result(
            error_code="transport_output_limit",
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            timed_out=False,
            authorization_consumed=authorization_consumed,
        )
        _persist_result(root, result)
        raise

    if completed.returncode != 0:
        result = _stop_result(
            error_code="readonly_probe_failed",
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            timed_out=False,
            authorization_consumed=authorization_consumed,
        )
        _persist_result(root, result)
        raise StopExecution(f"readonly_probe_failed:{completed.returncode}")

    try:
        document = json.loads(completed.stdout.decode("utf-8"))
        report = validate_probe_response(
            document,
            execution_id=execution_id,
            source_head=expected_source_head,
            probe_sha256=probe_digest,
            contract_digest=contract_digest,
            grant_id=grant_id,
            target_binding_token_sha256=binding_digest,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, StopExecution) as error:
        result = _stop_result(
            error_code="probe_report_invalid",
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            timed_out=False,
            authorization_consumed=authorization_consumed,
        )
        _persist_result(root, result)
        raise StopExecution("probe_report_invalid") from error

    write_private(root / "report.json", _json_bytes(report))
    public_candidate = build_public_candidate(report)
    write_private(root / "public-candidate.json", _json_bytes(public_candidate))
    write_private(
        root / "authorization-result.json",
        _json_bytes(
            {
                "schema": EXECUTION_SCHEMA,
                "execution_id": execution_id,
                "grant_id": grant_id,
                "claimed": True,
                "consumed": True,
                "replay_permitted": False,
                "remote_exit": completed.returncode,
            }
        ),
    )

    result = {
        "schema": EXECUTION_SCHEMA,
        "status": "PASS",
        "gate_id": GATE_ID,
        "execution_id": execution_id,
        "expected_source_head": expected_source_head,
        "observed_source_head": authority["observed_source_head"],
        "executor_blob": authority["executor_blob"],
        "probe_sha256": probe_digest,
        "contract_sha256": contract_digest,
        "capture_status": report["capture_status"],
        "static_review_status": report["static_review_status"],
        "public_projection_review": report["public_projection_review"],
        "same_boot": report["target_binding"]["same_boot"],
        "remote_exit": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stderr_bytes": len(completed.stderr),
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "t1_access": True,
        "intentional_target_write": False,
        "service_mutation": False,
        "board_access": False,
        "merge": False,
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_required": True,
        "disk_capture_ready": False,
    }
    _persist_result(root, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--target")
    parser.add_argument("--target-binding-id")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--grant-id")
    parser.add_argument("--authorization-expires-at")
    parser.add_argument("--execution-id")
    parser.add_argument("--expected-source-head")
    parser.add_argument("--timeout-seconds", type=int, default=150)
    args = parser.parse_args()
    required = (
        args.target,
        args.target_binding_id,
        args.evidence_root,
        args.grant_id,
        args.authorization_expires_at,
        args.execution_id,
        args.expected_source_head,
    )
    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": EXECUTION_SCHEMA,
                    "status": "STOP",
                    "error_code": "execute_required",
                },
                sort_keys=True,
            )
        )
        return 2
    if any(value is None for value in required):
        print(
            json.dumps(
                {
                    "schema": EXECUTION_SCHEMA,
                    "status": "STOP",
                    "error_code": "execution_argument_missing",
                },
                sort_keys=True,
            )
        )
        return 2
    try:
        result = execute(
            target=args.target,
            target_binding_id=args.target_binding_id,
            evidence_root=args.evidence_root,
            confirmation=args.confirm,
            grant_id=args.grant_id,
            authorization_expires_at=args.authorization_expires_at,
            execution_id=args.execution_id,
            expected_source_head=args.expected_source_head,
            timeout_seconds=args.timeout_seconds,
        )
    except StopExecution as error:
        print(
            json.dumps(
                {
                    "schema": EXECUTION_SCHEMA,
                    "status": "STOP",
                    "error_code": str(error),
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
