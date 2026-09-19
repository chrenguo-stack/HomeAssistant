#!/usr/bin/env python3
"""One-shot offline generator for Stage 2D-9R private command material.

Default mode is a read-only toolchain/custody probe. Execution requires an exact,
unexpired, one-shot U1 authorization and explicit --execute. The tool never starts
a Broker, opens a socket, accesses a board, or invokes a firmware command.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from typing import Any

AUTH_SCHEMA = "gh.h3.n2.stage2d9r-private-command-material-u1-authorization/1"
AUTH_OPERATION = "GENERATE_PRIVATE_COMMAND_MATERIAL"
AUTH_PREFIX = "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-"
STAGE = "H3/N2 Stage 2D-9R G3R"
RUN_SUFFIX = "tlsvalid01"
CUSTODY_RULE = "HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_COMMAND_MATERIAL_V1"
CUSTODY_RELATIVE = Path(".local/state/greenhouse-stage2d9r/private-command-material-tlsvalid01")
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
TOKEN_FILE = "unlock-token.hex"
PRIVATE_DESCRIPTOR = "private-command-material-descriptor.json"
PUBLIC_DESCRIPTOR = "public-command-material-descriptor.redacted.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class GenerationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GenerationError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def write_private(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
    require(file_mode(path) == "0600", "private file mode mismatch")


def replace_private(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".new")
    require(not temp.exists(), "private replacement temporary already exists")
    write_private(temp, data)
    os.replace(temp, path)
    os.chmod(path, 0o600)
    require(file_mode(path) == "0600", "private file mode mismatch")


def default_root(home: Path) -> Path:
    return (home.resolve(strict=True) / CUSTODY_RELATIVE).resolve(strict=False)


def default_marker(home: Path, authorization_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", authorization_id)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(
        strict=False
    )


def validate_root(root: Path, home: Path, repository_root: Path | None) -> None:
    home = home.resolve(strict=True)
    require(root.resolve(strict=False) == default_root(home), "custody root selection rule mismatch")
    require(not root.exists(), "custody root already exists")
    for forbidden in (Path("/tmp"), Path("/private/tmp"), Path("/Users/Shared")):
        try:
            root.relative_to(forbidden)
        except ValueError:
            continue
        raise GenerationError("custody root is in a shared temporary location")
    require(root.is_relative_to(home), "custody root is outside the user home")
    if repository_root is not None:
        repo = repository_root.resolve(strict=True)
        try:
            root.relative_to(repo)
        except ValueError:
            pass
        else:
            raise GenerationError("custody root is inside the repository")


def parse_utc(value: object, field: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"{field} invalid")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GenerationError(f"{field} invalid") from exc
    return result.astimezone(timezone.utc)


def authorization_digest(record: dict[str, Any]) -> str:
    copy = dict(record)
    copy.pop("record_sha256", None)
    return canonical_json_sha256(copy)


def probe_summary(generator: Path, home: Path) -> dict[str, object]:
    python = Path(sys.executable).resolve(strict=True)
    root = default_root(home)
    return {
        "schema": "gh.h3.n2.stage2d9r-private-command-material-toolchain-probe/1",
        "stage": STAGE,
        "generator_sha256": sha256_file(generator.resolve(strict=True)),
        "python_executable_sha256": sha256_file(python),
        "python_version": sys.version.replace("\n", " ")[:240],
        "custody_root_selection_rule": CUSTODY_RULE,
        "custody_root_digest_sha256": sha256_bytes(str(root).encode()),
        "custody_root_exists": root.exists(),
        "private_paths_included": False,
        "secret_values_included": False,
        "board_operation": False,
        "network_operation": False,
        "broker_started": False,
    }


def validate_authorization(
    record: dict[str, Any],
    source_sha: str,
    implementation_binding: str,
    generator_sha: str,
    python_sha: str,
    home: Path,
    now: datetime,
) -> tuple[str, Path, str]:
    require(record.get("schema") == AUTH_SCHEMA, "authorization schema mismatch")
    require(record.get("stage") == STAGE, "authorization stage mismatch")
    authorization_id = record.get("authorization_id")
    require(isinstance(authorization_id, str) and authorization_id.startswith(AUTH_PREFIX), "authorization id invalid")
    require(record.get("operation") == AUTH_OPERATION, "authorization operation mismatch")
    require(record.get("authorized") is True, "authorization is not granted")
    require(record.get("one_shot") is True, "authorization must be one-shot")
    require(record.get("replay_permitted") is False, "authorization replay forbidden")
    require(record.get("test_run_suffix") == RUN_SUFFIX, "run suffix mismatch")
    require(record.get("custody_root_selection_rule") == CUSTODY_RULE, "custody rule mismatch")
    require(HEX40.fullmatch(source_sha) is not None, "source sha invalid")
    require(HEX40.fullmatch(implementation_binding) is not None, "implementation binding invalid")
    require(record.get("source_sha") == source_sha, "source sha mismatch")
    require(record.get("implementation_binding") == implementation_binding, "implementation binding mismatch")
    require(record.get("generator_sha256") == generator_sha, "generator sha mismatch")
    require(record.get("python_executable_sha256") == python_sha, "python sha mismatch")
    root = default_root(home)
    require(
        record.get("custody_root_digest_sha256") == sha256_bytes(str(root).encode()),
        "custody digest mismatch",
    )
    issued = parse_utc(record.get("issued_at"), "issued_at")
    expires = parse_utc(record.get("expires_at"), "expires_at")
    require(expires > issued, "authorization interval invalid")
    require(expires - issued <= timedelta(hours=2), "authorization interval too long")
    require(issued <= now <= expires, "authorization is not currently valid")
    observed = authorization_digest(record)
    require(record.get("record_sha256") == observed, "authorization record digest mismatch")
    marker = default_marker(home, authorization_id)
    require(not marker.exists(), "authorization already claimed or consumed")
    return authorization_id, marker, observed


def claim(marker: Path, authorization_id: str, record_sha: str) -> None:
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(marker.parent, 0o700)
    require(file_mode(marker.parent) == "0700", "authorization directory mode mismatch")
    payload = {
        "schema": "gh.h3.n2.stage2d9r-private-command-material-u1-consumption/1",
        "authorization_id": authorization_id,
        "status": "CLAIMED",
        "record_sha256": record_sha,
        "one_shot": True,
        "replay_permitted": False,
        "secret_values_included": False,
        "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    write_private(marker, json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n")


def finalize(marker: Path, public_descriptor_sha: str) -> None:
    payload = json.loads(marker.read_text())
    payload["status"] = "CONSUMED"
    payload["consumed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["public_descriptor_sha256"] = public_descriptor_sha
    replace_private(marker, json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n")


def execute(
    authorization_path: Path,
    source_sha: str,
    implementation_binding: str,
    repository_root: Path | None,
    generator: Path,
    home: Path,
) -> dict[str, object]:
    python = Path(sys.executable).resolve(strict=True)
    generator_sha = sha256_file(generator)
    python_sha = sha256_file(python)
    record = json.loads(authorization_path.read_text())
    authorization_id, marker, record_sha = validate_authorization(
        record,
        source_sha,
        implementation_binding,
        generator_sha,
        python_sha,
        home,
        datetime.now(timezone.utc),
    )
    root = default_root(home)
    validate_root(root, home, repository_root)
    claim(marker, authorization_id, record_sha)

    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root.parent, 0o700)
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    require(file_mode(root) == "0700", "custody root mode mismatch")

    token_hex = secrets.token_hex(32)
    require(HEX64.fullmatch(token_hex) is not None and token_hex != "0" * 64, "generated token invalid")
    token_path = root / TOKEN_FILE
    write_private(token_path, (token_hex + "\n").encode())
    unlock_digest = sha256_bytes(bytes.fromhex(token_hex))
    token_file_sha = sha256_file(token_path)

    public_descriptor = {
        "schema": "gh.h3.n2.stage2d9r-public-command-material-descriptor/1",
        "stage": STAGE,
        "state": "COMMAND_MATERIAL_FROZEN",
        "source_sha": source_sha,
        "implementation_binding": implementation_binding,
        "test_run_suffix": RUN_SUFFIX,
        "unlock_digest_sha256": unlock_digest,
        "private_material_package_sha256": canonical_json_sha256(
            {
                "schema": "gh.h3.n2.stage2d9r-private-command-material-set/1",
                "unlock_token_file_sha256": token_file_sha,
            }
        ),
        "private_values_included": False,
        "private_paths_included": False,
        "raw_unlock_token_included": False,
        "execution_authorized": False,
        "board_operation_authorized": False,
        "network_operation_authorized": False,
        "broker_operation_authorized": False,
        "prepare_authorized": False,
        "verify_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
    }
    public_bytes = json.dumps(public_descriptor, indent=2, sort_keys=True).encode() + b"\n"
    public_path = root / PUBLIC_DESCRIPTOR
    write_private(public_path, public_bytes)
    public_sha = sha256_bytes(public_bytes)

    private_descriptor = {
        "schema": "gh.h3.n2.stage2d9r-private-command-material-descriptor/1",
        "stage": STAGE,
        "state": "COMMAND_MATERIAL_FROZEN",
        "source_sha": source_sha,
        "implementation_binding": implementation_binding,
        "generator_sha256": generator_sha,
        "python_executable_sha256": python_sha,
        "python_version": sys.version.replace("\n", " ")[:240],
        "test_run_suffix": RUN_SUFFIX,
        "custody_root": str(root),
        "custody_root_mode": "0700",
        "unlock_token": {
            "relative_path": TOKEN_FILE,
            "mode": "0600",
            "file_sha256": token_file_sha,
            "unlock_digest_sha256": unlock_digest,
        },
        "public_descriptor_sha256": public_sha,
        "authorization": {
            "authorization_id": authorization_id,
            "operation": AUTH_OPERATION,
            "authorized": True,
            "consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "record_sha256": record_sha,
        },
        "private_values_included": False,
        "raw_unlock_token_in_descriptor": False,
        "board_operation_authorized": False,
        "network_operation_authorized": False,
        "broker_operation_authorized": False,
        "prepare_authorized": False,
        "verify_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
    }
    private_bytes = json.dumps(private_descriptor, indent=2, sort_keys=True).encode() + b"\n"
    private_path = root / PRIVATE_DESCRIPTOR
    write_private(private_path, private_bytes)
    finalize(marker, public_sha)

    token_hex = "0" * len(token_hex)
    return {
        "schema": "gh.h3.n2.stage2d9r-private-command-material-generation-result/1",
        "status": "PASS",
        "authorization_id": authorization_id,
        "source_sha": source_sha,
        "implementation_binding": implementation_binding,
        "generator_sha256": generator_sha,
        "private_descriptor_sha256": sha256_bytes(private_bytes),
        "public_descriptor_sha256": public_sha,
        "unlock_digest_sha256": unlock_digest,
        "authorization_consumed": True,
        "private_paths_included": False,
        "secret_values_included": False,
        "board_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-toolchain", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-record", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--implementation-binding")
    parser.add_argument("--repository-root", type=Path)
    args = parser.parse_args()
    generator = Path(__file__).resolve(strict=True)
    home = Path.home().resolve(strict=True)
    try:
        if args.probe_toolchain and not args.execute:
            print(json.dumps(probe_summary(generator, home), sort_keys=True))
            return 0
        require(args.execute, "generation requires explicit --execute")
        require(not args.probe_toolchain, "probe and execute modes are mutually exclusive")
        require(args.authorization_record is not None, "authorization record required")
        require(args.source_sha is not None, "source sha required")
        require(args.implementation_binding is not None, "implementation binding required")
        result = execute(
            args.authorization_record.resolve(strict=True),
            args.source_sha,
            args.implementation_binding,
            args.repository_root,
            generator,
            home,
        )
    except Exception as exc:
        print("STAGE2D9R_PRIVATE_COMMAND_MATERIAL_GENERATION=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        print("SECRET_VALUES_INCLUDED=false")
        print("BOARD_OPERATION=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        return 2
    print("STAGE2D9R_PRIVATE_COMMAND_MATERIAL_GENERATION=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
