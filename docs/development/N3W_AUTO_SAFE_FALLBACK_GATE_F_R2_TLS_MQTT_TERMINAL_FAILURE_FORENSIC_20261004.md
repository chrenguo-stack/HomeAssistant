# N3-W Auto Safe Fallback Gate F R2 — TLS/MQTT Terminal Failure Forensic — 2026-10-04

Status: `R2_NETWORK_RECOVERY_PATH_PROVEN_TLS_MQTT_TERMINAL_FAILURE_OPEN`

## Scope

This document records the physical network timeline for Board B running the frozen R2 exact artifact at source head:

`67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1`

No Board flash write, Board NVS mutation, or T1 configuration mutation occurred during this timeline capture.

## Preserved stale-Broker oracle

Manager deployment configuration remained intentionally stale throughout the test. The exact historical address is not recorded in this public-safe document.

```text
BROKER_STALE_HOST_PRESERVED=true
MANAGER_RESTART_COUNT=1
```

## Controlled timeline

A T1-side passive raw-packet capture was armed before a controlled Board B reset. A UDP marker packet established timeline zero without mutating T1 configuration.

Observed timeline:

```text
RESET_MARKER_FOUND=true
FIRST_DISCOVERY_REQUEST_SECONDS=15.492
FIRST_DISCOVERY_RESPONSE_SECONDS=15.508
FIRST_TCP_SYN_SECONDS=16.503
FIRST_TCP_SYN_ACK_SECONDS=16.504
FIRST_TCP_ACK_AFTER_SYN_SECONDS=16.509
FIRST_BOARD_TCP_PAYLOAD_SECONDS=16.526
FIRST_T1_TCP_PAYLOAD_SECONDS=16.559
FIRST_TLS_HANDSHAKE_BOARD_SECONDS=16.526
FIRST_TLS_HANDSHAKE_T1_SECONDS=16.559
FIRST_TLS_APPLICATION_BOARD_SECONDS=17.035
FIRST_TLS_APPLICATION_T1_SECONDS=17.050
FIRST_TLS_ALERT_T1_SECONDS=17.047
FIRST_TCP_FIN_SECONDS=17.049
FIRST_TCP_RST_SECONDS=17.053
UDP47111_REQUEST_COUNT=1
UDP47111_RESPONSE_COUNT=1
TCP_SYN_COUNT=1
TCP_SYNACK_COUNT=1
TCP_FIN_COUNT=1
TCP_RST_COUNT=2
```

The apparent sub-millisecond ordering of the first T1 application-data timestamp and T1 alert timestamp must not be over-interpreted; packet capture/processing order at this granularity is not itself a protocol-state oracle.

## Strong conclusions

The physical evidence proves that the R2 standalone Direct Broker relocation path progresses through all of the following stages within the required recovery budget:

```text
DIRECT_MQTT_FAILURE_TRIGGER_REACHED=true
MANAGER_DISCOVERY_REQUEST_SENT=true
MANAGER_DISCOVERY_RESPONSE_RECEIVED=true
RUNTIME_BROKER_RETARGET_TO_CURRENT_T1=true
TCP_SYN_TO_CURRENT_T1_8883=true
TCP_THREE_WAY_HANDSHAKE_COMPLETE=true
TLS_HANDSHAKE_TRAFFIC_BIDIRECTIONAL=true
TLS_APPLICATION_TRAFFIC_OBSERVED=true
```

Therefore the original Gate F R2 failure is no longer attributable to:

- the 60-second business telemetry cadence,
- failure to trigger standalone Broker relocation,
- failure to send discovery,
- failure to receive discovery response,
- failure to retarget the runtime Broker address,
- inability to open TCP to the current T1 address.

## Terminal failure boundary

The connection is terminated shortly after TLS application traffic begins:

```text
T1_TLS_ALERT_OBSERVED=true
TCP_CONNECTION_TERMINATED=true
MQTT_CANONICAL_TELEMETRY_RECOVERED=false
```

Manager canonical cursor remained unchanged after the test, so no new Board B telemetry reached canonical ingestion.

The current source/physical boundary is therefore:

```text
R2_BROKER_ADDRESS_RECOVERY_PATH=PASS
R2_END_TO_END_MQTT_RECOVERY=FAIL
OPEN_FAILURE_DOMAIN=POST_TLS_HANDSHAKE_MQTT_OR_AUTHENTICATION_OR_BROKER_POLICY
```

The raw packet evidence alone does not identify the exact TLS alert description or establish whether the terminal cause is MQTT authentication, broker authorization/policy, credential-state mismatch, or another post-handshake failure. Do not repair radio/discovery logic based on this evidence.

## Next boundary

Perform read-only reconciliation of:

1. Board B generation-3 provisioned MQTT credential lineage,
2. Manager credential-lifecycle state,
3. Mosquitto Dynamic Security client/role/ACL state,
4. broker-side connection/authentication evidence where available,
5. TLS alert description if additional packet-level evidence is needed.

Do not mutate T1 configuration or Board NVS until the exact post-handshake failure is identified.

```text
BOARD_FLASH_WRITE=false
BOARD_NVS_MUTATION=false
T1_CONFIG_MUTATION=false
PR522_MERGE=false
```
