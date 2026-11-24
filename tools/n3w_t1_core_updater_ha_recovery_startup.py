#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, BinaryIO

from n3w_t1_core_updater_common import (
    IMAGE_ID,
    SERVICES_UNIT,
    UpdaterError,
    canonical,
    sha256_bytes,
)
from n3w_t1_core_updater_ha_acceptance import (
    NATURAL_MONITORING_METHOD, LocalHaAcceptanceObserver, monitoring_self_test_qualified,
)
from n3w_t1_core_updater_ha_backup import DEFAULT_HA_DATA_ROOT, HA_DATABASE_NAME, ProtectedHaDataBackup
from n3w_t1_core_updater_ha_data_evidence import MANAGER_PAIRING_DB, HaProtectedDataEvidence
from n3w_t1_core_updater_ha_ipc import (
    APPROVED_MANIFEST, IPC_SOCKET, RELEASE_PIN, HaUsbIpcExecutor, LocalApprovedHaRelease,
    reject_duplicate_fields, serve_activated_ha_ipc,
)
from n3w_t1_core_updater_ha_monitoring_evidence import (
    LocalHaMonitoringEvidence, READ_HA_RECEIPTS, REQUEST_MANAGER_SELF_TEST,
)
from n3w_t1_core_updater_ha_mounted_media import (
    HaMountedBackupProvider, HaMountedInstallMaterialVerifier, bound_usb_device,
    measure_preparation_capacity, prepare_mounted_archives,
)
from n3w_t1_core_updater_ha_usb import (
    HaDataRestoreProvider, HaPredecessorRecovery, HaPredecessorRelease, destructive_cutover_allowed,
    ha_data_rollback_required, record_existing_media_bound, record_pre_cutover_failure_terminal,
    record_target_ready, resume_host_recovery, start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import USB_FILESYSTEM, validate_filesystem_uuid
from n3w_t1_core_updater_ha_usb_state import (
    TARGET_BINDING, TARGET_WRITES_POSSIBLE, U1, U2, U3, U4, U5, U6, U9, U10, HaUsbStateStore,
    record_usb_capacity_event,
)
from n3w_t1_core_updater_host import DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS, LocalHost
from n3w_t1_core_updater_v2_common import AUTHORIZATION_ID, COMPONENTS, SHA256, UpdaterV2Error
from n3w_t1_portable_image_identity import (
    MAX_ARCHIVE_BYTES, PortableImageIdentity, identity_from_dict, observe_docker_image, verify_runtime_document,
)


PROTECTED_BINDS = {
    "homeassistant": {"/config"},
    "manager": {"/var/lib/greenhouse-manager/manager", "/var/lib/greenhouse-manager/n3w"},
}
RECOVERY_ARCHIVE = "/opt/n3w-t1-core-updater/ha-recovery.pyz"
RECOVERY_COMMAND = f"/usr/bin/python3 -I {RECOVERY_ARCHIVE}"
RECOVERY_STARTUP_UNIT = "n3w-t1-ha-recovery-startup.service"
RECOVERY_RETRY_UNIT = "n3w-t1-ha-recovery-retry.service"
RECOVERY_TIMER = "n3w-t1-ha-recovery-retry.timer"
BOOT_CONDITION = f"ExecCondition={RECOVERY_COMMAND} --check-application-start"
IMAGE_LOAD_TIMEOUT_SECONDS = 1800
PREPARE_AUTHORITY_FILE = "ha-prepare-authority.json"
PREPARE_AUTHORITY_SCHEMA = "gh.n3w-t1-ha-prepare-authority/2"
INSTALL_AUTHORITY_FILE = "ha-install-authority.json"
INSTALL_AUTHORITY_SCHEMA = "gh.n3w-t1-ha-install-authority/3"


def _exclusive_image_references(
    image: dict[str, Any], reference: str, *, allow_untagged: bool = False,
) -> bool:
    """Match Docker's single-repository ownership rule, not an empty digest list.

    RepoDigests are aliases reported for the inspected image; their manifest
    digests need not equal the host-local image ID. Keep all other ownership
    and non-forced deletion checks independent of this metadata predicate.
    """
    tags = image.get("RepoTags")
    if tags != [reference] and not (allow_untagged and tags in (None, [])):
        return False
    repository, separator, tag = reference.rpartition(":")
    if not separator or not repository or not tag or "@" in reference:
        return False
    digests = image.get("RepoDigests")
    if digests is None:
        return True
    if not isinstance(digests, list):
        return False
    for digest in digests:
        if not isinstance(digest, str):
            return False
        name, separator, value = digest.partition("@sha256:")
        if not separator or name != repository or SHA256.fullmatch(value) is None:
            return False
    return True


def requested_install_binding_sha256(document: dict[str, Any]) -> str:
    return sha256_bytes(canonical({
        field: document[field] for field in (
            "transaction_id_sha256", "usb_filesystem_uuid", "usb_mount_authority", "prepared_image_materials",
        )
    }))


def _require_signed_predecessor(document: dict[str, Any], binding: dict[str, Any]) -> None:
    expected = document["target_manifest_identity"].get("predecessor_binding_sha256")
    if expected is not None and sha256_bytes(canonical(binding)) != expected:
        raise UpdaterV2Error("ha_usb_signed_predecessor_binding_drift")


def _read_authority_file(path: Path, reason: str) -> dict[str, Any]:
    if path.resolve() != path:
        raise UpdaterV2Error(reason)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid() or metadata.st_size > 4096
        ):
            raise UpdaterV2Error(reason)
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise UpdaterV2Error(reason)
    grant = json.loads(raw, object_pairs_hook=reject_duplicate_fields)
    if not isinstance(grant, dict):
        raise UpdaterV2Error(reason)
    return grant


def _read_authority(path: Path, reason: str) -> dict[str, Any]:
    grant = _read_authority_file(path, reason)
    if (
        type(grant.get("expires_at_unix")) is not int
        or time.time() >= grant["expires_at_unix"]
        or not isinstance(grant.get("launch_sha256"), str) or not SHA256.fullmatch(grant["launch_sha256"])
    ):
        raise UpdaterV2Error(reason)
    return grant


def _publish_authority(path: Path, grant: dict[str, Any], binding_key: str) -> None:
    reason = "ha_usb_authority_destination_invalid"
    try:
        existing = _read_authority_file(path, reason)
    except FileNotFoundError:
        existing = None
    if existing is not None:
        if type(existing.get("expires_at_unix")) is not int or not isinstance(existing.get(binding_key), str):
            raise UpdaterV2Error(reason)
        if (
            existing[binding_key] == grant[binding_key] and existing["expires_at_unix"] > time.time()
            and existing != grant
        ):
            raise UpdaterV2Error("ha_usb_authority_already_issued")

    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(grant) + b"\n")
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


def _read_prepare_authority(store: HaUsbStateStore, document: dict[str, Any]) -> dict[str, Any]:
    reason = "ha_usb_prepare_authority_invalid"
    return _validate_prepare_authority(_read_authority(store.root / PREPARE_AUTHORITY_FILE, reason), document)


def _validate_prepare_authority(grant: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    reason = "ha_usb_prepare_authority_invalid"
    if (
        set(grant) != {
            "schema", "transaction_id_sha256", "usb_filesystem_uuid", "target_source",
            "launch_sha256", "expires_at_unix",
        }
        or grant["schema"] != PREPARE_AUTHORITY_SCHEMA
        or grant["transaction_id_sha256"] != document["transaction_id_sha256"]
        or not isinstance(grant["target_source"], str) or not Path(grant["target_source"]).is_absolute()
    ):
        raise UpdaterV2Error(reason)
    grant["usb_filesystem_uuid"] = validate_filesystem_uuid(grant["usb_filesystem_uuid"])
    return grant


def _read_install_authority(store: HaUsbStateStore, document: dict[str, Any]) -> dict[str, Any]:
    reason = "ha_usb_install_authority_invalid"
    return _validate_install_authority(_read_authority(store.root / INSTALL_AUTHORITY_FILE, reason), document)


def _validate_install_authority(grant: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    reason = "ha_usb_install_authority_invalid"
    if (
        set(grant) != {"schema", "binding_sha256", "authorization_id", "launch_sha256", "expires_at_unix"}
        or grant["schema"] != INSTALL_AUTHORITY_SCHEMA
        or grant["binding_sha256"] != requested_install_binding_sha256(document)
        or not isinstance(grant["authorization_id"], str) or not AUTHORIZATION_ID.fullmatch(grant["authorization_id"])
    ):
        raise UpdaterV2Error(reason)
    return grant


def _retire_owned_candidate_archive(
    store: HaUsbStateStore,
    document: dict[str, Any],
    source: Path,
) -> bool:
    """Free only the updater-owned internal candidate after USB has exact durable copies."""
    expected = store.root / f"ha-target-{document['target_archive_sha256']}.tar"
    if source != expected:
        return False
    try:
        metadata = source.lstat()
    except FileNotFoundError:
        return True
    if (
        source.resolve(strict=True) != source
        or source.parent.resolve(strict=True) != store.root.resolve(strict=True)
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.geteuid()
        or metadata.st_nlink != 1
        or metadata.st_size != document["target_archive_size"]
    ):
        raise UpdaterV2Error("ha_usb_owned_target_source_invalid")
    try:
        source.unlink()
        parent = os.open(store.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    except OSError as error:
        raise UpdaterV2Error("ha_usb_owned_target_source_retirement_failed") from error
    return True


def _protected_data_evidence(origins: dict[str, dict[str, str]]) -> HaProtectedDataEvidence:
    history = Path(origins["homeassistant"]["/config"]) / HA_DATABASE_NAME
    manager = Path(origins["manager"][str(MANAGER_PAIRING_DB.parent)]) / MANAGER_PAIRING_DB.name
    return HaProtectedDataEvidence(history, manager)


class HaRecoveryMediaRequired(UpdaterError):
    pass


class HaRecoveryMonitoringPending(UpdaterError):
    pass


class LocalHaPredecessorRuntime(LocalHost):
    ha_data_root = DEFAULT_HA_DATA_ROOT

    def candidate_manager_monitoring_self_test_available(self) -> bool:
        manager = self._runtime("manager")
        result = self._run((
            "docker", "exec", manager["container_id"], "python3", "-I", "-B", "-c",
            "from greenhouse_manager.runtime.mqtt_service import ManagerMqttService\n"
            "raise SystemExit(0 if callable(getattr(ManagerMqttService, "
            "'_publish_ota_monitoring_self_test', None)) else 42)",
        ), check=False, timeout=10)
        if result.returncode == 0:
            return True
        if result.returncode == 42:
            return False
        raise UpdaterError("ha_recovery_candidate_manager_monitoring_probe_failed")

    def acceptance_observer(self) -> LocalHaAcceptanceObserver:
        binding, origins = self._restart_binding()
        if not all(self._check_running_predecessor(binding, origins).values()):
            raise UpdaterError("ha_usb_predecessor_acceptance_runtime_unavailable")
        monitoring = self._monitoring_evidence(origins)
        self_test = (
            monitoring.run_self_test
            if self.candidate_manager_monitoring_self_test_available()
            else None
        )
        return LocalHaAcceptanceObserver(
            monitoring, _protected_data_evidence(origins), monitoring_method=NATURAL_MONITORING_METHOD,
            self_test=self_test,
        )

    def _monitoring_evidence(self, origins: dict[str, dict[str, str]]) -> LocalHaMonitoringEvidence:
        environment = self.render_compose()["services"]["manager"]["environment"]
        system_id = environment["GH_SYSTEM_ID"]
        replay_root = "/var/lib/greenhouse-manager/n3w"
        if (
            not isinstance(system_id, str) or not system_id
            or environment.get("GH_N3W_REPLAY_DB_PATH") != f"{replay_root}/replay.sqlite3"
        ):
            raise UpdaterError("ha_usb_natural_monitoring_binding_invalid")
        return LocalHaMonitoringEvidence(
            system_id, Path(origins["manager"][replay_root]) / "replay.sqlite3",
            self._runtime, self._read_ha_receipts, self._request_ha_monitoring_self_test,
        )

    @staticmethod
    @contextmanager
    def _open_target_source(path: Path, size: int) -> Iterator[BinaryIO]:
        if path.resolve(strict=True) != path:
            raise UpdaterV2Error("ha_usb_preparation_target_source_invalid")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o022 or info.st_size != size
            ):
                raise UpdaterV2Error("ha_usb_preparation_target_source_invalid")
            yield source

    @staticmethod
    @contextmanager
    def _export_predecessor(reference: str) -> Iterator[BinaryIO]:
        with subprocess.Popen(
            ("docker", "image", "save", "--", reference), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ) as process:
            assert process.stdout is not None
            timeout = threading.Timer(IMAGE_LOAD_TIMEOUT_SECONDS, process.kill)
            timeout.start()
            try:
                with process.stdout as source:
                    yield source
                if process.wait() != 0:
                    raise UpdaterError("ha_usb_preparation_predecessor_export_failed")
            finally:
                timeout.cancel()
                if process.poll() is None:
                    process.kill()


    def _measure_predecessor_archive(self, reference: str) -> int:
        total = 0
        with self._export_predecessor(reference) as source:
            while block := source.read(1024 * 1024):
                total += len(block)
                if total > MAX_ARCHIVE_BYTES:
                    raise UpdaterV2Error("ha_usb_predecessor_archive_size_invalid")
        if total <= 0:
            raise UpdaterV2Error("ha_usb_predecessor_archive_size_invalid")
        return total

    def issue_candidate_authority(self, store: HaUsbStateStore, kind: str, request: dict[str, Any]) -> str:
        """Bind an explicit operator approval to the current private transaction."""
        with store.lock():
            document = store.read()
            if (
                document is None or document["status"] != "ACTIVE" or document["recovery_required"]
                or "predecessor_start" in document
            ):
                raise UpdaterV2Error("ha_usb_authority_request_not_admitted")
            expires = request.get("expires_at_unix")
            if (
                type(expires) is not int or expires <= time.time()
                or request.get("transaction_id_sha256") != document["transaction_id_sha256"]
            ):
                raise UpdaterV2Error("ha_usb_authority_request_binding_invalid")
            resolver = LocalApprovedHaRelease(
                store.root / RELEASE_PIN, IPC_SOCKET.with_name(APPROVED_MANIFEST),
                lambda: self._runtime("homeassistant"),
            )
            admission = resolver.resolve_homeassistant_release(document["target_manifest_identity"]["release_identity"])
            HaUsbIpcExecutor.require_same_admission(document, admission)
            predecessor_binding = self.capture_start_binding(document)
            _require_signed_predecessor(document, predecessor_binding)
            launch = predecessor_binding["launch_sha256"]
            common = {"expires_at_unix": expires, "launch_sha256": launch}
            binding_key = "transaction_id_sha256" if kind == "prepare" else "binding_sha256"
            request_fields = {"transaction_id_sha256", "expires_at_unix"}
            if kind == "prepare":
                fields = {"usb_filesystem_uuid", "target_source"}
                if document["phase"] not in {U1, U2, U3} or request.keys() != request_fields | fields:
                    raise UpdaterV2Error("ha_usb_authority_request_not_admitted")
                grant = _validate_prepare_authority({
                    **common, "schema": PREPARE_AUTHORITY_SCHEMA, binding_key: request[binding_key],
                    **{key: request[key] for key in fields},
                }, document)
                uuid = grant["usb_filesystem_uuid"]
                if document["phase"] != U1 and (
                    document.get("usb_binding_mode") != "existing_filesystem" or document["usb_filesystem_uuid"] != uuid
                ):
                    raise UpdaterV2Error("ha_usb_prepare_authority_drift")
                mountpoint = self._original_mountpoint(uuid)
                if document["phase"] == U1:
                    measure_preparation_capacity(
                        mountpoint, store.root, uuid, document["target_archive_size"],
                    )
                with self._open_target_source(Path(grant["target_source"]), document["target_archive_size"]) as archive:
                    if hashlib.file_digest(archive, "sha256").hexdigest() != document["target_archive_sha256"]:
                        raise UpdaterV2Error("ha_usb_prepare_authority_target_digest_mismatch")
                destination = store.root / PREPARE_AUTHORITY_FILE
            elif kind == "install":
                fields = {"binding_sha256", "authorization_id"}
                if (
                    document["phase"] not in {U5, U6} or document.get("usb_binding_mode") != "existing_filesystem"
                    or request.keys() != request_fields | fields
                ):
                    raise UpdaterV2Error("ha_usb_authority_request_not_admitted")
                grant = _validate_install_authority({
                    **common, "schema": INSTALL_AUTHORITY_SCHEMA, **{key: request[key] for key in fields},
                }, document)
                auth_digest = sha256_bytes(grant["authorization_id"].encode())
                if document["authorization_consumed"] or store.was_authorization_consumed(auth_digest):
                    raise UpdaterV2Error("ha_usb_install_authority_already_consumed")
                self._original_mountpoint(document["usb_filesystem_uuid"])
                destination = store.root / INSTALL_AUTHORITY_FILE
            else:
                raise UpdaterV2Error("ha_usb_authority_request_kind_invalid")
            final_binding = self.capture_start_binding(document)
            _require_signed_predecessor(document, final_binding)
            if final_binding["launch_sha256"] != launch or expires <= time.time():
                raise UpdaterV2Error("ha_usb_authority_request_binding_changed")
            _publish_authority(destination, grant, binding_key)
        return f"{kind.upper()}_AUTHORITY_ISSUED"

    def prepare_requested(self, store: HaUsbStateStore) -> str:
        with store.lock():
            document = store.read()
            if (
                document is None or document["status"] != "ACTIVE"
                or document["phase"] not in {U1, U2, U3} or document["recovery_required"]
                or (document["phase"] != U1 and document.get("usb_binding_mode") != "existing_filesystem")
            ):
                return "NO_ADMITTED_PREPARE_REQUEST"
            grant = _read_prepare_authority(store, document)
            uuid = grant["usb_filesystem_uuid"]
            if document["phase"] != U1 and document["usb_filesystem_uuid"] != uuid:
                raise UpdaterV2Error("ha_usb_prepare_authority_drift")
            binding = self.capture_start_binding(document)
            _require_signed_predecessor(document, binding)
            if binding["launch_sha256"] != grant["launch_sha256"]:
                raise UpdaterV2Error("ha_usb_prepare_authority_drift")
            mountpoint = self._original_mountpoint(uuid)
            if document["phase"] == U1:
                capacity = measure_preparation_capacity(
                    mountpoint, store.root, uuid, document["target_archive_size"],
                )
                document = record_existing_media_bound(document, filesystem_uuid=uuid, capacity_report=capacity)
                store.write(document)
            if document["phase"] == U2:
                document = start_target_preparation(document)
                store.write(document)

            old = binding["images"]["homeassistant"]

            def capacity_admit(operation: str, required: int, available: int, passed: bool) -> None:
                latest = store.read()
                if (
                    latest is None or latest["status"] != "ACTIVE" or latest["phase"] != U3
                    or latest["transaction_id_sha256"] != document["transaction_id_sha256"]
                ):
                    raise UpdaterV2Error("ha_usb_capacity_event_transaction_drift")
                store.write(record_usb_capacity_event(
                    latest,
                    operation=operation,
                    required_bytes=required,
                    available_bytes_before=available,
                    capacity_pass=passed,
                ))

            def capacity_complete(operation: str, actual: int, available_after: int) -> None:
                latest = store.read()
                if (
                    latest is None or latest["status"] != "ACTIVE" or latest["phase"] != U3
                    or latest["transaction_id_sha256"] != document["transaction_id_sha256"]
                ):
                    raise UpdaterV2Error("ha_usb_capacity_event_transaction_drift")
                events = latest.get("usb_capacity_events", [])
                matching = [event for event in events if event["operation"] == operation]
                if not matching:
                    # A fully verified final archive may predate V1.3 (for example an
                    # in-place takeover of a pre-V1.3 U3). No V1.3 write happened in
                    # this call, so do not fabricate historical pre-write capacity
                    # evidence. New writes still require an admission event.
                    return
                if matching[-1]["actual_written_bytes"] is not None:
                    if matching[-1]["actual_written_bytes"] == actual:
                        return
                    raise UpdaterV2Error("ha_usb_capacity_event_completion_drift")
                if not events or events[-1]["operation"] != operation:
                    raise UpdaterV2Error("ha_usb_capacity_event_admission_missing")
                admission = events[-1]
                store.write(record_usb_capacity_event(
                    latest,
                    operation=operation,
                    required_bytes=admission["required_bytes"],
                    available_bytes_before=admission["available_bytes_before"],
                    capacity_pass=True,
                    actual_written_bytes=actual,
                    available_bytes_after=available_after,
                ))

            def verify_predecessor(identity: PortableImageIdentity) -> None:
                observed = self._release_image(old["reference"])
                if (
                    observed is None or observed.get("Id") != old["runtime_id"]
                    or verify_runtime_document(identity, observed).status != "VERIFIED"
                ):
                    raise UpdaterV2Error("ha_usb_preparation_predecessor_image_drift")
                expected = document["current_image_identity"].get("portable_identity_sha256")
                if expected is not None and expected != sha256_bytes(canonical(identity.to_dict())):
                    raise UpdaterV2Error("ha_usb_preparation_predecessor_archive_drift")

            try:
                target, predecessor = prepare_mounted_archives(
                    mountpoint, store.root, document,
                    target_source=lambda: self._open_target_source(Path(grant["target_source"]), document["target_archive_size"]),
                    predecessor_source=lambda: self._export_predecessor(old["reference"]),
                    measure_predecessor_size=lambda: self._measure_predecessor_archive(old["reference"]),
                    verify_predecessor=verify_predecessor,
                    capacity_admit=capacity_admit,
                    capacity_complete=capacity_complete,
                )
            except UpdaterV2Error as error:
                code = str(error)
                if code in {"ha_usb_target_space_insufficient", "ha_usb_predecessor_space_insufficient"}:
                    latest = store.read()
                    if latest is not None and latest["status"] == "ACTIVE" and latest["phase"] == U3:
                        store.write({**latest, "failure_code": code})
                raise
            latest = store.read()
            if (
                latest is None or latest["status"] != "ACTIVE" or latest["phase"] != U3
                or latest["transaction_id_sha256"] != document["transaction_id_sha256"]
                or _read_prepare_authority(store, latest) != grant
                or self.capture_start_binding(latest) != binding
            ):
                raise UpdaterV2Error("ha_usb_prepare_authority_drift")
            _retire_owned_candidate_archive(store, latest, Path(grant["target_source"]))
            store.write(record_target_ready(latest, target=target, predecessor=predecessor))
            return "READY_TO_INSTALL"

    def install_requested(self, store: HaUsbStateStore) -> str:
        document = store.read()
        if (
            document is None or document["status"] != "ACTIVE"
            or document["phase"] not in {U5, U6} or "predecessor_start" in document
            or document["recovery_required"] or document.get("usb_binding_mode") != "existing_filesystem"
        ):
            return "NO_ADMITTED_INSTALL_REQUEST"
        grant = _read_install_authority(store, document)
        authorization_sha256 = sha256_bytes(grant["authorization_id"].encode("utf-8"))
        media = self.mounted_recovery_provider(store, document, require_original=True)
        image_storage = Path(self._run(("docker", "info", "--format", "{{.DockerRootDir}}")).stdout.decode().strip())
        if not image_storage.is_absolute():
            raise UpdaterV2Error("ha_usb_install_image_storage_invalid")

        def authorize(current: dict[str, Any]) -> str:
            if (
                _read_install_authority(store, current) != grant or current["authorization_consumed"]
                or store.was_authorization_consumed(authorization_sha256)
                or ("predecessor_start" in current
                    and current["predecessor_start"]["launch_sha256"] != grant["launch_sha256"])
            ):
                raise UpdaterV2Error("ha_usb_install_authority_changed")
            if "predecessor_start" in current:
                _require_signed_predecessor(current, current["predecessor_start"])
            return grant["authorization_id"]

        materials = HaMountedInstallMaterialVerifier(
            mountpoint=media.mountpoint, internal_storage=store.root, image_storage=image_storage,
            ha_data_root=self.ha_data_root,
            verify_prestate=lambda current: self._verify_install_prestate(current, grant["launch_sha256"]),
        )
        result = HaPredecessorRecovery(store, self, self).install_requested(materials, media, authorize)
        return result["status"]

    def _verify_install_prestate(self, document: dict[str, Any], expected_launch: str) -> bool:
        binding, origins = self._restart_binding()
        _require_signed_predecessor(document, binding)
        if (
            binding["launch_sha256"] != expected_launch
            or binding["images"]["homeassistant"]["reference"] != document["current_image_ref"]
            or self.image_binding_modes_v2()["homeassistant"] != "dynamic"
            or origins["homeassistant"]["/config"] != str(self.ha_data_root.resolve(strict=True))
        ):
            return False
        counts = self._check_running_predecessor(binding, origins)
        if "predecessor_start" in document:
            return (
                binding == document["predecessor_start"] and counts["manager"] == counts["homeassistant"] == 0
                and self.rollback_writers_quiesced()
            )
        if not all(counts.values()) or self._systemctl("is-active", SERVICES_UNIT) != "active":
            return False
        old = binding["images"]["homeassistant"]
        image = self._release_image(old["runtime_id"])
        if image is None or not _exclusive_image_references(image, old["reference"]):
            raise UpdaterV2Error("ha_usb_release_predecessor_exclusive_reference_unverified")
        return True

    def verify_predecessor_health(self, document: dict[str, Any]) -> None:
        live, origins = self._restart_binding()
        if live != document["predecessor_start"]:
            raise UpdaterError("ha_usb_predecessor_launch_binding_drift")
        self._verify_rollback_health(live, origins, document)

    def _read_ha_receipts(self, container_id: str) -> bytes:
        return self._run(
            ("docker", "exec", container_id, "python3", "-I", "-c", READ_HA_RECEIPTS), timeout=5,
        ).stdout

    def _request_ha_monitoring_self_test(self, container_id: str, challenge: str, started_ns: int) -> None:
        self._run((
            "docker", "exec", container_id, "python3", "-I", "-c", REQUEST_MANAGER_SELF_TEST,
            challenge, str(started_ns),
        ), timeout=5)

    def _restart_binding(
        self, *, published: dict[str, Any] | None = None, replacement: tuple[str, str] | None = None,
        missing_predecessor: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
        self._activation_env()
        self._service_unit()
        if self._run(
            ("systemctl", "show", "--property=NeedDaemonReload", "--value", SERVICES_UNIT)
        ).stdout.strip() != b"no":
            raise UpdaterError("ha_usb_predecessor_service_configuration_unloaded")
        unit = self._run(("systemctl", "cat", SERVICES_UNIT)).stdout
        compose = self.render_compose()
        references, modes = self._image_binding_authority_v2(compose)
        if replacement is not None:
            expected, predecessor = replacement
            if references["homeassistant"] != expected or modes.get("homeassistant") != "dynamic":
                raise UpdaterError("ha_usb_rollback_compose_binding_drift")
            compose = copy.deepcopy(compose)
            compose["services"]["homeassistant"]["image"] = predecessor
            references = {**references, "homeassistant": predecessor}
        images = {}
        for name, reference in references.items():
            if compose["services"][name].get("pull_policy") != "never":
                raise UpdaterError("ha_usb_predecessor_image_pull_allowed")
            if name in PROTECTED_BINDS and compose["services"][name].get("restart", "no") != "no":
                raise UpdaterError("ha_usb_unguarded_container_restart_enabled")
            runtime_id = self.image_id(reference)
            if (
                runtime_id is None and name == "homeassistant" and missing_predecessor is not None
                and reference == missing_predecessor["reference"]
            ):
                runtime_id = missing_predecessor["runtime_id"]
            if runtime_id is None:
                raise UpdaterError("ha_usb_predecessor_local_image_missing")
            images[name] = {"reference": reference, "runtime_id": runtime_id}

        protected = {}
        origins = {}
        for name, targets in PROTECTED_BINDS.items():
            paths = {}
            for mount in compose["services"][name].get("volumes", []):
                target = mount.get("target")
                if target not in targets:
                    continue
                raw_source = mount.get("source")
                if mount.get("type") != "bind" or not isinstance(raw_source, str):
                    raise UpdaterError("ha_usb_predecessor_protected_bind_invalid")
                source = Path(raw_source)
                if target in paths or not source.is_absolute() or not source.is_dir():
                    raise UpdaterError("ha_usb_predecessor_protected_bind_invalid")
                real_source = source.resolve(strict=True)
                inode = real_source.stat().st_ino
                filesystem = os.statvfs(real_source).f_fsid
                if name == "homeassistant" and published is not None:
                    if (
                        real_source != self.ha_data_root.resolve(strict=True)
                        or filesystem != published["filesystem_id"]
                        or inode != published["staged_inode"]
                    ):
                        raise UpdaterError("ha_usb_rollback_published_data_binding_drift")
                    # Compare the complete frozen launch contract with only the proven inode exchange normalized.
                    inode = published["original_inode"]
                paths[target] = (str(real_source), inode, filesystem)
            if paths.keys() != targets:
                raise UpdaterError("ha_usb_predecessor_protected_bind_missing")
            protected[name] = paths
            origins[name] = {target: value[0] for target, value in paths.items()}

        launch = {
            "compose": compose,
            "unit_sha256": sha256_bytes(unit),
            "protected": protected,
        }
        binding = {"launch_sha256": sha256_bytes(canonical(launch)), "images": images}
        return binding, origins

    def _check_running_predecessor(
        self, binding: dict[str, Any], origins: dict[str, dict[str, str]],
        *, observed: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        counts = {name: self._running_count(name) for name in COMPONENTS}
        if counts["broker"] != 1 or any(count > 1 for count in counts.values()):
            raise UpdaterError("ha_usb_predecessor_service_count_invalid")
        for name, count in counts.items():
            if count == 1:
                runtime = self._runtime(name)
                if binding["images"][name] != {
                    "reference": runtime["image_ref"],
                    "runtime_id": runtime["image_id"],
                }:
                    raise UpdaterError("ha_usb_predecessor_running_image_drift")
                if name in origins:
                    self._check_protected_mounts(runtime["container_id"], origins[name])
                if observed is not None:
                    observed[name] = runtime
        return counts

    def _check_protected_mounts(self, container_id: str, origins: dict[str, str]) -> None:
        raw = self._run(
            ("docker", "inspect", "--format", "{{json .Mounts}}", container_id)
        ).stdout
        mounts = json.loads(raw)
        if not isinstance(mounts, list) or not all(isinstance(m, dict) for m in mounts):
            raise UpdaterError("ha_usb_predecessor_running_mounts_invalid")
        for target, source in origins.items():
            matches = [m for m in mounts if m.get("Destination") == target]
            if len(matches) != 1:
                raise UpdaterError("ha_usb_predecessor_running_mount_drift")
            mount = matches[0]
            raw_source = mount.get("Source")
            if (
                mount.get("Type") != "bind"
                or mount.get("RW") is not True
                or not isinstance(raw_source, str)
                or str(Path(raw_source).resolve(strict=True)) != source
            ):
                raise UpdaterError("ha_usb_predecessor_running_mount_drift")

    def capture_start_binding(self, transaction: dict[str, Any]) -> dict[str, Any]:
        self.require_recovery_install()
        binding, origins = self._restart_binding()
        expected_runtime_id = transaction.get("current_image_identity", {}).get(
            "runtime_image_id", binding["images"]["homeassistant"]["runtime_id"],
        )
        if (
            binding["images"]["homeassistant"]["reference"]
            != transaction["current_image_ref"]
            or expected_runtime_id != binding["images"]["homeassistant"]["runtime_id"]
            or origins["homeassistant"]["/config"] != str(self.ha_data_root.resolve(strict=True))
            or self._systemctl("is-active", SERVICES_UNIT) != "active"
            or not all(self._check_running_predecessor(binding, origins).values())
        ):
            raise UpdaterError("ha_usb_predecessor_start_binding_unavailable")
        return binding

    def quiesce_for_backup(self) -> None:
        self.stop_services()

    def start_predecessor_if_needed(self, binding: dict[str, Any]) -> None:
        live_binding, origins = self._restart_binding()
        if live_binding != binding:
            raise UpdaterError("ha_usb_predecessor_launch_binding_drift")
        self._check_running_predecessor(binding, origins)
        owner = self._systemctl("is-active", SERVICES_UNIT)
        if owner in {"active", "activating"}:
            return
        if owner not in {"inactive", "failed"}:
            raise UpdaterError("ha_usb_predecessor_service_state_unresolved")
        self._run(("systemctl", "start", SERVICES_UNIT), timeout=180)

    def require_rollback_boot_guard(self) -> None:
        raw = self._run(("systemctl", "cat", SERVICES_UNIT)).stdout.decode()
        if BOOT_CONDITION not in raw.splitlines() or self._run(
            ("systemctl", "show", "--property=NeedDaemonReload", "--value", SERVICES_UNIT)
        ).stdout.strip() != b"no":
            raise UpdaterError("ha_usb_rollback_boot_guard_unavailable")

    def require_recovery_install(self) -> None:
        self.require_rollback_boot_guard()
        for unit, command in (
            (RECOVERY_STARTUP_UNIT, f"ExecStart={RECOVERY_COMMAND}"),
            (RECOVERY_RETRY_UNIT, f"ExecStart={RECOVERY_COMMAND} --resume-pending"),
        ):
            raw = self._run(("systemctl", "cat", unit)).stdout.decode()
            starts = [line.strip() for line in raw.splitlines() if line.strip().startswith("ExecStart=")]
            if starts != [command] or self._run(
                ("systemctl", "show", "--property=NeedDaemonReload", "--value", unit)
            ).stdout.strip() != b"no":
                raise UpdaterError("ha_usb_recovery_unit_unavailable")
        if (
            self._systemctl("is-enabled", RECOVERY_STARTUP_UNIT) != "enabled"
            or self._systemctl("is-enabled", RECOVERY_TIMER) != "enabled"
            or self._systemctl("is-active", RECOVERY_TIMER) != "active"
        ):
            raise UpdaterError("ha_usb_recovery_timer_not_armed")
        help_text = self._run(("/usr/bin/python3", "-I", RECOVERY_ARCHIVE, "--help"), timeout=10).stdout
        if not all(option in help_text for option in (b"--check-application-start", b"--resume-pending")):
            raise UpdaterError("ha_usb_recovery_program_unavailable")

    def rollback_writers_quiesced(self) -> bool:
        return (
            self._systemctl("is-active", SERVICES_UNIT) in {"inactive", "failed"}
            and self._running_count("manager") == 0
            and self._running_count("homeassistant") == 0
        )

    def _release_image(self, reference: str) -> dict[str, Any] | None:
        observation = observe_docker_image(reference, runner=lambda argv, **kwargs: self._run(
            argv, timeout=kwargs["timeout"], check=False,
        ))
        if observation.status == "AVAILABLE" and observation.document is not None:
            return observation.document
        if observation.status == "NOT_FOUND":
            return None
        raise UpdaterError("ha_usb_release_image_observation_unavailable")

    def observe_predecessor_released(self, document: dict[str, Any]) -> bool:
        old = document["predecessor_start"]["images"]["homeassistant"]
        target = self._release_image(document["target_image_ref"])
        if target is not None:
            proof = document.get("target_load_identity")
            if proof is None:
                raise UpdaterError("ha_usb_release_target_image_already_present")
            observed_id = self._verify_target_image(document, identity_from_dict(proof), target)
            if document.get("target_loaded_image_id", observed_id) != observed_id:
                raise UpdaterError("ha_usb_target_image_runtime_drift")
        tagged = self._release_image(old["reference"])
        by_id = self._release_image(old["runtime_id"])
        if tagged is None and by_id is None:
            listed = self._run(("docker", "image", "ls", "--all", "--no-trunc", "--quiet"), timeout=30).stdout
            counts = self._check_running_predecessor(document["predecessor_start"], {})
            if (
                old["runtime_id"] in listed.decode().split() or self.component_container_residue("homeassistant")
                or counts["homeassistant"] or counts["manager"]
            ):
                raise UpdaterError("ha_usb_release_image_absence_unconfirmed")
            return True
        if tagged is None or by_id is None or any(
            image.get("Id") != old["runtime_id"] for image in (tagged, by_id)
        ):
            raise UpdaterError("ha_usb_release_predecessor_image_binding_drift")
        return False

    def _verify_original_launch(
        self, document: dict[str, Any], *, allow_target_binding: bool,
    ) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
        expected = document["predecessor_start"]
        old = expected["images"]["homeassistant"]
        missing = old if self._release_image(old["reference"]) is None else None
        binding, origins = self._restart_binding(
            replacement=self._target_replacement(document) if allow_target_binding else None,
            missing_predecessor=missing,
        )
        if binding != expected:
            raise UpdaterError("ha_usb_predecessor_launch_binding_drift")
        return binding, origins

    def _target_replacement(self, document: dict[str, Any]) -> tuple[str, str] | None:
        target = document["target_image_ref"]
        if self.image_bindings_v2()["homeassistant"] == target:
            return target, document["current_image_ref"]
        return None

    def restore_untouched_launch_binding(self, document: dict[str, Any]) -> None:
        replacement = self._target_replacement(document)
        if replacement is not None:
            if not self.rollback_writers_quiesced():
                raise UpdaterError("ha_usb_rollback_application_not_quiesced")
            self.verify_untouched_release_launch(document)
            self.rewrite_component_image("homeassistant", *replacement)

    def check_cutover_target_start(
        self, document: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
        if self._target_replacement(document) is None:
            raise UpdaterError("ha_usb_target_launch_binding_missing")
        binding, origins = self._verify_original_launch(document, allow_target_binding=True)
        target = document["target_image_ref"]
        image_id = self._verify_target_image(
            document, identity_from_dict(document["target_load_identity"]), self._release_image(target),
        )
        if image_id != document["target_loaded_image_id"]:
            raise UpdaterError("ha_usb_target_image_runtime_drift")
        binding["images"]["homeassistant"] = {"reference": target, "runtime_id": image_id}
        return binding, origins

    def bind_cutover_target(self, document: dict[str, Any]) -> None:
        self.require_rollback_boot_guard()
        if (
            not self.rollback_writers_quiesced() or not self.observe_predecessor_released(document)
            or self.image_binding_modes_v2()["homeassistant"] != "dynamic"
        ):
            raise UpdaterError("ha_usb_target_activation_prestate_changed")
        self.verify_untouched_release_launch(document)
        self.rewrite_component_image("homeassistant", document["current_image_ref"], document["target_image_ref"])
        self.check_cutover_target_start(document)

    def start_cutover_target(self) -> None:
        self._run(("systemctl", "start", SERVICES_UNIT), timeout=180)

    def verify_cutover_target_started(self, document: dict[str, Any]) -> None:
        binding, origins = self.check_cutover_target_start(document)
        deadline = time.monotonic() + DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._systemctl("is-active", SERVICES_UNIT) == "active" and all(
                self._check_running_predecessor(binding, origins).values()
            ):
                self.check_cutover_target_start(document)
                return
            time.sleep(2)
        raise UpdaterError("ha_usb_target_start_not_observed")

    def target_acceptance_runtime(self, document: dict[str, Any]) -> str:
        binding, origins = self.check_cutover_target_start(document)
        observed: dict[str, dict[str, Any]] = {}
        if self._systemctl("is-active", SERVICES_UNIT) != "active" or not all(
            self._check_running_predecessor(binding, origins, observed=observed).values()
        ):
            raise UpdaterError("ha_usb_target_acceptance_runtime_unavailable")
        instances = {
            name: [runtime[key] for key in ("container_id", "started_at", "restart_count", "runtime_contract_sha256")]
            for name, runtime in observed.items()
        }
        return sha256_bytes(canonical({
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "binding": binding,
            "instances": instances,
        }))

    def verify_untouched_release_launch(self, document: dict[str, Any]) -> None:
        binding, origins = self._verify_original_launch(
            document, allow_target_binding=document.get("target_activation") == TARGET_BINDING,
        )
        self._check_running_predecessor(binding, origins)

    def load_cutover_target(
        self, document: dict[str, Any], media: HaDataRestoreProvider,
        record_load_intent: Callable[[PortableImageIdentity], None],
    ) -> str:
        if (
            document["phase"] != U10 or document.get("predecessor_release_observed") is not True
            or "target_load_identity" in document or not destructive_cutover_allowed(document)
            or not self.rollback_writers_quiesced() or not self.observe_predecessor_released(document)
        ):
            raise UpdaterError("ha_usb_target_image_load_not_admitted")
        self.require_rollback_boot_guard()
        self.verify_untouched_release_launch(document)

        def load_with_intent(source: BinaryIO, identity: PortableImageIdentity) -> None:
            if not self.rollback_writers_quiesced() or not self.observe_predecessor_released(document):
                raise UpdaterError("ha_usb_target_image_load_prestate_changed")
            record_load_intent(identity)
            self._load_ha_image(source)

        identity = media.load_target_image(load_with_intent)
        return self._verify_target_image(document, identity, self._release_image(document["target_image_ref"]))

    @staticmethod
    def _verify_target_image(
        document: dict[str, Any], identity: PortableImageIdentity, image: dict[str, Any] | None,
    ) -> str:
        if image is None:
            raise UpdaterError("ha_usb_target_loaded_image_unconfirmed")
        verdict = verify_runtime_document(identity, image)
        image_id = verdict.runtime_image_id
        if (
            verdict.status != "VERIFIED" or image_id is None or IMAGE_ID.fullmatch(image_id) is None
            or image_id == document["predecessor_start"]["images"]["homeassistant"]["runtime_id"]
        ):
            raise UpdaterError("ha_usb_target_image_runtime_drift")
        return image_id

    def capture_predecessor_release(self, document: dict[str, Any]) -> HaPredecessorRelease:
        self.require_rollback_boot_guard()
        if self.image_binding_modes_v2()["homeassistant"] != "dynamic":
            raise UpdaterError("ha_usb_target_dynamic_binding_required")
        binding, origins = self._restart_binding()
        if binding != document["predecessor_start"] or not self.rollback_writers_quiesced():
            raise UpdaterError("ha_usb_release_predecessor_launch_drift")
        self._check_running_predecessor(binding, origins)
        old = binding["images"]["homeassistant"]
        image = self._release_image(old["runtime_id"])
        if (
            image is None or self.observe_predecessor_released(document)
            or not _exclusive_image_references(image, old["reference"])
        ):
            raise UpdaterError("ha_usb_release_predecessor_exclusive_reference_unverified")
        residue = self.component_container_residue("homeassistant")
        if len(residue) > 1:
            raise UpdaterError("ha_usb_release_predecessor_container_ambiguous")
        container_id = None
        if residue:
            container = residue[0]
            container_id = container["container_id"]
            if (
                SHA256.fullmatch(container_id) is None or container["status"] != "exited" or container["replace"]
                or (container["image_ref"], container["image_id"]) != (old["reference"], old["runtime_id"])
            ):
                raise UpdaterError("ha_usb_release_predecessor_container_drift")
            self._check_protected_mounts(container_id, origins["homeassistant"])
        users = self._run((
            "docker", "ps", "--all", "--no-trunc", "--quiet", "--filter", f'ancestor={old["runtime_id"]}',
        ), timeout=30).stdout.decode().split()
        if users != ([container_id] if container_id is not None else []):
            raise UpdaterError("ha_usb_release_predecessor_has_other_users")
        return HaPredecessorRelease(container_id)

    def release_exact_predecessor(self, document: dict[str, Any]) -> None:
        if (
            document["phase"] != U9 or "predecessor_release_intent" not in document
            or not destructive_cutover_allowed(document)
        ):
            raise UpdaterError("ha_usb_release_action_not_admitted")
        candidate = self.capture_predecessor_release(document)
        if candidate.container_id != document["predecessor_release_intent"]["container_id"]:
            raise UpdaterError("ha_usb_release_predecessor_container_drift")
        if candidate.container_id is not None:
            self._run(("docker", "container", "rm", candidate.container_id), timeout=120)
        if self.capture_predecessor_release(document).container_id is not None:
            raise UpdaterError("ha_usb_release_predecessor_container_still_present")
        exact_id = document["predecessor_start"]["images"]["homeassistant"]["runtime_id"]
        self._run(("docker", "image", "rm", "--no-prune", exact_id), timeout=300)

    def quiesce_for_data_restore(self, document: dict[str, Any]) -> None:
        before = document["predecessor_start"]["images"]["broker"]
        if self._running_count("broker") != 1:
            raise UpdaterError("ha_usb_rollback_broker_unavailable")
        broker = self._runtime("broker")
        if (broker["image_ref"], broker["image_id"]) != (before["reference"], before["runtime_id"]):
            raise UpdaterError("ha_usb_rollback_broker_binding_drift")
        if not self.rollback_writers_quiesced():
            self.stop_services()
        if not self.rollback_writers_quiesced():
            raise UpdaterError("ha_usb_rollback_application_not_quiesced")
        if "predecessor_release_intent" in document and "ha_data_restore" not in document:
            self._verify_original_launch(document, allow_target_binding=True)

    def _rollback_target_image(self, document: dict[str, Any]) -> dict[str, Any] | None:
        reference = document["target_image_ref"]
        image = self._release_image(reference)
        proof = document.get("target_load_identity")
        recorded_id = document.get("target_release_image_id") or document.get("target_loaded_image_id")
        if image is None:
            if recorded_id is not None:
                return self._release_image(recorded_id)
            if proof is not None and self._release_image(identity_from_dict(proof).config_digest) is not None:
                raise UpdaterError("ha_usb_rollback_untagged_target_ownership_unverified")
        return image

    def capture_rollback_target(self, document: dict[str, Any]) -> str | None:
        image = self._rollback_target_image(document)
        if image is None:
            return None
        proof = document.get("target_load_identity")
        if proof is None:
            raise UpdaterError("ha_usb_rollback_target_ownership_unverified")
        reference = document["target_image_ref"]
        image_id = self._verify_target_image(document, identity_from_dict(proof), image)
        if (
            document.get("target_loaded_image_id", image_id) != image_id
            or not _exclusive_image_references(image, reference, allow_untagged=True)
        ):
            raise UpdaterError("ha_usb_rollback_target_exclusive_reference_unverified")
        return image_id

    def release_rollback_target(self, document: dict[str, Any]) -> None:
        if (
            document.get("target_release_step") != "INTENT" or document.get("recovery_required") is not True
            or document.get("predecessor_release_observed") is not True
            or not self.rollback_writers_quiesced()
        ):
            raise UpdaterError("ha_usb_rollback_target_release_not_admitted")
        image_id = self.capture_rollback_target(document)
        if image_id is None:
            return
        if image_id != document["target_release_image_id"]:
            raise UpdaterError("ha_usb_rollback_target_release_identity_drift")
        reference = document["target_image_ref"]
        residue = self.component_container_residue("homeassistant")
        if len(residue) > 1:
            raise UpdaterError("ha_usb_rollback_target_container_ambiguous")
        containers = []
        if residue:
            container = residue[0]
            container_id = container["container_id"]
            if (
                SHA256.fullmatch(container_id) is None or container["status"] not in {"created", "exited"}
                or container["replace"] or (container["image_ref"], container["image_id"]) != (reference, image_id)
            ):
                raise UpdaterError("ha_usb_rollback_target_container_drift")
            self._check_protected_mounts(container_id, {"/config": str(self.ha_data_root)})
            containers.append(container_id)
        users = self._run((
            "docker", "ps", "--all", "--no-trunc", "--quiet", "--filter", f"ancestor={image_id}",
        ), timeout=30).stdout.decode().split()
        if users != containers or not self.rollback_writers_quiesced():
            raise UpdaterError("ha_usb_rollback_target_has_other_users")
        if containers:
            self._run(("docker", "container", "rm", containers[0]), timeout=120)
        if (
            not self.rollback_writers_quiesced()
            or self.capture_rollback_target(document) != image_id
        ):
            raise UpdaterError("ha_usb_rollback_target_release_prestate_changed")
        self._run(("docker", "image", "rm", "--no-prune", image_id), timeout=300)
        if self._rollback_target_image(document) is not None or self._release_image(image_id) is not None:
            raise UpdaterError("ha_usb_rollback_target_release_not_observed")

    def _verify_published_launch(
        self, document: dict[str, Any], *, replacement: tuple[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
        journal = document["ha_data_restore"]
        if journal["step"] != "PUBLISHED":
            raise UpdaterError("ha_usb_rollback_data_not_published")
        binding, origins = self._restart_binding(published=journal, replacement=replacement)
        if binding != document["predecessor_start"]:
            raise UpdaterError("ha_usb_predecessor_launch_binding_drift")
        return binding, origins

    def check_rollback_application_start(self, document: dict[str, Any]) -> None:
        self._verify_published_launch(document)
        value = document["ha_data_restore"].get("predecessor_load_identity")
        if value is not None:
            self._verify_loaded_predecessor(document, identity_from_dict(value))

    def _predecessor_image_absent(self, reference: str) -> bool:
        return self._release_image(reference) is None

    @staticmethod
    def _load_ha_image(source: BinaryIO) -> None:
        with subprocess.Popen(
            ("docker", "image", "load", "--quiet"), stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) as process:
            assert process.stdin is not None
            timeout = threading.Timer(IMAGE_LOAD_TIMEOUT_SECONDS, process.kill)
            timeout.start()
            try:
                with process.stdin as sink:
                    shutil.copyfileobj(source, sink, length=1024 * 1024)
                if process.wait() != 0:
                    raise UpdaterError("ha_usb_image_load_failed")
            finally:
                timeout.cancel()
                if process.poll() is None:
                    process.kill()

    def ensure_rollback_predecessor(
        self, document: dict[str, Any], original_media: Callable[[], HaDataRestoreProvider],
        record_load_intent: Callable[[PortableImageIdentity], None],
    ) -> None:
        binding = document["predecessor_start"]["images"]["homeassistant"]
        reference, expected_id = binding["reference"], binding["runtime_id"]
        local_id = self.image_id(reference)
        if "recovery_workspace_bytes" in document.get("predecessor_release_admission", {}) and (
            document.get("target_release_step") != "RELEASED" or self._rollback_target_image(document) is not None
        ):
            raise UpdaterError("ha_usb_rollback_target_release_not_observed")
        if local_id == expected_id:
            value = document.get("predecessor_reload_identity") or document.get("ha_data_restore", {}).get("predecessor_load_identity")
            if value is not None:
                self._verify_loaded_predecessor(document, identity_from_dict(value))
            return
        if local_id is not None:
            raise UpdaterError("ha_usb_rollback_predecessor_image_tag_drift")
        if not self._predecessor_image_absent(reference):
            raise UpdaterError("ha_usb_rollback_predecessor_image_lookup_unavailable")
        if not self.rollback_writers_quiesced():
            raise UpdaterError("ha_usb_rollback_image_load_writers_not_quiesced")
        def load_with_intent(source: BinaryIO, identity: PortableImageIdentity) -> None:
            record_load_intent(identity)
            self._load_ha_image(source)

        identity = original_media().load_predecessor_image(load_with_intent)
        self._verify_loaded_predecessor(document, identity)

    def _verify_loaded_predecessor(self, document: dict[str, Any], identity: PortableImageIdentity) -> None:
        binding = document["predecessor_start"]["images"]["homeassistant"]
        loaded = self._image_document(binding["reference"])
        if loaded is None:
            raise UpdaterError("ha_usb_rollback_predecessor_image_load_unconfirmed")
        verdict = verify_runtime_document(identity, loaded)
        if verdict.status != "VERIFIED" or verdict.runtime_image_id != binding["runtime_id"]:
            raise UpdaterError("ha_usb_rollback_predecessor_loaded_image_drift")

    def resume_published_predecessor(self, document: dict[str, Any]) -> None:
        observed = self.image_bindings_v2()["homeassistant"]
        predecessor, target = document["current_image_ref"], document["target_image_ref"]
        if observed == target:
            self._verify_published_launch(document, replacement=(target, predecessor))
            if not self.rollback_writers_quiesced():
                raise UpdaterError("ha_usb_rollback_published_data_may_have_target_writes")
            self.rewrite_component_image("homeassistant", target, predecessor)
        binding, origins = self._verify_published_launch(document)
        counts = self._check_running_predecessor(binding, origins)
        owner = self._systemctl("is-active", SERVICES_UNIT)
        if owner in {"active", "activating"}:
            return
        if owner not in {"inactive", "failed"} or counts["manager"] or counts["homeassistant"]:
            raise UpdaterError("ha_usb_predecessor_service_state_unresolved")
        self._run(("systemctl", "start", SERVICES_UNIT), timeout=180)

    def verify_published_predecessor_health(self, document: dict[str, Any]) -> None:
        binding, origins = self._verify_published_launch(document)
        self._verify_rollback_health(binding, origins, document)

    def verify_resident_predecessor_health(self, document: dict[str, Any]) -> None:
        binding, origins = self._restart_binding()
        if binding != document["predecessor_start"]:
            raise UpdaterError("ha_usb_predecessor_launch_binding_drift")
        self._verify_rollback_health(binding, origins, document)

    @staticmethod
    def _verify_restored_data(document: dict[str, Any], origins: dict[str, dict[str, str]]) -> None:
        sample = document.get("target_acceptance", {}).get("data_sample")
        if sample is None:
            return
        if _protected_data_evidence(origins).compare(sample) != "PASS":
            raise UpdaterError("ha_usb_rollback_protected_data_evidence_pending")

    def _verify_recovered_monitoring(self, document: dict[str, Any], origins: dict[str, dict[str, str]]) -> None:
        state = document.get("target_acceptance", {})
        if "monitoring_method" not in state:
            return
        monitoring = self._monitoring_evidence(origins)
        evidence = monitoring.observe(document, fallback=False)
        if evidence.verdict == "EVIDENCE_UNAVAILABLE" and monitoring_self_test_qualified(state):
            evidence = monitoring.run_self_test()
        if evidence.verdict != "PASS":
            # The recovery journal stays published. The retry worker checks
            # the running predecessor without applying the restore again.
            raise HaRecoveryMonitoringPending("ha_usb_rollback_monitoring_evidence_pending")

    def _verify_rollback_health(
        self, binding: dict[str, Any], origins: dict[str, dict[str, str]], document: dict[str, Any],
    ) -> None:
        # Existing records without a frozen monitoring method still use their original checks.
        legacy = "monitoring_method" not in document.get("target_acceptance", {})
        deadline = time.monotonic() + DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if (
                self._systemctl("is-active", SERVICES_UNIT) == "active"
                and all(self._check_running_predecessor(binding, origins).values())
                and (
                    not legacy or (
                        self._homeassistant_http_status(allow_unavailable=True) in {200, 401}
                        and all(self._mqtt_authenticated(name) for name in ("manager", "homeassistant"))
                    )
                )
            ):
                self._verify_restored_data(document, origins)
                self._verify_recovered_monitoring(document, origins)
                return
            time.sleep(2)
        raise UpdaterError("ha_usb_rollback_predecessor_health_pending")

    def _original_mountpoint(self, uuid: str) -> Path:
        result = self._run((
            "findmnt", "--list", "--json", "--source", f"UUID={uuid}", "--output", "TARGET",
        ), timeout=10, check=False)
        if result.returncode == 1:
            raise HaRecoveryMediaRequired("ha_usb_rollback_original_mount_required")
        if result.returncode:
            raise UpdaterError("ha_usb_rollback_mount_discovery_failed")
        result_document = json.loads(result.stdout)
        filesystems = result_document.get("filesystems") if isinstance(result_document, dict) else None
        if filesystems == []:
            raise HaRecoveryMediaRequired("ha_usb_rollback_original_mount_required")
        if not isinstance(filesystems, list) or len(filesystems) != 1:
            raise UpdaterError("ha_usb_rollback_mount_discovery_failed")
        filesystem = filesystems[0]
        target = filesystem.get("target") if isinstance(filesystem, dict) else None
        if not isinstance(target, str) or not Path(target).is_absolute():
            raise UpdaterError("ha_usb_rollback_mount_discovery_failed")
        return Path(target)

    def mounted_recovery_provider(
        self, store: HaUsbStateStore, document: dict[str, Any], *, require_original: bool = False,
    ) -> HaMountedBackupProvider:
        mountpoint = store.root
        if require_original or document.get("ha_data_restore", {}).get("step", "STAGING") == "STAGING":
            mountpoint = self._original_mountpoint(document["usb_filesystem_uuid"])
        return HaMountedBackupProvider(
            store=store, mountpoint=mountpoint, internal_storage=store.root,
            backup=ProtectedHaDataBackup(work_root=store.root, ha_data_root=self.ha_data_root),
            verify_quiesced=self.rollback_writers_quiesced,
        )

    @contextmanager
    def mount_original_for_recovery(
        self, store: HaUsbStateStore, document: dict[str, Any],
    ) -> Iterator[None]:
        device = bound_usb_device(document["usb_filesystem_uuid"].lower(), store.root)
        if device is None:
            raise HaRecoveryMediaRequired("ha_usb_rollback_original_mount_required")
        name = device.get("name")
        if device.get("fstype") != USB_FILESYSTEM or not isinstance(name, str):
            raise UpdaterError("ha_usb_rollback_original_filesystem_invalid")
        path = Path(name)
        if path.parent != Path("/dev"):
            raise UpdaterError("ha_usb_rollback_original_device_path_invalid")
        metadata = path.lstat()
        if (
            not stat.S_ISBLK(metadata.st_mode)
            or f"{os.major(metadata.st_rdev)}:{os.minor(metadata.st_rdev)}" != device["maj:min"]
        ):
            raise UpdaterError("ha_usb_rollback_original_device_changed")

        # The retry unit isolates this mount from the host. Skip ext4 journal replay.
        mountpoint = Path(tempfile.mkdtemp(prefix="n3w-ha-recovery-", dir="/run"))
        try:
            self._run((
                "mount", "--internal-only", "-t", USB_FILESYSTEM,
                "-o", "ro,noload,nodev,nosuid,noexec", "--", str(path), str(mountpoint),
            ), timeout=10)
            try:
                yield
            finally:
                self._run(("umount", "--", str(mountpoint)), timeout=10)
        finally:
            mountpoint.rmdir()


def check_application_start(store: HaUsbStateStore, runtime: LocalHaPredecessorRuntime) -> int:
    # The recovery worker may hold the transaction lock while systemd evaluates this condition.
    document = store.read()
    if document and ha_data_rollback_required(document):
        if (
            document["phase"] == U10 and document.get("target_activation") == TARGET_WRITES_POSSIBLE
            and destructive_cutover_allowed(document)
            and store.take_target_start_permit(document["transaction_id_sha256"])
        ):
            runtime.check_cutover_target_start(document)
            return 0
        if document["status"] != "ACTIVE" or document.get("ha_data_restore", {}).get("step") != "PUBLISHED":
            return 1
        runtime.check_rollback_application_start(document)
    elif document and document["phase"] in {U9, U10} and "predecessor_release_intent" in document:
        if (
            document["status"] != "ACTIVE" or not document["recovery_required"]
        ):
            return 1
        binding, _ = runtime._restart_binding()
        if binding != document["predecessor_start"]:
            return 1
        if "predecessor_reload_identity" in document:
            runtime._verify_loaded_predecessor(document, identity_from_dict(document["predecessor_reload_identity"]))
    return 0


def _dispatch_pending_candidate(store: HaUsbStateStore, runtime: LocalHaPredecessorRuntime) -> str:
    document = store.read()
    if document is None or document["status"] != "ACTIVE" or document["recovery_required"]:
        return "NO_PENDING_RECOVERY"
    capacity_failures = {
        "ha_usb_target_space_insufficient": "target_archive",
        "ha_usb_predecessor_space_insufficient": "predecessor_archive",
    }
    failure = document.get("failure_code")
    if document["phase"] == U3 and failure in capacity_failures:
        operation = capacity_failures[failure]
        events = document.get("usb_capacity_events", [])
        matching = [
            event for event in events
            if event["operation"] == operation and event["capacity_pass"] is False
        ]
        if not matching:
            raise UpdaterV2Error("ha_usb_capacity_block_evidence_missing")
        blocked = matching[-1]
        mountpoint = runtime._original_mountpoint(document["usb_filesystem_uuid"])
        report = measure_preparation_capacity(
            mountpoint, store.root, document["usb_filesystem_uuid"], blocked["required_bytes"],
        )
        if report.capacity_pass is not True:
            return "PREPARE_WAITING_FOR_USB_SPACE"
        with store.lock():
            latest = store.read()
            if (
                latest is None or latest["status"] != "ACTIVE" or latest["phase"] != U3
                or latest.get("failure_code") != failure
            ):
                raise UpdaterV2Error("ha_usb_capacity_block_transaction_drift")
            store.write({
                **latest,
                "failure_code": None,
                "updated_at_unix": max(latest["updated_at_unix"], int(time.time())),
            })
        document = store.read()
    prepare_authority = store.root / PREPARE_AUTHORITY_FILE
    if document["phase"] in {U1, U2, U3} and prepare_authority.exists():
        raw_authority = _read_authority_file(
            prepare_authority, "ha_usb_prepare_authority_invalid"
        )
        if raw_authority.get("transaction_id_sha256") != document["transaction_id_sha256"]:
            return "PREPARE_WAITING_FOR_AUTHORITY"
        return runtime.prepare_requested(store)
    if (
        document["phase"] in {U5, U6} and "predecessor_start" not in document
        and (store.root / INSTALL_AUTHORITY_FILE).exists()
    ):
        return runtime.install_requested(store)
    return "NO_PENDING_RECOVERY"


def retire_pre_cutover_failure(
    store: HaUsbStateStore,
    runtime: LocalHaPredecessorRuntime,
) -> dict[str, object]:
    """Close a proven no-mutation U4 failure so checker/runtime repair can proceed."""
    authority_path = store.root / INSTALL_AUTHORITY_FILE
    with store.lock():
        document = store.read()
        if document is None:
            raise UpdaterV2Error("ha_usb_pre_cutover_failure_transaction_missing")
        if (
            document["phase"] != U4
            or document.get("failure_code") not in {
                "ha_usb_predecessor_acceptance_baseline_unavailable",
                "ha_usb_install_revalidation_failed",
            }
            or document["recovery_required"]
            or document["authorization_claimed"]
            or document["authorization_consumed"]
            or document.get("authorization_id_sha256") is not None
            or "predecessor_start" in document
        ):
            raise UpdaterV2Error("ha_usb_pre_cutover_failure_retirement_not_admitted")
        if document["status"] not in {"ACTIVE", "ROLLED_BACK"}:
            raise UpdaterV2Error("ha_usb_pre_cutover_failure_retirement_not_admitted")

        binding = runtime.capture_start_binding(document)
        _require_signed_predecessor(document, binding)
        if runtime._release_image(document["target_image_ref"]) is not None:
            raise UpdaterV2Error("ha_usb_pre_cutover_failure_target_image_present")

        if authority_path.exists():
            grant = _read_authority_file(authority_path, "ha_usb_install_authority_invalid")
            _validate_install_authority(grant, document)
            if grant.get("launch_sha256") != binding["launch_sha256"]:
                raise UpdaterV2Error("ha_usb_install_authority_invalid")

        if document["status"] == "ACTIVE":
            document = record_pre_cutover_failure_terminal(document)
            store.write(document)

        if authority_path.exists():
            authority_path.unlink()
            parent = os.open(store.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)

        return {
            "status": "PRE_CUTOVER_FAILURE_RETIRED",
            "transaction_status": document["status"],
            "transaction_phase": document["phase"],
            "failure_code": document["failure_code"],
            "install_authority_present": authority_path.exists(),
            "authorization_claimed": document["authorization_claimed"],
            "authorization_consumed": document["authorization_consumed"],
        }


def maintenance_submit_approved_release(
    store: HaUsbStateStore,
    runtime: LocalHaPredecessorRuntime,
    *,
    action: str,
    release_identity: str,
) -> dict[str, object]:
    """Submit an operator-maintenance intent through the durable HA transaction executor.

    This intentionally bypasses the Manager's user-facing version ordering only.
    Candidate admission, release pinning, transaction persistence, recovery ownership,
    and every destructive install boundary remain unchanged.
    """
    resolver = LocalApprovedHaRelease(
        store.root / RELEASE_PIN,
        IPC_SOCKET.with_name(APPROVED_MANIFEST),
        lambda: runtime._runtime("homeassistant"),
    )
    return HaUsbIpcExecutor(store=store, admission_resolver=resolver).submit(
        action, release_identity,
    )


def main(
    *, application_condition: bool = False, pending_only: bool = False,
    install_requested: bool = False, serve_ipc: bool = False,
) -> int:
    store = HaUsbStateStore()
    runtime = LocalHaPredecessorRuntime()
    try:
        if application_condition:
            return check_application_start(store, runtime)
        if serve_ipc:
            serve_activated_ha_ipc(store, lambda: runtime._runtime("homeassistant"))
            return 0
        if install_requested:
            status = runtime.install_requested(store)
            print(json.dumps({"status": status}))
            return 0
        with ExitStack() as mounts:
            def provider(document: dict[str, Any], *, require_original: bool = False) -> HaDataRestoreProvider:
                kwargs = {"require_original": True} if require_original else {}
                try:
                    return runtime.mounted_recovery_provider(store, document, **kwargs)
                except HaRecoveryMediaRequired:
                    if not pending_only:
                        raise
                mounts.enter_context(runtime.mount_original_for_recovery(store, document))
                return runtime.mounted_recovery_provider(store, document, **kwargs)

            status = resume_host_recovery(
                store, runtime, provider, lambda document: provider(document, require_original=True),
                pending_only=pending_only, health=runtime,
            )
        if pending_only and status == "NO_PENDING_RECOVERY":
            status = _dispatch_pending_candidate(store, runtime)
    except HaRecoveryMediaRequired:
        print(json.dumps({"status": "RECOVERY_MEDIA_REQUIRED"}))
        return 0
    except HaRecoveryMonitoringPending:
        print(json.dumps({"status": "RECOVERY_MONITORING_EVIDENCE_PENDING"}))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        if pending_only and isinstance(error, UpdaterV2Error) and str(error) == "upgrade_transaction_busy":
            return 0
        if not application_condition:
            status = "RECOVERY_STARTUP_NEEDS_REVIEW"
            if install_requested:
                status = "INSTALL_NEEDS_REVIEW"
            elif serve_ipc:
                status = "IPC_STARTUP_NEEDS_REVIEW"
            print(json.dumps({"status": status}))
            # Never expose subprocess output, paths, or arbitrary exception text.
            code = str(error) if isinstance(error, (UpdaterError, UpdaterV2Error)) else ""
            if re.fullmatch(r"ha_[a-z0-9_]{1,190}", code) is None:
                code = type(error).__name__
            print(json.dumps({"failure_reason": code}), file=sys.stderr)
        return 1
    if not pending_only or status != "NO_PENDING_RECOVERY":
        print(json.dumps({"status": status}))
    return 0


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-application-start", action="store_true")
    action.add_argument("--resume-pending", action="store_true")
    action.add_argument("--install-requested", action="store_true")
    action.add_argument("--serve-ipc", action="store_true")
    action.add_argument("--issue-prepare-authority", type=Path, metavar="PRIVATE_REQUEST")
    action.add_argument("--issue-install-authority", type=Path, metavar="PRIVATE_REQUEST")
    action.add_argument("--retire-precutover-failure", action="store_true")
    action.add_argument(
        "--maintenance-submit-approved-release",
        choices=("PREPARE", "INSTALL"),
        metavar="ACTION",
    )
    parser.add_argument("--release-identity")
    args = parser.parse_args(argv)
    if args.retire_precutover_failure:
        if os.geteuid() != 0:
            parser.error("pre-cutover failure retirement requires root")
        try:
            status = retire_pre_cutover_failure(HaUsbStateStore(), LocalHaPredecessorRuntime())
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            response = {"status": "PRE_CUTOVER_FAILURE_NOT_RETIRED"}
            if isinstance(error, UpdaterV2Error):
                response["reason"] = str(error)
            print(json.dumps(response, sort_keys=True))
            return 1
        print(json.dumps(status, sort_keys=True))
        return 0
    if args.maintenance_submit_approved_release is not None:
        if os.geteuid() != 0:
            parser.error("maintenance release submission requires root")
        if not args.release_identity:
            parser.error("--release-identity is required for maintenance release submission")
        try:
            status = maintenance_submit_approved_release(
                HaUsbStateStore(),
                LocalHaPredecessorRuntime(),
                action=args.maintenance_submit_approved_release,
                release_identity=args.release_identity,
            )
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            response = {"status": "MAINTENANCE_INTENT_NOT_SUBMITTED"}
            if isinstance(error, UpdaterV2Error):
                response["reason"] = str(error)
            print(json.dumps(response, sort_keys=True))
            return 1
        print(json.dumps({
            "status": "MAINTENANCE_INTENT_SUBMITTED",
            "action": args.maintenance_submit_approved_release,
            "release_identity": args.release_identity,
            "transaction": status,
        }, sort_keys=True))
        return 0
    if args.release_identity is not None:
        parser.error("--release-identity requires --maintenance-submit-approved-release")

    request_path = args.issue_prepare_authority or args.issue_install_authority
    if request_path is not None:
        if os.geteuid() != 0:
            parser.error("authority issuance requires root")
        kind = "prepare" if args.issue_prepare_authority else "install"
        try:
            request = _read_authority_file(request_path, "ha_usb_authority_request_invalid")
            status = LocalHaPredecessorRuntime().issue_candidate_authority(HaUsbStateStore(), kind, request)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            response = {"status": "AUTHORITY_NOT_ISSUED"}
            if isinstance(error, UpdaterV2Error):
                response["reason"] = str(error)
            print(json.dumps(response))
            return 1
        print(json.dumps({"status": status}))
        return 0
    return main(
        application_condition=args.check_application_start, pending_only=args.resume_pending,
        install_requested=args.install_requested, serve_ipc=args.serve_ipc,
    )


if __name__ == "__main__":
    raise SystemExit(cli())
