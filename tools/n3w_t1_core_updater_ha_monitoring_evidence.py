from __future__ import annotations

import json
import re
import sqlite3
from subprocess import TimeoutExpired
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_common import UpdaterError
from n3w_t1_core_updater_ha_acceptance import HaAcceptanceEvidence
from n3w_t1_core_updater_ha_data_evidence import read_local_database
from n3w_t1_core_updater_v2_common import UpdaterV2Error, canonical, sha256_bytes


MAX_RECEIPT_BYTES = 8192
MAX_AGE_SECONDS = 30
SERVICES = ("manager", "broker", "homeassistant")
CURSOR_QUERY = """
    SELECT boot_session_hex, seq, updated_at, last_source
    FROM n3w_canonical_cursors WHERE node_id = ?
"""
# Run in the already bound HA container. The receipt must have a live writer.
READ_HA_RECEIPTS = f"""
import json
import os
import stat
from pathlib import Path

fd = os.open("/dev/shm/n3w-ota-monitoring.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
with os.fdopen(fd, "rb") as stream:
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        raise SystemExit(1)
    raw = stream.read({MAX_RECEIPT_BYTES + 1})
if len(raw) > {MAX_RECEIPT_BYTES}:
    raise SystemExit(1)
pid, started = json.loads(raw)["owner"]
if type(pid) is not int or pid <= 0:
    raise SystemExit(1)
if started != Path(f"/proc/{{pid}}/stat").read_text().rsplit(")", 1)[1].split()[19]:
    raise SystemExit(1)
os.write(1, raw)
"""


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("time zone required")
    return parsed.astimezone(UTC)


def _candidate(record: Any, monotonic_now: int) -> bool:
    if not isinstance(record, list) or len(record) != 5:
        return False
    node, boot, seq, received, observed = record
    return (
        isinstance(node, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", node) is not None
        and isinstance(boot, str) and re.fullmatch(r"boot_[0-9a-f]{16}", boot) is not None
        and type(seq) is int and 0 <= seq <= 0xFFFFFFFF
        and isinstance(received, str) and len(received) <= 32
        and type(observed) is int and 0 <= monotonic_now - observed <= MAX_AGE_SECONDS * 10**9
    )


class LocalHaMonitoringEvidence:
    def __init__(
        self, system_id: str, replay_db: Path,
        runtime: Callable[[str], dict[str, Any]], read_receipts: Callable[[str], bytes],
    ) -> None:
        self.system_id = system_id
        self.replay_db = replay_db
        self.runtime = runtime
        self.read_receipts = read_receipts

    def capture_baseline(self, transaction: dict[str, Any]) -> str:
        evidence = self._observe()
        if evidence is None:
            raise UpdaterV2Error("ha_usb_natural_monitoring_baseline_unavailable")
        return evidence

    def observe(self, transaction: dict[str, Any], *, fallback: bool) -> HaAcceptanceEvidence:
        evidence = None if fallback else self._observe()
        if evidence is None:
            return HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")
        return HaAcceptanceEvidence("PASS", evidence)

    def _observe(self) -> str | None:
        try:
            return self._match()
        except (OSError, ValueError, RecursionError, sqlite3.Error, TimeoutExpired, UpdaterError, UpdaterV2Error):
            return None

    def _match(self) -> str | None:
        instances = {name: self.runtime(name) for name in SERVICES}
        raw = self.read_receipts(instances["homeassistant"]["container_id"])
        if len(raw) > MAX_RECEIPT_BYTES:
            return None
        receipt = json.loads(raw)
        if not isinstance(receipt, dict) or receipt.get("system_id") != self.system_id:
            return None
        records = receipt.get("records")
        if not isinstance(records, list) or len(records) > 16:
            return None

        now = datetime.now(UTC)
        after = max(
            now - timedelta(seconds=MAX_AGE_SECONDS),
            *(_utc(instance["started_at"]) for instance in instances.values()),
        )
        monotonic_now = time.monotonic_ns()
        with read_local_database(self.replay_db) as connection:
            for record in reversed(records):
                if not _candidate(record, monotonic_now):
                    continue
                node, boot, seq, received, _ = record
                try:
                    if not after < _utc(received) <= now:
                        continue
                except ValueError:
                    continue
                cursor = connection.execute(CURSOR_QUERY, (node,)).fetchone()
                if cursor not in {(boot[5:], seq, received, "direct"), (boot[5:], seq, received, "relay")}:
                    continue
                if any(self.runtime(name) != instance for name, instance in instances.items()):
                    return None
                return sha256_bytes(canonical({"system_id": self.system_id, "receipt": record}))
        return None
