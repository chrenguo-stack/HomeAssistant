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
ID19_IMPL_PATH = PACKAGE_DIR.parent / "id19_board_a_slot_switch_only" / "executor_impl.py"
ID18_IMPL_GIT_BLOB = "27744d2b54ec0d5318496d9ca99b647465daa769"
ID19_IMPL_GIT_BLOB = "b51344bc804463f5e5c9d1d3c421be81e3fb352e"
ID19_EXECUTION_PACKAGE_COMMIT = "643df426a03a20b319d8faa2a9d62eda9c56d6a6"
DIAG_PARSER_GIT_BLOB = "af78ed4cb14c38579f56e6ba3019e2debdb21d9e"
EXPECTED_APP0_SHA256 = "5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b"
EXPECTED_APP1_SHA256 = "5a3004647de0ef71e7be5664863a62b76a47c0cfdb32e38b07a296ca379f7562"
EXPECTED_SELECTED_SLOT = 0
EXPECTED_ACTIVE_SEQ = 5
EXPECTED_ACTIVE_STATE = 2
PRIOR_BOARD_A_SCHEMA_VERSION = 3
PRIOR_BOARD_A_BOOT_SESSION = 11540229135812003068
EXPECTED_SCHEMA_VERSION = 5
MIN_OPERATOR_ELAPSED_SECONDS = 45
MIN_SNAPSHOT_UPTIME_MS = 5000
ALLOWED_DIRECT_CHANNELS = {1, 6, 11}
OPERATOR_TOKEN = "BOOT_COMPLETE_AND_ROM_REENTERED"
NVS_OFFSET = 0x790000
NVS_SIZE = 0x70000

COMPACT_COUNTER_FIELDS = (
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
    spec = importlib.util.spec_from_file_location("id20_id18_common", ID18_IMPL_PATH)
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
    if value.get("gate_id") != "id20_board_a_schema5_boot_postcheck":
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
                "claim_boundary": "immediately_before_single_normal_boot_operator_interlock",
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
    diag_parser = repo_root / "tools" / "n3w_read_diag_snapshot.py"
    checks = (
        ("host_git_head", ["git", "rev-parse", "HEAD"], expected_commit),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"], ""),
        (
            "id18_impl_blob",
            ["git", "hash-object", str(ID18_IMPL_PATH.relative_to(repo_root))],
            ID18_IMPL_GIT_BLOB,
        ),
        (
            "id19_impl_blob",
            ["git", "hash-object", str(ID19_IMPL_PATH.relative_to(repo_root))],
            ID19_IMPL_GIT_BLOB,
        ),
        (
            "diag_parser_blob",
            ["git", "hash-object", str(diag_parser.relative_to(repo_root))],
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


def operator_interlock(root: Path) -> float:
    instructions = (
        "\nID20 OPERATOR INTERLOCK\n"
        "1) Board B and every other N3-W compact sender must be fully powered off.\n"
        "2) Fully power off Board A, including USB and every alternate power source.\n"
        "3) Release BOOT/GPIO9. Connect Board A normally exactly once without pressing BOOT.\n"
        "4) Leave the application running for at least 45 seconds. Do not open serial, reset, or run a Relay/RF experiment.\n"
        "5) Fully power Board A off once.\n"
        "6) Hold BOOT/GPIO9 low, connect USB, wait for enumeration, then release BOOT.\n"
        "7) Leave only this Board A as a /dev/cu.usbmodem* device for this gate.\n"
        f"8) Type exactly {OPERATOR_TOKEN} only after fresh ROM re-entry is complete.\n"
    )
    print(instructions, file=sys.stderr, flush=True)
    start_monotonic = time.monotonic()
    start_utc = id18.utc_now()
    token = input("ID20 confirmation token: ").strip()
    elapsed = time.monotonic() - start_monotonic
    id18.write_json(
        root / "operator_interlock.json",
        {
            "required_token": OPERATOR_TOKEN,
            "token_match": token == OPERATOR_TOKEN,
            "minimum_elapsed_seconds": MIN_OPERATOR_ELAPSED_SECONDS,
            "observed_elapsed_seconds": elapsed,
            "interlock_started_at": start_utc,
            "interlock_confirmed_at": id18.utc_now(),
            "board_b_and_other_compact_senders_powered_off_attested": token == OPERATOR_TOKEN,
            "single_normal_boot_attested": token == OPERATOR_TOKEN,
            "serial_open_attested_false": token == OPERATOR_TOKEN,
            "controlled_rf_experiment_attested_false": token == OPERATOR_TOKEN,
            "fresh_rom_reentry_attested": token == OPERATOR_TOKEN,
        },
    )
    if token != OPERATOR_TOKEN:
        raise StopExecution("operator interlock token mismatch")
    if elapsed < MIN_OPERATOR_ELAPSED_SECONDS:
        raise StopExecution("operator interlock elapsed time is below minimum")
    return elapsed


def locate_single_usbmodem(root: Path) -> str:
    candidates = sorted(set(glob.glob("/dev/cu.usbmodem*")))
    id18.write_json(
        root / "host_port_locator_postboot.json",
        {
            "candidates": candidates,
            "candidate_count": len(candidates),
            "serial_open": False,
            "checked_at": id18.utc_now(),
        },
    )
    if len(candidates) != 1:
        raise StopExecution("expected exactly one /dev/cu.usbmodem* locator after ROM re-entry")
    path = Path(candidates[0])
    info = path.stat()
    if not stat.S_ISCHR(info.st_mode):
        raise StopExecution("postboot Board A locator is not a character device")
    return candidates[0]


def decode_snapshot(
    *,
    root: Path,
    index: int,
    repo_root: Path,
    nvs_path: Path,
) -> tuple[int, dict[str, Any]]:
    parser_path = repo_root / "tools" / "n3w_read_diag_snapshot.py"
    result = run_recorded(
        root=root,
        index=index,
        label="host_decode_schema5_snapshot",
        argv=[sys.executable, str(parser_path), "--nvs-image", str(nvs_path)],
        cwd=repo_root,
    )
    if result.returncode != 0:
        raise StopExecution("Board A diagnostic snapshot decode failed")
    try:
        value = json.loads((result.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise StopExecution("Board A diagnostic snapshot output is not JSON") from exc
    if not isinstance(value, dict):
        raise StopExecution("Board A diagnostic snapshot output is not an object")
    return index + 1, value


def _require_int(snapshot: dict[str, Any], field: str) -> int:
    value = snapshot.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StopExecution(f"diagnostic field is not an integer: {field}")
    return value


def adjudicate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    schema = _require_int(snapshot, "schema_version")
    if schema != EXPECTED_SCHEMA_VERSION:
        raise StopExecution(f"Board A diagnostic schema mismatch: {schema}")

    boot_session = _require_int(snapshot, "boot_session")
    if boot_session == 0:
        raise StopExecution("Schema-v5 boot session is zero")
    if boot_session == PRIOR_BOARD_A_BOOT_SESSION:
        raise StopExecution("Schema-v5 boot session did not change from ID16")

    uptime = _require_int(snapshot, "snapshot_uptime_ms")
    if uptime < MIN_SNAPSHOT_UPTIME_MS:
        raise StopExecution("Schema-v5 snapshot uptime is below minimum")

    start_mode = _require_int(snapshot, "runtime_start_mode")
    if start_mode not in (0, 1):
        raise StopExecution("Schema-v5 runtime start mode is invalid")

    path_state = _require_int(snapshot, "path_state")
    if path_state != 0:
        raise StopExecution("Board A did not finish ID20 in Direct path state")

    current_channel = _require_int(snapshot, "current_channel")
    direct_hint = _require_int(snapshot, "direct_channel_hint")
    if current_channel not in ALLOWED_DIRECT_CHANNELS:
        raise StopExecution("Board A current channel is outside the frozen N3-W channel set")
    if direct_hint != current_channel:
        raise StopExecution("Board A direct channel hint does not match current channel")

    ad_attempts = _require_int(snapshot, "relay_advertisement_attempts")
    ad_success = _require_int(snapshot, "relay_advertisement_submit_success")
    broadcast_done = _require_int(snapshot, "broadcast_completion_count")
    if ad_attempts < 1:
        raise StopExecution("Schema-v5 runtime did not attempt a Relay advertisement")
    if ad_success < 1:
        raise StopExecution("Schema-v5 runtime did not successfully submit a Relay advertisement")
    if broadcast_done < 1:
        raise StopExecution("Schema-v5 runtime has no broadcast completion evidence")

    relay_active_count = _require_int(snapshot, "relay_active_count")
    relay_telemetry_attempts = _require_int(snapshot, "relay_telemetry_attempts")
    if relay_active_count != 0 or relay_telemetry_attempts != 0:
        raise StopExecution("Board A clean Direct baseline was contaminated by Relay-active runtime")

    compact_values: dict[str, int] = {}
    for field in COMPACT_COUNTER_FIELDS:
        value = _require_int(snapshot, field)
        compact_values[field] = value
        if value != 0:
            raise StopExecution(f"Schema-v5 compact baseline is not zero: {field}")

    return {
        "schema_version": schema,
        "boot_session": boot_session,
        "boot_session_changed_from_id16": True,
        "snapshot_uptime_ms": uptime,
        "runtime_start_mode": start_mode,
        "path_state": path_state,
        "current_channel": current_channel,
        "direct_channel_hint": direct_hint,
        "relay_advertisement_attempts": ad_attempts,
        "relay_advertisement_submit_success": ad_success,
        "relay_advertisement_submit_failure": _require_int(
            snapshot, "relay_advertisement_submit_failure"
        ),
        "broadcast_completion_count": broadcast_done,
        "broadcast_completion_success": _require_int(snapshot, "broadcast_completion_success"),
        "broadcast_completion_failure": _require_int(snapshot, "broadcast_completion_failure"),
        "relay_active_count": relay_active_count,
        "relay_telemetry_attempts": relay_telemetry_attempts,
        "compact_counters": compact_values,
        "compact_baseline_clean": True,
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
    operator_elapsed_seconds: float | None,
    poststate: dict[str, Any] | None,
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
            "boot_postcheck_result": result,
            "first_failed_operation": failed,
            "stop_reason": stop_reason,
            "target_access_occurred": target_access,
            "operator_interlock_elapsed_seconds": operator_elapsed_seconds,
            "single_normal_boot_authorized": True,
            "single_normal_boot_attested": (root / "operator_interlock.json").is_file(),
            "application_booted": result == "PASS",
            "board_b_physical_access": False,
            "t1_access": False,
            "controlled_rf_experiment": False,
            "serial_open": False,
            "flash_write": False,
            "flash_erase": False,
            "nvs_write": False,
            "otadata_write": False,
            "app0_write": False,
            "app1_write": False,
            "automatic_retry": False,
            "automatic_rollback": False,
            "poststate": poststate,
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
    if manifest["predecessor"]["execution_package_commit"] != ID19_EXECUTION_PACKAGE_COMMIT:
        raise StopExecution("ID19 predecessor binding mismatch")
    refs = manifest["authority_references"]
    if refs["schema5_app0_sha256"] != EXPECTED_APP0_SHA256:
        raise StopExecution("app0 Schema-v5 authority mismatch")
    if refs["rollback_app1_sha256"] != EXPECTED_APP1_SHA256:
        raise StopExecution("app1 rollback authority mismatch")
    if refs["id18_executor_impl_git_blob"] != ID18_IMPL_GIT_BLOB:
        raise StopExecution("ID18 helper blob authority mismatch")
    if refs["id19_executor_impl_git_blob"] != ID19_IMPL_GIT_BLOB:
        raise StopExecution("ID19 predecessor blob authority mismatch")
    if refs["diag_parser_git_blob"] != DIAG_PARSER_GIT_BLOB:
        raise StopExecution("diagnostic parser blob authority mismatch")
    if manifest["operator_contract"]["minimum_interlock_elapsed_seconds"] != MIN_OPERATOR_ELAPSED_SECONDS:
        raise StopExecution("operator elapsed-time contract mismatch")
    if manifest["postcheck_contract"]["minimum_snapshot_uptime_ms"] != MIN_SNAPSHOT_UPTIME_MS:
        raise StopExecution("snapshot uptime contract mismatch")
    id18.assert_read_only_argv(id18.build_read_mac_command("/dev/example"))
    for offset, size in (
        (id18.PARTITION_TABLE_OFFSET, id18.PARTITION_TABLE_SIZE),
        (id18.OTADATA_OFFSET, id18.OTADATA_SIZE),
        (id18.APP0_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
        (id18.APP1_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
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
    write_authorization(root, args.authorization_id, args.execution_id, claimed=False)

    op_index = 1
    target_access: bool | str = False
    failed = "HOST_PREFLIGHT"
    operator_elapsed: float | None = None
    poststate: dict[str, Any] | None = None
    next_route = "STOP_RETURN_TO_HIGH_LEVEL_MODEL"

    try:
        op_index = verify_host(root, repo_root, args.expected_package_commit)
        write_authorization(root, args.authorization_id, args.execution_id, claimed=True)

        failed = "OPERATOR_SINGLE_NORMAL_BOOT_AND_ROM_REENTRY"
        operator_elapsed = operator_interlock(root)

        failed = "POSTBOOT_BOARD_A_LOCATOR"
        board_a_port = locate_single_usbmodem(root)
        env = {
            "ESPTOOL_CFGFILE": str(cfg),
            "ESPTOOL_OPEN_PORT_ATTEMPTS": "1",
        }

        failed = "BOARD_A_READ_MAC"
        target_access = "UNKNOWN"
        identity = run_recorded(
            root=root,
            index=op_index,
            label="board_a_read_mac",
            argv=id18.build_read_mac_command(board_a_port),
            cwd=repo_root,
            target_operation=True,
            extra_env=env,
        )
        op_index += 1
        if identity.returncode != 0:
            raise StopExecution("Board A read-mac failed")
        target_access = True
        base_mac = id18.parse_base_mac(identity.stdout or "")
        if id18.mac_suffix(base_mac) != id18.EXPECTED_BOARD_A_SUFFIX:
            raise StopExecution("Board A identity suffix mismatch")

        board_dir = root / "board_a"
        id18.ensure_private_dir(board_dir)
        id18.write_json(
            board_dir / "identity_private.json",
            {
                "base_mac": base_mac,
                "base_mac_sha256": hashlib.sha256(base_mac.encode()).hexdigest(),
                "observed_suffix": id18.mac_suffix(base_mac),
                "identity_match": True,
            },
        )

        captures = (
            ("post_partition_table", id18.PARTITION_TABLE_OFFSET, id18.PARTITION_TABLE_SIZE),
            ("post_otadata", id18.OTADATA_OFFSET, id18.OTADATA_SIZE),
            ("post_app0_window", id18.APP0_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
            ("post_app1_window", id18.APP1_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
            ("post_nvs", NVS_OFFSET, NVS_SIZE),
        )
        paths: dict[str, Path] = {}
        for label, offset, size in captures:
            failed = f"BOARD_A_{label.upper()}_READ"
            out = board_dir / f"{label}.bin"
            paths[label] = out
            result = run_recorded(
                root=root,
                index=op_index,
                label=f"board_a_read_{label}",
                argv=id18.build_read_flash_command(board_a_port, offset, size, out),
                cwd=repo_root,
                target_operation=True,
                extra_env=env,
            )
            op_index += 1
            if result.returncode != 0:
                raise StopExecution(f"Board A {label} read failed")
            if not out.is_file() or out.stat().st_size != size:
                raise StopExecution(f"Board A {label} output size/path mismatch")
            os.chmod(out, 0o600)

        failed = "HOST_POSTBOOT_SLOT_AND_IMAGE_ADJUDICATION"
        id18.parse_partition_table(paths["post_partition_table"].read_bytes())
        ota = id18.parse_otadata(paths["post_otadata"].read_bytes())
        if ota.selected_slot != EXPECTED_SELECTED_SLOT:
            raise StopExecution("postboot selected OTA slot is not app0")
        if ota.active_seq != EXPECTED_ACTIVE_SEQ:
            raise StopExecution("postboot active OTA sequence is not 5")
        if ota.active_state != EXPECTED_ACTIVE_STATE:
            raise StopExecution("postboot active OTA state is not VALID")
        app0_sha = id18.sha256_file(paths["post_app0_window"])
        app1_sha = id18.sha256_file(paths["post_app1_window"])
        if app0_sha != EXPECTED_APP0_SHA256:
            raise StopExecution("app0 exact Schema-v5 binding changed after boot")
        if app1_sha != EXPECTED_APP1_SHA256:
            raise StopExecution("app1 rollback binding changed after boot")

        failed = "HOST_SCHEMA5_SNAPSHOT_DECODE"
        op_index, snapshot = decode_snapshot(
            root=root,
            index=op_index,
            repo_root=repo_root,
            nvs_path=paths["post_nvs"],
        )

        failed = "HOST_SCHEMA5_RUNTIME_ADJUDICATION"
        diagnostic = adjudicate_snapshot(snapshot)
        poststate = {
            "selected_slot": ota.selected_slot,
            "active_seq": ota.active_seq,
            "active_state": ota.active_state,
            "app0_window_sha256": app0_sha,
            "app1_window_sha256": app1_sha,
            "app0_exact_schema5": True,
            "app1_rollback_hash_exact": True,
            "nvs_partition_size": paths["post_nvs"].stat().st_size,
            "nvs_partition_sha256": id18.sha256_file(paths["post_nvs"]),
            "diagnostic": diagnostic,
            "board_a_schema5_actually_booted": True,
            "board_a_schema5_runtime_alive": True,
            "schema5_compact_baseline_clean": True,
        }
        id18.write_json(board_dir / "poststate_summary.json", poststate)
        next_route = "PREPARE_KF089_SCHEMA5_TWO_BOARD_RELAY_VALIDATION_PACKAGE"
        write_closure(
            root,
            execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="PASS",
            failed=None,
            stop_reason=None,
            target_access=target_access,
            operator_elapsed_seconds=operator_elapsed,
            poststate=poststate,
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
            operator_elapsed_seconds=operator_elapsed,
            poststate=poststate,
            next_route="STOP_RETURN_TO_HIGH_LEVEL_MODEL",
        )

    closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["boot_postcheck_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())