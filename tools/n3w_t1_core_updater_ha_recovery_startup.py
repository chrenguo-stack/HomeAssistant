#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_common import (
    SERVICES_UNIT,
    UpdaterError,
    canonical,
    sha256_bytes,
)
from n3w_t1_core_updater_ha_usb import resume_pre_cutover_services
from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
from n3w_t1_core_updater_host import LocalHost
from n3w_t1_core_updater_v2_common import COMPONENTS


PROTECTED_BINDS = {
    "homeassistant": {"/config"},
    "manager": {"/var/lib/greenhouse-manager/manager", "/var/lib/greenhouse-manager/n3w"},
}


class LocalHaPredecessorRuntime(LocalHost):
    def _restart_binding(self) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
        self._activation_env()
        self._service_unit()
        if self._run(
            ("systemctl", "show", "--property=NeedDaemonReload", "--value", SERVICES_UNIT)
        ).stdout.strip() != b"no":
            raise UpdaterError("ha_usb_predecessor_service_configuration_unloaded")
        unit = self._run(("systemctl", "cat", SERVICES_UNIT)).stdout
        compose = self.render_compose()
        references, _ = self._image_binding_authority_v2(compose)
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
                paths[target] = (
                    str(real_source),
                    real_source.stat().st_ino,
                    os.statvfs(real_source).f_fsid,
                )
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


def main() -> int:
    try:
        resumed = resume_pre_cutover_services(HaUsbStateStore(), LocalHaPredecessorRuntime())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        print(json.dumps({"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}))
        return 1
    print(json.dumps({"status": "RECOVERING" if resumed else "NO_PRE_CUTOVER_RECOVERY"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
