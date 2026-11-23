from __future__ import annotations

import base64
import hashlib
import inspect
import io
import json
import os
import shutil
import sqlite3
import stat
import sys
import tarfile
import threading
from contextlib import closing, nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_ha_mounted_media as mounted_media
import n3w_t1_core_updater_ha_recovery_startup as recovery_startup
import n3w_t1_core_updater_ha_usb as ha_usb_mod
from n3w_t1_core_updater_ha_acceptance import (
    HA_ACCEPTANCE_CHECKS, NATURAL_MONITORING_METHOD, HaAcceptanceEvidence, LocalHaAcceptanceObserver,
)
from n3w_t1_core_updater_ha_backup import (
    BACKUP_ARCHIVE_NAME,
    BACKUP_METADATA_NAME,
    HA_DATABASE_NAME,
    HaDataBackupRecord,
    ProtectedHaDataBackup,
    backup_record_from_document,
    validate_backup_record,
)
from n3w_t1_core_updater_ha_data_evidence import MANAGER_PAIRING_DB, HaProtectedDataEvidence
from n3w_t1_core_updater_ha_ipc import (
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    VERSIONED_STATUS_OPERATION,
    VERSIONED_STATUS_SCHEMA,
    HaUsbIpcDispatcher,
    HaUsbIpcExecutor,
    HostOtaAdmission,
)
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb import (
    HaInstallMaterials,
    HaInternalSpace,
    HaPredecessorRecovery,
    claim_live_authorization,
    classify_power_loss_reentry,
    record_commit,
    record_existing_media_bound,
    record_media_bound,
    record_predecessor_capacity_released,
    record_predecessor_recovery_and_ha_quiesced,
    record_recovery_admission,
    record_rollback_complete,
    record_target_accepted,
    record_target_ready,
    record_target_started,
    request_install,
    request_prepare,
    start_predecessor_recovery,
    start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import (
    FORMAT_CONFIRMATION,
    USB_MEDIA_MIN_CAPACITY_BYTES,
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    FormatAuthorization,
    RemovableDeviceCandidate,
    UsbCapacityInputs,
    assess_capacity,
    authorize_destructive_format,
    select_single_eligible_device,
)
from n3w_t1_core_updater_ha_usb_state import (
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
    HaUsbStateStore,
    new_transaction,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error, canonical, sha256_bytes
from n3w_t1_portable_image_identity import parse_image_archive


CURRENT = "local/n3w-homeassistant:2026.10.0-aaaaaaaa"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
CURRENT_BYTES = b"synthetic-predecessor-image" * 64
TARGET_BYTES = b"synthetic-target-image" * 64
TARGET_SHA = hashlib.sha256(TARGET_BYTES).hexdigest()
CURRENT_IDENTITY = "2" * 64
TARGET_IDENTITY = "4" * 64
USB_UUID = "12345678-1234-5678-1234-567812345678"
OTHER_UUID = "87654321-4321-8765-4321-876543218765"
FINGERPRINT = "a" * 64
AUTHORIZATION_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_R2_TEST_01"
USB_BYTES = USB_MEASURED_USABLE_CAPACITY_MIN_BYTES
CAPACITY_INPUTS = UsbCapacityInputs(
    target_artifact_bytes=1 * 1024**3,
    predecessor_recovery_worst_case_bytes=2 * 1024**3,
    ha_data_backup_worst_case_bytes=3 * 1024**3,
    transaction_metadata_and_working_bytes=1 * 1024**3,
    removable_media_reserve_bytes=1 * 1024**3,
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def candidate() -> RemovableDeviceCandidate:
    return RemovableDeviceCandidate(
        public_fingerprint=FINGERPRINT,
        newly_inserted=True,
        removable=True,
        mass_storage=True,
        read_only=False,
        is_root_device=False,
        backs_production_mount=False,
        display_identity_matches=True,
        capacity_bytes=USB_MEDIA_MIN_CAPACITY_BYTES,
    )


def transaction(*, target: ImageRecoveryRecord | None = None, predecessor_portable: str = CURRENT_IDENTITY):
    return new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={
            "portable_identity_sha256": predecessor_portable,
            "platform": "linux/arm64",
        },
        target_manifest_identity={
            "release_identity": "ha-2026.10.4-r2-synthetic",
            "manifest_sha256": "3" * 64,
        },
        target_image_ref=TARGET,
        target_archive_sha256=target.archive_sha256 if target is not None else TARGET_SHA,
        target_archive_size=target.archive_size_bytes if target is not None else len(TARGET_BYTES),
        created_at_unix=1_800_100_000,
    )


class InterruptedPower(BaseException):
    pass


class SyntheticAcceptance:
    def capture_baseline(self, transaction):
        return {check: sha256_bytes(check.encode()) for check in HA_ACCEPTANCE_CHECKS}

    def observe(self, transaction, check, *, fallback):
        return HaAcceptanceEvidence("PASS", sha256_bytes(check.encode()))


class PredecessorRuntime:
    def __init__(self, store):
        self.store = store
        self.running = {"manager", "homeassistant", "broker"}
        self.stop_count = 0
        self.start_count = 0
        self.interrupt_stop = False
        self.health_available = True
        self.binding = {
            "launch_sha256": "d" * 64,
            "images": {
                "manager": {
                    "reference": "local/greenhouse-manager:old",
                    "runtime_id": "sha256:" + "1" * 64,
                },
                "homeassistant": {"reference": CURRENT, "runtime_id": "sha256:" + "2" * 64},
                "broker": {
                    "reference": "local/n3w-mosquitto:old",
                    "runtime_id": "sha256:" + "3" * 64,
                },
            },
        }

    def capture_start_binding(self, transaction):
        assert self.running == {"manager", "homeassistant", "broker"}
        return self.binding

    def rollback_writers_quiesced(self):
        return self.running == {"broker"}

    def resolve_homeassistant_release(self, release_identity):
        pytest.fail("read-only status must not resolve a candidate release")

    def quiesce_for_backup(self):
        assert self.store.read()["predecessor_start"] == self.binding
        self.stop_count += 1
        self.running.remove("manager")
        if self.interrupt_stop:
            raise InterruptedPower()
        self.running.remove("homeassistant")

    def start_predecessor_if_needed(self, binding):
        assert binding == self.binding
        assert self.store.read()["recovery_required"]
        if self.running != {"manager", "homeassistant", "broker"}:
            self.running |= {"manager", "homeassistant"}
            self.start_count += 1

    def verify_predecessor_health(self, document):
        assert document["predecessor_start"] == self.binding
        assert self.running == {"manager", "homeassistant", "broker"}
        if not self.health_available:
            raise UpdaterV2Error("test_health_evidence_unavailable")


def first_stop_fixture(tmp_path):
    tx, media, docker, _ha, _target = prepare_to_u4(tmp_path)
    tx = start_predecessor_recovery(request_install(tx))
    predecessor = docker.verify_predecessor(media, docker.export_predecessor(media))
    store = HaUsbStateStore(tmp_path / "state")
    store.write(tx)
    return predecessor, store, PredecessorRuntime(store)


def test_first_stop_requires_successfully_persisted_restart_binding(tmp_path, monkeypatch):
    predecessor, store, runtime = first_stop_fixture(tmp_path)

    def failed_write(document):
        raise OSError("test disk write failure")

    monkeypatch.setattr(store, "write", failed_write)
    with (
        pytest.raises(OSError, match="disk write failure"),
        HaPredecessorRecovery(store, runtime, runtime).quiesced_for_backup(predecessor),
    ):
        pytest.fail("backup must not run when the durable intent fails")

    assert runtime.stop_count == 0
    assert "predecessor_start" not in store.read()


def test_partial_first_stop_can_restore_without_usb_and_never_restarts_twice(tmp_path):
    predecessor, store, runtime = first_stop_fixture(tmp_path)
    runtime.interrupt_stop = True
    with (
        pytest.raises(InterruptedPower),
        HaPredecessorRecovery(store, runtime, runtime).quiesced_for_backup(predecessor),
    ):
        pytest.fail("backup must not run after interruption")

    assert store.read()["phase"] == U6
    assert runtime.running == {"homeassistant", "broker"}
    shutil.rmtree(tmp_path / "synthetic-usb")
    assert classify_power_loss_reentry(
        store.read(), usb_present=False, observed_usb_filesystem_uuid=None
    ) == "RESTORE_PREDECESSOR_BEFORE_CUTOVER"
    reopened = HaUsbStateStore(store.root)
    resumed = HaPredecessorRecovery(reopened, runtime, runtime)
    runtime.health_available = False
    with pytest.raises(UpdaterV2Error, match="health_evidence_unavailable"):
        resumed.recover()
    status = HaUsbIpcExecutor(store=reopened, admission_resolver=runtime)
    before = reopened.path.read_bytes()
    assert status.status()["phase"] == "RECOVERING"
    assert reopened.path.read_bytes() == before
    assert runtime.start_count == 1

    runtime.health_available = True
    assert resumed.recover() is True
    assert status.status()["phase"] == "ROLLED_BACK"
    assert reopened.read()["authorization_consumed"] is False
    assert resumed.recover() is False
    assert runtime.start_count == 1


def test_recovery_at_u7_does_not_repeat_first_stop(tmp_path):
    predecessor, store, runtime = first_stop_fixture(tmp_path)
    recovery = HaPredecessorRecovery(store, runtime, runtime)
    with recovery.quiesced_for_backup(predecessor) as transaction:
        assert transaction["phase"] == U7
        with pytest.raises(UpdaterV2Error, match="upgrade_transaction_busy"):
            recovery.recover()
    assert runtime.running == {"broker"}
    with (
        pytest.raises(UpdaterV2Error, match="ha_usb_first_stop_not_admitted"),
        recovery.quiesced_for_backup(predecessor),
    ):
        pytest.fail("an attempted stop cannot be replayed")
    assert recovery.recover() is True
    assert runtime.stop_count == runtime.start_count == 1


def test_backup_failure_restores_predecessor_under_the_same_lock(tmp_path):
    predecessor, store, runtime = first_stop_fixture(tmp_path)
    recovery = HaPredecessorRecovery(store, runtime, runtime)
    with (
        pytest.raises(UpdaterV2Error, match="backup_failed"),
        recovery.quiesced_for_backup(predecessor),
    ):
        raise UpdaterV2Error("test_backup_failed")

    restored = store.read()
    assert restored["phase"] == U7
    assert restored["status"] == "ROLLED_BACK"
    assert restored["ha_data_backup_verified"] is False
    assert restored["authorization_consumed"] is False
    assert runtime.start_count == 1


class StartupRuntime(recovery_startup.LocalHaPredecessorRuntime):
    def __init__(self, root: Path):
        self.owner = "active"
        self.running = {"manager", "homeassistant", "broker"}
        self.saved = PredecessorRuntime(None).binding["images"]
        self.running_ids = {name: item["runtime_id"] for name, item in self.saved.items()}
        self.starts = 0
        self.rewrites = 0
        self.compose = {
            "services": {
                name: {"image": image["reference"], "pull_policy": "never", "volumes": []}
                for name, image in self.saved.items()
            }
        }
        for name, targets in recovery_startup.PROTECTED_BINDS.items():
            for target in targets:
                source = root / name / Path(target).name
                source.mkdir(parents=True)
                self.compose["services"][name]["volumes"].append(
                    {"source": str(source), "target": target, "type": "bind"}
                )
        self.ha_data_root = root / "homeassistant" / "config"

    def _activation_env(self):
        pass

    def _service_unit(self):
        pass

    def _run(self, argv, **kwargs):
        unit = recovery_startup.SERVICES_UNIT
        if argv[:4] == ("systemctl", "show", "--property=NeedDaemonReload", "--value"):
            return SimpleNamespace(stdout=b"no\n")
        if argv == ("systemctl", "cat", unit):
            return SimpleNamespace(stdout=("test unit\n" + recovery_startup.BOOT_CONDITION).encode())
        if argv == ("systemctl", "cat", recovery_startup.RECOVERY_STARTUP_UNIT):
            return SimpleNamespace(stdout=f"ExecStart={recovery_startup.RECOVERY_COMMAND}".encode())
        if argv == ("systemctl", "cat", recovery_startup.RECOVERY_RETRY_UNIT):
            return SimpleNamespace(stdout=f"ExecStart={recovery_startup.RECOVERY_COMMAND} --resume-pending".encode())
        if argv == ("/usr/bin/python3", "-I", recovery_startup.RECOVERY_ARCHIVE, "--help"):
            return SimpleNamespace(stdout=b"--check-application-start --resume-pending")
        if argv == ("systemctl", "start", unit):
            self.starts += 1
            self.owner = "active"
            self.running.update(("manager", "homeassistant"))
            return SimpleNamespace(stdout=b"")
        if argv[:3] == ("docker", "inspect", "--format"):
            volumes = self.compose["services"][argv[-1]]["volumes"]
            mounts = [
                {"Destination": item["target"], "Source": item["source"],
                 "Type": "bind", "RW": True}
                for item in volumes
            ]
            return SimpleNamespace(stdout=json.dumps(mounts).encode())
        raise AssertionError(argv)

    def render_compose(self):
        return self.compose

    def _image_binding_authority_v2(self, rendered=None):
        rendered = self.compose if rendered is None else rendered
        bindings = {name: item["image"] for name, item in rendered["services"].items()}
        return bindings, dict.fromkeys(bindings, "dynamic")

    def rewrite_component_image(self, component, expected, replacement):
        service = self.compose["services"][component]
        assert service["image"] == expected
        service["image"] = replacement
        self.rewrites += 1

    def _homeassistant_http_status(self, *, allow_unavailable=False):
        return 401

    def _mqtt_authenticated(self, name):
        return name in self.running

    def image_id(self, reference):
        return next((item["runtime_id"] for item in self.saved.values()
                     if item["reference"] == reference), None)

    def _running_count(self, service):
        return int(service in self.running)

    def _runtime(self, service):
        return {
            "container_id": service, "image_ref": self.saved[service]["reference"],
            "image_id": self.running_ids[service], "started_at": "fixture",
            "restart_count": 0, "runtime_contract_sha256": "0" * 64,
        }

    def _systemctl(self, action, unit):
        if action == "is-enabled":
            return "enabled"
        if unit == recovery_startup.RECOVERY_TIMER:
            return "active"
        return self.owner

    def stop_services(self):
        self.running.remove("manager")
        self.owner = "failed"
        raise InterruptedPower()


class ReleaseStartupRuntime(StartupRuntime):
    container_id = "d" * 64

    def __init__(self, root, fault):
        super().__init__(root)
        self.fault = fault
        self.container_present = False
        self.image_present = True
        self.removals = []

    def stop_services(self):
        self.running = {"broker"}
        self.owner = "inactive"
        self.container_present = True

    def image_id(self, reference):
        if reference == CURRENT and not self.image_present:
            return None
        return super().image_id(reference)

    def component_container_residue(self, component):
        assert component == "homeassistant"
        if self.container_present:
            return [{
                "container_id": self.container_id, "image_ref": CURRENT,
                "image_id": self.saved["homeassistant"]["runtime_id"], "status": "exited", "replace": "",
            }]
        return []

    def _run(self, argv, **kwargs):
        old_id = self.saved["homeassistant"]["runtime_id"]
        if argv[:3] == ("docker", "image", "inspect"):
            if self.fault == "daemon_unavailable":
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"Cannot connect to the Docker daemon")
            if argv[-1] == TARGET or not self.image_present:
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"Error: No such image")
            assert argv[-1] in {CURRENT, old_id}
            return SimpleNamespace(returncode=0, stdout=json.dumps([{
                "Id": old_id, "RepoTags": [CURRENT], "RepoDigests": [],
            }]).encode())
        if argv[:3] == ("docker", "image", "ls"):
            return SimpleNamespace(stdout=old_id.encode() if self.image_present else b"")
        if argv[:2] == ("docker", "ps"):
            users = [self.container_id] if self.container_present else []
            if self.fault == "shared":
                users.append("a" * 64)
            return SimpleNamespace(stdout="\n".join(users).encode())
        if argv == ("docker", "container", "rm", self.container_id):
            self.removals.append(argv)
            self.container_present = False
            if self.fault == "after_container":
                raise InterruptedPower()
            if self.fault == "command_error_after_container":
                raise recovery_startup.UpdaterError("test_release_command_interrupted")
            return SimpleNamespace(stdout=b"")
        if argv == ("docker", "image", "rm", "--no-prune", old_id):
            self.removals.append(argv)
            self.image_present = False
            if self.fault == "after_image":
                raise InterruptedPower()
            return SimpleNamespace(stdout=b"")
        if argv[:3] == ("docker", "inspect", "--format") and argv[-1] == self.container_id:
            argv = (*argv[:-1], "homeassistant")
        return super()._run(argv, **kwargs)


def test_first_stop_binding_requires_an_armed_recovery_timer(tmp_path, monkeypatch):
    runtime = StartupRuntime(tmp_path)
    systemctl = runtime._systemctl
    monkeypatch.setattr(runtime, "_systemctl", lambda action, unit: (
        "inactive" if (action, unit) == ("is-active", recovery_startup.RECOVERY_TIMER)
        else systemctl(action, unit)
    ))
    with pytest.raises(recovery_startup.UpdaterError, match="ha_usb_recovery_timer_not_armed"):
        runtime.capture_start_binding({"current_image_ref": CURRENT})
    assert runtime.owner == "active" and runtime.running == {"broker", "manager", "homeassistant"}


@pytest.mark.parametrize("old_container_running", [False, True])
def test_target_acceptance_counts_only_running_service_instances(tmp_path, monkeypatch, old_container_running):
    runtime = StartupRuntime(tmp_path)
    binding, origins = runtime._restart_binding()
    monkeypatch.setattr(runtime, "check_cutover_target_start", lambda _: (binding, origins))
    monkeypatch.setattr(runtime, "_running_count", recovery_startup.LocalHost._running_count.__get__(runtime))
    run = runtime._run

    def observe(argv, **kwargs):
        if argv[:2] != ("docker", "ps"):
            return run(argv, **kwargs)
        service = argv[-1].rsplit("=", 1)[-1]
        containers = [(service, True)]
        if service == "homeassistant":
            containers.append(("old-homeassistant", old_container_running))
        visible = [name for name, running in containers if running or "-a" in argv or "--all" in argv]
        return SimpleNamespace(returncode=0, stdout="\n".join(visible).encode())

    monkeypatch.setattr(runtime, "_run", observe)
    if old_container_running:
        with pytest.raises(recovery_startup.UpdaterError, match="ha_usb_predecessor_service_count_invalid"):
            runtime.target_acceptance_runtime({})
    else:
        receipt = runtime.target_acceptance_runtime({})
        assert len(receipt) == 64 and receipt == runtime.target_acceptance_runtime({})


@pytest.mark.parametrize("fault", [None, "shared", "after_container", "after_image", "command_error_after_container"])
def test_release_and_boot_reconcile_exact_predecessor(tmp_path, monkeypatch, capsys, fault):
    _, media, _, _, target, predecessor, backup = drive_to_u8(tmp_path)
    initial = record_existing_media_bound(
        request_prepare(transaction()), filesystem_uuid=USB_UUID, capacity_report=media.report,
    )
    prepared = record_target_ready(start_target_preparation(initial), target=target, predecessor=predecessor)
    store = HaUsbStateStore(tmp_path / "release-state")
    store.write(request_install(prepared))
    runtime = ReleaseStartupRuntime(tmp_path / "application", fault)
    live = runtime.ha_data_root / "protected-data"
    live.write_bytes(b"old HA data")
    materials = SimpleNamespace(verify_install_materials=lambda _: HaInstallMaterials(
        USB_UUID, target, predecessor, media.report, True, HaInternalSpace(3_000, 1_000, 2_000),
    ))
    backups = SimpleNamespace(create_consistent_backup=lambda **_: backup, verify_backup=lambda record: record)
    health = SimpleNamespace(verify_predecessor_health=lambda _: None)
    recovery = HaPredecessorRecovery(store, runtime, health)
    monkeypatch.setattr(recovery_startup, "HaUsbStateStore", lambda: HaUsbStateStore(store.root))
    monkeypatch.setattr(recovery_startup, "LocalHaPredecessorRuntime", lambda: runtime)
    def missing_media(*_a, **_kw):
        assert fault != "after_container", "resident recovery reopened USB"
        raise recovery_startup.HaRecoveryMediaRequired("fixture USB absent")

    monkeypatch.setattr(runtime, "mounted_recovery_provider", missing_media)

    outcome = nullcontext()
    if fault == "shared":
        outcome = pytest.raises(recovery_startup.UpdaterError, match="predecessor_has_other_users")
    elif fault == "command_error_after_container":
        outcome = pytest.raises(recovery_startup.UpdaterError, match="test_release_command_interrupted")
    elif fault is not None:
        outcome = pytest.raises(InterruptedPower)
    with outcome, recovery.install_recovery_point(materials, backups, acceptance=SyntheticAcceptance()) as ready:
        with pytest.raises(recovery_startup.UpdaterError, match="release_action_not_admitted"):
            runtime.release_exact_predecessor(ready)
        released = recovery.release_predecessor_image(materials, backups, AUTHORIZATION_ID)
        assert released["phase"] == U10 and released["predecessor_release_observed"] is True

    interrupted = store.read()
    if fault == "shared":
        assert interrupted["phase"] == U8 and interrupted["status"] == "ROLLED_BACK"
        assert not interrupted["authorization_consumed"] and not runtime.removals
        return
    if fault == "command_error_after_container":
        assert interrupted["phase"] == U13B and interrupted["authorization_consumed"]
        assert runtime.image_present and runtime.starts == 1 and len(runtime.removals) == 1
        return
    assert interrupted["authorization_consumed"] is True
    assert interrupted["predecessor_release_intent"] == {"container_id": runtime.container_id}
    assert recovery_startup.main(application_condition=True) == 1
    removals_before_boot = runtime.removals[:]
    if fault is not None:
        assert interrupted["phase"] == U9
        assert "predecessor_release_observed" not in interrupted
    if fault == "after_image":
        runtime.fault = "daemon_unavailable"
        assert recovery_startup.main() == 1
        assert json.loads(capsys.readouterr().out)["status"] == "RECOVERY_STARTUP_NEEDS_REVIEW"
        assert store.read() == interrupted
        runtime.fault = None

    assert recovery_startup.main() == 0
    reported = json.loads(capsys.readouterr().out)["status"]
    result = store.read()
    assert runtime.removals == removals_before_boot
    assert live.read_bytes() == b"old HA data"
    if fault == "after_container":
        assert (reported, result["phase"], runtime.starts) == ("ROLLED_BACK", U13B, 1)
    else:
        assert (reported, result["phase"], runtime.starts) == ("RECOVERY_MEDIA_REQUIRED", U10, 0)
        assert result["recovery_required"] is True and result["predecessor_release_observed"] is True
    assert result["authorization_id_sha256"] == interrupted["authorization_id_sha256"]


@pytest.mark.parametrize("drift", [None, "protected_directory", "running_image"])
def test_boot_entry_resumes_only_the_bound_predecessor(tmp_path, monkeypatch, capsys, drift):
    predecessor, store, health = first_stop_fixture(tmp_path)
    runtime = StartupRuntime(tmp_path / "application")
    with (
        pytest.raises(InterruptedPower),
        HaPredecessorRecovery(store, runtime, health).quiesced_for_backup(predecessor),
    ):
        pytest.fail("the interrupted stop must not enter the backup")
    shutil.rmtree(tmp_path / "synthetic-usb")
    if drift == "protected_directory":
        source = Path(runtime.compose["services"]["homeassistant"]["volumes"][0]["source"])
        source.rename(source.with_name("older-config"))
        source.mkdir()
    elif drift == "running_image":
        runtime.running_ids["homeassistant"] = "sha256:" + "f" * 64

    monkeypatch.setattr(recovery_startup, "HaUsbStateStore", lambda: HaUsbStateStore(store.root))
    monkeypatch.setattr(recovery_startup, "LocalHaPredecessorRuntime", lambda: runtime)
    assert recovery_startup.main() == (0 if drift is None else 1)
    expected = "RECOVERING" if drift is None else "RECOVERY_STARTUP_NEEDS_REVIEW"
    assert json.loads(capsys.readouterr().out) == {"status": expected}
    assert runtime.starts == (1 if drift is None else 0)
    document = store.read()
    assert document["recovery_required"] is True
    assert document["status"] == "ACTIVE"
    assert document["authorization_consumed"] is False
    if drift is None:
        # A timer wake can close the orphaned transaction without boot or USB.
        assert recovery_startup.main(pending_only=True) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "ROLLED_BACK"
        assert runtime.starts == 1
        assert store.read()["status"] == "ROLLED_BACK"


def test_boot_entry_leaves_legacy_and_post_cutover_transactions_alone(tmp_path, monkeypatch, capsys):
    prepared, _, _, _, target, predecessor, backup = drive_to_u8(tmp_path)
    store = HaUsbStateStore(tmp_path / "state")
    monkeypatch.setattr(recovery_startup, "HaUsbStateStore", lambda: store)
    monkeypatch.setattr(recovery_startup, "LocalHaPredecessorRuntime", object)
    store.write(prepared)
    assert recovery_startup.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "NO_PRE_CUTOVER_RECOVERY"}
    assert store.read() == prepared

    prepared["predecessor_start"] = PredecessorRuntime(store).binding
    prepared["install_recovery_materials"] = {
        "target": target.public(), "predecessor": predecessor.public(), "backup": backup.public(),
    }
    post_cutover = claim_live_authorization(prepared, AUTHORIZATION_ID)
    store.write(post_cutover)
    assert recovery_startup.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "NO_PRE_CUTOVER_RECOVERY"}
    assert store.read() == post_cutover


@pytest.mark.parametrize("monitoring_pending", [False, True])
def test_boot_reconciles_selected_data_rollback_and_waits_for_health(tmp_path, monkeypatch, capsys, monitoring_pending):
    units = Path(__file__).resolve().parents[2] / "infra" / "n3w-t1" / "systemd"
    guard = units / f"{recovery_startup.SERVICES_UNIT}.d" / "ota-ha-recovery.conf"
    assert recovery_startup.BOOT_CONDITION in guard.read_text().splitlines()
    prepared, _, _, _, target, predecessor, backup = drive_to_u8(tmp_path)
    store = HaUsbStateStore(tmp_path / "state")
    runtime = StartupRuntime(tmp_path / "application")
    prepared["predecessor_start"] = runtime.capture_start_binding(prepared)
    prepared["usb_binding_mode"] = "existing_filesystem"
    prepared["prepared_image_materials"] = {"target": target.public(), "predecessor": predecessor.public()}
    prepared["install_recovery_materials"] = {**prepared["prepared_image_materials"], "backup": backup.public()}
    cutover = record_target_started(record_predecessor_capacity_released(
        claim_live_authorization(prepared, AUTHORIZATION_ID, internal_space=HaInternalSpace(2048, 768, 896)),
    ))
    live = runtime.ha_data_root
    journal = {"step": "STAGING", "filesystem_id": os.statvfs(live).f_fsid, "original_inode": live.stat().st_ino}
    store.write({**cutover, "ha_data_restore": journal, "recovery_required": True})
    runtime.compose["services"]["homeassistant"]["image"] = TARGET
    runtime.owner = "inactive"
    runtime.running = {"broker"}
    monkeypatch.setattr(recovery_startup, "HaUsbStateStore", lambda: HaUsbStateStore(store.root))
    monkeypatch.setattr(recovery_startup, "LocalHaPredecessorRuntime", lambda: runtime)
    assert recovery_startup.main(application_condition=True) == 1

    def missing_original(*args):
        raise recovery_startup.HaRecoveryMediaRequired("original media absent")

    with monkeypatch.context() as patch:
        patch.setattr(runtime, "mounted_recovery_provider", missing_original)
        assert recovery_startup.main() == 0
        assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_MEDIA_REQUIRED"}
    assert store.read()["ha_data_restore"] == journal
    assert runtime.starts == runtime.rewrites == 0

    def publish_data():
        live.rename(live.with_name("former"))
        live.mkdir()
        store.write({**store.read(), "ha_data_restore": {
            **journal, "step": "PUBLISHED", "staged_inode": live.stat().st_ino,
        }})
        assert recovery_startup.main(application_condition=True) == 1

    def health_pending(document):
        assert recovery_startup.main(application_condition=True) == 0
        if monitoring_pending:
            raise recovery_startup.HaRecoveryMonitoringPending("simulated monitoring interruption")
        raise recovery_startup.UpdaterError("simulated readiness interruption")

    with monkeypatch.context() as patch:
        patch.setattr(runtime, "mounted_recovery_provider", lambda *_: SimpleNamespace(
            restore_preupgrade_data=publish_data,
        ))
        patch.setattr(runtime, "verify_published_predecessor_health", health_pending)
        assert recovery_startup.main() == (0 if monitoring_pending else 1)
        expected = "RECOVERY_MONITORING_EVIDENCE_PENDING" if monitoring_pending else "RECOVERY_STARTUP_NEEDS_REVIEW"
        assert json.loads(capsys.readouterr().out) == {"status": expected}
    assert store.read()["phase"] == U11
    assert store.read()["ha_data_restore"]["step"] == "PUBLISHED"
    assert runtime.starts == runtime.rewrites == 1

    monkeypatch.setattr(runtime, "mounted_recovery_provider", lambda *_: pytest.fail("unneeded original media"))
    manager = runtime.compose["services"]["manager"]
    original_policy = manager["pull_policy"]
    manager["pull_policy"] = "always"
    assert recovery_startup.main(application_condition=True) == 1
    assert recovery_startup.main() == 1
    assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}
    assert store.read()["phase"] == U11
    manager["pull_policy"] = original_policy
    assert recovery_startup.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "ROLLED_BACK"}
    closed = store.read()
    assert closed["phase"] == U13B
    assert closed["authorization_id_sha256"] == cutover["authorization_id_sha256"]
    assert runtime.starts == runtime.rewrites == 1


def _write_restorable_image_archive(archive, *, extra_tag=False, reference=CURRENT):
    layer = b"image-layer" * (256 * 1024)
    layers = ["sha256:" + sha256_bytes(layer)]
    config = canonical({
        "architecture": "arm64", "os": "linux", "rootfs": {"type": "layers", "diff_ids": layers},
        "config": {"Entrypoint": ["homeassistant"], "Cmd": [reference]},
    })
    config_name = sha256_bytes(config) + ".json"
    tags = [reference, "local/unrelated:retained"] if extra_tag else [reference]
    manifest = canonical([{"Config": config_name, "Layers": ["layer.tar"], "RepoTags": tags}])
    with tarfile.open(archive, "w") as stream:
        for name, content in (("manifest.json", manifest), (config_name, config), ("layer.tar", layer)):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            stream.addfile(member, io.BytesIO(content))
    return config, layers


def _bind_test_image(record, archive):
    identity = parse_image_archive(archive, expected_tag=record.image_ref)
    return replace(
        record, archive_sha256=identity.archive_sha256, archive_size_bytes=identity.archive_size_bytes,
        portable_identity_sha256=sha256_bytes(canonical(identity.to_dict())),
    )


@pytest.mark.parametrize("fault", [
    None, "rollback_reserve", "after_target_import", "after_old_reload",
    "target_runtime_drift", "after_target_binding", "write_intent_failed", "before_target_start",
    "after_target_start", "target_start_failed", "after_target_observed",
    "accept_ok", "accept_fallback", "accept_failed", "accept_unavailable",
    "commit_interrupted", "commit_runtime_drift", "install_worker",
])
def test_target_import_and_activation_select_the_bound_rollback_path(tmp_path, monkeypatch, capsys, fault):
    _exercise_target_import(tmp_path, monkeypatch, capsys, fault, single_image=False)


@pytest.mark.parametrize("fault", [
    "install_worker", "accept_failed", "after_target_import", "after_target_binding",
    "before_target_start", "after_old_reload",
])
def test_single_image_install_and_rollback(tmp_path, monkeypatch, capsys, fault):
    _exercise_target_import(tmp_path, monkeypatch, capsys, fault, single_image=True)


def _exercise_target_import(tmp_path, monkeypatch, capsys, fault, *, single_image):
    _, usb, _, _, target, predecessor, backup = drive_to_u8(tmp_path)
    store = HaUsbStateStore(tmp_path / "state")
    runtime = ReleaseStartupRuntime(tmp_path / "application", None)
    original_file = runtime.ha_data_root / "recorder"
    original_file.write_bytes(b"original data")
    original_inode = original_file.stat().st_ino
    live_inode = runtime.ha_data_root.stat().st_ino
    acceptance_case = fault in {
        "accept_ok", "accept_fallback", "accept_failed", "accept_unavailable",
        "commit_interrupted", "commit_runtime_drift", "install_worker",
    }
    activation_fault = acceptance_case or fault in {
        "target_runtime_drift", "after_target_binding", "write_intent_failed", "before_target_start",
        "after_target_start", "target_start_failed", "after_target_observed",
    }
    data_rollback = fault in {
        "before_target_start", "after_target_start", "target_start_failed", "after_target_observed",
        "accept_failed", "accept_unavailable", "commit_runtime_drift",
    }
    target_path, old_path = tmp_path / "target.tar", tmp_path / "predecessor.tar"
    target_config, target_layers = _write_restorable_image_archive(target_path, reference=TARGET)
    old_config, old_layers = _write_restorable_image_archive(old_path)
    target, predecessor = _bind_test_image(target, target_path), _bind_test_image(predecessor, old_path)
    initial = transaction(target=target, predecessor_portable=predecessor.portable_identity_sha256)
    bound = record_existing_media_bound(request_prepare(initial), filesystem_uuid=USB_UUID, capacity_report=usb.report)
    prepared = record_target_ready(start_target_preparation(bound), target=target, predecessor=predecessor)
    directory = usb.root / "N3W-OTA" / prepared["transaction_id_sha256"]
    if fault != "install_worker":
        directory.mkdir(parents=True)
        shutil.copyfile(target_path, directory / "target.tar")
        shutil.copyfile(old_path, directory / "predecessor.tar")
    device = mounted_media._device_number(usb.root.stat().st_dev)
    mounts = [{"target": str(usb.root), "fstype": "ext4", "fsroot": "/", "options": "rw" if activation_fault else "ro",
               "maj:min": device, "uuid": USB_UUID}]
    devices = [{"type": "disk", "tran": "usb", "maj:min": "8:0", "size": USB_MEDIA_MIN_CAPACITY_BYTES, "children": [
        {"type": "part", "uuid": USB_UUID, "maj:min": device},
    ]}]
    monkeypatch.setattr(mounted_media, "_protected_devices", lambda _: {"8:3"})
    monkeypatch.setattr(mounted_media, "_command_json", lambda command, *_: (
        {"filesystems": mounts} if command == "findmnt" else {"blockdevices": devices}
    ))
    available = (5 if single_image else 4 if fault == "rollback_reserve" else 16) * 1024**2
    filesystem_id = os.statvfs(runtime.ha_data_root).f_fsid
    monkeypatch.setattr(mounted_media.os, "statvfs", lambda path: SimpleNamespace(
        f_bavail=available, f_frsize=1, f_fsid=filesystem_id,
    ))
    work = tmp_path / "protected-work"
    work.mkdir(mode=0o700)
    key = work / "fixture-root"
    key.write_bytes(os.urandom(32))
    key.chmod(0o600)
    provider = mounted_media.HaMountedBackupProvider(
        store=store, mountpoint=usb.root, internal_storage=tmp_path,
        backup=ProtectedHaDataBackup(
            work_root=work, ha_data_root=runtime.ha_data_root, system_root_key=key,
            product_config=work / "fixture-config.yaml",
        ),
        verify_quiesced=runtime.rollback_writers_quiesced,
    )
    if fault != "install_worker":
        store.write(request_install(prepared))
    single_workspace = 512 * 1024 if single_image else None
    recovery_bytes = 3 * 1024**2 + (single_workspace or 0)
    verification = SimpleNamespace(verify_install_materials=lambda _: HaInstallMaterials(
        USB_UUID, target, predecessor, usb.report, True,
        HaInternalSpace(available if single_image else 8 * 1024**2, 3 * 1024**2, recovery_bytes, single_workspace),
    ))
    backups = provider if activation_fault else SimpleNamespace(
        create_consistent_backup=lambda **_: backup, verify_backup=lambda record: record,
    )
    recovery = HaPredecessorRecovery(store, runtime, SimpleNamespace(verify_predecessor_health=lambda _: None))

    runtime_id = "sha256:" + "9" * 64
    loaded_target = None
    run = runtime._run
    prior_runtime = runtime._runtime
    prior_rewrite = runtime.rewrite_component_image
    target_starts = []
    loads = []
    observations = []
    instance_changed = False
    target_releases = []
    target_release_attempts = []
    target_config_id = "sha256:" + sha256_bytes(target_config)

    class Acceptance(SyntheticAcceptance):
        def capture_baseline(self, transaction):
            assert runtime.running == {"broker", "manager", "homeassistant"}
            assert original_file.read_bytes() == b"original data"
            return super().capture_baseline(transaction)

        def observe(self, transaction, check, *, fallback):
            assert transaction["target_acceptance"]["attempts"] == store.read()["target_acceptance"]["attempts"]
            observations.append((check, fallback))
            if check == "protected_data" and fault == "accept_failed":
                return HaAcceptanceEvidence("PROVEN_FAIL")
            if check == "monitoring_path" and fault == "accept_unavailable":
                return HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")
            return super().observe(transaction, check, fallback=fallback)

    observer = Acceptance()
    real_data = fault in {"accept_ok", "accept_failed", "accept_fallback"}
    self_tests = []

    def self_test():
        self_tests.append(runtime.compose["services"]["homeassistant"]["image"])
        return HaAcceptanceEvidence("PASS", "c" * 64)

    if real_data:
        history = runtime.ha_data_root / HA_DATABASE_NAME
        pairing = tmp_path / "application" / "manager" / "manager" / MANAGER_PAIRING_DB.name
        with closing(sqlite3.connect(history)) as connection:
            connection.executescript(
                """
                CREATE TABLE states_meta (metadata_id INTEGER PRIMARY KEY, entity_id TEXT);
                CREATE TABLE states (state_id INTEGER PRIMARY KEY, metadata_id INTEGER, last_updated_ts REAL, state TEXT);
                INSERT INTO states_meta VALUES (1, 'sensor.fixture_history');
                INSERT INTO states VALUES (1, 1, 1900000000.25, '16.5');
                """
            )
        with closing(sqlite3.connect(pairing)) as connection:
            connection.executescript(
                """
                CREATE TABLE registrations (
                    node_id TEXT PRIMARY KEY, current_pairing_id TEXT, pairing_epoch INTEGER, retired_at TEXT
                );
                CREATE TABLE pairing_sessions (pairing_id TEXT PRIMARY KEY, state TEXT);
                INSERT INTO pairing_sessions VALUES ('fixture-assignment', 'approved');
                INSERT INTO registrations VALUES ('fixture-node', 'fixture-assignment', 1, NULL);
                """
            )
        observer = LocalHaAcceptanceObserver(
            SimpleNamespace(
                capture_baseline=lambda _: "1" * 64,
                observe=lambda *_args, **_kwargs: HaAcceptanceEvidence(
                    {
                        "accept_failed": "PROVEN_FAIL", "accept_fallback": "EVIDENCE_UNAVAILABLE",
                    }.get(fault, "PASS"), "2" * 64,
                ),
            ),
            HaProtectedDataEvidence(history, pairing),
            monitoring_method=NATURAL_MONITORING_METHOD if fault == "accept_fallback" else None,
            self_test=self_test if fault == "accept_fallback" else None,
        )

    def observe(argv, **kwargs):
        nonlocal loaded_target, available
        if argv[:3] == ("docker", "image", "inspect") and argv[-1] in {TARGET, runtime_id, target_config_id}:
            if loaded_target is not None and argv[-1] in {TARGET, runtime_id}:
                return SimpleNamespace(returncode=0, stdout=json.dumps([loaded_target]).encode())
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"Error: No such image")
        if single_image and argv == ("docker", "image", "rm", "--no-prune", runtime_id):
            assert store.read()["target_release_step"] == "INTENT"
            assert store.read()["target_release_image_id"] == runtime_id
            assert runtime.running == {"broker"} and loaded_target is not None
            target_release_attempts.append(runtime_id)
            if fault == "after_target_binding" and len(target_release_attempts) == 1:
                raise InterruptedPower()
            loaded_target = None
            available += 3 * 1024**2
            if fault == "before_target_start":
                available -= 2 * 1024**2  # Unreclaimed bytes still count against recovery.
            target_releases.append(runtime_id)
            if fault == "after_target_import":
                raise InterruptedPower()
            return SimpleNamespace(stdout=b"")
        if argv == ("systemctl", "start", recovery_startup.SERVICES_UNIT) and activation_fault:
            document = store.read()
            forward = runtime.compose["services"]["homeassistant"]["image"] == TARGET
            if forward:
                assert document["phase"] == U10
                assert document["target_activation"] == "WRITES_POSSIBLE"
                assert recovery_startup.main(application_condition=True) == 0
                assert recovery_startup.main(application_condition=True) == 1
                if fault == "before_target_start":
                    raise InterruptedPower()
                target_starts.append(document["phase"])
                result = run(argv, **kwargs)
                original_file.write_bytes(b"target migrated data")
                if fault == "accept_failed":
                    with closing(sqlite3.connect(history)) as connection:
                        connection.execute("DELETE FROM states")
                        connection.commit()
                if fault == "after_target_start":
                    raise InterruptedPower()
                if fault == "target_start_failed":
                    raise recovery_startup.UpdaterError("synthetic_target_start_failure")
                return result
            assert recovery_startup.main(application_condition=True) == 0
            assert original_file.read_bytes() == b"original data"
        return run(argv, **kwargs)

    def rewrite(component, expected, replacement):
        prior_rewrite(component, expected, replacement)
        if replacement == TARGET:
            assert store.read()["target_activation"] == "BINDING"
            assert recovery_startup.main(application_condition=True) == 1
            if fault == "after_target_binding":
                raise InterruptedPower()

    def observed_runtime(name):
        value = prior_runtime(name)
        if name == "homeassistant" and runtime.compose["services"][name]["image"] == TARGET:
            return {**value, "image_ref": TARGET, "image_id": runtime_id, "restart_count": int(instance_changed)}
        return value

    prior_residue = runtime.component_container_residue

    def residue(component):
        rows = prior_residue(component)
        if single_image and target_starts and loaded_target is not None:
            return [{**row, "image_ref": TARGET, "image_id": runtime_id} for row in rows]
        return rows

    def load(source):
        nonlocal loaded_target, available
        payload = source.read()
        if payload == target_path.read_bytes():
            assert store.read()["target_load_identity"]["archive_sha256"] == target.archive_sha256
            loads.append(TARGET)
            loaded_target = {"Id": runtime_id, "Os": "linux", "Architecture": "arm64",
                             "Config": json.loads(target_config)["config"], "RootFS": {"Layers": target_layers},
                             "RepoTags": [TARGET], "RepoDigests": []}
            if single_image:
                assert not runtime.image_present
                assert available < store.read()["predecessor_release_admission"]["install_required_bytes"] + recovery_bytes
                available -= 3 * 1024**2
            if fault == "after_target_import":
                raise InterruptedPower()
        else:
            assert payload == old_path.read_bytes()
            document = store.read()
            if single_image:
                assert document["target_release_step"] == "RELEASED"
                assert loaded_target is None and target_releases == [runtime_id]
                assert available >= 3 * 1024**2
            intent = (document["ha_data_restore"]["predecessor_load_identity"] if data_rollback
                      else document["predecessor_reload_identity"])
            assert intent["archive_sha256"] == predecessor.archive_sha256
            loads.append(CURRENT)
            runtime.image_present = True
            if fault == "after_old_reload":
                raise InterruptedPower()

    monkeypatch.setattr(runtime, "_run", observe)
    monkeypatch.setattr(runtime, "_runtime", observed_runtime)
    monkeypatch.setattr(runtime, "component_container_residue", residue)
    monkeypatch.setattr(runtime, "rewrite_component_image", rewrite)
    monkeypatch.setattr(runtime, "_load_ha_image", load)
    monkeypatch.setattr(runtime, "_image_document", lambda _: {
        "Id": runtime.image_id(CURRENT), "Os": "linux", "Architecture": "arm64",
        "Config": json.loads(old_config)["config"], "RootFS": {"Layers": old_layers},
    })
    monkeypatch.setattr(recovery_startup, "HaUsbStateStore", lambda: HaUsbStateStore(store.root))
    monkeypatch.setattr(recovery_startup, "LocalHaPredecessorRuntime", lambda: runtime)
    monkeypatch.setattr(runtime, "mounted_recovery_provider", lambda *_args, **_kwargs: provider)

    if fault == "install_worker":
        admission = HostOtaAdmission(
            release_identity=prepared["target_manifest_identity"]["release_identity"],
            **{field: prepared[field] for field in (
                "current_image_ref", "current_image_identity", "target_image_ref", "target_manifest_identity",
                "target_archive_size", "target_archive_sha256",
            )},
        )
        ipc = HaUsbIpcDispatcher(HaUsbIpcExecutor(
            store=store, admission_resolver=SimpleNamespace(resolve_homeassistant_release=lambda _: admission),
        ))
        monkeypatch.setattr(recovery_startup, "LocalApprovedHaRelease", lambda *_: SimpleNamespace(
            resolve_homeassistant_release=lambda _: admission,
        ))
        assert recovery_startup.cli(["--install-requested"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "NO_ADMITTED_INSTALL_REQUEST"
        def submit(action):
            return json.loads(ipc.handle(json.dumps({
                "schema": REQUEST_SCHEMA, "operation": "submit", "action": action,
                "target_release_id": admission.release_identity,
            }).encode()))

        assert submit("PREPARE")["accepted"] is True
        pending = store.read()
        assert pending["phase"] == U1
        assert recovery_startup.cli(["--resume-pending"]) == 0
        assert capsys.readouterr().out == "" and store.read() == pending

        original_run = runtime._run

        def installer_command(argv, **kwargs):
            if argv == ("docker", "info", "--format", "{{.DockerRootDir}}"):
                return SimpleNamespace(stdout=str(store.root).encode())
            if argv[0] == "findmnt":
                assert f"UUID={USB_UUID}" in argv
                return SimpleNamespace(returncode=0, stdout=json.dumps({"filesystems": mounts}).encode())
            if argv == ("docker", "image", "inspect", CURRENT) and runtime.image_present:
                observed = {**runtime._image_document(CURRENT), "RepoTags": [CURRENT], "RepoDigests": []}
                return SimpleNamespace(returncode=0, stdout=json.dumps([observed]).encode())
            return original_run(argv, **kwargs)

        monkeypatch.setattr(runtime, "_run", installer_command)
        monkeypatch.setattr(runtime, "acceptance_observer", lambda: observer)
        exports = []

        def export(reference):
            exports.append(reference)
            return old_path.open("rb")

        monkeypatch.setattr(runtime, "_export_predecessor", export)
        usable = usb.report.measured_usable_bytes
        monkeypatch.setattr(mounted_media.os, "fstatvfs", lambda _: SimpleNamespace(
            f_bavail=usable, f_blocks=usable, f_bfree=usable, f_frsize=1,
        ))
        binding = runtime.capture_start_binding(pending)
        prepare_path = store.root / recovery_startup.PREPARE_AUTHORITY_FILE
        prepare_request = {
            "transaction_id_sha256": pending["transaction_id_sha256"],
            "usb_filesystem_uuid": USB_UUID,
            "target_source": str(target_path),
            "expires_at_unix": 0x7FFFFFFF,
        }
        customer_file = usb.root / "customer.txt"
        customer_file.write_bytes(b"keep this file")
        candidate_data = target_path.read_bytes()
        target_path.write_bytes(b"X" + candidate_data[1:])
        with pytest.raises(UpdaterV2Error, match="ha_usb_prepare_authority_target_digest_mismatch"):
            runtime.issue_candidate_authority(store, "prepare", prepare_request)
        assert not prepare_path.exists() and store.read() == pending
        target_path.write_bytes(candidate_data)
        assert runtime.issue_candidate_authority(store, "prepare", prepare_request) == "PREPARE_AUTHORITY_ISSUED"
        assert prepare_path.stat().st_mode & 0o777 == 0o600
        assert store.read() == pending and not exports
        target_path.write_bytes(b"X" + candidate_data[1:])
        assert recovery_startup.cli(["--resume-pending"]) == 1
        assert json.loads(capsys.readouterr().out)["status"] == "RECOVERY_STARTUP_NEEDS_REVIEW"
        directory = usb.root / "N3W-OTA" / pending["transaction_id_sha256"]
        assert store.read()["phase"] == U3
        assert not (directory / "target.tar").exists() and not exports and not loads
        assert runtime.running == {"broker", "manager", "homeassistant"}

        target_path.write_bytes(candidate_data)
        write = store.write
        with monkeypatch.context() as interruption:
            def fail_ready(document):
                if document["phase"] == U4:
                    raise InterruptedPower()
                write(document)

            interruption.setattr(recovery_startup, "HaUsbStateStore", lambda: store)
            interruption.setattr(store, "write", fail_ready)
            with pytest.raises(InterruptedPower):
                recovery_startup.cli(["--resume-pending"])
        assert store.read()["phase"] == U3 and exports == [CURRENT, CURRENT]
        assert recovery_startup.cli(["--resume-pending"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "READY_TO_INSTALL"
        assert store.read()["phase"] == U4 and exports == [CURRENT, CURRENT, CURRENT]
        assert (directory / "target.tar").read_bytes() == candidate_data
        assert (directory / "predecessor.tar").read_bytes() == old_path.read_bytes()
        assert target_path.read_bytes() == candidate_data
        assert customer_file.read_bytes() == b"keep this file"
        assert not loads and runtime.starts == runtime.rewrites == 0
        assert recovery_startup.cli(["--resume-pending"]) == 0
        assert capsys.readouterr().out == "" and store.read()["phase"] == U4
        assert submit("INSTALL")["accepted"] is True
        requested = store.read()
        assert requested["phase"] == U5
        assert recovery_startup.cli(["--resume-pending"]) == 0
        assert capsys.readouterr().out == "" and store.read() == requested
        assert runtime.starts == runtime.rewrites == 0

        grant_path = store.root / recovery_startup.INSTALL_AUTHORITY_FILE
        grant = {
            "schema": recovery_startup.INSTALL_AUTHORITY_SCHEMA,
            "binding_sha256": recovery_startup.requested_install_binding_sha256(requested),
            "authorization_id": AUTHORIZATION_ID,
            "launch_sha256": binding["launch_sha256"],
            "expires_at_unix": 0x7FFFFFFF,
            "space": dict.fromkeys(recovery_startup.INSTALL_BUDGET_FIELDS, 1024),
        }
        for wrong in (
            {"binding_sha256": "0" * 64}, {"expires_at_unix": 1}, {"launch_sha256": "0" * 64},
        ):
            grant_path.write_text(json.dumps({**grant, **wrong}))
            grant_path.chmod(0o600)
            assert recovery_startup.cli(["--install-requested"]) == 1
            assert json.loads(capsys.readouterr().out)["status"] == "INSTALL_NEEDS_REVIEW"
            assert runtime.running == {"broker", "manager", "homeassistant"}
            if store.read()["phase"] == U4:
                assert submit("INSTALL")["accepted"] is True
        grant_path.unlink()
        request = {
            **{key: grant[key] for key in ("binding_sha256", "authorization_id", "expires_at_unix", "space")},
            "transaction_id_sha256": requested["transaction_id_sha256"],
        }
        with pytest.raises(UpdaterV2Error, match="ha_usb_install_authority_invalid"):
            runtime.issue_candidate_authority(store, "install", {**request, "binding_sha256": "0" * 64})
        with monkeypatch.context() as replay:
            replay.setattr(store, "was_authorization_consumed", lambda _: True)
            with pytest.raises(UpdaterV2Error, match="ha_usb_install_authority_already_consumed"):
                runtime.issue_candidate_authority(store, "install", request)
        assert not grant_path.exists()
        assert runtime.issue_candidate_authority(store, "install", request) == "INSTALL_AUTHORITY_ISSUED"
        assert grant_path.stat().st_mode & 0o777 == 0o600
        assert json.loads(grant_path.read_bytes()) == grant
        assert runtime.issue_candidate_authority(store, "install", request) == "INSTALL_AUTHORITY_ISSUED"
        with pytest.raises(UpdaterV2Error, match="ha_usb_authority_already_issued"):
            runtime.issue_candidate_authority(store, "install", {
                **request, "authorization_id": AUTHORIZATION_ID + "_different",
            })
        assert not store.read()["authorization_consumed"]
        assert recovery_startup.cli(["--resume-pending"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "COMMITTED"
        committed = store.read()
        assert committed["phase"] == U13A and committed["authorization_consumed"] is True
        assert loads == [TARGET] and target_starts == [U10]
        assert recovery_startup.cli(["--install-requested"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "NO_ADMITTED_INSTALL_REQUEST"
        assert store.read() == committed and loads == [TARGET]
        with store.lock():
            store.prepare_new()
            assert store.was_authorization_consumed(sha256_bytes(AUTHORIZATION_ID.encode()))
            assert not store.was_authorization_consumed("0" * 64)
        return

    outcome = nullcontext()
    if fault == "rollback_reserve":
        outcome = pytest.raises(UpdaterV2Error, match="recovery_space_insufficient")
    elif fault in {
        "after_target_import", "after_target_binding", "before_target_start", "after_target_start",
        "commit_interrupted", "commit_runtime_drift",
    }:
        outcome = pytest.raises(InterruptedPower)
    elif fault == "target_start_failed":
        outcome = pytest.raises(recovery_startup.UpdaterError, match="synthetic_target_start_failure")
    elif fault == "target_runtime_drift":
        outcome = pytest.raises(recovery_startup.UpdaterError, match="target_image_runtime_drift")
    elif fault == "write_intent_failed":
        outcome = pytest.raises(OSError, match="synthetic write intent failure")
    with outcome, recovery.install_recovery_point(verification, backups, acceptance=observer):
        recovery.release_predecessor_image(verification, backups, AUTHORIZATION_ID)
        with pytest.raises(UpdaterV2Error, match="target_image_load_not_admitted"):
            HaPredecessorRecovery(store, runtime, runtime).load_target_after_release(provider)
        loaded = recovery.load_target_after_release(provider)
        assert loaded["phase"] == U10 and loaded["target_loaded_image_id"] == runtime_id
        with pytest.raises(UpdaterV2Error, match="target_write_intent_missing"):
            record_target_started(loaded)
        assert recovery_startup.main(application_condition=True) == 1
        if activation_fault:
            with pytest.raises(UpdaterV2Error, match="target_activation_not_admitted"):
                HaPredecessorRecovery(store, runtime, runtime).activate_target_after_import(provider)
            if fault == "target_runtime_drift":
                loaded_target["Id"] = "sha256:" + "8" * 64
            if fault == "write_intent_failed":
                write = store.write

                def fail_write_intent(document):
                    if document.get("target_activation") == "WRITES_POSSIBLE":
                        raise OSError("synthetic write intent failure")
                    write(document)

                monkeypatch.setattr(store, "write", fail_write_intent)
            started = recovery.activate_target_after_import(provider)
            assert started["phase"] == U11 and not started["recovery_required"]
            assert recovery_startup.main(application_condition=True) == 1
            assert original_file.read_bytes() == b"target migrated data"
            if acceptance_case:
                with pytest.raises(UpdaterV2Error, match="target_acceptance_receipt_required"):
                    record_target_accepted(started)
                if fault in {"commit_interrupted", "commit_runtime_drift"}:
                    write = store.write

                    def interrupt_commit(document):
                        if document["status"] == "COMMITTED":
                            raise InterruptedPower()
                        write(document)

                    monkeypatch.setattr(store, "write", interrupt_commit)
                monkeypatch.setattr(ha_usb_mod.time, "sleep", lambda _: None)
                result = recovery.accept_and_commit_target(provider)
                assert result == store.read()
    if fault in {"commit_interrupted", "commit_runtime_drift"}:
        assert store.read()["phase"] == U12 and store.read()["status"] == "ACTIVE"
        instance_changed = fault == "commit_runtime_drift"
        assert recovery_startup.main() == 0
        assert json.loads(capsys.readouterr().out)["status"] == ("ROLLED_BACK" if instance_changed else "COMMITTED")
    if acceptance_case:
        result = store.read()
        if real_data:
            evidence = result["target_acceptance"]
            assert evidence["data_sample"]["history"]["entity"] == "sensor.fixture_history"
            assert HaProtectedDataEvidence(history, pairing).compare(evidence["data_sample"]) == "PASS"
            altered = store.read()
            altered["target_acceptance"]["data_sample"]["history"]["sha256"] = "0" * 64
            with pytest.raises(UpdaterV2Error, match="ha_usb_target_acceptance_invalid"):
                store.write(altered)
        projected = HaUsbIpcExecutor(store=store, admission_resolver=SimpleNamespace()).status()
        assert projected["phase"] == result["status"]
        assert result["target_acceptance"]["attempts"] == (3 if fault == "accept_unavailable" else 1)
        if not data_rollback:
            assert result["status"] == "COMMITTED"
            receipt = result["target_acceptance"]["receipt"]
            assert receipt["images"]["homeassistant"]["runtime_id"] == runtime_id
            assert set(receipt["observations"]) == set(HA_ACCEPTANCE_CHECKS)
            assert original_file.read_bytes() == b"target migrated data"
            assert loads == [TARGET] and runtime.starts == runtime.rewrites == 1
            assert recovery_startup.main(application_condition=True) == 0
            assert recovery_startup.main() == 0
            assert store.read() == result
            assert loads == [TARGET] and runtime.starts == runtime.rewrites == 1
        else:
            assert result["status"] == "ROLLED_BACK" and original_file.read_bytes() == b"original data"
            assert loads == [TARGET, CURRENT] and runtime.starts == runtime.rewrites == 2
            if fault.startswith("accept_"):
                reason = "proven_failure" if fault == "accept_failed" else "evidence_unavailable"
                assert result["failure_code"] == f"ha_usb_target_acceptance_{reason}"
                assert projected["error_code"] == result["failure_code"]
        if fault == "accept_fallback":
            assert self_tests == [CURRENT, TARGET]
            assert result["target_acceptance"]["monitoring_fallback_sha256"] == "c" * 64
            assert result["target_acceptance"]["receipt"]["observations"]["monitoring_path"] == "c" * 64
            result["target_acceptance"]["monitoring_fallback_sha256"] = "invalid"
            with pytest.raises(UpdaterV2Error, match="target_acceptance_invalid"):
                store.write(result)
        return
    if fault == "after_target_observed":
        with store.lock():
            assert recovery_startup.main(pending_only=True) == 0
        assert capsys.readouterr().out == ""
        assert store.read() == started and runtime.starts == 1

    if fault in {"before_target_start", "after_target_start", "after_target_observed"}:
        assert not store.take_target_start_permit(prepared["transaction_id_sha256"])
        assert recovery_startup.main(application_condition=True) == 1
        with monkeypatch.context() as patch:
            def absent_media(*_args, **_kwargs):
                raise recovery_startup.HaRecoveryMediaRequired("original media absent")

            patch.setattr(runtime, "mounted_recovery_provider", absent_media)
            patch.setattr(runtime, "mount_original_for_recovery", absent_media)
            assert recovery_startup.main(pending_only=fault == "after_target_observed") == 0
            assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_MEDIA_REQUIRED"}
        if single_image:
            assert not target_releases and loaded_target is not None
        assert store.read()["recovery_required"]
        assert not {"homeassistant", "manager"} & runtime.running
        assert recovery_startup.main(application_condition=True) == 1

    if fault not in {"rollback_reserve", "target_runtime_drift", "write_intent_failed", "target_start_failed"}:
        if single_image and fault == "after_target_binding":
            loaded_target["RepoTags"] = [TARGET, "local/retained:fixture"]
            assert recovery_startup.main() == 1
            assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}
            assert not target_release_attempts and "target_release_step" not in store.read()
            loaded_target["RepoTags"] = [TARGET]
            with pytest.raises(InterruptedPower):
                recovery_startup.main()
            assert store.read()["target_release_step"] == "INTENT" and loaded_target is not None
        if single_image and fault == "after_target_import":
            with pytest.raises(InterruptedPower):
                recovery_startup.main()
            assert store.read()["target_release_step"] == "INTENT"
            assert loaded_target is None and target_releases == [runtime_id]
        if single_image and fault == "before_target_start":
            assert recovery_startup.main() == 1
            assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}
            assert store.read()["target_release_step"] == "INTENT"
            assert "ha_data_restore" not in store.read() and loads == [TARGET]
            available += 2 * 1024**2
        if fault == "after_old_reload":
            with pytest.raises(InterruptedPower):
                recovery_startup.main()
            monkeypatch.setattr(runtime, "mounted_recovery_provider", lambda *_a, **_kw: pytest.fail("old reload replayed"))
        assert recovery_startup.main(pending_only=bool(store.read()["recovery_required"])) == 0
        assert json.loads(capsys.readouterr().out) == {"status": "ROLLED_BACK"}
    assert store.read()["phase"] == U13B
    assert ("ha_data_restore" in store.read()) is data_rollback
    assert store.read()["authorization_consumed"]
    assert loads == ([CURRENT] if fault == "rollback_reserve" else [TARGET, CURRENT])
    assert original_file.read_bytes() == b"original data"
    assert (original_file.stat().st_ino == original_inode) is not data_rollback
    assert (runtime.ha_data_root.stat().st_ino == live_inode) is not data_rollback
    assert len(target_starts) == int(fault in {"after_target_start", "target_start_failed", "after_target_observed"})
    assert runtime.starts == 1 + len(target_starts)
    assert runtime.rewrites == (2 if activation_fault and fault != "target_runtime_drift" else 0)
    assert len(runtime.removals) == 2


def test_boot_restores_a_released_predecessor_from_bound_media(tmp_path, monkeypatch, capsys):
    units = Path(__file__).resolve().parents[2] / "infra" / "n3w-t1" / "systemd"
    retry = (units / "n3w-t1-ha-recovery-retry.service").read_text()
    timer = (units / "n3w-t1-ha-recovery-retry.timer").read_text()
    assert f"ExecStart={recovery_startup.RECOVERY_COMMAND} --resume-pending" in retry.splitlines()
    assert "PrivateMounts=yes" in retry.splitlines()
    assert "WantedBy=timers.target" in timer.splitlines()
    prepared, media, _, _, target, predecessor, backup = drive_to_u8(tmp_path)
    store = HaUsbStateStore(tmp_path / "state")
    runtime = StartupRuntime(tmp_path / "application")
    prepared["predecessor_start"] = runtime.capture_start_binding(prepared)
    directory = media.root / "N3W-OTA" / prepared["transaction_id_sha256"]
    directory.mkdir(parents=True)
    archive = directory / "predecessor.tar"
    config, layers = _write_restorable_image_archive(archive)
    original = archive.read_bytes()
    identity = parse_image_archive(archive, expected_tag=CURRENT)
    portable_sha = sha256_bytes(canonical(identity.to_dict()))
    predecessor = replace(
        predecessor, archive_sha256=identity.archive_sha256, archive_size_bytes=identity.archive_size_bytes,
        portable_identity_sha256=portable_sha,
    )
    prepared["current_image_identity"]["portable_identity_sha256"] = portable_sha
    prepared["usb_binding_mode"] = "existing_filesystem"
    prepared["prepared_image_materials"] = {"target": target.public(), "predecessor": predecessor.public()}
    prepared["install_recovery_materials"] = {**prepared["prepared_image_materials"], "backup": backup.public()}
    claimed = claim_live_authorization(prepared, AUTHORIZATION_ID, internal_space=HaInternalSpace(2048, 768, 896))
    cutover = record_target_started(record_predecessor_capacity_released(claimed))
    live = runtime.ha_data_root
    original_inode = live.stat().st_ino
    live.rename(live.with_name("former"))
    live.mkdir()
    pending = {**cutover, "recovery_required": True, "ha_data_restore": {
        "step": "PUBLISHED", "filesystem_id": os.statvfs(live).f_fsid,
        "original_inode": original_inode, "staged_inode": live.stat().st_ino,
    }}
    store.write(pending)
    runtime.compose["services"]["homeassistant"]["image"] = TARGET
    runtime.owner = "inactive"
    runtime.running = {"broker"}
    projection_store = SimpleNamespace(read=store.read)
    dispatcher = HaUsbIpcDispatcher(HaUsbIpcExecutor(store=projection_store, admission_resolver=SimpleNamespace()))
    request = canonical({"schema": REQUEST_SCHEMA, "operation": "status"})
    device = mounted_media._device_number(media.root.stat().st_dev)
    mounts = [{
        "target": str(media.root), "fstype": "ext4", "fsroot": "/", "options": "ro,nosuid",
        "maj:min": device, "uuid": USB_UUID,
    }]
    partition = {"type": "part", "uuid": OTHER_UUID, "maj:min": device,
                 "name": "/dev/n3w-fixture1", "fstype": "ext4"}
    devices = [{"type": "disk", "tran": "usb", "maj:min": "8:0", "size": USB_MEDIA_MIN_CAPACITY_BYTES, "children": [
        partition,
    ]}]
    monkeypatch.setattr(mounted_media, "_protected_devices", lambda _: {"8:3"})
    monkeypatch.setattr(mounted_media, "_command_json", lambda command, *_: (
        {"filesystems": mounts} if command == "findmnt" else {"blockdevices": devices}
    ))
    monkeypatch.setattr(recovery_startup, "HaUsbStateStore", lambda: HaUsbStateStore(store.root))
    monkeypatch.setattr(recovery_startup, "LocalHaPredecessorRuntime", lambda: runtime)
    attached = False
    commands = []
    run = runtime._run
    mountpoint = tmp_path / "private-mount"
    lstat = Path.lstat

    def device_lstat(path):
        if path == Path(partition["name"]):
            return SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=media.root.stat().st_dev)
        return lstat(path)

    def make_mountpoint(**kwargs):
        assert kwargs["dir"] == "/run"
        mountpoint.mkdir(mode=0o700)
        return str(mountpoint)

    monkeypatch.setattr(Path, "lstat", device_lstat)
    monkeypatch.setattr(recovery_startup.tempfile, "mkdtemp", make_mountpoint)

    def mounted_runtime(argv, **kwargs):
        nonlocal attached
        if argv[0] == "findmnt":
            assert f"UUID={USB_UUID}" in argv
            return SimpleNamespace(returncode=0 if attached else 1, stdout=json.dumps({"filesystems": mounts}).encode())
        if argv[0] == "mount":
            assert argv == ("mount", "--internal-only", "-t", "ext4", "-o", "ro,noload,nodev,nosuid,noexec",
                            "--", partition["name"], str(mountpoint))
            assert not attached
            attached = True
            commands.append("mount")
            return SimpleNamespace(stdout=b"")
        if argv[0] == "umount":
            assert argv == ("umount", "--", str(mountpoint))
            assert attached
            attached = False
            commands.append("umount")
            return SimpleNamespace(stdout=b"")
        return run(argv, **kwargs)

    resident = False
    image_id = runtime.image_id
    monkeypatch.setattr(runtime, "_run", mounted_runtime)
    monkeypatch.setattr(runtime, "image_id", lambda ref: None if ref == CURRENT and not resident else image_id(ref))
    monkeypatch.setattr(runtime, "_predecessor_image_absent", lambda ref: ref == CURRENT and not resident)
    monkeypatch.setattr(runtime, "_image_document", lambda ref: {
        "Id": runtime.image_id(ref), "Os": "linux", "Architecture": "arm64",
        "Config": json.loads(config)["config"], "RootFS": {"Layers": layers},
    })
    assert recovery_startup.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_MEDIA_REQUIRED"}
    assert store.read() == pending
    assert runtime.starts == runtime.rewrites == 0

    with store.lock():
        assert recovery_startup.main(pending_only=True) == 0
        assert capsys.readouterr().out == ""
    assert recovery_startup.main(pending_only=True) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_MEDIA_REQUIRED"}
    assert not commands and store.read() == pending
    partition["uuid"] = USB_UUID
    sent = []

    def changed_after_precheck(source):
        block_size = mounted_media.ARCHIVE_BLOCK_BYTES
        sent.append(source.read(block_size))
        with archive.open("r+b") as victim:
            victim.seek(2 * block_size)
            victim.write(b"changed bytes")
        source.read()

    monkeypatch.setattr(runtime, "_load_ha_image", changed_after_precheck)
    assert recovery_startup.main(pending_only=True) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}
    assert sent == [original[:mounted_media.ARCHIVE_BLOCK_BYTES]]
    load_intent = store.read()
    assert load_intent["ha_data_restore"]["predecessor_load_identity"] == identity.to_dict()
    assert not resident and load_intent["phase"] == U11
    assert runtime.starts == runtime.rewrites == 0
    archive.write_bytes(original)

    def load(source):
        nonlocal resident
        assert source.read() == original
        resident = True
        raise InterruptedPower()

    monkeypatch.setattr(runtime, "_load_ha_image", load)
    with pytest.raises(InterruptedPower):
        recovery_startup.main(pending_only=True)
    assert resident and store.read() == load_intent
    assert runtime.starts == runtime.rewrites == 0
    assert commands == ["mount", "umount"] * 2 and not mountpoint.exists()
    attached = False
    inspect_image = runtime._image_document
    with monkeypatch.context() as patch:
        patch.setattr(runtime, "_image_document", lambda ref: {
            **inspect_image(ref), "RootFS": {"Layers": ["sha256:" + "f" * 64]},
        })
        assert recovery_startup.main() == 1
        assert json.loads(capsys.readouterr().out) == {"status": "RECOVERY_STARTUP_NEEDS_REVIEW"}
        available = json.loads(dispatcher.handle(request))
        assert available["accepted"] is True and available["phase"] == "RECOVERING"
        assert store.read() == load_intent
        assert runtime.starts == runtime.rewrites == 0

    def unavailable_projection():
        raise OSError("fixture status read failure")

    with monkeypatch.context() as patch:
        patch.setattr(projection_store, "read", unavailable_projection)
        unavailable = json.loads(dispatcher.handle(request))
        assert unavailable["accepted"] is False and unavailable["code"] == "ota_host_rejected"
        assert unavailable["error_code"] == "ota_host_status_unavailable"
        assert store.read() == load_intent
        assert recovery_startup.main(pending_only=True) == 0
        assert json.loads(dispatcher.handle(request)) == unavailable
    assert json.loads(capsys.readouterr().out) == {"status": "ROLLED_BACK"}
    restored = json.loads(dispatcher.handle(request))
    assert restored["accepted"] is True and restored["phase"] == "ROLLED_BACK"
    assert archive.read_bytes() == original
    assert store.read()["status"] == "ROLLED_BACK"
    assert store.read()["authorization_id_sha256"] == cutover["authorization_id_sha256"]
    assert runtime.starts == runtime.rewrites == 1
    assert recovery_startup.main(pending_only=True) == 0
    assert capsys.readouterr().out == ""
    assert runtime.starts == runtime.rewrites == 1 and commands == ["mount", "umount"] * 2


class SyntheticUsb:
    def __init__(self, root: Path):
        self.root = root
        self.report = assess_capacity(USB_BYTES, CAPACITY_INPUTS)

    def format(self):
        selected = select_single_eligible_device([candidate()])
        authorization = authorize_destructive_format(
            selected,
            FORMAT_CONFIRMATION,
        )
        self.root.mkdir(mode=0o700)
        metadata = {
            "synthetic_only": True,
            "partition_table": "GPT",
            "filesystem": "ext4",
            "label": "N3W-UPDATE",
            "filesystem_uuid": USB_UUID,
            "measured_usable_bytes": USB_BYTES,
        }
        (self.root / "media.json").write_text(
            json.dumps(metadata, sort_keys=True),
            encoding="utf-8",
        )
        return authorization

    def target_record(self, *, corrupt: bool = False) -> ImageRecoveryRecord:
        target_dir = self.root / "target"
        target_dir.mkdir(exist_ok=True)
        archive = target_dir / "homeassistant-target.bin"
        archive.write_bytes(TARGET_BYTES + (b"corrupt" if corrupt else b""))
        return ImageRecoveryRecord(
            kind="target",
            image_ref=TARGET,
            archive_sha256=sha(archive),
            archive_size_bytes=archive.stat().st_size,
            portable_identity_sha256=TARGET_IDENTITY,
            platform="linux/arm64",
            verified=True,
            fsynced=True,
        )


class SyntheticDockerHost:
    def __init__(self):
        self.images = {CURRENT: CURRENT_BYTES}
        self.identities = {CURRENT: CURRENT_IDENTITY}
        self.active = CURRENT

    def export_predecessor(self, media: SyntheticUsb) -> ImageRecoveryRecord:
        recovery = media.root / "predecessor"
        recovery.mkdir()
        archive = recovery / "homeassistant-predecessor.bin"
        archive.write_bytes(self.images[CURRENT])
        return ImageRecoveryRecord(
            kind="predecessor",
            image_ref=CURRENT,
            archive_sha256=sha(archive),
            archive_size_bytes=archive.stat().st_size,
            portable_identity_sha256=CURRENT_IDENTITY,
            platform="linux/arm64",
            verified=True,
            fsynced=True,
        )

    def verify_predecessor(
        self,
        media: SyntheticUsb,
        record: ImageRecoveryRecord,
    ) -> ImageRecoveryRecord:
        validated = validate_image_recovery_record(
            record,
            expected_kind="predecessor",
            expected_image_ref=CURRENT,
        )
        archive = media.root / "predecessor" / "homeassistant-predecessor.bin"
        if sha(archive) != validated.archive_sha256:
            raise UpdaterV2Error("synthetic_predecessor_corrupt")
        return validated

    def remove_predecessor(self, record: ImageRecoveryRecord) -> None:
        self.verify_identity(record)
        self.images.pop(CURRENT)
        self.identities.pop(CURRENT)
        self.active = None

    def verify_identity(self, record: ImageRecoveryRecord) -> None:
        if record.portable_identity_sha256 != CURRENT_IDENTITY:
            raise UpdaterV2Error("synthetic_predecessor_identity_mismatch")

    def load_target(self, record: ImageRecoveryRecord) -> None:
        validate_image_recovery_record(
            record,
            expected_kind="target",
            expected_image_ref=TARGET,
            expected_archive_sha256=TARGET_SHA,
        )
        self.images[TARGET] = TARGET_BYTES
        self.identities[TARGET] = TARGET_IDENTITY
        self.active = TARGET

    def restore_predecessor(
        self,
        media: SyntheticUsb,
        record: ImageRecoveryRecord,
    ) -> None:
        validated = self.verify_predecessor(media, record)
        archive = media.root / "predecessor" / "homeassistant-predecessor.bin"
        self.images[CURRENT] = archive.read_bytes()
        self.identities[CURRENT] = validated.portable_identity_sha256
        self.active = CURRENT


class SyntheticHaData:
    def __init__(self, root: Path):
        self.root = root
        self.running = True
        (root / ".storage").mkdir(parents=True)
        (root / "configuration.yaml").write_text("demo: true\n", encoding="utf-8")
        (root / ".storage" / "core.config").write_text(
            '{"version":"preupgrade"}\n',
            encoding="utf-8",
        )
        (root / "home-assistant_v2.db").write_bytes(b"sqlite-synthetic")

    def quiesce(self) -> None:
        assert self.running is True
        self.running = False

    def start_target(self) -> None:
        self.running = True
        (self.root / ".storage" / "core.config").write_text(
            '{"version":"target-migrated"}\n',
            encoding="utf-8",
        )
        (self.root / ".storage" / "r2-target-marker").write_text(
            "present\n",
            encoding="utf-8",
        )

    def create_backup(self, media: SyntheticUsb) -> HaDataBackupRecord:
        assert self.running is False
        entries = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            entries.append(
                {
                    "path": path.relative_to(self.root).as_posix(),
                    "mode": stat.S_IMODE(path.stat().st_mode),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "payload": base64.b64encode(raw).decode("ascii"),
                }
            )
        payload = {
            "schema": "gh.n3w-r2-synthetic-ha-backup/1",
            "synthetic_confidentiality_contract": True,
            "synthetic_authenticity_contract": True,
            "entries": entries,
        }
        backup_dir = media.root / "ha-data"
        backup_dir.mkdir()
        archive = backup_dir / "preupgrade.sim.json"
        archive.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        manifest = backup_dir / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "archive_sha256": sha(archive),
                    "archive_size_bytes": archive.stat().st_size,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return HaDataBackupRecord(
            archive_sha256=sha(archive),
            archive_size_bytes=archive.stat().st_size,
            manifest_sha256=sha(manifest),
            verified=True,
            fsynced=True,
            consistent_preupgrade_point=True,
            complete_production_config=True,
            storage_integrity_verified=True,
            ownership_metadata_present=True,
            confidentiality_protected=True,
            authenticity_protected=True,
            unsupported_external_state=False,
        )

    def verify_backup(
        self,
        media: SyntheticUsb,
        record: HaDataBackupRecord,
    ) -> HaDataBackupRecord:
        validated = validate_backup_record(record)
        archive = media.root / "ha-data" / "preupgrade.sim.json"
        manifest = media.root / "ha-data" / "manifest.json"
        if (
            sha(archive) != validated.archive_sha256
            or archive.stat().st_size != validated.archive_size_bytes
            or sha(manifest) != validated.manifest_sha256
        ):
            raise UpdaterV2Error("synthetic_ha_backup_corrupt")
        payload = json.loads(archive.read_text(encoding="utf-8"))
        if (
            payload["synthetic_confidentiality_contract"] is not True
            or payload["synthetic_authenticity_contract"] is not True
        ):
            raise UpdaterV2Error("synthetic_ha_backup_protection_invalid")
        for entry in payload["entries"]:
            raw = base64.b64decode(entry["payload"].encode("ascii"), validate=True)
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise UpdaterV2Error("synthetic_ha_backup_entry_corrupt")
        return validated

    def restore_backup(
        self,
        media: SyntheticUsb,
        record: HaDataBackupRecord,
    ) -> None:
        self.verify_backup(media, record)
        payload = json.loads(
            (media.root / "ha-data" / "preupgrade.sim.json").read_text(
                encoding="utf-8"
            )
        )
        shutil.rmtree(self.root)
        self.root.mkdir(mode=0o700)
        for entry in payload["entries"]:
            relative = Path(entry["path"])
            assert not relative.is_absolute()
            assert ".." not in relative.parts
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(
                base64.b64decode(entry["payload"].encode("ascii"), validate=True)
            )
            os.chmod(destination, entry["mode"])
        self.running = True


def prepare_to_u4(tmp_path: Path):
    media = SyntheticUsb(tmp_path / "synthetic-usb")
    docker = SyntheticDockerHost()
    ha = SyntheticHaData(tmp_path / "synthetic-config")
    tx = request_prepare(transaction())
    authorization = media.format()
    tx = record_media_bound(
        tx,
        format_authorization=authorization,
        filesystem_uuid=USB_UUID,
        measured_usable_bytes=USB_BYTES,
        capacity_report=media.report,
    )
    tx = start_target_preparation(tx)
    target = media.target_record()
    tx = record_target_ready(tx, target=target)
    return tx, media, docker, ha, target


@pytest.mark.parametrize("fault", (
    None, "wrong_uuid", "duplicate_uuid", "same_disk", "archive_drift",
    "symlink", "internal_space", "occupied_backup", "restore", "unsafe_load_tag",
    "release_space_drift", "release_archive_drift",
))
def test_verify_existing_usb_media_from_bound_archives(tmp_path, monkeypatch, fault):
    media = SyntheticUsb(tmp_path / "original")
    media.root.mkdir()
    sentinel = media.root / "existing-user-file"
    sentinel.write_bytes(b"keep unchanged")
    target = media.target_record()
    target_archive = tmp_path / "target.tar"
    _write_restorable_image_archive(target_archive, reference=TARGET)
    target = _bind_test_image(target, target_archive)
    predecessor = SyntheticDockerHost().export_predecessor(media)
    original_archive = tmp_path / "predecessor.tar"
    _write_restorable_image_archive(original_archive, extra_tag=fault == "unsafe_load_tag")
    identity = parse_image_archive(original_archive, expected_tag=CURRENT)
    predecessor = replace(
        predecessor, archive_sha256=identity.archive_sha256, archive_size_bytes=identity.archive_size_bytes,
        portable_identity_sha256=sha256_bytes(canonical(identity.to_dict())),
    )
    created = transaction(target=target, predecessor_portable=predecessor.portable_identity_sha256)
    initial = record_existing_media_bound(
        request_prepare(created), filesystem_uuid=USB_UUID, capacity_report=media.report,
    )
    store = HaUsbStateStore(tmp_path / "state")
    store.write(initial)
    ipc = HaUsbIpcExecutor(store=store, admission_resolver=SimpleNamespace())
    assert ipc.status()["phase"] == "USB_QUALIFIED_BOUND"
    downloading = start_target_preparation(initial)
    with pytest.raises(UpdaterV2Error, match="prepared_predecessor_missing"):
        record_target_ready(downloading, target=target)
    prepared = record_target_ready(downloading, target=target, predecessor=predecessor)
    pending = request_install(prepared)
    archive_dir = media.root / "N3W-OTA" / pending["transaction_id_sha256"]
    archive_dir.mkdir(parents=True)
    shutil.copyfile(target_archive, archive_dir / "target.tar")
    shutil.copyfile(original_archive, archive_dir / "predecessor.tar")
    ha = SyntheticHaData(tmp_path / "ha")

    actual_device = mounted_media._device_number(media.root.stat().st_dev)
    protected_device = "8:3"
    partition = {"type": "part", "uuid": USB_UUID, "maj:min": actual_device}
    children = [partition]
    if fault == "duplicate_uuid":
        children.append({**partition, "maj:min": "8:99"})
    if fault == "same_disk":
        children.append({"type": "part", "maj:min": protected_device})
    devices = [{"type": "disk", "tran": "usb", "maj:min": "8:0", "size": USB_MEDIA_MIN_CAPACITY_BYTES, "children": children}]
    mounts = [{
        "target": str(media.root),
        "fstype": "ext4", "fsroot": "/", "options": "rw,nosuid",
        "maj:min": actual_device, "uuid": OTHER_UUID if fault == "wrong_uuid" else USB_UUID,
    }]
    commands = []

    def metadata(*argv):
        commands.append(argv[0])
        return {"filesystems": mounts} if argv[0] == "findmnt" else {"blockdevices": devices}

    monkeypatch.setattr(mounted_media, "_command_json", metadata)
    monkeypatch.setattr(mounted_media, "_protected_devices", lambda _: {protected_device})
    fstatvfs = os.fstatvfs
    monkeypatch.setattr(mounted_media.os, "fstatvfs", lambda fd: SimpleNamespace(
        f_blocks=USB_BYTES, f_bfree=USB_BYTES // 2, f_bavail=USB_BYTES // 2, f_frsize=1,
        f_fsid=fstatvfs(fd).f_fsid,
    ))
    available = (4 if fault == "internal_space" else 16) * 1024 * 1024
    monkeypatch.setattr(mounted_media.os, "statvfs", lambda _: SimpleNamespace(f_bavail=available, f_frsize=1))
    if fault == "archive_drift":
        with (archive_dir / "target.tar").open("r+b") as changed:
            changed.write(b"changed before admission")
    if fault == "symlink":
        (archive_dir / "target.tar").unlink()
        (archive_dir / "target.tar").symlink_to(
            media.root / "target" / "homeassistant-target.bin"
        )

    verifier = mounted_media.HaMountedInstallMaterialVerifier(
        mountpoint=media.root,
        internal_storage=tmp_path,
        image_storage=tmp_path,
        ha_data_root=ha.root,
        budget=lambda _: mounted_media.HaInstallSpaceBudget(1024, 2048),
        verify_prestate=lambda _: True,
    )
    errors = {
        "wrong_uuid": "usb_filesystem_uuid_mismatch",
        "duplicate_uuid": "ha_usb_original_filesystem_not_unique",
        "same_disk": "ha_usb_original_mount_device_mismatch",
        "archive_drift": "ha_usb_recovery_archive_digest_mismatch",
        "symlink": "ha_usb_original_material_unavailable",
        "unsafe_load_tag": "ha_usb_predecessor_archive_identity_invalid",
    }
    if fault in errors:
        with pytest.raises(UpdaterV2Error, match=errors[fault]):
            verifier.verify_install_materials(pending)
    else:
        observed = verifier.verify_install_materials(pending)
        assert observed.target == target
        assert observed.predecessor == predecessor
        assert observed.capacity.capacity_pass is True
        assert observed.internal_space.recovery_required_bytes > 2 * 1024 * 1024
        if fault == "internal_space":
            assert max(observed.internal_space.install_required_bytes, observed.internal_space.recovery_required_bytes) < available
            assert available < observed.internal_space.install_required_bytes + observed.internal_space.recovery_required_bytes
            available = max(observed.internal_space.install_required_bytes, observed.internal_space.recovery_required_bytes) - 1
            assert not verifier.verify_install_materials(pending).capacity.capacity_pass
            assert commands == ["findmnt", "lsblk"] * 4
            return
        assert commands == ["findmnt", "lsblk", "findmnt", "lsblk"]
    assert set(commands) <= {"findmnt", "lsblk"}
    assert sentinel.read_bytes() == b"keep unchanged"
    if fault in {None, "occupied_backup", "restore", "release_space_drift", "release_archive_drift"}:
        store.write(pending)
        runtime = PredecessorRuntime(store)
        config = ha.root / ".storage" / "core.config"
        config.chmod(0o640)
        original_config = config.read_bytes()
        (ha.root / "config-link").symlink_to("configuration.yaml")
        if fault == "restore":
            payload = ha.root / "synthetic-history.bin"
            payload.write_bytes(os.urandom(1088 * 1024))
        work = tmp_path / "internal-work"
        work.mkdir(mode=0o700)
        key = work / "fixture-root"
        key.write_bytes(os.urandom(32))
        key.chmod(0o600)
        donor_path = work / "recorder.db"
        donor = sqlite3.connect(donor_path)
        try:
            donor.execute("PRAGMA journal_mode=WAL")
            donor.execute("PRAGMA wal_autocheckpoint=0")
            donor.execute("CREATE TABLE records (value TEXT)")
            donor.execute("INSERT INTO records VALUES ('quiesced test data')")
            donor.commit()
            database = ha.root / "home-assistant_v2.db"
            for suffix in ("", "-wal", "-shm"):
                shutil.copyfile(str(donor_path) + suffix, str(database) + suffix)
        finally:
            donor.close()
        db_files = sorted(ha.root.glob("home-assistant_v2.db*"))
        before = {path: sha(path) for path in db_files}
        backups = mounted_media.HaMountedBackupProvider(
            store=store, mountpoint=media.root, internal_storage=tmp_path,
            backup=ProtectedHaDataBackup(
                work_root=work, ha_data_root=ha.root, system_root_key=key,
                product_config=work / "fixture-config.yaml",
            ),
            verify_quiesced=lambda: runtime.running == {"broker"},
        )
        backup_dir = archive_dir / "ha-backup"
        expected = "ha_usb_install_cutover_not_consumed"
        if fault == "release_space_drift":
            expected = "ha_usb_install_materials_unavailable"
        elif fault == "release_archive_drift":
            expected = "ha_usb_recovery_archive_digest_mismatch"
        if fault == "occupied_backup":
            backup_dir.mkdir()
            (backup_dir / BACKUP_ARCHIVE_NAME).write_bytes(b"preserve existing backup")
            expected = "ha_data_backup_destination_occupied"
        recovery = HaPredecessorRecovery(store, runtime, runtime)
        outcome = (
            nullcontext() if fault == "restore" else pytest.raises(UpdaterV2Error, match=expected)
        )
        with outcome, recovery.install_recovery_point(verifier, backups, acceptance=SyntheticAcceptance()) as document:
            assert document["phase"] == U8
            assert document["install_recovery_materials"]["predecessor"] == predecessor.public()
            record = backup_record_from_document(document["install_recovery_materials"]["backup"])
            assert backups.verify_backup(record) == record
            with pytest.raises(UpdaterV2Error, match="release_admission_missing"):
                claim_live_authorization(document, AUTHORIZATION_ID)
            if fault == "release_space_drift":
                available = 4096
                recovery.admit_predecessor_release(verifier, backups, AUTHORIZATION_ID)
            if fault == "release_archive_drift":
                with (archive_dir / "predecessor.tar").open("r+b") as changed:
                    changed.write(b"changed after admission")
                recovery.admit_predecessor_release(verifier, backups, AUTHORIZATION_ID)
            if fault == "restore":
                with (
                    pytest.raises(UpdaterV2Error, match="restore_phase_invalid"),
                    backups.stage_preupgrade_data(),
                ):
                    pytest.fail("an unclaimed transaction must not stage a restore")
                space = verifier.verify_install_materials(document).internal_space
                # This direct data-publication fixture models a transaction written by older code.
                claimed = claim_live_authorization(document, AUTHORIZATION_ID, internal_space=replace(
                    space, recovery_workspace_bytes=None,
                ))
                assert claimed["predecessor_release_admission"]["recovery_required_bytes"] > 3 * 1024 * 1024
                cutover = record_target_started(record_predecessor_capacity_released(claimed))
                store.write(cutover)
        if fault == "restore":
            archive = backup_dir / BACKUP_ARCHIVE_NAME
            ciphertext = archive.read_bytes()
            assert len(ciphertext) > 1024 * 1024
            config.write_bytes(b"new version's data")
            live_inode = ha.root.stat().st_ino
            with store.lock():
                runtime.running.add("homeassistant")
                with (
                    pytest.raises(UpdaterV2Error, match="restore_writers_not_quiesced"),
                    backups.stage_preupgrade_data(),
                ):
                    pytest.fail("HA must be stopped before restoring")
                runtime.running.remove("homeassistant")
                mounts[0]["uuid"] = OTHER_UUID
                with (
                    pytest.raises(UpdaterV2Error, match="usb_filesystem_uuid_mismatch"),
                    backups.stage_preupgrade_data(),
                ):
                    pytest.fail("the wrong USB must not supply the restore")
                mounts[0]["uuid"] = USB_UUID

                ciphertext_identity = backups.backup._ciphertext_identity

                def change_ciphertext_after_authentication(*args, **kwargs):
                    identity = ciphertext_identity(*args, **kwargs)
                    archive.write_bytes(ciphertext[:-1] + bytes([ciphertext[-1] ^ 1]))
                    return identity

                with monkeypatch.context() as patch:
                    patch.setattr(backups.backup, "_ciphertext_identity", change_ciphertext_after_authentication)
                    with (
                        pytest.raises(UpdaterV2Error, match="backup_archive_changed"),
                        backups.stage_preupgrade_data(),
                    ):
                        pytest.fail("the changed ciphertext must never reach the recovery caller")
                assert not list(work.glob(".ha-restore-*"))
                archive.write_bytes(ciphertext)

                mounts[0]["options"] = "ro,nosuid"
                with pytest.raises(UpdaterV2Error, match="original_mount_not_writable"):
                    verifier.verify_install_materials(cutover)
                with backups.stage_preupgrade_data() as stage:
                    staged_config = stage / config.relative_to(ha.root)
                    assert staged_config.read_bytes() == original_config
                    assert stat.S_IMODE(staged_config.stat().st_mode) == 0o640
                    assert (stage / "config-link").readlink() == Path("configuration.yaml")
                    assert sha(stage / payload.name) == sha(payload)
                    assert stat.S_IMODE(stage.parent.stat().st_mode) == 0o700
                    assert all(sha(stage / path.name) == digest for path, digest in before.items())
                    assert config.read_bytes() == b"new version's data"
                assert not stage.exists()
            assert archive.read_bytes() == ciphertext
            assert store.read() == cutover
            assert ha.root.stat().st_ino == live_inode
            assert sentinel.read_bytes() == b"keep unchanged"
            assert {path: sha(path) for path in db_files} == before
            _exercise_durable_data_restore(backups, ipc, runtime, mounts, config, original_config, monkeypatch)
            assert archive.read_bytes() == ciphertext
            assert sentinel.read_bytes() == b"keep unchanged"
            return
        assert store.read()["status"] == "ROLLED_BACK"
        assert store.read()["authorization_consumed"] is False
        assert sentinel.read_bytes() == b"keep unchanged"
        assert {path: sha(path) for path in db_files} == before
        archive = backup_dir / BACKUP_ARCHIVE_NAME
        if fault == "occupied_backup":
            assert archive.read_bytes() == b"preserve existing backup"
            assert not (backup_dir / BACKUP_METADATA_NAME).exists()
        else:
            ciphertext = archive.read_bytes()
            assert ciphertext.startswith(b"Salted__")
            assert b"quiesced test data" not in ciphertext
            metadata = backup_dir / BACKUP_METADATA_NAME
            original = metadata.read_bytes()
            changed = json.loads(original)
            changed["auth_tag_sha256"] = "0" * 64
            metadata.write_text(json.dumps(changed))
            with pytest.raises(UpdaterV2Error, match="backup_authentication_failed"):
                backups.verify_backup(record)
            metadata.write_bytes(original)
            archive.write_bytes(ciphertext[:-1] + bytes([ciphertext[-1] ^ 1]))
            with pytest.raises(UpdaterV2Error, match="archive_hash_mismatch"):
                backups.verify_backup(record)


def _exercise_durable_data_restore(backups, ipc, runtime, mounts, config, original_config, monkeypatch):
    store = backups.store
    transaction = store.read()
    live = backups.backup.ha_data_root
    old_inode = live.stat().st_ino
    workspace = backups.backup.work_root / f'.ha-restore-{transaction["transaction_id_sha256"]}'
    workspace.mkdir(mode=0o700)
    stranger = workspace / "unrelated"
    stranger.write_bytes(b"keep this")
    with store.lock(), pytest.raises(UpdaterV2Error, match="restore_workspace_occupied"):
        backups.restore_preupgrade_data()
    assert stranger.read_bytes() == b"keep this"
    assert store.read() == transaction
    stranger.unlink()
    workspace.rmdir()

    def interrupt_staging(directory, transaction_id, record, destination):
        destination.mkdir()
        (destination / "partial").write_bytes(b"interrupted extraction")
        raise InterruptedPower()

    with monkeypatch.context() as patch:
        patch.setattr(backups.backup, "restore_to_stage", interrupt_staging)
        with store.lock(), pytest.raises(InterruptedPower):
            backups.restore_preupgrade_data()
    assert store.read()["ha_data_restore"]["step"] == "STAGING"
    assert config.read_bytes() == b"new version's data"
    assert ipc.status()["phase"] == "RECOVERING"
    assert not ha_usb_mod.destructive_cutover_allowed(store.read())

    exchange = mounted_media._exchange_directories

    def interrupt_before_exchange(*args):
        raise InterruptedPower()

    with monkeypatch.context() as patch:
        patch.setattr(mounted_media, "_exchange_directories", interrupt_before_exchange)
        with store.lock(), pytest.raises(InterruptedPower):
            backups.restore_preupgrade_data()
    assert not (workspace / "data" / "partial").exists()
    pending = store.read()
    assert pending["ha_data_restore"]["step"] == "EXCHANGE_PENDING"
    assert live.stat().st_ino == old_inode
    with pytest.raises(UpdaterV2Error, match="data_restore_journal_invalid"):
        record_rollback_complete(
            pending, observed_usb_filesystem_uuid=USB_UUID,
            predecessor_image_restored=True, ha_data_backup_restored=True,
        )

    def interrupt_after_exchange(*args):
        exchange(*args)
        raise InterruptedPower()

    with monkeypatch.context() as patch:
        patch.setattr(mounted_media, "_exchange_directories", interrupt_after_exchange)
        with store.lock(), pytest.raises(InterruptedPower):
            backups.restore_preupgrade_data()
    assert store.read() == pending
    assert config.read_bytes() == original_config
    assert (workspace / "data").stat().st_ino == old_inode
    assert (workspace / "data" / config.relative_to(live)).read_bytes() == b"new version's data"
    assert ipc.status()["phase"] == "RECOVERING"

    with monkeypatch.context() as patch:
        patch.setattr(mounted_media, "_exchange_directories", lambda *args: pytest.fail("duplicate swap"))
        patch.setattr(backups.backup, "restore_to_stage", lambda *args: pytest.fail("duplicate extraction"))
        mounts.clear()
        reopened = HaUsbStateStore(store.root)
        backups.store = reopened
        with reopened.lock():
            backups.restore_preupgrade_data()
        published = reopened.read()
        assert published["ha_data_restore"]["step"] == "PUBLISHED"
        assert published["authorization_id_sha256"] == transaction["authorization_id_sha256"]
        runtime.running.add("homeassistant")
        config.write_bytes(b"legitimate write after predecessor restart")
        with reopened.lock():
            backups.restore_preupgrade_data()
        assert reopened.read() == published
        assert config.read_bytes() == b"legitimate write after predecessor restart"
    result = record_rollback_complete(
        published, observed_usb_filesystem_uuid=USB_UUID,
        predecessor_image_restored=True, ha_data_backup_restored=True,
    )
    assert result["phase"] == U13B
    assert result["recovery_required"] is False


class InstallMaterialFixture:
    def __init__(self, media, target, predecessor, ha, runtime, drift):
        self.media = media
        self.target = target
        self.predecessor = predecessor
        self.ha = ha
        self.runtime = runtime
        self.drift = drift
        self.preflight_phases = []

    def verify_install_materials(self, document):
        self.preflight_phases.append(document["phase"])
        target = self.target
        if self.drift == "target_size":
            target = replace(target, archive_size_bytes=target.archive_size_bytes + 1)
        return HaInstallMaterials(
            filesystem_uuid=(
                OTHER_UUID if self.drift == "usb_after_stop" and document["phase"] == U7
                else USB_UUID
            ),
            target=target,
            predecessor=self.predecessor,
            capacity=self.media.report,
            production_prestate_exact=True,
        )

    def create_consistent_backup(self, *, transaction_id_sha256):
        assert self.runtime.running == {"broker"}
        assert transaction_id_sha256 == self.runtime.store.read()["transaction_id_sha256"]
        self.ha.quiesce()
        return self.ha.create_backup(self.media)

    def verify_backup(self, record):
        return self.ha.verify_backup(self.media, record)


@pytest.mark.parametrize(
    ("drift", "expected", "expected_phase"),
    [
        ("target_size", "ha_usb_install_target_size_drift", U4),
        ("baseline_missing", "ha_usb_predecessor_acceptance_baseline_unavailable", U4),
        ("usb_after_stop", "usb_filesystem_uuid_mismatch", U7),
        (None, "ha_usb_install_cutover_not_consumed", U8),
    ],
)
def test_ipc_install_request_reaches_qualified_recovery_point(
    tmp_path, drift, expected, expected_phase
):
    current, media, docker, ha, target = prepare_to_u4(tmp_path)
    predecessor = docker.verify_predecessor(media, docker.export_predecessor(media))
    store = HaUsbStateStore(tmp_path / "state")
    store.write(current)
    runtime = PredecessorRuntime(store)
    fixture = InstallMaterialFixture(media, target, predecessor, ha, runtime, drift)
    admission_fields = {
        key: current[key]
        for key in ("current_image_ref", "current_image_identity", "target_manifest_identity",
                    "target_image_ref", "target_archive_sha256", "target_archive_size")
    }
    release = current["target_manifest_identity"]["release_identity"]
    resolver = SimpleNamespace(
        resolve_homeassistant_release=lambda release_id: HostOtaAdmission(
            release_identity=release_id, **admission_fields
        )
    )
    install_ready = threading.Event()
    executor = HaUsbIpcExecutor(
        store=store, admission_resolver=resolver, install_ready=install_ready
    )
    dispatcher = HaUsbIpcDispatcher(executor)
    response = json.loads(dispatcher.handle(json.dumps({
        "schema": REQUEST_SCHEMA, "operation": "submit", "action": "INSTALL",
        "target_release_id": release,
    }).encode()))
    assert response["accepted"] is True
    assert runtime.stop_count == 0
    assert store.read()["phase"] == U5
    assert install_ready.is_set()

    observer = SyntheticAcceptance()
    if drift == "baseline_missing":
        observer.capture_baseline = lambda _: {}
    with (
        pytest.raises(UpdaterV2Error, match=expected),
        HaPredecessorRecovery(store, runtime, runtime).install_recovery_point(
            fixture, fixture, acceptance=observer,
        )
        as ready,
    ):
        assert ready["phase"] == U8
        assert store.read()["install_recovery_materials"]["target"] == target.public()
        assert runtime.running == {"broker"}
        with pytest.raises(UpdaterV2Error, match="upgrade_transaction_busy"):
            with store.lock():
                pytest.fail("cutover uses the existing lock")
    result = store.read()
    assert result["phase"] == expected_phase
    assert result["authorization_consumed"] is False
    assert runtime.running == {"manager", "homeassistant", "broker"}
    if expected_phase == U4:
        assert runtime.stop_count == runtime.start_count == 0
        assert fixture.preflight_phases == [U5]
        failure_code = expected if drift == "baseline_missing" else "ha_usb_install_revalidation_failed"
        assert executor.status()["error_code"] == failure_code
    else:
        assert runtime.stop_count == runtime.start_count == 1
        assert fixture.preflight_phases == [U5, U7]
        assert executor.status()["phase"] == "ROLLED_BACK"


def drive_to_u8(tmp_path: Path):
    tx, media, docker, ha, target = prepare_to_u4(tmp_path)
    tx = request_install(tx)
    assert tx["phase"] == U5
    assert tx["authorization_claimed"] is False
    assert tx["authorization_consumed"] is False

    tx = start_predecessor_recovery(tx)
    predecessor = docker.export_predecessor(media)
    predecessor = docker.verify_predecessor(media, predecessor)

    ha.quiesce()
    tx = record_predecessor_recovery_and_ha_quiesced(
        tx,
        predecessor=predecessor,
        ha_quiesced=ha.running is False,
    )
    assert tx["phase"] == U7

    backup = ha.create_backup(media)
    backup = ha.verify_backup(media, backup)
    tx = record_recovery_admission(
        tx,
        target=target,
        predecessor=predecessor,
        backup=backup,
        observed_usb_filesystem_uuid=USB_UUID,
        capacity_report=media.report,
        production_prestate_exact=(docker.active == CURRENT),
    )
    assert tx["phase"] == U8
    return tx, media, docker, ha, target, predecessor, backup


def test_r2_prepare_reaches_ready_without_stopping_ha_or_exporting_predecessor(tmp_path):
    tx, media, docker, ha, _target = prepare_to_u4(tmp_path)
    assert tx["phase"] == U4
    assert tx["target_artifact_verified"] is True
    assert tx["authorization_claimed"] is False
    assert ha.running is True
    assert docker.active == CURRENT
    assert CURRENT in docker.images
    assert not (media.root / "predecessor").exists()
    assert not (media.root / "ha-data").exists()
    metadata = json.loads((media.root / "media.json").read_text(encoding="utf-8"))
    assert metadata["synthetic_only"] is True
    assert metadata["partition_table"] == "GPT"
    assert metadata["filesystem"] == "ext4"
    assert metadata["label"] == "N3W-UPDATE"


def test_r2_corrupt_target_stops_before_ready_and_leaves_production_unchanged(tmp_path):
    media = SyntheticUsb(tmp_path / "synthetic-usb")
    docker = SyntheticDockerHost()
    ha = SyntheticHaData(tmp_path / "synthetic-config")
    tx = request_prepare(transaction())
    tx = record_media_bound(
        tx,
        format_authorization=media.format(),
        filesystem_uuid=USB_UUID,
        measured_usable_bytes=USB_BYTES,
        capacity_report=media.report,
    )
    tx = start_target_preparation(tx)
    corrupt = media.target_record(corrupt=True)
    with pytest.raises(
        UpdaterV2Error,
        match="image_recovery_archive_sha256_mismatch",
    ):
        record_target_ready(tx, target=corrupt)
    assert ha.running is True
    assert docker.active == CURRENT
    assert CURRENT in docker.images


def test_r2_predecessor_corruption_stops_before_u7_and_u9(tmp_path):
    tx, media, docker, ha, _target = prepare_to_u4(tmp_path)
    tx = start_predecessor_recovery(request_install(tx))
    predecessor = docker.export_predecessor(media)
    archive = media.root / "predecessor" / "homeassistant-predecessor.bin"
    archive.write_bytes(archive.read_bytes() + b"corrupt")
    with pytest.raises(UpdaterV2Error, match="synthetic_predecessor_corrupt"):
        docker.verify_predecessor(media, predecessor)
    assert tx["authorization_claimed"] is False
    assert ha.running is True
    assert docker.active == CURRENT


def test_r2_backup_corruption_stops_before_u8_and_u9(tmp_path):
    tx, media, docker, ha, _target = prepare_to_u4(tmp_path)
    tx = start_predecessor_recovery(request_install(tx))
    predecessor = docker.verify_predecessor(
        media,
        docker.export_predecessor(media),
    )
    ha.quiesce()
    tx = record_predecessor_recovery_and_ha_quiesced(
        tx,
        predecessor=predecessor,
        ha_quiesced=True,
    )
    backup = ha.create_backup(media)
    archive = media.root / "ha-data" / "preupgrade.sim.json"
    archive.write_text(archive.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(UpdaterV2Error, match="synthetic_ha_backup_corrupt"):
        ha.verify_backup(media, backup)
    assert tx["phase"] == U7
    assert tx["authorization_claimed"] is False
    assert docker.active == CURRENT


def test_r2_success_keeps_target_migrated_config(tmp_path):
    tx, media, docker, ha, target, predecessor, backup = drive_to_u8(tmp_path)
    tx = claim_live_authorization(tx, AUTHORIZATION_ID)
    assert tx["phase"] == U9

    docker.remove_predecessor(predecessor)
    tx = record_predecessor_capacity_released(tx)
    assert tx["phase"] == U10
    assert CURRENT not in docker.images

    docker.load_target(target)
    ha.start_target()
    tx = record_target_started(tx)
    assert tx["phase"] == U11
    tx = record_target_accepted(tx)
    assert tx["phase"] == U12
    tx = record_commit(tx)
    assert tx["phase"] == U13A
    assert tx["status"] == "COMMITTED"
    assert docker.active == TARGET
    assert (ha.root / ".storage" / "r2-target-marker").is_file()
    assert "target-migrated" in (
        ha.root / ".storage" / "core.config"
    ).read_text(encoding="utf-8")
    assert backup is not None


def test_r2_failed_target_restores_predecessor_and_preupgrade_data(tmp_path):
    tx, media, docker, ha, target, predecessor, backup = drive_to_u8(tmp_path)
    tx = claim_live_authorization(tx, AUTHORIZATION_ID)
    docker.remove_predecessor(predecessor)
    tx = record_predecessor_capacity_released(tx)
    docker.load_target(target)
    ha.start_target()
    tx = record_target_started(tx)
    assert tx["phase"] == U11
    assert (ha.root / ".storage" / "r2-target-marker").exists()

    docker.restore_predecessor(media, predecessor)
    ha.restore_backup(media, backup)
    tx = record_rollback_complete(
        tx,
        observed_usb_filesystem_uuid=USB_UUID,
        predecessor_image_restored=(docker.active == CURRENT),
        ha_data_backup_restored=(
            "preupgrade"
            in (ha.root / ".storage" / "core.config").read_text(encoding="utf-8")
        ),
    )
    assert tx["phase"] == U13B
    assert tx["status"] == "ROLLED_BACK"
    assert docker.active == CURRENT
    assert TARGET in docker.images
    assert not (ha.root / ".storage" / "r2-target-marker").exists()
    assert ha.running is True


def test_r2_rollback_requires_both_image_and_data_restore(tmp_path):
    tx, media, docker, ha, _target, predecessor, backup = drive_to_u8(tmp_path)
    tx = claim_live_authorization(tx, AUTHORIZATION_ID)
    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_rollback_predecessor_not_restored",
    ):
        record_rollback_complete(
            tx,
            observed_usb_filesystem_uuid=USB_UUID,
            predecessor_image_restored=False,
            ha_data_backup_restored=True,
        )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_rollback_data_not_restored",
    ):
        record_rollback_complete(
            tx,
            observed_usb_filesystem_uuid=USB_UUID,
            predecessor_image_restored=True,
            ha_data_backup_restored=False,
        )
    assert predecessor is not None
    assert backup is not None
    assert docker.active == CURRENT
    assert ha.running is False


def test_r2_power_loss_before_u9_keeps_predecessor_authority(tmp_path):
    tx, media, docker, ha, _target = prepare_to_u4(tmp_path)
    tx = start_predecessor_recovery(request_install(tx))
    predecessor = docker.verify_predecessor(
        media,
        docker.export_predecessor(media),
    )
    ha.quiesce()
    tx = record_predecessor_recovery_and_ha_quiesced(
        tx,
        predecessor=predecessor,
        ha_quiesced=True,
    )
    store = HaUsbStateStore(tmp_path / "state")
    store.write(tx)
    recovered = store.read()
    assert recovered is not None
    assert recovered["phase"] == U7
    assert recovered["authorization_claimed"] is False
    assert CURRENT in docker.images
    assert classify_power_loss_reentry(
        recovered,
        usb_present=False,
        observed_usb_filesystem_uuid=None,
    ) == "PRE_U9_PREDECESSOR_AUTHORITY"


def test_r2_power_loss_after_u9_requires_same_recovery_media(tmp_path):
    tx, _media, _docker, _ha, _target, _predecessor, _backup = drive_to_u8(tmp_path)
    tx = claim_live_authorization(tx, AUTHORIZATION_ID)
    store = HaUsbStateStore(tmp_path / "state")
    store.write(tx)
    recovered = store.read()
    assert recovered is not None
    assert recovered["phase"] == U9

    assert classify_power_loss_reentry(
        recovered,
        usb_present=False,
        observed_usb_filesystem_uuid=None,
    ) == "RECOVERY_MEDIA_REQUIRED"
    assert classify_power_loss_reentry(
        recovered,
        usb_present=True,
        observed_usb_filesystem_uuid=USB_UUID,
    ) == "ROLLBACK_REQUIRED"
    with pytest.raises(UpdaterV2Error, match="usb_filesystem_uuid_mismatch"):
        classify_power_loss_reentry(
            recovered,
            usb_present=True,
            observed_usb_filesystem_uuid=OTHER_UUID,
        )


def test_r2_u12_power_loss_can_only_forward_commit_with_same_media(tmp_path):
    tx, _media, docker, ha, target, predecessor, _backup = drive_to_u8(tmp_path)
    tx = claim_live_authorization(tx, AUTHORIZATION_ID)
    docker.remove_predecessor(predecessor)
    tx = record_predecessor_capacity_released(tx)
    docker.load_target(target)
    ha.start_target()
    tx = record_target_started(tx)
    tx = record_target_accepted(tx)
    assert tx["phase"] == U12
    assert classify_power_loss_reentry(
        tx,
        usb_present=True,
        observed_usb_filesystem_uuid=USB_UUID,
    ) == "FORWARD_COMMIT_ELIGIBLE"


def test_status_publishes_committed_version_and_survives_next_prepare_interruption(tmp_path, monkeypatch):
    prepared, *_ = drive_to_u8(tmp_path)
    started = record_target_started(record_predecessor_capacity_released(
        claim_live_authorization(prepared, AUTHORIZATION_ID)
    ))
    accepted = record_target_accepted(started)
    committed = record_commit(accepted)
    rolled_back = record_rollback_complete(
        started, observed_usb_filesystem_uuid=USB_UUID,
        predecessor_image_restored=True, ha_data_backup_restored=True,
    )
    store = HaUsbStateStore(tmp_path / "projection-state")
    executor = HaUsbIpcExecutor(store=store, admission_resolver=None)
    dispatcher = HaUsbIpcDispatcher(executor)

    def status(operation=VERSIONED_STATUS_OPERATION):
        request = {"schema": REQUEST_SCHEMA, "operation": operation}
        return json.loads(dispatcher.handle(json.dumps(request).encode()))

    assert status()["installed_version"] is None
    for document, phase, version in (
        (started, "TARGET_INSTALLED_STARTED", "2026.10.0"),
        (accepted, "TARGET_ACCEPTANCE", "2026.10.0"),
        (rolled_back, "ROLLED_BACK", "2026.10.0"),
        (committed, "COMMITTED", "2026.10.4"),
    ):
        store.write(document)
        before = store.path.read_bytes()
        assert status() == {
            "schema": VERSIONED_STATUS_SCHEMA, "accepted": True, "code": "status",
            "phase": phase, "progress_percent": None, "error_code": None,
            "installed_version": version,
        }
        legacy = status("status")
        assert legacy["schema"] == RESPONSE_SCHEMA and "installed_version" not in legacy
        assert store.path.read_bytes() == before

    replacement = request_prepare(new_transaction(
        current_image_ref=committed["target_image_ref"], current_image_identity={"test": "predecessor"},
        target_manifest_identity={"release_identity": "homeassistant-2026.10.5"},
        target_image_ref="local/n3w-homeassistant:2026.10.5-01234567",
        target_archive_sha256="a" * 64, target_archive_size=1234,
    ))

    def interrupted_write(_document):
        raise OSError("synthetic replacement interruption")

    with monkeypatch.context() as patch:
        patch.setattr(store, "write", interrupted_write)
        with store.lock(), pytest.raises(OSError, match="synthetic replacement interruption"):
            store.prepare_new(replacement=replacement)
    assert status()["phase"] == "COMMITTED" and status()["installed_version"] == "2026.10.4"
    with store.lock():
        store.prepare_new(replacement=replacement)
    assert status()["phase"] == "PREPARE_REQUESTED" and status()["installed_version"] == "2026.10.4"
    assert len(list(store.history.glob("*.json"))) == 1
    assert store.was_authorization_consumed(committed["authorization_id_sha256"])


def test_r2_media_binding_rejects_wrong_label(tmp_path):
    media = SyntheticUsb(tmp_path / "synthetic-usb")
    tx = request_prepare(transaction())
    media.root.mkdir(mode=0o700)
    forged = FormatAuthorization(
        public_fingerprint=FINGERPRINT,
        confirmation_verified=True,
        filesystem="ext4",
        label="WRONG-LABEL",
    )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_format_authorization_invalid",
    ):
        record_media_bound(
            tx,
            format_authorization=forged,
            filesystem_uuid=USB_UUID,
            measured_usable_bytes=USB_BYTES,
            capacity_report=media.report,
        )


def test_r2_power_loss_classification_is_deterministic_u0_through_u11(tmp_path):
    media = SyntheticUsb(tmp_path / "synthetic-usb")
    docker = SyntheticDockerHost()
    ha = SyntheticHaData(tmp_path / "synthetic-config")

    snapshots = {}
    tx = transaction()
    snapshots[U0] = tx

    tx = request_prepare(tx)
    snapshots[U1] = tx

    tx = record_media_bound(
        tx,
        format_authorization=media.format(),
        filesystem_uuid=USB_UUID,
        measured_usable_bytes=USB_BYTES,
        capacity_report=media.report,
    )
    snapshots[U2] = tx

    tx = start_target_preparation(tx)
    snapshots[U3] = tx

    target = media.target_record()
    tx = record_target_ready(tx, target=target)
    snapshots[U4] = tx

    tx = request_install(tx)
    snapshots[U5] = tx

    tx = start_predecessor_recovery(tx)
    snapshots[U6] = tx

    predecessor = docker.verify_predecessor(
        media,
        docker.export_predecessor(media),
    )
    ha.quiesce()
    tx = record_predecessor_recovery_and_ha_quiesced(
        tx,
        predecessor=predecessor,
        ha_quiesced=True,
    )
    snapshots[U7] = tx

    backup = ha.verify_backup(media, ha.create_backup(media))
    tx = record_recovery_admission(
        tx,
        target=target,
        predecessor=predecessor,
        backup=backup,
        observed_usb_filesystem_uuid=USB_UUID,
        capacity_report=media.report,
        production_prestate_exact=(docker.active == CURRENT),
    )
    snapshots[U8] = tx

    tx = claim_live_authorization(tx, AUTHORIZATION_ID)
    snapshots[U9] = tx

    docker.remove_predecessor(predecessor)
    tx = record_predecessor_capacity_released(tx)
    snapshots[U10] = tx

    docker.load_target(target)
    ha.start_target()
    tx = record_target_started(tx)
    snapshots[U11] = tx

    assert set(snapshots) == {
        U0, U1, U2, U3, U4, U5, U6, U7, U8, U9, U10, U11
    }

    for phase in (U0, U1, U2, U3, U4, U5, U6, U7, U8):
        assert classify_power_loss_reentry(
            snapshots[phase],
            usb_present=False,
            observed_usb_filesystem_uuid=None,
        ) == "PRE_U9_PREDECESSOR_AUTHORITY"

    for phase in (U9, U10, U11):
        assert classify_power_loss_reentry(
            snapshots[phase],
            usb_present=False,
            observed_usb_filesystem_uuid=None,
        ) == "RECOVERY_MEDIA_REQUIRED"
        assert classify_power_loss_reentry(
            snapshots[phase],
            usb_present=True,
            observed_usb_filesystem_uuid=USB_UUID,
        ) == "ROLLBACK_REQUIRED"


def test_r2_media_binding_rejects_capacity_drift(tmp_path):
    media = SyntheticUsb(tmp_path / "synthetic-usb")
    tx = request_prepare(transaction())
    authorization = media.format()
    with pytest.raises(UpdaterV2Error, match="ha_usb_measured_capacity_drift"):
        record_media_bound(
            tx,
            format_authorization=authorization,
            filesystem_uuid=USB_UUID,
            measured_usable_bytes=USB_BYTES + 1,
            capacity_report=media.report,
        )


def test_r2_orchestrator_remains_command_free():
    source = inspect.getsource(ha_usb_mod)
    assert "subprocess" not in source
    assert "mkfs" not in source
    assert "parted" not in source
    assert "sgdisk" not in source
    assert "docker system prune" not in source
    assert "docker image prune" not in source
    assert "systemctl" not in source
