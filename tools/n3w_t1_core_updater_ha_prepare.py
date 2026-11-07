from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import (
    record_media_bound,
    record_target_ready,
    start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import (
    FORMAT_CONFIRMATION,
    RemovableDeviceCandidate,
    UsbCapacityInputs,
    assess_capacity,
    authorize_destructive_format,
    classify_candidate,
)
from n3w_t1_core_updater_ha_usb_state import (
    U1,
    U2,
    U3,
    U4,
    HaUsbStateStore,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error

PREPARE_STATE_SCHEMA = "gh.n3w-t1-ha-usb-prepare-state/1"
PREPARE_STATE_FILE = "homeassistant-usb-prepare.json"


@dataclass(frozen=True, slots=True)
class HostUsbCandidate:
    locator: str
    public_fingerprint: str
    display_model: str
    display_capacity_bytes: int
    newly_inserted: bool = True
    removable: bool = True
    mass_storage: bool = True
    read_only: bool = False
    is_root_device: bool = False
    backs_production_mount: bool = False

    def validate(self) -> "HostUsbCandidate":
        if (
            not isinstance(self.locator, str)
            or not self.locator.startswith("/dev/")
            or "\x00" in self.locator
        ):
            raise UpdaterV2Error("usb_candidate_locator_invalid")
        if not isinstance(self.public_fingerprint, str) or SHA256.fullmatch(
            self.public_fingerprint
        ) is None:
            raise UpdaterV2Error("usb_public_fingerprint_invalid")
        if (
            not isinstance(self.display_model, str)
            or not self.display_model.strip()
            or len(self.display_model) > 160
            or any(character in self.display_model for character in ("\x00", "\n", "\r"))
        ):
            raise UpdaterV2Error("usb_display_model_invalid")
        if (
            type(self.display_capacity_bytes) is not int
            or self.display_capacity_bytes <= 0
        ):
            raise UpdaterV2Error("usb_display_capacity_invalid")
        classify_candidate(self.as_media_candidate())
        return self

    def as_media_candidate(self) -> RemovableDeviceCandidate:
        return RemovableDeviceCandidate(
            public_fingerprint=self.public_fingerprint,
            newly_inserted=self.newly_inserted,
            removable=self.removable,
            mass_storage=self.mass_storage,
            read_only=self.read_only,
            is_root_device=self.is_root_device,
            backs_production_mount=self.backs_production_mount,
            display_identity_matches=True,
        )

    def public(self) -> dict[str, str | int]:
        self.validate()
        return {
            "public_fingerprint": self.public_fingerprint,
            "display_model": self.display_model.strip(),
            "display_capacity_bytes": self.display_capacity_bytes,
        }


@dataclass(frozen=True, slots=True)
class PreparedUsbMedia:
    locator: str
    public_fingerprint: str
    filesystem_uuid: str
    measured_usable_bytes: int
    mount_path: str

    def validate(self) -> "PreparedUsbMedia":
        if not isinstance(self.locator, str) or not self.locator.startswith("/dev/"):
            raise UpdaterV2Error("usb_prepared_locator_invalid")
        if not isinstance(self.public_fingerprint, str) or SHA256.fullmatch(
            self.public_fingerprint
        ) is None:
            raise UpdaterV2Error("usb_public_fingerprint_invalid")
        if (
            type(self.measured_usable_bytes) is not int
            or self.measured_usable_bytes <= 0
        ):
            raise UpdaterV2Error("usb_measured_usable_bytes_invalid")
        path = Path(self.mount_path)
        if not path.is_absolute() or "\x00" in self.mount_path:
            raise UpdaterV2Error("usb_mount_path_invalid")
        return self


class PreparePipelineBackend(Protocol):
    def inventory(self) -> tuple[HostUsbCandidate, ...]:
        """Return a read-only host inventory of removable-device candidates."""

    def capacity_inputs(
        self,
        transaction: dict[str, Any],
    ) -> UsbCapacityInputs:
        """Return host-owned, fail-closed capacity inputs for this release."""

    def format_and_mount(
        self,
        *,
        candidate: HostUsbCandidate,
        transaction_id_sha256: str,
    ) -> PreparedUsbMedia:
        """Format only the already revalidated candidate and return bound media."""

    def reopen_bound_media(
        self,
        transaction: dict[str, Any],
    ) -> PreparedUsbMedia | None:
        """Reopen only the UUID/fingerprint already durably bound at U2."""

    def prepare_target(
        self,
        *,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        """Stream, verify and fsync the exact target directly on bound media."""

    def abort_prepared_media(self, media: PreparedUsbMedia) -> None:
        """Best-effort unmount/cleanup after post-format admission failure."""


class PrepareStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / PREPARE_STATE_FILE

    def _existing_root(self) -> bool:
        if self.root.is_symlink():
            raise UpdaterV2Error("transaction_root_symlink")
        if not self.root.exists():
            return False
        if not self.root.is_dir():
            raise UpdaterV2Error("transaction_directory_invalid")
        metadata = self.root.stat()
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise UpdaterV2Error("transaction_directory_not_private")
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("transaction_directory_owner_invalid")
        return True

    def _ensure_root(self) -> None:
        if not self._existing_root():
            self.root.mkdir(parents=True, mode=0o700)
        if not self._existing_root():
            raise UpdaterV2Error("transaction_directory_invalid")

    def read(self) -> dict[str, Any] | None:
        if not self._existing_root() or not self.path.exists():
            return None
        if self.path.is_symlink() or not self.path.is_file():
            raise UpdaterV2Error("ha_usb_prepare_state_invalid")
        metadata = self.path.stat()
        if stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.getuid():
            raise UpdaterV2Error("ha_usb_prepare_state_metadata_invalid")
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error("ha_usb_prepare_state_invalid") from error
        return validate_prepare_state(document)

    def write(self, document: dict[str, Any]) -> None:
        validated = validate_prepare_state(document)
        self._ensure_root()
        payload = json.dumps(validated, sort_keys=True, indent=2) + "\n"
        descriptor, raw = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.root,
        )
        temporary = Path(raw)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(
                self.root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


def validate_prepare_state(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema") != PREPARE_STATE_SCHEMA:
        raise UpdaterV2Error("ha_usb_prepare_state_schema_invalid")
    transaction_id = document.get("transaction_id_sha256")
    if not isinstance(transaction_id, str) or SHA256.fullmatch(transaction_id) is None:
        raise UpdaterV2Error("ha_usb_prepare_transaction_invalid")
    release_identity = document.get("release_identity")
    if (
        not isinstance(release_identity, str)
        or not 3 <= len(release_identity) <= 128
        or any(character.isspace() for character in release_identity)
    ):
        raise UpdaterV2Error("ha_usb_prepare_release_invalid")
    baseline = document.get("baseline_public_fingerprints")
    if (
        not isinstance(baseline, list)
        or len(baseline) > 32
        or any(
            not isinstance(value, str) or SHA256.fullmatch(value) is None
            for value in baseline
        )
        or len(set(baseline)) != len(baseline)
    ):
        raise UpdaterV2Error("ha_usb_prepare_baseline_invalid")
    candidate = document.get("candidate")
    if candidate is not None:
        if not isinstance(candidate, dict) or set(candidate) != {
            "public_fingerprint",
            "display_model",
            "display_capacity_bytes",
        }:
            raise UpdaterV2Error("ha_usb_prepare_candidate_invalid")
        if (
            not isinstance(candidate["public_fingerprint"], str)
            or SHA256.fullmatch(candidate["public_fingerprint"]) is None
            or not isinstance(candidate["display_model"], str)
            or not candidate["display_model"].strip()
            or type(candidate["display_capacity_bytes"]) is not int
            or candidate["display_capacity_bytes"] <= 0
        ):
            raise UpdaterV2Error("ha_usb_prepare_candidate_invalid")
    for key in ("confirmation_required", "confirmation_consumed"):
        if type(document.get(key)) is not bool:
            raise UpdaterV2Error("ha_usb_prepare_confirmation_invalid")
    if document["confirmation_required"] and candidate is None:
        raise UpdaterV2Error("ha_usb_prepare_candidate_missing")
    if document["confirmation_consumed"] and candidate is None:
        raise UpdaterV2Error("ha_usb_prepare_candidate_missing")
    error_code = document.get("error_code")
    if error_code is not None and (
        not isinstance(error_code, str)
        or not 3 <= len(error_code) <= 96
        or not error_code.replace("_", "").isalnum()
        or not error_code.islower()
    ):
        raise UpdaterV2Error("ha_usb_prepare_error_code_invalid")
    updated_at = document.get("updated_at_unix")
    if type(updated_at) is not int or updated_at <= 0:
        raise UpdaterV2Error("ha_usb_prepare_updated_at_invalid")
    return json.loads(json.dumps(document))


def _eligible(
    candidates: tuple[HostUsbCandidate, ...],
) -> tuple[HostUsbCandidate, ...]:
    result: list[HostUsbCandidate] = []
    for candidate in candidates:
        candidate.validate()
        if not classify_candidate(candidate.as_media_candidate()):
            result.append(candidate)
    return tuple(result)


class HaUsbPrepareController:
    """Bound U1->U4 controller. It never enters U5 or later phases."""

    def __init__(
        self,
        *,
        transaction_store: HaUsbStateStore,
        prepare_store: PrepareStateStore,
        backend: PreparePipelineBackend,
    ) -> None:
        self.transaction_store = transaction_store
        self.prepare_store = prepare_store
        self.backend = backend

    def _transaction(self) -> dict[str, Any]:
        document = self.transaction_store.read()
        if document is None:
            raise UpdaterV2Error("ha_usb_transaction_missing")
        return validate_transaction_document(document)

    def _matching_prepare_state(
        self,
        transaction: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.prepare_store.read()
        if state is None:
            raise UpdaterV2Error("ha_usb_prepare_state_missing")
        if state["transaction_id_sha256"] != transaction["transaction_id_sha256"]:
            raise UpdaterV2Error("ha_usb_prepare_transaction_drift")
        if state["release_identity"] != transaction["target_manifest_identity"].get(
            "release_identity"
        ):
            raise UpdaterV2Error("ha_usb_prepare_release_drift")
        return state

    def begin(self, transaction: dict[str, Any]) -> None:
        current = validate_transaction_document(transaction)
        if current["phase"] != U1:
            raise UpdaterV2Error("ha_usb_prepare_begin_phase_invalid")
        baseline = sorted(
            candidate.public_fingerprint
            for candidate in _eligible(tuple(self.backend.inventory()))
        )
        release_identity = current["target_manifest_identity"].get("release_identity")
        if not isinstance(release_identity, str):
            raise UpdaterV2Error("ha_usb_prepare_release_invalid")
        self.prepare_store.write(
            {
                "schema": PREPARE_STATE_SCHEMA,
                "transaction_id_sha256": current["transaction_id_sha256"],
                "release_identity": release_identity,
                "baseline_public_fingerprints": baseline,
                "candidate": None,
                "confirmation_required": False,
                "confirmation_consumed": False,
                "error_code": None,
                "updated_at_unix": int(time.time()),
            }
        )

    def refresh_candidate(self) -> dict[str, Any]:
        transaction = self._transaction()
        if transaction["phase"] != U1:
            return self.public_status()
        state = self._matching_prepare_state(transaction)
        baseline = set(state["baseline_public_fingerprints"])
        fresh = tuple(
            candidate
            for candidate in _eligible(tuple(self.backend.inventory()))
            if candidate.public_fingerprint not in baseline
        )
        next_state = dict(state)
        next_state["updated_at_unix"] = int(time.time())
        next_state["confirmation_consumed"] = False
        if not fresh:
            next_state["candidate"] = None
            next_state["confirmation_required"] = False
            next_state["error_code"] = None
        elif len(fresh) != 1:
            next_state["candidate"] = None
            next_state["confirmation_required"] = False
            next_state["error_code"] = "usb_multiple_eligible_devices"
        else:
            next_state["candidate"] = fresh[0].public()
            next_state["confirmation_required"] = True
            next_state["error_code"] = None
        self.prepare_store.write(next_state)
        return self.public_status()

    def confirm_and_prepare(self) -> dict[str, Any]:
        transaction = self._transaction()
        if transaction["phase"] != U1:
            raise UpdaterV2Error("ha_usb_confirm_phase_invalid")
        state = self._matching_prepare_state(transaction)
        candidate_public = state.get("candidate")
        if (
            state.get("confirmation_required") is not True
            or not isinstance(candidate_public, dict)
        ):
            raise UpdaterV2Error("usb_destructive_confirmation_not_ready")

        baseline = set(state["baseline_public_fingerprints"])
        fresh = tuple(
            candidate
            for candidate in _eligible(tuple(self.backend.inventory()))
            if candidate.public_fingerprint not in baseline
        )
        if len(fresh) != 1:
            raise UpdaterV2Error("usb_confirmation_candidate_ambiguous")
        candidate = fresh[0]
        if candidate.public_fingerprint != candidate_public["public_fingerprint"]:
            raise UpdaterV2Error("usb_confirmation_candidate_drift")
        if (
            candidate.display_model.strip() != candidate_public["display_model"].strip()
            or candidate.display_capacity_bytes
            != candidate_public["display_capacity_bytes"]
        ):
            raise UpdaterV2Error("usb_confirmation_display_identity_drift")

        authorization = authorize_destructive_format(
            candidate.as_media_candidate(),
            FORMAT_CONFIRMATION,
        )
        consumed = dict(state)
        consumed["confirmation_required"] = False
        consumed["confirmation_consumed"] = True
        consumed["error_code"] = None
        consumed["updated_at_unix"] = int(time.time())
        self.prepare_store.write(consumed)

        capacity_inputs = self.backend.capacity_inputs(transaction)
        media = self.backend.format_and_mount(
            candidate=candidate,
            transaction_id_sha256=transaction["transaction_id_sha256"],
        ).validate()
        if media.public_fingerprint != candidate.public_fingerprint:
            raise UpdaterV2Error("usb_prepared_identity_drift")

        capacity = assess_capacity(media.measured_usable_bytes, capacity_inputs)
        if capacity.capacity_pass is not True:
            try:
                self.backend.abort_prepared_media(media)
            finally:
                raise UpdaterV2Error("ha_usb_capacity_not_verified")
        u2 = record_media_bound(
            transaction,
            format_authorization=authorization,
            filesystem_uuid=media.filesystem_uuid,
            measured_usable_bytes=media.measured_usable_bytes,
            capacity_report=capacity,
        )
        self.transaction_store.write(u2)

        u3 = start_target_preparation(u2)
        self.transaction_store.write(u3)
        target = self.backend.prepare_target(transaction=u3, media=media)
        u4 = record_target_ready(u3, target=target)
        self.transaction_store.write(u4)
        return self.public_status()

    def resume_prepare(self) -> dict[str, Any]:
        transaction = self._transaction()
        if transaction["phase"] not in {U2, U3}:
            raise UpdaterV2Error("ha_usb_prepare_resume_phase_invalid")
        media = self.backend.reopen_bound_media(transaction)
        if media is None:
            raise UpdaterV2Error("usb_bound_media_unavailable")
        current = transaction
        if current["phase"] == U2:
            current = start_target_preparation(current)
            self.transaction_store.write(current)
        target = self.backend.prepare_target(transaction=current, media=media)
        u4 = record_target_ready(current, target=target)
        self.transaction_store.write(u4)
        return self.public_status()

    def public_status(self) -> dict[str, Any]:
        transaction = self._transaction()
        phase = transaction["phase"]
        candidate = None
        confirmation_required = False
        error_code = None
        if phase == U1:
            state = self._matching_prepare_state(transaction)
            candidate = state.get("candidate")
            confirmation_required = bool(state.get("confirmation_required"))
            error_code = state.get("error_code")
            if error_code is not None:
                public_phase = "ERROR"
            elif confirmation_required:
                public_phase = "USB_REQUIRED_CONFIRMATION"
            else:
                public_phase = "USB_REQUIRED"
        elif phase in {U2, U3}:
            public_phase = "TARGET_DOWNLOADING_VERIFYING"
        elif phase == U4:
            public_phase = "READY_TO_INSTALL"
        else:
            raise UpdaterV2Error("ha_usb_prepare_status_phase_invalid")
        return {
            "phase": public_phase,
            "progress_percent": None,
            "error_code": error_code,
            "usb_candidate": candidate,
            "usb_confirmation_required": confirmation_required,
        }
