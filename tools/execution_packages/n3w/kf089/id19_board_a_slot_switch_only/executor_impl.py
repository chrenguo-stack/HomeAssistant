#!/usr/bin/env python3
from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import os
import stat
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PACKAGE_DIR = Path(__file__).resolve().parent
ID18_IMPL_PATH = PACKAGE_DIR.parent / "id18_board_a_inactive_app0_schema5_deployment" / "executor_impl.py"
ID18_IMPL_GIT_BLOB = "27744d2b54ec0d5318496d9ca99b647465daa769"
ID18_EXECUTION_PACKAGE_COMMIT = "b796acc305a06610b34c1d0d0e35fcf2b37336ff"
EXPECTED_APP0_SHA256 = "5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b"
EXPECTED_APP1_SHA256 = "5a3004647de0ef71e7be5664863a62b76a47c0cfdb32e38b07a296ca379f7562"
TARGET_SLOT = 0
EXPECTED_SELECTED_SLOT = 1
EXPECTED_ACTIVE_SEQ = 4
EXPECTED_ACTIVE_STATE = 2
OTA_ENTRY_SIZE = 32
OTADATA_SECTOR_SIZE = 0x1000
OTA_COPY_RELATIVE_OFFSETS = (0x0000, 0x1000)
UINT32_MAX = 0xFFFFFFFF
VALID_STATE = 2
UNDEFINED_STATE = UINT32_MAX


def _load_id18():
    spec = importlib.util.spec_from_file_location("id19_id18_common", ID18_IMPL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("ID18 implementation could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


id18 = _load_id18()
StopExecution = id18.StopExecution


@dataclass(frozen=True)
class SlotSwitchPlan:
    target_slot: int
    current_slot: int
    active_index: int
    target_copy_index: int
    target_flash_offset: int
    old_active_seq: int
    new_seq: int
    preserved_state: int
    expected_crc: int
    entry_image: bytes
    expected_post_otadata: bytes

    def public_dict(self) -> dict[str, Any]:
        return {
            "target_slot": self.target_slot,
            "current_slot": self.current_slot,
            "active_index": self.active_index,
            "target_copy_index": self.target_copy_index,
            "target_flash_offset": hex(self.target_flash_offset),
            "old_active_seq": self.old_active_seq,
            "new_seq": self.new_seq,
            "preserved_state": self.preserved_state,
            "expected_crc": self.expected_crc,
            "entry_image_sha256": hashlib.sha256(self.entry_image).hexdigest(),
            "expected_post_otadata_sha256": hashlib.sha256(self.expected_post_otadata).hexdigest(),
        }


def load_manifest() -> dict[str, Any]:
    value = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    if value.get("package_schema_version") != 1:
        raise StopExecution("manifest package schema version mismatch")
    if value.get("gate_id") != "id19_board_a_slot_switch_only":
        raise StopExecution("manifest gate id mismatch")
    return value


def ota_crc(seq: int) -> int:
    return binascii.crc32(struct.pack("<I", seq), UINT32_MAX) & UINT32_MAX


def next_seq_for_slot(active_seq: int, target_slot: int) -> int:
    if not 0 < active_seq < UINT32_MAX:
        raise StopExecution("active ota_seq outside supported range")
    if target_slot not in (0, 1):
        raise StopExecution("target slot must be 0 or 1")
    candidate = active_seq + 1
    while (candidate - 1) % 2 != target_slot:
        candidate += 1
    if candidate >= UINT32_MAX:
        raise StopExecution("computed ota_seq reaches overflow marker")
    return candidate


def plan_slot_switch(pre_otadata: bytes) -> SlotSwitchPlan:
    if len(pre_otadata) != id18.OTADATA_SIZE:
        raise StopExecution("prechange otadata size mismatch")
    snap = id18.parse_otadata(pre_otadata)
    if snap.selected_slot != EXPECTED_SELECTED_SLOT:
        raise StopExecution("selected OTA slot drifted from ID18")
    if snap.active_seq != EXPECTED_ACTIVE_SEQ:
        raise StopExecution("active OTA sequence drifted from ID18")
    if snap.active_state != EXPECTED_ACTIVE_STATE:
        raise StopExecution("active OTA state drifted from ID18")

    target_index = 1 - snap.active_index
    rel = OTA_COPY_RELATIVE_OFFSETS[target_index]
    target_raw = pre_otadata[rel:rel + OTA_ENTRY_SIZE]
    erased = target_raw == b"\xff" * OTA_ENTRY_SIZE
    target_state = struct.unpack_from("<I", target_raw, 24)[0]
    if erased:
        preserved_state = UNDEFINED_STATE
    elif target_state in (VALID_STATE, UNDEFINED_STATE):
        preserved_state = target_state
    else:
        raise StopExecution("target OTA entry state is unsafe to preserve")

    new_seq = next_seq_for_slot(snap.active_seq, TARGET_SLOT)
    entry = bytearray(target_raw)
    struct.pack_into("<I", entry, 0, new_seq)
    crc = ota_crc(new_seq)
    struct.pack_into("<I", entry, 28, crc)
    if struct.unpack_from("<I", entry, 24)[0] != preserved_state:
        raise StopExecution("slot planner changed OTA state")
    if entry[4:24] != target_raw[4:24]:
        raise StopExecution("slot planner changed seq_label")
    for index, (before, after) in enumerate(zip(target_raw, entry)):
        if before != after and not (index < 4 or index >= 28):
            raise StopExecution("slot planner changed bytes outside sequence/CRC")

    expected = bytearray(pre_otadata)
    expected[rel:rel + OTADATA_SECTOR_SIZE] = bytes(entry) + b"\xff" * (OTADATA_SECTOR_SIZE - OTA_ENTRY_SIZE)
    return SlotSwitchPlan(
        target_slot=TARGET_SLOT,
        current_slot=snap.selected_slot,
        active_index=snap.active_index,
        target_copy_index=target_index,
        target_flash_offset=id18.OTADATA_OFFSET + rel,
        old_active_seq=snap.active_seq,
        new_seq=new_seq,
        preserved_state=preserved_state,
        expected_crc=crc,
        entry_image=bytes(entry),
        expected_post_otadata=bytes(expected),
    )


def verify_post_otadata(pre: bytes, post: bytes, plan: SlotSwitchPlan) -> dict[str, Any]:
    if post != plan.expected_post_otadata:
        raise StopExecution("postchange otadata does not match exact planned image")
    other = 1 - plan.target_copy_index
    rel = OTA_COPY_RELATIVE_OFFSETS[other]
    if post[rel:rel + OTADATA_SECTOR_SIZE] != pre[rel:rel + OTADATA_SECTOR_SIZE]:
        raise StopExecution("non-target otadata sector changed")
    snap = id18.parse_otadata(post)
    if snap.selected_slot != TARGET_SLOT:
        raise StopExecution("postchange selected slot is not app0")
    if snap.active_index != plan.target_copy_index:
        raise StopExecution("postchange active OTA copy mismatch")
    active = snap.entries[snap.active_index]
    if active.seq != plan.new_seq or active.crc != plan.expected_crc:
        raise StopExecution("postchange sequence/CRC mismatch")
    if active.ota_state != plan.preserved_state:
        raise StopExecution("postchange OTA state mismatch")
    return {
        "selected_slot": snap.selected_slot,
        "active_seq": snap.active_seq,
        "active_state": snap.active_state,
        "active_copy_index": snap.active_index,
        "new_seq": plan.new_seq,
        "non_target_sector_unchanged": True,
        "otadata_exact_plan_match": True,
    }


def run_recorded(*, root: Path, index: int, label: str, argv: list[str], cwd: Path,
                 target_operation: bool = False, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return id18.run_recorded(
        root=root, index=index, label=label, argv=argv, cwd=cwd,
        target_operation=target_operation, extra_env=extra_env,
    )


def verify_host(root: Path, repo_root: Path, expected_commit: str) -> int:
    index = 1
    checks = (
        ("host_git_head", ["git", "rev-parse", "HEAD"], expected_commit),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"], ""),
        ("id18_impl_blob", ["git", "hash-object", str(ID18_IMPL_PATH.relative_to(repo_root))], ID18_IMPL_GIT_BLOB),
    )
    for label, argv, expected in checks:
        result = run_recorded(root=root, index=index, label=label, argv=argv, cwd=repo_root)
        if result.returncode != 0 or (result.stdout or "").strip() != expected:
            raise StopExecution(f"{label} binding failed")
        index += 1
    result = run_recorded(
        root=root, index=index, label="host_esptool_version",
        argv=[sys.executable, "-m", "esptool", "version"], cwd=repo_root,
    )
    versions = id18.VERSION_RE.findall((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0 or id18.EXPECTED_ESPTOOL_VERSION not in versions:
        raise StopExecution("esptool version preflight failed")
    return index + 1


def verify_port_locator(root: Path, port: str) -> None:
    path = Path(port)
    info = path.stat()
    if not stat.S_ISCHR(info.st_mode):
        raise StopExecution("Board A port locator is not a character device")
    id18.write_json(root / "host_port_locator_preflight.json", {
        "serial_open": False,
        "board_a_locator": str(path),
        "resolved_locator": os.path.realpath(str(path)),
        "character_device": True,
        "checked_at": id18.utc_now(),
    })


def direct_switch_once(*, runtime: Mapping[str, Any], root: Path, port: str,
                       expected_base_mac: str, plan: SlotSwitchPlan,
                       pre_otadata: bytes, pre_app0: Path, pre_app1: Path) -> None:
    expected_mac = id18.mac_tuple(expected_base_mac)
    app0_md5 = id18.md5_file(pre_app0)
    app1_md5 = id18.md5_file(pre_app1)
    ota_md5 = id18.md5_bytes(pre_otadata)
    expected_post_md5 = id18.md5_bytes(plan.expected_post_otadata)
    esp_cls = runtime["ESP32C6ROM"]
    attach_flash = runtime["attach_flash"]
    block_size = int(runtime["flash_write_size"])
    if block_size != id18.EXPECTED_FLASH_WRITE_SIZE:
        raise StopExecution("direct ROM block size mismatch")

    id18.write_json(root / "direct_rom_mutation_attempt.json", {
        "primitive": "DIRECT_ESP32C6_ROM_OTADATA_SLOT_SWITCH_SINGLE_CONNECTION",
        "target_flash_offset": hex(plan.target_flash_offset),
        "entry_size": OTA_ENTRY_SIZE,
        "new_seq": plan.new_seq,
        "stock_high_level_write_flash_used": False,
        "flash_finish_used": False,
        "whole_image_retry": False,
        "automatic_rollback": False,
        "utc": id18.utc_now(),
    })

    with esp_cls(port, id18.BAUD) as esp:
        esp.connect(mode="no-reset", attempts=1)
        if getattr(esp, "sync_stub_detected", False) or getattr(esp, "IS_STUB", False):
            raise StopExecution("existing flasher stub detected; ROM-only mutation required")
        if getattr(esp, "secure_download_mode", False):
            raise StopExecution("unexpected secure download mode")
        if tuple(esp.read_mac("BASE_MAC")) != expected_mac:
            raise StopExecution("mutation-time ROM identity mismatch")
        attach_flash(esp)
        esp.flash_set_parameters(id18.FLASH_SIZE_BYTES)
        if str(esp.flash_md5sum(id18.APP0_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE)).lower() != app0_md5:
            raise StopExecution("mutation-time app0 freshness check failed")
        if str(esp.flash_md5sum(id18.APP1_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE)).lower() != app1_md5:
            raise StopExecution("mutation-time app1 freshness check failed")
        if str(esp.flash_md5sum(id18.OTADATA_OFFSET, id18.OTADATA_SIZE)).lower() != ota_md5:
            raise StopExecution("mutation-time otadata freshness check failed")

        id18.write_json(root / "direct_rom_mutation_boundary_entered.json", {
            "phase": "OTADATA_FLASH_BEGIN_ENTERING",
            "persistent_otadata_state_may_change_after_this_point": True,
            "target_flash_offset": hex(plan.target_flash_offset),
            "entry_size": OTA_ENTRY_SIZE,
            "utc": id18.utc_now(),
        })
        blocks = esp.flash_begin(OTA_ENTRY_SIZE, plan.target_flash_offset)
        if blocks != 1:
            raise StopExecution("direct ROM otadata flash_begin did not return one block")
        block = plan.entry_image + b"\xff" * (block_size - len(plan.entry_image))
        esp.flash_block(block, 0)
        observed = str(esp.flash_md5sum(id18.OTADATA_OFFSET, id18.OTADATA_SIZE)).lower()
        if observed != expected_post_md5:
            raise StopExecution("same-connection postchange otadata MD5 mismatch")
        id18.write_json(root / "direct_rom_mutation_completion.json", {
            "phase": "OTADATA_BLOCK_COMPLETED_AND_FULL_MD5_VERIFIED",
            "new_seq": plan.new_seq,
            "flash_finish_used": False,
            "whole_image_retry": False,
            "utc": id18.utc_now(),
        })


def evidence_manifest(root: Path) -> list[dict[str, Any]]:
    return id18.evidence_manifest(root)


def write_closure(root: Path, *, execution_id: str, package_commit: str,
                  authorization_id: str, result: str, failed: str | None,
                  stop_reason: str | None, target_access: bool | str,
                  prestate: dict[str, Any] | None, poststate: dict[str, Any] | None,
                  plan: SlotSwitchPlan | None, next_route: str) -> None:
    auth = json.loads((root / "authorization.json").read_text(encoding="utf-8"))
    id18.write_json(root / "closure.json", {
        "execution_id": execution_id,
        "execution_package_commit": package_commit,
        "authorization": authorization_id,
        "authorization_claimed": bool(auth.get("claimed")),
        "authorization_consumed": bool(auth.get("consumed")),
        "replay_permitted": False,
        "slot_switch_result": result,
        "first_failed_operation": failed,
        "stop_reason": stop_reason,
        "target_access_occurred": target_access,
        "mutation_boundary_entered": (root / "direct_rom_mutation_boundary_entered.json").is_file(),
        "mutation_completed_and_same_connection_md5_verified": (root / "direct_rom_mutation_completion.json").is_file(),
        "application_booted": False,
        "reset_after_switch": False,
        "app0_write_executed": False,
        "app1_write_executed": False,
        "stock_high_level_write_flash_used": False,
        "whole_image_mutation_retry": False,
        "automatic_rollback": False,
        "flash_finish_used": False,
        "prestate": prestate,
        "slot_switch_plan": plan.public_dict() if plan else None,
        "poststate": poststate,
        "next_route": next_route,
    })
    id18.write_json(root / "evidence_manifest.json", {
        "schema_version": 1,
        "execution_id": execution_id,
        "authorization": authorization_id,
        "files": evidence_manifest(root),
    })


def self_check() -> None:
    manifest = load_manifest()
    if manifest["predecessor"]["execution_package_commit"] != ID18_EXECUTION_PACKAGE_COMMIT:
        raise StopExecution("ID18 predecessor binding mismatch")
    if manifest["authority_references"]["schema5_app0_sha256"] != EXPECTED_APP0_SHA256:
        raise StopExecution("app0 Schema-v5 authority mismatch")
    if manifest["authority_references"]["rollback_app1_sha256"] != EXPECTED_APP1_SHA256:
        raise StopExecution("app1 rollback authority mismatch")
    if next_seq_for_slot(EXPECTED_ACTIVE_SEQ, TARGET_SLOT) != 5:
        raise StopExecution("frozen ID18->ID19 sequence transition mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--board-a-port")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0
    required = (args.expected_package_commit, args.authorization_id, args.execution_id, args.board_a_port, args.evidence_root)
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
    id18.write_authorization(root, args.authorization_id, args.execution_id, claimed=False)

    op_index = 1
    target_access: bool | str = False
    failed = "HOST_PREFLIGHT"
    prestate = None
    poststate = None
    plan = None
    next_route = "STOP_RETURN_TO_HIGH_LEVEL_MODEL"
    try:
        op_index = verify_host(root, repo_root, args.expected_package_commit)
        verify_port_locator(root, args.board_a_port)
        id18.write_authorization(root, args.authorization_id, args.execution_id, claimed=True)
        env = {"ESPTOOL_CFGFILE": str(cfg), "ESPTOOL_OPEN_PORT_ATTEMPTS": "1"}

        failed = "BOARD_A_READ_MAC"
        target_access = "UNKNOWN"
        identity = run_recorded(
            root=root, index=op_index, label="board_a_read_mac",
            argv=id18.build_read_mac_command(args.board_a_port), cwd=repo_root,
            target_operation=True, extra_env=env,
        )
        op_index += 1
        if identity.returncode != 0:
            raise StopExecution("board_a read-mac failed")
        target_access = True
        base_mac = id18.parse_base_mac(identity.stdout or "")
        if id18.mac_suffix(base_mac) != id18.EXPECTED_BOARD_A_SUFFIX:
            raise StopExecution("board_a identity suffix mismatch")
        board_dir = root / "board_a"
        id18.ensure_private_dir(board_dir)
        id18.write_json(board_dir / "identity_private.json", {
            "base_mac": base_mac,
            "base_mac_sha256": hashlib.sha256(base_mac.encode()).hexdigest(),
            "observed_suffix": id18.mac_suffix(base_mac),
            "identity_match": True,
        })

        captures = (
            ("pre_partition_table", id18.PARTITION_TABLE_OFFSET, id18.PARTITION_TABLE_SIZE),
            ("pre_otadata", id18.OTADATA_OFFSET, id18.OTADATA_SIZE),
            ("pre_app0_window", id18.APP0_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
            ("pre_app1_window", id18.APP1_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
        )
        paths: dict[str, Path] = {}
        for label, offset, size in captures:
            failed = f"BOARD_A_{label.upper()}_READ"
            out = board_dir / f"{label}.bin"
            paths[label] = out
            result = run_recorded(
                root=root, index=op_index, label=f"board_a_read_{label}",
                argv=id18.build_read_flash_command(args.board_a_port, offset, size, out),
                cwd=repo_root, target_operation=True, extra_env=env,
            )
            op_index += 1
            if result.returncode != 0:
                raise StopExecution(f"board_a {label} read failed")
            if not out.is_file() or out.stat().st_size != size:
                raise StopExecution(f"board_a {label} output size/path mismatch")
            os.chmod(out, 0o600)

        failed = "HOST_PREMUTATION_ADJUDICATION"
        id18.parse_partition_table(paths["pre_partition_table"].read_bytes())
        pre_otadata = paths["pre_otadata"].read_bytes()
        plan = plan_slot_switch(pre_otadata)
        app0_sha = id18.sha256_file(paths["pre_app0_window"])
        app1_sha = id18.sha256_file(paths["pre_app1_window"])
        if app0_sha != EXPECTED_APP0_SHA256:
            raise StopExecution("app0 exact Schema-v5 binding drifted from ID18")
        if app1_sha != EXPECTED_APP1_SHA256:
            raise StopExecution("app1 rollback payload binding drifted from ID18")
        prestate = {
            "selected_slot": EXPECTED_SELECTED_SLOT,
            "active_seq": EXPECTED_ACTIVE_SEQ,
            "active_state": EXPECTED_ACTIVE_STATE,
            "app0_window_sha256": app0_sha,
            "app1_window_sha256": app1_sha,
            "app0_exact_schema5": True,
            "app1_rollback_hash_exact": True,
        }
        id18.write_json(board_dir / "prestate_summary.json", prestate)
        id18.write_json(board_dir / "slot_switch_plan.json", plan.public_dict())

        failed = "BOARD_A_DIRECT_ROM_OTADATA_SLOT_SWITCH"
        runtime = id18.bind_direct_rom_runtime(cfg, root)
        direct_switch_once(
            runtime=runtime, root=root, port=args.board_a_port,
            expected_base_mac=base_mac, plan=plan, pre_otadata=pre_otadata,
            pre_app0=paths["pre_app0_window"], pre_app1=paths["pre_app1_window"],
        )

        post_paths: dict[str, Path] = {}
        for label, offset, size in (
            ("post_otadata", id18.OTADATA_OFFSET, id18.OTADATA_SIZE),
            ("post_app0_window", id18.APP0_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
            ("post_app1_window", id18.APP1_OFFSET, id18.SCHEMA5_FIRMWARE_SIZE),
        ):
            failed = f"BOARD_A_{label.upper()}_READ"
            out = board_dir / f"{label}.bin"
            post_paths[label] = out
            result = run_recorded(
                root=root, index=op_index, label=f"board_a_read_{label}",
                argv=id18.build_read_flash_command(args.board_a_port, offset, size, out),
                cwd=repo_root, target_operation=True, extra_env=env,
            )
            op_index += 1
            if result.returncode != 0:
                raise StopExecution(f"board_a {label} read failed")
            if not out.is_file() or out.stat().st_size != size:
                raise StopExecution(f"board_a {label} output size/path mismatch")
            os.chmod(out, 0o600)

        failed = "HOST_POSTMUTATION_VERIFICATION"
        poststate = verify_post_otadata(pre_otadata, post_paths["post_otadata"].read_bytes(), plan)
        app0_post = id18.sha256_file(post_paths["post_app0_window"])
        app1_post = id18.sha256_file(post_paths["post_app1_window"])
        if app0_post != EXPECTED_APP0_SHA256:
            raise StopExecution("app0 changed during slot switch")
        if app1_post != EXPECTED_APP1_SHA256:
            raise StopExecution("app1 changed during slot switch")
        poststate.update({
            "app0_window_sha256": app0_post,
            "app1_window_sha256": app1_post,
            "app0_exact_schema5_unchanged": True,
            "app1_hash_unchanged": True,
        })
        id18.write_json(board_dir / "poststate_summary.json", poststate)
        next_route = "PREPARE_BOARD_A_SCHEMA5_BOOT_POSTCHECK_PACKAGE"
        write_closure(
            root, execution_id=args.execution_id, package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id, result="PASS", failed=None,
            stop_reason=None, target_access=target_access, prestate=prestate,
            poststate=poststate, plan=plan, next_route=next_route,
        )
    except (StopExecution, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        write_closure(
            root, execution_id=args.execution_id, package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id, result="STOP", failed=failed,
            stop_reason=str(exc), target_access=target_access, prestate=prestate,
            poststate=poststate, plan=plan, next_route="STOP_RETURN_TO_HIGH_LEVEL_MODEL",
        )

    closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["slot_switch_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
