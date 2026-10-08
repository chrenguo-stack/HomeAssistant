from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

GATE = "N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_FULL_EXACT_FLASH_NO_BOOT_20261008_01"
REPOSITORY = "chrenguo-stack/HomeAssistant"
BUILD_RUN_ID = "37594598870"
ARTIFACT_ID = "11469977052"
ARTIFACT_NAME = "n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source"
RELEASE_ZIP_NAME = "n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source.zip"
RELEASE_ZIP_SIZE = 4340810
RELEASE_ZIP_SHA256 = "55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c"
SOURCE_HEAD = "629f096a32e087087ea32d30707dcc3cd6295e5d"
SOURCE_TREE = "0b97a97a63d7e251ed92cc96507386b454709161"
EXPECTED_SILICON_SHA256 = "f9c00d136f84d1fdabb1e296608702539ed674271021b28cff2d4a23e4cd2bf7"
EXPECTED_MEMBERS = {
    "MANIFEST.txt": None,
    "bootloader.bin": (22576, "985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5"),
    "firmware.bin": (1412672, "4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65"),
    "firmware.factory.bin": (1478208, "658645083ed2d83d6951abeb5f894dbde7d7124030c8bc1815683ed2bf24e914"),
    "firmware.ota.bin": (1412672, "4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65"),
    "flash_args": (167, "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713"),
    "ota_data_initial.bin": (8192, "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"),
    "partitions.bin": (3072, "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"),
}
FLASH_LAYOUT = (
    (0x0000, "bootloader.bin"),
    (0x8000, "partitions.bin"),
    (0x9000, "ota_data_initial.bin"),
    (0x10000, "firmware.bin"),
)
MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
ESPTOOL_VERSION_RE = re.compile(r"\besptool(?:\.py)?\s+v?(\d+)\.(\d+)\.(\d+)\b", re.I)
FLASH_8MB_RE = re.compile(r"Detected flash size:\s*8\s*MB\b", re.I)
SECURE_BOOT_DISABLED_RE = re.compile(r"Secure Boot:\s*Disabled\b", re.I)
FLASH_ENCRYPTION_DISABLED_RE = re.compile(r"Flash Encryption:\s*Disabled\b", re.I)


class StopExecution(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise StopExecution("COMMAND_TIMEOUT") from error


def require_command(args: list[str], error_code: str, *, timeout: int = 120) -> str:
    proc = run(args, timeout=timeout)
    if proc.returncode != 0:
        raise StopExecution(error_code)
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def esptool_base(port: str | None = None) -> list[str]:
    result = [sys.executable, "-m", "esptool", "--chip", "esp32c6"]
    if port is not None:
        result += [
            "--port",
            port,
            "--before",
            "no-reset",
            "--after",
            "no-reset",
            "--no-stub",
        ]
    return result


def verify_esptool() -> str:
    output = require_command(
        [sys.executable, "-m", "esptool", "version"],
        "ESPTOOL_VERSION_FAILED",
    )
    match = ESPTOOL_VERSION_RE.search(output)
    if match is None:
        raise StopExecution("ESPTOOL_VERSION_UNPARSEABLE")
    major, minor, patch = map(int, match.groups())
    if major != 5:
        raise StopExecution("ESPTOOL_MAJOR_NOT_5")
    return f"{major}.{minor}.{patch}"


def ensure_single_port() -> str:
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if len(ports) != 1:
        raise StopExecution("USB_MODEM_COUNT_NOT_1")
    port = ports[0]
    for _ in range(2):
        proc = run(["lsof", "-t", "--", port], timeout=10)
        if proc.returncode == 0 and (proc.stdout or "").strip():
            raise StopExecution("SERIAL_PORT_BUSY")
        if proc.returncode not in (0, 1):
            raise StopExecution("SERIAL_OWNER_CHECK_FAILED")
        time.sleep(1)
    return port


def silicon_sha256_from_security(output: str) -> str:
    if "ESP32-C6" not in output.upper():
        raise StopExecution("TARGET_NOT_ESP32_C6")
    mac = MAC_RE.search(output)
    if mac is None:
        raise StopExecution("ROM_MAC_MISSING")
    compact = mac.group(1).replace(":", "").lower()
    binding = "rom-c6-" + compact
    return sha256_bytes(binding.encode("ascii"))


def fresh_board_preclaim(port: str, expected_silicon_sha256: str) -> dict[str, str]:
    security = require_command(
        esptool_base(port) + ["get-security-info"],
        "SECURITY_INFO_FAILED",
        timeout=60,
    )
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("SECURE_BOOT_DISABLED_NOT_PROVEN")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("FLASH_ENCRYPTION_DISABLED_NOT_PROVEN")
    silicon_sha = silicon_sha256_from_security(security)
    if silicon_sha != EXPECTED_SILICON_SHA256:
        raise StopExecution("SILICON_BINDING_MISMATCH")
    flash_id = require_command(
        esptool_base(port) + ["flash-id"],
        "FLASH_ID_FAILED",
        timeout=60,
    )
    if FLASH_8MB_RE.search(flash_id) is None:
        raise StopExecution("FLASH_SIZE_8MB_NOT_PROVEN")
    return {
        "silicon_sha256": silicon_sha,
        "security_output_sha256": sha256_bytes(security.encode("utf-8")),
        "flash_id_output_sha256": sha256_bytes(flash_id.encode("utf-8")),
    }


def download_artifact(directory: Path) -> Path:
    if shutil.which("gh") is None:
        raise StopExecution("GH_CLI_NOT_FOUND")
    artifact_dir = directory / "artifact"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    proc = run(
        [
            "gh",
            "run",
            "download",
            BUILD_RUN_ID,
            "-R",
            REPOSITORY,
            "-n",
            ARTIFACT_NAME,
            "-D",
            str(artifact_dir),
        ],
        timeout=180,
    )
    if proc.returncode != 0:
        raise StopExecution("ARTIFACT_DOWNLOAD_FAILED")
    release = artifact_dir / RELEASE_ZIP_NAME
    sidecar = artifact_dir / (RELEASE_ZIP_NAME + ".sha256")
    if not release.is_file() or not sidecar.is_file():
        raise StopExecution("ARTIFACT_MEMBER_MISSING")
    if release.stat().st_size != RELEASE_ZIP_SIZE:
        raise StopExecution("RELEASE_ZIP_SIZE_MISMATCH")
    if sha256_file(release) != RELEASE_ZIP_SHA256:
        raise StopExecution("RELEASE_ZIP_SHA256_MISMATCH")
    if RELEASE_ZIP_SHA256 not in sidecar.read_text(encoding="utf-8", errors="strict"):
        raise StopExecution("RELEASE_SHA256_SIDECAR_MISMATCH")
    return release


def verify_and_extract_release(release: Path, directory: Path) -> Path:
    extract_dir = directory / "release"
    extract_dir.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(release, "r") as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        if names != set(EXPECTED_MEMBERS):
            raise StopExecution("RELEASE_MEMBER_SET_MISMATCH")
        for name, binding in EXPECTED_MEMBERS.items():
            data = archive.read(name)
            if binding is not None:
                size, digest = binding
                if len(data) != size or sha256_bytes(data) != digest:
                    raise StopExecution("RELEASE_MEMBER_BINDING_MISMATCH")
            destination = extract_dir / name
            destination.write_bytes(data)
            destination.chmod(0o600)
    manifest = (extract_dir / "MANIFEST.txt").read_text(encoding="utf-8", errors="strict")
    required = (
        "BINDING_SCHEMA=N3W_PRODUCTION_EXACT_ARTIFACT_V1",
        f"SOURCE_HEAD={SOURCE_HEAD}",
        f"SOURCE_TREE={SOURCE_TREE}",
        "SOURCE_REPAIR_R2=true",
        "KF050_FIRST_PAIR_BOOT_REPAIR=true",
        "CLEAN_PRODUCT_FIRST_PAIR_HANDOFF_REPAIR=true",
        "PAIRING_ID_LOG_REDACTION=true",
        f"WORKFLOW_RUN_ID={BUILD_RUN_ID}",
        "BINARY_DEHARNESS_PROOF=PASS",
        "DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS",
        "KF050_FIRST_PAIR_BOOT_REPAIR_MARKERS=PASS",
        "CLEAN_PRODUCT_FIRST_PAIR_HANDOFF_MARKERS=PASS",
        "PAIRING_ID_LOG_REDACTION_MARKERS=PASS",
        "PHASE4_HARNESS_PRESENT=false",
        "LAB_DIAGNOSTICS_PRESENT=false",
        "RTC_BREADCRUMB_PRESENT=false",
    )
    if any(item not in manifest for item in required):
        raise StopExecution("RELEASE_MANIFEST_AUTHORITY_MISMATCH")
    return extract_dir


def write_private_state(path: Path, state: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def esptool_mutation(
    port: str,
    command: list[str],
    error_code: str,
    state: dict[str, object],
    state_path: Path,
    step: str,
    *,
    timeout: int = 300,
) -> str:
    state["last_started_step"] = step
    write_private_state(state_path, state)
    output = require_command(
        esptool_base(port) + command,
        error_code,
        timeout=timeout,
    )
    state["last_completed_step"] = step
    state["last_step_output_sha256"] = sha256_bytes(output.encode("utf-8"))
    write_private_state(state_path, state)
    return output


def readback(
    port: str,
    offset: int,
    size: int,
    destination: Path,
    expected_sha: str,
    state: dict[str, object],
    state_path: Path,
    label: str,
) -> None:
    esptool_mutation(
        port,
        ["read-flash", hex(offset), hex(size), str(destination)],
        f"READBACK_{label}_COMMAND_FAILED",
        state,
        state_path,
        f"readback_{label.lower()}",
        timeout=180,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution(f"READBACK_{label}_SIZE_MISMATCH")
    if sha256_file(destination) != expected_sha:
        raise StopExecution(f"READBACK_{label}_SHA256_MISMATCH")
    state[f"readback_{label.lower()}_pass"] = True
    write_private_state(state_path, state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-dir",
        default=str(
            Path.home()
            / "N3W_PRIVATE_EVIDENCE"
            / GATE
        ),
    )
    args = parser.parse_args()

    public: dict[str, object] = {
        "STAGE": "P3_FULL_EXACT_FLASH_NO_PRODUCT_BOOT",
        "AUTHORIZATION_GRANTED": True,
        "AUTHORIZATION_CLAIMED": False,
        "AUTHORIZATION_CONSUMED": False,
        "P1_R2_CLEAN_BOARD_ELIGIBILITY": "CLOSED_PASS",
        "P2_STATUS": "CLOSED_PASS",
        "ARTIFACT_BINDING_PASS": False,
        "BOARD_PRECLAIM_PASS": False,
        "FULL_CHIP_ERASE": False,
        "FOUR_REGION_WRITE": False,
        "READBACK_VERIFY_BOOTLOADER": False,
        "READBACK_VERIFY_PARTITIONS": False,
        "READBACK_VERIFY_OTADATA": False,
        "READBACK_VERIFY_FIRMWARE": False,
        "PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED": False,
        "P3_PASS": False,
        "READY_FOR_P4": False,
        "P4_AUTHORIZATION_GRANTED": False,
        "MANAGER_RESTART": False,
        "BROKER_RESTART": False,
        "T1_MUTATION": False,
        "AUTO_P4": False,
        "STOP": True,
    }

    private_dir = Path(args.private_dir).expanduser().resolve()
    if private_dir.exists() or private_dir.is_symlink():
        public["ERROR"] = "PRIVATE_EVIDENCE_DIRECTORY_ALREADY_EXISTS"
        print(json.dumps(public, indent=2, sort_keys=True))
        return 2

    try:
        private_dir.mkdir(parents=True, mode=0o700)
        os.chmod(private_dir, 0o700)

        public["ESPTOOL_VERSION"] = verify_esptool()
        release = download_artifact(private_dir)
        extract_dir = verify_and_extract_release(release, private_dir)
        public["ARTIFACT_BINDING_PASS"] = True
        public["RELEASE_ZIP_SHA256"] = RELEASE_ZIP_SHA256
        public["ARTIFACT_ID"] = ARTIFACT_ID
        public["BUILD_RUN_ID"] = BUILD_RUN_ID

        port = ensure_single_port()
        public["SERIAL_PORT_SHA256"] = sha256_bytes(port.encode("utf-8"))
        board = fresh_board_preclaim(port, expected_silicon_sha256)
        public["SILICON_BINDING_SHA256"] = board["silicon_sha256"]\n        public["EXPECTED_SILICON_BINDING_SHA256"] = expected_silicon_sha256
        public["BOARD_PRECLAIM_PASS"] = True
        public["FLASH_SIZE"] = "8MB"
        public["SECURE_BOOT"] = False
        public["FLASH_ENCRYPTION"] = False

        state_path = private_dir / "mutation_state.private.json"
        state: dict[str, object] = {
            "gate": GATE,
            "authorization_granted": True,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "silicon_binding_sha256": board["silicon_sha256"],\n            "expected_silicon_binding_sha256": expected_silicon_sha256,
            "security_output_sha256": board["security_output_sha256"],
            "flash_id_output_sha256": board["flash_id_output_sha256"],
            "release_zip_sha256": RELEASE_ZIP_SHA256,
            "normal_product_boot_started": False,
            "after_policy": "no-reset",
            "no_stub": True,
        }
        write_private_state(state_path, state)

        public["AUTHORIZATION_CLAIMED"] = True
        public["AUTHORIZATION_CONSUMED"] = True

        esptool_mutation(
            port,
            ["erase-flash"],
            "FULL_CHIP_ERASE_FAILED",
            state,
            state_path,
            "full_chip_erase",
            timeout=300,
        )
        public["FULL_CHIP_ERASE"] = True

        erased_probe = private_dir / "post_erase_partition_probe.bin"
        esptool_mutation(
            port,
            ["read-flash", "0x8000", "0x1000", str(erased_probe)],
            "POST_ERASE_PROBE_FAILED",
            state,
            state_path,
            "post_erase_probe",
            timeout=120,
        )
        erased = erased_probe.read_bytes()
        if len(erased) != 0x1000 or any(value != 0xFF for value in erased):
            raise StopExecution("POST_ERASE_PARTITION_WINDOW_NOT_BLANK")
        state["post_erase_partition_window_blank"] = True
        write_private_state(state_path, state)

        write_command = [
            "write-flash",
            "--flash-mode",
            "dio",
            "--flash-freq",
            "80m",
            "--flash-size",
            "8MB",
        ]
        for offset, name in FLASH_LAYOUT:
            write_command += [hex(offset), str(extract_dir / name)]

        esptool_mutation(
            port,
            write_command,
            "FOUR_REGION_WRITE_FAILED",
            state,
            state_path,
            "four_region_write",
            timeout=600,
        )
        public["FOUR_REGION_WRITE"] = True

        readback_dir = private_dir / "readback"
        readback_dir.mkdir(mode=0o700)

        for offset, name in FLASH_LAYOUT:
            size, digest = EXPECTED_MEMBERS[name]
            label = {
                "bootloader.bin": "BOOTLOADER",
                "partitions.bin": "PARTITIONS",
                "ota_data_initial.bin": "OTADATA",
                "firmware.bin": "FIRMWARE",
            }[name]
            readback(
                port,
                offset,
                size,
                readback_dir / name,
                digest,
                state,
                state_path,
                label,
            )
            public[f"READBACK_VERIFY_{label}"] = True

        state["p3_pass"] = True
        state["ready_for_p4"] = True
        state["normal_product_boot_started"] = False
        write_private_state(state_path, state)

        public["P3_PASS"] = True
        public["READY_FOR_P4"] = True
        print(json.dumps(public, indent=2, sort_keys=True))
        return 0

    except StopExecution as error:
        public["ERROR"] = str(error)
        print(json.dumps(public, indent=2, sort_keys=True))
        return 2
    except Exception:
        public["ERROR"] = "UNEXPECTED_P3_EXECUTOR_FAILURE"
        print(json.dumps(public, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
