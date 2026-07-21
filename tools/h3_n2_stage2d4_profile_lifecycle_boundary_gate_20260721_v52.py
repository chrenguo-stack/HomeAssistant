#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = Path("/tmp/stage2d4-profile-lifecycle-boundary-v52.txt")

REQUIRED_PATHS = {
    ".github/workflows/h3-n2-stage2d4-profile-lifecycle-integration-ci.yml",
    "docs/development/h3-n2-stage2d4-profile-lifecycle-integration-20260721.md",
    "firmware/esphome_rc/board_lab/h3_profile_lifecycle/greenhouse_profile_lifecycle_board_lab_20260721_v52.yml",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_lifecycle_integration.cpp",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_lifecycle_integration.h",
    "firmware/esphome_rc/components/greenhouse_pairing_client/tests/pairing_stage2d4_profile_lifecycle_integration_fault_matrix_20260721_v52.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_lab/__init__.py",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_lab/greenhouse_profile_lifecycle_lab.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_lab/greenhouse_profile_lifecycle_lab.h",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_lifecycle_board_lab_20260721_v52.yml",
    "protocols/pairing/gh-h3-node-profile-lifecycle-integration-v1.md",
    "tools/h3_n2_stage2d4_profile_lifecycle_boundary_gate_20260721_v52.py",
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
}

YAML_PATHS = {
    path for path in REQUIRED_PATHS if path.endswith((".yml", ".yaml"))
}

FORBIDDEN_YAML_KEYS = {
    "on_boot:",
    "button:",
    "switch:",
    "on_press:",
    "script:",
    "mqtt:",
}

FORBIDDEN_LAB_TOKENS = (
    ".configure(",
    ".recover_prepared(",
    ".begin_validation(",
    ".poll_validation(",
    ".activate(",
    "EspIdfNvsPersistenceBackend",
    "EfuseHmacPersistenceKeyProvider",
    "EspIdfCandidateMqttTransport",
    "esp_mqtt_client_",
    "nvs_open",
    "nvs_set_",
    "nvs_commit",
    "set_username",
    "set_password",
    "restart_mqtt",
)

REQUIRED_INTEGRATION_TOKENS = (
    "NO_ACTIVE_PREPARED",
    "ACTIVE_WITH_PREPARED",
    "candidate_probe_client_destroyed",
    "old_authority_preserved_",
    "OLD_ACTIVE_PRESERVED",
    "INDETERMINATE_REBOOT_REQUIRED",
    "persistence_adapter_.refresh()",
    "activation_.execute",
    "candidate_credentials_.clear()",
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def changed_paths() -> set[str]:
    base = git("merge-base", "HEAD", "origin/main")
    output = git("diff", "--name-only", f"{base}...HEAD")
    return {line for line in output.splitlines() if line}


def fail(errors: list[str]) -> None:
    DIAGNOSTIC.write_text("\n".join(errors) + "\n", encoding="utf-8")
    raise SystemExit("Stage 2D-4 lifecycle boundary failed; see diagnostic")


def yaml_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        keys.add(stripped.split("#", 1)[0].rstrip())
    return keys


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
        errors.append(f"protected reviewed paths changed: {protected}")

    for relative in sorted(YAML_PATHS):
        text = (ROOT / relative).read_text(encoding="utf-8")
        keys = yaml_keys(text)
        exposed = sorted(FORBIDDEN_YAML_KEYS & keys)
        if exposed:
            errors.append(f"{relative}: startup or runtime trigger exposed {exposed}")

    minimal = (
        ROOT
        / "firmware/esphome_rc/board_lab/h3_profile_lifecycle/greenhouse_profile_lifecycle_board_lab_20260721_v52.yml"
    ).read_text(encoding="utf-8")
    if "enable_on_boot: false" not in minimal:
        errors.append("minimal target must keep Wi-Fi disabled at boot")

    lab_paths = (
        "firmware/esphome_rc/components/greenhouse_profile_lifecycle_lab/greenhouse_profile_lifecycle_lab.cpp",
        "firmware/esphome_rc/components/greenhouse_profile_lifecycle_lab/greenhouse_profile_lifecycle_lab.h",
        "firmware/esphome_rc/components/greenhouse_profile_lifecycle_lab/__init__.py",
    )
    for relative in lab_paths:
        text = (ROOT / relative).read_text(encoding="utf-8")
        leaked = [token for token in FORBIDDEN_LAB_TOKENS if token in text]
        if leaked:
            errors.append(f"{relative}: forbidden concrete integration tokens {leaked}")

    integration_path = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_lifecycle_integration.cpp"
    )
    integration = integration_path.read_text(encoding="utf-8")
    absent = [token for token in REQUIRED_INTEGRATION_TOKENS if token not in integration]
    if absent:
        errors.append(f"lifecycle integration evidence missing: {absent}")

    preflight_position = integration.find("persistence_adapter_.refresh()")
    execute_position = integration.find("activation_.execute")
    if preflight_position < 0 or execute_position < 0 or preflight_position >= execute_position:
        errors.append("persistent preflight must occur before activation execution")

    local_clear_position = integration.find("candidate_credentials_.clear()")
    validator_stage_position = integration.find("validator_.stage")
    if local_clear_position < 0 or validator_stage_position < 0:
        errors.append("candidate transfer and local-clear evidence missing")

    combined_yaml = "\n".join(
        (ROOT / path).read_text(encoding="utf-8") for path in sorted(YAML_PATHS)
    )
    forbidden_literals = (
        "BEGIN CERTIFICATE",
        "broker.local",
        "mqtt_password:",
        "mqtt_username:",
        "mqtt_client_id:",
        "credential_generation:",
        "partition_name:",
        "namespace_name:",
        "efuse_key",
    )
    leaked_literals = [token for token in forbidden_literals if token in combined_yaml]
    if leaked_literals:
        errors.append(f"compile YAML contains credential or environment literals: {leaked_literals}")

    if errors:
        fail(errors)

    DIAGNOSTIC.unlink(missing_ok=True)
    print("Stage 2D-4 profile lifecycle source and production boundaries passed")


if __name__ == "__main__":
    main()
