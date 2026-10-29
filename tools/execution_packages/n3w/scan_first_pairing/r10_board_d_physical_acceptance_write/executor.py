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

SCHEMA_PREFLIGHT = "gh.n3w.r10-board-d-physical-acceptance-preflight/1"
SCHEMA_WRITE = "gh.n3w.r10-board-d-physical-acceptance-write/1"

PRODUCT_SOURCE = "44d3320877a0a47c3dd728182fae2f209bffbc0f"
ACCEPTANCE_SOURCE = "faf07839fcef221f9defb296eadcc7c090e12d4e"
ACCEPTANCE_TREE = "dc26f11617b721da316e7815b5330b8d8c1f3474"
WORKFLOW_HEAD = "1c7247b64191fc72a3a0f1db0b1be13ceabec0f2"
ARTIFACT_RUN_ID = 40798244418
ARTIFACT_ID = 12864962159
ARTIFACT_NAME = "n3w-r10-physical-acceptance-faf07839"
OUTER_SHA256 = "b57a5af10c23344e8e03250857455898eb60640e3e18c62022af9c2b9ab7f6da"
OUTER_SIZE = 4501387
INNER_NAME = "n3w-r10-physical-acceptance-faf07839.zip"
INNER_SIDECAR = INNER_NAME + ".sha256"
INNER_SHA256 = "91b3e47b16025ec9fdf73500e463ecc0db4121ea0dc9dcc12325e88e7e7c347b"
INNER_SIZE = 4500900
MANIFEST_SHA256 = "1aa0da0be83d461d92274fef0f37420032a05d7b3e25803ad236e3bb6883ef44"
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

SELECTED_WRITE_ROUTE = "R10_PHYSICAL_ACCEPTANCE_DUAL_SLOT_APP_ONLY"
NORMALIZED_SLOT_SHA256 = "9d3b7b9d6b277e06cb6eb7f3155e9c777025b0d5cdb6e40feec47d46435eafbd"
NORMALIZATION_TAIL_SHA256 = "07f265cc0685350b34f568eb55654c3bd55ebea6a85588721df2f5c9ac180ac7"
CURRENT_R9_SLOT_SHA256 = "6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079"
CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256 = "e88f39529dd195f7f792c4be45d435c0c205c64e5147cf31be125d9344d600ae"
PHY_ALL_FF_SHA256 = hashlib.sha256(b"\xff" * PHY_INIT_SIZE).hexdigest()

PREFLIGHT_CONFIRMATION = "R10 BOARD D PHYSICAL ACCEPTANCE PREFLIGHT: YES"
WRITE_CONFIRMATION = "N3W_R10_BOARD_D_PHYSICAL_ACCEPTANCE_WRITE_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900

EXPECTED_FLASH_ARGS = """--flash_mode dio --flash_freq 80m --flash_size 8MB
0x0 bootloader/bootloader.bin
0x10000 gh.bin
0x8000 partition_table/partition-table.bin
0x9000 ota_data_initial.bin
"""

MEMBER_BINDINGS = {
    "MANIFEST.txt": (3355, MANIFEST_SHA256),
    "bootloader.bin": (22576, "a3818092401a75580eb19a5d54ea01fed651467f54c01550988932d56ce7e9b5"),
    "firmware.bin": (1465712, "e68dcd2883500b99960b483fd06e5d16ef95557b8faedc928eb81d1b14a98eb2"),
    "firmware.factory.bin": (1531248, "a82d3d61de12008163f4b9c3f9ec964b20c0a00f31df664a130576d1a831e847"),
    "firmware.ota.bin": (1465712, "e68dcd2883500b99960b483fd06e5d16ef95557b8faedc928eb81d1b14a98eb2"),
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
    "otadata": (OTADATA_OFFSET, MEMBER_BINDINGS["ota_data_initial.bin"][0], "prewrite-otadata.bin"),
    "app0": (APP0_OFFSET, OTA_SLOT_SIZE, "prewrite-app0-full-slot.bin"),
    "app1": (APP1_OFFSET, OTA_SLOT_SIZE, "prewrite-app1-full-slot.bin"),
}
PROTECTED_LAYOUT = {
    "bootloader_erase_span": (BOOTLOADER_OFFSET, BOOTLOADER_ERASE_SPAN_SIZE, "prewrite-bootloader-erase-span.bin"),
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
        raise StopExecution("R10 acceptance firmware image is not identified as ESP32-C6")


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
        raise StopExecution("R10 acceptance application does not fit OTA slot")
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
        raise StopExecution("R10 normalized-slot binding mismatch")
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
        "acceptance_source": ACCEPTANCE_SOURCE,
        "acceptance_tree": ACCEPTANCE_TREE,
        "workflow_head": WORKFLOW_HEAD,
        "workflow_run_id": ARTIFACT_RUN_ID,
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "outer_sha256": OUTER_SHA256,
        "inner_sha256": INNER_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "physical_acceptance_only": True,
        "production_eligible": False,
        "low_battery_protection_bypassed": True,
    }

def validate_write_erase_boundaries() -> dict[str, tuple[int, int]]:
    if APP0_OFFSET + OTA_SLOT_SIZE != APP1_OFFSET:
        raise StopExecution("app0 boundary does not meet app1")
    if APP1_OFFSET + OTA_SLOT_SIZE != NVS_OFFSET:
        raise StopExecution("app1 boundary does not meet NVS")
    write_ranges = {
        "otadata": (OTADATA_OFFSET, MEMBER_BINDINGS["ota_data_initial.bin"][0]),
        "app0": (APP0_OFFSET, OTA_SLOT_SIZE),
        "app1": (APP1_OFFSET, OTA_SLOT_SIZE),
    }
    protected = {
        "bootloader": (BOOTLOADER_OFFSET, BOOTLOADER_OFFSET + BOOTLOADER_ERASE_SPAN_SIZE),
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
    with tempfile.TemporaryDirectory(prefix="n3w-r10-board-probe-") as td:
        root = Path(td)
        bootloader = root / "bootloader-erase-span.bin"
        partition = root / "partition-sector.bin"
        phy = root / "phy.bin"
        bootloader_sha = read_rom_region(port, BOOTLOADER_OFFSET, BOOTLOADER_ERASE_SPAN_SIZE, bootloader)
        partition_sector_sha = read_rom_region(port, PARTITION_TABLE_OFFSET, PARTITION_SECTOR_SIZE, partition)
        phy_sha = read_rom_region(port, PHY_INIT_OFFSET, PHY_INIT_SIZE, phy)
        partition_member_sha = sha256_bytes(partition.read_bytes()[: MEMBER_BINDINGS["partitions.bin"][0]])
        phy_all_ff = phy.read_bytes() == b"\xff" * PHY_INIT_SIZE
    if bootloader_sha != CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256:
        raise StopExecution("Board D bootloader baseline does not match frozen R9 state")
    if partition_member_sha != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("Board D partition table does not match exact acceptance partition table")
    if not phy_all_ff:
        raise StopExecution("Board D PHY disposition does not match frozen all-FF route")
    return {
        "hardware_id_sha256": identity,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": ROM_FLASH_SIZE,
        "secure_boot": False,
        "flash_encryption": False,
        "bootloader_erase_span_sha256": bootloader_sha,
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

    if backups["app0"]["sha256"] != CURRENT_R9_SLOT_SHA256:
        raise StopExecution("fresh prewrite app0 is not the frozen R9 normalized slot")
    if backups["app1"]["sha256"] != CURRENT_R9_SLOT_SHA256:
        raise StopExecution("fresh prewrite app1 is not the frozen R9 normalized slot")
    if backups["bootloader_erase_span"]["sha256"] != CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256:
        raise StopExecution("fresh prewrite bootloader baseline drifted")

    partition_bytes = paths["partition_sector"].read_bytes()
    if sha256_bytes(partition_bytes[: MEMBER_BINDINGS["partitions.bin"][0]]) != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("fresh prewrite partition table does not match exact acceptance artifact")
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
        "current_r9_app0_match": True,
        "current_r9_app1_match": True,
        "current_r9_bootloader_match": True,
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
    with tempfile.TemporaryDirectory(prefix="n3w-r10-acceptance-artifact-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        derive_normalized_slot(files["firmware.bin"], Path(td) / "r10-normalized-slot.bin")
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
        "current_r9_slot_binding_required": True,
        "bootloader_write": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "flash_write": False,
        "nvs_write": False,
    }
    preflight = evidence / "preflight.json"
    write_private_json(preflight, payload)
    print("R10_PHYSICAL_ACCEPTANCE_PREFLIGHT=PASS")
    print(f"PREFLIGHT_PATH={preflight}")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"CURRENT_BOOTLOADER_ERASE_SPAN_SHA256={board['bootloader_erase_span_sha256']}")
    print(f"NORMALIZED_SLOT_SHA256={NORMALIZED_SLOT_SHA256}")
    print("FRESH_PREWRITE_BACKUP_REQUIRED=true")
    print("BOOTLOADER_WRITE=false")
    print("FLASH_WRITE=false")
    print("NVS_WRITE=false")
    print("WRITE_AUTHORIZATION_CONSUMED=false")
    return 0

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

    with tempfile.TemporaryDirectory(prefix="n3w-r10-acceptance-write-") as td:
        temp = Path(td)
        files = validate_artifact(Path(args.artifact_zip), temp / "artifact")
        normalized_slot = derive_normalized_slot(files["firmware.bin"], temp / "r10-normalized-slot.bin")
        esptool_version = verify_esptool_version()
        verify_image(files["firmware.bin"])
        fresh = capture_prewrite_evidence(args.port, evidence_root)
        verify_backup_files(evidence_root, fresh)

        if fresh.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
            raise StopExecution("fresh prewrite target identity mismatch")
        if fresh.get("current_r9_app0_match") is not True or fresh.get("current_r9_app1_match") is not True:
            raise StopExecution("fresh prewrite R9 slot baseline mismatch")
        if fresh.get("current_r9_bootloader_match") is not True:
            raise StopExecution("fresh prewrite bootloader baseline mismatch")
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
            "bootloader_write": False,
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
    print("R10_PHYSICAL_ACCEPTANCE_WRITE=PASS")
    print(f"HARDWARE_ID_SHA256={fresh['hardware_id_sha256']}")
    print(f"BOOTLOADER_ERASE_SPAN_SHA256={result['postwrite']['bootloader_erase_span_sha256']}")
    print(f"OTADATA_SHA256={result['postwrite']['otadata_sha256']}")
    print(f"APP0_FULL_SLOT_SHA256={result['postwrite']['app0_full_slot_sha256']}")
    print(f"APP1_FULL_SLOT_SHA256={result['postwrite']['app1_full_slot_sha256']}")
    print("BOOTLOADER_UNCHANGED=true")
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
