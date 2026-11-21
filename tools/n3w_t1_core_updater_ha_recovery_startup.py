#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import stat
import subprocess
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
from n3w_t1_core_updater_ha_backup import DEFAULT_HA_DATA_ROOT, ProtectedHaDataBackup
from n3w_t1_core_updater_ha_mounted_media import HaMountedBackupProvider, bound_usb_device
from n3w_t1_core_updater_ha_usb import (
    HaDataRestoreProvider, HaPredecessorRelease, destructive_cutover_allowed, ha_data_rollback_required,
    resume_host_recovery,
)
from n3w_t1_core_updater_ha_usb_media import USB_FILESYSTEM
from n3w_t1_core_updater_ha_usb_state import (
    TARGET_BINDING, TARGET_WRITES_POSSIBLE, U9, U10, HaUsbStateStore,
)
from n3w_t1_core_updater_host import DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS, LocalHost
from n3w_t1_core_updater_v2_common import COMPONENTS, SHA256, UpdaterV2Error
from n3w_t1_portable_image_identity import (
    PortableImageIdentity, identity_from_dict, observe_docker_image, verify_runtime_document,
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


class HaRecoveryMediaRequired(UpdaterError):
    pass


class LocalHaPredecessorRuntime(LocalHost):
    ha_data_root = DEFAULT_HA_DATA_ROOT

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
        if (
            binding["images"]["homeassistant"]["reference"]
            != transaction["current_image_ref"]
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
            or image.get("RepoTags") != [old["reference"]] or image.get("RepoDigests") not in (None, [])
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
        self._verify_rollback_health(binding, origins)

    def verify_resident_predecessor_health(self, document: dict[str, Any]) -> None:
        binding, origins = self._restart_binding()
        if binding != document["predecessor_start"]:
            raise UpdaterError("ha_usb_predecessor_launch_binding_drift")
        self._verify_rollback_health(binding, origins)

    def _verify_rollback_health(self, binding: dict[str, Any], origins: dict[str, dict[str, str]]) -> None:
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

    def mounted_recovery_provider(
        self, store: HaUsbStateStore, document: dict[str, Any], *, require_original: bool = False,
    ) -> HaMountedBackupProvider:
        mountpoint = store.root
        if require_original or document.get("ha_data_restore", {}).get("step", "STAGING") == "STAGING":
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
            if filesystems == []:
                raise HaRecoveryMediaRequired("ha_usb_rollback_original_mount_required")
            if not isinstance(filesystems, list) or len(filesystems) != 1:
                raise UpdaterError("ha_usb_rollback_mount_discovery_failed")
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


def main(*, application_condition: bool = False, pending_only: bool = False) -> int:
    store = HaUsbStateStore()
    runtime = LocalHaPredecessorRuntime()
    try:
        if application_condition:
            return check_application_start(store, runtime)
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
                pending_only=pending_only,
            )
    except HaRecoveryMediaRequired:
        print(json.dumps({"status": "RECOVERY_MEDIA_REQUIRED"}))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        if pending_only and isinstance(error, UpdaterV2Error) and str(error) == "upgrade_transaction_busy":
            return 0
        if not application_condition:
            print(json.dumps({"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}))
        return 1
    if not pending_only or status != "NO_PENDING_RECOVERY":
        print(json.dumps({"status": status}))
    return 0


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-application-start", action="store_true")
    action.add_argument("--resume-pending", action="store_true")
    args = parser.parse_args(argv)
    return main(application_condition=args.check_application_start, pending_only=args.resume_pending)


if __name__ == "__main__":
    raise SystemExit(cli())
