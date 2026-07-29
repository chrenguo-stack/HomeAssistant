#!/usr/bin/env python3
"""Normalize ESP-IDF task-watchdog panic cycles for Stage2D9R evidence.

Source-only parser. It performs no board, serial, network, Broker, or physical
operation. Raw evidence remains in private operator custody; public review uses
synthetic lines and normalized digests only.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable, Sequence

SCHEMA = "gh.h3.n2.stage2d9r-g3r-task-watchdog-signature/1"
SOURCE_STATE = "SOURCE_ONLY_TASK_WATCHDOG_PARSER"

TRIGGER_RE = re.compile(r"Task watchdog got triggered", re.I)
TASK_RE = re.compile(r"(?:^|:)\s*-\s+([A-Za-z0-9_.-]+)\s+\(CPU\s+(\d+)\)\s*$", re.I)
ABORT_RE = re.compile(r"(?:^|:)\s*Aborting\.\s*$", re.I)
REGISTER_RE = re.compile(r"Print CPU\s+(\d+)\s+\(current core\)\s+registers", re.I)
MEPC_RE = re.compile(r"\bMEPC\s*[:=]\s*(0x[0-9a-fA-F]+)", re.I)
RA_RE = re.compile(r"(?:^|\s)RA\s*[:=]\s*(0x[0-9a-fA-F]+)", re.I)
SAVED_PC_RE = re.compile(r"\bSaved PC\s*[:=]\s*(0x[0-9a-fA-F]+)", re.I)
REBOOT_RE = re.compile(r"\bRebooting\.\.\.", re.I)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).lower() if match else None


def parse_task_watchdog_cycle(lines: Sequence[str]) -> dict[str, object]:
    text = "\n".join(lines)
    triggered = TRIGGER_RE.search(text) is not None
    task_match = next((TASK_RE.search(line) for line in lines if TASK_RE.search(line)), None)
    register_match = REGISTER_RE.search(text)
    abort_observed = ABORT_RE.search(text) is not None
    reboot_observed = REBOOT_RE.search(text) is not None
    normalized: dict[str, object] = {
        "classification": "TASK_WATCHDOG" if triggered else "NOT_TASK_WATCHDOG",
        "triggered": triggered,
        "starved_task": task_match.group(1) if task_match else None,
        "starved_task_cpu": int(task_match.group(2)) if task_match else None,
        "abort_observed": abort_observed,
        "register_dump_cpu": int(register_match.group(1)) if register_match else None,
        "mepc": _first(MEPC_RE, text),
        "ra": _first(RA_RE, text),
        "saved_pc": _first(SAVED_PC_RE, text),
        "reboot_observed": reboot_observed,
        "cycle_complete": bool(triggered and task_match and abort_observed and reboot_observed),
    }
    return {
        "schema": SCHEMA,
        **normalized,
        "signature_sha256": canonical_sha256(normalized),
    }


def split_and_parse_cycles(lines: Iterable[str]) -> list[dict[str, object]]:
    cycles: list[list[str]] = []
    active: list[str] = []
    for line in lines:
        if TRIGGER_RE.search(line) and active:
            cycles.append(active)
            active = []
        if TRIGGER_RE.search(line) or active:
            active.append(line)
        if active and REBOOT_RE.search(line):
            cycles.append(active)
            active = []
    if active:
        cycles.append(active)
    return [parse_task_watchdog_cycle(cycle) for cycle in cycles]


def main() -> int:
    print(json.dumps({
        "status": SOURCE_STATE,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "broker_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
