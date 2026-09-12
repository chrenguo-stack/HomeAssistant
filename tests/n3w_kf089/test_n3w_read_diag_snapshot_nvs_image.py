import ctypes
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
UTILITY = ROOT / "tools/n3w_read_diag_snapshot.py"


def load_reader():
    spec = importlib.util.spec_from_file_location("n3w_read_diag_snapshot", UTILITY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_snapshot_v5(reader):
    snapshot = reader.SnapshotV5()
    snapshot.magic = reader.MAGIC
    snapshot.schema_version = 5
    snapshot.size = ctypes.sizeof(reader.SnapshotV5)
    snapshot.boot_session = 77
    snapshot.snapshot_uptime_ms = 90000
    snapshot.path_state = 4
    snapshot.relay_active_count = 1
    snapshot.relay_telemetry_attempts = 4
    snapshot.relay_telemetry_success = 3
    snapshot.unicast_completion_count = 4
    snapshot.unicast_completion_success = 3
    snapshot.unicast_completion_failure = 1
    snapshot.compact_rx_count = 2
    snapshot.compact_decode_success = 2
    snapshot.compact_forward_attempts = 2
    snapshot.compact_forward_submit_success = 2
    return bytes(snapshot)


def build_nvs_image(reader, payload: bytes) -> bytes:
    page = bytearray(b"\xff" * reader.PAGE_SIZE)

    def mark_written(slot: int) -> None:
        bitmap_slot = slot - 2
        bitmap_index = bitmap_slot // 4
        shift = (bitmap_slot % 4) * 2
        page[reader.ENTRY_SIZE + bitmap_index] &= ~(0x03 << shift)
        page[reader.ENTRY_SIZE + bitmap_index] |= 0x02 << shift

    def write_entry(
        slot: int,
        namespace: int,
        entry_type: int,
        key: bytes,
        *,
        span: int = 1,
        chunk_index: int = 0,
    ) -> memoryview:
        start = slot * reader.ENTRY_SIZE
        entry = memoryview(page)[start : start + reader.ENTRY_SIZE]
        entry[:] = b"\x00" * reader.ENTRY_SIZE
        entry[0] = namespace
        entry[1] = entry_type
        entry[2] = span
        entry[3] = chunk_index
        entry[8:24] = b"\x00" * 16
        entry[8 : 8 + len(key)] = key
        mark_written(slot)
        return entry

    write_entry(2, 0, 0x01, reader.NAMESPACE.encode())[24] = 1

    blob_index = write_entry(3, 1, 0x48, reader.KEY.encode())
    blob_index[24:28] = len(payload).to_bytes(4, "little")
    blob_index[28] = 1
    blob_index[29] = 1

    child_slots = (len(payload) + reader.ENTRY_SIZE - 1) // reader.ENTRY_SIZE
    blob_data = write_entry(
        4,
        1,
        0x42,
        reader.KEY.encode(),
        span=1 + child_slots,
        chunk_index=1,
    )
    blob_data[24:28] = len(payload).to_bytes(4, "little")

    remaining = payload
    for offset in range(child_slots):
        slot = 5 + offset
        start = slot * reader.ENTRY_SIZE
        chunk = remaining[: reader.ENTRY_SIZE]
        page[start : start + len(chunk)] = chunk
        if len(chunk) < reader.ENTRY_SIZE:
            page[start + len(chunk) : start + reader.ENTRY_SIZE] = b"\x00" * (
                reader.ENTRY_SIZE - len(chunk)
            )
        remaining = remaining[reader.ENTRY_SIZE :]

    return bytes(page)


def test_blob_mode_remains_exported_snapshot_value(tmp_path: Path):
    reader = load_reader()
    payload = build_snapshot_v5(reader)
    blob = tmp_path / "snapshot.bin"
    blob.write_bytes(payload)

    result = subprocess.run(
        [sys.executable, str(UTILITY), "--blob", str(blob)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    decoded = json.loads(result.stdout)
    assert decoded["schema_version"] == 5
    assert decoded["boot_session"] == 77
    assert decoded["unicast_completion_count"] == 4


def test_nvs_image_mode_extracts_snapshot_before_schema_decode(tmp_path: Path):
    reader = load_reader()
    payload = build_snapshot_v5(reader)
    image = tmp_path / "nvs_partition.bin"
    image.write_bytes(build_nvs_image(reader, payload))

    result = subprocess.run(
        [sys.executable, str(UTILITY), "--nvs-image", str(image)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    decoded = json.loads(result.stdout)
    assert decoded["schema_version"] == 5
    assert decoded["boot_session"] == 77
    assert decoded["relay_telemetry_attempts"] == 4
    assert decoded["relay_telemetry_success"] == 3
    assert decoded["unicast_completion_success"] == 3
    assert decoded["unicast_completion_failure"] == 1
