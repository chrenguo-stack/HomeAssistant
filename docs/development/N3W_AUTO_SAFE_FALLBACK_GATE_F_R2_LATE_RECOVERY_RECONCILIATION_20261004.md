# N3-W Auto Safe Fallback Gate F R2 Late Recovery Reconciliation — 2026-10-04

Status: `R2_LATE_RECOVERY_SUSPECTED_REQUIRES_RECONCILIATION`

## Context

The formal 120-second stale-Broker recovery acceptance failed:

```text
MQTT_RECOVERY_WITHIN_120S=FAIL
CANONICAL_CURSOR_ADVANCE=false
MANAGER_RESTART_COUNT_STABLE=true
T1_MUTATION=false
BOARD_NVS_MUTATION=false
```

A later passive T1-side 90-second packet capture observed:

```text
BOARD_DISCOVERY_UDP47111_REQUEST_COUNT=0
T1_DISCOVERY_UDP47111_RESPONSE_COUNT=0
BOARD_TO_CURRENT_T1_8883_TCP_PACKET_COUNT=46
BOARD_TO_CURRENT_T1_8883_SYN_COUNT=0
BOARD_RESET=false
BOARD_FLASH_WRITE=false
T1_MUTATION=false
```

Real private IPv4 addresses and board identifiers are intentionally omitted from this public repository record.

## Interpretation boundary

The packet capture does **not** prove that Broker discovery never happened. The capture began after the formal 120-second acceptance window had already ended. The presence of outbound Board-to-current-T1 TCP traffic on port 8883 means the Board had, by the capture window, acquired a route toward the current Broker endpoint or was participating in an already-existing/retrying TCP flow.

Because no SYN was seen in that later window, one plausible explanation is that discovery and runtime retarget occurred before the capture began, but only after the <=120-second acceptance budget had already been missed.

Therefore the current stronger classification is:

```text
R2_STALE_BROKER_PHYSICAL_ACCEPTANCE=FAIL
R2_RECOVERY_WITHIN_120S=FAIL
R2_NEVER_RECOVERED=NOT_PROVEN
R2_LATE_RECOVERY=SUPPORTED_HYPOTHESIS
```

## Required reconciliation

Before any R3 source mutation:

1. Read current Manager TCP state for the Board and Broker port.
2. Read the current canonical cursor for the stable Board node identity.
3. If current MQTT is established and/or canonical telemetry has advanced, classify R2 as late recovery rather than no recovery.
4. If no established MQTT and no canonical advance, decode the observed outbound TCP flags/state before changing source.

## Safety boundary

```text
BOARD_MUTATION=false
T1_MUTATION=false
MERGE=false
R3_SOURCE_MUTATION=HOLD
```
