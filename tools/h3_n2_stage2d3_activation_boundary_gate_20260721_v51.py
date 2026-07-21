#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = Path("/tmp/stage2d3-activation-boundary-v51.txt")

REQUIRED_PATHS = {
    ".github/workflows/h3-n2-stage2d3-activation-transaction-ci.yml",
    "docs/development/h3-n2-stage2d3-activation-transaction-20260721.md",
    "firmware/esphome_rc/board_lab/h3_profile_activation/greenhouse_profile_activation_board_lab_20260721_v51.yml",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_activation_coordinator.cpp",
    "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_activation_coordinator.h",
    "firmware/esphome_rc/components/greenhouse_pairing_client/tests/pairing_stage2d3_activation_transaction_fault_matrix_20260721_v51.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_activation_lab/__init__.py",
    "firmware/esphome_rc/components/greenhouse_profile_activation_lab/greenhouse_profile_activation_lab.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_activation_lab/greenhouse_profile_activation_lab.h",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_activation_board_lab_20260721_v51.yml",
    "protocols/pairing/gh-h3-node-profile-activation-transaction-v1.md",
    "tools/h3_n2_stage2d3_activation_boundary_gate_20260721_v51.py",
}

SOURCE_PATHS = {
    path
    for path in REQUIRED_PATHS
    if path.endswith((".cpp", ".h", ".py", ".yml"))
    and not path.startswith(".github/")
    and not path.startswith("tools/")
}

PROTECTED_PATHS = {
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/core.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/control.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/buses.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/sensors.yml",
    "firmware/esphome_rc/f1_0_rc2/packages/display.yml",
}

FORBIDDEN_SOURCE_TOKENS = (
    "PairingPersistentStore",
    "commit_prepared(",
    "esp_mqtt_client",
    "mqtt_client.h",
    "nvs_open",
    "nvs_set_",
    "nvs_commit",
    "set_username",
    "set_password",
    "set_broker",
    "restart_mqtt",
)

FORBIDDEN_YAML_TOKENS = (
    "on_boot:",
    "button:",
    "switch:",
    "on_press:",
    "script:",
)

REQUIRED_COORDINATOR_TOKENS = (
    "confirm_candidate_round_trip",
    "commit_verified_candidate",
    "OLD_ACTIVE_PRESERVED",
    "INDETERMINATE_REBOOT_REQUIRED",
    "quiesce_all",
    "REBOOT_REQUIRED",
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
    raise SystemExit("Stage 2D-3 activation boundary failed; see diagnostic")


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

    for relative in sorted(SOURCE_PATHS):
        text = (ROOT / relative).read_text(encoding="utf-8")
        leaked = [token for token in FORBIDDEN_SOURCE_TOKENS if token in text]
        if leaked:
            errors.append(f"{relative}: forbidden production integration tokens {leaked}")

    yaml_paths = [
        path for path in REQUIRED_PATHS if path.endswith((".yml", ".yaml"))
    ]
    for relative in sorted(yaml_paths):
        text = (ROOT / relative).read_text(encoding="utf-8")
        exposed = [token for token in FORBIDDEN_YAML_TOKENS if token in text]
        if exposed:
            errors.append(f"{relative}: startup or user trigger exposed {exposed}")

    minimal_yaml = (
        ROOT
        / "firmware/esphome_rc/board_lab/h3_profile_activation/greenhouse_profile_activation_board_lab_20260721_v51.yml"
    ).read_text(encoding="utf-8")
    if "enable_on_boot: false" not in minimal_yaml:
        errors.append("minimal target must keep Wi-Fi disabled at boot")

    coordinator = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_profile_activation_coordinator.cpp"
    ).read_text(encoding="utf-8")
    absent = [token for token in REQUIRED_COORDINATOR_TOKENS if token not in coordinator]
    if absent:
        errors.append(f"activation coordinator evidence missing: {absent}")
    confirm_position = coordinator.find("confirm_candidate_round_trip")
    commit_position = coordinator.find("commit_verified_candidate")
    if confirm_position < 0 or commit_position < 0 or confirm_position >= commit_position:
        errors.append("persistence commit must occur after candidate round-trip confirmation")

    lab_source = (
        ROOT
        / "firmware/esphome_rc/components/greenhouse_profile_activation_lab/greenhouse_profile_activation_lab.cpp"
    ).read_text(encoding="utf-8")
    if ".arm(" in lab_source or ".execute(" in lab_source:
        errors.append("compile-only lab must not arm or execute activation")

    if errors:
        fail(errors)

    DIAGNOSTIC.unlink(missing_ok=True)
    print("Stage 2D-3 activation source and production boundaries passed")


if __name__ == "__main__":
    main()
