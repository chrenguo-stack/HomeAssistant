from __future__ import annotations

import os
from typing import Mapping

from b1i1_contract import FRESH_RW, EXISTING_RO, require

REQUIRED_ZERO_TABLES = (
    "registrations", "pairing_sessions", "registration_node_history",
    "registration_events", "node_id_leases", "retirement_outbox",
    "credential_assignments", "n3w_replay_meta", "n3w_replay_state",
    "n3w_replay_seen",
)


def _overlap(left: str, right: str) -> bool:
    return os.path.commonpath((left, right)) in (left, right)


def validate_fresh_mount_sources(
    previous: Mapping[str, str],
    fresh: Mapping[str, str],
) -> None:
    require(set(previous) == set(FRESH_RW + EXISTING_RO), "ORIGINAL_MOUNT_AUTHORITY_INCOMPLETE")
    require(set(fresh) == set(FRESH_RW + EXISTING_RO), "FRESH_MOUNT_MAP_INCOMPLETE")
    for dest in EXISTING_RO:
        require(fresh[dest] == previous[dest], "RO_SECRET_SOURCE_CHANGED")
    for dest in FRESH_RW:
        source = fresh[dest]
        require(
            isinstance(source, str) and source.startswith("/")
            and source != "/" and os.path.normpath(source) == source,
            "FRESH_RW_SOURCE_UNSAFE",
        )
        for prior in previous.values():
            require(not _overlap(source, prior), "FRESH_RW_OVERLAPS_ORIGINAL")
        for other_dest in FRESH_RW:
            if other_dest != dest:
                require(not _overlap(source, fresh[other_dest]), "FRESH_RW_SOURCES_OVERLAP")
    require(len(set(fresh.values())) == 6, "FRESH_MOUNT_SOURCE_REUSED")


def require_initialized_zero_business_state(
    table_rows: Mapping[str, int],
    relay_key_file_count: int,
) -> None:
    require(set(table_rows) == set(REQUIRED_ZERO_TABLES), "BUSINESS_TABLE_PROOF_INCOMPLETE")
    require(
        all(type(value) is int and value == 0 for value in table_rows.values()),
        "BUSINESS_ROWS_NOT_ZERO",
    )
    require(type(relay_key_file_count) is int and relay_key_file_count == 0, "RELAY_KEYS_NOT_EMPTY")
