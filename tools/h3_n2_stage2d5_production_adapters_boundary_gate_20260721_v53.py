#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = Path("/tmp/stage2d5-production-adapters-boundary-v53.txt")

REQUIRED_PATHS = {
    ".github/workflows/h3-n2-stage2d5-production-adapters-ci.yml",
    "docs/development/h3-n2-stage2d5-production-adapters-20260721.md",
    "firmware/esphome_rc/board_lab/h3_profile_production_adapters/greenhouse_profile_production_adapters_board_lab_20260721_v53.yml",
    "firmware/esphome_rc/components/greenhouse_profile_production_adapters/__init__.py",
    "firmware/esphome_rc/components/greenhouse_profile_production_adapters/profile_production_adapters.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_production_adapters/profile_production_adapters.h",
    "firmware/esphome_rc/components/greenhouse_profile_production_adapters/tests/pairing_stage2d5_production_adapters_fault_matrix_20260721_v53.cpp",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_production_adapters_board_lab_20260721_v53.yml",
    "protocols/pairing/gh-h3-node-production-profile-adapters-v1.md",
    "tools/h3_n2_stage2d5_production_adapters_boundary_gate_20260721_v53.py",
}

PROTECTED_PATHS = {
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/core.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/control.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/buses.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/sensors.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/display.yml",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_persistent_store.cpp",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_candidate_mqtt_validator.cpp",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_activation_coordinator.cpp",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_lifecycle_integration.cpp",
}

YAML_PATHS = {
    path for path in REQUIRED_PATHS if path.endswith((".yml", ".yaml"))
}

FORBIDDEN_YAML_KEYS = {
    "on_boot:",
    "button:",
    "switch:",
    "script:",
    "on_press:",
    "mqtt:",
}

REQUIRED_SOURCE_TOKENS = (
    "ProductionCandidateMqttTransport",
    "ProductionProfileLifecycleRuntime",
    "ProductionPersistenceAdapter",
    "EspIdfProductionMqttSession",
    "EspIdfProductionPersistenceAdapter",
    "esp_mqtt_client_init",
    "MQTT_TRANSPORT_OVER_SSL",
    "broker.verification.certificate",
    "credentials.authentication.password",
    "EfuseHmacPersistenceKeyProvider",
    "allow_read_write_",
    "finalize_activation_promotion",
    "wait_round_trip",
)

REQUIRED_COMPONENT_TOKENS = (
    'include_builtin_idf_component("mqtt")',
    'include_builtin_idf_component("nvs_flash")',
    'include_builtin_idf_component("esp_hw_support")',
    'cg.add_define("USE_GREENHOUSE_PROFILE_PRODUCTION_ADAPTERS")',
)

FORBIDDEN_LITERALS = (
    "broker.greenhouse.local",
    "192.168.",
    "BEGIN CERTIFICATE",
    "ghs_",
    "mqtt_password:",
    "mqtt_username:",
    "mqtt_client_id:",
    "pairing_secret:",
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def changed_paths() -> set[str]:
    base = git("merge-base", "HEAD", "origin/main")
    output = git("diff", "--name-only", f"{base}...HEAD")
    return {line for line in output.splitlines() if line}


def yaml_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        keys.add(stripped.split("#", 1)[0].rstrip())
    return keys


def fail(errors: list[str]) -> None:
    DIAGNOSTIC.write_text("\n".join(errors) + "\n", encoding="utf-8")
    raise SystemExit("Stage 2D-5 production adapter boundary failed; see diagnostic")


def main() -> None:
    errors: list[str] = []
    changed = changed_paths()

    unexpected = sorted(changed - REQUIRED_PATHS)
    missing = sorted(REQUIRED_PATHS - changed)
    protected = sorted(changed & PROTECTED_PATHS)
    if unexpected:
        errors.append(f"unexpected changed paths: {unexpected}")
    if missing:
        errors.append(f"required changed paths missing: {missing}")
    if protected:
        errors.append(f"protected production paths changed: {protected}")

    for relative in sorted(YAML_PATHS):
        text = (ROOT / relative).read_text(encoding="utf-8")
        keys = yaml_keys(text)
        exposed = sorted(FORBIDDEN_YAML_KEYS & keys)
        if exposed:
            errors.append(f"{relative}: runtime or startup trigger exposed {exposed}")
        leaked = [token for token in FORBIDDEN_LITERALS if token in text]
        if leaked:
            errors.append(f"{relative}: environment or credential literal present {leaked}")
        if text.count("greenhouse_profile_production_adapters:") != 1:
            errors.append(f"{relative}: compile-only adapter key must appear exactly once")

    minimal_path = (
        ROOT
        / "firmware/esphome_rc/board_lab/h3_profile_production_adapters/greenhouse_profile_production_adapters_board_lab_20260721_v53.yml"
    )
    minimal = minimal_path.read_text(encoding="utf-8")
    if "enable_on_boot: false" not in minimal:
        errors.append("minimal target must keep Wi-Fi disabled at boot")

    source_paths = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_production_adapters/profile_production_adapters.h",
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_production_adapters/profile_production_adapters.cpp",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    absent = [token for token in REQUIRED_SOURCE_TOKENS if token not in source]
    if absent:
        errors.append(f"production adapter evidence missing: {absent}")
    leaked_source = [token for token in FORBIDDEN_LITERALS if token in source]
    if leaked_source:
        errors.append(f"production adapter source contains fixed environment data: {leaked_source}")

    component = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_production_adapters/__init__.py"
    ).read_text(encoding="utf-8")
    absent_component = [
        token for token in REQUIRED_COMPONENT_TOKENS if token not in component
    ]
    if absent_component:
        errors.append(f"component dependency evidence missing: {absent_component}")
    forbidden_component = (
        "cg.new_Pvariable",
        "register_component",
        "set_broker",
        "set_username",
        "set_password",
    )
    leaked_component = [token for token in forbidden_component if token in component]
    if leaked_component:
        errors.append(f"compile-only component constructs runtime state: {leaked_component}")

    implementation = source_paths[1].read_text(encoding="utf-8")
    configure_position = implementation.find("EspIdfProductionMqttSession::configure")
    start_position = implementation.find("EspIdfProductionMqttSession::start")
    marker_policy_position = implementation.find("allow_read_write_")
    nvs_open_position = implementation.find("EspIdfProductionPersistenceAdapter::open")
    if configure_position < 0 or start_position <= configure_position:
        errors.append("MQTT session must configure before start implementation")
    if marker_policy_position < 0 or nvs_open_position < 0:
        errors.append("explicit NVS write-access policy evidence missing")

    docs = (
        ROOT / "docs/development/h3-n2-stage2d5-production-adapters-20260721.md"
    ).read_text(encoding="utf-8")
    for token in (
        "compile-only",
        "不得连接真实 Broker",
        "不得写入物理 NVS",
        "finalize_activation_promotion",
    ):
        if token not in docs:
            errors.append(f"development boundary documentation missing: {token}")

    if errors:
        fail(errors)

    DIAGNOSTIC.unlink(missing_ok=True)
    print("Stage 2D-5 production adapter source and execution boundaries passed")


if __name__ == "__main__":
    main()
