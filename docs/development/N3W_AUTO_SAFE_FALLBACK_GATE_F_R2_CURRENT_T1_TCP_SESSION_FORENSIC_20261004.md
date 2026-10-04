# N3-W Auto Safe Fallback Gate F R2 current-T1 TCP session forensic evidence — 2026-10-04

## Scope

Read-only physical forensic follow-up after R2 stale-Broker runtime acceptance remained FAIL within the 120 s budget.

## Preserved conditions

- Board B runs the R2 exact artifact bound to source `67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1`.
- Durable Broker host on T1 remains intentionally stale for the physical oracle.
- T1 configuration unchanged.
- Board NVS unchanged.
- No Board reset or flash write during this capture.

## Passive T1 capture

A 90 s AF_PACKET capture on the current LAN interface observed Board B traffic to the current T1 TLS MQTT listener.

Results:

```text
BOARD_TO_CURRENT_T1_8883_TCP_PACKET_COUNT=43
UDP47111_REQUEST_COUNT=0
UDP47111_RESPONSE_COUNT=0
TCP_SOURCE_PORT_COUNT=1
TCP_FLAG_ACK_COUNT=11
TCP_FLAG_ACK_PSH_COUNT=32
```

All 43 Board-to-current-T1 packets used one source TCP port. The first packet was observed at approximately 2.5 s into the capture and the last at approximately 82.6 s. Multiple packets carried non-zero payloads, including payloads larger than ordinary pure ACKs.

No SYN, RST, or FIN packets were observed in this capture window.

## Interpretation

This rules out the earlier assumption that the R2 node never retargeted toward the current T1 address. During this capture, Board B was actively sending data over an already-existing TCP connection toward the current T1 TCP/8883 endpoint.

Because the connection was already established before the capture began, this capture cannot show when discovery occurred or when the TCP handshake completed. The absence of UDP/47111 in this later window therefore does not prove discovery never happened.

However, Manager canonical telemetry still had not advanced and no stable MQTT recovery had been proven. The current defect boundary is therefore below or after RAM-only Broker retarget and TCP establishment, with remaining candidate layers including TLS, MQTT authentication/session establishment, or later canonical ingestion.

## Current classification

```text
R2_RECOVERY_WITHIN_120S=FAIL
R2_RAM_ONLY_RETARGET_TO_CURRENT_T1=SUPPORTED_BY_TCP_EVIDENCE
R2_TCP_SESSION_TO_CURRENT_T1=OBSERVED
R2_TLS_MQTT_SUCCESS=NOT_PROVEN
R2_CANONICAL_TELEMETRY_RECOVERY=FAIL
R2_UDP_DISCOVERY_TIMING=NOT_OBSERVED_IN_LATE_CAPTURE
BOARD_RESET=false
BOARD_FLASH_WRITE=false
T1_MUTATION=false
MERGE=false
```

## Next step

Read-only Broker-side reconciliation should determine whether the current-T1 TCP session completed TLS, whether MQTT authentication/session establishment was accepted or rejected, and whether the connection reached a usable MQTT state. Do not mutate T1 or Board before that classification is complete.
