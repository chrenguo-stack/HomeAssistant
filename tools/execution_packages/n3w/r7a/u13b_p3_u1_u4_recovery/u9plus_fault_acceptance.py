#!/usr/bin/env python3
"""Exact-bound Phase A real-T1 U9+ fault-injection acceptance.

This gate starts from the already-consumed P3 U9 transaction.  It may stage an
exact candidate OTA daemon through a temporary systemd override, perform only
the exact U9->U10 predecessor-capacity release, and then stops for operator
power/media fault injection.  It never claims/replays product U9 authorization,
never loads the target image, and never enters U11.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = HERE / "u9plus_fault_acceptance_manifest.json"
P3_MANIFEST_PATH = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_live_to_u11" / "manifest.json"
)
sys.path.insert(0, str(HERE))

import check_ha_backup
import executor as recovery
import ha_backup
import install_intent
import preflight
import recovery_admission as u8
import u10_preflight
import u6_preflight
import u6_recovery
import u9_live_authorization as u9

SCHEMA = "gh.n3w-t1-u9plus-fault-acceptance/1"
SOURCE_PASS = "U9PLUS_PHASE_A_SOURCE_CHECK_PASS"
PREFLIGHT_PASS = "U9PLUS_PHASE_A_PREFLIGHT_PASS"
ARMED = "U9PLUS_PHASE_A_U10_ARMED"
MEDIA_REQUIRED_PASS = "U9PLUS_PHASE_A_MEDIA_REQUIRED_PASS"
RECOVERED_PASS = "U9PLUS_PHASE_A_RECOVERED_PASS"
U9 = "U9_LIVE_AUTHORIZATION_CLAIMED"
U10 = "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
U13B = "U13B_ROLLED_BACK"
STATE_ROOT = Path("/var/lib/n3w-t1-core-updater/u9plus-fault-acceptance-r1")
CANDIDATE_DIR = STATE_ROOT / "candidate-tools"
CLAIM_PATH = STATE_ROOT / "acceptance-claim.json"
ARMED_PATH = STATE_ROOT / "armed-u10.json"
MISSING_PATH = STATE_ROOT / "missing-media-observed.json"
RECOVERED_PATH = STATE_ROOT / "recovered.json"
OTA_UNIT = "n3w-t1-ha-ota.service"
OTA_SOCKET = Path("/run/n3w-t1-ota/ha-ota.sock")
OVERRIDE_DIR = Path("/etc/systemd/system/n3w-t1-ha-ota.service.d")
OVERRIDE_PATH = OVERRIDE_DIR / "90-u9plus-fault-acceptance.conf"
ORIGINAL_DAEMON = "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_daemon.py"
CANDIDATE_DAEMON = str(CANDIDATE_DIR / "n3w_t1_core_updater_ha_daemon.py")
require = recovery.require


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    require(completed.returncode == 0, "git_command_failed")
    return completed.stdout.strip()


def load_manifest(expected_commit: str) -> dict:
    require(
        re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is not None,
        "expected_commit_invalid",
    )
    require(git_text("rev-parse", "HEAD") == expected_commit, "local_head_mismatch")
    require(
        git_text("status", "--porcelain", "--untracked-files=no") == "",
        "tracked_worktree_dirty",
    )
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    require(value.get("schema") == "gh.n3w-t1-u9plus-fault-acceptance-manifest/1", "manifest_schema_invalid")
    require(value.get("live_execution_authorized") is True, "live_authorization_missing")
    require(value.get("destructive_u10_authorized") is True, "u10_authorization_missing")
    require(value.get("candidate_daemon_override_authorized") is True, "daemon_override_authorization_missing")
    require(value.get("product_u9_reclaim_authorized") is False, "product_u9_reclaim_forbidden")
    require(value.get("product_u9_replay_authorized") is False, "product_u9_replay_forbidden")
    require(value.get("target_image_load_authorized") is False, "target_load_must_remain_forbidden")
    require(value.get("u11_plus_authorized") is False, "u11_plus_must_remain_forbidden")
    require(value.get("merge") is False, "merge_must_remain_forbidden")
    for relative, blob in value["package_source_authority"].items():
        require(git_text("rev-parse", "HEAD:" + relative) == blob, "package_source_authority_drift:" + relative)
    require(
        git_text("rev-parse", "HEAD:" + value["p3_candidate_source_manifest"])
        == value["p3_candidate_source_manifest_blob"],
        "p3_candidate_manifest_drift",
    )
    return value


def build_candidate_bundle(manifest: dict, directory: Path):
    p3 = json.loads(P3_MANIFEST_PATH.read_text(encoding="utf-8"))
    authority = p3["product_source_authority"]
    bundle = directory / "candidate-tools.zip"
    content_hashes = {}
    names = set()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, blob in sorted(authority.items()):
            require(git_text("rev-parse", "HEAD:" + relative) == blob, "candidate_source_blob_drift:" + relative)
            path = ROOT / relative
            name = path.name
            require(name not in names, "candidate_source_name_collision")
            names.add(name)
            raw = path.read_bytes()
            content_hashes[name] = hashlib.sha256(raw).hexdigest()
            archive.writestr(name, raw)
    return bundle, content_hashes


def build_plan(manifest: dict, expected_commit: str, execution_id: str, hashes: dict | None = None, bundle_sha: str | None = None):
    plan = install_intent.build_plan(ROOT, expected_commit)
    plan["fault_acceptance"] = {
        "gate_id": manifest["gate_id"],
        "authorization_id": manifest["authorization_id"],
        "confirmation": manifest["confirmation"],
        "authorized_execution_id": manifest["authorized_execution_id"],
        "execution_id": execution_id,
        "source_head": expected_commit,
        "current_u9": manifest["current_u9"],
        "candidate_source_sha256": hashes or {},
        "candidate_bundle_sha256": bundle_sha,
    }
    return plan


def _fsync_dir(path: Path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_json_once(path: Path, value: dict):
    require(not path.exists() and not path.is_symlink(), "durable_file_exists:" + path.name)
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(path.parent)


def command(argv, *, timeout=120, check=True):
    completed = subprocess.run(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode:
        detail = (completed.stderr or completed.stdout).decode(errors="replace")[:240]
        raise RuntimeError("command_failed:" + Path(argv[0]).name + ":" + detail)
    return completed


def boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def transaction_sha(path: Path) -> str:
    return sha_file(path)


def systemd_contract(*, expect_override: bool):
    active = command(["systemctl", "is-active", OTA_UNIT], check=False).stdout.decode().strip()
    require(active == "active", "ota_service_not_active")
    main_pid_raw = command(["systemctl", "show", "-p", "MainPID", "--value", OTA_UNIT]).stdout.decode().strip()
    require(main_pid_raw.isdigit() and int(main_pid_raw) > 0, "ota_main_pid_invalid")
    dropins = command(["systemctl", "show", "-p", "DropInPaths", "--value", OTA_UNIT]).stdout.decode().strip()
    execstart = command(["systemctl", "show", "-p", "ExecStart", "--value", OTA_UNIT]).stdout.decode()
    if expect_override:
        require(str(OVERRIDE_PATH) in dropins, "candidate_override_not_loaded")
        require(CANDIDATE_DAEMON in execstart, "candidate_execstart_not_loaded")
    else:
        require(not dropins, "unexpected_ota_dropin_present")
        require(ORIGINAL_DAEMON in execstart, "original_ota_execstart_drift")
    return {"main_pid": int(main_pid_raw), "execstart": CANDIDATE_DAEMON if expect_override else ORIGINAL_DAEMON}


def ipc_status():
    deadline = time.time() + 60
    while time.time() < deadline and not OTA_SOCKET.exists():
        time.sleep(1)
    require(OTA_SOCKET.exists(), "ota_socket_missing")
    original_euid = os.geteuid()
    original_egid = os.getegid()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        os.setegid(999)
        os.seteuid(999)
        sock.settimeout(10)
        sock.connect(str(OTA_SOCKET))
        payload = {
            "schema": "gh.n3w-t1-ha-ota-ipc-request/1",
            "operation": "status",
        }
        sock.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        raw = b""
        while b"\n" not in raw and len(raw) < 16384:
            part = sock.recv(4096)
            if not part:
                break
            raw += part
    finally:
        try:
            sock.close()
        finally:
            os.seteuid(original_euid)
            os.setegid(original_egid)
    require(raw, "ota_status_response_empty")
    value = json.loads(raw.splitlines()[0])
    require(value.get("accepted") is True and value.get("code") == "status", "ota_status_rejected")
    return value


def installed_image_present(reference: str) -> bool:
    return command(["docker", "image", "inspect", reference], check=False).returncode == 0


def running_service_count(service: str) -> int:
    raw = command(
        [
            "docker", "ps", "-q",
            "--filter", "label=com.docker.compose.project=n3wfc4",
            "--filter", "label=com.docker.compose.service=" + service,
        ],
        check=False,
    ).stdout.decode()
    return len([line for line in raw.splitlines() if line.strip()])


def same_authorization(tx: dict, expected: list):
    return [
        tx.get("authorization_id_sha256"),
        tx.get("authorization_claimed"),
        tx.get("authorization_consumed"),
    ] == expected


def remote_preflight(plan: dict, result: dict):
    pre = {}
    u10_preflight.inspect(plan, pre)
    require(pre.get("status") == u10_preflight.PASS, "delegated_u10_preflight_failed")
    require(pre.get("transaction_sha256") == plan["fault_acceptance"]["current_u9"]["transaction_sha256"], "u9_sha_drift")
    require(pre.get("u11_plus") is False and pre.get("destructive_cutover") is False, "delegated_preflight_boundary_invalid")
    require(not STATE_ROOT.exists() and not STATE_ROOT.is_symlink(), "acceptance_state_root_exists")
    unit = systemd_contract(expect_override=False)
    ss = command(["ss", "-Htin"], check=False)
    require(ss.returncode == 0, "ss_tcp_info_capability_missing")
    result.update(
        status=PREFLIGHT_PASS,
        read_only=True,
        transaction_phase=U9,
        transaction_sha256=pre["transaction_sha256"],
        recovery_content_manifest_sha256=pre["recovery_content_manifest_sha256"],
        application_services_stopped=pre["application_services_stopped"],
        broker_continuity_verified=pre["broker_continuity_verified"],
        usb_metadata_matches=pre["usb_metadata_matches"],
        release_candidate=pre["release_candidate"],
        recovery_assets=pre["recovery_assets"],
        ota_main_pid=unit["main_pid"],
        ss_tcp_info_command_supported=True,
        u10_transition=False,
        target_image_load=False,
        u11_plus=False,
    )
    return pre


def extract_candidate(plan: dict, bundle: Path):
    fa = plan["fault_acceptance"]
    require(bundle.is_file() and not bundle.is_symlink(), "candidate_bundle_missing")
    require(sha_file(bundle) == fa["candidate_bundle_sha256"], "candidate_bundle_sha256_drift")
    require(not CANDIDATE_DIR.exists() and not CANDIDATE_DIR.is_symlink(), "candidate_dir_exists")
    CANDIDATE_DIR.mkdir(mode=0o700)
    expected = fa["candidate_source_sha256"]
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        require(set(names) == set(expected), "candidate_bundle_members_drift")
        for name in names:
            require(Path(name).name == name and "/" not in name and "\\" not in name, "candidate_member_invalid")
            raw = archive.read(name)
            require(hashlib.sha256(raw).hexdigest() == expected[name], "candidate_member_hash_drift:" + name)
            target = CANDIDATE_DIR / name
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                os.write(fd, raw)
                os.fsync(fd)
            finally:
                os.close(fd)
    _fsync_dir(CANDIDATE_DIR)
    require((CANDIDATE_DIR / "n3w_t1_core_updater_ha_daemon.py").is_file(), "candidate_daemon_missing")


def install_override_without_restart():
    before = systemd_contract(expect_override=False)
    require(not OVERRIDE_DIR.exists(), "ota_override_directory_preexisting")
    OVERRIDE_DIR.mkdir(mode=0o755)
    payload = (
        "[Service]\n"
        "ExecStart=\n"
        f"ExecStart=/usr/bin/python3 {CANDIDATE_DAEMON}\n"
    ).encode()
    fd = os.open(OVERRIDE_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(OVERRIDE_DIR)
    command(["systemctl", "daemon-reload"])
    after = systemd_contract(expect_override=True)
    require(after["main_pid"] == before["main_pid"], "ota_daemon_restarted_during_override_install")
    return before["main_pid"]


def arm_u10(plan: dict, bundle_path: str, authorization_id: str, confirmation: str, result: dict):
    fa = plan["fault_acceptance"]
    require(fa["execution_id"] == fa["authorized_execution_id"], "execution_id_not_authorized")
    require(authorization_id == fa["authorization_id"], "acceptance_authorization_id_mismatch")
    require(confirmation == fa["confirmation"], "acceptance_confirmation_mismatch")
    pre = remote_preflight(plan, result)

    STATE_ROOT.mkdir(mode=0o700)
    _fsync_dir(STATE_ROOT.parent)
    auth_before = None
    tx_path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(tx_path)
    tx = json.loads(raw)
    auth_before = [
        tx.get("authorization_id_sha256"),
        tx.get("authorization_claimed"),
        tx.get("authorization_consumed"),
    ]
    require(auth_before[1:] == [True, True], "product_u9_not_consumed")
    claim = {
        "schema": "gh.n3w-t1-u9plus-fault-acceptance-claim/1",
        "gate_id": fa["gate_id"],
        "authorization_id": authorization_id,
        "execution_id": fa["execution_id"],
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
        "product_u9_reclaimed": False,
        "product_u9_replayed": False,
        "source_head": fa["source_head"],
        "u9_transaction_sha256": transaction_sha(tx_path),
        "authorization_tuple": auth_before,
    }
    durable_json_once(CLAIM_PATH, claim)

    bundle = Path(bundle_path)
    extract_candidate(plan, bundle)
    bundle.unlink(missing_ok=True)
    old_pid = install_override_without_restart()

    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_usb import (
        destructive_cutover_allowed,
        record_predecessor_capacity_released,
    )
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore, validate_transaction_document

    tx = validate_transaction_document(json.loads(preflight.read_private(tx_path)))
    require(tx["phase"] == U9, "u9_phase_drift_before_u10")
    require(destructive_cutover_allowed(tx) is True, "destructive_cutover_not_allowed")
    require(transaction_sha(tx_path) == fa["current_u9"]["transaction_sha256"], "u9_sha_changed_before_u10")
    require(same_authorization(tx, auth_before), "u9_authorization_drift_before_u10")

    backend = SubprocessPrepareBackend()
    media = backend.resolve_transaction_media(tx, write_required=True)
    require(media is not None, "bound_media_unavailable_before_u10")
    require(media.filesystem_uuid == tx["usb_filesystem_uuid"], "bound_media_uuid_drift_before_u10")

    release = pre["release_candidate"]
    ha_container = release["homeassistant_container_id"]
    predecessor_runtime = release["predecessor_runtime_image_id"]
    predecessor_ref = tx["current_image_ref"]
    target_ref = tx["target_image_ref"]
    require(not installed_image_present(target_ref), "target_image_present_before_u10")

    cutover_started = int(time.time())
    boot_before = boot_id()
    command(["docker", "rm", ha_container], timeout=180)
    command(["docker", "image", "rm", predecessor_runtime], timeout=600)
    require(not installed_image_present(predecessor_ref), "predecessor_image_still_present_after_u10")
    require(not installed_image_present(target_ref), "target_image_loaded_during_u10")

    u10 = record_predecessor_capacity_released(
        tx,
        predecessor_runtime_released=True,
        predecessor_image_released=True,
        target_internal_image_absent=True,
    )
    require(u10["phase"] == U10, "u10_transition_invalid")
    require(same_authorization(u10, auth_before), "authorization_drift_in_u10_transition")
    backend.sync_transaction_metadata(u10, media)
    store = HaUsbStateStore()
    store.write(u10)

    final = validate_transaction_document(json.loads(preflight.read_private(tx_path)))
    require(final["phase"] == U10 and final["status"] == "ACTIVE", "u10_terminal_invalid")
    require(same_authorization(final, auth_before), "authorization_drift_after_u10")
    require(not installed_image_present(final["current_image_ref"]), "predecessor_reappeared_after_u10")
    require(not installed_image_present(final["target_image_ref"]), "target_loaded_after_u10")
    require(systemd_contract(expect_override=True)["main_pid"] == old_pid, "ota_daemon_restarted_before_fault")

    armed = {
        "schema": "gh.n3w-t1-u9plus-fault-acceptance-armed/1",
        "phase": U10,
        "transaction_sha256": transaction_sha(tx_path),
        "transaction_id_sha256": final["transaction_id_sha256"],
        "usb_filesystem_uuid": final["usb_filesystem_uuid"],
        "authorization_tuple": auth_before,
        "predecessor_image_ref": final["current_image_ref"],
        "target_image_ref": final["target_image_ref"],
        "cutover_started_unix": cutover_started,
        "boot_id_before_fault": boot_before,
        "old_daemon_pid": old_pid,
        "candidate_daemon": CANDIDATE_DAEMON,
        "safe_to_power_off": True,
    }
    durable_json_once(ARMED_PATH, armed)
    result.update(
        status=ARMED,
        read_only=False,
        destructive_u10=True,
        transaction_phase=U10,
        transaction_sha256=armed["transaction_sha256"],
        usb_filesystem_uuid=armed["usb_filesystem_uuid"],
        candidate_override_installed=True,
        current_daemon_restarted=False,
        target_image_load=False,
        u11_plus=False,
        product_u9_reclaimed=False,
        product_u9_replayed=False,
        safe_to_power_off=True,
        next_action="POWER_OFF_T1_THEN_REMOVE_BOUND_USB_THEN_POWER_ON",
    )


def observe_missing(plan: dict, result: dict):
    require(STATE_ROOT.is_dir() and ARMED_PATH.is_file() and CLAIM_PATH.is_file(), "acceptance_arm_state_missing")
    armed = json.loads(ARMED_PATH.read_text())
    require(boot_id() != armed["boot_id_before_fault"], "power_cycle_not_observed")
    systemd_contract(expect_override=True)
    tx_path = recovery.STATE / preflight.TX_NAME
    tx = json.loads(preflight.read_private(tx_path))
    require(tx.get("phase") == U10, "transaction_advanced_without_recovery_media")
    require(transaction_sha(tx_path) == armed["transaction_sha256"], "u10_transaction_changed_without_media")
    require(same_authorization(tx, armed["authorization_tuple"]), "authorization_drift_without_media")
    lsblk = command(["lsblk", "-J", "-o", "UUID"], check=False)
    require(lsblk.returncode == 0, "lsblk_failed")
    require(armed["usb_filesystem_uuid"] not in lsblk.stdout.decode(errors="replace"), "bound_usb_still_present")
    status = ipc_status()
    require(status.get("phase") == "RECOVERY_MEDIA_REQUIRED", "recovery_media_required_not_projected")
    require(status.get("error_code") is None, "recovery_media_required_has_error")
    require(not installed_image_present(armed["predecessor_image_ref"]), "predecessor_restored_without_media")
    require(not installed_image_present(armed["target_image_ref"]), "target_loaded_without_media")
    observed = {
        "schema": "gh.n3w-t1-u9plus-fault-acceptance-missing-media/1",
        "boot_id": boot_id(),
        "observed_at_unix": int(time.time()),
        "transaction_sha256": transaction_sha(tx_path),
        "usb_filesystem_uuid": armed["usb_filesystem_uuid"],
        "ipc_phase": status["phase"],
    }
    durable_json_once(MISSING_PATH, observed)
    result.update(
        status=MEDIA_REQUIRED_PASS,
        read_only=True,
        transaction_phase=U10,
        recovery_media_required=True,
        bound_usb_present=False,
        target_image_load=False,
        u11_plus=False,
        product_u9_replayed=False,
        next_action="POWER_OFF_T1_THEN_REINSERT_SAME_BOUND_USB_THEN_POWER_ON",
    )


def verify_recovered(plan: dict, result: dict):
    require(ARMED_PATH.is_file() and MISSING_PATH.is_file(), "missing_media_checkpoint_not_complete")
    armed = json.loads(ARMED_PATH.read_text())
    missing = json.loads(MISSING_PATH.read_text())
    require(boot_id() != missing["boot_id"], "second_power_cycle_not_observed")
    systemd_contract(expect_override=True)
    deadline = time.time() + 900
    last = None
    while time.time() < deadline:
        last = ipc_status()
        if last.get("phase") in {"ROLLED_BACK", "ERROR"}:
            break
        time.sleep(2)
    require(isinstance(last, dict) and last.get("phase") == "ROLLED_BACK", "automatic_recovery_not_rolled_back")
    require(last.get("error_code") is None, "automatic_recovery_error")

    tx_path = recovery.STATE / preflight.TX_NAME
    tx = json.loads(preflight.read_private(tx_path))
    require(tx.get("phase") == U13B and tx.get("status") == "ROLLED_BACK", "terminal_u13b_invalid")
    require(tx.get("rollback_origin_phase") == U10, "rollback_origin_not_u10")
    require(tx.get("failure_code") == "u9_plus_restart_bounded_recovery", "rollback_failure_code_drift")
    require(tx.get("rollback_recovery_content_verified") is True, "recovery_content_not_verified")
    require(tx.get("rollback_ha_data_restored") is True, "ha_data_not_restored")
    require(tx.get("rollback_health_verified") is True, "rollback_health_not_verified")
    require(same_authorization(tx, armed["authorization_tuple"]), "authorization_drift_after_recovery")
    require(installed_image_present(armed["predecessor_image_ref"]), "predecessor_image_not_restored")
    require(not installed_image_present(armed["target_image_ref"]), "target_image_present_after_rollback")
    require(command(["systemctl", "is-active", "n3wfc4-services-activation.service"], check=False).stdout.decode().strip() == "active", "application_owner_not_active")
    require(command(["systemctl", "is-active", "n3wfc4-broker-activation.service"], check=False).stdout.decode().strip() == "active", "broker_owner_not_active")
    for service in ("manager", "homeassistant", "broker"):
        require(running_service_count(service) == 1, "runtime_service_count_invalid:" + service)

    now = int(time.time())
    uptime = float(Path("/proc/uptime").read_text().split()[0])
    boot_epoch = int(time.time() - uptime)
    automatic_seconds = max(0, now - boot_epoch)
    lab_total_seconds = max(0, now - int(armed["cutover_started_unix"]))
    recovered = {
        "schema": "gh.n3w-t1-u9plus-fault-acceptance-recovered/1",
        "status": RECOVERED_PASS,
        "completed_at_unix": now,
        "boot_id": boot_id(),
        "transaction_sha256": transaction_sha(tx_path),
        "transaction_id_sha256": tx["transaction_id_sha256"],
        "usb_filesystem_uuid": tx["usb_filesystem_uuid"],
        "automatic_recovery_seconds_from_second_boot": automatic_seconds,
        "lab_u10_to_recovered_seconds_includes_operator_hold": lab_total_seconds,
        "customer_downtime_sla_proven": False,
        "target_image_load": False,
        "u11_plus": False,
        "product_u9_replayed": False,
    }
    durable_json_once(RECOVERED_PATH, recovered)
    result.update(recovered)
    result["read_only"] = True
    result["phase_a_pass"] = True
    result["next_boundary"] = "PHASE_B_FRESH_CONTINUOUS_DOWNTIME_ACCEPTANCE_OR_STOP"


def remote_main(mode: str, encoded: str, extra: list[str]):
    result = {
        "schema": SCHEMA,
        "status": "STOP",
        "read_only": mode != "arm-u10",
        "destructive_u10": False,
        "target_image_load": False,
        "u11_plus": False,
        "product_u9_replayed": False,
        "merge": False,
    }
    try:
        require(os.geteuid() == 0, "target_root_required")
        plan = json.loads(base64.b64decode(encoded, validate=True))
        if mode == "preflight":
            remote_preflight(plan, result)
        elif mode == "arm-u10":
            require(len(extra) == 3, "arm_arguments_invalid")
            arm_u10(plan, extra[0], extra[1], extra[2], result)
        elif mode == "observe-missing":
            observe_missing(plan, result)
        elif mode == "verify-recovered":
            verify_recovered(plan, result)
        else:
            raise RuntimeError("remote_mode_invalid")
    except Exception as error:
        result["reason"] = recovery.safe_reason(error)
    print(json.dumps(result, sort_keys=True))
    success = {
        "preflight": PREFLIGHT_PASS,
        "arm-u10": ARMED,
        "observe-missing": MEDIA_REQUIRED_PASS,
        "verify-recovered": RECOVERED_PASS,
    }
    return 0 if result.get("status") == success.get(mode) else 2


def bootstrap_for_remote():
    return u6_recovery.make_bootstrap(
        Path(__file__).resolve(),
        extra_modules=(
            ("u10_preflight", u10_preflight),
            ("u6_recovery", u6_recovery),
            ("check_ha_backup", check_ha_backup),
            ("ha_backup", ha_backup),
            ("recovery_admission", u8),
            ("u9_live_authorization", u9),
        ),
    )


def source_check(manifest: dict, expected_commit: str):
    with tempfile.TemporaryDirectory(prefix="n3w-u9plus-fi-") as raw:
        bundle, hashes = build_candidate_bundle(manifest, Path(raw))
        require("n3w_t1_core_updater_ha_daemon.py" in hashes, "candidate_daemon_not_bound")
        require("n3w_t1_core_updater_ha_u13b_host.py" in hashes, "candidate_oracle_not_bound")
        require("n3w_t1_core_updater_ha_u13b_auto.py" in hashes, "candidate_recovery_not_bound")
        require("n3w_t1_core_updater_ha_ipc.py" in hashes, "candidate_ipc_not_bound")
        return {
            "schema": SCHEMA,
            "status": SOURCE_PASS,
            "expected_commit": expected_commit,
            "candidate_member_count": len(hashes),
            "candidate_bundle_sha256": sha_file(bundle),
            "current_u9_transaction_sha256": manifest["current_u9"]["transaction_sha256"],
            "target_image_load_authorized": False,
            "u11_plus_authorized": False,
            "merge": False,
        }


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument(
        "--mode",
        choices=("source-check", "preflight", "arm-u10", "observe-missing", "verify-recovered"),
        default="source-check",
    )
    parser.add_argument("--execution-id")
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--authorization-id")
    parser.add_argument("--confirm")
    args = parser.parse_args()

    manifest = load_manifest(args.expected_commit)
    if args.mode == "source-check":
        print(json.dumps(source_check(manifest, args.expected_commit), sort_keys=True))
        return 0

    require(
        all((args.execution_id, args.t1_ssh_target, args.known_hosts, args.expected_host_key_sha256, args.evidence_root)),
        "missing_operator_connection_inputs",
    )
    require(args.execution_id == manifest["authorized_execution_id"], "execution_id_not_authorized")
    os.umask(0o077)
    args.evidence_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    sys.path.insert(0, str(ROOT / "tools"))
    from n3w_t1_ssh_transport import SSHTransport

    bundle_path = None
    hashes = None
    bundle_sha = None
    temp = None
    if args.mode == "arm-u10":
        require(args.authorization_id == manifest["authorization_id"], "authorization_id_mismatch")
        require(args.confirm == manifest["confirmation"], "confirmation_mismatch")
        temp = tempfile.TemporaryDirectory(prefix="n3w-u9plus-fi-bundle-")
        bundle_path, hashes = build_candidate_bundle(manifest, Path(temp.name))
        bundle_sha = sha_file(bundle_path)

    plan = build_plan(manifest, args.expected_commit, args.execution_id, hashes, bundle_sha)
    data = base64.b64encode(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).decode()
    bootstrap = bootstrap_for_remote()
    transport = SSHTransport(
        target=args.t1_ssh_target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.expected_host_key_sha256,
    )
    receipt = None
    rc = 2
    transport.start_epoch()
    try:
        remote_extra = []
        remote_bundle = None
        if args.mode == "arm-u10":
            remote_bundle = f"/tmp/n3w-u9plus-fi-{args.execution_id}.zip"
            transport.scp_to(bundle_path, remote_bundle, timeout=1800)
            remote_extra = [remote_bundle, args.authorization_id, args.confirm]
        completed = transport.run_remote(
            ["python3", "-I", "-B", "-c", bootstrap, "--remote", args.mode, data, *remote_extra],
            timeout=3600 if args.mode in {"arm-u10", "verify-recovered"} else 1200,
            check=False,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        require(lines, "remote_stdout_empty")
        receipt = json.loads(lines[-1])
        rc = completed.returncode
    except Exception as error:
        receipt = {
            "schema": SCHEMA,
            "status": "STOP_UNKNOWN",
            "reason": recovery.safe_reason(error),
            "target_image_load": False,
            "u11_plus": False,
            "product_u9_replayed": False,
            "merge": False,
        }
        rc = 2
    finally:
        transport.close_epoch()
        if temp is not None:
            temp.cleanup()

    recovery.write_once(args.evidence_root / f"{args.mode}-result.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    expected = {
        "preflight": PREFLIGHT_PASS,
        "arm-u10": ARMED,
        "observe-missing": MEDIA_REQUIRED_PASS,
        "verify-recovered": RECOVERED_PASS,
    }[args.mode]
    return 0 if rc == 0 and receipt.get("status") == expected else 2


if __name__ == "__main__":
    try:
        if len(sys.argv) >= 4 and sys.argv[1] == "--remote":
            raise SystemExit(remote_main(sys.argv[2], sys.argv[3], sys.argv[4:]))
        raise SystemExit(local_main())
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": recovery.safe_reason(error),
                    "target_image_load": False,
                    "u11_plus": False,
                    "product_u9_replayed": False,
                    "merge": False,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2) from None
