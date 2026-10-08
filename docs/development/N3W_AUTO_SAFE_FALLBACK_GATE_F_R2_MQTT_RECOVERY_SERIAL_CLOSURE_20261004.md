# N3W Auto Safe Fallback Gate F R2 MQTT Recovery Serial Closure — 2026-10-04

## Result

Controlled-reset Board B serial evidence proves the R2 stale-Broker runtime recovery path through successful MQTT reconnection and in-boot candidate promotion.

Observed sequence:

1. Device starts with the previously persisted stale Broker endpoint.
2. Wi-Fi connects normally.
3. Initial MQTT connection to the stale endpoint times out.
4. Broker relocation discovery starts.
5. One current Manager/Broker candidate is retained.
6. Standalone Direct Broker candidate attempt starts.
7. MQTT reports Connected.
8. The candidate is promoted for the current boot.

## Classification

- DIRECT_MQTT_FAILURE_TRIGGER=PASS
- MANAGER_DISCOVERY=PASS
- RAM_ONLY_BROKER_RETARGET=PASS
- MQTT_CONNECT_TO_DISCOVERED_BROKER=PASS
- BROKER_CANDIDATE_PROMOTION=PASS

The earlier 120-second failure observation is superseded for the address-recovery/MQTT-connect portion by stronger Board-local serial evidence from the later controlled-reset run.

## Remaining Gate F closure item

A final read-only Manager canonical-cursor check is still required to prove telemetry ingestion advanced after the successful candidate promotion. Also confirm Manager restart count did not change and the durable configured Broker host remains unchanged, demonstrating that recovery was runtime-only.

## Mutation statement

- BOARD_FLASH_WRITE=false
- BOARD_NVS_MUTATION=false
- T1_CONFIG_MUTATION=false
- PR_MERGE=false
