#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
ID18_IMPL_PATH = PACKAGE_DIR.parent / "id18_board_a_inactive_app0_schema5_deployment" / "executor_impl.py"
ID18_IMPL_GIT_BLOB = "27744d2b54ec0d5318496d9ca99b647465daa769"
DIAG_PARSER_GIT_BLOB = "af78ed4cb14c38579f56e6ba3019e2debdb21d9e"
ID20R1_EXECUTION_PACKAGE_COMMIT = "88c7d29a1c6f9fc2b17e371b0c6dd95f8867ab61"
SCHEMA5_SOURCE_COMMIT = "5d58727f5040281ee2beb9597f66a6a2da9bac57"
SCHEMA5_FIRMWARE_SHA256 = "5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b"
SCHEMA5_FIRMWARE_SIZE = 1_115_648
EXPECTED_BOARD_A_SUFFIX = "f3:50"
EXPECTED_BOARD_B_SUFFIX = "f4:5c"
EXPECTED_BOARD_A_SELECTED_SLOT = 0
EXPECTED_BOARD_A_ACTIVE_SEQ = 5
EXPECTED_ACTIVE_STATE = 2
EXPECTED_SCHEMA_VERSION = 5
NVS_OFFSET = 0x790000
NVS_SIZE = 0x70000
ALLOWED_DIRECT_CHANNELS = {1, 6, 11}
MIN_DIRECT_BASELINE_SECONDS = 60
MIN_RELAY_STAGING_SECONDS = 45
MIN_RELAY_WINDOW_SECONDS = 150

TOKEN_PRECLAIM_ROM = "BOTH_BOARDS_PRECLAIM_ROM_READY"
TOKEN_DIRECT_BASELINE = "DIRECT_BASELINE_CAPTURE_READY"
TOKEN_RELAY_STAGING = "RELAY_STAGING_DIRECT_COMPLETE"
TOKEN_RELAY_COMPLETE = "RELAY_WINDOW_COMPLETE_AND_BOTH_ROM_READY"

COMPACT_FIELDS = (
    "compact_rx_count",
    "compact_state_reject_count",
    "compact_child_binding_failure",
    "compact_decode_success",
    "compact_decode_failure",
    "compact_wrap_failure",
    "compact_forward_attempts",
    "compact_forward_submit_success",
    "compact_forward_submit_failure",
)


def _load_id18():
    spec = importlib.util.spec_from_file_location("id21_id18_common", ID18_IMPL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("ID18 implementation could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


id18 = _load_id18()
StopExecution = id18.StopExecution


def load_manifest() -> dict[str, Any]:
    value = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    if value.get("package_schema_version") != 1:
        raise StopExecution("manifest package schema version mismatch")
    if value.get("gate_id") != "id21_schema5_two_board_relay_validation":
        raise StopExecution("manifest gate id mismatch")
    return value


def write_authorization(root: Path, auth: str, execution_id: str, *, claimed: bool) -> None:
    value: dict[str, Any] = {
        "authorization_id": auth,
        "execution_id": execution_id,
        "claimed": claimed,
        "consumed": claimed,
        "replay_permitted": False,
    }
    if claimed:
        now = id18.utc_now()
        value.update(
            {
                "claim_boundary": "immediately_before_two_board_preclaim_operator_interlock",
                "claimed_at": now,
                "consumed_at": now,
            }
        )
    id18.write_json(root / "authorization.json", value)


def run_recorded(
    *,
    root: Path,
    index: int,
    label: str,
    argv: list[str],
    cwd: Path,
    target_operation: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return id18.run_recorded(
        root=root,
        index=index,
        label=label,
        argv=argv,
        cwd=cwd,
        target_operation=target_operation,
        extra_env=extra_env,
    )


def verify_host(root: Path, repo_root: Path, expected_commit: str) -> int:
    index = 1
    parser_path = repo_root / "tools" / "n3w_read_diag_snapshot.py"
    checks = (
        ("host_git_head", ["git", "rev-parse", "HEAD"], expected_commit),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"], ""),
        (
            "id18_impl_blob",
            ["git", "hash-object", str(ID18_IMPL_PATH.relative_to(repo_root))],
            ID18_IMPL_GIT_BLOB,
        ),
        (
            "diag_parser_blob",
            ["git", "hash-object", str(parser_path.relative_to(repo_root))],
            DIAG_PARSER_GIT_BLOB,
        ),
    )
    for label, argv, expected in checks:
        result = run_recorded(root=root, index=index, label=label, argv=argv, cwd=repo_root)
        if result.returncode != 0 or (result.stdout or "").strip() != expected:
            raise StopExecution(f"{label} binding failed")
        index += 1

    result = run_recorded(
        root=root,
        index=index,
        label="host_esptool_version",
        argv=[sys.executable, "-m", "esptool", "version"],
        cwd=repo_root,
    )
    versions = id18.VERSION_RE.findall((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0 or id18.EXPECTED_ESPTOOL_VERSION not in versions:
        raise StopExecution("esptool version preflight failed")
    return index + 1


def operator_interlock(
    root: Path,
    *,
    name: str,
    token: str,
    minimum_seconds: int,
    instructions: str,
) -> float:
    print(f"\nID21 OPERATOR INTERLOCK: {name}\n{instructions}", file=sys.stderr, flush=True)
    started = time.monotonic()
    started_utc = id18.utc_now()
    observed = input(f"ID21 token [{token}]: ").strip()
    elapsed = time.monotonic() - started
    matched = observed == token
    id18.write_json(
        root / f"operator_interlock_{name.lower()}.json",
        {
            "name": name,
            "required_token": token,
            "token_match": matched,
            "minimum_elapsed_seconds": minimum_seconds,
            "observed_elapsed_seconds": elapsed,
            "started_at": started_utc,
            "confirmed_at": id18.utc_now(),
        },
    )
    if not matched:
        raise StopExecution(f"operator interlock token mismatch: {name}")
    if elapsed < minimum_seconds:
        raise StopExecution(f"operator interlock elapsed time below minimum: {name}")
    return elapsed


def _private_identity_record(base_mac: str) -> dict[str, Any]:
    return {
        "base_mac": base_mac,
        "base_mac_sha256": hashlib.sha256(base_mac.encode()).hexdigest(),
        "suffix": id18.mac_suffix(base_mac),
    }


def discover_and_bind_boards(
    *,
    root: Path,
    repo_root: Path,
    op_index: int,
    phase: str,
    env: dict[str, str],
) -> tuple[int, dict[str, dict[str, str]]]:
    candidates = sorted(set(glob.glob("/dev/cu.usbmodem*")))
    id18.write_json(
        root / f"{phase}_port_locators_private.json",
        {
            "candidates": candidates,
            "candidate_count": len(candidates),
            "checked_at": id18.utc_now(),
        },
    )
    if len(candidates) != 2:
        raise StopExecution(f"{phase}: expected exactly two /dev/cu.usbmodem* locators")
    for raw in candidates:
        info = Path(raw).stat()
        if not stat.S_ISCHR(info.st_mode):
            raise StopExecution(f"{phase}: locator is not a character device")

    roles: dict[str, dict[str, str]] = {}
    for ordinal, port in enumerate(candidates, start=1):
        result = run_recorded(
            root=root,
            index=op_index,
            label=f"{phase}_read_mac_{ordinal}",
            argv=id18.build_read_mac_command(port),
            cwd=repo_root,
            target_operation=True,
            extra_env=env,
        )
        op_index += 1
        if result.returncode != 0:
            raise StopExecution(f"{phase}: read-mac failed")
        base_mac = id18.parse_base_mac(result.stdout or "")
        suffix = id18.mac_suffix(base_mac)
        if suffix == EXPECTED_BOARD_A_SUFFIX:
            role = "board_a"
        elif suffix == EXPECTED_BOARD_B_SUFFIX:
            role = "board_b"
        else:
            raise StopExecution(f"{phase}: unexpected board identity suffix")
        if role in roles:
            raise StopExecution(f"{phase}: duplicate board role")
        roles[role] = {"port": port, "base_mac": base_mac}

    if set(roles) != {"board_a", "board_b"}:
        raise StopExecution(f"{phase}: A/B identity binding incomplete")
    id18.write_json(
        root / f"{phase}_identity_private.json",
        {
            role: _private_identity_record(value["base_mac"])
            for role, value in sorted(roles.items())
        },
    )
    return op_index, roles


def decode_snapshot(
    *,
    root: Path,
    repo_root: Path,
    op_index: int,
    label: str,
    nvs_path: Path,
) -> tuple[int, dict[str, Any]]:
    parser = repo_root / "tools" / "n3w_read_diag_snapshot.py"
    result = run_recorded(
        root=root,
        index=op_index,
        label=label,
        argv=[sys.executable, str(parser), "--nvs-image", str(nvs_path)],
        cwd=repo_root,
    )
    op_index += 1
    if result.returncode != 0:
        raise StopExecution(f"{label}: diagnostic decode failed")
    try:
        value = json.loads((result.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise StopExecution(f"{label}: diagnostic output is not JSON") from exc
    if not isinstance(value, dict):
        raise StopExecution(f"{label}: diagnostic output is not an object")
    return op_index, value


def _read_flash(
    *,
    root: Path,
    repo_root: Path,
    op_index: int,
    label: str,
    port: str,
    offset: int,
    size: int,
    output: Path,
    env: dict[str, str],
) -> int:
    result = run_recorded(
        root=root,
        index=op_index,
        label=label,
        argv=id18.build_read_flash_command(port, offset, size, output),
        cwd=repo_root,
        target_operation=True,
        extra_env=env,
    )
    if result.returncode != 0:
        raise StopExecution(f"{label}: read failed")
    if not output.is_file() or output.stat().st_size != size:
        raise StopExecution(f"{label}: output size/path mismatch")
    os.chmod(output, 0o600)
    return op_index + 1


def capture_prestate(
    *,
    root: Path,
    repo_root: Path,
    op_index: int,
    role: str,
    binding: dict[str, str],
    env: dict[str, str],
) -> tuple[int, dict[str, Any]]:
    phase_dir = root / "prestate" / role
    id18.ensure_private_dir(phase_dir)
    captures = (
        ("partition_table", id18.PARTITION_TABLE_OFFSET, id18.PARTITION_TABLE_SIZE),
        ("otadata", id18.OTADATA_OFFSET, id18.OTADATA_SIZE),
        ("app0_window", id18.APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        ("app1_window", id18.APP1_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        ("nvs", NVS_OFFSET, NVS_SIZE),
    )
    paths: dict[str, Path] = {}
    for name, offset, size in captures:
        out = phase_dir / f"{name}.bin"
        paths[name] = out
        op_index = _read_flash(
            root=root,
            repo_root=repo_root,
            op_index=op_index,
            label=f"pre_{role}_{name}",
            port=binding["port"],
            offset=offset,
            size=size,
            output=out,
            env=env,
        )

    id18.parse_partition_table(paths["partition_table"].read_bytes())
    ota = id18.parse_otadata(paths["otadata"].read_bytes())
    app0_sha = id18.sha256_file(paths["app0_window"])
    app1_sha = id18.sha256_file(paths["app1_window"])
    op_index, snapshot = decode_snapshot(
        root=root,
        repo_root=repo_root,
        op_index=op_index,
        label=f"pre_{role}_decode_snapshot",
        nvs_path=paths["nvs"],
    )
    summary = {
        "selected_slot": ota.selected_slot,
        "active_seq": ota.active_seq,
        "active_state": ota.active_state,
        "app0_sha256": app0_sha,
        "app1_sha256": app1_sha,
        "selected_image_sha256": app0_sha if ota.selected_slot == 0 else app1_sha,
        "snapshot": snapshot,
    }
    id18.write_json(phase_dir / "summary_private.json", summary)
    return op_index, summary


def capture_nvs_phase(
    *,
    root: Path,
    repo_root: Path,
    op_index: int,
    phase: str,
    role: str,
    binding: dict[str, str],
    env: dict[str, str],
) -> tuple[int, dict[str, Any]]:
    phase_dir = root / phase / role
    id18.ensure_private_dir(phase_dir)
    out = phase_dir / "nvs.bin"
    op_index = _read_flash(
        root=root,
        repo_root=repo_root,
        op_index=op_index,
        label=f"{phase}_{role}_nvs",
        port=binding["port"],
        offset=NVS_OFFSET,
        size=NVS_SIZE,
        output=out,
        env=env,
    )
    op_index, snapshot = decode_snapshot(
        root=root,
        repo_root=repo_root,
        op_index=op_index,
        label=f"{phase}_{role}_decode_snapshot",
        nvs_path=out,
    )
    id18.write_json(phase_dir / "snapshot_private.json", snapshot)
    return op_index, snapshot


def _int(snapshot: dict[str, Any], field: str) -> int:
    value = snapshot.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StopExecution(f"diagnostic field is not an integer: {field}")
    return value


def _schema5(snapshot: dict[str, Any]) -> None:
    if _int(snapshot, "schema_version") != EXPECTED_SCHEMA_VERSION:
        raise StopExecution("diagnostic schema is not v5")
    if _int(snapshot, "boot_session") == 0:
        raise StopExecution("diagnostic boot_session is zero")
    if _int(snapshot, "snapshot_uptime_ms") < 5000:
        raise StopExecution("diagnostic snapshot uptime is below minimum")


def _compact_values(snapshot: dict[str, Any]) -> dict[str, int]:
    return {field: _int(snapshot, field) for field in COMPACT_FIELDS}


def _direct_runtime(snapshot: dict[str, Any]) -> None:
    _schema5(snapshot)
    if _int(snapshot, "path_state") != 0:
        raise StopExecution("runtime is not Direct")
    channel = _int(snapshot, "current_channel")
    hint = _int(snapshot, "direct_channel_hint")
    if channel not in ALLOWED_DIRECT_CHANNELS or hint != channel:
        raise StopExecution("Direct channel/hint contract failed")


def adjudicate_prestate(role: str, summary: dict[str, Any]) -> dict[str, Any]:
    snapshot = summary["snapshot"]
    _schema5(snapshot)
    if summary["active_state"] != EXPECTED_ACTIVE_STATE:
        raise StopExecution(f"{role}: active OTA state is not VALID")
    if summary["selected_image_sha256"] != SCHEMA5_FIRMWARE_SHA256:
        raise StopExecution(f"{role}: selected application is not exact Schema-v5")
    if role == "board_a":
        if summary["selected_slot"] != EXPECTED_BOARD_A_SELECTED_SLOT:
            raise StopExecution("board_a: selected slot drifted from ID20R1")
        if summary["active_seq"] != EXPECTED_BOARD_A_ACTIVE_SEQ:
            raise StopExecution("board_a: active sequence drifted from ID20R1")
        compact = _compact_values(snapshot)
        if any(compact.values()):
            raise StopExecution("board_a: prestate compact baseline is not zero")
    return {
        "selected_slot": summary["selected_slot"],
        "active_seq": summary["active_seq"],
        "active_state": summary["active_state"],
        "selected_image_exact_schema5": True,
        "schema_version": _int(snapshot, "schema_version"),
        "boot_session": _int(snapshot, "boot_session"),
    }


def adjudicate_direct_baseline(
    *,
    role: str,
    snapshot: dict[str, Any],
    pre_boot_session: int,
) -> dict[str, Any]:
    _direct_runtime(snapshot)
    boot_session = _int(snapshot, "boot_session")
    if boot_session == pre_boot_session:
        raise StopExecution(f"{role}: Direct baseline boot session did not change")
    if _int(snapshot, "relay_active_count") != 0:
        raise StopExecution(f"{role}: Direct baseline has RelayActive evidence")
    if _int(snapshot, "relay_telemetry_attempts") != 0:
        raise StopExecution(f"{role}: Direct baseline has relay telemetry attempts")
    if _int(snapshot, "relay_advertisement_attempts") < 1:
        raise StopExecution(f"{role}: Direct baseline has no relay advertisement attempt")
    compact = _compact_values(snapshot)
    if role == "board_a" and any(compact.values()):
        raise StopExecution("board_a: Direct baseline compact counters are contaminated")
    return {
        "schema_version": 5,
        "boot_session_changed": True,
        "snapshot_uptime_ms": _int(snapshot, "snapshot_uptime_ms"),
        "path_state": 0,
        "current_channel": _int(snapshot, "current_channel"),
        "direct_channel_hint": _int(snapshot, "direct_channel_hint"),
        "relay_advertisement_attempts": _int(snapshot, "relay_advertisement_attempts"),
        "relay_active_count": 0,
        "relay_telemetry_attempts": 0,
        "compact_counters": compact,
    }


def relay_first_unproven_stage(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    if _int(b, "path_state") != 2 or _int(b, "relay_active_count") < 1:
        return "B_RELAY_ACTIVE"
    if _int(b, "accept_verify") < 1 or _int(b, "peer_install_success") < 1:
        return "B_AUTHENTICATED_RELAY_ACQUISITION"
    if _int(b, "relay_telemetry_attempts") < 1 or _int(b, "relay_telemetry_success") < 1:
        return "B_RELAY_TELEMETRY_SUBMISSION"
    if _int(b, "unicast_completion_success") < 1:
        return "B_UNICAST_TX_COMPLETION"
    if _int(a, "compact_rx_count") < 1:
        return "A_COMPACT_RX"
    if _int(a, "compact_decode_success") < 1:
        if _int(a, "compact_state_reject_count") > 0:
            return "A_COMPACT_STATE_GATE"
        if _int(a, "compact_child_binding_failure") > 0:
            return "A_COMPACT_CHILD_BINDING"
        return "A_COMPACT_DECODE"
    if _int(a, "compact_forward_attempts") < 1:
        if _int(a, "compact_wrap_failure") > 0:
            return "A_COMPACT_WRAP"
        return "A_COMPACT_FORWARD_ATTEMPT"
    if _int(a, "compact_forward_submit_success") < 1:
        return "A_COMPACT_FORWARD_SUBMIT"
    return None


def adjudicate_relay_phase(
    *,
    a: dict[str, Any],
    b: dict[str, Any],
    baseline_a_boot_session: int,
    baseline_b_boot_session: int,
) -> dict[str, Any]:
    _schema5(a)
    _schema5(b)
    if _int(a, "boot_session") == baseline_a_boot_session:
        raise StopExecution("board_a: Relay phase boot session did not change")
    if _int(b, "boot_session") == baseline_b_boot_session:
        raise StopExecution("board_b: Relay phase boot session did not change")
    _direct_runtime(a)
    stage = relay_first_unproven_stage(a, b)
    compact = _compact_values(a)
    return {
        "first_unproven_stage": stage,
        "board_side_relay_chain_proven": stage is None,
        "board_a": {
            "schema_version": 5,
            "boot_session_changed_from_baseline": True,
            "path_state": _int(a, "path_state"),
            "current_channel": _int(a, "current_channel"),
            "direct_channel_hint": _int(a, "direct_channel_hint"),
            "compact_counters": compact,
        },
        "board_b": {
            "schema_version": 5,
            "boot_session_changed_from_baseline": True,
            "path_state": _int(b, "path_state"),
            "relay_active_count": _int(b, "relay_active_count"),
            "accept_verify": _int(b, "accept_verify"),
            "peer_install_success": _int(b, "peer_install_success"),
            "relay_telemetry_attempts": _int(b, "relay_telemetry_attempts"),
            "relay_telemetry_success": _int(b, "relay_telemetry_success"),
            "unicast_completion_count": _int(b, "unicast_completion_count"),
            "unicast_completion_success": _int(b, "unicast_completion_success"),
            "unicast_completion_failure": _int(b, "unicast_completion_failure"),
        },
    }


def _public_prestate(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_slot": summary["selected_slot"],
        "active_seq": summary["active_seq"],
        "active_state": summary["active_state"],
        "selected_image_exact_schema5": True,
        "schema_version": summary["schema_version"],
    }


def evidence_manifest(root: Path) -> list[dict[str, Any]]:
    return id18.evidence_manifest(root)


def write_closure(
    root: Path,
    *,
    execution_id: str,
    package_commit: str,
    authorization_id: str,
    result: str,
    failed: str | None,
    stop_reason: str | None,
    target_access: bool | str,
    interlocks: dict[str, float],
    prestate: dict[str, Any] | None,
    direct_baseline: dict[str, Any] | None,
    relay_phase: dict[str, Any] | None,
    next_route: str,
) -> None:
    auth = json.loads((root / "authorization.json").read_text(encoding="utf-8"))
    id18.write_json(
        root / "closure.json",
        {
            "execution_id": execution_id,
            "execution_package_commit": package_commit,
            "authorization": authorization_id,
            "authorization_claimed": bool(auth.get("claimed")),
            "authorization_consumed": bool(auth.get("consumed")),
            "replay_permitted": False,
            "relay_validation_result": result,
            "first_failed_operation": failed,
            "stop_reason": stop_reason,
            "target_access_occurred": target_access,
            "operator_interlock_elapsed_seconds": interlocks,
            "board_a_physical_access": bool(auth.get("claimed")),
            "board_b_physical_access": bool(auth.get("claimed")),
            "controlled_rf_experiment": True,
            "t1_access": False,
            "serial_open": False,
            "flash_write": False,
            "flash_erase": False,
            "nvs_write": False,
            "otadata_write": False,
            "pairing_change": False,
            "automatic_retry": False,
            "automatic_rollback": False,
            "normal_boots_per_board_authorized": 2,
            "prestate": prestate,
            "direct_baseline": direct_baseline,
            "relay_phase": relay_phase,
            "kf089_end_to_end_relay_telemetry": "NOT_YET_PROVEN",
            "next_route": next_route,
        },
    )
    id18.write_json(
        root / "evidence_manifest.json",
        {
            "schema_version": 1,
            "execution_id": execution_id,
            "authorization": authorization_id,
            "files": evidence_manifest(root),
        },
    )


def self_check() -> None:
    manifest = load_manifest()
    if manifest["predecessor"]["execution_package_commit"] != ID20R1_EXECUTION_PACKAGE_COMMIT:
        raise StopExecution("ID20R1 predecessor binding mismatch")
    refs = manifest["authority_references"]
    if refs["schema5_source_commit"] != SCHEMA5_SOURCE_COMMIT:
        raise StopExecution("Schema-v5 source authority mismatch")
    if refs["schema5_firmware_sha256"] != SCHEMA5_FIRMWARE_SHA256:
        raise StopExecution("Schema-v5 firmware authority mismatch")
    if refs["id18_executor_impl_git_blob"] != ID18_IMPL_GIT_BLOB:
        raise StopExecution("ID18 helper blob authority mismatch")
    if refs["diag_parser_git_blob"] != DIAG_PARSER_GIT_BLOB:
        raise StopExecution("diagnostic parser blob authority mismatch")
    contract = manifest["operator_contract"]
    if contract["direct_baseline_min_seconds"] != MIN_DIRECT_BASELINE_SECONDS:
        raise StopExecution("Direct baseline timing contract mismatch")
    if contract["relay_staging_min_seconds"] != MIN_RELAY_STAGING_SECONDS:
        raise StopExecution("Relay staging timing contract mismatch")
    if contract["relay_window_min_seconds"] != MIN_RELAY_WINDOW_SECONDS:
        raise StopExecution("Relay window timing contract mismatch")
    id18.assert_read_only_argv(id18.build_read_mac_command("/dev/example"))
    for offset, size in (
        (id18.PARTITION_TABLE_OFFSET, id18.PARTITION_TABLE_SIZE),
        (id18.OTADATA_OFFSET, id18.OTADATA_SIZE),
        (id18.APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        (id18.APP1_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        (NVS_OFFSET, NVS_SIZE),
    ):
        id18.assert_read_only_argv(
            id18.build_read_flash_command("/dev/example", offset, size, Path("/tmp/out.bin"))
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    if args.self_check:
        if any(
            value is not None
            for value in (
                args.expected_package_commit,
                args.authorization_id,
                args.execution_id,
                args.evidence_root,
            )
        ):
            parser.error("--self-check cannot be combined with execution arguments")
        self_check()
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0

    required = (
        args.expected_package_commit,
        args.authorization_id,
        args.execution_id,
        args.evidence_root,
    )
    if any(value is None or value == "" for value in required):
        parser.error("all execution arguments are required")
    if sys.version_info[:2] != (3, 11):
        raise StopExecution("Python 3.11 is required")

    repo_root = id18.find_repo_root(PACKAGE_DIR)
    root = args.evidence_root.expanduser().resolve()
    if id18.is_within(root, repo_root):
        raise StopExecution("private evidence root must be outside repository")
    if root.exists() and any(root.iterdir()):
        raise StopExecution("evidence root must be absent or empty")
    id18.ensure_private_dir(root)
    cfg = id18.make_esptool_cfg(root)
    env = {
        "ESPTOOL_CFGFILE": str(cfg),
        "ESPTOOL_OPEN_PORT_ATTEMPTS": "1",
    }
    write_authorization(root, args.authorization_id, args.execution_id, claimed=False)

    op_index = 1
    target_access: bool | str = False
    failed = "HOST_PREFLIGHT"
    interlocks: dict[str, float] = {}
    public_prestate: dict[str, Any] | None = None
    direct_public: dict[str, Any] | None = None
    relay_public: dict[str, Any] | None = None
    next_route = "STOP_RETURN_TO_HIGH_LEVEL_MODEL"

    try:
        op_index = verify_host(root, repo_root, args.expected_package_commit)
        write_authorization(root, args.authorization_id, args.execution_id, claimed=True)

        failed = "OPERATOR_PRECLAIM_ROM_PREPARATION"
        interlocks["preclaim_rom"] = operator_interlock(
            root,
            name="PRECLAIM_ROM",
            token=TOKEN_PRECLAIM_ROM,
            minimum_seconds=0,
            instructions=(
                "1) Fully power off Board A and Board B.\n"
                "2) For each board, hold BOOT/GPIO9 low, apply USB power, wait for enumeration, then release BOOT.\n"
                "3) Leave only these two boards as /dev/cu.usbmodem* devices.\n"
                "4) Do not open serial, reset, reconnect, or run RF.\n"
                f"5) Type exactly {TOKEN_PRECLAIM_ROM}.\n"
            ),
        )

        failed = "PRECLAIM_IDENTITY_BINDING"
        target_access = "UNKNOWN"
        op_index, bindings = discover_and_bind_boards(
            root=root,
            repo_root=repo_root,
            op_index=op_index,
            phase="preclaim",
            env=env,
        )
        target_access = True

        pre_private: dict[str, Any] = {}
        pre_public: dict[str, Any] = {}
        for role in ("board_a", "board_b"):
            failed = f"PRECLAIM_{role.upper()}_CAPTURE"
            op_index, pre_private[role] = capture_prestate(
                root=root,
                repo_root=repo_root,
                op_index=op_index,
                role=role,
                binding=bindings[role],
                env=env,
            )
            adjudicated = adjudicate_prestate(role, pre_private[role])
            pre_public[role] = _public_prestate(adjudicated)
        public_prestate = pre_public

        failed = "OPERATOR_DIRECT_BASELINE"
        interlocks["direct_baseline"] = operator_interlock(
            root,
            name="DIRECT_BASELINE",
            token=TOKEN_DIRECT_BASELINE,
            minimum_seconds=MIN_DIRECT_BASELINE_SECONDS,
            instructions=(
                "1) Fully power both boards off from the preclaim ROM state.\n"
                "2) Normal-boot Board A and Board B exactly once with BOOT/GPIO9 released.\n"
                "3) Keep both boards in normal AP coverage and do not create selective RF isolation.\n"
                f"4) Leave both applications running for at least {MIN_DIRECT_BASELINE_SECONDS} seconds.\n"
                "5) Fully power both boards off.\n"
                "6) Re-enter fresh ROM Download on both boards using BOOT/GPIO9 low during USB power-on.\n"
                "7) Leave only these two ROM-mode boards enumerated.\n"
                f"8) Type exactly {TOKEN_DIRECT_BASELINE}.\n"
            ),
        )

        failed = "DIRECT_BASELINE_IDENTITY_BINDING"
        op_index, baseline_bindings = discover_and_bind_boards(
            root=root,
            repo_root=repo_root,
            op_index=op_index,
            phase="direct_baseline",
            env=env,
        )
        baseline_private: dict[str, dict[str, Any]] = {}
        baseline_public: dict[str, Any] = {}
        for role in ("board_a", "board_b"):
            failed = f"DIRECT_BASELINE_{role.upper()}_NVS"
            op_index, snapshot = capture_nvs_phase(
                root=root,
                repo_root=repo_root,
                op_index=op_index,
                phase="direct_baseline",
                role=role,
                binding=baseline_bindings[role],
                env=env,
            )
            baseline_private[role] = snapshot
            baseline_public[role] = adjudicate_direct_baseline(
                role=role,
                snapshot=snapshot,
                pre_boot_session=pre_private[role]["snapshot"]["boot_session"],
            )
        direct_public = baseline_public

        failed = "OPERATOR_RELAY_STAGING"
        interlocks["relay_staging"] = operator_interlock(
            root,
            name="RELAY_STAGING",
            token=TOKEN_RELAY_STAGING,
            minimum_seconds=MIN_RELAY_STAGING_SECONDS,
            instructions=(
                "1) Fully power both boards off from the Direct-baseline ROM state.\n"
                "2) Normal-boot Board A and Board B exactly once with BOOT/GPIO9 released.\n"
                "3) Keep both boards in normal AP coverage for the staging interval.\n"
                f"4) Wait at least {MIN_RELAY_STAGING_SECONDS} seconds; do not move/isolate Board B yet.\n"
                f"5) Type exactly {TOKEN_RELAY_STAGING}.\n"
            ),
        )

        failed = "OPERATOR_SELECTIVE_RF_RELAY_WINDOW"
        interlocks["relay_window"] = operator_interlock(
            root,
            name="RELAY_WINDOW",
            token=TOKEN_RELAY_COMPLETE,
            minimum_seconds=MIN_RELAY_WINDOW_SECONDS,
            instructions=(
                "1) Keep Board A powered and in normal AP coverage.\n"
                "2) Move/isolate Board B into the already-qualified selective-RF condition: AP/Wi-Fi unavailable to B while A<->B ESP-NOW remains viable.\n"
                f"3) Keep that condition for at least {MIN_RELAY_WINDOW_SECONDS} seconds.\n"
                "4) Do not open serial and do not access T1 during the window.\n"
                "5) At window end, fully power Board B off; leave Board A running for at least 10 additional seconds so its diagnostics can persist.\n"
                "6) Fully power Board A off. Bring both boards back unpowered.\n"
                "7) Re-enter fresh ROM Download on both boards; leave only these two boards enumerated.\n"
                f"8) Type exactly {TOKEN_RELAY_COMPLETE}.\n"
            ),
        )

        failed = "RELAY_POST_IDENTITY_BINDING"
        op_index, relay_bindings = discover_and_bind_boards(
            root=root,
            repo_root=repo_root,
            op_index=op_index,
            phase="relay_post",
            env=env,
        )
        relay_private: dict[str, dict[str, Any]] = {}
        for role in ("board_a", "board_b"):
            failed = f"RELAY_POST_{role.upper()}_NVS"
            op_index, relay_private[role] = capture_nvs_phase(
                root=root,
                repo_root=repo_root,
                op_index=op_index,
                phase="relay_post",
                role=role,
                binding=relay_bindings[role],
                env=env,
            )

        failed = "HOST_RELAY_CHAIN_ADJUDICATION"
        relay_public = adjudicate_relay_phase(
            a=relay_private["board_a"],
            b=relay_private["board_b"],
            baseline_a_boot_session=baseline_private["board_a"]["boot_session"],
            baseline_b_boot_session=baseline_private["board_b"]["boot_session"],
        )
        if not relay_public["board_side_relay_chain_proven"]:
            stage = relay_public["first_unproven_stage"]
            raise StopExecution(f"board-side Relay chain remains unproven at {stage}")

        next_route = "PREPARE_KF089_T1_RELAY_INGRESS_CONFIRMATION_PACKAGE"
        write_closure(
            root,
            execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="PASS",
            failed=None,
            stop_reason=None,
            target_access=target_access,
            interlocks=interlocks,
            prestate=public_prestate,
            direct_baseline=direct_public,
            relay_phase=relay_public,
            next_route=next_route,
        )
    except (StopExecution, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        write_closure(
            root,
            execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="STOP",
            failed=failed,
            stop_reason=str(exc),
            target_access=target_access,
            interlocks=interlocks,
            prestate=public_prestate,
            direct_baseline=direct_public,
            relay_phase=relay_public,
            next_route="STOP_RETURN_TO_HIGH_LEVEL_MODEL",
        )

    closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["relay_validation_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
