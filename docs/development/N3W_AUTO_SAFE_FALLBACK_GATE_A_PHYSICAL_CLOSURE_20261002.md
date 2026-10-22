# N3-W Auto Safe Fallback Gate A Physical Closure — 2026-10-02

Status: `GATE_A_CLOSED_PASS`

This document closes **Gate A only** for the N3-W `auto` safe-fallback source-repair route. It proves the minimum runtime MQTT retarget prerequisite and proves that the temporary Gate A physical fixture was cleaned up and Board B was returned to the accepted KF-099 baseline.

It does **not** claim that the full auto-safe-fallback feature is implemented or physically accepted. Gates B–F remain separate work.

## 1. Route authority

```text
TASK=N3W_AUTO_SAFE_FALLBACK_V1_SOURCE_REPAIR_20260929
PR=516
BRANCH=fix/n3w-auto-safe-fallback-v1-20260929
PR_STATE=OPEN_DRAFT
MERGE=false

DESIGN_AUTHORITY=docs/development/N3W_AUTO_SAFE_FALLBACK_DEVELOPMENT_TEST_PLAN_V1_20260929.md
EXECUTION_PLAN=docs/development/N3W_AUTO_SAFE_FALLBACK_SOURCE_REPAIR_EXECUTION_PLAN_20260929.md
GATE_A_STATUS_PREDECESSOR=docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_A_MQTT_RETARGET_STATUS_20260929.md
```

Frozen Gate A source authority before physical execution:

```text
SOURCE_HEAD=8210cf7b53e9ec934d145f1c15e9619579c923be
SOURCE_TREE=5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c
TARGET_BLOB=7279271d469958940c2b51aa4a80602078470891
PATCH_BLOB=49570a83ead08158d4d99c385740fa6d646b5e3d
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

## 2. Gate A runtime result

The real ESP32-C6 timing sequence passed. The runtime address-retarget adapter changed only the runtime TCP/TLS destination address and preserved the existing TLS identity and MQTT identity/configuration.

```text
GATE_A_RUNTIME_RESULT=PASS
GATE_A_RUNTIME_BOUNDED_CANCEL_PROVEN=true
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=true

LIVE_RECONNECT_MS=15704
BLACKHOLE_ACTIVE_RECOVER_MS=8711
BLACKHOLE_ACTIVE_API_MS=0
BLACKHOLE_WAIT_RECOVER_MS=12960
BLACKHOLE_WAIT_API_MS=0

MQTT_STAGE_BUDGET_MS=25000
BLACKHOLE_ACTIVE_WITHIN_BUDGET=true
BLACKHOLE_WAIT_WITHIN_BUDGET=true
```

The successful physical sequence proved the minimum backend prerequisite required before implementing the complete safe-fallback flow. It does not by itself implement discovery reuse, candidate filtering, recovery-state integration, or end-to-end T1 address migration.

## 3. Temporary T1 lab cleanup

The isolated Gate A lab was removed after the runtime test.

```text
GATE_A_T1_LAB_CLEANUP=PASS
ISOLATED_BROKER_18883=false
LIVE_ALIAS_ACTIVE=false
REMOTE_PRIVATE_LAB_REMOVED=true
BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=1
PRODUCTION_BROKER_MUTATION=false
MANAGER_MUTATION=false
T1_LAB_RESIDUE=false
```

`MANAGER_RESTART_COUNT=1` is the previously documented expected consequence of the user's intentional T1 restart/network move and is not classified as a Gate A failure.

No private LAN candidate address, private key, password, private bundle path, or secret-bearing raw runtime log is recorded in this public document.

## 4. Board B exact KF-099 rollback

Board B was restored with the exact accepted KF-099 application/OTA-data pair.

```text
BOARD_B_KF099_ROLLBACK_PREFLIGHT=PASS
BOARD_B_KF099_ROLLBACK_WRITE=PASS

BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
APPLICATION_SHA256=d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
PRODUCT_NVS_WRITE=false
PARTITION_TABLE_WRITE=false
BOOTLOADER_WRITE=false
FULL_FLASH_ERASE=false
T1_MUTATION=false
```

The rollback authorization is consumed and must not be replayed.

## 5. Post-rollback pairing continuity

A read-only Board B serial observation proved that the rollback preserved the historical KF-099 pairing transaction instead of generating a new one.

```text
PAIRING_TRANSACTION_PRESERVED=true
PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
PAIRING_ID_HASH_MATCH_HISTORICAL_KF099=true
```

A later authorized **reset-only** Board B reboot was used to reinitialize the Wi-Fi state machine. It did not write flash, clear Wi-Fi credentials, alter N3-W pairing/NVS/identity state, or mutate T1. After reboot, the existing Wi-Fi configuration reconnected successfully on its second attempt and the pairing transaction hash remained unchanged.

```text
CONTROLLED_RESET_EXECUTED=true
RESET_AUTHORIZATION_CONSUMED=true
BOARD_FLASH=false
PRODUCT_NVS_WRITE=false
PAIRING_MUTATION=false
T1_MUTATION=false
POST_RESET_WIFI_CONNECTED=true
```

## 6. Valid post-rollback KF-099 WAIT observation

T1 does not have `tcpdump`, and earlier commands using remote `timeout ... tcpdump` exited before capture. Those empty captures are explicitly invalid negative evidence and must not be used to claim absence of pairing traffic.

A replacement 60-second read-only raw-socket observation on T1 `eth0` produced valid complete TCP stream evidence:

```text
CAPTURE_SECONDS=60
BOARD_B_IPV4_PACKET_COUNT=168
IP_FRAGMENTED_PACKET_COUNT=0
TCP47112_CLIENT_CONNECTION_COUNT=12
HELLO_COUNT=12
PAIRING_ID_UNIQUE_COUNT=1
PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
REPAIR_INTENT_REQUIRED_COUNT=12
BEGIN_COUNT=0
CLIENT_STREAM_GAP_COUNT=0
SERVER_STREAM_GAP_COUNT=0
CLIENT_CAPTURE_COMPLETE=true

BOARD_RESET=false
BOARD_FLASH=false
PRODUCT_NVS_WRITE=false
PAIRING_MUTATION=false
T1_PERSISTENT_MUTATION=false
```

This proves the restored Board B resumed the accepted KF-099 behavior:

```text
same historical pairing transaction
-> discovery succeeds
-> /v2/pairing/hello repeats
-> Manager returns repair_intent_required
-> client remains WAIT
-> /v2/pairing/begin is suppressed
```

### Observer-counter correction

Two local observer counters from that run were mislabeled and are **not product defects**:

1. the observer searched for `gh.discovery.request`, while the firmware actually emits `gh.discovery.query/1`; the run observed 12 `gh.discovery.response/1` responses and 12 subsequent hello connections, which proves discovery was functioning;
2. the observer searched for JSON key `nonce`, while the hello request uses `node_nonce`; the firmware source generates a fresh 32-byte random `node_nonce` for every `send_hello_()` call.

Therefore these two printed values are invalid measurements and must not be interpreted as product evidence:

```text
DISCOVERY_REQUEST_COUNT=0   # invalid label/parser
HELLO_DISTINCT_NONCE_COUNT=0 # invalid field parser
```

Historical KF-099 physical acceptance already proved 18 distinct hello nonces with this exact product source and pairing transaction.

## 7. Gate A closure

```text
GATE_A_SOURCE_ADAPTER=PASS
GATE_A_SOURCE_CONTRACT_TEST=PASS
GATE_A_EXACT_COMPILE=PASS
GATE_A_RUNTIME_RESULT=PASS
GATE_A_RUNTIME_BOUNDED_CANCEL_PROVEN=true
GATE_A_T1_LAB_CLEANUP=PASS
GATE_A_T1_LAB_RESIDUE=false
BOARD_B_KF099_ROLLBACK=PASS
PAIRING_TRANSACTION_PRESERVED=true
KF099_POST_ROLLBACK_WAIT_BEHAVIOR=PASS
BEGIN_SUPPRESSION=PASS

GATE_A_PHYSICAL_CLOSURE_COMPLETE=true
GATE_A=PASS
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=true

FULL_AUTO_FALLBACK_SOURCE_REPAIR_COMPLETE=false
FULL_AUTO_FALLBACK_PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
PR516_DRAFT=true
MERGE=false
```

## 8. Next gate

Gate A is closed. The next and only active gate for this route is **Gate B — discovery 与配对流程解耦**.

Gate B is source/test work only at entry. It does not require live Board/T1 mutation.

Required V1 behavior:

- extract reusable discovery query/response protocol logic without routing already-provisioned nodes through `SimplePairingClient::run_once()`;
- fresh request ID and nonce per discovery round;
- collect responses rather than accepting only the first;
- parse at most 8 responses, retain at most 3 deduplicated candidates, attempt at most 2 addresses;
- validate `system_id`, IPv4 unicast, same-subnet, and source-IP == advertised-host;
- keep Broker port from the durable trusted Broker record;
- discovery response must not overwrite CA, TLS server name, username/password/client_id, NODE_ID/SYSTEM_ID, peer trust, or other durable identity;
- no NVS persistence of discovered candidate addresses;
- stop when the pure protocol/filter tests pass; do not automatically enter Gate C.

```text
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_EXECUTE_GATE_C=false
```
