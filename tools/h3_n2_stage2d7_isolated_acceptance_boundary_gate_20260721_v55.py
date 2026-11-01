#!/usr/bin/env python3
"""Fail-closed Stage 2D-7 source and execution boundary gate."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

BASE_COMMIT = "b8cc4f68d29393cdf9da7d00fdfeef28ee147c7b"
DIAGNOSTIC = Path("/tmp/stage2d7-isolated-acceptance-boundary-v55.txt")

EXPECTED_PATHS = {
    ".github/workflows/h3-n2-stage2d7-isolated-acceptance-ci.yml",
    "docs/development/h3-n2-stage2d7-isolated-acceptance-20260721.md",
    "firmware/esphome_rc/board_lab/h3_profile_isolated_acceptance/greenhouse_profile_isolated_acceptance_board_lab_20260721_v55.yml",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance/__init__.py",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance/isolated_acceptance_package.cpp",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance/isolated_acceptance_package.h",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance/tests/pairing_stage2d7_isolated_acceptance_fault_matrix_20260721_v55.cpp",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_isolated_acceptance_board_lab_20260721_v55.yml",
    "protocols/pairing/gh-h3-node-isolated-acceptance-v1.md",
    "tools/h3_n2_stage2d7_isolated_acceptance_boundary_gate_20260721_v55.py",
}

PROTECTED_PATHS = (
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml",
    "firmware/esphome_rc/f1_0_rc2/packages",
    "firmware/esphome_rc/components/greenhouse_profile_lifecycle_controller",
    "firmware/esphome_rc/board_lab/h3_profile_lifecycle_controller",
    "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_lifecycle_controller_board_lab_20260721_v54.yml",
    ".github/workflows/h3-n2-stage2d6-lifecycle-assembly-ci.yml",
    "protocols/pairing/gh-h3-node-profile-lifecycle-controller-v1.md",
    "tools/h3_n2_stage2d6_lifecycle_assembly_boundary_gate_20260721_v54.py",
)

FORBIDDEN_RUNTIME_TOKENS = (
    "nvs_open(",
    "nvs_open_from_partition(",
    "nvs_set_",
    "nvs_erase_",
    "nvs_commit(",
    "esp_mqtt_client_init(",
    "esp_mqtt_client_start(",
    "esp_mqtt_client_publish(",
    "esp_efuse_",
    "esp_hmac_calculate(",
    "EfuseHmacPersistenceKeyProvider(",
    "cg.new_Pvariable",
    "register_component(",
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

SENSITIVE_EVIDENCE_NAMES = (
    "broker_host",
    "broker_port",
    "broker_tls_server_name",
    "ca_pem",
    "mqtt_username",
    "mqtt_client_id",
    "mqtt_password",
    "authorization_digest",
)


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def fail(errors: list[str]) -> None:
    DIAGNOSTIC.write_text("\n".join(errors) + "\n", encoding="utf-8")
    raise SystemExit("Stage 2D-7 boundary gate failed")


def main() -> None:
    errors: list[str] = []

    missing = sorted(path for path in EXPECTED_PATHS if not Path(path).is_file())
    if missing:
        errors.append(f"missing expected paths: {missing}")

    try:
        changed = {
            line
            for line in git("diff", "--name-only", BASE_COMMIT, "--").splitlines()
            if line
        }
    except subprocess.CalledProcessError as exc:
        errors.append(f"cannot compare Stage 2D-7 base commit: {exc}")
        changed = set()

    unexpected = sorted(changed - EXPECTED_PATHS)
    if unexpected:
        errors.append(f"unexpected changed paths: {unexpected}")
    absent_from_diff = sorted(EXPECTED_PATHS - changed)
    if absent_from_diff:
        errors.append(f"expected Stage 2D-7 paths absent from diff: {absent_from_diff}")

    try:
        protected_diff = git("diff", "--name-only", BASE_COMMIT, "--", *PROTECTED_PATHS)
        if protected_diff:
            errors.append(f"protected Stage 2D-6/production paths changed: {protected_diff}")
    except subprocess.CalledProcessError as exc:
        errors.append(f"cannot verify protected paths: {exc}")

    component_root = Path(
        "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance"
    )
    source_paths = (
        component_root / "__init__.py",
        component_root / "isolated_acceptance_package.h",
        component_root / "isolated_acceptance_package.cpp",
    )
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for token in FORBIDDEN_RUNTIME_TOKENS:
        if token in source_text:
            errors.append(f"forbidden runtime token in Stage 2D-7 source: {token}")

    init_text = read(str(component_root / "__init__.py"))
    required_init_markers = (
        'AUTO_LOAD = ["greenhouse_profile_lifecycle_controller"]',
        'cg.add_define("USE_GREENHOUSE_PROFILE_ISOLATED_ACCEPTANCE")',
        "creates no driver",
    )
    for marker in required_init_markers:
        if marker not in init_text:
            errors.append(f"compile-only component marker missing: {marker}")

    dedicated_yaml_path = (
        "firmware/esphome_rc/board_lab/h3_profile_isolated_acceptance/"
        "greenhouse_profile_isolated_acceptance_board_lab_20260721_v55.yml"
    )
    dedicated_yaml = read(dedicated_yaml_path)
    if "enable_on_boot: false" not in dedicated_yaml:
        errors.append("dedicated test target does not disable Wi-Fi at boot")
    for key in FORBIDDEN_YAML_KEYS:
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*$", dedicated_yaml):
            errors.append(f"forbidden dedicated-target YAML key: {key}")
    if dedicated_yaml.count("greenhouse_profile_isolated_acceptance:") != 1:
        errors.append("dedicated target must contain exactly one inert component block")

    product_overlay = read(
        "firmware/esphome_rc/f1_0_rc2/"
        "f1_0_rc2_h3_profile_isolated_acceptance_board_lab_20260721_v55.yml"
    )
    for key in ("mqtt:", "on_boot:"):
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*$", product_overlay):
            errors.append(f"product compile overlay adds forbidden YAML key: {key}")
    if "must not be flashed" not in product_overlay:
        errors.append("product compile overlay lacks no-flash warning")

    if re.search(r"(?<![0-9])(?:192\.168|10\.\d+\.\d+\.|172\.(?:1[6-9]|2\d|3[01])\.)", source_text):
        errors.append("private network literal present in Stage 2D-7 component source")
    if "BEGIN CERTIFICATE" in source_text:
        errors.append("certificate body present in Stage 2D-7 component source")
    if re.search(r"(?i)(password|secret|key)\s*=\s*[\"'][^\"']+[\"']", source_text):
        errors.append("compiled credential-like default present in component source")

    header = read(str(component_root / "isolated_acceptance_package.h"))
    implementation = read(str(component_root / "isolated_acceptance_package.cpp"))
    required_contracts = (
        "PREPARE_CANDIDATE",
        "ACTIVATE_PROFILE",
        "CLEANUP_TEST_STATE",
        "OneShotGenerationAuthorization",
        "VolatileTestPersistenceKeyProvider",
        "AUTHORIZATION_NOT_CONSUMED",
        "marker_last_observed",
        "cleanup_confirmed",
    )
    for marker in required_contracts:
        if marker not in header + implementation:
            errors.append(f"required Stage 2D-7 contract missing: {marker}")

    evidence_start = implementation.find(
        "std::string IsolatedAcceptancePackage::evidence_json_() const"
    )
    evidence_end = implementation.find(
        "std::string IsolatedAcceptancePackage::json_escape_", evidence_start
    )
    if evidence_start < 0 or evidence_end < 0:
        errors.append("redacted evidence serializer not found")
    else:
        evidence_body = implementation[evidence_start:evidence_end]
        for sensitive_name in SENSITIVE_EVIDENCE_NAMES:
            if sensitive_name in evidence_body:
                errors.append(
                    f"sensitive candidate field referenced by evidence serializer: {sensitive_name}"
                )

    protocol = read("protocols/pairing/gh-h3-node-isolated-acceptance-v1.md")
    for marker in (
        "Stage 2D-8 physical fault matrix",
        "Cleanup is itself a persistent write",
        "gh.h3.n2.stage2d7-isolated-evidence/1",
        "No Stage 2D-8 action is authorized",
        "P01",
        "A09",
        "C02",
    ):
        if marker not in protocol:
            errors.append(f"protocol requirement missing: {marker}")

    workflow = read(".github/workflows/h3-n2-stage2d7-isolated-acceptance-ci.yml")
    for marker in (
        "host-fault-matrix",
        "esp32-c6-compile",
        "secret redaction",
        "production paths remain unchanged",
    ):
        if marker not in workflow:
            errors.append(f"CI marker missing: {marker}")

    if errors:
        fail(errors)

    DIAGNOSTIC.unlink(missing_ok=True)
    print("stage2d7_isolated_acceptance_boundary=pass")


if __name__ == "__main__":
    main()
