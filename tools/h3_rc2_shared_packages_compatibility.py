from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "firmware/esphome_rc/components/greenhouse_pairing_client"
RC2 = ROOT / "firmware/esphome_rc/f1_0_rc2"
FORBIDDEN = (
    "ghs_",
    "BEGIN CERTIFICATE",
    "mqtt_password",
    "broker.greenhouse.local",
    "nvs_namespace",
    "efuse_key",
)


@dataclass(frozen=True)
class Stage:
    name: str
    host_sources: tuple[str, ...]
    minimal_dir: str
    minimal_config: str
    product_config: str
    component_object: str
    lab_object: str
    link_crypto: bool = False


STAGES = {
    "d2": Stage(
        name="Stage 2D-2 candidate MQTT",
        host_sources=(
            "pairing_mqtt_activation_contract.cpp",
            "pairing_candidate_mqtt_validator.cpp",
            "tests/pairing_stage2d2_candidate_mqtt_validator_fault_matrix_20260721_v50.cpp",
        ),
        minimal_dir="firmware/esphome_rc/board_lab/h3_candidate_mqtt_validator",
        minimal_config="greenhouse_candidate_mqtt_validator_board_lab_20260721_v50.yml",
        product_config="f1_0_rc2_h3_candidate_mqtt_validator_board_lab_20260721_v50.yml",
        component_object="pairing_candidate_mqtt_validator.cpp.o",
        lab_object="greenhouse_candidate_mqtt_lab.cpp.o",
    ),
    "d3": Stage(
        name="Stage 2D-3 profile activation",
        host_sources=(
            "pairing_profile_activation_coordinator.cpp",
            "tests/pairing_stage2d3_activation_transaction_fault_matrix_20260721_v51.cpp",
        ),
        minimal_dir="firmware/esphome_rc/board_lab/h3_profile_activation",
        minimal_config="greenhouse_profile_activation_board_lab_20260721_v51.yml",
        product_config="f1_0_rc2_h3_profile_activation_board_lab_20260721_v51.yml",
        component_object="pairing_profile_activation_coordinator.cpp.o",
        lab_object="greenhouse_profile_activation_lab.cpp.o",
    ),
    "d4": Stage(
        name="Stage 2D-4 profile lifecycle",
        host_sources=(
            "pairing_client_core.cpp",
            "pairing_transport_core.cpp",
            "secure_pairing_channel.cpp",
            "secure_pairing_channel_encoding.cpp",
            "secure_pairing_channel_crypto.cpp",
            "pairing_ram_credentials.cpp",
            "pairing_persistence_backend.cpp",
            "pairing_persistence_crypto.cpp",
            "pairing_credential_codec.cpp",
            "pairing_persistent_store.cpp",
            "pairing_mqtt_activation_contract.cpp",
            "pairing_candidate_mqtt_validator.cpp",
            "pairing_profile_activation_coordinator.cpp",
            "pairing_profile_lifecycle_integration.cpp",
            "tests/pairing_stage2d4_profile_lifecycle_integration_fault_matrix_20260721_v52.cpp",
        ),
        minimal_dir="firmware/esphome_rc/board_lab/h3_profile_lifecycle",
        minimal_config="greenhouse_profile_lifecycle_board_lab_20260721_v52.yml",
        product_config="f1_0_rc2_h3_profile_lifecycle_board_lab_20260721_v52.yml",
        component_object="pairing_profile_lifecycle_integration.cpp.o",
        lab_object="greenhouse_profile_lifecycle_lab.cpp.o",
        link_crypto=True,
    ),
}


class StageFailure(RuntimeError):
    def __init__(self, step: str, detail: str, log: Path | None = None):
        super().__init__(f"{step}: {detail}")
        self.log = log


def host_command(stage: Stage, binary: Path) -> list[str]:
    command = [
        "g++",
        "-std=gnu++20",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-I",
        COMPONENT,
        *(f"{COMPONENT}/{name}" for name in stage.host_sources),
    ]
    if stage.link_crypto:
        command.append("-lcrypto")
    return [*command, "-o", str(binary)]


def run_logged(
    step: str,
    command: list[str],
    cwd: Path,
    log: Path,
    *,
    environment: dict[str, str] | None = None,
    timeout: int = 1200,
) -> None:
    try:
        with log.open("wb") as output:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=output,
                stderr=subprocess.STDOUT,
                env=environment,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise StageFailure(step, "command timed out", log) from exc
    except OSError as exc:
        raise StageFailure(step, f"command unavailable ({type(exc).__name__})", log) from exc
    if result.returncode != 0:
        raise StageFailure(step, f"exit code {result.returncode}", log)
    print(f"{step}: PASS", flush=True)


def sanitized_diagnostic(log: Path, ephemeral: tuple[str, ...]) -> list[str]:
    if not log.is_file():
        return []
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[-65:]
    visible = []
    for line in lines:
        if any(value and value in line for value in ephemeral):
            visible.append("[REDACTED_EPHEMERAL_VALUE]")
            continue
        if any(marker.lower() in line.lower() for marker in FORBIDDEN):
            visible.append("[REDACTED_SENSITIVE_CONTENT]")
            continue
        line = re.sub(r"(?i)(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})", "[REDACTED_TOKEN]", line)
        line = re.sub(r"(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){3}", "[REDACTED_ADDRESS]", line)
        visible.append(line[:360])
    return visible


def verify_compile(stage: Stage, logs: tuple[Path, Path], ephemeral: tuple[str, ...]) -> None:
    for label, log in zip(("minimal", "product"), logs):
        data = log.read_text(encoding="utf-8", errors="replace")
        if any(value and value in data for value in ephemeral):
            raise StageFailure(f"{label} secret redaction", "ephemeral credential in log")
        if any(value.lower() in data.lower() for value in FORBIDDEN):
            raise StageFailure(f"{label} secret redaction", "forbidden credential marker in log")
        expected = (
            stage.component_object,
            stage.lab_object,
            "INFO Successfully compiled program.",
        )
        missing = [item for item in expected if item not in data]
        if missing:
            raise StageFailure(f"{label} compile evidence", f"missing expected objects: {missing}")
        print(f"{stage.name} {label} compile evidence: PASS", flush=True)


def execute(stage: Stage) -> None:
    ephemeral: tuple[str, ...] = ()
    with tempfile.TemporaryDirectory(prefix="h3-rc2-compat-") as temporary:
        area = Path(temporary)
        binary = area / "fault-matrix"
        run_logged(
            f"{stage.name} host compile",
            host_command(stage, binary),
            ROOT,
            area / "host-build.log",
            timeout=180,
        )
        run_logged(
            f"{stage.name} host fault matrix",
            [str(binary)],
            ROOT,
            area / "host-run.log",
            timeout=120,
        )

        minimal_root = ROOT / stage.minimal_dir
        secrets_file = minimal_root / "secrets.yaml"
        if secrets_file.exists():
            raise StageFailure(stage.name, "refusing to overwrite an existing secrets file")
        ssid = f"ci-h3-{secrets.token_hex(5)}"
        password = secrets.token_urlsafe(30)
        ephemeral = (ssid, password)
        environment = dict(os.environ, RC2_CONFIG=stage.product_config)
        minimal_log = area / "minimal-compile.log"
        product_log = area / "product-compile.log"
        try:
            secrets_file.write_text(
                f'node_pairing_wifi_ssid: "{ssid}"\n'
                f'node_pairing_wifi_password: "{password}"\n',
                encoding="utf-8",
            )
            run_logged(
                f"{stage.name} minimal config",
                ["esphome", "config", stage.minimal_config],
                minimal_root,
                area / "minimal-config.log",
                timeout=180,
            )
            run_logged(
                f"{stage.name} minimal ESP32-C6 compile",
                ["esphome", "compile", stage.minimal_config],
                minimal_root,
                minimal_log,
                timeout=1200,
            )
            run_logged(
                f"{stage.name} product config",
                ["bash", "tools/rc2.sh", "config"],
                RC2,
                area / "product-config.log",
                environment=environment,
                timeout=180,
            )
            run_logged(
                f"{stage.name} full RC2 ESP32-C6 compile",
                ["bash", "tools/rc2.sh", "compile"],
                RC2,
                product_log,
                environment=environment,
                timeout=1200,
            )
            verify_compile(stage, (minimal_log, product_log), ephemeral)
        except StageFailure as exc:
            if exc.log is not None:
                for line in sanitized_diagnostic(exc.log, ephemeral):
                    print(line, flush=True)
            raise
        finally:
            secrets_file.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    args = parser.parse_args()
    try:
        execute(STAGES[args.stage])
    except StageFailure as error:
        print(f"H3 compatibility FAIL: {error}", flush=True)
        return 1
    print(f"H3 compatibility {args.stage}: COMPLETE PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
