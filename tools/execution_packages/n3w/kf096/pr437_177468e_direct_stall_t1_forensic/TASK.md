# N3-W PR #437 177468e Board B post-write Direct stall T1 read-only forensic

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Trigger

The Manager canonical cursor for Board B is proven stale:

    BOARD_B_SEQ=49
    BOARD_B_UPDATED_AT=2026-09-20T14:35:06.070Z
    BOARD_B_CURSOR_ACTIVITY=STALE
    MANAGER_RESTART_COUNT=0

The application image itself was independently read back exact against artifact 10607030747, so this gate does not rewrite or reset the board.

## Goal

Distinguish, using only T1 read-only evidence:

1. fresh Board B Direct messages reached Manager but were rejected;
2. Manager accepted Direct messages but durable cursor evidence is inconsistent;
3. no Manager log evidence of Direct ingress exists after the stale cursor.

The third outcome is evidence absence, not proof that the board never transmitted.

## Read-only sources

Inside the running Manager container:

- GH_N3W_REPLAY_DB_PATH, SQLite URI mode=ro;
- GH_PAIRING_DB_PATH, SQLite URI mode=ro;
- canonical cursor;
- replay high-water / latest committed tuple;
- current registration / pairing state;
- current node lease state.

On T1 host:

- docker inspect of the Manager;
- docker logs --since <canonical.updated_at> of the Manager.

The raw node ID is resolved only inside private execution and is never emitted by this executor. Public-safe output uses the frozen node-ID SHA-256.

## Log classification

The executor counts, for the exact Board B node:

- Accepted simplified N3-W telemetry source=direct
- Rejected simplified N3-W ingress source=direct ... code=<code>
- lifecycle rejection for retired/unassigned node

Output classification is one of:

    DIRECT_ARRIVED_MANAGER_REJECTED
    DIRECT_ARRIVED_LIFECYCLE_REJECTED
    DIRECT_ACCEPTED_LOG_CURSOR_INCONSISTENT
    NO_MANAGER_DIRECT_LOG_EVIDENCE_AFTER_CURSOR

## Execution

    python3 /tmp/n3w-pr437-177468e-direct-stall-t1-forensic.py       --t1-target <PRIVATE_T1_SSH_TARGET>       --output /tmp/n3w-pr437-177468e-direct-stall-t1-forensic.json

## Boundary

    BOARD_ACCESS=false
    BOARD_RESET=false
    BOARD_FLASH_WRITE=false
    PRODUCT_NVS_WRITE=false
    APPLICATION_SERIAL_OPEN=false

    T1_ACCESS=SSH_READ_ONLY
    T1_MUTATION=false

    PR437_MERGE=false
    KF096_STATUS=OPEN
