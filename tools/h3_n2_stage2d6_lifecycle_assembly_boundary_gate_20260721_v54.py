#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = Path("/tmp/stage2d6-lifecycle-assembly-boundary-v54.txt")

REQUIRED_PATHS = {
    ".github/workflows/h3-n2-stage2d6-lifecycle-assembly-ci.yml",
    "docs/development/h3-n2-stage2d6-lifecycle-assembly-20260721.md",
    "firmware/esphome_rc/board_lab/h3_profile_lifecycle_controller/greenhouse_profile_lifecycle_controller_board_lab_20260721_v54.yml",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/__init__.py",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/profile_lifecycle_controller.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/profile_lifecycle_controller.h",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/tests/pairing_stage2d6_lifecycle_assembly_fault_matrix_20260721_v54.cpp",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_lifecycle_controller_board_lab_20260721_v54.yml",
    "protocols/pairing/gh-h3-node-profile-lifecycle-controller-v1.md",
    "tools/h3_n2_stage2d6_lifecycle_assembly_boundary_gate_20260721_v54.py",
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
    "firmware/esphome_rc/components/greenhouse_profile_production_adapters/profile_production_adapters.cpp",
}

COMPILE_YAML_PATHS = {
    "firmware/esphome_rc/board_lab/h3_profile_lifecycle_controller/greenhouse_profile_lifecycle_controller_board_lab_20260721_v54.yml",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_lifecycle_controller_board_lab_20260721_v54.yml",
}

FORBIDDEN_YAML_KEYS = {
    "on_boot:",
    "button:",
    "switch:",
    "script:",
    "on_press:",
    "mqtt:",
}

FORBIDDEN_LITERALS = (
    "broker.greenhouse.local",
    "192.168.",
    "BEGIN CERTIFICATE",
    "ghs_",
    "mqtt_password:",
    "mqtt_username:",
    "mqtt_client_id:",
    "pairing_secret:",
    "nvs_namespace:",
    "hmac_key_id:",
)

REQUIRED_SOURCE_TOKENS = (
    "ProductionProfileLifecycleController",
    "recover_startup",
    "start_recovered_active",
    "begin_prepared_validation",
    "poll_validation",
    "ProfileLifecycleMutationAuthorizer",
    "COMMIT_PREPARED_PROFILE",
    "MUTATION_NOT_AUTHORIZED",
    "finalize_activation_promotion",
    "ACTIVE_WITH_MAINTENANCE_PENDING",
    "NO_ACTIVE_COMMITTED_ORPHAN",
    "quiesce_for_reboot",
    "transaction_busy",
)

REQUIRED_TEST_TOKENS = (
    "test_empty_startup_is_read_only",
    "test_active_start_is_explicit",
    "test_first_enrollment_authorization_gate",
    "test_rotation_validation_failure_preserves_active",
    "test_rotation_activation_failure_rolls_back",
    "test_two_rotations_reuse_promoted_active",
    "test_stale_committed_slot_requires_maintenance_without_cleanup",
    "test_storage_error_quiesces_and_requires_reboot",
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


def function_body(text: str, signature: str, next_signature: str) -> str:
    start = text.find(signature)
    stop = text.find(next_signature, start + len(signature))
    if start < 0 or stop < 0 or stop <= start:
        return ""
    return text[start:stop]


def fail(errors: list[str]) -> None:
    DIAGNOSTIC.write_text("\n".join(errors) + "\n", encoding="utf-8")
    raise SystemExit("Stage 2D-6 lifecycle boundary failed; see diagnostic")


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

    for relative in sorted(COMPILE_YAML_PATHS):
        text = (ROOT / relative).read_text(encoding="utf-8")
        keys = yaml_keys(text)
        exposed = sorted(FORBIDDEN_YAML_KEYS & keys)
        if exposed:
            errors.append(f"{relative}: runtime or startup trigger exposed {exposed}")
        leaked = [token for token in FORBIDDEN_LITERALS if token in text]
        if leaked:
            errors.append(f"{relative}: environment or credential literal present {leaked}")
        if text.count("greenhouse_profile_lifecycle_controller:") != 1:
            errors.append(
                f"{relative}: compile-only controller key must appear exactly once"
            )

    minimal = (
        ROOT
        / "firmware/esphome_rc/board_lab/h3_profile_lifecycle_controller/greenhouse_profile_lifecycle_controller_board_lab_20260721_v54.yml"
    ).read_text(encoding="utf-8")
    if "enable_on_boot: false" not in minimal:
        errors.append("minimal target must keep Wi-Fi disabled at boot")

    header_path = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/profile_lifecycle_controller.h"
    )
    implementation_path = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/profile_lifecycle_controller.cpp"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (header_path, implementation_path)
    )
    absent = [token for token in REQUIRED_SOURCE_TOKENS if token not in source]
    if absent:
        errors.append(f"lifecycle assembly evidence missing: {absent}")
    leaked_source = [token for token in FORBIDDEN_LITERALS if token in source]
    if leaked_source:
        errors.append(f"controller source contains fixed environment data: {leaked_source}")

    implementation = implementation_path.read_text(encoding="utf-8")
    recovery_body = function_body(
        implementation,
        "ProductionProfileLifecycleController::recover_startup",
        "ProductionProfileLifecycleController::start_recovered_active",
    )
    if not recovery_body:
        errors.append("unable to isolate recover_startup implementation")
    else:
        forbidden_recovery_mutations = (
            "prepare(",
            "commit_prepared(",
            "rollback_prepared(",
            "discard_committed_orphan(",
            "bind_active_profile(",
            "begin_prepared_validation(",
            "activate(",
        )
        exposed = [
            token for token in forbidden_recovery_mutations if token in recovery_body
        ]
        if exposed:
            errors.append(f"startup recovery contains mutation or network action: {exposed}")

    activate_position = implementation.find(
        "ProductionProfileLifecycleController::activate"
    )
    authorize_position = implementation.find("authorizer->authorize", activate_position)
    lifecycle_activate_position = implementation.find(
        "this->lifecycle_.activate", activate_position
    )
    promotion_position = implementation.find(
        "finalize_activation_promotion", activate_position
    )
    if (
        activate_position < 0
        or authorize_position <= activate_position
        or lifecycle_activate_position <= authorize_position
        or promotion_position <= lifecycle_activate_position
    ):
        errors.append(
            "activation must authorize before lifecycle commit and promote after commit"
        )

    component = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/__init__.py"
    ).read_text(encoding="utf-8")
    for token in (
        'AUTO_LOAD = ["greenhouse_profile_production_adapters"]',
        'cg.add_define("USE_GREENHOUSE_PROFILE_LIFECYCLE_CONTROLLER")',
    ):
        if token not in component:
            errors.append(f"compile-only component evidence missing: {token}")
    forbidden_component = (
        "cg.new_Pvariable",
        "register_component",
        "automation",
        "set_broker",
        "set_username",
        "set_password",
        "set_namespace",
        "set_hmac_key",
    )
    exposed_component = [
        token for token in forbidden_component if token in component
    ]
    if exposed_component:
        errors.append(
            f"compile-only component constructs runtime state: {exposed_component}"
        )

    test_path = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller/tests/pairing_stage2d6_lifecycle_assembly_fault_matrix_20260721_v54.cpp"
    )
    test_text = test_path.read_text(encoding="utf-8")
    absent_tests = [token for token in REQUIRED_TEST_TOKENS if token not in test_text]
    if absent_tests:
        errors.append(f"host fault matrix coverage missing: {absent_tests}")

    docs = (
        ROOT / "docs/development/h3-n2-stage2d6-lifecycle-assembly-20260721.md"
    ).read_text(encoding="utf-8")
    protocol = (
        ROOT / "protocols/pairing/gh-h3-node-profile-lifecycle-controller-v1.md"
    ).read_text(encoding="utf-8")
    documentation = docs + "\n" + protocol
    for token in (
        "read-only startup recovery",
        "MUTATION_NOT_AUTHORIZED",
        "REBOOT_REQUIRED",
        "compile-only",
        "不得连接真实 Broker",
        "不得打开或写入物理 NVS",
        "不得操作实板",
    ):
        if token not in documentation:
            errors.append(f"development boundary documentation missing: {token}")

    if errors:
        fail(errors)

    DIAGNOSTIC.unlink(missing_ok=True)
    print("Stage 2D-6 lifecycle assembly source and execution boundaries passed")


if __name__ == "__main__":
    main()
