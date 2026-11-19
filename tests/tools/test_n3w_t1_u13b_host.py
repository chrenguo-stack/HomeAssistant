from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_common import BROKER_UNIT, SERVICES_UNIT
from n3w_t1_core_updater_ha_backup import HaDataBackupRecord
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
import n3w_t1_core_updater_ha_u13b_host as host_mod
from n3w_t1_core_updater_ha_u13b_host import (
    U13BProductionBackend,
    U13BProductionRuntime,
    U13BProductionReadOnlyObserver,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


CURRENT = "local/n3w-homeassistant:2026.10.0-aaaaaaaa"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"


def image(kind, ref):
    return ImageRecoveryRecord(
        kind=kind,
        image_ref=ref,
        archive_sha256="1" * 64,
        archive_size_bytes=1234,
        portable_identity_sha256="2" * 64,
        platform="linux/arm64",
        verified=True,
        fsynced=True,
    )


class Host:
    def __init__(self):
        self.binding = TARGET
        self.ha_restart_count = 0
        self.ha_runtime_image_id_override = None
        self.broker_owner_active = True
        self.images = {
            TARGET: "sha256:" + "a" * 64,
            CURRENT: "sha256:" + "b" * 64,
        }
        self.residue = [{
            "container_id": "target-container",
            "image_ref": TARGET,
            "image_id": self.images[TARGET],
            "status": "exited",
            "name": "/ha",
            "replace": "",
        }]
        self.owner = "inactive"
        self.started = 0

    def _activation_env(self):
        pass

    def _service_unit(self, **kwargs):
        return {}

    def assert_mutation_safe(self, component):
        assert component == "homeassistant"

    def _runtime(self, service):
        if service == "broker":
            return {
                "container_id": "broker-id",
                "image_ref": "broker-image",
                "image_id": "sha256:" + "c" * 64,
                "restart_count": 0,
            }
        if service == "manager":
            return {
                "container_id": "manager-id",
                "image_ref": "manager-image",
                "image_id": "sha256:" + "d" * 64,
                "restart_count": 0,
            }
        return {
            "container_id": "ha-id",
            "image_ref": CURRENT,
            "image_id": (
                self.ha_runtime_image_id_override
                or self.images[CURRENT]
            ),
            "restart_count": self.ha_restart_count,
        }

    def _systemctl(self, action, unit):
        if action != "is-active":
            return ""
        if unit == BROKER_UNIT:
            return "active" if self.broker_owner_active else "inactive"
        if unit == SERVICES_UNIT:
            return self.owner
        return "unknown"

    def stop_services(self):
        self.owner = "inactive"

    def image_id(self, ref):
        return self.images.get(ref)

    def component_container_residue(self, component):
        return list(self.residue)

    def _run(self, argv, timeout=60, check=True):
        class R:
            returncode = 1 if argv[:2] == ("docker", "inspect") else 0
            stdout = b""
            stderr = b""
        if argv[:2] == ("docker", "rm"):
            self.residue = [
                item for item in self.residue
                if item["container_id"] != argv[2]
            ]
        return R()

    def containers_using_image(self, image_id):
        return tuple(
            item["container_id"]
            for item in self.residue
            if item["image_id"] == image_id
        )

    def remove_image_exact(self, image_id):
        for ref, observed in list(self.images.items()):
            if observed == image_id:
                del self.images[ref]

    def _running_count(self, service):
        if service == "broker":
            return 1
        if self.owner == "active":
            return 1
        return 0

    def load_image(self, archive):
        self.images[CURRENT] = "sha256:" + "b" * 64

    def verify_image_archive(self, ref, archive, sha):
        return self.images[ref]

    def component_binding_v2(self, component):
        return self.binding

    def rewrite_component_image(self, component, expected, replacement):
        assert self.binding == expected
        self.binding = replacement

    def _listener_snapshot(self):
        return {
            "tcp_8883": 1,
            "tcp_47110": 1,
            "udp_47111": 1,
            "tcp_47112": 0,
        }

    def _mqtt_authenticated(self, service):
        return True

    def _homeassistant_http_status(self):
        return 401


def transaction():
    return {
        "current_image_ref": CURRENT,
        "current_image_identity": {
            "runtime_image_id": "sha256:" + "b" * 64,
            "platform": "linux/arm64",
        },
        "target_image_ref": TARGET,
    }


def runtime(host):
    value = U13BProductionRuntime(
        expected_manager_container_id="manager-id",
        expected_manager_image_ref="manager-image",
        expected_manager_runtime_image_id="sha256:" + "d" * 64,
        expected_broker_container_id="broker-id",
        expected_broker_image_ref="broker-image",
        expected_broker_runtime_image_id="sha256:" + "c" * 64,
        host=host,
    )
    value.u11._production_config_mounted = lambda container_id: True
    value.u11.start_target_owner = lambda **kwargs: type(
        "Evidence",
        (),
        {
            "homeassistant_running": True,
            "target_image_ref": CURRENT,
            "production_config_mounted": True,
            "manager_running": True,
            "broker_running": True,
        },
    )()
    return value


def test_u13b_production_runtime_cleanup_is_homeassistant_only():
    host = Host()
    adapter = runtime(host)
    cleanup = adapter.cleanup_failed_target(
        transaction=transaction(),
        target=image("target", TARGET),
    )
    assert cleanup.target_image_absent is True
    assert CURRENT in host.images
    assert TARGET not in host.images
    assert host._runtime("broker")["container_id"] == "broker-id"


def test_u13b_data_restore_requiesces_and_preserves_broker():
    host = Host()
    adapter = runtime(host)
    evidence = adapter.quiesce_for_data_restore(
        transaction=transaction(),
    )
    assert evidence.services_quiesced is True
    assert evidence.broker_preserved is True
    assert host._running_count("broker") == 1


def test_u13b_predecessor_runtime_start_uses_ha_ota_path():
    host = Host()
    adapter = runtime(host)
    evidence = adapter.start_predecessor_runtime(
        transaction=transaction(),
        predecessor=image("predecessor", CURRENT),
    )
    assert evidence.predecessor_runtime_started is True
    assert host.binding == CURRENT


def test_u13b_predecessor_health_rejects_binding_drift():
    host = Host()
    host.owner = "active"
    adapter = runtime(host)
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_homeassistant_binding_drift",
    ):
        adapter.verify_predecessor_health(
            transaction=transaction(),
            predecessor=image("predecessor", CURRENT),
        )


def test_u13b_predecessor_health_rejects_wrong_runtime_image_id():
    host = Host()
    host.owner = "active"
    host.binding = CURRENT
    host.ha_runtime_image_id_override = "sha256:" + "e" * 64
    adapter = runtime(host)
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_predecessor_runtime_identity_drift",
    ):
        adapter.verify_predecessor_health(
            transaction=transaction(),
            predecessor=image("predecessor", CURRENT),
        )


def test_u13b_predecessor_health_rejects_restart_loop_evidence():
    host = Host()
    host.owner = "active"
    host.binding = CURRENT
    host.ha_restart_count = 1
    adapter = runtime(host)
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_predecessor_runtime_identity_drift",
    ):
        adapter.verify_predecessor_health(
            transaction=transaction(),
            predecessor=image("predecessor", CURRENT),
        )


def test_u13b_predecessor_health_requires_broker_owner_active():
    host = Host()
    host.owner = "active"
    host.broker_owner_active = False
    adapter = runtime(host)
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_broker_owner_not_active",
    ):
        adapter.verify_predecessor_health(
            transaction=transaction(),
            predecessor=image("predecessor", CURRENT),
        )


def test_u13b_restore_predecessor_rejects_runtime_identity_drift(tmp_path):
    host = Host()
    host.images[CURRENT] = "sha256:" + "e" * 64
    adapter = runtime(host)
    media = type(
        "Media",
        (),
        {"mount_path": str(tmp_path)},
    )()
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_predecessor_runtime_image_identity_drift",
    ):
        adapter.restore_predecessor_image(
            transaction=transaction(),
            media=media,
            predecessor=image("predecessor", CURRENT),
        )



def test_u13b_production_backend_reads_usb_metadata_without_mutation(tmp_path):
    mount = tmp_path / "usb"
    update_dir = mount / "n3w-update"
    transaction_dir = update_dir / "transaction"
    transaction_dir.mkdir(parents=True, mode=0o700)
    update_dir.chmod(0o700)
    transaction_dir.chmod(0o700)
    documents = {
        "manifest.json": {"schema": "manifest", "value": 1},
        "phase.json": {"schema": "phase", "value": 2},
        "checksums.json": {"schema": "checksums", "value": 3},
        "content-authority.json": {"schema": "authority", "value": 4},
        "host-transaction.json": {"schema": "host", "value": 5},
    }
    for name, document in documents.items():
        path = transaction_dir / name
        path.write_text(json.dumps(document) + "\n", encoding="utf-8")
        path.chmod(0o600)

    before = {name: (transaction_dir / name).read_bytes() for name in documents}
    observed_media = PreparedUsbMedia(
        locator="/dev/sdz",
        public_fingerprint="a" * 64,
        filesystem_uuid="12345678-1234-5678-1234-567812345678",
        measured_usable_bytes=1024,
        mount_path=str(mount),
    ).validate()
    backend = U13BProductionBackend(prepare_backend=object())
    snapshot = backend.read_transaction_metadata(
        {"usb_filesystem_uuid": observed_media.filesystem_uuid},
        observed_media,
    )

    assert snapshot.manifest == documents["manifest.json"]
    assert snapshot.phase == documents["phase.json"]
    assert snapshot.checksums == documents["checksums.json"]
    assert snapshot.content_authority == documents["content-authority.json"]
    assert snapshot.host_transaction == documents["host-transaction.json"]
    assert {name: (transaction_dir / name).read_bytes() for name in documents} == before



def test_u13b_production_backend_rejects_symlinked_update_directory(tmp_path):
    mount = tmp_path / "usb"
    mount.mkdir()
    outside = tmp_path / "outside"
    (outside / "transaction").mkdir(parents=True, mode=0o700)
    (mount / "n3w-update").symlink_to(outside, target_is_directory=True)

    observed_media = PreparedUsbMedia(
        locator="/dev/sdz",
        public_fingerprint="a" * 64,
        filesystem_uuid="12345678-1234-5678-1234-567812345678",
        measured_usable_bytes=1024,
        mount_path=str(mount),
    ).validate()
    backend = U13BProductionBackend(prepare_backend=object())

    with pytest.raises(
        UpdaterV2Error,
        match="u13b_usb_transaction_directory_invalid",
    ):
        backend.read_transaction_metadata(
            {"usb_filesystem_uuid": observed_media.filesystem_uuid},
            observed_media,
        )


def test_readonly_production_target_cleanup_observer_does_not_mutate():
    host = Host()
    host.owner = "inactive"
    host.images.pop(TARGET)
    host.residue.clear()
    adapter = U13BProductionReadOnlyObserver(
        runtime=runtime(host), backend=object(), backup_provider=object()
    )
    before = (dict(host.images), list(host.residue), host.owner, host.binding)
    assert adapter.observe_target_cleanup(
        transaction=transaction(), media=object()
    ) is True
    assert before == (host.images, host.residue, host.owner, host.binding)


def test_readonly_production_target_cleanup_rejects_target_residue():
    host = Host()
    adapter = U13BProductionReadOnlyObserver(
        runtime=runtime(host), backend=object(), backup_provider=object()
    )
    assert adapter.observe_target_cleanup(
        transaction=transaction(), media=object()
    ) is False


def test_readonly_production_image_observer_requires_exact_id_without_load():
    host = Host()
    backend = type("Backend", (), {
        "verify_recovery_predecessor": lambda self, **kwargs:
            image("predecessor", CURRENT)
    })()
    adapter = U13BProductionReadOnlyObserver(
        runtime=runtime(host), backend=backend, backup_provider=object()
    )
    tx = transaction()
    tx["predecessor_recovery_identity"] = image(
        "predecessor", CURRENT
    ).public()
    assert adapter.observe_predecessor_image(
        transaction=tx, media=object()
    ) is True
    assert host.images[CURRENT] == "sha256:" + "b" * 64
    host.images[CURRENT] = "sha256:" + "e" * 64
    assert adapter.observe_predecessor_image(
        transaction=tx, media=object()
    ) is False


def test_readonly_production_data_observer_fails_closed_without_quiescence():
    host = Host()
    host.owner = "active"
    adapter = U13BProductionReadOnlyObserver(
        runtime=runtime(host), backend=object(), backup_provider=object()
    )
    assert adapter.observe_ha_data_restored(
        transaction=transaction(), media=object()
    ) is False


def test_readonly_production_data_observer_validates_exact_backup_without_restore(
    tmp_path,
):
    host = Host()
    record = HaDataBackupRecord(
        archive_sha256="1" * 64,
        archive_size_bytes=1024,
        manifest_sha256="2" * 64,
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

    class Provider:
        def __init__(self):
            self.calls = []

        def verify_restored_preupgrade_backup_readonly(
            self,
            observed,
            *,
            transaction_id_sha256,
            source_root,
        ):
            self.calls.append(
                (observed.public(), transaction_id_sha256, source_root)
            )
            return observed

    provider = Provider()
    adapter = U13BProductionReadOnlyObserver(
        runtime=runtime(host), backend=object(), backup_provider=provider,
    )
    tx = transaction()
    tx.update({
        "ha_data_backup_identity": record.public(),
        "transaction_id_sha256": "a" * 64,
    })
    observed_media = type(
        "Media",
        (),
        {"mount_path": str(tmp_path)},
    )()
    before = (dict(host.images), list(host.residue), host.owner, host.binding)
    assert adapter.observe_ha_data_restored(
        transaction=tx,
        media=observed_media,
    ) is True
    assert provider.calls == [(
        record.public(),
        "a" * 64,
        tmp_path / "n3w-update" / "ha-data",
    )]
    assert before == (host.images, host.residue, host.owner, host.binding)


def test_readonly_production_runtime_observer_does_not_start_services():
    host = Host()
    host.owner = "active"
    host.binding = CURRENT
    adapter = U13BProductionReadOnlyObserver(
        runtime=runtime(host), backend=object(), backup_provider=object()
    )
    tx = transaction()
    tx["predecessor_recovery_identity"] = image(
        "predecessor", CURRENT
    ).public()
    assert adapter.observe_predecessor_runtime(
        transaction=tx, media=object()
    ) is True
    assert host.started == 0
    host.binding = TARGET
    with pytest.raises(
        UpdaterV2Error, match="u13b_homeassistant_binding_drift"
    ):
        adapter.observe_predecessor_runtime(
            transaction=tx, media=object()
        )



class PeerHost:
    def __init__(self, *, running, residue=None, runtime=None):
        self.running = running
        self.residue = residue or []
        self.runtime = runtime or {}

    def _running_count(self, _component):
        return self.running

    def _runtime(self, _component):
        return dict(self.runtime)

    def component_container_residue(self, _component):
        return [dict(item) for item in self.residue]


def test_u9_plus_peer_identity_accepts_unique_stopped_manager_residue():
    host = PeerHost(
        running=0,
        residue=[
            {
                "container_id": "manager-id",
                "image_ref": "local/greenhouse-manager:test",
                "image_id": "sha256:" + "a" * 64,
            }
        ],
    )
    assert host_mod._resolve_u9_plus_peer_identity(
        host,
        "manager",
        allow_stopped=True,
    ) == {
        "container_id": "manager-id",
        "image_ref": "local/greenhouse-manager:test",
        "image_id": "sha256:" + "a" * 64,
    }


def test_u9_plus_peer_identity_rejects_stopped_broker():
    host = PeerHost(running=0)
    with pytest.raises(
        UpdaterV2Error,
        match="u9_plus_broker_runtime_not_running",
    ):
        host_mod._resolve_u9_plus_peer_identity(
            host,
            "broker",
            allow_stopped=False,
        )


def test_u9_plus_peer_identity_rejects_ambiguous_manager_residue():
    host = PeerHost(
        running=0,
        residue=[
            {
                "container_id": "one",
                "image_ref": "local/greenhouse-manager:a",
                "image_id": "sha256:" + "a" * 64,
            },
            {
                "container_id": "two",
                "image_ref": "local/greenhouse-manager:b",
                "image_id": "sha256:" + "b" * 64,
            },
        ],
    )
    with pytest.raises(
        UpdaterV2Error,
        match="u9_plus_manager_residue_ambiguous",
    ):
        host_mod._resolve_u9_plus_peer_identity(
            host,
            "manager",
            allow_stopped=True,
        )


def test_u9_plus_customer_data_plane_requires_new_manager_ingress_and_ha_state(
    tmp_path,
):
    import sqlite3
    from types import SimpleNamespace

    storage = tmp_path / ".storage"
    storage.mkdir()
    (storage / "core.entity_registry").write_text(
        json.dumps(
            {
                "data": {
                    "entities": [
                        {
                            "unique_id": "node-1_air_temperature_c",
                            "entity_id": "sensor.node_1_air_temperature",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    database = tmp_path / "home-assistant_v2.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "CREATE TABLE states_meta "
            "(metadata_id INTEGER PRIMARY KEY, entity_id TEXT)"
        )
        connection.execute(
            "CREATE TABLE states "
            "(metadata_id INTEGER, last_updated_ts REAL)"
        )
        connection.execute(
            "INSERT INTO states_meta(metadata_id, entity_id) "
            "VALUES (1, 'sensor.node_1_air_temperature')"
        )
        connection.execute(
            "INSERT INTO states(metadata_id, last_updated_ts) "
            "VALUES (1, 110.0)"
        )
        connection.commit()
    finally:
        connection.close()

    class LogHost:
        def _run(self, _argv, **_kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    b"Accepted telemetry node=node-1 "
                    b"key=boot:1\n"
                ),
                stderr=b"",
            )

    runtime = SimpleNamespace(
        host=LogHost(),
        u11=SimpleNamespace(
            expected_manager_container_id="manager-id"
        ),
    )
    oracle = host_mod.U9PlusProductionCompletionOracle(
        runtime=runtime,
        backend=object(),
        backup_provider=SimpleNamespace(ha_data_root=tmp_path),
        clock=lambda: 100.0,
        sleeper=lambda _seconds: None,
        telemetry_timeout_s=1.0,
    )
    assert oracle._history_readable() is True
    assert oracle._fresh_greenhouse_telemetry_visible(100) is True


def test_u9_plus_history_oracle_fails_closed_when_recorder_missing(
    tmp_path,
):
    from types import SimpleNamespace
    oracle = host_mod.U9PlusProductionCompletionOracle(
        runtime=object(),
        backend=object(),
        backup_provider=SimpleNamespace(ha_data_root=tmp_path),
    )
    assert oracle._history_readable() is False



def test_u9_plus_history_oracle_uses_durable_u13b3_restore_evidence(
    tmp_path,
):
    from types import SimpleNamespace

    oracle = host_mod.U9PlusProductionCompletionOracle(
        runtime=object(),
        backend=object(),
        backup_provider=SimpleNamespace(ha_data_root=tmp_path),
    )
    terminal = {
        "rollback_recovery_content_verified": True,
        "rollback_ha_data_restored": True,
        "ha_data_backup_identity": {"archive_sha256": "a" * 64},
    }
    assert (
        oracle._durable_preupgrade_restore_proven(terminal)
        is True
    )

    terminal["rollback_ha_data_restored"] = False
    assert (
        oracle._durable_preupgrade_restore_proven(terminal)
        is False
    )
