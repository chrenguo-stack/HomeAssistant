from __future__ import annotations

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
    U13BHealthEvidence,
    U13BPredecessorImageEvidence,
    U13BRuntimeEvidence,
    U13BTargetCleanupEvidence,
)
from n3w_t1_core_updater_host import EXPECTED_LISTENERS, LocalHost
from n3w_t1_core_updater_v2_common import (
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
        return U13BPredecessorImageEvidence(
            predecessor_image_exact_present=(
                self.host.image_id(predecessor.image_ref) == runtime_id
            )
        ).validate()

    def _running_predecessor_evidence(
        self,
        predecessor: ImageRecoveryRecord,
    ) -> U13BRuntimeEvidence | None:
        if self.host._systemctl("is-active", SERVICES_UNIT) != "active":
            return None
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
        ha = self.host._runtime("homeassistant")
        container_id = ha["container_id"]
        if (
            ha["image_ref"] != predecessor.image_ref
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

        existing = self._running_predecessor_evidence(predecessor)
        if existing is not None:
            return existing.validate()

        runtime_id = self.host.image_id(predecessor.image_ref)
        if runtime_id is None:
            raise UpdaterV2Error("u13b_predecessor_image_missing")
        evidence = self.u11.start_target_owner(
            target_image_ref=predecessor.image_ref,
            target_runtime_image_id=runtime_id,
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
        runtime = self._running_predecessor_evidence(predecessor)
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
