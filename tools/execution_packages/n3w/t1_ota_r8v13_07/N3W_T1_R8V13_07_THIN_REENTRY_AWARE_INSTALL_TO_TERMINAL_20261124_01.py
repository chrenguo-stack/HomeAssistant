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
INSTALL_AUTH = ROOT / "ha-install-authority.json"
PIN = ROOT / "ha-release-pin.json"
APPROVED = Path("/run/n3w/t1-ota/approved-homeassistant.json")

EXPECTED_TX = "d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4"
EXPECTED_PYZ = "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a"
EXPECTED_MANIFEST = "5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36"
EXPECTED_USB = "b72ac2fc-79a0-4fb8-888e-f35b0114f959"
EXPECTED_TARGET_REF = "local/n3w-homeassistant:2026.10.0-0c73235a"
EXPECTED_PREDECESSOR_REF = "local/n3w-homeassistant:2026.10.4-5881590f"
EXPECTED_MANAGER_REF = "local/greenhouse-manager:fresh-1cae18039eee"
EXPECTED_BROKER_REF = "local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_TARGET_SHA = "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663"
EXPECTED_TARGET_SIZE = 2448553472
EXPECTED_PREDECESSOR_SHA = "6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f"
EXPECTED_PREDECESSOR_SIZE = 2447090176
RELEASE = "homeassistant-r8-predecessor-2026.10.0"
AUTH_ID = "N3W_T1_CORE_UPDATER_R8V13_07_FRESH_TX_A_INSTALL_CUTOVER_20261124_01"
RECOVERY_UNIT = "n3w-t1-ha-recovery-retry.service"

U4 = "U4_READY_TO_INSTALL"
U5 = "U5_INSTALL_REQUESTED_REVALIDATING"
U6 = "U6_PREDECESSOR_RECOVERY_PREPARING"
U7 = "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
U8 = "U8_RECOVERY_ADMISSION_COMPLETE"
U9 = "U9_LIVE_AUTHORIZATION_CLAIMED"
U10 = "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
U11 = "U11_TARGET_INSTALLED_STARTED"
U12 = "U12_TARGET_ACCEPTANCE"
U13A = "U13A_COMMITTED"
U13B = "U13B_ROLLED_BACK"
PRE_CUTOVER_PHASES = {U6, U7, U8}
POST_AUTH_PHASES = {U9, U10, U11, U12}
PRE_CUTOVER_TERMINAL_FAILURES = {
    "ha_usb_predecessor_acceptance_baseline_unavailable",
    "ha_usb_install_revalidation_failed",
}


class GateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def atomic_private_json(path: Path, value: dict[str, Any]) -> None:
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(raw)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temp.unlink(missing_ok=True)


def validate_exact_transaction(document: dict[str, Any]) -> None:
    if document.get("transaction_id_sha256") != EXPECTED_TX:
        raise GateError("TRANSACTION_ID_DRIFT")
    if document.get("usb_binding_mode") != "existing_filesystem":
        raise GateError("USB_BINDING_MODE_DRIFT")
    if document.get("usb_filesystem_uuid") != EXPECTED_USB:
        raise GateError("USB_UUID_DRIFT")
    if document.get("current_image_ref") != EXPECTED_PREDECESSOR_REF:
        raise GateError("PREDECESSOR_REF_DRIFT")
    if document.get("target_image_ref") != EXPECTED_TARGET_REF:
        raise GateError("TARGET_REF_DRIFT")
    if document.get("target_artifact_verified") is not True:
        raise GateError("TARGET_ARTIFACT_NOT_VERIFIED")
    materials = document.get("prepared_image_materials")
    if not isinstance(materials, dict):
        raise GateError("PREPARED_MATERIALS_MISSING")
    target = materials.get("target")
    predecessor = materials.get("predecessor")
    if not isinstance(target, dict) or not isinstance(predecessor, dict):
        raise GateError("PREPARED_MATERIALS_INVALID")
    target_tuple = (
        target.get("image_ref"),
        target.get("archive_sha256"),
        target.get("archive_size_bytes"),
        target.get("verified"),
        target.get("fsynced"),
    )
    predecessor_tuple = (
        predecessor.get("image_ref"),
        predecessor.get("archive_sha256"),
        predecessor.get("archive_size_bytes"),
        predecessor.get("verified"),
        predecessor.get("fsynced"),
    )
    if target_tuple != (
        EXPECTED_TARGET_REF,
        EXPECTED_TARGET_SHA,
        EXPECTED_TARGET_SIZE,
        True,
        True,
    ):
        raise GateError("TARGET_MATERIAL_DRIFT")
    if predecessor_tuple != (
        EXPECTED_PREDECESSOR_REF,
        EXPECTED_PREDECESSOR_SHA,
        EXPECTED_PREDECESSOR_SIZE,
        True,
        True,
    ):
        raise GateError("PREDECESSOR_MATERIAL_DRIFT")


def classify(document: dict[str, Any]) -> str:
    validate_exact_transaction(document)
    status = document.get("status")
    phase = document.get("phase")
    recovery = document.get("recovery_required")
    has_start = "predecessor_start" in document

    if status == "COMMITTED" and phase == U13A:
        return "committed"

    if status == "ROLLED_BACK":
        if phase == U13B:
            return "rolled_back"
        if document.get("pre_cutover_predecessor_restored") is True and phase in PRE_CUTOVER_PHASES:
            return "rolled_back_pre_cutover"
        if (
            phase == U4
            and not has_start
            and recovery is False
            and document.get("failure_code") in PRE_CUTOVER_TERMINAL_FAILURES
        ):
            return "rolled_back_pre_cutover"
        raise GateError("ROLLED_BACK_STATE_INVALID")

    if status != "ACTIVE":
        raise GateError("NONACTIVE_NONTERMINAL_STATE")

    if phase == U4:
        if (
            recovery is not False
            or has_start
            or document.get("authorization_claimed") is not False
            or document.get("authorization_consumed") is not False
            or document.get("authorization_id_sha256") is not None
        ):
            raise GateError("U4_STATE_INVALID")
        if document.get("failure_code") in PRE_CUTOVER_TERMINAL_FAILURES:
            return "precutover_failure"
        if document.get("failure_code") is not None:
            raise GateError("U4_FAILURE_UNCLASSIFIED")
        return "u4"

    if phase in {U5, U6} and not has_start and recovery is False:
        if (
            document.get("authorization_claimed") is not False
            or document.get("authorization_consumed") is not False
            or document.get("authorization_id_sha256") is not None
        ):
            raise GateError("PREDESTRUCTIVE_AUTHORIZATION_STATE_INVALID")
        return "predestructive"

    if phase in PRE_CUTOVER_PHASES and has_start:
        return "recovery"

    if phase in POST_AUTH_PHASES:
        return "recovery"

    raise GateError("ACTIVE_STATE_NOT_ADMITTED")


def summarize(document: dict[str, Any]) -> None:
    keys = (
        "transaction_id_sha256",
        "status",
        "phase",
        "failure_code",
        "recovery_required",
        "authorization_claimed",
        "authorization_consumed",
        "authorization_id_sha256",
        "pre_cutover_predecessor_restored",
        "predecessor_release_observed",
        "target_loaded_image_id",
        "target_activation",
    )
    for key in keys:
        print(f"{key.upper()}={json.dumps(document.get(key), separators=(',', ':'))}")
    print("PREDECESSOR_START_PRESENT=" + str("predecessor_start" in document).lower())
    print("TARGET_ACCEPTANCE_PRESENT=" + str("target_acceptance" in document).lower())


def install_authority_reusable(
    existing: dict[str, Any] | None,
    *,
    binding_sha256: str,
    launch_sha256: str,
    now: float,
) -> bool:
    if existing is None:
        return False
    return (
        set(existing)
        == {"schema", "binding_sha256", "authorization_id", "launch_sha256", "expires_at_unix"}
        and existing.get("schema") == "gh.n3w-t1-ha-install-authority/3"
        and existing.get("binding_sha256") == binding_sha256
        and existing.get("authorization_id") == AUTH_ID
        and existing.get("launch_sha256") == launch_sha256
        and type(existing.get("expires_at_unix")) is int
        and existing["expires_at_unix"] > now
    )


def validate_committed_document(document: dict[str, Any]) -> None:
    if document.get("authorization_claimed") is not True:
        raise GateError("COMMIT_AUTHORIZATION_NOT_CLAIMED")
    if document.get("authorization_consumed") is not True:
        raise GateError("COMMIT_AUTHORIZATION_NOT_CONSUMED")
    if document.get("authorization_id_sha256") != hashlib.sha256(AUTH_ID.encode()).hexdigest():
        raise GateError("COMMIT_AUTHORIZATION_ID_DRIFT")
    if document.get("recovery_required") is not False:
        raise GateError("COMMIT_RECOVERY_FLAG_INVALID")
    if document.get("target_activation") != "WRITES_POSSIBLE":
        raise GateError("COMMIT_TARGET_ACTIVATION_INVALID")
    receipt = document.get("target_acceptance", {}).get("receipt")
    if not isinstance(receipt, dict):
        raise GateError("COMMIT_ACCEPTANCE_MISSING")
    observations = receipt.get("observations")
    if not isinstance(observations, dict) or set(observations) != {"monitoring_path", "protected_data"}:
        raise GateError("COMMIT_ACCEPTANCE_OBSERVATIONS_INVALID")
    if not all(isinstance(value, str) and len(value) == 64 for value in observations.values()):
        raise GateError("COMMIT_ACCEPTANCE_OBSERVATION_HASH_INVALID")
    if receipt.get("images", {}).get("homeassistant", {}).get("reference") != EXPECTED_TARGET_REF:
        raise GateError("COMMIT_ACCEPTANCE_TARGET_REF_DRIFT")
    if receipt.get("images", {}).get("homeassistant", {}).get("runtime_id") != document.get("target_loaded_image_id"):
        raise GateError("COMMIT_ACCEPTANCE_RUNTIME_ID_DRIFT")


class RealOps:
    def __init__(self) -> None:
        if str(LIVE) not in sys.path:
            sys.path.insert(0, str(LIVE))

    def preflight_static(self) -> None:
        print("PHASE=STATIC_BINDING")
        if os.geteuid() != 0:
            raise GateError("ROOT_REQUIRED")
        if sha256_file(LIVE) != EXPECTED_PYZ:
            raise GateError("LIVE_PYZ_DRIFT")
        print("STATIC_BINDING=PASS")

    def read_transaction(self) -> dict[str, Any]:
        from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

        document = HaUsbStateStore().read()
        if document is None:
            raise GateError("TRANSACTION_MISSING")
        return document

    def validate_runtime_binding(self, document: dict[str, Any]) -> str:
        print("PHASE=PRODUCT_RUNTIME_REBIND")
        from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

        runtime = LocalHaPredecessorRuntime()
        binding = runtime.capture_start_binding(document)
        if binding["images"]["homeassistant"]["reference"] != EXPECTED_PREDECESSOR_REF:
            raise GateError("RUNTIME_HA_REF_DRIFT")
        if binding["images"]["manager"]["reference"] != EXPECTED_MANAGER_REF:
            raise GateError("RUNTIME_MANAGER_REF_DRIFT")
        if binding["images"]["broker"]["reference"] != EXPECTED_BROKER_REF:
            raise GateError("RUNTIME_BROKER_REF_DRIFT")
        print("PRODUCT_RUNTIME_REBIND=PASS")
        print("CURRENT_LAUNCH_SHA256=" + binding["launch_sha256"])
        return binding["launch_sha256"]

    def ensure_release_pin(self) -> None:
        print("PHASE=RELEASE_PIN")
        from n3w_t1_core_updater_ha_ipc import (
            LocalApprovedHaRelease,
            RELEASE_PIN_SCHEMA,
            SIGNED_INDEX_STATE,
            read_local_release_input,
            read_signed_index,
            valid_signed_index,
        )
        from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
        from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error

        def resolver() -> LocalApprovedHaRelease:
            return LocalApprovedHaRelease(
                PIN,
                APPROVED,
                lambda: LocalHaPredecessorRuntime()._runtime("homeassistant"),
            )

        try:
            admission = resolver().resolve_homeassistant_release(RELEASE)
            if admission.release_identity != RELEASE:
                raise GateError("RELEASE_ADMISSION_DRIFT")
            print("RELEASE_PIN_REFRESH=NOT_REQUIRED")
            print("RELEASE_ADMISSION=PASS")
            return
        except UpdaterV2Error as error:
            if str(error) != "ha_ota_ipc_release_pin_invalid":
                raise

        metadata = PIN.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()
            or metadata.st_nlink != 1
        ):
            raise GateError("RELEASE_PIN_METADATA_INVALID")

        pin = json.loads(read_local_release_input(PIN, limit=4096, private=True))
        base = {"schema", "manifest_sha256", "predecessor_image_id", "expires_at_unix"}
        signed = {"signed_index", "predecessor_binding_sha256"}
        if not isinstance(pin, dict) or set(pin) not in (base, base | signed):
            raise GateError("RELEASE_PIN_FIELDS_INVALID")
        if pin.get("schema") != RELEASE_PIN_SCHEMA:
            raise GateError("RELEASE_PIN_SCHEMA_DRIFT")
        if pin.get("manifest_sha256") != EXPECTED_MANIFEST:
            raise GateError("RELEASE_PIN_MANIFEST_DRIFT")
        if sha256_file(APPROVED) != EXPECTED_MANIFEST:
            raise GateError("APPROVED_MANIFEST_DRIFT")
        current = LocalHaPredecessorRuntime()._runtime("homeassistant")
        if pin.get("predecessor_image_id") != current.get("image_id"):
            raise GateError("RELEASE_PIN_PREDECESSOR_DRIFT")
        if "signed_index" in pin:
            if not valid_signed_index(pin["signed_index"]):
                raise GateError("RELEASE_PIN_SIGNED_INDEX_INVALID")
            if pin["signed_index"] != read_signed_index(PIN.with_name(SIGNED_INDEX_STATE)):
                raise GateError("RELEASE_PIN_SIGNED_INDEX_DRIFT")
            binding = pin.get("predecessor_binding_sha256")
            if not isinstance(binding, str) or SHA256.fullmatch(binding) is None:
                raise GateError("RELEASE_PIN_PREDECESSOR_BINDING_INVALID")
        expiry = pin.get("expires_at_unix")
        if type(expiry) is not int:
            raise GateError("RELEASE_PIN_EXPIRY_INVALID")
        now = int(time.time())
        if expiry > now:
            raise GateError("RELEASE_PIN_INVALID_FOR_NONEXPIRY_REASON")

        pin["expires_at_unix"] = now + 21600
        atomic_private_json(PIN, pin)
        admission = resolver().resolve_homeassistant_release(RELEASE)
        if admission.release_identity != RELEASE:
            raise GateError("RELEASE_ADMISSION_DRIFT")
        print("RELEASE_PIN_REFRESH=PASS")
        print("RELEASE_PIN_SHA256=" + sha256_file(PIN))
        print("RELEASE_ADMISSION=PASS")

    def submit_install(self) -> None:
        print("PHASE=SUBMIT_INSTALL_INTENT")
        result = subprocess.run(
            [
                "/usr/bin/python3",
                "-I",
                str(LIVE),
                "--maintenance-submit-approved-release",
                "INSTALL",
                "--release-identity",
                RELEASE,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        if result.returncode != 0:
            raise GateError("INSTALL_INTENT_SUBMIT_FAILED")
        print("INSTALL_INTENT_SUBMIT=PASS")

    def ensure_install_authority(self, document: dict[str, Any], launch_sha256: str) -> None:
        print("PHASE=INSTALL_AUTHORITY")
        from n3w_t1_core_updater_ha_recovery_startup import requested_install_binding_sha256

        binding = requested_install_binding_sha256(document)
        reusable = False
        try:
            existing = read_json(INSTALL_AUTH)
        except FileNotFoundError:
            existing = None
        reusable = install_authority_reusable(
            existing,
            binding_sha256=binding,
            launch_sha256=launch_sha256,
            now=time.time(),
        )
        if reusable:
            print("INSTALL_AUTHORITY=REUSED_CURRENT_BINDING")
            return

        request = {
            "transaction_id_sha256": document["transaction_id_sha256"],
            "expires_at_unix": int(time.time()) + 21600,
            "binding_sha256": binding,
            "authorization_id": AUTH_ID,
        }
        with tempfile.TemporaryDirectory(
            prefix="n3w-r8v13-07-install-authority-",
            dir="/tmp",
        ) as work:
            path = Path(work) / "request.json"
            atomic_private_json(path, request)
            result = subprocess.run(
                ["/usr/bin/python3", "-I", str(LIVE), "--issue-install-authority", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip(), file=sys.stderr)
            if result.returncode != 0:
                raise GateError("INSTALL_AUTHORITY_ISSUE_FAILED")

        grant = read_json(INSTALL_AUTH)
        if (
            set(grant)
            != {"schema", "binding_sha256", "authorization_id", "launch_sha256", "expires_at_unix"}
            or grant.get("schema") != "gh.n3w-t1-ha-install-authority/3"
            or grant.get("binding_sha256") != binding
            or grant.get("authorization_id") != AUTH_ID
            or grant.get("launch_sha256") != launch_sha256
            or type(grant.get("expires_at_unix")) is not int
            or grant["expires_at_unix"] <= time.time()
        ):
            raise GateError("INSTALL_AUTHORITY_POSTCHECK_FAILED")
        print("INSTALL_AUTHORITY=ISSUED")
        print("INSTALL_AUTHORITY_SHA256=" + sha256_file(INSTALL_AUTH))

    def start_worker(self, attempt: int) -> int:
        print(f"PHASE=PRODUCT_WORKER_DISPATCH_{attempt}")
        from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

        LocalHaPredecessorRuntime().require_recovery_install()
        result = subprocess.run(
            ["systemctl", "start", RECOVERY_UNIT],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        print(f"PRODUCT_WORKER_RC_{attempt}={result.returncode}")
        return result.returncode

    def verify_committed(self, document: dict[str, Any]) -> None:
        from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

        validate_committed_document(document)

        runtime = LocalHaPredecessorRuntime()
        ha = runtime._runtime("homeassistant")
        manager = runtime._runtime("manager")
        broker = runtime._runtime("broker")
        if (
            ha["image_ref"] != EXPECTED_TARGET_REF
            or ha["image_id"] != document.get("target_loaded_image_id")
            or ha["restart_count"] != 0
        ):
            raise GateError("POST_COMMIT_HA_RUNTIME_DRIFT")
        if manager["image_ref"] != EXPECTED_MANAGER_REF or manager["restart_count"] != 0:
            raise GateError("POST_COMMIT_MANAGER_RUNTIME_DRIFT")
        if broker["image_ref"] != EXPECTED_BROKER_REF or broker["restart_count"] != 0:
            raise GateError("POST_COMMIT_BROKER_RUNTIME_DRIFT")
        print("POST_COMMIT_RUNTIME=PASS")
        print("TARGET_ACCEPTANCE_RECEIPT=PASS")

    def verify_rolled_back(self, document: dict[str, Any]) -> None:
        from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

        runtime = LocalHaPredecessorRuntime()
        ha = runtime._runtime("homeassistant")
        manager = runtime._runtime("manager")
        broker = runtime._runtime("broker")
        if ha["image_ref"] != EXPECTED_PREDECESSOR_REF:
            raise GateError("ROLLBACK_HA_RUNTIME_DRIFT")
        if manager["image_ref"] != EXPECTED_MANAGER_REF:
            raise GateError("ROLLBACK_MANAGER_RUNTIME_DRIFT")
        if broker["image_ref"] != EXPECTED_BROKER_REF:
            raise GateError("ROLLBACK_BROKER_RUNTIME_DRIFT")
        print("ROLLBACK_RUNTIME_HEALTH=PASS")


def worker_reentry_admitted(document: dict[str, Any]) -> bool:
    if document.get("status") != "ACTIVE":
        return False
    phase = document.get("phase")
    return (
        phase in {U5, U6}
        or document.get("recovery_required") is True
        or "predecessor_start" in document
        or phase in POST_AUTH_PHASES
    )


def finish_terminal(ops: Any, document: dict[str, Any], state: str) -> int:
    print("PHASE=FINAL_DURABLE_CLASSIFICATION")
    summarize(document)
    if state == "committed":
        ops.verify_committed(document)
        print("FRESH_TX_A_INSTALL_RESULT=PASS")
        print("R8V13_07_RESULT=PASS")
        print("R8V13_07_TERMINAL=U13A_COMMITTED")
        print("NEXT_BOUNDARY=STOP_BEFORE_R8V13_08")
        return 0
    if state in {"rolled_back", "rolled_back_pre_cutover"}:
        ops.verify_rolled_back(document)
        print("FRESH_TX_A_INSTALL_RESULT=ROLLED_BACK")
        print("R8V13_07_RESULT=NOT_PASS")
        print("R8V13_08_BLOCKED=true")
        print("DO_NOT_REPLAY=true")
        return 2
    raise GateError("TERMINAL_CLASSIFICATION_INVALID")


def execute(ops: Any) -> int:
    ops.preflight_static()
    document = ops.read_transaction()
    state = classify(document)
    print("ENTRY_STATE=" + state)
    summarize(document)

    if state in {"committed", "rolled_back", "rolled_back_pre_cutover"}:
        return finish_terminal(ops, document, state)

    if state == "precutover_failure":
        print("FRESH_TX_A_INSTALL_RESULT=SAFE_PRECUTOVER_FAILURE")
        print("R8V13_07_RESULT=NOT_PASS")
        print("R8V13_08_BLOCKED=true")
        print("NEXT_ACTION=REVIEW_PRECUTOVER_FAILURE_NO_REPLAY")
        return 3

    if state in {"u4", "predestructive"}:
        launch_sha256 = ops.validate_runtime_binding(document)
        ops.ensure_release_pin()
        if state == "u4":
            ops.submit_install()
            document = ops.read_transaction()
            state = classify(document)
            if state != "predestructive":
                raise GateError("INSTALL_INTENT_DID_NOT_REACH_PREDESTRUCTIVE_STATE")
        ops.ensure_install_authority(document, launch_sha256)

    ops.start_worker(1)
    document = ops.read_transaction()
    state = classify(document)
    if state in {"committed", "rolled_back", "rolled_back_pre_cutover"}:
        return finish_terminal(ops, document, state)
    if state == "precutover_failure":
        print("FRESH_TX_A_INSTALL_RESULT=SAFE_PRECUTOVER_FAILURE")
        print("R8V13_07_RESULT=NOT_PASS")
        print("R8V13_08_BLOCKED=true")
        print("NEXT_ACTION=REVIEW_PRECUTOVER_FAILURE_NO_REPLAY")
        return 3

    if worker_reentry_admitted(document):
        ops.start_worker(2)
        document = ops.read_transaction()
        state = classify(document)
        if state in {"committed", "rolled_back", "rolled_back_pre_cutover"}:
            return finish_terminal(ops, document, state)
        if state == "precutover_failure":
            print("FRESH_TX_A_INSTALL_RESULT=SAFE_PRECUTOVER_FAILURE")
            print("R8V13_07_RESULT=NOT_PASS")
            print("R8V13_08_BLOCKED=true")
            print("NEXT_ACTION=REVIEW_PRECUTOVER_FAILURE_NO_REPLAY")
            return 3

    print("PHASE=PRODUCT_RECOVERY_PENDING")
    summarize(document)
    print("FRESH_TX_A_INSTALL_RESULT=PENDING_PRODUCT_RECOVERY")
    print("R8V13_07_RESULT=NOT_PASS_YET")
    print("R8V13_08_BLOCKED=true")
    print("PRODUCT_RECOVERY_OWNER=n3w-t1-ha-recovery-retry.service+timer")
    print("DO_NOT_SUBMIT_INSTALL_AGAIN=true")
    return 4


def main() -> int:
    try:
        return execute(RealOps())
    except (GateError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("FRESH_TX_A_INSTALL_RESULT=STOP")
        print("R8V13_07_RESULT=NOT_PASS")
        print("R8V13_08_BLOCKED=true")
        try:
            summarize(read_json(TX_FILE))
        except Exception:
            print("DURABLE_TRANSACTION_SUMMARY=UNAVAILABLE")
        print("STOP_REASON=" + str(error))
        print("REPLAY_DECISION=READ_DURABLE_STATE_FIRST")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
