#!/usr/bin/env python3
"""Read only the Phase 4 gh_n3w_diag/snapshot blob from a host export.

This utility intentionally does not open a serial port, talk to a board, or
write an NVS partition.  The input is an already-exported value blob.
"""

from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path


MAGIC = 0x4E335744
SCHEMA_VERSION = 1
NAMESPACE = "gh_n3w_diag"
KEY = "snapshot"


class Snapshot(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("schema_version", ctypes.c_uint16),
        ("size", ctypes.c_uint16),
        ("runtime_start_mode", ctypes.c_uint8),
        ("path_state", ctypes.c_uint8),
        ("current_channel", ctypes.c_uint8),
        ("last_requested_channel", ctypes.c_uint8),
        ("last_observed_channel", ctypes.c_uint8),
        ("reserved", ctypes.c_uint8 * 3),
        ("scan_attempts", ctypes.c_uint32),
        ("scan_successes", ctypes.c_uint32),
        ("scan_failures", ctypes.c_uint32),
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
    ]


def _values(snapshot: Snapshot) -> dict[str, object]:
    return {
        "schema_version": snapshot.schema_version,
        "runtime_start_mode": snapshot.runtime_start_mode,
        "path_state": snapshot.path_state,
        "current_channel": snapshot.current_channel,
        "last_requested_channel": snapshot.last_requested_channel,
        "last_observed_channel": snapshot.last_observed_channel,
        "scan_attempts": snapshot.scan_attempts,
        "scan_successes": snapshot.scan_successes,
        "scan_failures": snapshot.scan_failures,
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
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blob", type=Path, required=True)
    parser.add_argument("--namespace", default=NAMESPACE)
    parser.add_argument("--key", default=KEY)
    args = parser.parse_args()
    if args.namespace != NAMESPACE or args.key != KEY:
        parser.error("only gh_n3w_diag/snapshot is readable")
    raw = args.blob.read_bytes()
    if len(raw) != ctypes.sizeof(Snapshot):
        parser.error("snapshot blob size is invalid")
    snapshot = Snapshot.from_buffer_copy(raw)
    if snapshot.magic != MAGIC or snapshot.schema_version != SCHEMA_VERSION:
        parser.error("snapshot schema is invalid")
    if snapshot.size != ctypes.sizeof(Snapshot):
        parser.error("snapshot self-size is invalid")
    print(json.dumps(_values(snapshot), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
