from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
import shutil
import stat
import sys
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_ha_recovery_startup as recovery_startup
import n3w_t1_core_updater_ha_usb as ha_usb_mod
from n3w_t1_core_updater_ha_backup import (
    HaDataBackupRecord,
    validate_backup_record,
)
from n3w_t1_core_updater_ha_ipc import (
    REQUEST_SCHEMA,
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
    HaPredecessorRecovery,
    claim_live_authorization,
    classify_power_loss_reentry,
    record_commit,
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
from n3w_t1_core_updater_v2_common import UpdaterV2Error


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
    )


def transaction():
    return new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={
            "portable_identity_sha256": CURRENT_IDENTITY,
            "platform": "linux/arm64",
        },
        target_manifest_identity={
            "release_identity": "ha-2026.10.4-r2-synthetic",
            "manifest_sha256": "3" * 64,
        },
        target_image_ref=TARGET,
        target_archive_sha256=TARGET_SHA,
        target_archive_size=len(TARGET_BYTES),
        created_at_unix=1_800_100_000,
    )


class InterruptedPower(BaseException):
    pass


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

    def verify_predecessor_health(self, binding):
        assert binding == self.binding
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

    def _activation_env(self):
        pass

    def _service_unit(self):
        pass

    def _run(self, argv, **kwargs):
        unit = recovery_startup.SERVICES_UNIT
        if argv == ("systemctl", "show", "--property=NeedDaemonReload", "--value", unit):
            return SimpleNamespace(stdout=b"no\n")
        if argv == ("systemctl", "cat", unit):
            return SimpleNamespace(stdout=b"test unit")
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

    def _image_binding_authority_v2(self, rendered):
        return {name: item["image"] for name, item in rendered["services"].items()}, {}

    def image_id(self, reference):
        return next(item["runtime_id"] for item in self.saved.values()
                    if item["reference"] == reference)

    def _running_count(self, service):
        return int(service in self.running)

    def _runtime(self, service):
        return {"container_id": service, "image_ref": self.saved[service]["reference"],
                "image_id": self.running_ids[service]}

    def _systemctl(self, action, unit):
        return self.owner

    def stop_services(self):
        self.running.remove("manager")
        self.owner = "failed"
        raise InterruptedPower()


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
        assert recovery_startup.main() == 0
        assert runtime.starts == 1


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

    with (
        pytest.raises(UpdaterV2Error, match=expected),
        HaPredecessorRecovery(store, runtime, runtime).install_recovery_point(fixture, fixture)
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
        assert executor.status()["error_code"] == "ha_usb_install_revalidation_failed"
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
