from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

import n3w_t1_portable_image_identity as portable
from n3w_t1_core_updater_common import BROKER_UNIT, SERVICES_UNIT
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    image_recovery_record_from_document,
)
from n3w_t1_core_updater_ha_u11_host import (
    EXPECTED_U11_EXECSTART,
    EXPECTED_U11_EXECSTOP,
    LocalU11RuntimeOwner,
)
from n3w_t1_core_updater_ha_u13b import (
    U13BDataRestoreReadiness,
    U13BHealthEvidence,
    U13BPredecessorImageEvidence,
    U13BRuntimeEvidence,
    U13BTargetCleanupEvidence,
    U13BUsbMetadataSnapshot,
)
from n3w_t1_core_updater_host import EXPECTED_LISTENERS, LocalHost
from n3w_t1_core_updater_v2_common import (
    SHA256,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)


class U13BProductionBackend:
    def __init__(
        self,
        prepare_backend: SubprocessPrepareBackend | None = None,
    ) -> None:
        self.prepare_backend = prepare_backend or SubprocessPrepareBackend()

    def resolve_transaction_media(
        self,
        transaction: Mapping[str, Any],
        *,
        write_required: bool,
    ) -> PreparedUsbMedia | None:
        return self.prepare_backend.resolve_transaction_media(
            transaction,
            write_required=write_required,
        )

    def resolve_transaction_media_for_reconciliation(
        self,
        transaction: Mapping[str, Any],
    ) -> PreparedUsbMedia | None:
        return self.prepare_backend.resolve_transaction_media_for_reconciliation(
            dict(transaction)
        )

    def release_transaction_media_for_reconciliation(
        self,
        media: PreparedUsbMedia,
    ) -> None:
        self.prepare_backend.release_transaction_media_for_reconciliation(
            media
        )

    @staticmethod
    def archive_path(media: PreparedUsbMedia, kind: str) -> Path:
        if kind not in {"target", "predecessor"}:
            raise UpdaterV2Error("u13b_archive_kind_invalid")
        name = (
            "homeassistant-arm64.tar.gz"
            if kind == "target"
            else "homeassistant-predecessor.tar.gz"
        )
        return Path(media.mount_path) / "n3w-update" / kind / name

    @staticmethod
    def _verify_record(
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
        kind: str,
    ) -> ImageRecoveryRecord:
        media.validate()
        if media.filesystem_uuid != transaction.get("usb_filesystem_uuid"):
            raise UpdaterV2Error("u13b_bound_media_uuid_drift")
        key = (
            "target_artifact_identity"
            if kind == "target"
            else "predecessor_recovery_identity"
        )
        expected_ref = (
            transaction["target_image_ref"]
            if kind == "target"
            else transaction["current_image_ref"]
        )
        expected_sha = (
            transaction["target_archive_sha256"]
            if kind == "target"
            else None
        )
        record = image_recovery_record_from_document(
            transaction.get(key),
            expected_kind=kind,
            expected_image_ref=expected_ref,
            expected_archive_sha256=expected_sha,
        )
        path = U13BProductionBackend.archive_path(media, kind)
        try:
            identity = portable.parse_image_archive(
                path,
                expected_archive_sha256=record.archive_sha256,
                expected_archive_size_bytes=record.archive_size_bytes,
                expected_tag=record.image_ref,
                platform_os="linux",
                platform_architecture="arm64",
            )
        except portable.PortableImageIdentityError as error:
            raise UpdaterV2Error(
                f"u13b_{kind}_archive_identity_invalid"
            ) from error
        if (
            sha256_bytes(canonical(identity.to_dict()))
            != record.portable_identity_sha256
        ):
            raise UpdaterV2Error(
                f"u13b_{kind}_portable_identity_drift"
            )
        return record

    def verify_recovery_target(
        self,
        *,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        return self._verify_record(transaction, media, "target")

    def verify_recovery_predecessor(
        self,
        *,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        return self._verify_record(transaction, media, "predecessor")

    @staticmethod
    def _read_transaction_metadata_file(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("u13b_usb_transaction_metadata_file_invalid")
        metadata = path.stat()
        if (
            metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size <= 0
            or metadata.st_size > 256 * 1024
        ):
            raise UpdaterV2Error(
                "u13b_usb_transaction_metadata_file_metadata_invalid"
            )
        try:
            payload = path.read_text(encoding="utf-8")
            def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                result: dict[str, Any] = {}
                for key, value in pairs:
                    if key in result:
                        raise UpdaterV2Error(
                            "u13b_usb_transaction_metadata_duplicate_field"
                        )
                    result[key] = value
                return result
            document = json.loads(payload, object_pairs_hook=reject_duplicates)
        except UpdaterV2Error:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error(
                "u13b_usb_transaction_metadata_json_invalid"
            ) from error
        if not isinstance(document, dict):
            raise UpdaterV2Error("u13b_usb_transaction_metadata_json_invalid")
        return document

    def read_transaction_metadata(
        self,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> U13BUsbMetadataSnapshot:
        media.validate()
        if media.filesystem_uuid != transaction.get("usb_filesystem_uuid"):
            raise UpdaterV2Error("u13b_bound_media_uuid_drift")
        mount_path = Path(media.mount_path)
        if mount_path.is_symlink() or not mount_path.is_dir():
            raise UpdaterV2Error("u13b_usb_transaction_directory_invalid")
        update_dir = mount_path / "n3w-update"
        transaction_dir = update_dir / "transaction"
        for directory in (update_dir, transaction_dir):
            if directory.is_symlink() or not directory.is_dir():
                raise UpdaterV2Error(
                    "u13b_usb_transaction_directory_invalid"
                )
            metadata = directory.stat()
            if (
                metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                raise UpdaterV2Error(
                    "u13b_usb_transaction_directory_metadata_invalid"
                )
        return U13BUsbMetadataSnapshot(
            manifest=self._read_transaction_metadata_file(transaction_dir / "manifest.json"),
            phase=self._read_transaction_metadata_file(transaction_dir / "phase.json"),
            checksums=self._read_transaction_metadata_file(transaction_dir / "checksums.json"),
            content_authority=self._read_transaction_metadata_file(
                transaction_dir / "content-authority.json"
            ),
            host_transaction=self._read_transaction_metadata_file(
                transaction_dir / "host-transaction.json"
            ),
        )

    def sync_transaction_metadata(
        self,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> None:
        self.prepare_backend.sync_transaction_metadata(transaction, media)


class U13BProductionRuntime:
    def __init__(
        self,
        *,
        expected_manager_container_id: str,
        expected_manager_image_ref: str,
        expected_manager_runtime_image_id: str,
        expected_broker_container_id: str,
        expected_broker_image_ref: str,
        expected_broker_runtime_image_id: str,
        host: LocalHost | None = None,
    ) -> None:
        self.host = host or LocalHost()
        self.u11 = LocalU11RuntimeOwner(
            expected_manager_container_id=expected_manager_container_id,
            expected_manager_image_ref=expected_manager_image_ref,
            expected_manager_runtime_image_id=expected_manager_runtime_image_id,
            expected_broker_container_id=expected_broker_container_id,
            expected_broker_image_ref=expected_broker_image_ref,
            expected_broker_runtime_image_id=expected_broker_runtime_image_id,
            host=self.host,
        )

    @staticmethod
    def _expected_predecessor_runtime_id(
        transaction: Mapping[str, Any],
    ) -> str:
        identity = transaction.get("current_image_identity")
        runtime_id = (
            identity.get("runtime_image_id")
            if isinstance(identity, Mapping)
            else None
        )
        platform = (
            identity.get("platform")
            if isinstance(identity, Mapping)
            else None
        )
        if (
            not isinstance(runtime_id, str)
            or not runtime_id.startswith("sha256:")
            or SHA256.fullmatch(runtime_id[7:]) is None
            or platform != "linux/arm64"
        ):
            raise UpdaterV2Error(
                "u13b_predecessor_transaction_identity_invalid"
            )
        return runtime_id

    def _require_overlay_contract(self) -> None:
        self.host._activation_env()
        self.host._service_unit(
            expected_execstart=EXPECTED_U11_EXECSTART,
            expected_execstop=EXPECTED_U11_EXECSTOP,
        )

    def _remove_exact_residue(
        self,
        item: Mapping[str, str],
    ) -> None:
        container_id = item["container_id"]
        self.host._run(("docker", "rm", container_id), timeout=120)
        if self.host._run(
            ("docker", "inspect", container_id),
            check=False,
        ).returncode == 0:
            raise UpdaterV2Error("u13b_target_container_remove_failed")

    def cleanup_failed_target(
        self,
        *,
        transaction: Mapping[str, Any],
        target: ImageRecoveryRecord,
    ) -> U13BTargetCleanupEvidence:
        self.host.assert_mutation_safe("homeassistant")
        self._require_overlay_contract()
        broker_before = self.u11._exact_peer(
            "broker",
            expected_container_id=self.u11.expected_broker_container_id,
            expected_image_ref=self.u11.expected_broker_image_ref,
            expected_runtime_image_id=(
                self.u11.expected_broker_runtime_image_id
            ),
        )
        self.host.stop_services()

        target_ref = target.image_ref
        target_id = self.host.image_id(target_ref)
        residues = [
            item
            for item in self.host.component_container_residue("homeassistant")
            if item["image_ref"] == target_ref
        ]
        ids = {item["image_id"] for item in residues}
        if target_id is not None:
            ids.add(target_id)
        if len(ids) > 1:
            raise UpdaterV2Error("u13b_target_runtime_identity_ambiguous")
        exact_target_id = next(iter(ids), None)

        predecessor_id = self.host.image_id(transaction["current_image_ref"])
        if (
            exact_target_id is not None
            and predecessor_id is not None
            and exact_target_id == predecessor_id
        ):
            raise UpdaterV2Error(
                "u13b_target_predecessor_runtime_identity_collision"
            )

        for item in residues:
            self._remove_exact_residue(item)
        if exact_target_id is not None:
            if self.host.containers_using_image(exact_target_id):
                raise UpdaterV2Error("u13b_target_image_still_referenced")
            self.host.remove_image_exact(exact_target_id)

        broker_after = self.u11._exact_peer(
            "broker",
            expected_container_id=self.u11.expected_broker_container_id,
            expected_image_ref=self.u11.expected_broker_image_ref,
            expected_runtime_image_id=(
                self.u11.expected_broker_runtime_image_id
            ),
        )
        if broker_after["container_id"] != broker_before["container_id"]:
            raise UpdaterV2Error("u13b_broker_identity_drift")

        counts = {
            name: self.host._running_count(name)
            for name in ("manager", "homeassistant", "broker")
        }
        owner = self.host._systemctl("is-active", SERVICES_UNIT)
        return U13BTargetCleanupEvidence(
            services_quiesced=(
                owner in {"inactive", "failed"}
                and counts == {
                    "manager": 0,
                    "homeassistant": 0,
                    "broker": 1,
                }
            ),
            target_runtime_absent=(
                not any(
                    item["image_ref"] == target_ref
                    for item in self.host.component_container_residue(
                        "homeassistant"
                    )
                )
            ),
            target_image_absent=self.host.image_id(target_ref) is None,
        ).validate()

    def restore_predecessor_image(
        self,
        *,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
        predecessor: ImageRecoveryRecord,
    ) -> U13BPredecessorImageEvidence:
        archive = U13BProductionBackend.archive_path(media, "predecessor")
        if self.host.image_id(predecessor.image_ref) is None:
            self.host.load_image(archive)
        runtime_id = self.host.verify_image_archive(
            predecessor.image_ref,
            archive,
            predecessor.archive_sha256,
        )
        expected_runtime_id = self._expected_predecessor_runtime_id(
            transaction
        )
        if runtime_id != expected_runtime_id:
            raise UpdaterV2Error(
                "u13b_predecessor_runtime_image_identity_drift"
            )
        return U13BPredecessorImageEvidence(
            predecessor_image_exact_present=(
                self.host.image_id(predecessor.image_ref)
                == expected_runtime_id
            )
        ).validate()

    def quiesce_for_data_restore(
        self,
        *,
        transaction: Mapping[str, Any],
    ) -> U13BDataRestoreReadiness:
        self._require_overlay_contract()
        broker_before = self.u11._exact_peer(
            "broker",
            expected_container_id=self.u11.expected_broker_container_id,
            expected_image_ref=self.u11.expected_broker_image_ref,
            expected_runtime_image_id=(
                self.u11.expected_broker_runtime_image_id
            ),
        )
        self.host.stop_services()
        broker_after = self.u11._exact_peer(
            "broker",
            expected_container_id=self.u11.expected_broker_container_id,
            expected_image_ref=self.u11.expected_broker_image_ref,
            expected_runtime_image_id=(
                self.u11.expected_broker_runtime_image_id
            ),
        )
        counts = {
            name: self.host._running_count(name)
            for name in ("manager", "homeassistant", "broker")
        }
        return U13BDataRestoreReadiness(
            services_quiesced=(
                self.host._systemctl("is-active", SERVICES_UNIT)
                in {"inactive", "failed"}
                and counts == {
                    "manager": 0,
                    "homeassistant": 0,
                    "broker": 1,
                }
            ),
            broker_preserved=(
                broker_after["container_id"] == broker_before["container_id"]
            ),
        ).validate()

    def _running_predecessor_evidence(
        self,
        transaction: Mapping[str, Any],
        predecessor: ImageRecoveryRecord,
    ) -> U13BRuntimeEvidence | None:
        if self.host._systemctl("is-active", SERVICES_UNIT) != "active":
            return None
        if self.host._systemctl("is-active", BROKER_UNIT) != "active":
            raise UpdaterV2Error("u13b_broker_owner_not_active")
        counts = {
            name: self.host._running_count(name)
            for name in ("manager", "homeassistant", "broker")
        }
        if counts != {"manager": 1, "homeassistant": 1, "broker": 1}:
            return None
        self._require_overlay_contract()
        self.u11._exact_peer(
            "manager",
            expected_container_id=self.u11.expected_manager_container_id,
            expected_image_ref=self.u11.expected_manager_image_ref,
            expected_runtime_image_id=(
                self.u11.expected_manager_runtime_image_id
            ),
        )
        self.u11._exact_peer(
            "broker",
            expected_container_id=self.u11.expected_broker_container_id,
            expected_image_ref=self.u11.expected_broker_image_ref,
            expected_runtime_image_id=(
                self.u11.expected_broker_runtime_image_id
            ),
        )
        if self.host.component_binding_v2("homeassistant") != predecessor.image_ref:
            raise UpdaterV2Error("u13b_homeassistant_binding_drift")
        ha = self.host._runtime("homeassistant")
        container_id = ha["container_id"]
        expected_runtime_id = self._expected_predecessor_runtime_id(
            transaction
        )
        if (
            ha["image_ref"] != predecessor.image_ref
            or ha["image_id"] != expected_runtime_id
            or ha.get("restart_count") != 0
            or not self.u11._production_config_mounted(container_id)
        ):
            raise UpdaterV2Error("u13b_predecessor_runtime_identity_drift")
        return U13BRuntimeEvidence(True, True, True, True, True)

    def start_predecessor_runtime(
        self,
        *,
        transaction: Mapping[str, Any],
        predecessor: ImageRecoveryRecord,
    ) -> U13BRuntimeEvidence:
        binding = self.host.component_binding_v2("homeassistant")
        if binding == transaction["target_image_ref"]:
            self.host.rewrite_component_image(
                "homeassistant",
                transaction["target_image_ref"],
                predecessor.image_ref,
            )
        elif binding != predecessor.image_ref:
            raise UpdaterV2Error("u13b_homeassistant_binding_drift")

        existing = self._running_predecessor_evidence(
            transaction,
            predecessor,
        )
        if existing is not None:
            return existing.validate()

        runtime_id = self.host.image_id(predecessor.image_ref)
        expected_runtime_id = self._expected_predecessor_runtime_id(
            transaction
        )
        if runtime_id is None:
            raise UpdaterV2Error("u13b_predecessor_image_missing")
        if runtime_id != expected_runtime_id:
            raise UpdaterV2Error(
                "u13b_predecessor_runtime_image_identity_drift"
            )
        evidence = self.u11.start_target_owner(
            target_image_ref=predecessor.image_ref,
            target_runtime_image_id=expected_runtime_id,
        )
        return U13BRuntimeEvidence(
            predecessor_runtime_started=(
                evidence.homeassistant_running
                and evidence.target_image_ref == predecessor.image_ref
            ),
            production_config_mounted=evidence.production_config_mounted,
            manager_running=evidence.manager_running,
            broker_running=evidence.broker_running,
            homeassistant_running=evidence.homeassistant_running,
        ).validate()

    def verify_predecessor_health(
        self,
        *,
        transaction: Mapping[str, Any],
        predecessor: ImageRecoveryRecord,
    ) -> U13BHealthEvidence:
        runtime = self._running_predecessor_evidence(
            transaction,
            predecessor,
        )
        if runtime is None:
            raise UpdaterV2Error("u13b_predecessor_runtime_not_running")
        if self.host._listener_snapshot() != EXPECTED_LISTENERS:
            raise UpdaterV2Error("u13b_listener_contract_drift")
        authenticated = {
            service: self.host._mqtt_authenticated(service)
            for service in ("manager", "homeassistant")
        }
        http_status = self.host._homeassistant_http_status()
        return U13BHealthEvidence(
            predecessor_health_verified=True,
            manager_mqtt_authenticated=(
                authenticated["manager"] is True
            ),
            homeassistant_mqtt_authenticated=(
                authenticated["homeassistant"] is True
            ),
            homeassistant_http_ready=http_status in {200, 401},
        ).validate()



class U13BProductionReadOnlyObserver:
    """Pure observation adapter. No rollback commands or metadata writes."""

    def __init__(self, *, runtime: U13BProductionRuntime,
                 backend: U13BProductionBackend, backup_provider: Any) -> None:
        self.runtime = runtime
        self.backend = backend
        self.backup_provider = backup_provider

    def _quiesced(self) -> bool:
        runtime = self.runtime
        runtime._require_overlay_contract()
        runtime.u11._exact_peer(
            "broker",
            expected_container_id=runtime.u11.expected_broker_container_id,
            expected_image_ref=runtime.u11.expected_broker_image_ref,
            expected_runtime_image_id=runtime.u11.expected_broker_runtime_image_id,
        )
        return (
            runtime.host._systemctl("is-active", SERVICES_UNIT)
            in {"inactive", "failed"}
            and {name: runtime.host._running_count(name)
                 for name in ("manager", "homeassistant", "broker")}
            == {"manager": 0, "homeassistant": 0, "broker": 1}
        )

    def _recovery_assets(self, transaction: Mapping[str, Any],
                         media: PreparedUsbMedia):
        from n3w_t1_core_updater_ha_backup import backup_record_from_document
        from n3w_t1_core_updater_ha_recovery import validate_image_recovery_record

        target = validate_image_recovery_record(
            self.backend.verify_recovery_target(
                transaction=transaction, media=media),
            expected_kind="target",
            expected_image_ref=transaction["target_image_ref"],
            expected_archive_sha256=transaction["target_archive_sha256"],
        )
        predecessor = validate_image_recovery_record(
            self.backend.verify_recovery_predecessor(
                transaction=transaction, media=media),
            expected_kind="predecessor",
            expected_image_ref=transaction["current_image_ref"],
        )
        if (target.public() != transaction["target_artifact_identity"]
            or predecessor.public()
                != transaction["predecessor_recovery_identity"]):
            raise UpdaterV2Error("u13b_readonly_recovery_identity_drift")
        backup = backup_record_from_document(
            transaction["ha_data_backup_identity"])
        verified = self.backup_provider.verify_backup(
            backup,
            transaction_id_sha256=transaction["transaction_id_sha256"],
            destination_root=Path(media.mount_path) / "n3w-update" / "ha-data",
        )
        if verified.public() != backup.public():
            raise UpdaterV2Error("u13b_readonly_backup_identity_drift")
        return target, predecessor, backup

    def observe_rollback_entry(self, *, transaction, media) -> bool:
        self._recovery_assets(transaction, media)
        return True

    def observe_target_cleanup(self, *, transaction, media) -> bool:
        if not self._quiesced():
            return False
        host = self.runtime.host
        return (
            host.image_id(transaction["target_image_ref"]) is None
            and not any(
                item["image_ref"] == transaction["target_image_ref"]
                for item in host.component_container_residue("homeassistant")
            )
        )

    def observe_predecessor_image(self, *, transaction, media) -> bool:
        if not self._quiesced():
            return False
        predecessor = self.backend.verify_recovery_predecessor(
            transaction=transaction, media=media)
        if predecessor.public() != transaction["predecessor_recovery_identity"]:
            return False
        return (
            self.runtime.host.image_id(transaction["current_image_ref"])
            == self.runtime._expected_predecessor_runtime_id(transaction)
        )

    def observe_ha_data_restored(self, *, transaction, media) -> bool:
        from n3w_t1_core_updater_ha_backup import backup_record_from_document
        if not self._quiesced():
            return False
        backup = backup_record_from_document(
            transaction["ha_data_backup_identity"]
        )
        verified = self.backup_provider.verify_restored_preupgrade_backup_readonly(
            backup,
            transaction_id_sha256=transaction["transaction_id_sha256"],
            source_root=Path(media.mount_path) / "n3w-update" / "ha-data",
        )
        return verified.public() == backup.public()

    def observe_predecessor_runtime(self, *, transaction, media) -> bool:
        from n3w_t1_core_updater_ha_recovery import (
            image_recovery_record_from_document,
        )
        predecessor = image_recovery_record_from_document(
            transaction["predecessor_recovery_identity"],
            expected_kind="predecessor",
            expected_image_ref=transaction["current_image_ref"],
        )
        return self.runtime._running_predecessor_evidence(
            transaction, predecessor) is not None

    def observe_predecessor_health(self, *, transaction, media) -> bool:
        from n3w_t1_core_updater_ha_recovery import (
            image_recovery_record_from_document,
        )
        predecessor = image_recovery_record_from_document(
            transaction["predecessor_recovery_identity"],
            expected_kind="predecessor",
            expected_image_ref=transaction["current_image_ref"],
        )
        return (
            self.runtime.verify_predecessor_health(
                transaction=transaction,
                predecessor=predecessor,
            ).validate()
            is not None
        )



def _resolve_u9_plus_peer_identity(
    host: LocalHost,
    component: str,
    *,
    allow_stopped: bool,
) -> dict[str, str]:
    """Resolve one exact Compose peer without inventing a replacement."""
    running = host._running_count(component)
    if running == 1:
        value = host._runtime(component)
        return {
            "container_id": value["container_id"],
            "image_ref": value["image_ref"],
            "image_id": value["image_id"],
        }
    if running != 0:
        raise UpdaterV2Error(f"u9_plus_{component}_runtime_ambiguous")
    if not allow_stopped:
        raise UpdaterV2Error(f"u9_plus_{component}_runtime_not_running")
    residue = host.component_container_residue(component)
    if len(residue) != 1:
        raise UpdaterV2Error(f"u9_plus_{component}_residue_ambiguous")
    item = residue[0]
    return {
        "container_id": item["container_id"],
        "image_ref": item["image_ref"],
        "image_id": item["image_id"],
    }


class U9PlusProductionCompletionOracle:
    """Prove customer-visible rollback completion on the production host."""

    _ACCEPTED_TELEMETRY_RE = __import__("re").compile(
        r"Accepted telemetry node=([A-Za-z0-9._:-]{1,128})\b"
    )

    def __init__(
        self,
        *,
        runtime: U13BProductionRuntime,
        backend: U13BProductionBackend,
        backup_provider: Any,
        clock=None,
        sleeper=None,
        telemetry_timeout_s: float = 180.0,
        poll_interval_s: float = 2.0,
    ) -> None:
        import time
        self.runtime = runtime
        self.backend = backend
        self.backup_provider = backup_provider
        self.clock = clock or time.time
        self.sleeper = sleeper or time.sleep
        self.telemetry_timeout_s = telemetry_timeout_s
        self.poll_interval_s = poll_interval_s

    def _terminal_host_usb_exact(
        self,
        transaction: Mapping[str, Any],
    ) -> bool:
        from n3w_t1_core_updater_ha_u13b_reconcile import (
            HOST_USB_EXACT,
            classify_u13b_usb_host_split,
        )
        media = self.backend.resolve_transaction_media_for_reconciliation(
            transaction
        )
        if media is None:
            raise UpdaterV2Error(
                "u9_plus_completion_bound_media_unavailable"
            )
        try:
            snapshot = self.backend.read_transaction_metadata(
                transaction,
                media,
            )
            split = classify_u13b_usb_host_split(
                dict(transaction),
                media,
                snapshot,
            )
            return split.classification == HOST_USB_EXACT
        finally:
            self.backend.release_transaction_media_for_reconciliation(
                media
            )

    def _history_readable(self) -> bool:
        import sqlite3
        database = (
            Path(self.backup_provider.ha_data_root)
            / "home-assistant_v2.db"
        )
        if (
            not database.exists()
            or database.is_symlink()
            or not database.is_file()
        ):
            return False
        try:
            connection = sqlite3.connect(
                f"file:{database}?mode=ro",
                uri=True,
                timeout=10.0,
            )
            try:
                checks = tuple(connection.execute("PRAGMA quick_check"))
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "states" not in tables:
                    return False
                connection.execute("SELECT COUNT(*) FROM states").fetchone()
            finally:
                connection.close()
        except sqlite3.Error:
            return False
        return checks == (("ok",),)

    def _accepted_nodes_since(
        self,
        recovery_started_unix: int,
    ) -> set[str]:
        from datetime import UTC, datetime
        since = (
            datetime.fromtimestamp(recovery_started_unix, tz=UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        result = self.runtime.host._run(
            (
                "docker",
                "logs",
                "--since",
                since,
                self.runtime.u11.expected_manager_container_id,
            ),
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise UpdaterV2Error(
                "u9_plus_completion_manager_logs_unavailable"
            )
        payload = (
            result.stdout + result.stderr
        ).decode("utf-8", errors="replace")
        return {
            match.group(1)
            for match in self._ACCEPTED_TELEMETRY_RE.finditer(payload)
        }

    def _ha_entity_ids(self, node_ids: set[str]) -> tuple[str, ...]:
        registry = (
            Path(self.backup_provider.ha_data_root)
            / ".storage"
            / "core.entity_registry"
        )
        if (
            registry.is_symlink()
            or not registry.is_file()
            or not node_ids
        ):
            return ()
        try:
            document = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return ()
        data = document.get("data")
        entities = data.get("entities") if isinstance(data, dict) else None
        if not isinstance(entities, list):
            return ()
        result: set[str] = set()
        for item in entities:
            if not isinstance(item, dict):
                continue
            unique_id = item.get("unique_id")
            entity_id = item.get("entity_id")
            if (
                not isinstance(unique_id, str)
                or not isinstance(entity_id, str)
            ):
                continue
            if any(
                unique_id.startswith(node_id + "_")
                for node_id in node_ids
            ):
                result.add(entity_id)
        return tuple(sorted(result))[:256]

    def _ha_has_fresh_state(
        self,
        entity_ids: tuple[str, ...],
        recovery_started_unix: int,
    ) -> bool:
        import sqlite3
        if not entity_ids:
            return False
        database = (
            Path(self.backup_provider.ha_data_root)
            / "home-assistant_v2.db"
        )
        if database.is_symlink() or not database.is_file():
            return False
        try:
            connection = sqlite3.connect(
                f"file:{database}?mode=ro",
                uri=True,
                timeout=10.0,
            )
            try:
                state_columns = {
                    str(row[1])
                    for row in connection.execute(
                        "PRAGMA table_info(states)"
                    )
                }
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                placeholders = ",".join("?" for _ in entity_ids)
                if (
                    "states_meta" in tables
                    and "metadata_id" in state_columns
                    and "last_updated_ts" in state_columns
                ):
                    row = connection.execute(
                        "SELECT 1 FROM states AS s "
                        "JOIN states_meta AS m "
                        "ON m.metadata_id=s.metadata_id "
                        f"WHERE m.entity_id IN ({placeholders}) "
                        "AND s.last_updated_ts>=? LIMIT 1",
                        (*entity_ids, float(recovery_started_unix)),
                    ).fetchone()
                    return row is not None
                if (
                    "entity_id" in state_columns
                    and "last_updated" in state_columns
                ):
                    from datetime import UTC, datetime
                    timestamp = datetime.fromtimestamp(
                        recovery_started_unix,
                        tz=UTC,
                    ).isoformat()
                    row = connection.execute(
                        "SELECT 1 FROM states "
                        f"WHERE entity_id IN ({placeholders}) "
                        "AND last_updated>=? LIMIT 1",
                        (*entity_ids, timestamp),
                    ).fetchone()
                    return row is not None
            finally:
                connection.close()
        except sqlite3.Error:
            return False
        return False

    def _fresh_greenhouse_telemetry_visible(
        self,
        recovery_started_unix: int,
    ) -> bool:
        deadline = self.clock() + self.telemetry_timeout_s
        while True:
            nodes = self._accepted_nodes_since(recovery_started_unix)
            entities = self._ha_entity_ids(nodes)
            if self._ha_has_fresh_state(
                entities,
                recovery_started_unix,
            ):
                return True
            if self.clock() >= deadline:
                return False
            self.sleeper(self.poll_interval_s)

    def verify(
        self,
        transaction: dict[str, Any],
        *,
        recovery_started_unix: int,
    ):
        from n3w_t1_core_updater_ha_recovery import (
            image_recovery_record_from_document,
        )
        from n3w_t1_core_updater_ha_u13b_auto import (
            U9PlusRecoveryCompletionEvidence,
        )
        from n3w_t1_core_updater_ha_usb_state import U13B

        if transaction.get("phase") != U13B:
            raise UpdaterV2Error(
                "u9_plus_completion_transaction_not_terminal"
            )
        if (
            transaction.get("authorization_claimed") is not True
            or transaction.get("authorization_consumed") is not True
        ):
            raise UpdaterV2Error(
                "u9_plus_completion_authorization_invalid"
            )
        predecessor = image_recovery_record_from_document(
            transaction["predecessor_recovery_identity"],
            expected_kind="predecessor",
            expected_image_ref=transaction["current_image_ref"],
        )
        health = self.runtime.verify_predecessor_health(
            transaction=transaction,
            predecessor=predecessor,
        ).validate()
        return U9PlusRecoveryCompletionEvidence(
            predecessor_runtime_healthy=(
                health.predecessor_health_verified
            ),
            homeassistant_http_ready=health.homeassistant_http_ready,
            manager_ready=health.manager_mqtt_authenticated,
            broker_ready=(
                self.runtime.host._systemctl("is-active", BROKER_UNIT)
                == "active"
            ),
            fresh_greenhouse_telemetry_visible=(
                self._fresh_greenhouse_telemetry_visible(
                    recovery_started_unix
                )
            ),
            preupgrade_history_readable=self._history_readable(),
            host_usb_terminal_exact=(
                self._terminal_host_usb_exact(transaction)
            ),
            authorization_replay_absent=True,
        ).validate()


def build_production_u9_plus_recovery(transaction_store: Any):
    """Compose existing production rollback mechanisms for daemon recovery."""
    from n3w_t1_core_updater_ha_backup import (
        ProtectedHaDataBackupProvider,
    )
    from n3w_t1_core_updater_ha_u13b import (
        HaUsbU13BRollbackController,
    )
    from n3w_t1_core_updater_ha_u13b_auto import (
        U13BAutomaticRollbackCoordinator,
        U9PlusBoundedRecoveryCoordinator,
    )
    from n3w_t1_core_updater_ha_u13b_reconcile import (
        U13BHostOnlyReconciliationWriter,
    )

    host = LocalHost()
    manager = _resolve_u9_plus_peer_identity(
        host,
        "manager",
        allow_stopped=True,
    )
    broker = _resolve_u9_plus_peer_identity(
        host,
        "broker",
        allow_stopped=False,
    )
    backend = U13BProductionBackend()
    runtime = U13BProductionRuntime(
        expected_manager_container_id=manager["container_id"],
        expected_manager_image_ref=manager["image_ref"],
        expected_manager_runtime_image_id=manager["image_id"],
        expected_broker_container_id=broker["container_id"],
        expected_broker_image_ref=broker["image_ref"],
        expected_broker_runtime_image_id=broker["image_id"],
        host=host,
    )
    backup = ProtectedHaDataBackupProvider()
    observer = U13BProductionReadOnlyObserver(
        runtime=runtime,
        backend=backend,
        backup_provider=backup,
    )
    reconciliation = U13BHostOnlyReconciliationWriter(
        transaction_store=transaction_store,
        backend=backend,
        observer=observer,
    )
    rollback = HaUsbU13BRollbackController(
        transaction_store=transaction_store,
        backend=backend,
        runtime_owner=runtime,
        backup_provider=backup,
    )
    automatic = U13BAutomaticRollbackCoordinator(
        reconciliation_writer=reconciliation,
        rollback_controller=rollback,
    )
    oracle = U9PlusProductionCompletionOracle(
        runtime=runtime,
        backend=backend,
        backup_provider=backup,
    )
    return U9PlusBoundedRecoveryCoordinator(
        transaction_store=transaction_store,
        rollback_coordinator=automatic,
        completion_oracle=oracle,
    )
