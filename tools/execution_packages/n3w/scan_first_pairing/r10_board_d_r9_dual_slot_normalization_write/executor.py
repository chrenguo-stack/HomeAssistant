from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

SCHEMA_PREFLIGHT = "gh.n3w.r10-board-d-r9-dual-slot-preflight/1"
SCHEMA_WRITE = "gh.n3w.r10-board-d-r9-dual-slot-write/1"

PRODUCT_SOURCE = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
PRODUCT_TREE = "e6e8290bdea3d9b09a70c598b4c3a9f5551540a7"
WORKFLOW_HEAD = "d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303"
ARTIFACT_RUN_ID = 40612774339
ARTIFACT_ID = 12783234959
ARTIFACT_NAME = "n3w-scan-first-pair-r9-e299c937-exact-source"
OUTER_SHA256 = "6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995"
OUTER_SIZE = 4484150
INNER_NAME = "n3w-scan-first-pair-r9-e299c937-exact-source.zip"
INNER_SIDECAR = INNER_NAME + ".sha256"
INNER_SHA256 = "b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1"
INNER_SIZE = 4483623
MANIFEST_SHA256 = "8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05"
EXPECTED_HARDWARE_ID_SHA256 = "3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5"

BOOTLOADER_OFFSET = 0x000000
PARTITION_TABLE_OFFSET = 0x008000
OTADATA_OFFSET = 0x009000
PHY_INIT_OFFSET = 0x00B000
APP0_OFFSET = 0x010000
APP1_OFFSET = 0x3D0000
NVS_OFFSET = 0x790000

FLASH_SECTOR_SIZE = 0x1000
PARTITION_SECTOR_SIZE = 0x1000
PHY_INIT_SIZE = 0x1000
NVS_SIZE = 0x70000
OTA_SLOT_SIZE = 0x3C0000
BOOTLOADER_ERASE_SPAN_SIZE = 0x6000
ROM_FLASH_SIZE = "8MB"

SELECTED_WRITE_ROUTE = "R9_DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA"
NORMALIZED_SLOT_SHA256 = "6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079"
NORMALIZATION_TAIL_SHA256 = "a77ed5023b0caeaad43d58317f864574f4d82e9ba5af0274fb8df9df7584d209"
BOOTLOADER_ERASE_SPAN_SHA256 = "e88f39529dd195f7f792c4be45d435c0c205c64e5147cf31be125d9344d600ae"
PHY_ALL_FF_SHA256 = hashlib.sha256(b"\xff" * PHY_INIT_SIZE).hexdigest()

PREFLIGHT_CONFIRMATION = "R10 BOARD D R9 DUAL SLOT PREFLIGHT: YES"
WRITE_CONFIRMATION = "N3W_R10_BOARD_D_R9_DUAL_SLOT_NORMALIZATION_WRITE_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900

EXPECTED_FLASH_ARGS = """--flash_mode dio --flash_freq 80m --flash_size 8MB
0x0 bootloader/bootloader.bin
0x10000 gh.bin
0x8000 partition_table/partition-table.bin
0x9000 ota_data_initial.bin
"""

MEMBER_BINDINGS = {
    "MANIFEST.txt": (2782, MANIFEST_SHA256),
    "bootloader.bin": (22576, "1f107afc1cbfe6ae993f450a38f41dff33e672ed8c8f69b5a2cc1a15194e7ad3"),
    "firmware.bin": (1460144, "fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be"),
    "firmware.factory.bin": (1525680, "b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf"),
    "firmware.ota.bin": (1460144, "fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be"),
    "flash_args": (167, "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713"),
    "ota_data_initial.bin": (8192, "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"),
    "partitions.bin": (3072, "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"),
}
EXPECTED_MEMBERS = set(MEMBER_BINDINGS)

MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
ESPTOOL_VERSION_RE = re.compile(r"\besptool(?:\.py)?\s+v?(\d+)\.(\d+)\.(\d+)\b", re.I)
FLASH_8MB_RE = re.compile(r"Detected flash size:\s*8\s*MB\b", re.I)
SECURE_BOOT_DISABLED_RE = re.compile(r"Secure Boot:\s*Disabled\b", re.I)
FLASH_ENCRYPTION_DISABLED_RE = re.compile(r"Flash Encryption:\s*Disabled\b", re.I)

BACKUP_LAYOUT = {
    "bootloader_erase_span": (BOOTLOADER_OFFSET, BOOTLOADER_ERASE_SPAN_SIZE, "prewrite-bootloader-erase-span.bin"),
    "otadata": (OTADATA_OFFSET, MEMBER_BINDINGS["ota_data_initial.bin"][0], "prewrite-otadata.bin"),
    "app0": (APP0_OFFSET, OTA_SLOT_SIZE, "prewrite-app0-full-slot.bin"),
    "app1": (APP1_OFFSET, OTA_SLOT_SIZE, "prewrite-app1-full-slot.bin"),
}
PROTECTED_LAYOUT = {
    "partition_sector": (PARTITION_TABLE_OFFSET, PARTITION_SECTOR_SIZE, "prewrite-partition-sector.bin"),
    "phy_init": (PHY_INIT_OFFSET, PHY_INIT_SIZE, "prewrite-phy-init.bin"),
    "nvs": (NVS_OFFSET, NVS_SIZE, "prewrite-nvs.bin"),
}


class StopExecution(RuntimeError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hardware_id_from_mac(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC format")
    return "ghw-c6-" + compact


def public_identity_sha256(raw_mac: str) -> str:
    return sha256_bytes(hardware_id_from_mac(raw_mac).encode("utf-8"))


def _redacted_command(args: Iterable[str], port: str | None = None) -> str:
    return " ".join("<PORT>" if port is not None and item == port else item for item in args)


def run_capture(args: list[str], *, port: str | None = None, timeout: int = 360) -> str:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise StopExecution("command timeout") from exc
    except OSError as exc:
        raise StopExecution("command transport error") from exc
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise StopExecution(f"command failed rc={proc.returncode}: {_redacted_command(args, port)}")
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


def verify_image(path: Path) -> None:
    output = run_capture(esptool_base() + ["--chip", "esp32c6", "image-info", str(path)])
    if "ESP32-C6" not in output.upper():
        raise StopExecution("R9 firmware image is not identified as ESP32-C6")


def verify_single_serial_target(port: str) -> None:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is empty or contains whitespace")
    candidates = sorted(glob.glob("/dev/cu.usbmodem*"))
    if candidates != [port]:
        raise StopExecution("exactly one selected /dev/cu.usbmodem target is required")


def validate_artifact(outer_path: Path, extract_root: Path) -> dict[str, Path]:
    if not outer_path.is_file() or outer_path.is_symlink():
        raise StopExecution("artifact outer ZIP missing or unsafe")
    if outer_path.stat().st_size != OUTER_SIZE or sha256_file(outer_path) != OUTER_SHA256:
        raise StopExecution("artifact outer ZIP binding mismatch")

    with zipfile.ZipFile(outer_path, "r") as outer:
        outer_files = [n for n in outer.namelist() if not n.endswith("/")]
        if outer_files != [INNER_NAME, INNER_SIDECAR]:
            raise StopExecution("artifact outer member set mismatch")
        inner_bytes = outer.read(INNER_NAME)
        sidecar = outer.read(INNER_SIDECAR).decode("utf-8")
    if len(inner_bytes) != INNER_SIZE or sha256_bytes(inner_bytes) != INNER_SHA256:
        raise StopExecution("artifact inner ZIP binding mismatch")
    if sidecar != f"{INNER_SHA256}  {INNER_NAME}\n":
        raise StopExecution("artifact sidecar mismatch")

    release = extract_root / "release"
    release.mkdir(parents=True)
    with zipfile.ZipFile(__import__("io").BytesIO(inner_bytes), "r") as inner:
        names = [n for n in inner.namelist() if not n.endswith("/")]
        if set(names) != EXPECTED_MEMBERS or len(names) != len(EXPECTED_MEMBERS):
            raise StopExecution("artifact release member set mismatch")
        for info in inner.infolist():
            if info.is_dir():
                continue
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                raise StopExecution("artifact release timestamp mismatch")
            if info.compress_type != zipfile.ZIP_STORED:
                raise StopExecution("artifact release compression mismatch")
            data = inner.read(info.filename)
            size, digest = MEMBER_BINDINGS[info.filename]
            if len(data) != size or sha256_bytes(data) != digest:
                raise StopExecution(f"artifact member mismatch: {info.filename}")
            target = release / info.filename
            target.write_bytes(data)

    manifest_path = release / "MANIFEST.txt"
    if (release / "flash_args").read_text(encoding="utf-8") != EXPECTED_FLASH_ARGS:
        raise StopExecution("artifact flash_args semantic binding mismatch")
    validate_otadata_erased(release / "ota_data_initial.bin")
    return {name: release / name for name in EXPECTED_MEMBERS}


def validate_otadata_erased(path: Path) -> None:
    data = path.read_bytes()
    if len(data) != MEMBER_BINDINGS["ota_data_initial.bin"][0] or data != b"\xff" * len(data):
        raise StopExecution("ota_data_initial.bin is not the expected all-FF state")


def derive_normalized_slot(application: Path, destination: Path) -> Path:
    size, digest = MEMBER_BINDINGS["firmware.bin"]
    if application.stat().st_size != size or sha256_file(application) != digest:
        raise StopExecution("normalized-slot source application binding mismatch")
    if size >= OTA_SLOT_SIZE:
        raise StopExecution("R9 application does not fit OTA slot")
    remaining = OTA_SLOT_SIZE - size
    with application.open("rb") as source, destination.open("wb") as target:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            target.write(chunk)
        fill = b"\xff" * (64 * 1024)
        while remaining:
            n = min(remaining, len(fill))
            target.write(fill[:n])
            remaining -= n
    if destination.stat().st_size != OTA_SLOT_SIZE or sha256_file(destination) != NORMALIZED_SLOT_SHA256:
        raise StopExecution("R9 normalized-slot binding mismatch")
    return destination


def normalized_slot_binding_payload() -> dict[str, object]:
    app_size = MEMBER_BINDINGS["firmware.bin"][0]
    return {
        "size": OTA_SLOT_SIZE,
        "sha256": NORMALIZED_SLOT_SHA256,
        "source_application_size": app_size,
        "source_application_sha256": MEMBER_BINDINGS["firmware.bin"][1],
        "tail_size": OTA_SLOT_SIZE - app_size,
        "tail_sha256": NORMALIZATION_TAIL_SHA256,
    }


def artifact_binding_payload() -> dict[str, object]:
    return {
        "product_source": PRODUCT_SOURCE,
        "product_tree": PRODUCT_TREE,
        "workflow_head": WORKFLOW_HEAD,
        "workflow_run_id": ARTIFACT_RUN_ID,
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "outer_sha256": OUTER_SHA256,
        "inner_sha256": INNER_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
    }


def validate_write_erase_boundaries() -> dict[str, tuple[int, int]]:
    if APP0_OFFSET + OTA_SLOT_SIZE != APP1_OFFSET:
        raise StopExecution("app0 boundary does not meet app1")
    if APP1_OFFSET + OTA_SLOT_SIZE != NVS_OFFSET:
        raise StopExecution("app1 boundary does not meet NVS")
    write_ranges = {
        "bootloader": (BOOTLOADER_OFFSET, MEMBER_BINDINGS["bootloader.bin"][0]),
        "otadata": (OTADATA_OFFSET, MEMBER_BINDINGS["ota_data_initial.bin"][0]),
        "app0": (APP0_OFFSET, OTA_SLOT_SIZE),
        "app1": (APP1_OFFSET, OTA_SLOT_SIZE),
    }
    protected = {
        "partition_table": (PARTITION_TABLE_OFFSET, PARTITION_TABLE_OFFSET + FLASH_SECTOR_SIZE),
        "phy_init": (PHY_INIT_OFFSET, PHY_INIT_OFFSET + PHY_INIT_SIZE),
        "nvs": (NVS_OFFSET, NVS_OFFSET + NVS_SIZE),
    }
    erased: dict[str, tuple[int, int]] = {}
    for name, (offset, size) in write_ranges.items():
        start = offset - (offset % FLASH_SECTOR_SIZE)
        end = ((offset + size + FLASH_SECTOR_SIZE - 1) // FLASH_SECTOR_SIZE) * FLASH_SECTOR_SIZE
        for protected_name, (p0, p1) in protected.items():
            if start < p1 and p0 < end:
                raise StopExecution(f"write erase range overlaps protected region: {name}->{protected_name}")
        erased[name] = (start, end)
    expected = {
        "bootloader": (0x0, 0x6000),
        "otadata": (0x9000, 0xB000),
        "app0": (0x10000, 0x3D0000),
        "app1": (0x3D0000, 0x790000),
    }
    if erased != expected:
        raise StopExecution("write erase ranges drifted")
    return erased


def private_evidence_root(path: Path, *, require_empty: bool) -> Path:
    path = path.expanduser().resolve()
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise StopExecution("evidence directory is unsafe")
        s = path.stat()
        if s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode) != 0o700:
            raise StopExecution("evidence directory must be owned and mode 0700")
        if require_empty and any(path.iterdir()):
            raise StopExecution("evidence directory must be empty")
    else:
        path.mkdir(parents=True, mode=0o700)
    return path


def require_absent(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise StopExecution(f"output already exists: {path}")


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise StopExecution("private state write made no progress")
        view = view[written:]


def _fsync_dir(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_private_json(path: Path, payload: dict[str, object]) -> None:
    require_absent(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(path.parent)


def replace_private_json(path: Path, payload: dict[str, object]) -> None:
    if path.is_symlink() or not path.is_file():
        raise StopExecution("private state file missing or unsafe")
    tmp = path.with_name(path.name + ".tmp")
    require_absent(tmp)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def observe_board_identity_security(port: str, *, before: str) -> str:
    security = run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port,
            "--before", before, "--after", "no-reset", "--no-stub",
            "get-security-info",
        ],
        port=port,
        timeout=60,
    )
    if "ESP32-C6" not in security.upper():
        raise StopExecution("connected target is not ESP32-C6")
    m = MAC_RE.search(security)
    if m is None:
        raise StopExecution("ROM MAC was not observed")
    identity = public_identity_sha256(m.group(1))
    if identity != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("connected target does not match frozen Board D identity")
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot is not proven disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption is not proven disabled")
    return identity


def verify_flash_size(port: str) -> None:
    output = run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port,
            "--before", "no-reset", "--after", "no-reset", "--no-stub",
            "flash-id",
        ],
        port=port,
        timeout=60,
    )
    if FLASH_8MB_RE.search(output) is None:
        raise StopExecution("8MB flash is not proven")


def read_rom_region(port: str, offset: int, size: int, destination: Path) -> str:
    run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port,
            "--before", "no-reset", "--after", "no-reset", "--no-stub",
            "read-flash", "--flash-size", ROM_FLASH_SIZE,
            hex(offset), hex(size), str(destination),
        ],
        port=port,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash readback size mismatch")
    destination.chmod(0o600)
    return sha256_file(destination)


def read_stub_start(port: str, offset: int, size: int, destination: Path) -> str:
    run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port, "--baud", "460800",
            "--before", "no-reset", "--after", "no-reset-stub",
            "read-flash", hex(offset), hex(size), str(destination),
        ],
        port=port,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash readback size mismatch")
    destination.chmod(0o600)
    return sha256_file(destination)


def read_stub_continue(port: str, offset: int, size: int, destination: Path) -> str:
    run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port, "--baud", "460800",
            "--before", "no-reset-no-sync", "--after", "no-reset-stub",
            "read-flash", hex(offset), hex(size), str(destination),
        ],
        port=port,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash readback size mismatch")
    destination.chmod(0o600)
    return sha256_file(destination)


def probe_board_readonly(port: str) -> dict[str, object]:
    verify_single_serial_target(port)
    identity = observe_board_identity_security(port, before="default-reset")
    verify_flash_size(port)
    with tempfile.TemporaryDirectory(prefix="n3w-r9-board-probe-") as td:
        root = Path(td)
        partition = root / "partition-sector.bin"
        phy = root / "phy.bin"
        partition_sector_sha = read_rom_region(port, PARTITION_TABLE_OFFSET, PARTITION_SECTOR_SIZE, partition)
        phy_sha = read_rom_region(port, PHY_INIT_OFFSET, PHY_INIT_SIZE, phy)
        partition_member_sha = sha256_bytes(partition.read_bytes()[: MEMBER_BINDINGS["partitions.bin"][0]])
        phy_all_ff = phy.read_bytes() == b"\xff" * PHY_INIT_SIZE
    if partition_member_sha != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("Board D partition table does not match exact R9 partition table")
    if not phy_all_ff:
        raise StopExecution("Board D PHY disposition does not match frozen all-FF route")
    return {
        "hardware_id_sha256": identity,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": ROM_FLASH_SIZE,
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_sha256": partition_member_sha,
        "partition_sector_sha256": partition_sector_sha,
        "phy_init_sha256": phy_sha,
        "phy_all_ff": True,
    }


def capture_prewrite_evidence(port: str, root: Path) -> dict[str, object]:
    verify_single_serial_target(port)
    identity = observe_board_identity_security(port, before="default-reset")
    verify_flash_size(port)

    paths: dict[str, Path] = {}
    for name, (_, _, filename) in {**BACKUP_LAYOUT, **PROTECTED_LAYOUT}.items():
        path = root / filename
        require_absent(path)
        paths[name] = path

    backups: dict[str, dict[str, object]] = {}
    ordered = list(BACKUP_LAYOUT.items()) + list(PROTECTED_LAYOUT.items())
    for idx, (name, (offset, size, filename)) in enumerate(ordered):
        path = paths[name]
        digest = (
            read_stub_start(port, offset, size, path)
            if idx == 0
            else read_stub_continue(port, offset, size, path)
        )
        backups[name] = {
            "offset": hex(offset),
            "size": size,
            "sha256": digest,
            "file": filename,
        }

    partition_bytes = paths["partition_sector"].read_bytes()
    if sha256_bytes(partition_bytes[: MEMBER_BINDINGS["partitions.bin"][0]]) != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("fresh prewrite partition table does not match exact R9")
    if paths["phy_init"].read_bytes() != b"\xff" * PHY_INIT_SIZE:
        raise StopExecution("fresh prewrite PHY is not all-FF")

    return {
        "captured_at": utc_now().isoformat(),
        "hardware_id_sha256": identity,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": ROM_FLASH_SIZE,
        "secure_boot": False,
        "flash_encryption": False,
        "backups": {k: backups[k] for k in BACKUP_LAYOUT},
        "protected": {k: backups[k] for k in PROTECTED_LAYOUT},
        "partition_table_sha256": MEMBER_BINDINGS["partitions.bin"][1],
        "phy_all_ff": True,
    }


def verify_backup_files(root: Path, evidence: dict[str, object]) -> None:
    for section in ("backups", "protected"):
        records = evidence.get(section)
        if not isinstance(records, dict):
            raise StopExecution(f"fresh prewrite {section} missing")
        expected_layout = BACKUP_LAYOUT if section == "backups" else PROTECTED_LAYOUT
        if set(records) != set(expected_layout):
            raise StopExecution(f"fresh prewrite {section} set mismatch")
        for name, (offset, size, filename) in expected_layout.items():
            record = records.get(name)
            if not isinstance(record, dict):
                raise StopExecution(f"fresh prewrite record missing: {name}")
            path = root / filename
            if path.is_symlink() or not path.is_file():
                raise StopExecution(f"fresh prewrite backup unsafe: {name}")
            s = path.stat()
            if stat.S_IMODE(s.st_mode) != 0o600 or s.st_uid != os.geteuid():
                raise StopExecution(f"fresh prewrite backup permissions invalid: {name}")
            if s.st_size != size or sha256_file(path) != record.get("sha256"):
                raise StopExecution(f"fresh prewrite backup drifted: {name}")
            if record.get("offset") != hex(offset) or record.get("size") != size or record.get("file") != filename:
                raise StopExecution(f"fresh prewrite backup binding mismatch: {name}")


def run_preflight(args: argparse.Namespace) -> int:
    if args.confirm != PREFLIGHT_CONFIRMATION:
        raise StopExecution("preflight confirmation token mismatch")
    evidence = private_evidence_root(Path(args.evidence_dir), require_empty=True)
    with tempfile.TemporaryDirectory(prefix="n3w-r9-artifact-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        derive_normalized_slot(files["firmware.bin"], Path(td) / "r9-normalized-slot.bin")
        esptool_version = verify_esptool_version()
        verify_image(files["firmware.bin"])
        board = probe_board_readonly(args.port)
    payload: dict[str, object] = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "artifact": artifact_binding_payload(),
        "selected_write_route": SELECTED_WRITE_ROUTE,
        "normalized_slot": normalized_slot_binding_payload(),
        "erase_ranges": {name: [hex(a), hex(b)] for name, (a, b) in validate_write_erase_boundaries().items()},
        "fresh_prewrite_backup_required": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "flash_write": False,
        "nvs_write": False,
    }
    preflight = evidence / "preflight.json"
    write_private_json(preflight, payload)
    print("R9_DUAL_SLOT_PREFLIGHT=PASS")
    print(f"PREFLIGHT_PATH={preflight}")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"NORMALIZED_SLOT_SHA256={NORMALIZED_SLOT_SHA256}")
    print("FRESH_PREWRITE_BACKUP_REQUIRED=true")
    print("FLASH_WRITE=false")
    print("NVS_WRITE=false")
    print("WRITE_AUTHORIZATION_CONSUMED=false")
    return 0


def load_preflight(path: Path, port: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise StopExecution("preflight closure missing or unsafe")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StopExecution("preflight closure unreadable") from exc
    if payload.get("schema") != SCHEMA_PREFLIGHT or payload.get("status") != "PASS":
        raise StopExecution("preflight closure is not PASS")
    if payload.get("artifact") != artifact_binding_payload():
        raise StopExecution("preflight artifact binding drifted")
    if payload.get("selected_write_route") != SELECTED_WRITE_ROUTE:
        raise StopExecution("preflight write route mismatch")
    if payload.get("normalized_slot") != normalized_slot_binding_payload():
        raise StopExecution("preflight normalized-slot binding mismatch")
    expected_ranges = {name: [hex(a), hex(b)] for name, (a, b) in validate_write_erase_boundaries().items()}
    if payload.get("erase_ranges") != expected_ranges:
        raise StopExecution("preflight erase-range binding mismatch")
    if payload.get("fresh_prewrite_backup_required") is not True:
        raise StopExecution("preflight backup contract missing")
    if payload.get("authorization_claimed") is not False or payload.get("authorization_consumed") is not False:
        raise StopExecution("preflight authorization already claimed/consumed")
    if payload.get("replay_permitted") is not False:
        raise StopExecution("preflight replay policy invalid")
    if payload.get("flash_write") is not False or payload.get("nvs_write") is not False:
        raise StopExecution("preflight mutation state invalid")
    board = payload.get("board")
    if not isinstance(board, dict):
        raise StopExecution("preflight board binding missing")
    if board.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("preflight target identity mismatch")
    if board.get("port_sha256") != sha256_bytes(port.encode("utf-8")):
        raise StopExecution("preflight serial locator changed")
    if board.get("partition_table_sha256") != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("preflight partition binding mismatch")
    if board.get("phy_all_ff") is not True:
        raise StopExecution("preflight PHY disposition mismatch")
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
        raise StopExecution("preflight is stale")
    return payload


def claim_preflight(path: Path, payload: dict[str, object], fresh: dict[str, object]) -> tuple[Path, dict[str, object]]:
    if path.is_symlink() or not path.is_file():
        raise StopExecution("preflight closure path unsafe")
    claimed = path.with_name("claimed-preflight.json")
    require_absent(claimed)
    source_inode = path.stat().st_ino
    try:
        os.link(path, claimed, follow_symlinks=False)
        _fsync_dir(path.parent)
        path.unlink()
        _fsync_dir(path.parent)
    except OSError as exc:
        claimed.unlink(missing_ok=True)
        _fsync_dir(path.parent)
        raise StopExecution("preflight authorization claim failed") from exc
    if path.exists() or claimed.is_symlink() or not claimed.is_file() or claimed.stat().st_ino != source_inode:
        raise StopExecution("preflight authorization claim verification failed")
    now = utc_now().isoformat()
    payload = dict(payload)
    payload["authorization_claimed"] = True
    payload["authorization_consumed"] = True
    payload["replay_permitted"] = False
    payload["consumed_at"] = now
    payload["fresh_prewrite"] = fresh
    payload["execution_state"] = {
        "write_started": False,
        "write_flash_returned_success": False,
        "postwrite_integrity_pass": False,
        "postwrite_identity_pass": False,
        "rollback_attempted": False,
        "rollback_pass": False,
    }
    replace_private_json(claimed, payload)
    return claimed, payload


def persist_claimed_state(claimed: Path, payload: dict[str, object], **updates: object) -> None:
    state = payload.get("execution_state")
    if not isinstance(state, dict):
        raise StopExecution("claimed execution state missing")
    state.update(updates)
    payload["execution_state_updated_at"] = utc_now().isoformat()
    replace_private_json(claimed, payload)


def build_write_command(port: str, files: dict[str, Path], normalized_slot: Path) -> list[str]:
    return esptool_base() + [
        "--chip", "esp32c6", "--port", port, "--baud", "460800",
        "--before", "no-reset", "--after", "no-reset-stub",
        "write-flash",
        "--flash-mode", "keep",
        "--flash-freq", "keep",
        "--flash-size", "keep",
        hex(BOOTLOADER_OFFSET), str(files["bootloader.bin"]),
        hex(OTADATA_OFFSET), str(files["ota_data_initial.bin"]),
        hex(APP0_OFFSET), str(normalized_slot),
        hex(APP1_OFFSET), str(normalized_slot),
    ]


def build_restore_command(port: str, evidence_root: Path) -> list[str]:
    return esptool_base() + [
        "--chip", "esp32c6", "--port", port, "--baud", "460800",
        "--before", "no-reset-no-sync", "--after", "no-reset-stub",
        "write-flash",
        "--flash-mode", "keep",
        "--flash-freq", "keep",
        "--flash-size", "keep",
        hex(BOOTLOADER_OFFSET), str(evidence_root / BACKUP_LAYOUT["bootloader_erase_span"][2]),
        hex(OTADATA_OFFSET), str(evidence_root / BACKUP_LAYOUT["otadata"][2]),
        hex(APP0_OFFSET), str(evidence_root / BACKUP_LAYOUT["app0"][2]),
        hex(APP1_OFFSET), str(evidence_root / BACKUP_LAYOUT["app1"][2]),
    ]


def _postwrite_read(port: str, offset: int, size: int, destination: Path, *, first: bool) -> str:
    return (
        read_stub_start(port, offset, size, destination)
        if first
        else read_stub_continue(port, offset, size, destination)
    )


def verify_postwrite_integrity(
    port: str,
    root: Path,
    *,
    prewrite: dict[str, object],
) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    protected = prewrite["protected"]
    assert isinstance(protected, dict)
    expected_partition_sector = protected["partition_sector"]["sha256"]
    expected_phy = protected["phy_init"]["sha256"]
    expected_nvs = protected["nvs"]["sha256"]

    checks = [
        ("bootloader_erase_span", BOOTLOADER_OFFSET, BOOTLOADER_ERASE_SPAN_SIZE, BOOTLOADER_ERASE_SPAN_SHA256),
        ("otadata", OTADATA_OFFSET, MEMBER_BINDINGS["ota_data_initial.bin"][0], MEMBER_BINDINGS["ota_data_initial.bin"][1]),
        ("app0_full_slot", APP0_OFFSET, OTA_SLOT_SIZE, NORMALIZED_SLOT_SHA256),
        ("app1_full_slot", APP1_OFFSET, OTA_SLOT_SIZE, NORMALIZED_SLOT_SHA256),
        ("partition_sector", PARTITION_TABLE_OFFSET, PARTITION_SECTOR_SIZE, expected_partition_sector),
        ("phy_init", PHY_INIT_OFFSET, PHY_INIT_SIZE, expected_phy),
        ("nvs", NVS_OFFSET, NVS_SIZE, expected_nvs),
    ]
    out: dict[str, object] = {}
    for idx, (name, offset, size, expected) in enumerate(checks):
        actual = _postwrite_read(port, offset, size, root / f"{name}.bin", first=(idx == 0))
        if actual != expected:
            raise StopExecution(f"post-write {name} SHA256 mismatch")
        out[name + "_sha256"] = actual
        out[name + "_match"] = True

    part = (root / "partition_sector.bin").read_bytes()
    if sha256_bytes(part[: MEMBER_BINDINGS["partitions.bin"][0]]) != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("post-write partition table exact member mismatch")
    app_size = MEMBER_BINDINGS["firmware.bin"][0]
    tail = b"\xff" * (OTA_SLOT_SIZE - app_size)
    for name in ("app0_full_slot", "app1_full_slot"):
        data = (root / f"{name}.bin").read_bytes()
        if data[app_size:] != tail:
            raise StopExecution(f"post-write {name} tail is not all-FF")
    out["app0_tail_erased"] = True
    out["app1_tail_erased"] = True
    out["old_application_code_remains"] = False
    out["partition_unchanged"] = True
    out["phy_init_unchanged"] = True
    out["nvs_unchanged"] = True
    return out


def verify_restore(port: str, evidence_root: Path, prewrite: dict[str, object], verify_root: Path) -> None:
    verify_root.mkdir(parents=True, exist_ok=True)
    records: list[tuple[str, int, int, str]] = []
    for name, (offset, size, _) in BACKUP_LAYOUT.items():
        records.append((name, offset, size, prewrite["backups"][name]["sha256"]))
    for name, (offset, size, _) in PROTECTED_LAYOUT.items():
        records.append((name, offset, size, prewrite["protected"][name]["sha256"]))
    for idx, (name, offset, size, expected) in enumerate(records):
        actual = _postwrite_read(port, offset, size, verify_root / f"{name}.bin", first=(idx == 0))
        if actual != expected:
            raise StopExecution(f"rollback verification mismatch: {name}")
    identity = observe_board_identity_security(port, before="default-reset")
    if identity != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("rollback identity continuity mismatch")


def attempt_rollback(
    port: str,
    evidence_root: Path,
    prewrite: dict[str, object],
    claimed: Path,
    payload: dict[str, object],
) -> bool:
    try:
        persist_claimed_state(claimed, payload, rollback_attempted=True, rollback_pass=False)
        verify_backup_files(evidence_root, prewrite)
        run_capture(build_restore_command(port, evidence_root), port=port)
        verify_restore(port, evidence_root, prewrite, evidence_root / "rollback-readback")
        persist_claimed_state(claimed, payload, rollback_attempted=True, rollback_pass=True)
        return True
    except Exception as exc:
        try:
            persist_claimed_state(
                claimed,
                payload,
                rollback_attempted=True,
                rollback_pass=False,
                rollback_error_type=type(exc).__name__,
            )
        except Exception:
            pass
        return False


def run_write(args: argparse.Namespace) -> int:
    if args.confirm != WRITE_CONFIRMATION:
        raise StopExecution("write confirmation token mismatch")

    preflight_path = Path(args.preflight).expanduser().resolve()
    payload = load_preflight(preflight_path, args.port)
    evidence_root = private_evidence_root(preflight_path.parent, require_empty=False)
    output = Path(args.output).expanduser().resolve()
    require_absent(output)
    if output.parent != evidence_root:
        raise StopExecution("write output must stay inside private evidence directory")

    with tempfile.TemporaryDirectory(prefix="n3w-r9-write-") as td:
        temp = Path(td)
        files = validate_artifact(Path(args.artifact_zip), temp / "artifact")
        normalized_slot = derive_normalized_slot(files["firmware.bin"], temp / "r9-normalized-slot.bin")
        esptool_version = verify_esptool_version()
        verify_image(files["firmware.bin"])
        fresh = capture_prewrite_evidence(args.port, evidence_root)
        verify_backup_files(evidence_root, fresh)

        if fresh.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
            raise StopExecution("fresh prewrite target identity mismatch")
        if fresh.get("partition_table_sha256") != MEMBER_BINDINGS["partitions.bin"][1]:
            raise StopExecution("fresh prewrite partition mismatch")
        if fresh.get("phy_all_ff") is not True:
            raise StopExecution("fresh prewrite PHY mismatch")

        claimed, claimed_payload = claim_preflight(preflight_path, payload, fresh)
        command = build_write_command(args.port, files, normalized_slot)

        persist_claimed_state(claimed, claimed_payload, write_started=True)
        try:
            run_capture(command, port=args.port)
            persist_claimed_state(claimed, claimed_payload, write_flash_returned_success=True)
            postwrite = verify_postwrite_integrity(
                args.port,
                evidence_root / "postwrite-readback",
                prewrite=fresh,
            )
            claimed_payload["postwrite"] = postwrite
            persist_claimed_state(claimed, claimed_payload, postwrite_integrity_pass=True)
            identity = observe_board_identity_security(args.port, before="default-reset")
            if identity != EXPECTED_HARDWARE_ID_SHA256:
                raise StopExecution("post-write Board D identity mismatch")
            postwrite["hardware_id_sha256"] = identity
            postwrite["hardware_id_match"] = True
            persist_claimed_state(claimed, claimed_payload, postwrite_identity_pass=True)
        except Exception as exc:
            rollback_ok = attempt_rollback(args.port, evidence_root, fresh, claimed, claimed_payload)
            if rollback_ok:
                raise StopExecution(f"write/postwrite failed; rollback PASS; original={type(exc).__name__}") from exc
            raise StopExecution(f"write/postwrite failed; ROLLBACK_INCOMPLETE; original={type(exc).__name__}") from exc

    result: dict[str, object] = {
        "schema": SCHEMA_WRITE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "artifact": artifact_binding_payload(),
        "normalized_slot": normalized_slot_binding_payload(),
        "authorization": {
            "label": WRITE_CONFIRMATION,
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        },
        "fresh_prewrite": fresh,
        "execution_state": claimed_payload["execution_state"],
        "write_scope": {
            "selected_write_route": SELECTED_WRITE_ROUTE,
            "bootloader_offset": hex(BOOTLOADER_OFFSET),
            "otadata_offset": hex(OTADATA_OFFSET),
            "app0_offset": hex(APP0_OFFSET),
            "app1_offset": hex(APP1_OFFSET),
            "ota_slot_size": OTA_SLOT_SIZE,
            "partition_table_write": False,
            "phy_init_write": False,
            "nvs_write": False,
            "factory_image_direct_write": False,
            "raw_flash_args_direct_execution": False,
            "full_flash_erase": False,
            "erase_region_command_used": False,
            "manual_reset_allowed_after_claim": False,
        },
        "postwrite": claimed_payload["postwrite"],
    }
    write_private_json(output, result)
    print("R9_DUAL_SLOT_WRITE=PASS")
    print(f"HARDWARE_ID_SHA256={fresh['hardware_id_sha256']}")
    print(f"BOOTLOADER_ERASE_SPAN_SHA256={result['postwrite']['bootloader_erase_span_sha256']}")
    print(f"OTADATA_SHA256={result['postwrite']['otadata_sha256']}")
    print(f"APP0_FULL_SLOT_SHA256={result['postwrite']['app0_full_slot_sha256']}")
    print(f"APP1_FULL_SLOT_SHA256={result['postwrite']['app1_full_slot_sha256']}")
    print("PARTITION_UNCHANGED=true")
    print("PHY_INIT_UNCHANGED=true")
    print("NVS_UNCHANGED=true")
    print("OLD_APPLICATION_CODE_REMAINS=false")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_PERMITTED=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--port", required=True)
    pre.add_argument("--artifact-zip", required=True)
    pre.add_argument("--evidence-dir", required=True)
    pre.add_argument("--confirm", required=True)
    pre.set_defaults(func=run_preflight)

    write = sub.add_parser("write")
    write.add_argument("--port", required=True)
    write.add_argument("--artifact-zip", required=True)
    write.add_argument("--preflight", required=True)
    write.add_argument("--output", required=True)
    write.add_argument("--confirm", required=True)
    write.set_defaults(func=run_write)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
