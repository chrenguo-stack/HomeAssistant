from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

import n3w_t1_core_updater_ha_u11 as u11
from n3w_t1_core_updater_v2_common import UpdaterV2Error


TARGET = "local/n3w-homeassistant:2026.10.4-5881590f"
PREDECESSOR = "local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET_SHA = "e" * 64
TARGET_RUNTIME_ID = "sha256:" + "a" * 64


@dataclass
class FakeTarget:
    archive_sha256: str = TARGET_SHA

    def public(self):
        return {
            "kind": "target",
            "image_ref": TARGET,
            "archive_sha256": TARGET_SHA,
            "archive_size_bytes": 835309535,
            "portable_identity_sha256": "b" * 64,
            "platform": "linux/arm64",
            "verified": True,
            "fsynced": True,
        }


@dataclass
class FakeMedia:
    mount_path: str


class FakeStore:
    def __init__(self, document, events, *, fail_write=False):
        self.document = dict(document)
        self.events = events
        self.fail_write = fail_write

    def read(self):
        self.events.append("read_tx")
        return dict(self.document)

    def write(self, document):
        self.events.append("write_host_u11")
        if self.fail_write:
            raise RuntimeError("host-write-failure")
        self.document = dict(document)


class FakeBackend:
    def __init__(self, media, target, events, *, fail_sync=False):
        self.media = media
        self.target = target
        self.events = events
        self.fail_sync = fail_sync

    def resolve_transaction_media(self, transaction, *, write_required):
        self.events.append(("resolve_media", write_required))
        return self.media

    def verify_prepared_target(self, *, transaction, media):
        self.events.append("verify_usb_target")
        return self.target

    def sync_transaction_metadata(self, transaction, media):
        self.events.append("write_usb_u11")
        if self.fail_sync:
            raise RuntimeError("usb-write-failure")


class FakeRuntime:
    def __init__(
        self,
        events,
        *,
        preexisting=False,
        binding=PREDECESSOR,
        fail_at=None,
        evidence=None,
    ):
        self.events = events
        self.preexisting = preexisting
        self.binding = binding
        self.fail_at = fail_at
        self.evidence = evidence or u11.U11RuntimeEvidence(
            owner_active=True,
            manager_running=True,
            broker_running=True,
            homeassistant_running=True,
            target_image_ref=TARGET,
            target_runtime_image_id=TARGET_RUNTIME_ID,
            production_config_mounted=True,
        )

    def target_image_id(self, image_ref):
        self.events.append("target_image_prestate")
        return TARGET_RUNTIME_ID if self.preexisting else None

    def homeassistant_binding(self):
        self.events.append("binding_read")
        return self.binding

    def load_target_archive(self, archive):
        self.events.append("load_target")
        if self.fail_at == "load":
            raise RuntimeError("load-failure")

    def verify_loaded_target(
        self,
        *,
        image_ref,
        archive,
        expected_archive_sha256,
    ):
        self.events.append("verify_loaded_target")
        if self.fail_at == "verify":
            raise RuntimeError("verify-failure")
        return TARGET_RUNTIME_ID

    def publish_homeassistant_target_binding(
        self,
        *,
        expected_predecessor,
        target,
    ):
        self.events.append("publish_binding")
        if self.fail_at == "binding":
            raise RuntimeError("binding-failure")
        assert self.binding == expected_predecessor
        self.binding = target

    def start_target_owner(
        self,
        *,
        target_image_ref,
        target_runtime_image_id,
    ):
        self.events.append("start_owner")
        if self.fail_at == "start":
            raise RuntimeError("start-failure")
        return self.evidence


def transaction():
    target = FakeTarget()
    return {
        "phase": u11.U10,
        "status": "ACTIVE",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "target_image_ref": TARGET,
        "current_image_ref": PREDECESSOR,
        "target_archive_sha256": TARGET_SHA,
        "target_artifact_identity": target.public(),
    }


def patch_state_machine(monkeypatch):
    monkeypatch.setattr(
        u11,
        "validate_transaction_document",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        u11,
        "validate_image_recovery_record",
        lambda value, **_kwargs: value,
    )

    def advance(value):
        result = dict(value)
        result["phase"] = "U11_TARGET_INSTALLED_STARTED"
        return result

    monkeypatch.setattr(u11, "record_target_started", advance)


def make_controller(
    tmp_path,
    monkeypatch,
    *,
    runtime=None,
    backend=None,
    store=None,
):
    patch_state_machine(monkeypatch)
    events = []
    target = FakeTarget()
    mount = tmp_path / "usb"
    archive = mount / u11.TARGET_ARCHIVE_RELATIVE
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"exact-target")
    media = FakeMedia(str(mount))
    store = store or FakeStore(transaction(), events)
    backend = backend or FakeBackend(media, target, events)
    runtime = runtime or FakeRuntime(events)
    return (
        u11.HaUsbU11TargetInstallController(
            transaction_store=store,
            backend=backend,
            runtime_owner=runtime,
        ),
        events,
        store,
        backend,
        runtime,
    )


def test_u11_success_orders_load_bind_start_usb_then_host(tmp_path, monkeypatch):
    controller, events, store, _backend, runtime = make_controller(
        tmp_path,
        monkeypatch,
    )

    result = controller.install()

    assert result.transaction["phase"] == "U11_TARGET_INSTALLED_STARTED"
    assert result.target_runtime_image_id == TARGET_RUNTIME_ID
    assert result.runtime.production_config_mounted is True
    assert runtime.binding == TARGET
    assert store.document["phase"] == "U11_TARGET_INSTALLED_STARTED"

    assert events.index("load_target") < events.index("verify_loaded_target")
    assert events.index("verify_loaded_target") < events.index("publish_binding")
    assert events.index("publish_binding") < events.index("start_owner")
    assert events.index("start_owner") < events.index("write_usb_u11")
    assert events.index("write_usb_u11") < events.index("write_host_u11")


def test_u11_rejects_target_preexisting_before_mutation(tmp_path, monkeypatch):
    patch_state_machine(monkeypatch)
    events = []
    target = FakeTarget()
    mount = tmp_path / "usb"
    archive = mount / u11.TARGET_ARCHIVE_RELATIVE
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"x")
    runtime = FakeRuntime(events, preexisting=True)
    controller = u11.HaUsbU11TargetInstallController(
        transaction_store=FakeStore(transaction(), events),
        backend=FakeBackend(FakeMedia(str(mount)), target, events),
        runtime_owner=runtime,
    )

    with pytest.raises(UpdaterV2Error, match="ha_usb_u11_target_preexisting"):
        controller.install()

    assert "load_target" not in events
    assert "publish_binding" not in events
    assert "start_owner" not in events


def test_u11_rejects_binding_drift_before_mutation(tmp_path, monkeypatch):
    patch_state_machine(monkeypatch)
    events = []
    target = FakeTarget()
    mount = tmp_path / "usb"
    archive = mount / u11.TARGET_ARCHIVE_RELATIVE
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"x")
    runtime = FakeRuntime(events, binding=TARGET)
    controller = u11.HaUsbU11TargetInstallController(
        transaction_store=FakeStore(transaction(), events),
        backend=FakeBackend(FakeMedia(str(mount)), target, events),
        runtime_owner=runtime,
    )

    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_u11_binding_prestate_drift",
    ):
        controller.install()

    assert "load_target" not in events


@pytest.mark.parametrize(
    ("fail_at", "expected_stage"),
    (
        ("load", "target_load"),
        ("verify", "target_load"),
        ("binding", "binding_publish"),
        ("start", "target_owner_start"),
    ),
)
def test_u11_runtime_failure_after_mutation_requires_recovery(
    tmp_path,
    monkeypatch,
    fail_at,
    expected_stage,
):
    patch_state_machine(monkeypatch)
    events = []
    target = FakeTarget()
    mount = tmp_path / "usb"
    archive = mount / u11.TARGET_ARCHIVE_RELATIVE
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"x")
    controller = u11.HaUsbU11TargetInstallController(
        transaction_store=FakeStore(transaction(), events),
        backend=FakeBackend(FakeMedia(str(mount)), target, events),
        runtime_owner=FakeRuntime(events, fail_at=fail_at),
    )

    with pytest.raises(u11.U11PartialMutationError) as captured:
        controller.install()

    assert captured.value.stage == expected_stage
    assert "write_host_u11" not in events


def test_u11_usb_persist_failure_never_writes_host_u11(tmp_path, monkeypatch):
    patch_state_machine(monkeypatch)
    events = []
    target = FakeTarget()
    mount = tmp_path / "usb"
    archive = mount / u11.TARGET_ARCHIVE_RELATIVE
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"x")
    backend = FakeBackend(
        FakeMedia(str(mount)),
        target,
        events,
        fail_sync=True,
    )
    controller = u11.HaUsbU11TargetInstallController(
        transaction_store=FakeStore(transaction(), events),
        backend=backend,
        runtime_owner=FakeRuntime(events),
    )

    with pytest.raises(u11.U11PartialMutationError) as captured:
        controller.install()

    assert captured.value.stage == "usb_u11_persist"
    assert "write_usb_u11" in events
    assert "write_host_u11" not in events


def test_u11_host_persist_failure_is_reconciliation_boundary(
    tmp_path,
    monkeypatch,
):
    patch_state_machine(monkeypatch)
    events = []
    target = FakeTarget()
    mount = tmp_path / "usb"
    archive = mount / u11.TARGET_ARCHIVE_RELATIVE
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"x")
    controller = u11.HaUsbU11TargetInstallController(
        transaction_store=FakeStore(
            transaction(),
            events,
            fail_write=True,
        ),
        backend=FakeBackend(FakeMedia(str(mount)), target, events),
        runtime_owner=FakeRuntime(events),
    )

    with pytest.raises(u11.U11PartialMutationError) as captured:
        controller.install()

    assert captured.value.stage == "host_u11_persist"
    assert events.index("write_usb_u11") < events.index("write_host_u11")


def test_u11_runtime_evidence_requires_production_config_mount():
    evidence = u11.U11RuntimeEvidence(
        owner_active=True,
        manager_running=True,
        broker_running=True,
        homeassistant_running=True,
        target_image_ref=TARGET,
        target_runtime_image_id=TARGET_RUNTIME_ID,
        production_config_mounted=False,
    )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_u11_runtime_not_started",
    ):
        evidence.validate(
            expected_target_image_ref=TARGET,
            expected_target_runtime_image_id=TARGET_RUNTIME_ID,
        )


def test_u11_rejects_wrong_phase_and_unconsumed_authorization(
    tmp_path,
    monkeypatch,
):
    patch_state_machine(monkeypatch)
    events = []
    target = FakeTarget()
    mount = tmp_path / "usb"
    archive = mount / u11.TARGET_ARCHIVE_RELATIVE
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"x")

    wrong_phase = transaction()
    wrong_phase["phase"] = "U9_LIVE_AUTHORIZATION_CLAIMED"
    controller = u11.HaUsbU11TargetInstallController(
        transaction_store=FakeStore(wrong_phase, events),
        backend=FakeBackend(FakeMedia(str(mount)), target, events),
        runtime_owner=FakeRuntime(events),
    )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_u11_install_phase_invalid",
    ):
        controller.install()

    unconsumed = transaction()
    unconsumed["authorization_consumed"] = False
    controller = u11.HaUsbU11TargetInstallController(
        transaction_store=FakeStore(unconsumed, events),
        backend=FakeBackend(FakeMedia(str(mount)), target, events),
        runtime_owner=FakeRuntime(events),
    )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_u11_authorization_state_invalid",
    ):
        controller.install()


def test_u11_source_does_not_advance_u12():
    source = Path(u11.__file__).read_text(encoding="utf-8")
    assert "record_target_accepted" not in source
    assert "record_commit" not in source
    assert "U12" not in source
