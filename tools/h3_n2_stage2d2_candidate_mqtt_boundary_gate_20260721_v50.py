#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = Path("/tmp/stage2d2-candidate-mqtt-boundary-v50.txt")

CORE_HEADER = ROOT / (
    "firmware/esphome_rc/components/greenhouse_pairing_client/"
    "pairing_candidate_mqtt_validator.h"
)
CORE_SOURCE = ROOT / (
    "firmware/esphome_rc/components/greenhouse_pairing_client/"
    "pairing_candidate_mqtt_validator.cpp"
)
TEST_SOURCE = ROOT / (
    "firmware/esphome_rc/components/greenhouse_pairing_client/tests/"
    "pairing_stage2d2_candidate_mqtt_validator_fault_matrix_20260721_v50.cpp"
)
LAB_ROOT = ROOT / "firmware/esphome_rc/components/greenhouse_candidate_mqtt_lab"
LAB_INIT = LAB_ROOT / "__init__.py"
LAB_HEADER = LAB_ROOT / "greenhouse_candidate_mqtt_lab.h"
LAB_SOURCE = LAB_ROOT / "greenhouse_candidate_mqtt_lab.cpp"
MINIMAL_YAML = ROOT / (
    "firmware/esphome_rc/board_lab/h3_candidate_mqtt_validator/"
    "greenhouse_candidate_mqtt_validator_board_lab_20260721_v50.yml"
)
PRODUCT_YAML = ROOT / (
    "firmware/esphome_rc/f1_0_rc2/"
    "f1_0_rc2_h3_candidate_mqtt_validator_board_lab_20260721_v50.yml"
)
PRODUCTION_RC2 = ROOT / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml"

REQUIRED = (
    CORE_HEADER,
    CORE_SOURCE,
    TEST_SOURCE,
    LAB_INIT,
    LAB_HEADER,
    LAB_SOURCE,
    MINIMAL_YAML,
    PRODUCT_YAML,
)

ALLOWED_CHANGED_PREFIXES = (
    ".github/workflows/h3-n2-stage2d2-candidate-mqtt-validator-ci.yml",
    "docs/development/h3-n2-stage2d2-candidate-mqtt-validator-20260721.md",
    "protocols/pairing/gh-h3-node-candidate-mqtt-validation-v1.md",
    "tools/h3_n2_stage2d2_candidate_mqtt_boundary_gate_20260721_v50.py",
    "firmware/esphome_rc/components/greenhouse_pairing_client/"
    "pairing_candidate_mqtt_validator.",
    "firmware/esphome_rc/components/greenhouse_pairing_client/tests/"
    "pairing_stage2d2_candidate_mqtt_validator_fault_matrix_20260721_v50.cpp",
    "firmware/esphome_rc/components/greenhouse_candidate_mqtt_lab/",
    "firmware/esphome_rc/board_lab/h3_candidate_mqtt_validator/",
    "firmware/esphome_rc/f1_0_rc2/"
    "f1_0_rc2_h3_candidate_mqtt_validator_board_lab_20260721_v50.yml",
)


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def changed_paths() -> list[str]:
    base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    if not base_ref:
        return []
    completed = subprocess.run(
        ("git", "diff", "--name-only", f"origin/{base_ref}...HEAD"),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("unable to resolve PR changed paths")
    return [line for line in completed.stdout.splitlines() if line]


def allowed_changed(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in ALLOWED_CHANGED_PREFIXES)


def main() -> int:
    failures: list[str] = []
    for path in REQUIRED:
        require(path.is_file(), f"required Stage 2D-2 path missing: {path}", failures)
    if failures:
        DIAGNOSTIC.write_text("\n".join(failures) + "\n", encoding="utf-8")
        return 1

    core_header = read(CORE_HEADER)
    core_source = read(CORE_SOURCE)
    test_source = read(TEST_SOURCE)
    lab_init = read(LAB_INIT)
    lab_header = read(LAB_HEADER)
    lab_source = read(LAB_SOURCE)
    yaml_text = read(MINIMAL_YAML) + "\n" + read(PRODUCT_YAML)
    production_text = read(PRODUCTION_RC2)
    stage_text = "\n".join(
        (core_header, core_source, test_source, lab_init, lab_header, lab_source, yaml_text)
    )

    require(
        "class CandidateMqttProfileValidator" in core_header,
        "candidate validator class missing",
        failures,
    )
    require(
        "class CandidateMqttTransport" in core_header,
        "candidate transport abstraction missing",
        failures,
    )
    require(
        "active_profile_unchanged" in core_header
        and "candidate_client_live" in core_header,
        "active/candidate isolation evidence missing",
        failures,
    )
    require(
        "CandidateMqttProbePhase::VERIFIED" in core_source,
        "VERIFIED terminal state missing",
        failures,
    )
    require(
        ".activate(" not in core_source and "activation_.activate" not in stage_text,
        "Stage 2D-2 must not activate or switch the candidate profile",
        failures,
    )
    require(
        "esp_mqtt_client_handle_t client_" in lab_header,
        "independent ESP-IDF candidate client handle missing",
        failures,
    )
    require(
        "esp_mqtt_client_init" in lab_source
        and "esp_mqtt_client_destroy" in lab_source,
        "candidate client lifecycle implementation missing",
        failures,
    )
    require(
        "include_builtin_idf_component(\"mqtt\")" in lab_init,
        "ESP-IDF mqtt compile dependency missing",
        failures,
    )

    setup_match = re.search(
        r"void GreenhouseCandidateMqttLab::setup\(\)\s*\{(?P<body>.*?)\n\}",
        lab_source,
        flags=re.DOTALL,
    )
    require(setup_match is not None, "lab setup body missing", failures)
    if setup_match is not None:
        setup_body = setup_match.group("body")
        require(
            "esp_mqtt_client_init" not in setup_body
            and "begin_for_lab" not in setup_body
            and ".begin(" not in setup_body,
            "lab setup must not create or start a candidate MQTT client",
            failures,
        )

    require(
        "begin_for_lab" not in yaml_text,
        "YAML must not expose an automatic or button-triggered Broker probe",
        failures,
    )
    require(
        "enable_on_boot: false" in read(MINIMAL_YAML),
        "minimal compile target Wi-Fi must remain disabled at boot",
        failures,
    )
    require(
        "greenhouse_candidate_mqtt_lab" not in production_text
        and "pairing_candidate_mqtt_validator" not in production_text,
        "production RC2 YAML was wired to the Stage 2D-2 lab",
        failures,
    )

    forbidden_apis = (
        "nvs_set_",
        "nvs_erase_",
        "esp_efuse_",
        "burn_efuse",
        "global_mqtt_client",
        "set_username(",
        "set_password(",
    )
    for token in forbidden_apis:
        require(token not in stage_text, f"forbidden production mutation token: {token}", failures)

    require(
        "gh/v1/" in core_source
        and "/ingress/node/" in core_source
        and "/out/node/" in core_source,
        "controlled MQTT V1 probe topics missing",
        failures,
    )
    require(
        "gh.telemetry-probe/1" in core_source
        and "gh.telemetry-probe-confirm/1" in core_source,
        "controlled telemetry probe schemas missing",
        failures,
    )

    private_ipv4 = re.compile(
        r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
    )
    require(
        private_ipv4.search(stage_text) is None,
        "environment-looking private Broker address found",
        failures,
    )

    try:
        paths = changed_paths()
    except RuntimeError as error:
        failures.append(str(error))
        paths = []
    unexpected = [path for path in paths if not allowed_changed(path)]
    require(
        not unexpected,
        "Stage 2D-2 PR changed protected paths: " + ", ".join(unexpected),
        failures,
    )

    summary = {
        "schema": "gh.h3.n2.stage2d2-candidate-mqtt-boundary/1",
        "status": "passed" if not failures else "failed",
        "candidate_client_isolated": "esp_mqtt_client_handle_t client_" in lab_header,
        "auto_start_disabled": "begin_for_lab" not in yaml_text,
        "production_profile_mutation_present": any(
            token in stage_text for token in forbidden_apis
        ),
        "real_broker_literal_present": private_ipv4.search(stage_text) is not None,
        "changed_path_count": len(paths),
        "unexpected_paths": unexpected,
        "failures": failures,
    }
    if failures:
        DIAGNOSTIC.write_text(
            json.dumps(summary, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return 1
    DIAGNOSTIC.unlink(missing_ok=True)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
