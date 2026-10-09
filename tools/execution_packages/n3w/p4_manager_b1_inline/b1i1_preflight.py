from __future__ import annotations

import os
from typing import Any

from b1i1_contract import Authority, EXISTING_RO, FRESH_RW, require


def validate_live_origin(
    authority: Authority,
    manager: dict[str, Any],
    broker: dict[str, Any],
    *,
    ha_running: bool,
    r5_guard_verified: bool,
    tls_8883_verified: bool,
) -> dict[str, str]:
    authority.validate()
    require(manager.get("Id") == authority.old_manager_id, "OLD_MANAGER_ID_DRIFT")
    require(manager.get("Image") == authority.old_image, "OLD_MANAGER_IMAGE_DRIFT")
    require(manager.get("State", {}).get("Running") is True, "OLD_MANAGER_NOT_RUNNING")
    require(broker.get("Id") == authority.broker_id, "BROKER_ID_DRIFT")
    require(broker.get("State", {}).get("Running") is True, "BROKER_NOT_RUNNING")
    require(broker.get("State", {}).get("StartedAt") == authority.broker_started_at, "BROKER_STARTED_DRIFT")
    require(broker.get("RestartCount") == authority.broker_restart_count, "BROKER_RESTART_DRIFT")
    require(ha_running is True and r5_guard_verified is True, "HA_OR_R5_UNVERIFIED")
    require(tls_8883_verified is True, "BROKER_TLS_8883_UNVERIFIED")
    host = manager.get("HostConfig", {})
    require(host.get("NetworkMode") == "host", "MANAGER_NETWORK_NOT_HOST")
    mounts = manager.get("Mounts")
    require(isinstance(mounts, list) and len(mounts) == 6, "MANAGER_MOUNT_COUNT_INVALID")
    sources: dict[str, str] = {}
    for m in mounts:
        dest = m.get("Destination")
        require(dest in FRESH_RW + EXISTING_RO and dest not in sources, "MANAGER_MOUNT_DEST_DRIFT")
        require(m.get("Type") == "bind", "MANAGER_NOT_BIND_MOUNT")
        require(m.get("RW") is (dest in FRESH_RW), "MANAGER_MOUNT_PERMISSION_DRIFT")
        src = m.get("Source")
        require(
            isinstance(src, str) and src.startswith("/")
            and os.path.normpath(src) == src and src != "/",
            "MANAGER_MOUNT_SOURCE_UNSAFE",
        )
        sources[dest] = src
    require(set(sources) == set(FRESH_RW + EXISTING_RO), "MANAGER_MOUNT_MISSING")
    require(len(set(sources.values())) == 6, "MANAGER_MOUNT_SOURCE_REUSED")
    return sources
