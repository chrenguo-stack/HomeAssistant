from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_u13b_host import U13BProductionRuntime


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
            "image_id": self.images[CURRENT],
            "restart_count": 0,
        }

    def _systemctl(self, action, unit):
        return self.owner if action == "is-active" else ""

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
        transaction={
            "current_image_ref": CURRENT,
            "target_image_ref": TARGET,
        },
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
        transaction={
            "current_image_ref": CURRENT,
            "target_image_ref": TARGET,
        },
    )
    assert evidence.services_quiesced is True
    assert evidence.broker_preserved is True
    assert host._running_count("broker") == 1


def test_u13b_predecessor_runtime_start_uses_ha_ota_path():
    host = Host()
    adapter = runtime(host)
    evidence = adapter.start_predecessor_runtime(
        transaction={
            "current_image_ref": CURRENT,
            "target_image_ref": TARGET,
        },
        predecessor=image("predecessor", CURRENT),
    )
    assert evidence.predecessor_runtime_started is True
    assert host.binding == CURRENT
