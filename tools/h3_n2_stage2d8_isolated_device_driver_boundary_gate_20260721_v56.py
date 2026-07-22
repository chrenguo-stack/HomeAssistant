#!/usr/bin/env python3
"""Fail-closed source and execution boundary gate for H3/N2 Stage 2D-8."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

BASE_COMMIT = "ab04d31032403869379d976cd9f250fb3f144f7d"
DIAGNOSTIC = Path("/tmp/stage2d8-isolated-device-driver-boundary-v56.txt")

EXPECTED_PATHS = {
    ".github/workflows/h3-n2-stage2d8-isolated-device-driver-ci.yml",
    "docs/development/h3-n2-stage2d8-isolated-device-driver-20260721.md",
    "docs/development/h3-n2-stage2d8-live-authorization-record-20260721.md",
    "firmware/esphome_rc/board_lab/h3_profile_isolated_device_driver/greenhouse_profile_isolated_device_driver_board_lab_20260721_v56.yml",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/__init__.py",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/isolated_device_driver.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/isolated_device_driver.h",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/isolated_device_esp32_ports.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/isolated_device_esp32_ports.h",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/tests/pairing_stage2d8_isolated_device_driver_fault_matrix_20260721_v56.cpp",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_isolated_device_driver_board_lab_20260721_v56.yml",
    "protocols/pairing/gh-h3-node-isolated-device-driver-v1.md",
    "tests/h3_n2_stage2d8_isolated_broker/mosquitto_isolated_test_20260721_v56.conf.template",
    "tests/h3_n2_stage2d8_isolated_broker/mosquitto_isolated_test_acl_20260721_v56.template",
    "tests/h3_n2_stage2d8_isolated_broker/stage2d8_execution_manifest_20260721_v56.json.template",
    "tools/h3_n2_stage2d8_execution_manifest_gate_20260721_v56.py",
    "tools/h3_n2_stage2d8_isolated_device_driver_boundary_gate_20260721_v56.py",
}

PROTECTED_PATHS = (
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml",
    "firmware/esphome_rc/f1_0_rc2/packages",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance",
    "firmware/esphome_rc/board_lab/h3_profile_lifecycle_controller",
    "firmware/esphome_rc/board_lab/h3_profile_isolated_acceptance",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_lifecycle_controller_board_lab_20260721_v54.yml",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_isolated_acceptance_board_lab_20260721_v55.yml",
    ".github/workflows/h3-n2-stage2d6-lifecycle-assembly-ci.yml",
    ".github/workflows/h3-n2-stage2d7-isolated-acceptance-ci.yml",
    "protocols/pairing/gh-h3-node-profile-lifecycle-controller-v1.md",
    "protocols/pairing/gh-h3-node-isolated-acceptance-v1.md",
    "tools/h3_n2_stage2d6_lifecycle_assembly_boundary_gate_20260721_v54.py",
    "tools/h3_n2_stage2d7_isolated_acceptance_boundary_gate_20260721_v55.py",
    "docs/development/h3-n2-stage2d6-lifecycle-assembly-20260721.md",
    "docs/development/h3-n2-stage2d7-isolated-acceptance-20260721.md",
)

FORBIDDEN_COMPONENT_TOKENS = (
    "esp_efuse_",
    "esp_hmac_calculate(",
    "EfuseHmacPersistenceKeyProvider",
    "nvs_flash_erase(",
    "nvs_flash_erase_partition(",
    "nvs_flash_init(",
    "nvs_flash_init_partition(",
    "esp_restart(",
    "homeassistant",
    "greenhouse-manager",
    "gh/v1/",
    "broker.greenhouse",
    "192.168.",
    "10.0.",
    "172.16.",
    "-----BEGIN CERTIFICATE-----",
)

FORBIDDEN_YAML_KEYS = (
    "mqtt:",
    "on_boot:",
    "api:",
    "ota:",
    "web_server:",
    "button:",
    "switch:",
    "script:",
    "interval:",
)


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def read(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def fail(errors: list[str]) -> None:
    DIAGNOSTIC.write_text("\n".join(errors) + "\n", encoding="utf-8")
    raise SystemExit("stage2d8_isolated_device_driver_boundary=fail")


def main() -> None:
    errors: list[str] = []

    missing = sorted(path for path in EXPECTED_PATHS if not Path(path).is_file())
    if missing:
        errors.append(f"missing expected Stage 2D-8 paths: {missing}")

    try:
        changed = {
            line
            for line in git("diff", "--name-only", BASE_COMMIT, "--").splitlines()
            if line
        }
    except subprocess.CalledProcessError as exc:
        errors.append(f"cannot compare exact Stage 2D-8 base: {exc}")
        changed = set()

    unexpected = sorted(changed - EXPECTED_PATHS)
    absent = sorted(EXPECTED_PATHS - changed)
    if unexpected:
        errors.append(f"unexpected changed paths: {unexpected}")
    if absent:
        errors.append(f"expected paths absent from diff: {absent}")

    try:
        protected = git("diff", "--name-only", BASE_COMMIT, "--", *PROTECTED_PATHS)
        if protected:
            errors.append(f"protected Stage 2D-6/2D-7/production paths changed: {protected}")
    except subprocess.CalledProcessError as exc:
        errors.append(f"cannot verify protected paths: {exc}")

    component = Path(
        "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver"
    )
    init_text = read(component / "__init__.py")
    core_text = read(component / "isolated_device_driver.h") + "\n" + read(
        component / "isolated_device_driver.cpp"
    )
    port_text = read(component / "isolated_device_esp32_ports.h") + "\n" + read(
        component / "isolated_device_esp32_ports.cpp"
    )
    component_text = init_text + "\n" + core_text + "\n" + port_text

    for token in FORBIDDEN_COMPONENT_TOKENS:
        if token.lower() in component_text.lower():
            errors.append(f"forbidden production or irreversible token: {token}")

    for token in (
        "cg.new_Pvariable",
        "register_component(",
        "register_service(",
        "automation.register_action",
    ):
        if token in init_text:
            errors.append(f"compile-only component creates runtime surface: {token}")
    for marker in (
        'AUTO_LOAD = [',
        'cg.add_define("USE_GREENHOUSE_PROFILE_ISOLATED_DEVICE_DRIVER")',
        "creates no",
        "one-shot authorizations",
    ):
        if marker not in init_text:
            errors.append(f"compile-only component marker missing: {marker}")

    if re.search(
        r"(?i)(password|secret|private_key|test_key)\s*=\s*[\"'][^\"']+[\"']",
        component_text,
    ):
        errors.append("compiled credential-like literal present in driver source")

    direct_nvs_tokens = (
        "nvs_open_from_partition(",
        "nvs_erase_all(",
        "nvs_commit(",
        "nvs_close(",
    )
    for token in direct_nvs_tokens:
        if token in core_text or token in init_text:
            errors.append(f"direct NVS token outside ESP32 test port: {token}")
    for marker in (
        'safe_test_storage_name(this->partition_label, "gh2d8_")',
        'safe_test_storage_name(this->namespace_name, "gh2d8_")',
        "MirroredGenerationWriteAuthorization",
        "IsolatedDeviceAuthorizationBinder",
        "AUTHORITY_AMBIGUOUS",
        "MARKER_LAST_NOT_PROVEN",
    ):
        if marker not in core_text:
            errors.append(f"driver safety contract missing: {marker}")

    for marker in (
        "AuditedEspIdfNvsBackend",
        'committed_keys.back() != "active"',
        'record == "slot_a" || record == "slot_b"',
        'exchange->publish_topic = this->candidate_.test_topic_root + "/probe/request"',
        'exchange->subscribe_topic =',
        'rfind("gh-test/", 0)',
        "nvs_erase_all(handle)",
    ):
        if marker not in port_text:
            errors.append(f"ESP32 test-port contract missing: {marker}")
    if port_text.count("nvs_erase_all(") != 1:
        errors.append("test namespace erase must have exactly one explicit implementation")
    if "nvs_flash_erase" in port_text or "esp_efuse" in port_text:
        errors.append("partition erase or eFuse access present in ESP32 test port")

    dedicated_yaml = read(
        "firmware/esphome_rc/board_lab/h3_profile_isolated_device_driver/"
        "greenhouse_profile_isolated_device_driver_board_lab_20260721_v56.yml"
    )
    product_overlay = read(
        "firmware/esphome_rc/f1_0_rc2/"
        "f1_0_rc2_h3_profile_isolated_device_driver_board_lab_20260721_v56.yml"
    )
    if "enable_on_boot: false" not in dedicated_yaml:
        errors.append("dedicated Stage 2D-8 target does not disable Wi-Fi at boot")
    for yaml_name, yaml_text in (
        ("dedicated", dedicated_yaml),
        ("product-overlay", product_overlay),
    ):
        for key in FORBIDDEN_YAML_KEYS:
            if re.search(rf"(?m)^\s*{re.escape(key)}\s*$", yaml_text):
                errors.append(f"{yaml_name} target adds forbidden YAML key: {key}")
        if yaml_text.count("greenhouse_profile_isolated_device_driver:") != 1:
            errors.append(f"{yaml_name} target must contain one inert component block")
    if "must not be flashed" not in product_overlay:
        errors.append("product overlay lacks explicit no-flash warning")

    broker_conf = read(
        "tests/h3_n2_stage2d8_isolated_broker/"
        "mosquitto_isolated_test_20260721_v56.conf.template"
    )
    broker_acl = read(
        "tests/h3_n2_stage2d8_isolated_broker/"
        "mosquitto_isolated_test_acl_20260721_v56.template"
    )
    for marker in (
        "allow_anonymous false",
        "persistence false",
        "retain_available false",
        "require_certificate false",
    ):
        if marker not in broker_conf:
            errors.append(f"isolated Broker template missing: {marker}")
    if re.search(r"(?m)^\s*bridge\b", broker_conf):
        errors.append("isolated Broker template enables a bridge")
    if broker_acl.count("topic ") != 1 or "gh-test/<TEST_RUN_ID>/#" not in broker_acl:
        errors.append("isolated ACL must expose exactly one test root")
    if "homeassistant" in (broker_conf + broker_acl).lower() or "gh/v1/" in (
        broker_conf + broker_acl
    ):
        errors.append("production topic present in Broker templates")

    manifest_gate = read(
        "tools/h3_n2_stage2d8_execution_manifest_gate_20260721_v56.py"
    )
    for marker in (
        'require(gate == "LOCKED"',
        "--allow-live-gate",
        "FORBIDDEN_FIELD_FRAGMENTS",
        "authorization generations must match observed state",
        "test_partition_label",
        "test_namespace",
    ):
        if marker not in manifest_gate:
            errors.append(f"execution manifest gate marker missing: {marker}")
    for token in ("subprocess.run", "socket.", "serial.", "requests.", "nvs_"):
        if token in manifest_gate:
            errors.append(f"manifest gate contains live-operation token: {token}")

    host_test = read(
        component
        / "tests/pairing_stage2d8_isolated_device_driver_fault_matrix_20260721_v56.cpp"
    )
    for marker in (
        "test_driver_requires_mirrored_prepare_grant",
        "test_complete_reversible_flow",
        "test_marker_commit_failure_is_terminal",
        "test_missing_marker_last_proof_is_terminal",
        "test_promotion_failure_after_marker_is_terminal",
        "test_read_only_write_drift_fails_closed",
        "test_cleanup_failure_preserves_evidence_and_key",
    ):
        if marker not in host_test:
            errors.append(f"host fault matrix coverage missing: {marker}")

    documentation = (
        read("docs/development/h3-n2-stage2d8-isolated-device-driver-20260721.md")
        + "\n"
        + read("protocols/pairing/gh-h3-node-isolated-device-driver-v1.md")
        + "\n"
        + read("docs/development/h3-n2-stage2d8-live-authorization-record-20260721.md")
    )
    for marker in (
        "compile-only",
        "two-layer",
        "marker-last",
        "does not instantiate",
        "separate later one-shot approval",
        "No production Home Assistant",
    ):
        if marker.lower() not in documentation.lower():
            errors.append(f"Stage 2D-8 boundary documentation missing: {marker}")

    if errors:
        fail(errors)

    DIAGNOSTIC.unlink(missing_ok=True)
    print("stage2d8_isolated_device_driver_boundary=pass")


if __name__ == "__main__":
    main()
