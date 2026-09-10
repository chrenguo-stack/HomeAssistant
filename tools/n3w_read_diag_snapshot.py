#!/usr/bin/env python3
"""Read only the Phase 4 gh_n3w_diag/snapshot blob.

With ``--blob`` the input is an already-exported value blob.  With ``--port``
the utility invokes esptool's read-flash operation against the NVS partition,
with reset suppression, then extracts only the diagnostic namespace/key into a
0600 temporary file.  It never writes or erases flash.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import tempfile
from pathlib import Path


MAGIC = 0x4E335744
SCHEMA_VERSION = 3
NAMESPACE = "gh_n3w_diag"
KEY = "snapshot"
PAGE_SIZE = 4096
ENTRY_SIZE = 32
NVS_READ_COMMAND = "read-flash"


class SnapshotV3(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("schema_version", ctypes.c_uint16),
        ("size", ctypes.c_uint16),
        ("boot_session", ctypes.c_uint64),
        ("snapshot_uptime_ms", ctypes.c_uint64),
        ("runtime_start_mode", ctypes.c_uint8),
        ("path_state", ctypes.c_uint8),
        ("current_channel", ctypes.c_uint8),
        ("direct_channel_hint", ctypes.c_uint8),
        ("last_requested_channel", ctypes.c_uint8),
        ("last_observed_channel", ctypes.c_uint8),
        ("reserved", ctypes.c_uint8 * 1),
        ("scan_attempts", ctypes.c_uint32),
        ("scan_successes", ctypes.c_uint32),
        ("scan_failures", ctypes.c_uint32),
        ("channel_set_attempts", ctypes.c_uint32),
        ("channel_set_successes", ctypes.c_uint32),
        ("channel_set_failures", ctypes.c_uint32),
        ("channel_attempts", ctypes.c_uint32 * 3),
        ("channel_successes", ctypes.c_uint32 * 3),
        ("channel_failures", ctypes.c_uint32 * 3),
        ("last_driver_error_raw", ctypes.c_int32),
        ("discovery_rx", ctypes.c_uint32),
        ("discovery_rejected", ctypes.c_uint32),
        ("challenge_tx", ctypes.c_uint32),
        ("challenge_tx_success", ctypes.c_uint32),
        ("challenge_rx", ctypes.c_uint32),
        ("challenge_verify", ctypes.c_uint32),
        ("accept_tx", ctypes.c_uint32),
        ("accept_tx_success", ctypes.c_uint32),
        ("accept_rx", ctypes.c_uint32),
        ("accept_verify", ctypes.c_uint32),
        ("peer_install_attempts", ctypes.c_uint32),
        ("peer_install_success", ctypes.c_uint32),
        ("relay_active_count", ctypes.c_uint32),
        ("relay_telemetry_attempts", ctypes.c_uint32),
        ("relay_telemetry_success", ctypes.c_uint32),
        ("rx_dropped", ctypes.c_uint32),
        ("relay_advertisement_attempts", ctypes.c_uint32),
        ("relay_advertisement_submit_success", ctypes.c_uint32),
        ("relay_advertisement_submit_failure", ctypes.c_uint32),
        ("broadcast_completion_count", ctypes.c_uint32),
        ("broadcast_completion_success", ctypes.c_uint32),
        ("broadcast_completion_failure", ctypes.c_uint32),
    ]


class SnapshotV4(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = SnapshotV3._fields_ + [
        ("discovery_reject_state", ctypes.c_uint32),
        ("discovery_reject_pending", ctypes.c_uint32),
        ("discovery_reject_packet_invalid", ctypes.c_uint32),
        ("discovery_reject_trust_generation", ctypes.c_uint32),
        ("discovery_reject_self", ctypes.c_uint32),
        ("discovery_reject_channel_mismatch", ctypes.c_uint32),
        ("last_discovery_rejection_reason", ctypes.c_uint8),
        ("last_discovery_packet_channel", ctypes.c_uint8),
        ("last_discovery_rx_channel", ctypes.c_uint8),
    ]


class SnapshotV5(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = SnapshotV4._fields_ + [
        ("unicast_completion_count", ctypes.c_uint32),
        ("unicast_completion_success", ctypes.c_uint32),
        ("unicast_completion_failure", ctypes.c_uint32),
        ("compact_rx_count", ctypes.c_uint32),
        ("compact_state_reject_count", ctypes.c_uint32),
        ("compact_child_binding_failure", ctypes.c_uint32),
        ("compact_decode_success", ctypes.c_uint32),
        ("compact_decode_failure", ctypes.c_uint32),
        ("compact_wrap_failure", ctypes.c_uint32),
        ("compact_forward_attempts", ctypes.c_uint32),
        ("compact_forward_submit_success", ctypes.c_uint32),
        ("compact_forward_submit_failure", ctypes.c_uint32),
    ]


# Preserve the historical import name for callers that only need schema v3.
Snapshot = SnapshotV3


def _values(snapshot: Snapshot) -> dict[str, object]:
    values = {
        "schema_version": snapshot.schema_version,
        "boot_session": snapshot.boot_session,
        "snapshot_uptime_ms": snapshot.snapshot_uptime_ms,
        "runtime_start_mode": snapshot.runtime_start_mode,
        "path_state": snapshot.path_state,
        "current_channel": snapshot.current_channel,
        "direct_channel_hint": snapshot.direct_channel_hint,
        "last_requested_channel": snapshot.last_requested_channel,
        "last_observed_channel": snapshot.last_observed_channel,
        "scan_attempts": snapshot.scan_attempts,
        "scan_successes": snapshot.scan_successes,
        "scan_failures": snapshot.scan_failures,
        "channel_set_attempts": snapshot.channel_set_attempts,
        "channel_set_successes": snapshot.channel_set_successes,
        "channel_set_failures": snapshot.channel_set_failures,
        "channel_attempts": list(snapshot.channel_attempts),
        "channel_successes": list(snapshot.channel_successes),
        "channel_failures": list(snapshot.channel_failures),
        "last_driver_error_raw": snapshot.last_driver_error_raw,
        "discovery_rx": snapshot.discovery_rx,
        "discovery_rejected": snapshot.discovery_rejected,
        "challenge_tx": snapshot.challenge_tx,
        "challenge_tx_success": snapshot.challenge_tx_success,
        "challenge_rx": snapshot.challenge_rx,
        "challenge_verify": snapshot.challenge_verify,
        "accept_tx": snapshot.accept_tx,
        "accept_tx_success": snapshot.accept_tx_success,
        "accept_rx": snapshot.accept_rx,
        "accept_verify": snapshot.accept_verify,
        "peer_install_attempts": snapshot.peer_install_attempts,
        "peer_install_success": snapshot.peer_install_success,
        "relay_active_count": snapshot.relay_active_count,
        "relay_telemetry_attempts": snapshot.relay_telemetry_attempts,
        "relay_telemetry_success": snapshot.relay_telemetry_success,
        "rx_dropped": snapshot.rx_dropped,
        "relay_advertisement_attempts": snapshot.relay_advertisement_attempts,
        "relay_advertisement_submit_success": snapshot.relay_advertisement_submit_success,
        "relay_advertisement_submit_failure": snapshot.relay_advertisement_submit_failure,
        "broadcast_completion_count": snapshot.broadcast_completion_count,
        "broadcast_completion_success": snapshot.broadcast_completion_success,
        "broadcast_completion_failure": snapshot.broadcast_completion_failure,
    }
    if isinstance(snapshot, SnapshotV5):
        values.update(
            {
                "discovery_rejection_reason_supported": True,
                "discovery_reject_state": snapshot.discovery_reject_state,
                "discovery_reject_pending": snapshot.discovery_reject_pending,
                "discovery_reject_packet_invalid": snapshot.discovery_reject_packet_invalid,
                "discovery_reject_trust_generation": snapshot.discovery_reject_trust_generation,
                "discovery_reject_self": snapshot.discovery_reject_self,
                "discovery_reject_channel_mismatch": snapshot.discovery_reject_channel_mismatch,
                "last_discovery_rejection_reason": snapshot.last_discovery_rejection_reason,
                "last_discovery_packet_channel": snapshot.last_discovery_packet_channel,
                "last_discovery_rx_channel": snapshot.last_discovery_rx_channel,
                "unicast_completion_count": snapshot.unicast_completion_count,
                "unicast_completion_success": snapshot.unicast_completion_success,
                "unicast_completion_failure": snapshot.unicast_completion_failure,
                "compact_rx_count": snapshot.compact_rx_count,
                "compact_state_reject_count": snapshot.compact_state_reject_count,
                "compact_child_binding_failure": snapshot.compact_child_binding_failure,
                "compact_decode_success": snapshot.compact_decode_success,
                "compact_decode_failure": snapshot.compact_decode_failure,
                "compact_wrap_failure": snapshot.compact_wrap_failure,
                "compact_forward_attempts": snapshot.compact_forward_attempts,
                "compact_forward_submit_success": snapshot.compact_forward_submit_success,
                "compact_forward_submit_failure": snapshot.compact_forward_submit_failure,
            }
        )
    elif isinstance(snapshot, SnapshotV4):
        values.update(
            {
                "discovery_rejection_reason_supported": True,
                "discovery_reject_state": snapshot.discovery_reject_state,
                "discovery_reject_pending": snapshot.discovery_reject_pending,
                "discovery_reject_packet_invalid": snapshot.discovery_reject_packet_invalid,
                "discovery_reject_trust_generation": snapshot.discovery_reject_trust_generation,
                "discovery_reject_self": snapshot.discovery_reject_self,
                "discovery_reject_channel_mismatch": snapshot.discovery_reject_channel_mismatch,
                "last_discovery_rejection_reason": snapshot.last_discovery_rejection_reason,
                "last_discovery_packet_channel": snapshot.last_discovery_packet_channel,
                "last_discovery_rx_channel": snapshot.last_discovery_rx_channel,
            }
        )
    else:
        values["discovery_rejection_reason_supported"] = False
    return values


def _decode_key(raw: bytes) -> str:
    return raw.rstrip(b"\x00").decode("ascii")


def _extract_snapshot_from_nvs(raw: bytes) -> bytes:
    if len(raw) == 0 or len(raw) % PAGE_SIZE != 0:
        raise ValueError("NVS image size must be a non-zero multiple of 4096")

    namespace_indexes: dict[str, int] = {}
    blob_indexes: list[dict[str, int]] = []
    blob_chunks: dict[tuple[int, str, int], bytes] = {}

    for page_offset in range(0, len(raw), PAGE_SIZE):
        page = raw[page_offset : page_offset + PAGE_SIZE]
        state_bitmap = page[ENTRY_SIZE : ENTRY_SIZE * 2]
        entry_index = 2
        while entry_index < PAGE_SIZE // ENTRY_SIZE:
            state_byte = state_bitmap[(entry_index - 2) // 4]
            state_bits = (state_byte >> (((entry_index - 2) % 4) * 2)) & 0x03
            state = "written" if state_bits == 0x02 else "empty" if state_bits == 0x03 else "erased"
            raw_entry = page[entry_index * ENTRY_SIZE : (entry_index + 1) * ENTRY_SIZE]
            span = raw_entry[2] or 1
            if state == "written":
                namespace_index = raw_entry[0]
                entry_type = raw_entry[1]
                chunk_index = raw_entry[3]
                key = _decode_key(raw_entry[8:24])
                if namespace_index == 0 and entry_type == 0x01:
                    namespace_indexes[key] = raw_entry[24]
                elif entry_type == 0x48 and key == KEY:
                    blob_indexes.append(
                        {
                            "namespace": namespace_index,
                            "size": int.from_bytes(raw_entry[24:28], "little"),
                            "chunk_count": raw_entry[28],
                            "chunk_start": raw_entry[29],
                        }
                    )
                elif entry_type == 0x42:
                    child_bytes = bytearray()
                    for child_index in range(1, span):
                        child_start = (entry_index + child_index) * ENTRY_SIZE
                        child_bytes.extend(page[child_start : child_start + ENTRY_SIZE])
                    blob_chunks[(namespace_index, key, chunk_index)] = bytes(child_bytes)
            entry_index += span

    namespace_index = namespace_indexes.get(NAMESPACE)
    if namespace_index is None:
        raise ValueError("diagnostic namespace was not found")
    matching_indexes = [item for item in blob_indexes if item["namespace"] == namespace_index]
    if not matching_indexes:
        raise ValueError("diagnostic snapshot key was not found")
    blob = matching_indexes[-1]
    chunks = []
    for offset in range(blob["chunk_count"]):
        chunk_key = (namespace_index, KEY, blob["chunk_start"] + offset)
        if chunk_key not in blob_chunks:
            raise ValueError("diagnostic snapshot blob is incomplete")
        chunks.append(blob_chunks[chunk_key])
    value = b"".join(chunks)[: blob["size"]]
    if len(value) != blob["size"]:
        raise ValueError("diagnostic snapshot blob size is invalid")
    return value


def _capture_nvs_partition(args: argparse.Namespace) -> bytes:
    if args.port is None:
        return args.blob.read_bytes()
    if args.blob is not None:
        raise ValueError("--blob and --port are mutually exclusive")
    if args.nvs_offset < 0 or args.nvs_size <= 0 or args.nvs_size % PAGE_SIZE != 0:
        raise ValueError("NVS offset/size are invalid")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="n3w-nvs-", suffix=".bin", delete=False) as temp:
            temp_path = Path(temp.name)
        os.chmod(temp_path, 0o600)
        command = [
            args.esptool,
            "--before",
            "no_reset",
            "--after",
            "no_reset",
            "--port",
            args.port,
            NVS_READ_COMMAND,
            hex(args.nvs_offset),
            hex(args.nvs_size),
            str(temp_path),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("read-only ROM NVS capture failed")
        return _extract_snapshot_from_nvs(temp_path.read_bytes())
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--blob", type=Path)
    source.add_argument("--port")
    parser.add_argument("--esptool", default="esptool")
    parser.add_argument("--nvs-offset", type=lambda value: int(value, 0), default=0x790000)
    parser.add_argument("--nvs-size", type=lambda value: int(value, 0), default=0x70000)
    parser.add_argument("--namespace", default=NAMESPACE)
    parser.add_argument("--key", default=KEY)
    args = parser.parse_args()
    if args.namespace != NAMESPACE or args.key != KEY:
        parser.error("only gh_n3w_diag/snapshot is readable")
    raw = _capture_nvs_partition(args)
    if len(raw) < 8:
        parser.error("snapshot header is invalid")
    magic = int.from_bytes(raw[0:4], "little")
    schema_version = int.from_bytes(raw[4:6], "little")
    if magic != MAGIC:
        parser.error("snapshot magic is invalid")
    snapshot_type = {
        3: SnapshotV3,
        4: SnapshotV4,
        5: SnapshotV5,
    }.get(schema_version)
    if snapshot_type is None:
        parser.error("snapshot schema is invalid")
    expected_size = ctypes.sizeof(snapshot_type)
    if len(raw) != expected_size:
        parser.error("snapshot blob size is invalid")
    snapshot = snapshot_type.from_buffer_copy(raw)
    if snapshot.magic != MAGIC or snapshot.schema_version != schema_version:
        parser.error("snapshot schema is invalid")
    if snapshot.size != expected_size:
        parser.error("snapshot self-size is invalid")
    print(json.dumps(_values(snapshot), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
