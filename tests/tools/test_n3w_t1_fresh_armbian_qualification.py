from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load("n3w_t1_production_v2_contract", "n3w_t1_production_v2_contract.py")
qualification = load("n3w_t1_fresh_armbian_qualification_test", "n3w_t1_fresh_armbian_qualification.py")


def release_document():
    return {
        "schema": contract.RELEASE_SCHEMA,
        "release_id": "a" * 64,
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
            for index, name in enumerate(sorted(contract.REQUIRED_RELEASE_ARTIFACTS), start=1)
        },
        "capacity": {"minimum_post_peak_free_bytes": 5 * 1024**3},
        "public_evidence_fields": ["status", "release_id", "source_head"],
    }


def observation():
    return {
        "schema": qualification.OBSERVATION_SCHEMA,
        "os_release": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
        },
        "armbian_release": {
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
        },
        "kernel_architecture": "aarch64",
        "package_architecture": "arm64",
        "ssh": {"active": "active"},
        "networkmanager": {"active": "active"},
        "armbian_firstrun": {
            "load_state": "loaded",
            "active": "inactive",
            "unit_file_state": "disabled",
            "result": "success",
            "exec_main_status": "0",
        },
        "default_route_present": True,
        "dns_resolution_present": True,
        "ntp_synchronized": "yes",
        "root_free_bytes": 8 * 1024**3,
        "apt_source": {
            "text_present": True,
            "hosts": ["ports.ubuntu.com"],
            "suites": ["resolute"],
            "components": ["universe"],
            "unreadable_count": 0,
        },
        "docker_package_installed": False,
        "compose_package_installed": False,
        "docker_command_present": False,
        "engine_paths": {path: False for path in qualification.ENGINE_PATHS},
        "product_paths": {path: False for path in qualification.PRODUCT_PATHS},
        "product_units_present": [],
        "product_listeners_present": [],
        "fresh_staging_count": 0,
        "sudo_noninteractive": True,
        "unavailable": [],
        "read_only": True,
        "mutation_performed": False,
        "production_service_start": False,
        "board_access": False,
    }


def test_exact_standard_fresh_armbian_passes():
    result = qualification.evaluate(observation(), release_document(), ssh_trust=True)
    assert result["status"] == "PASS"
    assert result["reflash_required"] is False
    assert set(result["checks"]) == set(qualification.CHECK_IDS)
    assert set(result["checks"].values()) == {"PASS"}


def test_wrong_os_is_observed_nonstandard_and_requires_reflash():
    observed = observation()
    observed["os_release"]["VERSION_ID"] = "24.04"
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "FAIL_REFLASH_REQUIRED"
    assert result["reflash_required"] is True
    assert result["checks"]["HOST.OS_ARCH"] == "FAIL"


def test_docker_residue_is_observed_nonstandard_and_requires_reflash():
    observed = observation()
    observed["engine_paths"]["/var/lib/docker"] = True
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "FAIL_REFLASH_REQUIRED"
    assert result["checks"]["HOST.DOCKER_ABSENT"] == "FAIL"


def test_product_residue_is_observed_nonstandard_and_requires_reflash():
    observed = observation()
    observed["product_paths"]["/etc/n3wfc4"] = True
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "FAIL_REFLASH_REQUIRED"
    assert result["checks"]["HOST.PRODUCT_ABSENT"] == "FAIL"


def test_probe_unavailable_stops_without_reflash_disposition():
    observed = observation()
    observed["unavailable"] = ["ntp"]
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "STOP_UNAVAILABLE"
    assert result["reflash_required"] is False
    assert set(result["checks"].values()) == {"UNAVAILABLE"}


def test_ssh_trust_unproven_stops_without_reflash_disposition():
    result = qualification.evaluate(observation(), release_document(), ssh_trust=False)
    assert result["status"] == "STOP_UNAVAILABLE"
    assert result["reflash_required"] is False
    assert set(result["checks"].values()) == {"UNAVAILABLE"}




def test_network_readiness_gap_stops_without_reflash_disposition():
    observed = observation()
    observed["dns_resolution_present"] = False
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "STOP_UNAVAILABLE"
    assert result["reflash_required"] is False


def test_legacy_authorization_residue_requires_reflash():
    observed = observation()
    observed["product_paths"]["/var/lib/n3w-fresh-bootstrap-authorizations"] = True
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "FAIL_REFLASH_REQUIRED"
    assert result["checks"]["HOST.PRODUCT_ABSENT"] == "FAIL"


def test_production_authority_root_without_marker_is_residue():
    observed = observation()
    observed["product_paths"]["/var/lib/n3w-production"] = True
    observed["product_paths"]["/var/lib/n3w-production/run.json"] = False
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "FAIL_REFLASH_REQUIRED"
    assert result["checks"]["HOST.PRODUCT_ABSENT"] == "FAIL"


def test_product_unit_or_listener_residue_requires_reflash():
    observed = observation()
    observed["product_units_present"] = ["n3wfc4-services-activation.service"]
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "FAIL_REFLASH_REQUIRED"
    assert result["checks"]["HOST.PRODUCT_ABSENT"] == "FAIL"

    observed = observation()
    observed["product_listeners_present"] = [8883]
    result = qualification.evaluate(observed, release_document(), ssh_trust=True)
    assert result["status"] == "FAIL_REFLASH_REQUIRED"
    assert result["checks"]["HOST.PRODUCT_ABSENT"] == "FAIL"


def test_fresh_residue_contract_covers_historical_authority_and_provisioning_roots():
    expected = {
        "/var/lib/n3w-fresh-bootstrap-authorizations",
        "/var/lib/n3w-t1-provisioning",
        "/var/tmp/n3w-t1-provisioning-candidate",
        "/var/lib/n3w-production",
    }
    assert expected.issubset(set(qualification.PRODUCT_PATHS))
    assert set(qualification.PRODUCT_UNITS) == {
        "n3wfc4-broker-ingress-guard.service",
        "n3wfc4-provision-resume.service",
        "n3wfc4-broker-activation.service",
        "n3wfc4-services-activation.service",
        "n3wfc4-broker-certificate-lifecycle.service",
        "n3wfc4-broker-certificate-lifecycle.timer",
    }
    assert 8883 in qualification.PRODUCT_TARGET_PORTS


def test_remote_probe_contract_contains_no_mutation_commands():
    lowered = qualification.REMOTE_PROBE_SCRIPT.casefold()
    for forbidden in (
        "apt-get install",
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "systemctl enable",
        "docker rm",
        "docker rmi",
        "chmod ",
        "chown ",
        "unlink(",
        "write_text(",
        "write_bytes(",
    ):
        assert forbidden not in lowered
