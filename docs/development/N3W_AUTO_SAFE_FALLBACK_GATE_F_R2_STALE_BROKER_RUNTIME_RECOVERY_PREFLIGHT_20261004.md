# N3-W Auto Safe Fallback Gate F R2 Stale-Broker Runtime Recovery Preflight — 2026-10-04

Status: `PREFLIGHT_PASS_RUNTIME_ACCEPTANCE_NOT_STARTED`

## Scope

This preflight follows the R2 exact-artifact minimal write to Board B. It is read-only and precedes the controlled reboot used for stale-Broker runtime recovery acceptance.

No Board reset, Board flash write, Board NVS mutation, T1 mutation, Manager restart, or PR merge occurred in this preflight.

## Durable stale-Broker oracle

The running Manager still advertises the historical node Broker host configuration rather than the current T1 LAN address:

```text
GH_N3W_NODE_BROKER_HOST=<STALE_BROKER_ADDRESS>
```

The exact private address is intentionally omitted from the public repository. The stale-host condition remains physically present and has not been repaired by changing T1 configuration.

## Manager state

```text
MANAGER_RESTART_COUNT=1
PAIRING_DB_EXISTS=true
PAIRING_DB_READABLE=true
HISTORY_DB_EXISTS=false
HISTORY_DB_READABLE=false
```

The previous acceptance harness failed because it hard-coded the default registration/history path. This preflight instead searched readable Manager SQLite state and found the canonical cursor table in the N3-W replay database.

## Board B canonical baseline

```text
CANONICAL_CURSOR_FOUND=true
CANONICAL_DB_NAME=replay.sqlite3
BOOT_SESSION_BEFORE=dc40c82e1467cf88
SEQ_BEFORE=112
SOURCE_BEFORE=direct
UPDATED_AT_BEFORE=2026-09-24T13:28:35.713Z
CANONICAL_CURSOR_READONLY_PREFLIGHT=PASS
```

This is the same stale canonical cursor observed before the R2 physical recovery test. No new telemetry had reached Manager at preflight time.

## Mutation boundary

```text
BOARD_RESET=false
BOARD_FLASH_WRITE=false
BOARD_NVS_MUTATION=false
T1_MUTATION=false
MANAGER_RESTART=false
MERGE=false
```

## Next gate

Perform one controlled Board B reboot while preserving NVS and T1 configuration, then verify that the R2 production binary independently recovers from the stale persisted Broker address within the frozen no-Relay absolute recovery budget.

Primary runtime acceptance condition:

```text
MQTT_RECOVERY_WITHIN_120S=PASS
```

Secondary evidence:

- Manager restart count does not increase.
- Manager configuration remains on the stale Broker address.
- Board B establishes a new TLS MQTT connection to the current T1 Broker.
- Manager canonical telemetry advances from the stale cursor under the new boot.
- No persistent Broker configuration rewrite is required for this pass.
