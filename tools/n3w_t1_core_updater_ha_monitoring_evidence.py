from __future__ import annotations

import json
import re
import secrets
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any

from n3w_t1_core_updater_common import UpdaterError
from n3w_t1_core_updater_ha_acceptance import HaAcceptanceEvidence
from n3w_t1_core_updater_ha_data_evidence import read_local_database
from n3w_t1_core_updater_v2_common import UpdaterV2Error, canonical, sha256_bytes


MAX_RECEIPT_BYTES = 8192
MAX_AGE_SECONDS = 30
SERVICES = ("manager", "broker", "homeassistant")
SELF_TEST_TIMEOUT_SECONDS = 8
REQUEST_MANAGER_SELF_TEST = """
import json
import os
import sys
import tempfile
from pathlib import Path
from subprocess import TimeoutExpired

target = Path("/dev/shm/n3w-ota-monitoring-request.json")
document = {"challenge": sys.argv[1], "requested_ns": int(sys.argv[2])}
with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as stream:
    temporary = Path(stream.name)
    try:
        json.dump(document, stream)
        stream.close()
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
"""
_OBSERVATION_ERRORS = (
    OSError, ValueError, RecursionError, sqlite3.Error, TimeoutExpired, UpdaterError, UpdaterV2Error,
)
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
from subprocess import TimeoutExpired

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
if started != Path(f"/proc/{{pid}}/task/{{pid}}/stat").read_text().rsplit(")", 1)[1].split()[19]:
    raise SystemExit("ha_monitoring_receipt_owner_mismatch")
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
        request_self_test: Callable[[str, str, int], None] | None = None,
    ) -> None:
        self.system_id = system_id
        self.replay_db = replay_db
        self.runtime = runtime
        self.read_receipts = read_receipts
        self.request_self_test = request_self_test

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
        except _OBSERVATION_ERRORS:
            return None

    def run_self_test(self) -> HaAcceptanceEvidence:
        """Exercise the existing Manager client only from an updater action."""
        if self.request_self_test is None:
            return HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")
        try:
            instances = {name: self.runtime(name) for name in SERVICES}
            challenge = secrets.token_hex(16)
            started = time.monotonic_ns()
            self.request_self_test(instances["manager"]["container_id"], challenge, started)
            deadline = started + SELF_TEST_TIMEOUT_SECONDS * 10**9
            while time.monotonic_ns() < deadline:
                try:
                    records = self._records(instances["homeassistant"]["container_id"])
                except UpdaterError:
                    records = []
                now = time.monotonic_ns()
                for record in records:
                    if (
                        isinstance(record, list) and len(record) == 3
                        and record[:2] == ["self-test", challenge]
                        and type(record[2]) is int and started <= record[2] <= min(now, deadline)
                    ):
                        if any(self.runtime(name) != instance for name, instance in instances.items()):
                            return HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")
                        digest = sha256_bytes(canonical({"system_id": self.system_id, "receipt": record}))
                        return HaAcceptanceEvidence("PASS", digest)
                time.sleep(0.25)
        except _OBSERVATION_ERRORS:
            pass
        return HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")

    def _records(self, container_id: str) -> list[Any]:
        raw = self.read_receipts(container_id)
        if len(raw) > MAX_RECEIPT_BYTES:
            return []
        receipt = json.loads(raw)
        if not isinstance(receipt, dict) or receipt.get("system_id") != self.system_id:
            return []
        records = receipt.get("records")
        return records if isinstance(records, list) and len(records) <= 16 else []

    def _match(self) -> str | None:
        instances = {name: self.runtime(name) for name in SERVICES}
        records = self._records(instances["homeassistant"]["container_id"])
        if not records:
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
