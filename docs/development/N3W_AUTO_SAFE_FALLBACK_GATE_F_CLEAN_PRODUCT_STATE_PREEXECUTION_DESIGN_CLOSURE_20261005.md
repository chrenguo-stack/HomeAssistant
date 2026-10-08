# N3-W Auto Safe Fallback Gate F — Clean Product-State Preexecution Design Closure — 2026-10-05

```text
TASK=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01
STATUS=CLOSED_WITH_BLOCKER
DESIGN_CLOSURE=COMPLETE
PHYSICAL_EXECUTION_READY=false
BOARD_ACCESS=false
T1_MUTATION=false
SOURCE_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
RECOVERY_FLOOR_EXECUTION=false
MERGE=false
```

## 1. Fresh authority rebind

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR=522
PR_STATE_BEFORE_CLOSURE=OPEN_DRAFT
PR_MERGED_BEFORE_CLOSURE=false
PR_HEAD_BEFORE_CLOSURE=14c02dce804d03d0b86b5748735c15fc27c0dab7
R2_SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
R2_SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
R2_RELOCATION_SOURCE_DEFECT_PROVEN=false
```

The handoff process authority remains the exact historical authority at:

```text
4300890dff0ce63d5a547df21426e287d084d9ee
```

Current product/process authorities include:

```text
docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PROGRESS_ALIGNMENT_20261005.md
docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_F_R2_POST_MQTT_TELEMETRY_FORENSIC_20261004.md
docs/development/KF-050_N3W_BOOT_SESSION_CONTRACT_REPAIR.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
docs/adr/0008-n3w-pairing-recovery-simplification-v2.md
docs/development/N3W_GATE_F_INDEPENDENT_REVIEW_AND_CLEAN_BOARD_PLAN_20261005.md
```

## 2. Board B facts remain frozen

```text
BOARD_B_R2_STALE_BROKER_FALLBACK_CHAIN=PHYSICALLY_PROVEN
BOARD_B_MANAGER_DISCOVERY=PASS
BOARD_B_RAM_ONLY_BROKER_RETARGET=PASS
BOARD_B_MQTT_RECOVERY=PASS
BOARD_B_BROKER_TO_MANAGER_DELIVERY=PASS
BOARD_B_CANONICAL_FAILURE_DIRECT_REASON=KF050_HISTORICAL_BOOT_SESSION_HIGH_WATER
BOARD_B_R2_SOURCE_DEFECT=false
BOARD_B_FINAL_CLEAN_ACCEPTANCE_TARGET=false
```

Manager replay relaxation, replay/high-water clearing, and recovery-floor helper use remain forbidden as Final Product Acceptance mechanisms.

## 3. Fresh T1 read-only authority

The current production T1 was re-read without mutation. Private LAN values were intentionally not emitted.

```text
READ_ONLY=true
T1_MUTATION=false
BOARD_ACCESS=false

MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=1
MANAGER_NETWORK_MODE_HOST=true

BROKER_RUNTIME_RESOLUTION=PASS
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
BROKER_RESTART_POLICY_NO=true
BROKER_8883_WILDCARD_PUBLICATION=true
BROKER_NETWORK_SET_EXACT=true

PAIRING_ADVERTISED_HOST_MODE=auto
NODE_BROKER_HOST_KIND=ipv4
NODE_BROKER_HOST_IS_CURRENT_ETH0_IPV4=false
NODE_BROKER_PORT_8883=true
NODE_BROKER_TLS_NAME_KIND=hostname
NODE_BROKER_TLS_NAME_PRESENT=true

ETH0_NETWORKMANAGER_CONNECTED=true
ETH0_GLOBAL_IPV4_COUNT=1
ETH0_UNIQUE_IPV4_SUBNET_COUNT=1
ETH0_PREFIXLEN_SET=24
DEFAULT_ROUTE_VIA_ETH0=true

BROKER_GUARD_ACTIVE=active
BROKER_GUARD_ENABLED=enabled
DOCKER_USER_8883_ANCHOR_POSITIONS=1
INPUT_8883_ANCHOR_POSITIONS=1
BROKER_GUARD_LOOPBACK_RETURN=true
BROKER_GUARD_ETH0_RETURN=true
BROKER_GUARD_TERMINAL_DROP=true

TCP_8883_LISTENING=true
UDP_47111_LISTENING=true
TCP_47112_LISTENING=true
PRIVATE_LAN_VALUES_EMITTED=false
```

`MANAGER_BROKER_ENDPOINT_LOOPBACK_IPV4=false` from this probe is not promoted to a deployment failure. The probe only tested whether the configured value itself is a literal IPv4 loopback address; it did not establish the resolved runtime route. No mutation is authorized to investigate or change it in this gate.

The material finding for clean-board Gate F is:

```text
CURRENT_PAIRING_NODE_BROKER_HOST_IS_CURRENT_T1_IPV4=false
```

Therefore the present live configuration must not be assumed to provide a healthy initial Broker endpoint to a newly paired board.

## 4. Fresh higher-authority blocker discovered after handoff

PR #522 advanced after the handoff with:

```text
docs/development/N3W_GATE_F_INDEPENDENT_REVIEW_AND_CLEAN_BOARD_PLAN_20261005.md
```

That review identified an inherited KF-050 first-pair boot-session initialization window. Direct reinspection of the frozen R2 source confirms the relevant sequence:

1. `GreenhouseN3wCore::setup()` computes `fresh_identity_candidate_` from whether valid persisted peer/Broker identity already exists.
2. `SimplePairingClient::persist_bundle_()` persists peer, Broker and pending pairing acknowledgement state but does not create the durable boot-session counter.
3. `GreenhouseN3wCore::take_telemetry_identity()` calls `begin_boot_session_if_needed_()` only when telemetry identity is requested.
4. If power/reboot occurs after durable pairing identity exists but before the first telemetry identity request initializes `gh_n3w/boot_state`, the next process starts with persisted product identity and `fresh_identity_candidate_=false`.
5. `begin_boot_session_if_needed_()` then sees a missing counter and correctly fails closed because the process no longer qualifies as a fresh identity candidate.

Classification:

```text
KF050_FIRST_PAIR_INITIALIZATION_GAP=CONFIRMED_SOURCE_LEVEL
CLASSIFICATION=INHERITED_PRODUCT_CORRECTNESS_GAP
R2_RELOCATION_REGRESSION=false
CLEAN_PRODUCT_RELEASE_BLOCKER=true
SOURCE_FOLLOWUP_REQUIRED=true
```

This does not reopen the Board B R2 relocation conclusion. It blocks using the current R2 artifact as the final clean-product release artifact.

## 5. Clean-board eligibility contract — frozen

A future clean-board physical gate must first be read-only and explicitly authorized.

A candidate qualifies only if all of the following are proven:

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
MANAGER_OLD_NODE_BINDING_FOR_HARDWARE_ABSENT=true
MANAGER_OLD_REPLAY_IDENTITY_FOR_TARGET_ABSENT=true
```

`BRAND_NEW_UNUSED_BOARD=true` is an input, not acceptance evidence.

If historical N3-W state is found during read-only eligibility inspection:

```text
CLEAN_BOARD_ELIGIBILITY=FAIL
AUTO_ERASE_TO_HIDE_HISTORY=false
STOP=true
```

Once source repair is accepted and a new exact artifact is bound, authorized clean initialization should use that single exact artifact as the authority for bootloader, partition table, OTA metadata and application offsets. Board B's previous minimal two-region write must not be copied to a clean board.

No Board B NVS, credential, setup secret, boot floor, pairing epoch or legacy helper state may be imported.

## 6. First-pair correctness prerequisite — frozen

Before stale-Broker Gate F is allowed to start, the KF-050 first-pair initialization gap must be closed by source repair and regression evidence.

The repair contract is intentionally narrow:

```text
INITIAL_BOOT_FLOOR_CREATED_ONLY_FOR_PROVEN_FRESH_IDENTITY=true
INITIAL_BOOT_FLOOR_DURABLE_BEFORE_FINAL_IDENTITY_COMMIT=true
INITIAL_BOOT_FLOOR_READBACK_VERIFIED=true
EXISTING_PROVISIONED_IDENTITY_PLUS_MISSING_COUNTER_FAILS_CLOSED=true
EXISTING_COUNTER_NEVER_LOWERED_OR_OVERWRITTEN=true
CORRUPT_OR_IO_ERROR_FAILS_CLOSED=true
MANAGER_REPLAY_RELAXATION=false
LEGACY_RECOVERY_FLOOR_AS_NORMAL_PRODUCT_PATH=false
R2_RELOCATION_BEHAVIOR_UNCHANGED=true
```

Required regression cases include interruption/restart around the first pairing persistence boundary and before first telemetry identity issuance.

Any source change invalidates the current R2 exact artifact as Final Acceptance authority. The Board B R2 artifact remains valid historical evidence for relocation behavior only; a new source/tree/exact artifact must be built and bound before clean-board physical acceptance.

## 7. Healthy initial Broker baseline contract — frozen

Final stale-Broker acceptance must begin from a genuinely healthy durable Broker address.

Fresh T1 evidence currently proves:

```text
GH_N3W_PAIRING_ADVERTISED_HOST_MODE=auto
GH_N3W_NODE_BROKER_HOST_IS_CURRENT_ETH0_IPV4=false
```

Therefore the current T1 state is not directly eligible for clean-board healthy-baseline pairing.

Before clean-board pairing, a separate explicitly authorized T1 preparation gate must make the node credential Broker host equal the then-current real T1 LAN IPv4 address `A` and prove Broker TCP/TLS availability at `A:8883`. If that preparation requires Manager recreation/restart, it must occur before the formal baseline; after baseline starts, Manager/Broker restart counts and container identity are frozen.

Private address `A` must be derived live and never committed to the public repository.

## 8. Stale-Broker oracle — frozen

The Final Product Acceptance oracle is a real T1 LAN address relocation, not a board-NVS edit and not a fake discovery response.

```text
INITIAL_REAL_T1_ADDRESS=A
NEW_REAL_T1_ADDRESS=B
INITIAL_DURABLE_BOARD_BROKER=A
PAIRING_ADVERTISED_HOST_MODE=auto
BOARD_WIFI_NETWORK_UNCHANGED=true
BOARD_IDENTITY_UNCHANGED=true
BOARD_NVS_MUTATION_DURING_RELOCATION=false
MANAGER_RESTART_DURING_RELOCATION=false
BROKER_RESTART_DURING_RELOCATION=false
OLD_ADDRESS_A_RETAINED_AS_ALIAS=false
NAT_FORWARDER_FOR_A=false
DNS_ONLY_ORACLE=false
FAKE_DISCOVERY_ORACLE=false
```

Execution may proceed only after a future live preflight proves the selected A->B change is safe, conflict-free and reversible, including NetworkManager, DHCP/static addressing, route, Docker publication, ingress guard and recovery access.

A rollback mechanism must remain usable even if SSH to the old address is lost. If reliable rollback cannot be proven before the address change:

```text
STALE_BROKER_ORACLE_ELIGIBLE=false
STOP=true
```

## 9. Final Gate F acceptance contract — frozen

Final release acceptance requires both the first-pair correctness repair and the stale-Broker relocation path.

### 9.1 Clean product initialization

```text
NEW_REPAIRED_EXACT_ARTIFACT_BOUND=true
CLEAN_BOARD_ELIGIBILITY=PASS
FORMAL_PRODUCT_FLASH=PASS
LEGACY_HELPER_USED=false
FORMAL_PAIRING=PASS
PAIRING_COMMIT=PASS
INITIAL_BOOT_SESSION_VALID=true
INITIAL_CANONICAL_TELEMETRY_COUNT>=2
INITIAL_CANONICAL_SEQ_STRICTLY_ADVANCES=true
```

### 9.2 First-pair interruption regression

A controlled test must prove that an interruption/restart in the repaired first-pair initialization boundary cannot leave a normally paired clean product in the unrecoverable `identity present + boot_state missing` condition.

```text
KF050_FIRST_PAIR_INTERRUPTION_ACCEPTANCE=PASS
REPLAY_RELAXATION_USED=false
RECOVERY_FLOOR_USED=false
```

### 9.3 Healthy stale-Broker baseline

Before relocation:

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
```

### 9.4 A->B relocation

After real address A is removed and B becomes the real T1 address:

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

R2 source constants freeze the relocation timing facts:

```text
MQTT_FAILURE_TRIGGER=10000ms
DISCOVERY_COLLECTION_BUDGET=1000ms
CANDIDATE_BUDGET=6000ms
CLEANUP_RESERVE=2000ms
DISCOVERY_MIN_INTERVAL=60000ms
NO_RELAY_PRODUCT_ACCEPTANCE_LIMIT=120s
```

The 120-second value is the Final Product Acceptance ceiling for the real relocation recovery, not a claim that every standalone relocation source path is terminated by one shared 120-second timer.

After candidate promotion, preserve the production telemetry cadence. Observe up to 180 seconds and require at least two Manager-accepted canonical advances rather than shortening telemetry cadence for the test.

### 9.5 Cold-start revalidation on B

With T1 remaining at B, perform one controlled node reboot only after the first relocation acceptance has passed.

Required:

```text
BOARD_DURABLE_BROKER_STILL_A=true
NODE_REDODISCOVERS_B_WITHOUT_REPAIR_PAIRING=true
BOOT_SESSION_MONOTONICALLY_ADVANCES=true
CANONICAL_TELEMETRY_CONTINUES=true
MANAGER_RESTARTED=false
BROKER_RESTARTED=false
```

## 10. PASS / FAIL / STOP semantics

```text
PASS=all frozen product predicates satisfied on the repaired exact artifact
FAIL=valid controlled environment and bindings, but product behavior violates a predicate
STOP_OR_INVALID=identity/artifact/network/rollback/environment precondition cannot be proven
```

A STOP/INVALID result must never be promoted to PASS by clearing replay state, editing board durable Broker state, executing recovery-floor, restarting Manager during relocation, retaining the old address, or changing timing after failure.

## 11. Rollback contract — frozen

No rollback operation in Final Acceptance may restore old board NVS or Manager replay/high-water snapshots.

Before any future T1 mutation, snapshot and hash the exact private runtime/network authority needed to restore:

```text
NetworkManager connection/profile state
current interface addressing and routes
Manager/Broker container identity and restart counts
rendered deployment/publication state
ingress guard state
private Manager environment source needed for GH_N3W_NODE_BROKER_HOST
```

T1 preparation rollback and A->B relocation rollback must be designed as explicit future mutation gates.

If a clean board has completed formal pairing and a later acceptance step fails, that physical run remains evidence. Do not erase/re-pair it merely to obtain a clean-looking PASS. A new clean-state retry requires a separately qualified clean state and must not clear Manager historical replay authority.

## 12. Gate disposition

```text
CLEAN_BOARD_ELIGIBILITY_CONTRACT=FROZEN
STALE_BROKER_ORACLE=FROZEN
ROLLBACK_REQUIREMENTS=FROZEN
FINAL_ACCEPTANCE_CONTRACT=FROZEN

CURRENT_R2_RELOCATION_DESIGN=FROZEN
CURRENT_R2_EXACT_ARTIFACT_FINAL_RELEASE_AUTHORITY=false
PHYSICAL_CLEAN_BOARD_EXECUTION_AUTHORIZED=false
T1_PRECONDITIONING_AUTHORIZED=false
PR_522_MERGE=false
```

The current design gate is closed. Physical execution must not begin from this closure because the newly re-bound PR authority contains a confirmed first-pair KF-050 product-correctness blocker.

```text
NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_SOURCE_REPAIR_DESIGN_20261005_01
```

That successor begins with source-design work only. It does not authorize board access, T1 mutation, replay/high-water changes, recovery-floor execution or PR merge.
