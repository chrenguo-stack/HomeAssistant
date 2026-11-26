#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

LIVE = Path("/opt/n3w-t1-core-updater/ha-recovery.pyz")
ROOT = Path("/var/lib/n3w-t1-core-updater")
TX_FILE = ROOT / "homeassistant-usb-upgrade.json"
PIN = ROOT / "ha-release-pin.json"
PREPARE_AUTH = ROOT / "ha-prepare-authority.json"
INSTALL_AUTH = ROOT / "ha-install-authority.json"
APPROVED = Path("/run/n3w/t1-ota/approved-homeassistant.json")

EXPECTED_TX = "86b2fb28429672f6bd27269a62549d774e50814e1e428d6a79a8de531eb0cea0"
EXPECTED_TX_FILE_SHA = "caa61863a031f6a91b7cf1d3762d5b73b42a49b9cdff797df14387a37f139306"
EXPECTED_PYZ = "807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2"
EXPECTED_MANIFEST = "5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36"
EXPECTED_PIN_SHA = "f05cf21d29808d855bbc41b2be8d5f4c5cbef6eea90de1cf0da3c2a668422a14"
EXPECTED_PREPARE_AUTH_SHA = "27e911ffa176ca8b7b6e7ca0c12cdd6f8d901f8487570d0e83f33d91c119aabf"
EXPECTED_OLD_INSTALL_AUTH_SHA = "50eda7d64dce2fe9de2196316c2acb7b63297f3e1aff1d927824a72a7f7742ca"
EXPECTED_INSTALL_BINDING = "ca6d2841ac6ca037fbf0d850a2431ca684e243b7c5cd9dac133bc718a4d1a46e"
EXPECTED_LAUNCH = "987189ccd61c0784db089b08e51a9ad3ff317372ad8a952dcda7a03a6d844c70"
EXPECTED_USB = "b72ac2fc-79a0-4fb8-888e-f35b0114f959"
EXPECTED_TARGET_REF = "local/n3w-homeassistant:2026.10.0-0c73235a"
EXPECTED_PREDECESSOR_REF = "local/n3w-homeassistant:2026.10.4-5881590f"
EXPECTED_MANAGER_REF = "local/greenhouse-manager:fresh-1cae18039eee"
EXPECTED_BROKER_REF = "local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_TARGET_SHA = "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663"
EXPECTED_TARGET_SIZE = 2448553472
EXPECTED_PREDECESSOR_SHA = "6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f"
EXPECTED_PREDECESSOR_SIZE = 2447090176

APPROVAL_ENV = "N3W_T1_R8V13_07_FRESH_TX_A_PIN_REFRESH_INSTALL_INTENT_APPROVED"
AUTH_ID = "N3W_T1_CORE_UPDATER_R8V13_07_FRESH_TX_A_PIN_REFRESH_INSTALL_INTENT_20261126_01"
RELEASE = "homeassistant-r8-predecessor-2026.10.0"
U4 = "U4_READY_TO_INSTALL"
U5 = "U5_INSTALL_REQUESTED_REVALIDATING"
PIN_FIELDS = {"schema", "manifest_sha256", "predecessor_image_id", "expires_at_unix"}
PIN_SIGNED_FIELDS = {"signed_index", "predecessor_binding_sha256"}


class GateError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()




def reject_duplicate_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result

def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def atomic_write(path: Path, payload: bytes) -> None:
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, 0, 0)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temporary.unlink(missing_ok=True)


def require_private_root_file(path: Path, expected_sha: str | None = None) -> bytes:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != 0
        or info.st_nlink != 1
    ):
        raise GateError(f"PRIVATE_FILE_METADATA_DRIFT:{path.name}")
    raw = path.read_bytes()
    if expected_sha is not None and sha256_bytes(raw) != expected_sha:
        raise GateError(f"PRIVATE_FILE_SHA_DRIFT:{path.name}")
    return raw


def require_transaction(document: dict[str, Any]) -> None:
    expected = {
        "transaction_id_sha256": EXPECTED_TX,
        "status": "ACTIVE",
        "phase": U4,
        "failure_code": None,
        "recovery_required": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "authorization_id_sha256": None,
        "usb_binding_mode": "existing_filesystem",
        "usb_filesystem_uuid": EXPECTED_USB,
        "current_image_ref": EXPECTED_PREDECESSOR_REF,
        "target_image_ref": EXPECTED_TARGET_REF,
        "target_artifact_verified": True,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise GateError(f"U4_TRANSACTION_DRIFT:{key}")
    if "predecessor_start" in document:
        raise GateError("U4_PREDECESSOR_START_PRESENT")
    materials = document.get("prepared_image_materials")
    if not isinstance(materials, dict):
        raise GateError("PREPARED_MATERIALS_MISSING")
    target = materials.get("target")
    predecessor = materials.get("predecessor")
    if not isinstance(target, dict) or not isinstance(predecessor, dict):
        raise GateError("PREPARED_MATERIALS_INVALID")
    target_tuple = (
        target.get("image_ref"), target.get("archive_sha256"),
        target.get("archive_size_bytes"), target.get("verified"), target.get("fsynced"),
    )
    predecessor_tuple = (
        predecessor.get("image_ref"), predecessor.get("archive_sha256"),
        predecessor.get("archive_size_bytes"), predecessor.get("verified"), predecessor.get("fsynced"),
    )
    if target_tuple != (
        EXPECTED_TARGET_REF, EXPECTED_TARGET_SHA, EXPECTED_TARGET_SIZE, True, True,
    ):
        raise GateError("TARGET_MATERIAL_DRIFT")
    if predecessor_tuple != (
        EXPECTED_PREDECESSOR_REF, EXPECTED_PREDECESSOR_SHA, EXPECTED_PREDECESSOR_SIZE, True, True,
    ):
        raise GateError("PREDECESSOR_MATERIAL_DRIFT")


def materials_signature(document: dict[str, Any]) -> tuple[Any, ...]:
    materials = document["prepared_image_materials"]
    return tuple(
        materials[k].get(field)
        for k in ("target", "predecessor")
        for field in ("image_ref", "archive_sha256", "archive_size_bytes", "verified", "fsynced")
    )


def restore_pin_if_still_u4(old_raw: bytes) -> bool:
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    current = HaUsbStateStore().read()
    if (
        current is not None
        and current.get("transaction_id_sha256") == EXPECTED_TX
        and current.get("status") == "ACTIVE"
        and current.get("phase") == U4
        and sha256_file(TX_FILE) == EXPECTED_TX_FILE_SHA
    ):
        atomic_write(PIN, old_raw)
        if sha256_file(PIN) != EXPECTED_PIN_SHA:
            raise GateError("EXPIRED_PIN_RESTORE_VERIFY_FAILED")
        print("EXPIRED_PIN_RESTORE=PASS")
        return True
    print("EXPIRED_PIN_RESTORE=NOT_ATTEMPTED_TRANSACTION_ADVANCED")
    return False


def main() -> int:
    if os.environ.get(APPROVAL_ENV) != "YES":
        raise GateError("EXPLICIT_PIN_REFRESH_INSTALL_INTENT_AUTHORIZATION_REQUIRED")
    if os.geteuid() != 0:
        raise GateError("ROOT_REQUIRED")
    if sha256_file(LIVE) != EXPECTED_PYZ:
        raise GateError("LIVE_PYZ_DRIFT")
    if str(LIVE) not in sys.path:
        sys.path.insert(0, str(LIVE))
    print("LIVE_RECOVERY_PYZ_IMPORT_PATH=PASS")
    if sha256_file(TX_FILE) != EXPECTED_TX_FILE_SHA:
        raise GateError("U4_TRANSACTION_FILE_SHA_DRIFT")
    if sha256_file(APPROVED) != EXPECTED_MANIFEST:
        raise GateError("APPROVED_MANIFEST_DRIFT")
    if sha256_file(PREPARE_AUTH) != EXPECTED_PREPARE_AUTH_SHA:
        raise GateError("PREPARE_AUTHORITY_DRIFT")
    old_install_raw = require_private_root_file(INSTALL_AUTH, EXPECTED_OLD_INSTALL_AUTH_SHA)
    old_install = json.loads(old_install_raw, object_pairs_hook=reject_duplicate_fields)
    now = int(time.time())
    if old_install.get("schema") != "gh.n3w-t1-ha-install-authority/3":
        raise GateError("OLD_INSTALL_AUTHORITY_SCHEMA_DRIFT")
    if type(old_install.get("expires_at_unix")) is not int or old_install["expires_at_unix"] > now:
        raise GateError("OLD_INSTALL_AUTHORITY_NOT_EXPIRED")
    if old_install.get("binding_sha256") == EXPECTED_INSTALL_BINDING:
        raise GateError("OLD_INSTALL_AUTHORITY_BINDING_COLLISION")

    old_pin_raw = require_private_root_file(PIN, EXPECTED_PIN_SHA)
    pin = json.loads(old_pin_raw, object_pairs_hook=reject_duplicate_fields)
    if (
        not isinstance(pin, dict)
        or (set(pin) != PIN_FIELDS and set(pin) != PIN_FIELDS | PIN_SIGNED_FIELDS)
        or pin.get("schema") != "gh.n3w-t1-ha-release-pin/1"
        or pin.get("manifest_sha256") != EXPECTED_MANIFEST
        or not isinstance(pin.get("predecessor_image_id"), str)
        or not pin["predecessor_image_id"].startswith("sha256:")
        or len(pin["predecessor_image_id"]) != 71
        or type(pin.get("expires_at_unix")) is not int
        or pin["expires_at_unix"] > now
    ):
        raise GateError("EXPIRED_RELEASE_PIN_NOT_EXACT")

    from n3w_t1_core_updater_ha_ipc import (
        HaUsbIpcExecutor,
        LocalApprovedHaRelease,
        candidate_admission,
        read_local_release_input,
    )
    from n3w_t1_core_updater_ha_recovery_startup import (
        LocalHaPredecessorRuntime,
        requested_install_binding_sha256,
    )
    from n3w_t1_core_updater_v2_common import TERMINAL_TX_V2, canonical
    from n3w_t1_core_updater_v2_state import V2StateStore
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    document = HaUsbStateStore().read()
    if document is None:
        raise GateError("TRANSACTION_MISSING")
    require_transaction(document)
    if sha256_file(TX_FILE) != EXPECTED_TX_FILE_SHA:
        raise GateError("U4_TRANSACTION_FILE_SHA_DRIFT")

    runtime = LocalHaPredecessorRuntime()
    binding = runtime.capture_start_binding(document)
    if binding.get("launch_sha256") != EXPECTED_LAUNCH:
        raise GateError("CURRENT_LAUNCH_SHA_DRIFT")
    for name, ref in (
        ("homeassistant", EXPECTED_PREDECESSOR_REF),
        ("manager", EXPECTED_MANAGER_REF),
        ("broker", EXPECTED_BROKER_REF),
    ):
        if binding["images"][name]["reference"] != ref:
            raise GateError(f"RUNTIME_IMAGE_REF_DRIFT:{name}")
    if requested_install_binding_sha256(document) != EXPECTED_INSTALL_BINDING:
        raise GateError("INSTALL_BINDING_DRIFT")

    usb_mount = runtime._original_mountpoint(EXPECTED_USB)
    if not usb_mount.is_mount():
        raise GateError("ORIGINAL_USB_MOUNT_NOT_ACTIVE")
    usb_space = os.statvfs(usb_mount)
    if usb_space.f_frsize <= 0:
        raise GateError("ORIGINAL_USB_CAPACITY_UNAVAILABLE")
    usb_available_bytes = usb_space.f_bavail * usb_space.f_frsize
    if usb_available_bytes <= 0:
        raise GateError("ORIGINAL_USB_HAS_NO_AVAILABLE_SPACE")

    current = runtime._runtime("homeassistant")
    if current.get("image_ref") != EXPECTED_PREDECESSOR_REF:
        raise GateError("CURRENT_HA_IMAGE_REF_DRIFT")
    if pin["predecessor_image_id"] != current.get("image_id"):
        raise GateError("PIN_PREDECESSOR_IMAGE_ID_DRIFT")

    manifest_raw = read_local_release_input(APPROVED, limit=32768, private=False)
    admission = candidate_admission(manifest_raw, current)
    if (
        admission.release_identity != RELEASE
        or admission.current_image_ref != EXPECTED_PREDECESSOR_REF
        or admission.target_image_ref != EXPECTED_TARGET_REF
        or admission.target_archive_sha256 != EXPECTED_TARGET_SHA
        or admission.target_archive_size != EXPECTED_TARGET_SIZE
    ):
        raise GateError("APPROVED_RELEASE_ADMISSION_DRIFT")
    HaUsbIpcExecutor.require_same_admission(document, admission)

    if subprocess.run(
        ["docker", "image", "inspect", EXPECTED_TARGET_REF],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0:
        raise GateError("TARGET_IMAGE_ALREADY_PRESENT")

    evidence = runtime.acceptance_observer().run_monitoring_self_test()
    if evidence.verdict != "PASS":
        raise GateError("PREINSTALL_MONITORING_SELF_TEST_FAILED")

    print("PHASE=EXPIRED_RELEASE_PIN_EXACT_REBIND")
    print("U4_TRANSACTION=PASS")
    print("TX_FILE_SHA256=" + EXPECTED_TX_FILE_SHA)
    print("OLD_RELEASE_PIN_SHA256=" + EXPECTED_PIN_SHA)
    print("PIN_SCHEMA=PASS")
    print("PIN_MANIFEST_BINDING=PASS")
    print("PIN_PREDECESSOR_RUNTIME_BINDING=PASS")
    print("CURRENT_LAUNCH_SHA256=" + binding["launch_sha256"])
    print("INSTALL_BINDING_SHA256=" + EXPECTED_INSTALL_BINDING)
    print("USB_MOUNT=" + str(usb_mount))
    print("USB_AVAILABLE_BYTES=" + str(usb_available_bytes))
    print("MANAGER_BROKER_HA_SELF_TEST=PASS")
    print("MANAGER_BROKER_HA_SELF_TEST_SHA256=" + evidence.sha256)
    print("OLD_INSTALL_AUTHORITY_RESIDUE=EXPIRED_SAFE_REPLACEABLE")
    print("TARGET_10_0_PRESENT_BEFORE_INTENT=false")

    store = V2StateStore()
    with store.lock():
        manager_tx = store.read()
        legacy_tx = store.read_legacy()
        if manager_tx is not None and manager_tx.get("status") not in TERMINAL_TX_V2:
            raise GateError("MANAGER_V2_TRANSACTION_ACTIVE")
        if legacy_tx is not None and legacy_tx.get("status") not in {"COMMITTED", "ROLLED_BACK"}:
            raise GateError("LEGACY_MANAGER_TRANSACTION_ACTIVE")
        guard = store.read_ha_usb_guard()
        if guard != document:
            raise GateError("HA_USB_GUARD_TRANSACTION_DRIFT")
        if sha256_file(TX_FILE) != EXPECTED_TX_FILE_SHA:
            raise GateError("U4_TRANSACTION_CHANGED_BEFORE_PIN_REFRESH")
        if sha256_file(PIN) != EXPECTED_PIN_SHA:
            raise GateError("RELEASE_PIN_CHANGED_BEFORE_REFRESH")
        current_binding = runtime.capture_start_binding(document)
        if current_binding.get("launch_sha256") != EXPECTED_LAUNCH:
            raise GateError("RUNTIME_CHANGED_BEFORE_PIN_REFRESH")

        refreshed = dict(pin)
        refreshed_expiry = int(time.time()) + 21600
        refreshed["expires_at_unix"] = refreshed_expiry
        atomic_write(PIN, canonical(refreshed))

    refreshed_pin_sha = sha256_file(PIN)
    refreshed_pin = read_json(PIN)
    if (
        refreshed_pin.get("schema") != pin["schema"]
        or refreshed_pin.get("manifest_sha256") != pin["manifest_sha256"]
        or refreshed_pin.get("predecessor_image_id") != pin["predecessor_image_id"]
        or refreshed_pin.get("expires_at_unix") != refreshed_expiry
        or {k: v for k, v in refreshed_pin.items() if k != "expires_at_unix"}
        != {k: v for k, v in pin.items() if k != "expires_at_unix"}
        or refreshed_pin["expires_at_unix"] <= time.time()
    ):
        restore_pin_if_still_u4(old_pin_raw)
        raise GateError("RELEASE_PIN_REFRESH_POSTCHECK_FAILED")

    try:
        resolver = LocalApprovedHaRelease(
            PIN, APPROVED, lambda: LocalHaPredecessorRuntime()._runtime("homeassistant"),
        )
        refreshed_admission = resolver.resolve_homeassistant_release(RELEASE)
        HaUsbIpcExecutor.require_same_admission(document, refreshed_admission)
    except Exception:
        restore_pin_if_still_u4(old_pin_raw)
        raise

    print("RELEASE_PIN_REFRESH=PASS")
    print("REFRESHED_PIN_SHA256=" + refreshed_pin_sha)
    print("REFRESHED_PIN_EXPIRES_AT_UNIX=" + str(refreshed_expiry))
    print("PIN_RELEASE_BINDINGS_UNCHANGED=true")

    result = subprocess.run(
        [
            "/usr/bin/python3", "-I", str(LIVE),
            "--maintenance-submit-approved-release", "INSTALL",
            "--release-identity", RELEASE,
        ],
        capture_output=True, text=True, check=False,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        restored = restore_pin_if_still_u4(old_pin_raw)
        print("INSTALL_INTENT_RETURN_CODE=" + str(result.returncode))
        print("INSTALL_INTENT_SUBMIT=FAIL")
        print("PIN_RESTORED_TO_EXACT_PREIMAGE=" + str(restored).lower())
        raise GateError("INSTALL_INTENT_SUBMIT_FAILED")

    after = HaUsbStateStore().read()
    if (
        after is None
        or after.get("transaction_id_sha256") != EXPECTED_TX
        or after.get("status") != "ACTIVE"
        or after.get("phase") != U5
        or after.get("failure_code") is not None
        or after.get("recovery_required") is not False
        or after.get("authorization_claimed") is not False
        or after.get("authorization_consumed") is not False
        or after.get("authorization_id_sha256") is not None
        or "predecessor_start" in after
        or materials_signature(after) != materials_signature(document)
    ):
        print("INSTALL_INTENT_RETURN_CODE=0")
        print("INSTALL_INTENT_POSTCHECK=STOP")
        print("DO_NOT_REPLAY_INSTALL_INTENT=true")
        raise GateError("U5_INSTALL_INTENT_POSTCHECK_FAILED")

    if sha256_file(INSTALL_AUTH) != EXPECTED_OLD_INSTALL_AUTH_SHA:
        raise GateError("INSTALL_AUTHORITY_CHANGED_BEFORE_AUTHORITY_GATE")
    if sha256_file(PIN) != refreshed_pin_sha:
        raise GateError("REFRESHED_PIN_CHANGED_AFTER_INSTALL_INTENT")

    after_binding = runtime.capture_start_binding(after)
    if after_binding.get("launch_sha256") != EXPECTED_LAUNCH:
        raise GateError("RUNTIME_LAUNCH_CHANGED_AFTER_INSTALL_INTENT")
    after_evidence = runtime.acceptance_observer().run_monitoring_self_test()
    if after_evidence.verdict != "PASS":
        raise GateError("POST_INTENT_MONITORING_SELF_TEST_FAILED")

    if subprocess.run(
        ["docker", "image", "inspect", EXPECTED_TARGET_REF],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0:
        raise GateError("TARGET_IMAGE_LOADED_DURING_INSTALL_INTENT")

    print("INSTALL_INTENT_RETURN_CODE=0")
    print("TRANSACTION_STATUS=" + after["status"])
    print("TRANSACTION_PHASE=" + after["phase"])
    print("TRANSACTION_ID_SHA256=" + after["transaction_id_sha256"])
    print("TRANSACTION_FILE_SHA256=" + sha256_file(TX_FILE))
    print("PREPARED_IMAGE_MATERIALS_UNCHANGED=true")
    print("AUTHORIZATION_CLAIMED=false")
    print("AUTHORIZATION_CONSUMED=false")
    print("INSTALL_AUTHORITY_ISSUED=false")
    print("INSTALL_AUTHORITY_RESIDUE_SHA256=" + EXPECTED_OLD_INSTALL_AUTH_SHA)
    print("TARGET_IMAGE_LOADED=false")
    print("HA_MANAGER_BROKER_HEALTH=PASS")
    print("POST_INTENT_SELF_TEST_SHA256=" + after_evidence.sha256)
    print("PRODUCT_WORKER_DISPATCH=false")
    print("U6_PLUS=false")
    print("RELEASE_PIN_REFRESH_AND_U5_INTENT=PASS")
    print("NEXT_BOUNDARY=EXACT_U5_INSTALL_AUTHORITY_AND_PRODUCT_WORKER")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("PIN_REFRESH_INSTALL_INTENT_RESULT=STOP")
        print("STOP_REASON=" + str(error))
        print("R8V13_07_RESULT=NOT_PASS_YET")
        print("R8V13_08_BLOCKED=true")
        print("REPLAY_DECISION=READ_DURABLE_STATE_FIRST")
        raise SystemExit(1)
