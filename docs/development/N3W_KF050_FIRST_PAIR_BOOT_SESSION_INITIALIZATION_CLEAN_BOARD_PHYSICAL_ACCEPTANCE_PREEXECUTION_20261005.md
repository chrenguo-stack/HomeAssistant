# N3-W KF-050 First-Pair Boot-Session Initialization — Clean-Board Physical Acceptance Preexecution — 2026-10-05

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261005_01
STATUS=CLOSED_PASS
PREEXECUTION_DESIGN=PASS
BOARD_ACCESS=false
BOARD_WRITE=false
FLASH_ERASE=false
FLASH_WRITE=false
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
RECOVERY_FLOOR_EXECUTION=false
MERGE=false
```

## 1. Fresh authority binding

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR=522
PR_STATE=OPEN_DRAFT
PR_HEAD_AT_ENTRY=8640d62117d759ff0b149107856422b81b7a76f9
PR_BASE=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75

SOURCE_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
SOURCE_REPAIR=PASS

WORKFLOW_RUN_ID=37249933019
ARTIFACT_ID=11320812037
ARTIFACT_NAME=n3w-kf050-first-pair-f1rc2-157448b-exact-source
ARTIFACT_OUTER_SHA256=7f1d775bd2c15152b96ad6802e24ec64789fd1c7cd49cf66498c83eb25b8ee52
RELEASE_ZIP_SHA256=44610382a0e7d9c04e4445e873b9d99fd9a781d18fd497f39cb382d3fce3b3ff
FIRMWARE_BIN_SHA256=4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b
```

The KF-050 source repair and the replacement exact artifact are now closed. The former clean-product design blocker is therefore removed. Physical acceptance may proceed only through the staged gates below; this preexecution gate itself authorizes no live mutation.

## 2. What the physical acceptance must prove

The final clean-product route must prove all of the following on the repaired exact artifact:

```text
A. the target board was genuinely clean before any write
B. the board receives the full exact production image from one artifact
C. first pairing creates a valid product identity without legacy recovery helpers
D. power interruption before first accepted production telemetry does not create identity-without-boot-state lockout
E. healthy Direct MQTT starts from the real T1 address A
F. the real T1 address changes A -> B while board Wi-Fi and identity remain unchanged
G. the same running Manager discovers B and the node performs RAM-only Broker retarget
H. production canonical telemetry continues without pairing repair or replay/high-water clearing
I. with T1 still at B, one controlled node cold start rediscovers B from durable A and advances boot session monotonically
```

Board B remains historical R2 relocation evidence only and is not a clean-product acceptance target.

## 3. Staged execution model and STOP points

The physical route is split deliberately. No later gate is allowed to repair or hide a failed earlier gate.

### Stage P1 — clean-board eligibility, read-only only

Frozen successor:

```text
NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261005_01
```

This stage may connect exactly one candidate ESP32-C6 to the Mac and perform read-only ROM/eFuse/flash inspection. It must not erase or write flash.

Required PASS predicates:

```text
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
HARDWARE_ID_UNIQUE=true
HARDWARE_ID_NOT_BOARD_A=true
HARDWARE_ID_NOT_BOARD_B=true
OLD_N3W_PEER_STATE_ABSENT=true
OLD_N3W_BROKER_STATE_ABSENT=true
OLD_N3W_PENDING_PAIRING_STATE_ABSENT=true
OLD_N3W_BOOT_STATE_ABSENT=true
OLD_N3W_SETUP_OR_PAIRING_RESIDUE_ABSENT=true
MANAGER_OLD_REGISTRATION_FOR_HARDWARE_ABSENT=true
MANAGER_OLD_CREDENTIAL_HISTORY_FOR_HARDWARE_ABSENT=true
MANAGER_OLD_REPLAY_BINDING_FOR_TARGET_ABSENT=true
```

The board-side clean-state inspection must treat the current production storage names as authoritative:

```text
gh_n3w_v2/peer
gh_n3w_v2/broker
gh_n3w_v2/pair_ack
gh_n3w_v2/pair_intent
gh_n3w_v2/setup
gh_n3w_v2/pair_epoch
gh_n3w/boot_state
```

The read-only executor should:

1. bind and verify the exact artifact before touching the serial port;
2. require esptool v5;
3. read ROM/security information and flash geometry;
4. derive a public-safe hardware identity hash, while keeping raw MAC/private locator outside public GitHub evidence;
5. read and privately retain a raw pre-write flash snapshot or the complete set of partitions required to prove historical N3-W state absence;
6. decode the current partition table without assuming it already equals the production artifact partition table;
7. inspect every relevant NVS partition offline for the keys above;
8. perform Manager registration/credential/replay read-only checks bound to the candidate hardware identity;
9. emit only secret-free hashes/classifications to the public evidence record.

For a brand-new candidate, the existing factory partition table is not required to equal the product artifact partition table. A mismatch is not itself a failure. Ambiguous or unreadable persistent state is STOP/INVALID, not PASS.

If any prior N3-W product identity or pairing residue is discovered:

```text
CLEAN_BOARD_ELIGIBILITY=FAIL
ERASE_TO_MANUFACTURE_CLEAN_STATE=false
STOP=true
```

### Stage P2 — T1 healthy-Broker-A preparation

This stage starts only after Stage P1 passes and requires separate explicit mutation authorization.

Current read-only T1 evidence has already shown that the configured node Broker host is not the current T1 LAN IPv4. Therefore the current T1 state cannot be used as the initial healthy pairing baseline.

Before board pairing, T1 preparation must:

```text
PAIRING_ADVERTISED_HOST_MODE=auto
REAL_T1_ADDRESS=A
NODE_CREDENTIAL_BROKER_HOST=A
BROKER_TCP_TLS_A_8883=PASS
MANAGER_DISCOVERY_AUTO_SOURCE=A
```

Before any T1 mutation, privately snapshot/hash:

```text
NetworkManager connection/profile
interface addressing and routes
Manager container identity/StartedAt/restart count
Broker container identity/StartedAt/restart count
rendered deployment/publication state
ingress guard state
private configuration source for GH_N3W_NODE_BROKER_HOST
```

Manager/Broker recreation or restart is allowed only in this preparation stage if required. Once the formal board baseline begins, container identity and restart counts are frozen.

The address A remains private evidence and must not be committed to the public repository.

### Stage P3 — clean initialization and exact full-product flash

Only after Stage P1 PASS and Stage P2 PASS may board mutation begin.

A full erase may be authorized only after the board has already been independently proven clean. The erase is then a formal clean initialization action; it is never evidence that the board was clean beforehand.

The exact artifact `flash_args` freezes the production write layout:

```text
FLASH_MODE=dio
FLASH_FREQ=80m
FLASH_SIZE=8MB
0x0000  bootloader.bin
0x8000  partitions.bin
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

The clean-board write must use all four regions from the same bound release ZIP. The historical Board B two-region minimal write is forbidden for this route.

After write, each written region must be read back and hash-verified against the bound artifact before formal pairing starts.

### Stage P4 — first-pair + KF-050 physical interruption acceptance

The board must use the ordinary production provisioning route only:

```text
LEGACY_RECOVERY_HELPER=false
RECOVERY_FLOOR_EXECUTION=false
BOARD_B_STATE_IMPORT=false
MANAGER_REPLAY_CLEAR=false
MANAGER_HIGH_WATER_CLEAR=false
```

The preferred single-board sequence is:

```text
clean first boot
-> boot floor 0 is prepared by repaired product startup
-> ordinary pairing reaches Manager COMMIT
-> prove no production canonical telemetry has yet been accepted for this new identity
-> perform one controlled power interruption/reboot
-> no re-pairing and no NVS repair
-> product recovers
-> initial valid boot session is issued
-> Manager accepts production telemetry
-> at least two canonical seq advances occur
```

The interruption must occur after pairing COMMIT but before the first accepted canonical production telemetry for the new identity. If timing/evidence is ambiguous or the first canonical telemetry has already occurred, the interruption test is INVALID, not product FAIL.

Do not erase/re-pair the same board merely to retry a missed timing window. A second separately qualified clean board may be used for the interruption proof if required. A board that cleanly passes the interruption test may continue into the stale-Broker acceptance route.

Required first-pair PASS predicates:

```text
FORMAL_PAIRING=PASS
PAIRING_COMMIT=PASS
KF050_FIRST_PAIR_INTERRUPTION_ACCEPTANCE=PASS
PAIRING_REPAIR=false
INITIAL_BOOT_SESSION_VALID=true
INITIAL_CANONICAL_TELEMETRY_COUNT>=2
INITIAL_CANONICAL_SEQ_STRICTLY_ADVANCES=true
```

### Stage P5 — freeze healthy Direct baseline on A

After the first-pair interruption test passes:

```text
DURABLE_BROKER_HOST=A
DIRECT_MQTT_TO_A=PASS
MANAGER_CANONICAL_BASELINE=PASS
MANAGER_CONTAINER_ID_FROZEN=true
BROKER_CONTAINER_ID_FROZEN=true
MANAGER_RESTART_COUNT_FROZEN=true
BROKER_RESTART_COUNT_FROZEN=true
TLS_CA_AND_SERVER_NAME_HASH_FROZEN=true
MQTT_IDENTITY_HASH_FROZEN=true
BOARD_IDENTITY_FROZEN=true
```

The board remains powered and on the same Wi-Fi network for the following relocation test.

### Stage P6 — real T1 address relocation A -> B

The stale-Broker oracle remains a real T1 LAN address relocation. It is not a board-NVS edit, alias, NAT forwarder, DNS-only change or fake discovery response.

Before mutation, a separate live preflight must prove the A -> B change is conflict-free, reversible and recoverable even if SSH to A is lost.

Execution contract:

```text
INITIAL_REAL_T1_ADDRESS=A
NEW_REAL_T1_ADDRESS=B
OLD_A_REMOVED=true
OLD_A_RETAINED_AS_ALIAS=false
NAT_FORWARDER_FOR_A=false
BOARD_WIFI_NETWORK_UNCHANGED=true
BOARD_IDENTITY_UNCHANGED=true
BOARD_NVS_MUTATION_DURING_RELOCATION=false
MANAGER_RESTART_DURING_RELOCATION=false
BROKER_RESTART_DURING_RELOCATION=false
```

Required PASS:

```text
OLD_A_UNREACHABLE=PROVEN
MANAGER_DISCOVERY_FROM_SAME_RUNNING_MANAGER=PASS
DISCOVERY_RESPONSE_SOURCE_EQUALS_B=true
DISCOVERY_CANDIDATE_HOST_EQUALS_B=true
RAM_ONLY_BROKER_RETARGET_TO_B=PASS
MQTT_TLS_RECONNECT_TO_B=PASS
BROKER_CANDIDATE_PROMOTION=PASS
DURABLE_BROKER_HOST_REMAINS_A=true
PAIRING_REPAIR=false
MANAGER_REPLAY_CLEAR=false
MANAGER_HIGH_WATER_CLEAR=false
```

Product acceptance ceiling for A -> usable B recovery remains 120 seconds. The 10 s MQTT failure trigger, 1 s discovery collection, 6 s candidate budget, 2 s cleanup reserve and 60 s discovery minimum interval are recorded as implementation timing facts, not separate PASS shortcuts.

After promotion, keep the production telemetry cadence unchanged. Observe up to 180 seconds and require at least two Manager-accepted canonical advances.

### Stage P7 — cold-start revalidation while T1 remains at B

After Stage P6 PASS, perform exactly one controlled node reboot with T1 still at B.

Required:

```text
BOARD_DURABLE_BROKER_STILL_A=true
NODE_REDODISCOVERS_B_WITHOUT_REPAIR_PAIRING=true
BOOT_SESSION_MONOTONICALLY_ADVANCES=true
CANONICAL_TELEMETRY_CONTINUES=true
MANAGER_RESTARTED=false
BROKER_RESTARTED=false
```

Only after this passes may the clean-product stale-Broker acceptance be closed.

## 4. PASS / FAIL / STOP rules

```text
PASS=all predicates for the current authorized stage are proven
FAIL=environment and binding are valid, but product behavior violates an acceptance predicate
STOP_OR_INVALID=identity/artifact/network/rollback/timing evidence is ambiguous or a prerequisite is not proven
```

STOP/INVALID must never be converted to PASS by:

```text
erasing the board to hide history
re-pairing after a failed run
editing durable Broker state
clearing Manager replay/high-water
lowering a boot counter
using legacy recovery-floor helpers
retaining A as an alias
restarting Manager/Broker during relocation
extending timing limits after a failure
```

## 5. Evidence policy

Public GitHub evidence may contain source/tree/artifact hashes, public-safe hardware identity hashes, classifications, timings and secret-free state transitions.

Private evidence root must retain any raw material containing:

```text
raw ROM MAC / serial locator
raw flash or NVS snapshot
Setup Secret / pairing material
MQTT username/password/client identity material
CA/private runtime credential detail
real private LAN addresses A/B
raw packet captures or logs that expose the above
```

Do not publish raw private evidence solely to make the gate reproducible; publish hashes and secret-free summaries instead.

## 6. Full-channel fallback physical validation remains a separate item

PR #474 source review and automated/host regressions are PASS, but PR #474 explicitly remains physically unvalidated for the new full-channel RF fallback behavior.

```text
FULL_CHANNEL_FALLBACK_SOURCE=PASS
FULL_CHANNEL_FALLBACK_CI=PASS
FULL_CHANNEL_FALLBACK_PHYSICAL_RF_ACCEPTANCE=PENDING
```

That test must remain separate from this clean-board stale-Broker Gate F:

```text
CLEAN_BOARD_GATE_F_USES_SIMPLE_STABLE_WIFI=true
DUAL_AP_FULL_CHANNEL_TEST_MIXED_INTO_GATE_F=false
```

Before final PR #522 merge disposition, the project must explicitly account for both independent product axes:

```text
CLEAN_PRODUCT_STALE_BROKER_ACCEPTANCE
FULL_CHANNEL_FALLBACK_PHYSICAL_RF_ACCEPTANCE
```

A PASS on one does not imply a PASS on the other.

## 7. Gate disposition

```text
PREEXECUTION_DESIGN=PASS
EXACT_ARTIFACT_READY=true
CLEAN_BOARD_PHYSICAL_MUTATION_READY=false
BOARD_ACCESS=false
BOARD_WRITE=false
T1_MUTATION=false
PR522_MERGE=false

NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261005_01
STOP=true
```

The next gate is read-only. It may connect one candidate new board and inspect it, but it may not erase or write any flash and may not mutate T1.