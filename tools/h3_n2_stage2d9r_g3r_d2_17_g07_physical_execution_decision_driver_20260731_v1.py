#!/usr/bin/env python3
"""One-shot D2-17 G07 physical execution driver."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any
import zipfile

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PHYSICAL-EXECUTION-20260731-01"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17"
PACKAGE_NAME = "D2_17_PRIVATE_PACKAGE_20260731T001500CST_G07_HEAD662406F9"
PRIVATE_SOURCE_SHA = "662406f97a023c4edc71d6bc17841828d0cc7c36"
ACCEPTANCE_SOURCE_SHA = "fa85d0f335f47d60e2b2b1c6d43946246b246fe3"
ACCEPTANCE_ARTIFACT_ID = 8767063701
ACCEPTANCE_ARTIFACT_SHA256 = "fb16558862c3110fc778d9bf8a24af7ff3c763ad1d923884ccdc4212a3571a6d"
ACCEPTANCE_BINDING_SHA256 = "0f2e281c6ed0669ebc6629aefdaeab7e5382b84d17372b75cf2ab434eaac643e"
DECISION_REQUIRED_BINDING_SHA256 = "597edc89d0cda2dfa4effb0345560d974953b209dc4084728bea4e704f3f6691"
PRIVATE_DELIVERY_BINDING_SHA256 = "b1b213b82f8e7b3b954fc2c37eeb0e1d0da22d1c4c54731f9014555f32c329d7"
ROOT_MANIFEST_SHA256 = "351b3046db1b181982f54d1922ab798801927bebe39827053bbb0b7a5682f265"
AUTHORIZATION_FILE_SHA256 = "890f74a130572cabe5f93b85b8d272b6f9985abb7dd72f4655273a030a032351"
AUTHORIZATION_RECORD_SHA256 = "37fa9803c4ce96083f2b58d4b973c8373326c179d609645f35af1ec72076a601"
EXECUTION_IDENTITY_SHA256 = "9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c"
STATIC_CHECK_FILE_SHA256 = "a42a75efe3436c7d9928c7efac67cc21edee93fa2a7bdd90f714f810e79f6aec"
IDEMPOTENCY_FILE_SHA256 = "8a1b8588c0648f26063139a5eb3bcbeb5275aaca8e70d2cdee5b29bcf92a9f7b"
SENTINEL_FILE_SHA256 = "8991644cf66d81311ffe70f4dbe702047ae7f3ce64c7ebfe5c164dfc6f894050"
TERMINAL_RECORD_SHA256 = "7916d2ac33f9010a215b4f5f8698eb7b4d2c9a833b27aa8697cc2ddf83f2d029"
AUTHORIZATION_EXPIRES_AT = "2026-07-30T18:19:45.410516Z"
BOARD_IDENTITY_SHA256 = "2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8"
SERIAL_IDENTITY_SHA256 = "b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3"
BASELINE_STATE_SHA256 = "776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f"
OUTER_NAME = "run_d2_17_canonical_delivery_outer_20260730_v1.sh"
INNER_NAME = "run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh"
OUTER_SHA256 = "2083652dfeedb93c71ac589300b155c1102fd6354dbeb31ecd588669a97b7994"
INNER_SHA256 = "2dfe1e1118e37c9abc539a800c06e45901dd40966697d4e00b9d542f37db531e"
EXECUTION_REL = Path("public-review/d2-17-execution-identity-frozen-physical-d2-execution-package")
REQUEST_REL = Path("public-review/PHYSICAL_D2_REQUEST_17.json")
AUTH_MARKER_NAME = hashlib.sha256(D2_REQUEST_ID.encode()).hexdigest() + ".json"
TARGETS = {
    "python": ("/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11", "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a"),
    "openssl": ("/usr/local/Cellar/openssl@3/3.5.0/bin/openssl", "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973"),
    "esptool": ("~/Library/Python/3.11/bin/esptool", "ab727aa71b9bbf794aab424eca706cb4b340be491ab28ba8fe17ef6d7962c267"),
    "mosquitto": ("/opt/local/sbin/mosquitto", "4d53cf9654852472c9839e178848987603e16abd41622d197440945307227763"),
}

class DecisionError(RuntimeError):
    pass

def require(ok: bool, code: str) -> None:
    if not ok:
        raise DecisionError(code)

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def file_mode(path: Path) -> str:
    return format(stat.S_IMODE(path.stat().st_mode), "04o")

def load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DecisionError(code) from exc
    require(isinstance(value, dict), code)
    return value

def exclusive_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as f:
            json.dump(value, f, sort_keys=True, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    finally:
        os.close(fd)

def replace_json(path: Path, value: object) -> None:
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    exclusive_json(tmp, value)
    os.replace(tmp, path)

def verify_sums(root: Path, expected_manifest: str | None, prefix: str) -> None:
    root = root.resolve(strict=True)
    require(root.is_dir() and not root.is_symlink(), prefix + "_ROOT_INVALID")
    sums = root / "SHA256SUMS"
    require(sums.is_file() and not sums.is_symlink(), prefix + "_SHA256SUMS_MISSING")
    if expected_manifest is not None:
        require(sha(sums) == expected_manifest, prefix + "_SHA256SUMS_DIGEST_DRIFT")
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        rel = Path(name)
        require(name not in expected and not rel.is_absolute() and ".." not in rel.parts, prefix + "_SHA256SUMS_INVALID")
        expected[name] = digest
    observed = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not p.is_symlink() and p != sums}
    require(set(expected) == observed, prefix + "_SHA256SUMS_COVERAGE_DRIFT")
    for name, digest in expected.items():
        require(sha(root / name) == digest, prefix + "_MEMBER_DIGEST_DRIFT:" + name)
    require(not any(p.is_symlink() for p in root.rglob("*")), prefix + "_SYMLINK_FORBIDDEN")

def validate_terminal(value: dict[str, Any]) -> None:
    require(value.get("terminal_record_sha256") == TERMINAL_RECORD_SHA256, "TERMINAL_RECORD_DIGEST_BINDING_DRIFT")
    copy = dict(value)
    copy.pop("terminal_record_sha256", None)
    require(canonical(copy) == TERMINAL_RECORD_SHA256, "TERMINAL_RECORD_SEMANTIC_DIGEST_DRIFT")
    require(value.get("terminal_record_digest_semantics") == "CANONICAL_JSON_WITH_TERMINAL_RECORD_SHA256_REMOVED", "TERMINAL_RECORD_DIGEST_SEMANTICS_DRIFT")
    require(value.get("status") == "PASS", "TERMINAL_STATUS_NOT_PASS")
    require(value.get("terminal_state") == "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED", "TERMINAL_STATE_DRIFT")
    require(value.get("authorization_created") is True and value.get("authorization_claimed") is False and value.get("authorization_consumed") is False, "TERMINAL_AUTHORIZATION_STATE_DRIFT")
    require(value.get("physical_decision_created") is False, "TERMINAL_PHYSICAL_DECISION_ALREADY_CREATED")
    require(value.get("package_generation") == "G07", "TERMINAL_PACKAGE_GENERATION_DRIFT")
    require(value.get("private_source_sha") == PRIVATE_SOURCE_SHA, "TERMINAL_PRIVATE_SOURCE_SHA_DRIFT")
    require(value.get("private_delivery_binding_sha256") == PRIVATE_DELIVERY_BINDING_SHA256, "TERMINAL_PRIVATE_DELIVERY_BINDING_DRIFT")
    require(value.get("authorization_record_sha256") == AUTHORIZATION_RECORD_SHA256, "TERMINAL_AUTHORIZATION_BINDING_DRIFT")
    require(value.get("execution_identity_sha256") == EXECUTION_IDENTITY_SHA256, "TERMINAL_IDENTITY_BINDING_DRIFT")

def validate_acceptance(path: Path) -> None:
    require(path.is_file() and not path.is_symlink() and sha(path) == ACCEPTANCE_ARTIFACT_SHA256, "ACCEPTANCE_ARTIFACT_DIGEST_DRIFT")
    try:
        with zipfile.ZipFile(path) as z:
            require(z.read("SOURCE_SHA").decode().strip() == ACCEPTANCE_SOURCE_SHA, "ACCEPTANCE_ARTIFACT_SOURCE_SHA_DRIFT")
            names = [n for n in z.namelist() if n.endswith("h3-n2-stage2d9r-g3r-d2-17-g07-target-mac-static-check-pass-20260731-v1.json")]
            require(len(names) == 1, "ACCEPTANCE_ARTIFACT_RECORD_MISSING")
            value = json.loads(z.read(names[0]).decode())
    except DecisionError:
        raise
    except Exception as exc:
        raise DecisionError("ACCEPTANCE_ARTIFACT_INVALID") from exc
    require(value.get("acceptance_binding_sha256") == ACCEPTANCE_BINDING_SHA256, "ACCEPTANCE_BINDING_DRIFT")
    require(value.get("private_source_sha") == PRIVATE_SOURCE_SHA, "ACCEPTANCE_PRIVATE_SOURCE_SHA_DRIFT")
    require(value.get("authorization_record_sha256") == AUTHORIZATION_RECORD_SHA256, "ACCEPTANCE_AUTHORIZATION_RECORD_DRIFT")
    require(value.get("terminal_record_sha256") == TERMINAL_RECORD_SHA256, "ACCEPTANCE_TERMINAL_RECORD_DRIFT")
    require(value.get("authorization_claimed") is False and value.get("authorization_consumed") is False, "ACCEPTANCE_AUTHORIZATION_STATE_DRIFT")

def resolve_targets() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for name, (raw, digest) in TARGETS.items():
        path = Path(raw).expanduser().resolve(strict=True)
        require(path.is_file() and not path.is_symlink() and os.access(path, os.X_OK), "TARGET_TOOL_INVALID:" + name)
        require(sha(path) == digest, "TARGET_TOOL_DIGEST_DRIFT:" + name)
        result[name] = path
    return result

def execution_env(root: Path, python: Path) -> dict[str, str]:
    value = dict(os.environ)
    resolved = str(root.resolve(strict=True))
    value.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "GH_D2_17_DELIVERY_PROFILE": "private-package",
        "GH_D2_17_OUTER_PACKAGE_ROOT": resolved,
        "GH_D2_17_LAUNCHER_PACKAGE_ROOT": resolved,
        "GH_D2_13_LAUNCHER_PACKAGE_ROOT": resolved,
        "GH_D2_14_LAUNCHER_PACKAGE_ROOT": resolved,
        "GH_D2_15_LAUNCHER_PACKAGE_ROOT": resolved,
        "GH_D2_16_LAUNCHER_PACKAGE_ROOT": resolved,
        "PATH": str(python.parent) + os.pathsep + value.get("PATH", ""),
    })
    return value

def two_hop(root: Path, arguments: list[str], python: Path) -> tuple[list[str], dict[str, str]]:
    root = root.resolve(strict=True)
    outer, inner = root / OUTER_NAME, root / INNER_NAME
    for path, digest, label in ((outer, OUTER_SHA256, "CANONICAL_OUTER"), (inner, INNER_SHA256, "INNER_LAUNCHER")):
        require(path.is_file() and not path.is_symlink(), label + "_NOT_REGULAR")
        require(sha(path) == digest, label + "_DIGEST_DRIFT")
        require(file_mode(path) == "0600", label + "_MODE_DRIFT")
    shell = Path("/bin/sh").resolve(strict=True)
    require(shell.is_file() and not shell.is_symlink() and os.access(shell, os.X_OK), "POSIX_SHELL_INVALID")
    return [str(shell), str(inner), *arguments], execution_env(root, python)

def validate_host(package: Path, runtime: Path, targets: dict[str, Path]) -> tuple[dict[str, Any], Path]:
    verify_sums(package, ROOT_MANIFEST_SHA256, "G07_ROOT")
    terminal = load_json(runtime / "D2_17_TARGET_MAC_STATIC_CHECK_TERMINAL.json", "TERMINAL_RECORD_INVALID")
    validate_terminal(terminal)
    fixed = (
        ("D2_17_AUTHORIZATION.json", AUTHORIZATION_FILE_SHA256, "AUTHORIZATION_FILE_DIGEST_DRIFT"),
        ("D2_17_TARGET_MAC_STATIC_CHECK.json", STATIC_CHECK_FILE_SHA256, "STATIC_CHECK_FILE_DIGEST_DRIFT"),
        ("D2_17_BIND_INSTALL_IDEMPOTENCY.json", IDEMPOTENCY_FILE_SHA256, "IDEMPOTENCY_FILE_DIGEST_DRIFT"),
        ("D2_17_HARDWARE_SENTINEL_SELF_CHECK.json", SENTINEL_FILE_SHA256, "SENTINEL_FILE_DIGEST_DRIFT"),
    )
    for name, digest, code in fixed:
        path = runtime / name
        require(path.is_file() and not path.is_symlink() and sha(path) == digest, code)
    auth_path = runtime / "D2_17_AUTHORIZATION.json"
    identity_path = runtime / "D2_17_EXECUTION_IDENTITY.json"
    auth = load_json(auth_path, "AUTHORIZATION_RECORD_INVALID")
    identity = load_json(identity_path, "EXECUTION_IDENTITY_INVALID")
    require(sha(identity_path) is not None, "EXECUTION_IDENTITY_FILE_INVALID")
    require(auth.get("authorization_record_sha256") == AUTHORIZATION_RECORD_SHA256, "AUTHORIZATION_RECORD_BINDING_DRIFT")
    require(identity.get("execution_identity_sha256") == EXECUTION_IDENTITY_SHA256, "EXECUTION_IDENTITY_BINDING_DRIFT")
    require(auth.get("board_identity_sha256") == BOARD_IDENTITY_SHA256, "BOARD_IDENTITY_BINDING_DRIFT")
    require(auth.get("serial_identity_sha256") == SERIAL_IDENTITY_SHA256, "SERIAL_IDENTITY_BINDING_DRIFT")
    require(auth.get("baseline_state_sha256") == BASELINE_STATE_SHA256, "BASELINE_STATE_BINDING_DRIFT")
    require(auth.get("authorization_claimed") is False and auth.get("authorization_consumed") is False, "AUTHORIZATION_ALREADY_USED")
    expires = datetime.fromisoformat(str(auth.get("expires_at")).replace("Z", "+00:00")).astimezone(timezone.utc)
    require(expires.isoformat().replace("+00:00", "Z") == AUTHORIZATION_EXPIRES_AT, "AUTHORIZATION_EXPIRY_DRIFT")
    require(datetime.now(timezone.utc) <= expires, "AUTHORIZATION_EXPIRED")
    execution = (package / EXECUTION_REL).resolve(strict=True)
    request_path = (package / REQUEST_REL).resolve(strict=True)
    os.environ.update(execution_env(execution, targets["python"]))
    sys.path.insert(0, str(execution))
    import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as wrapper
    import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1 as contract
    wrapper.bind_complete_chain()
    core = wrapper._bound_d2_11().core
    request = contract.load_json(request_path, "PHYSICAL_REQUEST_INVALID")
    contract.validate_physical_request(request, execution)
    contract.validate_execution_identity(identity, execution, request=request, controller_path=Path(core.__file__), python_path=targets["python"], openssl_path=targets["openssl"], esptool_path=targets["esptool"], mosquitto_path=targets["mosquitto"])
    contract.validate_authorization_contract(auth, request, identity, now=datetime.now(timezone.utc))
    core.validate_private_metadata(Path.home())
    core.validate_authorization(auth_path, package_root=execution, python_path=targets["python"], openssl_path=targets["openssl"], esptool_path=targets["esptool"], mosquitto_path=targets["mosquitto"])
    return auth, execution

def failure(code: str, flags: dict[str, bool]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g07-physical-decision-terminal/1",
        "status": "BLOCKED_BEFORE_INHERITED_CLAIM",
        "terminal_state": "PHYSICAL_DECISION_PRECLAIM_BLOCKED_UNCLAIMED_UNCONSUMED",
        "failure_code": code,
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "board_operation": flags["board"],
        "usb_enumeration": flags["usb"],
        "serial_operation": flags["serial"],
        "esptool_operation": flags["esptool"],
        "flash_operation": False,
        "physical_nvs_operation": flags["nvs"],
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "recovery_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "ready": False,
        "merge": False,
        "release": False,
        "tag": False,
        "deployment": False,
    }
    value["terminal_record_sha256"] = canonical(value)
    return value

def run(decision_root: Path) -> int:
    require(sys.platform == "darwin", "TARGET_HOST_NOT_DARWIN")
    package = (Path.home() / "Downloads/ActiveTestRuns" / PACKAGE_NAME).resolve(strict=True)
    runtime = package.parent / (PACKAGE_NAME + "_runtime")
    require(runtime.is_dir() and not runtime.is_symlink(), "G07_RUNTIME_ROOT_INVALID")
    decision_root = decision_root.resolve(strict=True)
    verify_sums(decision_root, None, "PHYSICAL_DECISION")
    validate_acceptance(decision_root / "D2_17_G07_ACCEPTANCE_ARTIFACT_8767063701.zip")
    targets = resolve_targets()
    physical = runtime / "D2_17_G07_PHYSICAL_EXECUTION_20260731_01"
    terminal_path = physical / "D2_17_G07_PHYSICAL_DECISION_TERMINAL.json"
    result_path = physical / "D2_17_G07_PHYSICAL_RESULT.json"
    decision_marker = Path.home() / ".local/state/greenhouse-stage2d9r/d2-17-g07-physical-decisions" / (DECISION_ID + ".json")
    auth_state = Path.home() / ".local/state/greenhouse-stage2d9r/d2-authorizations"
    auth_marker = auth_state / AUTH_MARKER_NAME
    require(not physical.exists(), "PHYSICAL_RUNTIME_ROOT_ALREADY_EXISTS")
    require(not decision_marker.exists(), "PHYSICAL_DECISION_ALREADY_USED")
    require(not auth_marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    physical.mkdir(parents=True, mode=0o700)
    os.chmod(physical, 0o700)
    flags = {"board": False, "usb": False, "serial": False, "esptool": False, "nvs": False}
    try:
        auth, execution = validate_host(package, runtime, targets)
        sys.path.insert(0, str(execution))
        import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as wrapper
        wrapper.bind_complete_chain()
        core = wrapper._bound_d2_11().core
        work = physical / "preclaim-baseline"
        work.mkdir(mode=0o700)
        flags.update(board=True, usb=True, serial=True)
        selected = core.select_serial(auth)
        flags.update(esptool=True, nvs=True)
        baseline = core.baseline(selected, targets["esptool"], work, auth)
        require(canonical(baseline) == BASELINE_STATE_SHA256, "PRECLAIM_BASELINE_STATE_DRIFT")
        marker: dict[str, Any] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g07-physical-decision-marker/1",
            "status": "PHYSICAL_DECISION_CLAIMED_BOARD_BASELINE_VERIFIED",
            "decision_id": DECISION_ID,
            "d2_request_id": D2_REQUEST_ID,
            "private_source_sha": PRIVATE_SOURCE_SHA,
            "acceptance_source_sha": ACCEPTANCE_SOURCE_SHA,
            "acceptance_artifact_id": ACCEPTANCE_ARTIFACT_ID,
            "acceptance_artifact_sha256": ACCEPTANCE_ARTIFACT_SHA256,
            "acceptance_binding_sha256": ACCEPTANCE_BINDING_SHA256,
            "decision_required_binding_sha256": DECISION_REQUIRED_BINDING_SHA256,
            "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
            "execution_identity_sha256": EXECUTION_IDENTITY_SHA256,
            "board_identity_sha256": BOARD_IDENTITY_SHA256,
            "serial_identity_sha256": SERIAL_IDENTITY_SHA256,
            "baseline_state_sha256": BASELINE_STATE_SHA256,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }
        marker["marker_sha256"] = canonical(marker)
        exclusive_json(decision_marker, marker)
        auth_state.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(auth_state, 0o700)
        roots: dict[str, Path] = {}
        for name in ("immutable-root", "recovery-root", "prepare-evidence", "delivery-evidence", "terminalization-evidence"):
            roots[name] = physical / name
            roots[name].mkdir(mode=0o700)
        args = [
            "execute",
            "--package-root", str(execution),
            "--physical-request", str(package / REQUEST_REL),
            "--authorization-record", str(runtime / "D2_17_AUTHORIZATION.json"),
            "--immutable-root", str(roots["immutable-root"]),
            "--recovery-root", str(roots["recovery-root"]),
            "--home", str(Path.home()),
            "--state-root", str(auth_state),
            "--result-output", str(result_path),
            "--prepare-evidence-root", str(roots["prepare-evidence"]),
            "--delivery-evidence-root", str(roots["delivery-evidence"]),
            "--terminalization-evidence-root", str(roots["terminalization-evidence"]),
            "--openssl", str(targets["openssl"]),
            "--esptool", str(targets["esptool"]),
            "--mosquitto", str(targets["mosquitto"]),
        ]
        command, env = two_hop(execution, args, targets["python"])
        stdout_path, stderr_path = physical / "physical.stdout", physical / "physical.stderr"
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            os.chmod(stdout_path, 0o600)
            os.chmod(stderr_path, 0o600)
            completed = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err, check=False)
        result = load_json(result_path, "PHYSICAL_RESULT_MISSING_OR_INVALID") if result_path.exists() else {}
        auth_value = load_json(auth_marker, "AUTHORIZATION_MARKER_MISSING_OR_INVALID") if auth_marker.exists() else {}
        consumed = auth_value.get("status") in {"CONSUMED_PASS", "CONSUMED_FAILED"}
        passed = completed.returncode == 0 and result.get("status") == "CONSUMED_PASS" and auth_value.get("status") == "CONSUMED_PASS"
        terminal: dict[str, Any] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g07-physical-decision-terminal/1",
            "status": "PASS" if passed else "FAIL",
            "terminal_state": "D2_17_G07_PHYSICAL_EXECUTION_CONSUMED_PASS" if passed else str(result.get("terminal_state") or auth_value.get("status") or "PHYSICAL_EXECUTION_FAILED"),
            "failure_code": None if passed else str(result.get("failure_code") or "PHYSICAL_EXECUTION_FAILED"),
            "decision_id": DECISION_ID,
            "d2_request_id": D2_REQUEST_ID,
            "authorization_claimed": bool(auth_marker.exists()),
            "authorization_consumed": consumed,
            "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
            "execution_identity_sha256": EXECUTION_IDENTITY_SHA256,
            "physical_result_sha256": sha(result_path) if result_path.exists() else None,
            "authorization_marker_sha256": sha(auth_marker) if auth_marker.exists() else None,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_operation": True,
            "usb_enumeration": True,
            "serial_operation": True,
            "esptool_operation": True,
            "flash_operation": bool(result.get("flash_sha256")),
            "physical_nvs_operation": True,
            "broker_started": bool(result.get("broker_log_sha256")),
            "prepare_executed": int(result.get("prepare_count", 0)) > 0,
            "verify_executed": int(result.get("verify_count", 0)) > 0,
            "recovery_executed": bool(result.get("recovery_attempted")),
            "recovery_succeeded": bool(result.get("recovery_succeeded")),
            "activate_executed": False,
            "cleanup_executed": False,
            "ready": False,
            "merge": False,
            "release": False,
            "tag": False,
            "deployment": False,
        }
        terminal["terminal_record_sha256"] = canonical(terminal)
        exclusive_json(terminal_path, terminal)
        marker.update(status="CONSUMED_PASS" if passed else "CONSUMED_FAILED", authorization_claimed=bool(auth_marker.exists()), authorization_consumed=consumed, terminal_record_sha256=terminal["terminal_record_sha256"], completed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        replace_json(decision_marker, marker)
        print(json.dumps(terminal, sort_keys=True))
        print("PHYSICAL_RUNTIME_ROOT=" + str(physical))
        print("PHYSICAL_TERMINAL_FILE=" + str(terminal_path))
        print("PHYSICAL_RESULT_FILE=" + str(result_path))
        print("AUTHORIZATION_MARKER_FILE=" + str(auth_marker))
        return 0 if passed else 2
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, DecisionError) and exc.args else type(exc).__name__
        terminal = failure(str(code), flags)
        if not terminal_path.exists():
            exclusive_json(terminal_path, terminal)
        print(json.dumps(terminal, sort_keys=True))
        print("PHYSICAL_RUNTIME_ROOT=" + str(physical))
        print("PHYSICAL_TERMINAL_FILE=" + str(terminal_path))
        print("PHYSICAL_RESULT_FILE=" + str(result_path))
        print("AUTHORIZATION_MARKER_FILE=" + str(auth_marker))
        return 2

def self_test(execution: Path) -> int:
    execution = execution.expanduser().resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="d2-17-g07-two-hop-") as td:
        root = Path(td)
        os.chmod(root, 0o700)
        paths: dict[str, Path] = {}
        for name in ("immutable", "recovery", "state", "prepare", "delivery", "terminal"):
            paths[name] = root / name
            paths[name].mkdir(mode=0o700)
        args = [
            "execute", "--package-root", str(execution), "--physical-request", str(execution.parent / "PHYSICAL_D2_REQUEST_17.json"),
            "--authorization-record", str(root / "missing.json"), "--immutable-root", str(paths["immutable"]), "--recovery-root", str(paths["recovery"]),
            "--home", str(root), "--state-root", str(paths["state"]), "--result-output", str(root / "result.json"),
            "--prepare-evidence-root", str(paths["prepare"]), "--delivery-evidence-root", str(paths["delivery"]), "--terminalization-evidence-root", str(paths["terminal"]),
            "--openssl", "/bin/true", "--esptool", "/bin/true", "--mosquitto", "/bin/true",
        ]
        command, env = two_hop(execution, args, Path(sys.executable).resolve(strict=True))
        completed = subprocess.run(command, env=env, text=True, capture_output=True, check=False)
        require(completed.returncode == 2, "SELF_TEST_EXPECTED_PRECLAIM_FAILURE")
        combined = completed.stdout + completed.stderr
        require("LAUNCHER_PACKAGE_ROOT_MISMATCH" not in combined and "the following arguments are required" not in combined, "SELF_TEST_HANDOFF_FAILED")
        result = load_json(root / "result.json", "SELF_TEST_RESULT_MISSING")
        require(result.get("authorization_claimed") is False and result.get("authorization_consumed") is False, "SELF_TEST_AUTHORIZATION_BOUNDARY_VIOLATED")
        require(result.get("board_operation") is False and result.get("usb_enumeration") is False, "SELF_TEST_PHYSICAL_BOUNDARY_VIOLATED")
        value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g07-physical-decision-driver-self-test/1",
            "status": "PASS",
            "permission_independent_two_hop_handoff": True,
            "outer_mode_preserved": file_mode(execution / OUTER_NAME) == "0600",
            "inner_mode_preserved": file_mode(execution / INNER_NAME) == "0600",
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
        }
        print(json.dumps(value, sort_keys=True))
        return 0

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test-execution-root", type=Path)
    parser.add_argument("--decision-root", type=Path)
    args = parser.parse_args()
    if args.self_test_execution_root is not None:
        return self_test(args.self_test_execution_root)
    require(args.decision_root is not None, "PHYSICAL_DECISION_ROOT_REQUIRED")
    return run(args.decision_root)

if __name__ == "__main__":
    raise SystemExit(main())
