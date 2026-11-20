#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_common import (
    SERVICES_UNIT,
    UpdaterError,
    canonical,
    sha256_bytes,
)
from n3w_t1_core_updater_ha_backup import DEFAULT_HA_DATA_ROOT, ProtectedHaDataBackup
from n3w_t1_core_updater_ha_mounted_media import HaMountedBackupProvider
from n3w_t1_core_updater_ha_usb import resume_ha_data_rollback, resume_pre_cutover_services
from n3w_t1_core_updater_ha_usb_state import HA_DATA_RESTORE_PHASES, HaUsbStateStore
from n3w_t1_core_updater_host import DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS, LocalHost
from n3w_t1_core_updater_v2_common import COMPONENTS


PROTECTED_BINDS = {
    "homeassistant": {"/config"},
    "manager": {"/var/lib/greenhouse-manager/manager", "/var/lib/greenhouse-manager/n3w"},
}
BOOT_CONDITION = (
    "ExecCondition=/usr/bin/python3 /opt/HomeAssistant/tools/"
    "n3w_t1_core_updater_ha_recovery_startup.py --check-application-start"
)


class HaRecoveryMediaRequired(UpdaterError):
    pass


class LocalHaPredecessorRuntime(LocalHost):
    ha_data_root = DEFAULT_HA_DATA_ROOT

    def _restart_binding(
        self, *, published: dict[str, Any] | None = None, replacement: tuple[str, str] | None = None,
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
            runtime_id = self.image_id(reference)
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
        self, binding: dict[str, Any], origins: dict[str, dict[str, str]]
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
        binding, origins = self._restart_binding()
        if (
            binding["images"]["homeassistant"]["reference"]
            != transaction["current_image_ref"]
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

    def rollback_writers_quiesced(self) -> bool:
        return (
            self._systemctl("is-active", SERVICES_UNIT) in {"inactive", "failed"}
            and self._running_count("manager") == 0
            and self._running_count("homeassistant") == 0
        )

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
        deadline = time.monotonic() + DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if (
                self._systemctl("is-active", SERVICES_UNIT) == "active"
                and all(self._check_running_predecessor(binding, origins).values())
                and self._homeassistant_http_status(allow_unavailable=True) in {200, 401}
                and all(self._mqtt_authenticated(name) for name in ("manager", "homeassistant"))
            ):
                return
            time.sleep(2)
        raise UpdaterError("ha_usb_rollback_predecessor_health_pending")

    def mounted_recovery_provider(self, store: HaUsbStateStore, document: dict[str, Any]) -> HaMountedBackupProvider:
        mountpoint = store.root
        if document["ha_data_restore"]["step"] == "STAGING":
            result = self._run((
                "findmnt", "--list", "--json", "--source", f'UUID={document["usb_filesystem_uuid"]}',
                "--output", "TARGET",
            ), timeout=10, check=False)
            if result.returncode == 1:
                raise HaRecoveryMediaRequired("ha_usb_rollback_original_mount_required")
            if result.returncode:
                raise UpdaterError("ha_usb_rollback_mount_discovery_failed")
            result_document = json.loads(result.stdout)
            filesystems = result_document.get("filesystems") if isinstance(result_document, dict) else None
            if not isinstance(filesystems, list) or len(filesystems) != 1:
                raise HaRecoveryMediaRequired("ha_usb_rollback_original_mount_required")
            filesystem = filesystems[0]
            target = filesystem.get("target") if isinstance(filesystem, dict) else None
            if not isinstance(target, str):
                raise UpdaterError("ha_usb_rollback_mount_discovery_failed")
            mountpoint = Path(target)
            if not mountpoint.is_absolute():
                raise UpdaterError("ha_usb_rollback_mount_discovery_failed")
        return HaMountedBackupProvider(
            store=store, mountpoint=mountpoint, internal_storage=store.root,
            backup=ProtectedHaDataBackup(work_root=store.root, ha_data_root=self.ha_data_root),
            verify_quiesced=self.rollback_writers_quiesced,
        )


def check_application_start(store: HaUsbStateStore, runtime: LocalHaPredecessorRuntime) -> int:
    # The recovery worker may hold the transaction lock while systemd evaluates this condition.
    document = store.read()
    if document and document["phase"] in HA_DATA_RESTORE_PHASES and "ha_data_restore" in document:
        if document["status"] != "ACTIVE" or document["ha_data_restore"]["step"] != "PUBLISHED":
            return 1
        runtime.check_rollback_application_start(document)
    return 0


def main(*, application_condition: bool = False) -> int:
    store = HaUsbStateStore()
    runtime = LocalHaPredecessorRuntime()
    try:
        if application_condition:
            return check_application_start(store, runtime)
        current = store.read()
        if current and current["phase"] in HA_DATA_RESTORE_PHASES and "ha_data_restore" in current:
            runtime.require_rollback_boot_guard()
            resumed = resume_ha_data_rollback(
                store, runtime, lambda document: runtime.mounted_recovery_provider(store, document),
            )
            print(json.dumps({"status": "ROLLED_BACK" if resumed else "NO_PENDING_DATA_ROLLBACK"}))
            return 0
        resumed = resume_pre_cutover_services(store, runtime)
    except HaRecoveryMediaRequired:
        print(json.dumps({"status": "RECOVERY_MEDIA_REQUIRED"}))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        if not application_condition:
            print(json.dumps({"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}))
        return 1
    print(json.dumps({"status": "RECOVERING" if resumed else "NO_PRE_CUTOVER_RECOVERY"}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-application-start", action="store_true")
    raise SystemExit(main(application_condition=parser.parse_args().check_application_start))
