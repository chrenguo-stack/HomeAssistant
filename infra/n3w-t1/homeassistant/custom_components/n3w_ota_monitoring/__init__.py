"""Keep a short-lived receipt of natural telemetry delivered to HA's MQTT client."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from collections import deque
from pathlib import Path


DOMAIN = "n3w_ota_monitoring"
RECEIPTS = Path("/dev/shm/n3w-ota-monitoring.json")
LOGGER = logging.getLogger(__name__)


def _record(prefix, message):
    if (
        message.retain is not False or not isinstance(message.payload, bytes)
        or len(message.payload) > 16384
    ):
        return None
    try:
        document = json.loads(message.payload)
    except (ValueError, RecursionError):
        return None
    if not isinstance(document, dict):
        return None
    if message.topic == f"{prefix}/ota-monitoring/self-test":
        challenge = document.get("challenge")
        if (
            set(document) == {"schema", "challenge"}
            and document["schema"] == "gh.ota-monitoring-self-test/1"
            and isinstance(challenge, str) and re.fullmatch(r"[0-9a-f]{32}", challenge)
        ):
            return ["self-test", challenge, time.monotonic_ns()]
        return None
    if document.get("schema") != "gh.telemetry/1":
        return None
    node, boot, seq, received = (
        document.get(key) for key in ("node_id", "boot_id", "seq", "received_at")
    )
    if (
        not isinstance(node, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", node)
        or message.topic != f"{prefix}/{node}/telemetry"
        or not isinstance(boot, str) or not re.fullmatch(r"boot_[0-9a-f]{16}", boot)
        or type(seq) is not int or not 0 <= seq <= 0xFFFFFFFF
        or not isinstance(received, str) or len(received) > 32
    ):
        return None
    return [node, boot, seq, received, time.monotonic_ns()]


def _publish_receipts(system_id, records):
    pid = os.getpid()
    started = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]
    document = {"system_id": system_id, "owner": [pid, started], "records": records}
    with tempfile.NamedTemporaryFile(mode="w", dir=RECEIPTS.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(document, stream, separators=(",", ":"))
            stream.close()
            temporary.replace(RECEIPTS)
        finally:
            temporary.unlink(missing_ok=True)


async def async_setup(hass, config):
    from homeassistant.components import mqtt

    options = config.get(DOMAIN)
    system_id = options.get("system_id") if isinstance(options, dict) else None
    if not isinstance(system_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{3,64}", system_id):
        return False

    await hass.async_add_executor_job(RECEIPTS.unlink, True)
    prefix = f"gh/v1/{system_id}/state"
    records = deque(maxlen=16)
    last_write = 0
    writing = False

    async def receive(message):
        nonlocal last_write, writing
        record = _record(prefix, message)
        if record is None:
            return
        records.append(record)
        if writing:
            return
        writing = True
        try:
            while True:
                delay = 1 - (time.monotonic_ns() - last_write) / 1_000_000_000
                if delay > 0:
                    await asyncio.sleep(delay)
                snapshot = tuple(records)
                last_write = time.monotonic_ns()
                await hass.async_add_executor_job(_publish_receipts, system_id, snapshot)
                if snapshot[-1] is records[-1]:
                    break
        except OSError:
            LOGGER.warning("Unable to save the OTA monitoring receipt")
        finally:
            writing = False

    async def subscribe():
        if await mqtt.async_wait_for_mqtt_client(hass):
            await mqtt.async_subscribe(hass, f"{prefix}/+/telemetry", receive, qos=1, encoding=None)
            await mqtt.async_subscribe(
                hass, f"{prefix}/ota-monitoring/self-test", receive, qos=0, encoding=None,
            )

    hass.async_create_background_task(subscribe(), "n3w_ota_monitoring_subscribe")
    return True
