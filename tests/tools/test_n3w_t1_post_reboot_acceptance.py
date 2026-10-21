from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load(
    "n3w_t1_production_v2_contract_post_acceptance",
    "n3w_t1_production_v2_contract.py",
)
acceptance = load(
    "n3w_t1_post_reboot_acceptance_test",
    "n3w_t1_post_reboot_acceptance.py",
)


def release_document():
    material = {
        "schema": contract.RELEASE_SCHEMA,
        "source_head": "b" * 40,
        "source_tree": "c" * 40,
        "os_contract": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
            "kernel_arch": "aarch64",
        },
        "packages": {
            "docker.io": "29.1.3-0ubuntu4.1",
            "docker-compose-v2": "2.40.3+ds1-0ubuntu1",
        },
        "apt_source_policy": {
            "host": "ports.ubuntu.com",
            "suite": "resolute",
            "component": "universe",
            "architecture": "arm64",
        },
        "artifacts": {
            name: {"sha256": str(index % 10) * 64, "size_bytes": index}
            for index, name in enumerate(
                sorted(contract.REQUIRED_RELEASE_ARTIFACTS),
                start=1,
            )
        },
        "capacity": {"minimum_post_peak_free_bytes": 5 * 1024**3},
        "public_evidence_fields": ["status", "release_id", "source_head"],
    }
    return {"release_id": contract.canonical_sha256(material), **material}


def binding():
    release = release_document()
    return {
        "run_id": "1" * 64,
        "release_id": release["release_id"],
        "release_sha256": contract.canonical_sha256(release),
        "source_head": release["source_head"],
        "target_binding_sha256": "5" * 64,
        "ssh_host_key_sha256": "6" * 64,
        "plan_sha256": "7" * 64,
    }


def started_marker():
    return {
        "schema": contract.RUN_MARKER_SCHEMA,
        **binding(),
        "state": "STARTED",
        "replay_allowed": False,
        "created_at": "2026-10-20T00:00:00Z",
    }


def snapshot():
    return {
        "schema": acceptance.SNAPSHOT_SCHEMA, "status": "PASS",
        "boot_id_sha256": "9" * 64, "source_head": "b" * 40,
        "control_manifest_sha256": "a" * 64,
        "homeassistant_http_ready": True, "systemd_state_sha256": "a" * 64,
        "critical_errors_sha256": "b" * 64,
        "containers": {name: {"identity_sha256": "c" * 64, "restart_count": 0, "running": True}
                       for name in acceptance.CRITICAL_SERVICES},
        "runtime_service_auth": {name: {
            "authenticated": True, "endpoint_port": port,
            "identity_sha256": "d" * 64, "owned_socket_sha256": "e" * 64,
            "broker_events_sha256": "f" * 64,
        } for name, port in (("manager", 8883), ("homeassistant", 1883))},
    }


class Adapter:
    def __init__(self, fail_probe=None, restart_service=None):
        self.fail_probe = fail_probe
        self.restart_service = restart_service
        self.probes = []
        self.observation_seconds = None

    def read_started_marker(self):
        return started_marker()

    def target_local_reboot_verify(self):
        return {
            "status": "PASS",
            "state": "REBOOT_ACCEPTED",
            "reboot_acceptance_passed": True,
            "pre_boot_id_sha256": "8" * 64,
            "post_boot_id_sha256": "9" * 64,
        }

    def external_probe(self, name):
        self.probes.append(name)
        return {
            "status": "FAIL" if name == self.fail_probe else "PASS",
            "accepted": name != self.fail_probe,
            "connack_reason": 0x87,
        }

    def runtime_snapshot(self):
        return snapshot()

    def observe_runtime(self, seconds, baseline):
        self.observation_seconds = seconds
        samples = [{"elapsed_seconds": elapsed, "snapshot": snapshot()}
                   for elapsed in range(0, seconds + 1, 2)]
        if self.restart_service:
            samples[5]["snapshot"]["containers"][self.restart_service]["restart_count"] = 1
        return {"status": "PASS", "observation_seconds": seconds, "samples": samples}


def test_acceptance_requires_all_external_probes_and_exact_90_second_observation():
    adapter = Adapter()
    result = acceptance.run_acceptance(
        adapter,
        release_document(),
        binding(),
    )
    assert result["status"] == "PASS"
    assert result["target_local_reboot_verify"] is True
    assert result["observation_seconds"] == 90
    assert result["no_critical_restart"] is True
    assert result["secret_values_included"] is False
    assert adapter.probes == list(acceptance.REQUIRED_EXTERNAL_PROBES)
    assert adapter.observation_seconds == 90
    assert len(result["acceptance_sha256"]) == 64


def test_acceptance_rejects_any_external_probe_failure_before_observation():
    adapter = Adapter(fail_probe="TLS_HOSTNAME_SNI")
    with pytest.raises(
        acceptance.PostRebootAcceptanceError,
        match="external_probe:TLS_HOSTNAME_SNI_not_pass",
    ):
        acceptance.run_acceptance(adapter, release_document(), binding())
    assert adapter.observation_seconds is None


def test_acceptance_rejects_started_marker_binding_drift():
    adapter = Adapter()
    original = adapter.read_started_marker

    def changed():
        value = original()
        value["target_binding_sha256"] = "0" * 64
        return value

    adapter.read_started_marker = changed
    with pytest.raises(
        acceptance.PostRebootAcceptanceError,
        match="marker_binding_mismatch:target_binding_sha256",
    ):
        acceptance.run_acceptance(adapter, release_document(), binding())


def test_acceptance_requires_real_boot_change():
    adapter = Adapter()

    def unchanged():
        return {
            "status": "PASS",
            "state": "REBOOT_ACCEPTED",
            "reboot_acceptance_passed": True,
            "pre_boot_id_sha256": "8" * 64,
            "post_boot_id_sha256": "8" * 64,
        }

    adapter.target_local_reboot_verify = unchanged
    with pytest.raises(
        acceptance.PostRebootAcceptanceError,
        match="real_boot_change_not_proven",
    ):
        acceptance.run_acceptance(adapter, release_document(), binding())


def test_acceptance_rejects_critical_restart_during_observation():
    adapter = Adapter(restart_service="manager")
    with pytest.raises(
        acceptance.PostRebootAcceptanceError,
        match="runtime_continuity_changed",
    ):
        acceptance.run_acceptance(adapter, release_document(), binding())


def test_acceptance_public_document_has_no_raw_credential_fields():
    result = acceptance.run_acceptance(
        Adapter(),
        release_document(),
        binding(),
    )
    lowered = str(result).casefold()
    for token in ("password", "private_key", "credential_value", "raw_target"):
        assert token not in lowered


@pytest.mark.parametrize("change", [
    lambda s: s["runtime_service_auth"]["manager"].update(owned_socket_sha256="0" * 64),
    lambda s: s["runtime_service_auth"]["homeassistant"].update(broker_events_sha256="0" * 64),
    lambda s: s["containers"]["broker"].update(identity_sha256="0" * 64),
    lambda s: s.update(homeassistant_http_ready=False),
    lambda s: s.update(critical_errors_sha256="0" * 64),
    lambda s: s.update(systemd_state_sha256="0" * 64),
    lambda s: s.update(boot_id_sha256="0" * 64),
])
def test_transient_failure_cannot_be_hidden_by_final_recovery(change):
    adapter = Adapter()
    original = adapter.observe_runtime
    def observe(seconds, baseline):
        result = original(seconds, baseline)
        change(result["samples"][4]["snapshot"])
        return result
    adapter.observe_runtime = observe
    with pytest.raises(acceptance.PostRebootAcceptanceError):
        acceptance.run_acceptance(adapter, release_document(), binding())


@pytest.mark.parametrize("elapsed", [float("nan"), float("inf"), -1, True, 99, 0])
def test_invalid_sample_timing_is_rejected(elapsed):
    adapter = Adapter()
    original = adapter.observe_runtime
    def observe(seconds, baseline):
        result = original(seconds, baseline)
        result["samples"][1]["elapsed_seconds"] = elapsed
        return result
    adapter.observe_runtime = observe
    with pytest.raises(acceptance.PostRebootAcceptanceError, match="coverage"):
        acceptance.run_acceptance(adapter, release_document(), binding())


def test_probe_induced_reconnection_is_rejected_before_observation():
    adapter = Adapter()
    adapter.runtime_snapshot = lambda: snapshot() if not adapter.probes else {
        **snapshot(), "critical_errors_sha256": "0" * 64,
    }
    with pytest.raises(acceptance.PostRebootAcceptanceError, match="continuity_changed"):
        acceptance.run_acceptance(adapter, release_document(), binding())
    assert adapter.observation_seconds is None


def test_new_evidence_hash_binds_run_and_runtime_auth_without_legacy_labels():
    result = acceptance.run_acceptance(Adapter(), release_document(), binding())
    assert result["schema"].endswith("/2")
    assert set(result["runtime_service_auth"]) == {"manager", "homeassistant"}
    assert "MANAGER_MQTT_AUTH" not in result["external_probes"]
    assert result["run_id"] == binding()["run_id"]
    document = deepcopy(result)
    digest = document.pop("acceptance_sha256")
    assert contract.canonical_sha256(document) == digest
    document["runtime_baseline_sha256"] = "0" * 64
    assert contract.canonical_sha256(document) != digest
