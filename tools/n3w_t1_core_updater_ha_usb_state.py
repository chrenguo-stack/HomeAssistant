from __future__ import annotations

import copy
import json
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_ha_usb_media import (
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    validate_filesystem_uuid,
)
from n3w_t1_core_updater_v2_common import (
    SHA256,
    TERMINAL_TX_V2,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)
from n3w_t1_core_updater_v2_state import STATE_ROOT_V2, V2StateStore


HA_USB_TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
HA_USB_ACTIVE_FILE = "homeassistant-usb-upgrade.json"
HA_USB_TERMINAL_STATUSES = frozenset({"COMMITTED", "ROLLED_BACK"})
HA_USB_STATUSES = frozenset(
    {"ACTIVE", "COMMITTED", "ROLLED_BACK", "FAILED_EMERGENCY"}
)

U0 = "U0_READONLY_ADMISSION"
U1 = "U1_PREPARE_REQUESTED"
U2 = "U2_USB_QUALIFIED_FORMATTED_BOUND"
U3 = "U3_TARGET_DOWNLOADING_VERIFYING"
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

PHASES = (
    U0,
    U1,
    U2,
    U3,
    U4,
    U5,
    U6,
    U7,
    U8,
    U9,
    U10,
    U11,
    U12,
    U13A,
    U13B,
)
PHASE_INDEX = {phase: index for index, phase in enumerate(PHASES)}
_ALLOWED_TRANSITIONS = {
    U0: frozenset({U1}),
    U1: frozenset({U2}),
    U2: frozenset({U3}),
    U3: frozenset({U4}),
    U4: frozenset({U5}),
    U5: frozenset({U6}),
    U6: frozenset({U7}),
    U7: frozenset({U8}),
    U8: frozenset({U9}),
    U9: frozenset({U10, U13B}),
    U10: frozenset({U11, U13B}),
    U11: frozenset({U12, U13B}),
    U12: frozenset({U13A, U13B}),
    U13A: frozenset(),
    U13B: frozenset(),
}

_FORBIDDEN_KEY_FRAGMENTS = (
    "password",
    "secret",
    "private_key",
    "raw_serial",
)


def _reject_sensitive_fields(value: Any) -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).lower()
            if key == "authorization_id" or any(
                fragment in key for fragment in _FORBIDDEN_KEY_FRAGMENTS
            ):
                raise UpdaterV2Error("ha_usb_transaction_sensitive_field_forbidden")
            _reject_sensitive_fields(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_sensitive_fields(nested)


def _nonempty_string(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value:
        raise UpdaterV2Error(reason)
    return value


def _positive_int(value: Any, reason: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise UpdaterV2Error(reason)
    return value


def _bool(value: Any, reason: str) -> bool:
    if not isinstance(value, bool):
        raise UpdaterV2Error(reason)
    return value


def _phase_at_or_after(phase: str, threshold: str) -> bool:
    return PHASE_INDEX[phase] >= PHASE_INDEX[threshold]


def validate_transaction_document(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema") != HA_USB_TX_SCHEMA:
        raise UpdaterV2Error("ha_usb_transaction_schema_invalid")
    _reject_sensitive_fields(document)

    if document.get("component") != "homeassistant":
        raise UpdaterV2Error("ha_usb_transaction_component_invalid")

    transaction_id = document.get("transaction_id_sha256")
    if not isinstance(transaction_id, str) or SHA256.fullmatch(transaction_id) is None:
        raise UpdaterV2Error("ha_usb_transaction_id_invalid")

    phase = document.get("phase")
    if phase not in PHASE_INDEX:
        raise UpdaterV2Error("ha_usb_transaction_phase_invalid")
    status = document.get("status")
    if status not in HA_USB_STATUSES:
        raise UpdaterV2Error("ha_usb_transaction_status_invalid")

    current_ref = _nonempty_string(
        document.get("current_image_ref"),
        "ha_usb_current_image_ref_invalid",
    )
    target_ref = _nonempty_string(
        document.get("target_image_ref"),
        "ha_usb_target_image_ref_invalid",
    )
    if (
        not current_ref.startswith("local/n3w-homeassistant:")
        or not target_ref.startswith("local/n3w-homeassistant:")
        or current_ref == target_ref
    ):
        raise UpdaterV2Error("ha_usb_image_namespace_invalid")

    for key in ("current_image_identity", "target_manifest_identity"):
        value = document.get(key)
        if not isinstance(value, dict) or not value:
            raise UpdaterV2Error(f"ha_usb_{key}_invalid")

    target_sha = document.get("target_archive_sha256")
    if not isinstance(target_sha, str) or SHA256.fullmatch(target_sha) is None:
        raise UpdaterV2Error("ha_usb_target_archive_sha256_invalid")
    _positive_int(
        document.get("target_archive_size"),
        "ha_usb_target_archive_size_invalid",
    )

    created = _positive_int(
        document.get("created_at_unix"),
        "ha_usb_created_at_invalid",
    )
    updated = _positive_int(
        document.get("updated_at_unix"),
        "ha_usb_updated_at_invalid",
    )
    if updated < created:
        raise UpdaterV2Error("ha_usb_updated_before_created")

    target_verified = _bool(
        document.get("target_artifact_verified"),
        "ha_usb_target_verified_invalid",
    )
    predecessor_verified = _bool(
        document.get("predecessor_recovery_verified"),
        "ha_usb_predecessor_verified_invalid",
    )
    backup_verified = _bool(
        document.get("ha_data_backup_verified"),
        "ha_usb_backup_verified_invalid",
    )
    capacity_verified = _bool(
        document.get("usb_capacity_verified"),
        "ha_usb_capacity_verified_invalid",
    )
    prestate_verified = _bool(
        document.get("production_prestate_verified"),
        "ha_usb_prestate_verified_invalid",
    )
    claimed = _bool(
        document.get("authorization_claimed"),
        "ha_usb_authorization_claimed_invalid",
    )
    consumed = _bool(
        document.get("authorization_consumed"),
        "ha_usb_authorization_consumed_invalid",
    )
    if claimed != consumed:
        raise UpdaterV2Error("ha_usb_authorization_state_inconsistent")

    recovery_required = _bool(
        document.get("recovery_required"),
        "ha_usb_recovery_required_invalid",
    )
    failure_code = document.get("failure_code")
    if failure_code is not None and (
        not isinstance(failure_code, str)
        or not failure_code
        or len(failure_code) > 200
        or any(ch in failure_code for ch in ("/", "\\", "@"))
    ):
        raise UpdaterV2Error("ha_usb_failure_code_invalid")

    if _phase_at_or_after(phase, U2):
        fingerprint = document.get("usb_device_identity_public_fingerprint")
        if not isinstance(fingerprint, str) or SHA256.fullmatch(fingerprint) is None:
            raise UpdaterV2Error("ha_usb_public_fingerprint_invalid")
        validate_filesystem_uuid(
            _nonempty_string(
                document.get("usb_filesystem_uuid"),
                "ha_usb_filesystem_uuid_invalid",
            )
        )
        _nonempty_string(
            document.get("usb_mount_authority"),
            "ha_usb_mount_authority_invalid",
        )
        measured = _positive_int(
            document.get("usb_measured_usable_bytes"),
            "ha_usb_measured_usable_bytes_invalid",
        )
        if measured < USB_MEASURED_USABLE_CAPACITY_MIN_BYTES:
            raise UpdaterV2Error("ha_usb_measured_capacity_below_floor")
        if capacity_verified is not True:
            raise UpdaterV2Error("ha_usb_capacity_not_verified")
    else:
        if any(
            document.get(key) not in (None, 0, False)
            for key in (
                "usb_device_identity_public_fingerprint",
                "usb_filesystem_uuid",
                "usb_mount_authority",
                "usb_measured_usable_bytes",
                "usb_capacity_verified",
            )
        ):
            raise UpdaterV2Error("ha_usb_media_bound_too_early")

    if _phase_at_or_after(phase, U4) and target_verified is not True:
        raise UpdaterV2Error("ha_usb_target_not_verified")
    if _phase_at_or_after(phase, U7) and predecessor_verified is not True:
        raise UpdaterV2Error("ha_usb_predecessor_not_verified")
    if _phase_at_or_after(phase, U8):
        if backup_verified is not True:
            raise UpdaterV2Error("ha_usb_backup_not_verified")
        if prestate_verified is not True:
            raise UpdaterV2Error("ha_usb_prestate_not_verified")

    auth_sha = document.get("authorization_id_sha256")
    if _phase_at_or_after(phase, U9):
        if (
            claimed is not True
            or consumed is not True
            or not isinstance(auth_sha, str)
            or SHA256.fullmatch(auth_sha) is None
        ):
            raise UpdaterV2Error("ha_usb_live_authorization_missing")
    elif claimed or consumed or auth_sha is not None:
        raise UpdaterV2Error("ha_usb_live_authorization_claimed_too_early")

    if phase == U13A and status != "COMMITTED":
        raise UpdaterV2Error("ha_usb_commit_status_invalid")
    if phase == U13B and status != "ROLLED_BACK":
        raise UpdaterV2Error("ha_usb_rollback_status_invalid")
    if phase not in {U13A, U13B} and status in HA_USB_TERMINAL_STATUSES:
        raise UpdaterV2Error("ha_usb_terminal_status_phase_mismatch")
    if status == "FAILED_EMERGENCY" and recovery_required is not True:
        raise UpdaterV2Error("ha_usb_failed_emergency_without_recovery")
    return copy.deepcopy(document)


def new_transaction(
    *,
    current_image_ref: str,
    current_image_identity: dict[str, Any],
    target_manifest_identity: dict[str, Any],
    target_image_ref: str,
    target_archive_sha256: str,
    target_archive_size: int,
    created_at_unix: int | None = None,
) -> dict[str, Any]:
    created = int(time.time()) if created_at_unix is None else created_at_unix
    authority = {
        "component": "homeassistant",
        "current_image_ref": current_image_ref,
        "current_image_identity": copy.deepcopy(current_image_identity),
        "target_manifest_identity": copy.deepcopy(target_manifest_identity),
        "target_image_ref": target_image_ref,
        "target_archive_sha256": target_archive_sha256,
        "target_archive_size": target_archive_size,
        "created_at_unix": created,
    }
    document = {
        "schema": HA_USB_TX_SCHEMA,
        "transaction_id_sha256": sha256_bytes(canonical(authority)),
        "phase": U0,
        "status": "ACTIVE",
        **authority,
        "usb_device_identity_public_fingerprint": None,
        "usb_filesystem_uuid": None,
        "usb_measured_usable_bytes": 0,
        "usb_mount_authority": None,
        "usb_capacity_verified": False,
        "target_artifact_verified": False,
        "predecessor_recovery_verified": False,
        "ha_data_backup_verified": False,
        "production_prestate_verified": False,
        "authorization_id_sha256": None,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "failure_code": None,
        "recovery_required": False,
        "updated_at_unix": created,
    }
    return validate_transaction_document(document)


def transition(
    document: dict[str, Any],
    next_phase: str,
    *,
    updates: dict[str, Any] | None = None,
    updated_at_unix: int | None = None,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    current_phase = current["phase"]
    if current["status"] != "ACTIVE":
        raise UpdaterV2Error("ha_usb_transaction_not_active")
    if next_phase not in _ALLOWED_TRANSITIONS[current_phase]:
        raise UpdaterV2Error("ha_usb_phase_transition_invalid")

    result = copy.deepcopy(current)
    result["phase"] = next_phase
    if updates:
        for key, value in updates.items():
            if key in {"schema", "transaction_id_sha256", "component", "created_at_unix"}:
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            result[key] = copy.deepcopy(value)

    if next_phase == U13A:
        result["status"] = "COMMITTED"
        result["recovery_required"] = False
    elif next_phase == U13B:
        result["status"] = "ROLLED_BACK"
        result["recovery_required"] = False

    now = int(time.time()) if updated_at_unix is None else updated_at_unix
    result["updated_at_unix"] = max(int(result["created_at_unix"]), now)
    return validate_transaction_document(result)


def mark_failed_emergency(
    document: dict[str, Any],
    *,
    failure_code: str,
    updated_at_unix: int | None = None,
) -> dict[str, Any]:
    result = validate_transaction_document(document)
    if result["status"] in HA_USB_TERMINAL_STATUSES:
        raise UpdaterV2Error("ha_usb_terminal_transaction_cannot_fail")
    result["status"] = "FAILED_EMERGENCY"
    result["failure_code"] = failure_code
    result["recovery_required"] = True
    now = int(time.time()) if updated_at_unix is None else updated_at_unix
    result["updated_at_unix"] = max(int(result["created_at_unix"]), now)
    return validate_transaction_document(result)


class HaUsbStateStore:
    def __init__(self, root: Path = STATE_ROOT_V2) -> None:
        self.root = root
        self.path = root / HA_USB_ACTIVE_FILE
        self.history = root / "history"

    def lock(self):
        return V2StateStore(self.root).lock()

    def _validate_private_dir(self, path: Path) -> None:
        if path.is_symlink() or not path.is_dir():
            raise UpdaterV2Error("transaction_directory_invalid")
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise UpdaterV2Error("transaction_directory_not_private")
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("transaction_directory_owner_invalid")

    def _existing_root(self) -> bool:
        if self.root.is_symlink():
            raise UpdaterV2Error("transaction_root_symlink")
        if not self.root.exists():
            return False
        self._validate_private_dir(self.root)
        return True

    def _ensure_root(self) -> None:
        if not self._existing_root():
            self.root.mkdir(parents=True, mode=0o700)
        self._validate_private_dir(self.root)

    def _ensure_history(self) -> None:
        self._ensure_root()
        if self.history.is_symlink():
            raise UpdaterV2Error("transaction_history_symlink")
        if not self.history.exists():
            self.history.mkdir(mode=0o700)
        self._validate_private_dir(self.history)

    def read(self) -> dict[str, Any] | None:
        if not self._existing_root() or not self.path.exists():
            return None
        if self.path.is_symlink() or not self.path.is_file():
            raise UpdaterV2Error("ha_usb_transaction_invalid")
        metadata = self.path.stat()
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise UpdaterV2Error("ha_usb_transaction_metadata_invalid")
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("ha_usb_transaction_owner_invalid")
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error("ha_usb_transaction_invalid") from error
        return validate_transaction_document(document)

    def _archive_current(self, document: dict[str, Any]) -> None:
        self._ensure_history()
        digest = sha256_bytes(canonical(document))[:16]
        destination = (
            self.history
            / f"{int(time.time())}-homeassistant-usb-{digest}.json"
        )
        if destination.exists() or destination.is_symlink():
            raise UpdaterV2Error("transaction_history_collision")
        os.replace(self.path, destination)
        os.chmod(destination, 0o600)
        for path in (self.history, self.root):
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def prepare_new(self) -> None:
        self._ensure_root()
        generic = V2StateStore(self.root)
        current_generic = generic.read()
        legacy = generic.read_legacy()
        if (
            current_generic is not None
            and current_generic.get("status") not in TERMINAL_TX_V2
        ):
            raise UpdaterV2Error("upgrade_transaction_active")
        if (
            current_generic is not None
            and current_generic.get("status") == "COMMITTED"
            and current_generic.get("component") in {"manager", "broker"}
            and current_generic.get("cleanup_state")
            != "ACCEPTED_CLEANUP_COMPLETE"
        ):
            raise UpdaterV2Error("post_acceptance_cleanup_required")
        if (
            legacy is not None
            and legacy.get("status") not in {"COMMITTED", "ROLLED_BACK"}
        ):
            raise UpdaterV2Error("legacy_transaction_reconciliation_required")

        current = self.read()
        if current is not None and current["status"] not in HA_USB_TERMINAL_STATUSES:
            raise UpdaterV2Error("ha_usb_transaction_active")
        if current is not None:
            self._archive_current(current)

    def write(self, document: dict[str, Any]) -> None:
        validated = validate_transaction_document(document)
        self._ensure_root()
        payload = json.dumps(validated, sort_keys=True, indent=2) + "\n"
        fd, raw = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.root)
        temporary = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            descriptor = os.open(
                self.root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
