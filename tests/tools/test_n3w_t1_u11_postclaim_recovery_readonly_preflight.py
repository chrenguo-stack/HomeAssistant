from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u11_postclaim_recovery_readonly_preflight"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("u11_r41_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_r41_manifest_authorizes_readonly_only_and_forbids_r40_replay():
    value = manifest()
    assert value["read_only_preflight"] is True
    assert value["real_t1_readonly_execution_authorized"] is True
    assert value["live_recovery_authorized"] is False
    assert value["r40_replay_permitted"] is False
    assert value["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = value["execution_contract"]
    assert contract["real_t1_readonly_preflight_authorized"] is True
    assert contract["live_recovery_authorized"] is False
    assert contract["r40_replay"] is False
    for key in (
        "transaction_mutation",
        "usb_mutation",
        "target_image_load",
        "compose_binding_mutation",
        "service_mutation",
        "u11_transition",
        "u12_plus",
        "u13_plus",
        "board_access",
        "merge",
    ):
        assert contract[key] is False


def test_r41_binds_exact_partial_u10_and_r40_consumed_failure():
    value = manifest()
    assert value["expected_u10_entry"]["transaction_sha256"] == (
        "c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3"
    )
    assert value["expected_target_runtime_image_id"] == (
        "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
    )
    assert value["r40"] == {
        "gate_id": (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U11_TARGET_INSTALL_R40_20261116_01"
        ),
        "authorization_id": (
            "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U11_R40_20261116_01"
        ),
        "execution_id": "u11-r40-live02-20261116T063426Z",
        "result": "STOP_POSTCLAIM",
        "rc": 2,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
    }
    partial = value["expected_partial_u10_state"]
    assert partial["host_transaction_phase"] == (
        "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
    )
    assert partial["usb_phase"] == "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
    assert partial["target_image_present"] is True
    assert partial["target_binding_published"] is True
    assert partial["services_owner_state"] == "failed"


def test_r41_binds_repaired_source_authority_and_exact_blobs():
    value = manifest()
    assert value["source_repair_authority"] == (
        "155f9a7b62d6b758fb87c109b3ffbf54aa5614c7"
    )
    assert value["source_authority"]["source_repair_ci"] == "16_OF_16_SUCCESS"
    bound = value["package_source_authority"]
    assert bound["tools/n3w_t1_core_updater_host.py"] == (
        "fe859feef9f8321aa65289c688ee3d2a8d2d4a3b"
    )
    assert bound["tools/n3w_t1_core_updater_ha_u11_host.py"] == (
        "40b05778811091404ea8eef59b8ff51c635be25c"
    )
    assert bound[
        "tools/execution_packages/n3w/r7a/"
        "u11_postclaim_recovery_readonly_preflight/executor.py"
    ] == "edb5a1517a1320fb9b7ff5abe771ce23b55c53a7"
    assert value["exact_source_delivery"] == (
        "TEMPORARY_IN_MEMORY_REPAIRED_SUPERVISION_SOURCE_"
        "NO_LIVE_SOURCE_MUTATION"
    )


def test_r41_remote_payload_compiles_and_contains_no_recovery_mutation():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<r41-remote>", "exec")
    source = executor.REMOTE_SCRIPT
    forbidden = (
        '["docker", "rm"',
        '["docker", "image", "rm"',
        '["docker", "load"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        '["systemctl", "reset-failed"',
        "mkfs",
        "wipefs",
        "sgdisk",
        "parted",
        "record_target_started(",
        "rewrite_component_image(",
        "activate_component(",
        "start_services(",
        "controller.install(",
        "durable_json_once(",
        "durable_json_replace(",
    )
    for token in forbidden:
        assert token not in source


def test_r41_checks_consumed_r40_before_successor_eligibility():
    source = load_executor().REMOTE_SCRIPT
    run = source[source.index("def run_successor_readonly(plan):") :]
    r40 = run.index("verify_r40_consumed_failure(plan)")
    runtime = run.index("verify_partial_u10_runtime(plan, transaction)")
    supervision = run.index("verify_repaired_supervision_contract(plan)")
    eligible = run.index('"successor_live_recovery_eligible": True')
    assert r40 < runtime < supervision < eligible
    assert 'failure.get("status") != "STOP_POSTCLAIM"' in source
    assert 'failure.get("service_mutation") is not False' in source
    assert 'failure.get("transaction_mutation") is not False' in source
    assert 'failure.get("usb_mutation") is not False' in source
    assert 'failure.get("u11_transition") is not False' in source


def test_r41_proves_exact_loaded_target_and_published_binding():
    source = load_executor().REMOTE_SCRIPT
    assert (
        'target_doc[0].get("Id") != plan["expected_target_runtime_image_id"]'
        in source
    )
    assert 'binding != plan["target_image"]' in source
    assert "parse_image_archive(" in source
    assert (
        'target_record.get("portable_identity_sha256") != portable_sha256'
        in source
    )
    assert 'verdict.status != "VERIFIED"' in source
    assert (
        'verdict.runtime_image_id != plan["expected_target_runtime_image_id"]'
        in source
    )


def test_r41_uses_repaired_effective_supervision_in_memory_only():
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def verify_repaired_supervision_contract(plan):")
    end = source.index("def verify_postload_internal_reserve(plan):")
    function = source[start:end]
    assert "types.ModuleType" in function
    assert "sys.modules" in function
    assert "host._activation_env()" in function
    assert "host._service_unit(" in function
    assert "EXPECTED_U11_EXECSTART" in function
    assert "EXPECTED_U11_EXECSTOP" in function
    assert "write_text(" not in function
    assert "write_bytes(" not in function
    assert "systemctl" not in function


def test_r41_postload_capacity_requires_only_reserved_headroom():
    value = manifest()
    assert value["internal_capacity_policy"]["derived_post_peak_reserve_bytes"] == (
        1610612736
    )
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def verify_postload_internal_reserve(plan):")
    end = source.index("def run_successor_readonly(plan):")
    function = source[start:end]
    assert 'required = plan["derived_post_peak_reserve_bytes"]' in function
    assert "target_import_worst_case_allowance_bytes" not in function
    assert '"capacity_mode": "POST_TARGET_LOAD_RESERVE_ONLY"' in function


def test_r41_local_entry_has_no_execute_switch_or_live_recovery_claim():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'parser.add_argument("--execute"' not in source
    assert "--authorization-id" not in source
    assert "--confirm" not in source
    assert "r41_real_t1_readonly_execution_not_authorized" in source
    assert '"successor_live_recovery_authorized": False' in source
    assert '"r40_replay": False' in source
    assert '"service_mutation": False' in source
    assert '"u12_plus": False' in source
    assert '"u13_plus": False' in source


def test_r41_repaired_supervision_probe_executes_exact_in_memory_sources(
    monkeypatch,
    tmp_path,
):
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    start = source.index("def verify_repaired_supervision_contract(plan):")
    end = source.index("def verify_postload_internal_reserve(plan):")
    function = source[start:end]

    import n3w_t1_core_updater_common as common
    from n3w_t1_core_updater_ha_u11_host import (
        EXPECTED_U11_EXECSTART,
        EXPECTED_U11_EXECSTOP,
    )

    broker_env = tmp_path / "broker.env"
    compose = tmp_path / "docker-compose.yml"
    compose_env = tmp_path / "compose.env"
    broker_env.write_text(
        "\n".join(
            (
                f"N3WFC4_COMPOSE_FILE={compose}",
                f"N3WFC4_COMPOSE_ENV_FILE={compose_env}",
                f"N3WFC4_COMPOSE_PROJECT_NAME={common.PROJECT}",
                "",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "BROKER_ENV", broker_env)
    monkeypatch.setattr(common, "COMPOSE", compose)
    monkeypatch.setattr(common, "COMPOSE_ENV", compose_env)

    systemd_cat = "\n".join(
        (
            "ExecStart=/usr/bin/docker compose legacy-start",
            "ExecStop=/usr/bin/docker compose legacy-stop",
            "ExecStart=",
            EXPECTED_U11_EXECSTART,
            "ExecStop=",
            EXPECTED_U11_EXECSTOP,
            "",
        )
    )

    def fake_run(argv, **kwargs):
        assert tuple(argv) == ("systemctl", "cat", common.SERVICES_UNIT)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=systemd_cat.encode(),
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    host_raw = (ROOT / "tools" / "n3w_t1_core_updater_host.py").read_bytes()
    u11_host_raw = (
        ROOT / "tools" / "n3w_t1_core_updater_ha_u11_host.py"
    ).read_bytes()
    plan = {
        "repaired_host_source_b64": base64.b64encode(host_raw).decode("ascii"),
        "repaired_u11_host_source_b64": base64.b64encode(u11_host_raw).decode(
            "ascii"
        ),
        "repaired_host_source_sha256": hashlib.sha256(host_raw).hexdigest(),
        "repaired_u11_host_source_sha256": hashlib.sha256(
            u11_host_raw
        ).hexdigest(),
        "source_repair_authority": (
            "155f9a7b62d6b758fb87c109b3ffbf54aa5614c7"
        ),
    }
    namespace = {
        "base64": base64,
        "hashlib": hashlib,
        "sys": sys,
        "Stop": executor.Stop,
    }
    exec(compile(function, "<r41-supervision-probe>", "exec"), namespace)
    result = namespace["verify_repaired_supervision_contract"](plan)

    assert result["effective_contract"] == "EXACT_HA_OTA_OVERLAY"
    assert result["repair_source_authority"] == plan["source_repair_authority"]
    assert result["execstart_sha256"] == common.sha256_text(
        EXPECTED_U11_EXECSTART
    )
    assert result["execstop_sha256"] == common.sha256_text(
        EXPECTED_U11_EXECSTOP
    )


def test_r41_remote_transport_streams_large_program_over_stdin(monkeypatch):
    executor = load_executor()
    observed = {}

    class FakeTransport:
        target = "root@192.0.2.1"

        def _child_options(self):
            return (
                "-F",
                "/dev/null",
                "-o",
                "ControlPath=/tmp/n3w-r41-test-ctl",
            )

    def fake_run(argv, **kwargs):
        observed["argv"] = tuple(argv)
        observed["input"] = kwargs.get("input")
        observed["text"] = kwargs.get("text")
        observed["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                '{"status":"U11_R41_POST_R40_READONLY_PREFLIGHT_PASS"}\\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(executor.subprocess, "run", fake_run)
    plan = {
        "gate_id": executor.GATE_ID,
        "repaired_host_source_b64": "A" * 200000,
        "repaired_u11_host_source_b64": "B" * 200000,
    }
    completed, result = executor.remote_mode(
        FakeTransport(),
        plan,
        timeout=77,
    )

    assert completed.returncode == 0
    assert result["status"] == "U11_R41_POST_R40_READONLY_PREFLIGHT_PASS"
    assert observed["argv"][-1] == "python3 -B -"
    assert "-n" not in observed["argv"]
    assert executor.REMOTE_SCRIPT not in observed["argv"]
    assert "A" * 1000 not in " ".join(observed["argv"])
    assert len(" ".join(observed["argv"])) < 4096
    assert observed["text"] is True
    assert observed["timeout"] == 77
    assert observed["input"].startswith(
        "import sys\\nsys.argv = ['r41-remote', 'preflight', "
    )
    assert executor.REMOTE_SCRIPT in observed["input"]
    assert len(observed["input"]) > 400000
