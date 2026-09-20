from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

SCHEMA_PREFLIGHT = "n3w.kf096.pr437-177468e.boardb-preflight/1"
SCHEMA_WRITE = "n3w.kf096.pr437-177468e.boardb-write/1"

PRODUCT_SOURCE_HEAD = "177468e290a207f2fb7f6c554aedf60b61373b4d"
PRODUCT_SOURCE_TREE = "a50ff98887b14b70cf9d278c6f8b7edf536eae88"
TARGET_CONFIG = "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
TARGET_BLOB_SHA = "37654481747b21ca51ccecc246bf84ca437ab7a9"

WORKFLOW_TRIGGER_SHA = "ecf549bbc470b5636d00a6e8ff916149a263d6fe"
WORKFLOW_RUN_ID = 35515601957

ARTIFACT_ID = 10607030747
ARTIFACT_NAME = "n3w-pr437-boardb-exact-source"
ARTIFACT_ZIP_SIZE = 731016
ARTIFACT_ZIP_SHA256 = "371d4369b791df527c595bc43ac203487f18a000b47ec73692d728ce58483dd8"

APPLICATION_SIZE = 1145984
APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
MANIFEST_SIZE = 575
MANIFEST_SHA256 = "6b8fa94206440ab1b44839cadc5e38608dfe4c828d1aefb8301bcf095519bd2b"

EXPECTED_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"

EXPECTED_MEMBERS = {"MANIFEST.txt", "firmware.bin", "ota_data_initial.bin"}
WRITE_CONFIRMATION = "N3W_PR437_177468E_BOARD_B_WRITE_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900

EXPECTED_MANIFEST = {
    "SOURCE_HEAD": PRODUCT_SOURCE_HEAD,
    "SOURCE_TREE": PRODUCT_SOURCE_TREE,
    "TARGET_CONFIG": TARGET_CONFIG,
    "TARGET_BLOB_SHA": TARGET_BLOB_SHA,
    "PYTHON_VERSION": "3.11",
    "ESPHOME_VERSION": "2026.4.3",
    "ESP_IDF_VERSION": "5.5.4",
    "WORKFLOW_TRIGGER_SHA": WORKFLOW_TRIGGER_SHA,
    "APPLICATION_SIZE": str(APPLICATION_SIZE),
    "OTADATA_SIZE": str(OTADATA_SIZE),
    "APPLICATION_SHA256": APPLICATION_SHA256,
    "OTADATA_SHA256": OTADATA_SHA256,
}

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


def hardware_id_from_mac(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC format")
    return "ghw-c6-" + compact


def public_identity_sha256(raw_mac: str) -> str:
    return sha256_bytes(hardware_id_from_mac(raw_mac).encode("utf-8"))


def parse_manifest(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw:
            continue
        if "=" not in raw:
            raise StopExecution("manifest contains a non key=value line")
        key, value = raw.split("=", 1)
        if not key or key in result:
            raise StopExecution("manifest contains invalid or duplicate key")
        result[key] = value
    return result


def validate_artifact(archive: Path, extract_root: Path) -> dict[str, Path]:
    if not archive.is_file():
        raise StopExecution("artifact ZIP is missing")
    if archive.stat().st_size != ARTIFACT_ZIP_SIZE:
        raise StopExecution("artifact ZIP size mismatch")
    if sha256_file(archive) != ARTIFACT_ZIP_SHA256:
        raise StopExecution("artifact ZIP SHA256 mismatch")

    with zipfile.ZipFile(archive, "r") as zf:
        members = {name for name in zf.namelist() if not name.endswith("/")}
        if members != EXPECTED_MEMBERS:
            raise StopExecution("artifact member set mismatch")
        for name in sorted(EXPECTED_MEMBERS):
            target = extract_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name, "r") as source, target.open("wb") as dest:
                dest.write(source.read())

    app = extract_root / "firmware.bin"
    ota = extract_root / "ota_data_initial.bin"
    manifest = extract_root / "MANIFEST.txt"

    if app.stat().st_size != APPLICATION_SIZE or sha256_file(app) != APPLICATION_SHA256:
        raise StopExecution("firmware.bin binding mismatch")
    if ota.stat().st_size != OTADATA_SIZE or sha256_file(ota) != OTADATA_SHA256:
        raise StopExecution("ota_data_initial.bin binding mismatch")
    if manifest.stat().st_size != MANIFEST_SIZE or sha256_file(manifest) != MANIFEST_SHA256:
        raise StopExecution("MANIFEST.txt binding mismatch")

    if parse_manifest(manifest.read_text(encoding="utf-8")) != EXPECTED_MANIFEST:
        raise StopExecution("MANIFEST.txt content binding mismatch")
    return {"application": app, "otadata": ota, "manifest": manifest}


def redacted_command(args: Iterable[str], port: str | None = None) -> str:
    return " ".join("<PORT>" if port is not None and item == port else item for item in args)


def run_capture(args: list[str], *, port: str | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise StopExecution(
            f"command failed rc={proc.returncode}: {redacted_command(args, port)}"
        )
    return output


def esptool_base() -> list[str]:
    return [sys.executable, "-m", "esptool"]


def verify_esptool_version() -> str:
    output = run_capture(esptool_base() + ["version"])
    match = ESPTOOL_VERSION_RE.search(output)
    if match is None:
        raise StopExecution("unable to parse esptool version")
    major, minor, patch = map(int, match.groups())
    if major != 5:
        raise StopExecution("esptool major version must be 5")
    return f"{major}.{minor}.{patch}"


def read_identity(port: str) -> str:
    output = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "read-mac"],
        port=port,
    )
    match = MAC_RE.search(output)
    if match is None:
        raise StopExecution("ROM MAC was not observed")
    return public_identity_sha256(match.group(1))


def verify_security(port: str) -> None:
    output = run_capture(
        esptool_base()
        + ["--chip", "esp32c6", "--port", port, "--no-stub", "get-security-info"],
        port=port,
    )
    if "ESP32-C6" not in output.upper():
        raise StopExecution("connected target is not reported as ESP32-C6")
    if SECURE_BOOT_DISABLED_RE.search(output) is None:
        raise StopExecution("Secure Boot is not proven disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(output) is None:
        raise StopExecution("Flash Encryption is not proven disabled")


def verify_flash_size(port: str) -> None:
    output = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "flash-id"],
        port=port,
    )
    if FLASH_8MB_RE.search(output) is None:
        raise StopExecution("8MB flash is not proven")


def read_flash_hash(port: str, offset: int, size: int, prefix: str) -> str:
    with tempfile.TemporaryDirectory(prefix=prefix) as td:
        destination = Path(td) / "readback.bin"
        run_capture(
            esptool_base()
            + [
                "--chip", "esp32c6", "--port", port, "--no-stub",
                "read-flash", hex(offset), hex(size), str(destination),
            ],
            port=port,
        )
        if not destination.is_file() or destination.stat().st_size != size:
            raise StopExecution("flash readback size mismatch")
        return sha256_file(destination)


def probe_board(port: str) -> dict[str, object]:
    if not port.startswith("/dev/cu.usbmodem") or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is not an allowed usbmodem path")
    if not os.path.exists(port):
        raise StopExecution("serial port does not exist")

    identity_hash = read_identity(port)
    if identity_hash != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("connected target does not match frozen Board B identity")

    verify_security(port)
    verify_flash_size(port)
    partition_sha = read_flash_hash(
        port, PARTITION_TABLE_OFFSET, PARTITION_TABLE_SIZE, "n3w-pr437-partition-"
    )
    if partition_sha != PARTITION_TABLE_SHA256:
        raise StopExecution("partition table binding mismatch")

    return {
        "hardware_id_sha256": identity_hash,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_sha256": partition_sha,
    }


def artifact_binding() -> dict[str, object]:
    return {
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "archive_sha256": ARTIFACT_ZIP_SHA256,
        "application_size": APPLICATION_SIZE,
        "application_sha256": APPLICATION_SHA256,
        "otadata_size": OTADATA_SIZE,
        "otadata_sha256": OTADATA_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "product_source_tree": PRODUCT_SOURCE_TREE,
        "target_config": TARGET_CONFIG,
        "target_blob_sha": TARGET_BLOB_SHA,
    }


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def load_preflight(path: Path, port: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StopExecution("preflight closure is unreadable") from exc

    if payload.get("schema") != SCHEMA_PREFLIGHT or payload.get("status") != "PASS":
        raise StopExecution("preflight closure is not PASS")
    if payload.get("artifact") != artifact_binding():
        raise StopExecution("preflight artifact binding drifted")
    if payload.get("automated_identity_match") is not True:
        raise StopExecution("preflight target identity was not an automated PASS")
    if payload.get("identity_override_permitted") is not False:
        raise StopExecution("preflight identity override policy is invalid")
    if payload.get("authorization_claimed") is not False:
        raise StopExecution("preflight authorization is already claimed")
    if payload.get("authorization_consumed") is not False:
        raise StopExecution("preflight authorization is already consumed")
    if payload.get("port_sha256") != sha256_bytes(port.encode("utf-8")):
        raise StopExecution("serial port locator changed since preflight")
    if payload.get("observed_hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("preflight target identity mismatch")
    if payload.get("chip") != "ESP32-C6" or payload.get("flash_size") != "8MB":
        raise StopExecution("preflight silicon/flash binding mismatch")
    if payload.get("secure_boot") is not False or payload.get("flash_encryption") is not False:
        raise StopExecution("preflight security state mismatch")
    if payload.get("partition_table_sha256") != PARTITION_TABLE_SHA256:
        raise StopExecution("preflight partition table binding mismatch")

    raw_time = payload.get("created_at")
    if not isinstance(raw_time, str):
        raise StopExecution("preflight timestamp missing")
    try:
        created = dt.datetime.fromisoformat(raw_time)
    except ValueError as exc:
        raise StopExecution("preflight timestamp invalid") from exc
    if created.tzinfo is None:
        raise StopExecution("preflight timestamp must be timezone-aware")
    age = (utc_now() - created.astimezone(dt.timezone.utc)).total_seconds()
    if age < -30 or age > PREFLIGHT_MAX_AGE_SECONDS:
        raise StopExecution("preflight is stale; rerun preflight before write")
    return payload


def claim_preflight(path: Path, port: str) -> Path:
    load_preflight(path, port)
    if path.is_symlink() or not path.is_file():
        raise StopExecution("preflight closure path is unsafe")
    claimed = path.with_name("claimed-" + path.name)
    if claimed.exists() or claimed.is_symlink():
        raise StopExecution("preflight authorization was already claimed")
    try:
        source_inode = path.stat().st_ino
        os.link(path, claimed, follow_symlinks=False)
        path.unlink()
    except OSError as exc:
        claimed.unlink(missing_ok=True)
        raise StopExecution("preflight authorization claim failed") from exc
    if path.exists() or not claimed.is_file() or claimed.is_symlink():
        raise StopExecution("preflight authorization claim verification failed")
    if claimed.stat().st_ino != source_inode:
        raise StopExecution("preflight authorization claim inode mismatch")

    payload = json.loads(claimed.read_text(encoding="utf-8"))
    payload["authorization_claimed"] = True
    payload["authorization_consumed"] = True
    payload["consumed_at"] = utc_now().isoformat()
    write_json(claimed, payload)
    return claimed


def build_write_command(port: str, ota: Path, app: Path) -> list[str]:
    return esptool_base() + [
        "--chip", "esp32c6", "--port", port, "--baud", "460800",
        "--before", "default-reset", "--after", "hard-reset",
        "write-flash",
        "0x9000", str(ota),
        "0x10000", str(app),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    if args.confirm != WRITE_CONFIRMATION:
        raise SystemExit("STOP=write confirmation token mismatch")

    output_path = Path(args.output)
    preflight_path = Path(args.preflight)

    try:
        load_preflight(preflight_path, args.port)

        with tempfile.TemporaryDirectory(prefix="n3w-pr437-177468e-write-") as td:
            files = validate_artifact(Path(args.artifact_zip), Path(td))
            esptool_version = verify_esptool_version()

            board_before = probe_board(args.port)
            claimed = claim_preflight(preflight_path, args.port)

            run_capture(
                build_write_command(args.port, files["otadata"], files["application"]),
                port=args.port,
            )

            ota_readback_sha = read_flash_hash(
                args.port, 0x9000, OTADATA_SIZE, "n3w-pr437-ota-readback-"
            )
            app_readback_sha = read_flash_hash(
                args.port, 0x10000, APPLICATION_SIZE, "n3w-pr437-app-readback-"
            )
            if ota_readback_sha != OTADATA_SHA256:
                raise StopExecution("post-write otadata readback hash mismatch")
            if app_readback_sha != APPLICATION_SHA256:
                raise StopExecution("post-write application readback hash mismatch")

        payload: dict[str, object] = {
            "schema": SCHEMA_WRITE,
            "status": "PASS",
            "created_at": utc_now().isoformat(),
            "esptool_version": esptool_version,
            "board_before": board_before,
            "artifact": artifact_binding(),
            "authorization": {
                "claimed": True,
                "consumed": True,
                "replay_permitted": False,
                "claim_file_sha256": sha256_bytes(claimed.name.encode("utf-8")),
            },
            "write_scope": {
                "otadata_offset": "0x9000",
                "application_offset": "0x10000",
                "bootloader_write": False,
                "partition_table_write": False,
                "product_nvs_write": False,
                "full_flash_erase": False,
            },
            "readback": {
                "otadata_sha256": ota_readback_sha,
                "application_sha256": app_readback_sha,
                "verified": True,
            },
        }
        write_json(output_path, payload)

        print("BOARD_B_WRITE=PASS")
        print(f"HARDWARE_ID_SHA256={board_before['hardware_id_sha256']}")
        print(f"ARTIFACT_ID={ARTIFACT_ID}")
        print(f"OTADATA_SHA256={OTADATA_SHA256}")
        print(f"APPLICATION_SHA256={APPLICATION_SHA256}")
        print("OTADATA_READBACK_VERIFY=PASS")
        print("APPLICATION_READBACK_VERIFY=PASS")
        print(f"PARTITION_TABLE_SHA256={board_before['partition_table_sha256']}")
        print("AUTHORIZATION_CLAIMED=true")
        print("AUTHORIZATION_CONSUMED=true")
        print("REPLAY_PERMITTED=false")
        print("BOOTLOADER_WRITE=false")
        print("PARTITION_TABLE_WRITE=false")
        print("PRODUCT_NVS_WRITE=false")
        print("FULL_FLASH_ERASE=false")
        print("T1_MUTATION=false")
        return 0

    except StopExecution as exc:
        write_json(
            output_path,
            {
                "schema": SCHEMA_WRITE,
                "status": "STOP",
                "created_at": utc_now().isoformat(),
                "stop_reason": str(exc),
                "artifact": artifact_binding(),
                "flash_write_result": "UNKNOWN_IF_FAILURE_OCCURRED_AFTER_WRITE_START",
                "t1_mutation": False,
            },
        )
        print(f"STOP={exc}", file=sys.stderr)
        print("T1_MUTATION=false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
