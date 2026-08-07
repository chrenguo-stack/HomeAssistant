from __future__ import annotations

import re

DOMAIN = "greenhouse_history"
INTEGRATION_VERSION = "0.1.0"
STORAGE_KEY = "greenhouse_history.target_ledger"
STORAGE_VERSION = 2
REQUEST_SCHEMA = "gh.c06b2-ha-projection-request/1"
RESULT_SCHEMA = "gh.c06b2-ha-projection-result/1"
PROJECTION_SCHEMA = "gh.c06-hourly-projection/1"
VERIFIED_RETENTION_DAYS = 14
MAX_LEDGER_ENTRIES = 20_000
MAX_LEDGER_BYTES = 134_217_728
CONF_C06B2_RUNTIME_ENABLED = "c06b2_runtime_enabled"
DEFAULT_C06B2_RUNTIME_ENABLED = False
C06B2_MQTT_QUEUE_CAPACITY = 64
C06B2_MAX_REQUEST_BYTES = 1_052_672
C06B2_SUBSCRIBE_TIMEOUT_SECONDS = 15.0

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def validate_system_id(system_id: str) -> str:
    if not _ID_RE.fullmatch(system_id):
        raise ValueError("system_id must match [A-Za-z0-9_-]{3,64}")
    return system_id


def request_topic(system_id: str) -> str:
    return f"gh/v1/{validate_system_id(system_id)}/out/homeassistant/history/projection"


def result_topic(system_id: str) -> str:
    return (
        f"gh/v1/{validate_system_id(system_id)}"
        "/ingress/homeassistant/history/projection/result"
    )
