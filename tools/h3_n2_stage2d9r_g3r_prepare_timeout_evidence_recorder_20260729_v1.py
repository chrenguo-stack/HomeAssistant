#!/usr/bin/env python3
"""Source-only redacted evidence recorder for a future PREPARE execution."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SOURCE_STATE = "SOURCE_ONLY_NO_BOARD_OR_NETWORK_OPERATION"
MAC_RE = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PATH_RE = re.compile(r"(?:/dev/\S+|/Users/\S+|/home/\S+|[A-Za-z]:\\\\\S+)")
SECRET_RE = re.compile(r"(?i)\b(password|passwd|token|secret|key)\s*[:=]\s*\S+")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SAFE_STAGE_RE = re.compile(r"^stage2d9r_[A-Za-z0-9_.-]+=[A-Za-z0-9_.:-]+$")
COMMAND_RE = re.compile(r"^\s*(GH2D9R_PREPARE_V\d+|GH2D9R_VERIFY_V\d+)\b")
RESET_PATTERNS = ("ESP-ROM:", "rst:", "Saved PC:", "boot:")
BROKER_DISCONNECT_WORDS = ("disconnect", "socket error", "broken pipe", "connection lost")
BROKER_CONNECT_WORDS = ("new connection", "client connected", "connack", "sending connack")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_ipv4(value: str) -> bool:
    try:
        ipaddress.IPv4Address(value)
        return True
    except ipaddress.AddressValueError:
        return False


def redact_text(raw: str) -> str:
    text = ANSI_RE.sub("", raw.replace("\x00", ""))
    command = COMMAND_RE.match(text)
    if command:
        return f"{command.group(1)} [REDACTED_COMMAND_MATERIAL]"
    text = MAC_RE.sub("[REDACTED_MAC]", text)
    text = IPV4_RE.sub(lambda m: "[REDACTED_IP]" if _valid_ipv4(m.group(0)) else m.group(0), text)
    text = PATH_RE.sub("[REDACTED_PATH]", text)
    text = SECRET_RE.sub(lambda m: f"{m.group(1)}=[REDACTED_SECRET]", text)
    return text.strip()


def serial_event(raw_line: str, *, at: str, phase: str) -> dict[str, Any]:
    redacted = redact_text(raw_line)
    lower = redacted.lower()
    if not redacted:
        kind = "EMPTY_LINE"
        payload: dict[str, Any] = {}
    elif COMMAND_RE.match(raw_line):
        kind = "COMMAND_MATERIAL_REDACTED"
        payload = {"schema": redacted.split()[0]}
    elif SAFE_STAGE_RE.fullmatch(redacted):
        kind = "STAGE_MARKER"
        payload = {"marker": redacted}
    elif any(pattern.lower() in lower for pattern in RESET_PATTERNS):
        kind = "DEVICE_RESET_OBSERVED"
        payload = {"line_sha256": sha256_text(redacted)}
    elif "tls" in lower or "mqtt" in lower:
        kind = "PROTOCOL_DIAGNOSTIC"
        payload = {"line_sha256": sha256_text(redacted)}
    else:
        kind = "UNCLASSIFIED_LINE"
        payload = {"line_sha256": sha256_text(redacted)}
    return {"at": at, "channel": "serial", "phase": phase, "kind": kind, **payload}


def broker_event(raw_line: str, *, at: str, phase: str) -> dict[str, Any]:
    redacted = redact_text(raw_line)
    lower = redacted.lower()
    if any(word in lower for word in BROKER_DISCONNECT_WORDS):
        kind = "BROKER_DISCONNECT"
    elif any(word in lower for word in BROKER_CONNECT_WORDS):
        kind = "BROKER_CONNECT"
    elif "error" in lower or "failed" in lower:
        kind = "BROKER_ERROR"
    else:
        kind = "BROKER_LINE"
    return {
        "at": at,
        "channel": "broker",
        "phase": phase,
        "kind": kind,
        "line_sha256": sha256_text(redacted),
    }


def classify_prepare_outcome(events: Iterable[dict[str, Any]], *, deadline_at: str) -> str:
    ordered = list(events)
    command_index = next((i for i, event in enumerate(ordered) if event.get("kind") == "PREPARE_COMMAND_SENT"), None)
    if command_index is None:
        return "NO_RESULT"
    after = ordered[command_index + 1 :]
    for event in after:
        if event.get("kind") in {"PREPARE_PASS", "PREPARE_FAIL"} and str(event.get("at", "")) > deadline_at:
            return "LATE_RESULT"
    if any(event.get("kind") == "DEVICE_RESET_OBSERVED" for event in after):
        return "SERIAL_RESET"
    if any(event.get("kind") == "BROKER_DISCONNECT" for event in after):
        return "BROKER_DISCONNECT"
    if any(event.get("kind") == "UNRECOGNIZED_RESULT" for event in after):
        return "UNRECOGNIZED_RESULT"
    return "NO_RESULT"


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@dataclass
class EvidenceJournal:
    root: Path
    serial_events: list[dict[str, Any]] = field(default_factory=list)
    broker_events: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)

    def initialize(self) -> None:
        if self.root.exists():
            if self.root.is_symlink() or not self.root.is_dir():
                raise RuntimeError("EVIDENCE_ROOT_INVALID")
            if any(self.root.iterdir()):
                raise RuntimeError("EVIDENCE_ROOT_NOT_EMPTY")
        else:
            self.root.mkdir(parents=True, mode=0o700)
        os.chmod(self.root, 0o700)

    def record_timeline(self, kind: str, **fields: Any) -> None:
        self.timeline.append({"at": utc_now(), "kind": kind, **fields})

    def record_serial(self, raw_line: str, phase: str) -> None:
        event = serial_event(raw_line, at=utc_now(), phase=phase)
        self.serial_events.append(event)
        if event["kind"] == "DEVICE_RESET_OBSERVED":
            self.timeline.append({"at": event["at"], "kind": "DEVICE_RESET_OBSERVED"})

    def record_broker(self, raw_line: str, phase: str) -> None:
        event = broker_event(raw_line, at=utc_now(), phase=phase)
        self.broker_events.append(event)
        if event["kind"] == "BROKER_DISCONNECT":
            self.timeline.append({"at": event["at"], "kind": "BROKER_DISCONNECT"})

    def persist(self, *, classification: str, terminal: bool) -> dict[str, Any]:
        serial_bytes = b"".join(json.dumps(v, sort_keys=True, separators=(",", ":")).encode() + b"\n" for v in self.serial_events)
        broker_bytes = b"".join(json.dumps(v, sort_keys=True, separators=(",", ":")).encode() + b"\n" for v in self.broker_events)
        timeline_value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-timeout-timeline/1",
            "classification": classification,
            "terminal": terminal,
            "events": self.timeline,
        }
        timeline_bytes = json.dumps(timeline_value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        atomic_write(self.root / "prepare-serial.redacted.jsonl", serial_bytes)
        atomic_write(self.root / "broker.redacted.jsonl", broker_bytes)
        atomic_write(self.root / "prepare-timeline.json", timeline_bytes)
        result = {
            "classification": classification,
            "serial_evidence_sha256": hashlib.sha256(serial_bytes).hexdigest(),
            "broker_evidence_sha256": hashlib.sha256(broker_bytes).hexdigest(),
            "timeline_sha256": hashlib.sha256(timeline_bytes).hexdigest(),
            "raw_private_values_included": False,
            "terminal": terminal,
        }
        atomic_write(
            self.root / "prepare-evidence-manifest.json",
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode() + b"\n",
        )
        return result


def source_boundary() -> dict[str, Any]:
    return {
        "state": SOURCE_STATE,
        "authorization_created": False,
        "physical_request_created": False,
        "board_operation": False,
        "serial_operation": False,
        "network_operation": False,
        "broker_started": False,
    }


if __name__ == "__main__":
    print(json.dumps(source_boundary(), sort_keys=True))
