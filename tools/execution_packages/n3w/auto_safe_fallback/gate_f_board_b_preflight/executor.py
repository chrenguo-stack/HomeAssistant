from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PRODUCT_SOURCE = "b2419d17c198a85b7b50d9c1771544c2e3a0ab6b"
PRODUCT_TREE = "c138ac3efa9b23b4d083f0cb5248089fef493416"
WORKFLOW_TRIGGER_SHA = "5aac64e93380916e440eee740d0aca281999de5f"
WORKFLOW_RUN_ID = 37123365844
ARTIFACT_ID = 11273613346
ARTIFACT_NAME = "n3w-auto-safe-fallback-f1rc2-b2419d1-exact-source"
ARTIFACT_ZIP_SIZE = 4327764
ARTIFACT_ZIP_SHA256 = "57465f56362404b269f80adb21994a22ec0d1acdcc724f9a163c84b6df3eea4d"
RELEASE_BUNDLE = "n3w-auto-safe-fallback-f1rc2-b2419d1-exact-source.zip"
RELEASE_BUNDLE_SIZE = 4327212
RELEASE_BUNDLE_SHA256 = "7bf9980e50d2baa26459ca020002e8947d8038409dcb564a0101131be1799a6a"
APPLICATION_SIZE = 1408416
APPLICATION_SHA256 = "474e738068fc894b20cfe5f647a6112b66c141aa86c873d414d8ed183679e43c"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
EXPECTED_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
PREFLIGHT_MAX_AGE_SECONDS = 900
SCHEMA = "n3w.auto-safe-fallback.gate-f.boardb-preflight/1"

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


def public_identity_sha256(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC format")
    return sha256_bytes(("ghw-c6-" + compact).encode("utf-8"))


def run_capture(args: list[str], port: str | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        redacted = ["<PORT>" if port is not None and item == port else item for item in args]
        raise StopExecution(f"command failed rc={proc.returncode}: {' '.join(redacted)}")
    return output


def esptool_base() -> list[str]:
    return [sys.executable, "-m", "esptool"]


def validate_artifact(path: Path) -> None:
    if not path.is_file():
        raise StopExecution("artifact ZIP missing")
    if path.stat().st_size != ARTIFACT_ZIP_SIZE:
        raise StopExecution("artifact ZIP size mismatch")
    if sha256_file(path) != ARTIFACT_ZIP_SHA256:
        raise StopExecution("artifact ZIP SHA256 mismatch")
    with tempfile.TemporaryDirectory(prefix="n3w-gate-f-artifact-") as td:
        root = Path(td)
        with zipfile.ZipFile(path, "r") as outer:
            names = {n for n in outer.namelist() if not n.endswith("/")}
            expected = {RELEASE_BUNDLE, RELEASE_BUNDLE + ".sha256"}
            if names != expected:
                raise StopExecution("outer artifact member set mismatch")
            for name in expected:
                if Path(name).name != name:
                    raise StopExecution("unsafe outer artifact path")
                (root / name).write_bytes(outer.read(name))
        bundle = root / RELEASE_BUNDLE
        if bundle.stat().st_size != RELEASE_BUNDLE_SIZE:
            raise StopExecution("release bundle size mismatch")
        if sha256_file(bundle) != RELEASE_BUNDLE_SHA256:
            raise StopExecution("release bundle SHA256 mismatch")
        sidecar = (root / (RELEASE_BUNDLE + ".sha256")).read_text(encoding="utf-8")
        if sidecar != f"{RELEASE_BUNDLE_SHA256}  {RELEASE_BUNDLE}\n":
            raise StopExecution("release bundle sidecar mismatch")
        with zipfile.ZipFile(bundle, "r") as inner:
            names = {n for n in inner.namelist() if not n.endswith("/")}
            expected = {
                "MANIFEST.txt", "bootloader.bin", "firmware.bin", "firmware.factory.bin",
                "firmware.ota.bin", "flash_args", "ota_data_initial.bin", "partitions.bin",
            }
            if names != expected:
                raise StopExecution("inner artifact member set mismatch")
            app = inner.read("firmware.bin")
            ota = inner.read("ota_data_initial.bin")
            partitions = inner.read("partitions.bin")
            if len(app) != APPLICATION_SIZE or sha256_bytes(app) != APPLICATION_SHA256:
                raise StopExecution("firmware.bin binding mismatch")
            if len(ota) != OTADATA_SIZE or sha256_bytes(ota) != OTADATA_SHA256:
                raise StopExecution("ota_data_initial.bin binding mismatch")
            if len(partitions) != PARTITION_TABLE_SIZE or sha256_bytes(partitions) != PARTITION_TABLE_SHA256:
                raise StopExecution("partitions.bin binding mismatch")


def verify_esptool() -> str:
    output = run_capture(esptool_base() + ["version"])
    match = ESPTOOL_VERSION_RE.search(output)
    if match is None:
        raise StopExecution("unable to parse esptool version")
    major, minor, patch = map(int, match.groups())
    if major != 5:
        raise StopExecution("esptool major version must be 5")
    return f"{major}.{minor}.{patch}"


def verify_partition_table(port: str) -> str:
    with tempfile.TemporaryDirectory(prefix="n3w-gate-f-partition-") as td:
        destination = Path(td) / "partition-table.bin"
        run_capture(
            esptool_base() + [
                "--chip", "esp32c6", "--port", port, "--no-stub", "read-flash",
                hex(PARTITION_TABLE_OFFSET), hex(PARTITION_TABLE_SIZE), str(destination),
            ],
            port=port,
        )
        digest = sha256_file(destination)
        if destination.stat().st_size != PARTITION_TABLE_SIZE or digest != PARTITION_TABLE_SHA256:
            raise StopExecution("partition table binding mismatch")
        return digest


def probe_board(port: str) -> dict[str, object]:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator invalid")
    security = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "get-security-info"],
        port=port,
    )
    if "ESP32-C6" not in security.upper():
        raise StopExecution("target is not ESP32-C6")
    mac_match = MAC_RE.search(security)
    if mac_match is None:
        raise StopExecution("ROM MAC missing")
    identity = public_identity_sha256(mac_match.group(1))
    if identity != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("target is not frozen Board B")
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot disabled state not proven")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption disabled state not proven")
    flash = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "flash-id"],
        port=port,
    )
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash not proven")
    partition_sha = verify_partition_table(port)
    return {
        "hardware_id_sha256": identity,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_sha256": partition_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        validate_artifact(Path(args.artifact_zip))
        esptool_version = verify_esptool()
        board = probe_board(args.port)
        payload = {
            "schema": SCHEMA,
            "status": "PASS",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "preflight_max_age_seconds": PREFLIGHT_MAX_AGE_SECONDS,
            "esptool_version": esptool_version,
            "board": board,
            "artifact": {
                "artifact_id": ARTIFACT_ID,
                "artifact_name": ARTIFACT_NAME,
                "artifact_zip_sha256": ARTIFACT_ZIP_SHA256,
                "release_bundle_sha256": RELEASE_BUNDLE_SHA256,
                "application_sha256": APPLICATION_SHA256,
                "otadata_sha256": OTADATA_SHA256,
                "product_source": PRODUCT_SOURCE,
                "product_tree": PRODUCT_TREE,
                "workflow_run_id": WORKFLOW_RUN_ID,
                "workflow_trigger_sha": WORKFLOW_TRIGGER_SHA,
            },
            "persistent_mutation": False,
            "flash_write": False,
        }
        output = Path(args.output)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output.chmod(0o600)
        print("PREFLIGHT=PASS")
        print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
        print("CHIP=ESP32-C6")
        print("FLASH_SIZE=8MB")
        print("SECURE_BOOT=false")
        print("FLASH_ENCRYPTION=false")
        print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
        print("FLASH_WRITE=false")
        return 0
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
