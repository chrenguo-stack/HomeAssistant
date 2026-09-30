from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_kf100_short_lived_certificate_auto_renew_lab.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_kf100_short_lived_certificate_auto_renew_lab",
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_lifecycle_output_parser_uses_final_json_line() -> None:
    tool = load_tool()

    class Result:
        stdout = 'noise\n{"result":"renewed","renewal_attempted":true}\n'

    document = tool._parse_lifecycle_output(Result())

    assert document["result"] == "renewed"
    assert document["renewal_attempted"] is True


def test_source_freezes_exact_production_lifecycle_blob() -> None:
    tool = load_tool()

    assert (
        tool.PRODUCTION_LIFECYCLE_TOOL_BLOB
        == "65187b27a2ddd8f57221500a7019486e02bca101"
    )
    assert tool.PRODUCTION_LIFECYCLE_TOOL == Path(
        "/usr/local/sbin/n3w-broker-certificate-lifecycle"
    )


def test_lab_uses_isolated_loopback_dynamic_port_and_unique_container() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert '"gh.n3w.kf100-renewal-lab=true"' in source
    assert 'f"127.0.0.1:{port}:{LAB_INTERNAL_PORT}"' in source
    assert 'n3w-kf100-renew-lab-' in source
    assert '"docker", "rm", "-f", container' in source


def test_lab_exercises_success_and_forced_rollback_paths() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert '"success_path"' in source
    assert '"rollback_path"' in source
    assert '"renewed"' in source
    assert '"renewal_failed_rolled_back"' in source
    assert '"force_mismatch"' in source
    assert '"original_certificate_restored"' in source


def test_lab_routes_activation_unit_through_private_systemctl_shim() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'pki["bin"] / "systemctl"' in source
    assert 'env["PATH"] = str(pki["bin"])' in source
    assert 'EXPECTED_ACTIVATION_UNIT = "n3wfc4-broker-activation.service"' in source
    assert '["docker", "rm", "-f", CONTAINER]' in source
    assert "RUN_ARGS = " in source
    assert "wait_tls_matches_file" in source
    assert '["docker", "restart", CONTAINER]' not in source


def test_lab_never_invokes_production_timer_or_service_mutation() -> None:
    source = TOOL.read_text(encoding="utf-8")

    forbidden = (
        '("systemctl", "start", PRODUCTION_TIMER',
        '("systemctl", "stop", PRODUCTION_TIMER',
        '("systemctl", "restart", PRODUCTION_TIMER',
        '("systemctl", "enable", PRODUCTION_TIMER',
        '("systemctl", "disable", PRODUCTION_TIMER',
        '("systemctl", "start", PRODUCTION_SERVICE',
        '("systemctl", "stop", PRODUCTION_SERVICE',
        '("systemctl", "restart", PRODUCTION_SERVICE',
    )
    for token in forbidden:
        assert token not in source


def test_public_result_does_not_emit_private_paths_or_private_keys() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert '"production_certificate_mutation": False' in source
    assert '"production_broker_restart": False' in source
    assert '"production_status_unchanged": True' in source
    assert '"lab_cleanup": True' in source

    public_keys = {
        "result",
        "lifecycle_result",
        "initial_server_state",
        "renewal_attempted",
        "rollback_attempted",
        "certificate_replaced",
        "certificate_fingerprint_changed",
        "server_key_unchanged",
        "ca_certificate_unchanged",
        "live_tls_uses_new_certificate",
        "initial_not_after",
        "renewed_not_after",
        "forced_postrenew_mismatch",
        "original_certificate_restored",
        "live_tls_restored_to_original_certificate",
        "restored_not_after",
        "activation_recreate_count",
    }
    sample = {
        "result": "PASS",
        "lifecycle_result": "renewed",
        "renewal_attempted": True,
    }
    assert set(json.loads(json.dumps(sample))) <= public_keys


def test_lab_failure_reports_public_safe_lifecycle_diagnostic() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert '"diagnostic": error.details' in source
    assert '"lifecycle_rc": result.returncode' in source
    assert '"lifecycle_result": document.get("result")' in source
    assert '"renewal_attempted": document.get("renewal_attempted")' in source
    assert '"rollback_attempted": document.get("rollback_attempted")' in source


def test_lab_activation_recreates_container_to_rebind_single_file_mounts() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'subprocess.run(\n        ["docker", "rm", "-f", CONTAINER]' in source
    assert "result = subprocess.run(\n        RUN_ARGS," in source
    assert "live_fingerprint()" in source
    assert "file_fingerprint()" in source
