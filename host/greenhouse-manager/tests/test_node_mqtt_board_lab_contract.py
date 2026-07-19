from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "host/greenhouse-manager/src/greenhouse_manager/node_mqtt_board_lab.py"
SUPPORT_MODULES = tuple(
    ROOT / f"host/greenhouse-manager/src/greenhouse_manager/{name}"
    for name in (
        "node_mqtt_board_lab_common.py",
        "node_mqtt_board_lab_broker.py",
        "node_mqtt_board_lab_mqtt.py",
        "node_mqtt_board_lab_matrix.py",
    )
)
SCHEMA = (
    ROOT
    / "host/greenhouse-manager/src/greenhouse_manager/schemas"
    / "node_mqtt_board_lab_observation_v1.json"
)
TESTS = ROOT / "host/greenhouse-manager/tests/test_node_mqtt_board_lab.py"
COMPONENT = ROOT / "firmware/esphome_rc/components/greenhouse_mqtt_auth"
COMPONENT_HEADER = COMPONENT / "greenhouse_mqtt_auth.h"
COMPONENT_CPP = COMPONENT / "greenhouse_mqtt_auth.cpp"
BOARD_DIR = ROOT / "firmware/esphome_rc/board_lab/m2_node_auth"
BOARD_YAML = BOARD_DIR / "greenhouse_mqtt_auth_board_lab.yml"
RC2_DIR = ROOT / "firmware/esphome_rc/f1_0_rc2"
BASE_PRODUCT_YAML = RC2_DIR / "f1_0_rc2.yml"
PRODUCT_BOARD_YAML = RC2_DIR / "f1_0_rc2_m2_node_auth_board_lab.yml"
PRODUCT_CONTROL_YAML = RC2_DIR / "packages/control_m2_board_lab.yml"
PRODUCT_SENSORS_YAML = RC2_DIR / "packages/sensors.yml"
EXAMPLE_SECRETS = BOARD_DIR / "secrets.example.yaml"
RUNBOOK = BOARD_DIR / "README.md"
WORKFLOW = ROOT / ".github/workflows/m2-node-auth-board-lab-ci.yml"
CONTRACT = ROOT / "protocols/pairing/gh-node-mqtt-board-lab-v1.md"


def test_board_lab_files_are_present() -> None:
    for path in (
        MODULE,
        *SUPPORT_MODULES,
        SCHEMA,
        TESTS,
        COMPONENT_HEADER,
        COMPONENT_CPP,
        BOARD_YAML,
        BASE_PRODUCT_YAML,
        PRODUCT_BOARD_YAML,
        PRODUCT_CONTROL_YAML,
        PRODUCT_SENSORS_YAML,
        EXAMPLE_SECRETS,
        RUNBOOK,
        WORKFLOW,
        CONTRACT,
    ):
        assert path.is_file(), path


def test_board_target_is_fixed_nonproduction_and_uses_secret_indirection() -> None:
    config = BOARD_YAML.read_text(encoding="utf-8")

    assert "candidate_username: ghn_lab-board" in config
    assert "candidate_client_id: lab-board" in config
    assert "anonymous_client_id: lab-board-anon" in config
    assert "candidate_password: !secret board_lab_candidate_password" in config
    assert "broker: !secret board_lab_broker_host" in config
    assert "board_lab_candidate_password:" not in config
    assert "gh-n1-a9f2f8" not in config
    assert "192" + ".168." not in config
    assert "homeassistant/" not in config
    assert "$CONTROL/" not in config
    assert '"secret_values_included\\":false' in config
    assert "set_test_reboot_hold(true)" in config
    assert "release_held_reboot_for_test()" in config
    assert "reboot_held_for_test()" in config
    assert "candidate_lease_timeout: 10min" in config
    assert "candidate_lease_remaining_ms" in config
    assert "candidate_boot_started" in config
    assert "number: GPIO9" not in config
    assert "board_lab_offline_rollback_button" not in config


def test_product_board_target_preserves_full_rc2_local_stack() -> None:
    config = PRODUCT_BOARD_YAML.read_text(encoding="utf-8")

    for package in (
        "packages/core.yml",
        "packages/control_m2_board_lab.yml",
        "packages/buses.yml",
        "packages/sensors.yml",
        "packages/display.yml",
    ):
        assert package in config
    for token in (
        "soil_read_interval: 20s",
        "scd30_update_interval: 11s",
        "candidate_username: ghn_lab-board",
        "candidate_client_id: lab-board",
        "anonymous_client_id: lab-board-anon",
        "candidate_password: !secret board_lab_candidate_password",
        "broker: !secret board_lab_broker_host",
        "candidate_lease_timeout: 10min",
        "candidate_lease_remaining_ms",
        "candidate_boot_started",
        "soil_warmed_up",
        "soil_query_count",
        "soil_success_count",
        "air_data_present",
        "co2_data_present",
        "light_data_present",
        "soil_data_present",
        '"secret_values_included\\":false',
    ):
        assert token in config
    assert "status_led:" not in config
    assert "number: GPIO9" not in config
    assert "board_lab_offline_rollback_button" not in config
    assert "homeassistant/" not in config
    assert "$CONTROL/" not in config
    assert "192" + ".168." not in config


def test_product_board_soil_runtime_uses_one_warmup_then_20_second_reads() -> None:
    control = PRODUCT_CONTROL_YAML.read_text(encoding="utf-8")

    assert "warm up only after boot/recovery" in control
    assert "sensor remains powered" in control
    assert "interval: ${soil_read_interval}" in control
    assert "delay: ${soil_warmup_time}" in control
    assert "id(soil_warmed_up) = true" in control
    assert "id(soil_warmed_up) = false" in control
    assert "switch.turn_off: sensor_pwr_switch" in control


def test_scd30_cadence_is_substitutable_without_changing_base_default() -> None:
    base = BASE_PRODUCT_YAML.read_text(encoding="utf-8")
    sensors = PRODUCT_SENSORS_YAML.read_text(encoding="utf-8")

    assert "scd30_update_interval: 30s" in base
    assert "update_interval: ${scd30_update_interval}" in sensors


def test_example_secrets_are_placeholders_only() -> None:
    example = EXAMPLE_SECRETS.read_text(encoding="utf-8")

    assert "REPLACE_IN_PRIVATE_WORKSPACE" in example
    assert "REPLACE_WITH_GENERATED_NONPRODUCTION_SECRET" in example
    assert 'board_lab_broker_host: "192.0.2.10"' in example
    assert "192" + ".168." not in example
    assert "gh-n1-a9f2f8" not in example


def test_tooling_keeps_production_gates_closed() -> None:
    source = MODULE.read_text(encoding="utf-8")

    for token in (
        '"production_endpoint_used": False',
        '"production_identity_used": False',
        '"production_execution_invoked": False',
        '"current_services_modified": False',
        '"homeassistant_storage_read": False',
        '"node_credentials_delivered": False',
        '"anonymous_closure_enabled": False',
        '"ready_for_live_apply": False',
        '"ready_for_anonymous_closure": False',
        '"ready_for_node_credential_generation": False',
    ):
        assert token in source
    assert "M2-NONPRODUCTION-BOARD-LAB" in source
    assert "mosquitto_passwd" in source
    assert '"-U"' in source
    assert "address.is_global" in source
    assert "secure_erase_claimed" in source


def test_reboot_hold_is_ram_only_and_outside_persisted_state() -> None:
    header = COMPONENT_HEADER.read_text(encoding="utf-8")
    source = COMPONENT_CPP.read_text(encoding="utf-8")
    persisted = header.split("struct PersistedState", 1)[1].split("};", 1)[0]

    assert "test_reboot_hold" not in persisted
    assert "reboot_held_for_test" not in persisted
    assert "set_test_reboot_hold" in header
    assert "release_held_reboot_for_test" in header
    assert "Board-lab reboot hold is active" in source
    assert "Board-lab reboot hold released" in source
    assert "this->save_state_()" in source
    assert "this->schedule_safe_reboot_()" in source


def test_matrix_covers_handoff_fault_groups() -> None:
    source = MODULE.read_text(encoding="utf-8")

    for case_id in (
        "boot.first_flash_anonymous",
        "candidate.valid_connect_and_heartbeat",
        "invalid.threshold_selects_anonymous",
        "network.broker_restore_candidate",
        "power.reboot_hold_hook",
        "power.candidate_staged_before_reboot",
        "power.ready_uncommitted",
        "rollback.candidate_lease_expired",
        "rollback.after_commit",
        "logs.serial",
        "local.lcd_continuity",
        "local.sensors_continuity",
        "local.rs485_continuity",
    ):
        assert case_id in source


def test_runbook_defers_physical_actions_to_operator() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    normalized = " ".join(runbook.split())

    for statement in (
        "production T1",
        "production monitoring",
        "first USB flash",
        "power cuts",
        "Wi-Fi interruption",
        "LCD/sensor/RS485 observations are operator actions",
        "only target permitted for the 50-case product-board runtime matrix",
        "does not claim secure erasure",
    ):
        assert statement in normalized


def test_mqtt_smoke_waits_for_suback_and_uses_public_errors() -> None:
    mqtt_source = SUPPORT_MODULES[2].read_text(encoding="utf-8")
    command_source = MODULE.read_text(encoding="utf-8")

    assert "observer.on_subscribe = observer_subscribe" in mqtt_source
    assert "subscribe_deadline" in mqtt_source
    assert "observation_deadline" in mqtt_source
    assert "mqtt.MQTTException" not in mqtt_source
    assert "mqtt.MQTTException" not in command_source
    assert "ValueError" in command_source
    assert "RuntimeError" in command_source


def test_workflow_runs_unit_broker_compile_and_secret_checks() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "test_node_mqtt_board_lab.py" in workflow
    assert "test_node_mqtt_board_lab_contract.py" in workflow
    assert "smoke-valid" in workflow
    assert "smoke-invalid" in workflow
    assert "invalidate-candidate" in workflow
    assert "restore-candidate" in workflow
    assert "esphome==2026.4.3" in workflow
    assert "greenhouse_mqtt_auth_board_lab.yml" in workflow
    assert "f1_0_rc2_m2_node_auth_board_lab.yml" in workflow
    assert "Compile minimal ESP32-C6 auth target" in workflow
    assert "Compile full RC2 product board target" in workflow
    assert "ephemeral board-lab secret appeared" in workflow
    assert "private production marker appeared" in workflow
    assert "if: always()" in workflow


def test_contract_states_evidence_and_non_authorization_boundaries() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    for statement in (
        "Production node migration: prohibited",
        "Anonymous closure: prohibited",
        "Home Assistant `.storage` access: prohibited",
        "generic_candidate_connection_failure",
        "Commit is never automatic",
        "does not claim secure erasure",
        "does not authorize production credential",
    ):
        assert statement in contract
