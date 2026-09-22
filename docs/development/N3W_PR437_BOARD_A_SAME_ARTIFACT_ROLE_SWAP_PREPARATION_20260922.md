# N3-W PR #437 Board A same-artifact role-swap preparation — 2026-09-22

Status: `BOARD_A_SAME_ARTIFACT_WRITE_PASS; BOARD_A_POSTWRITE_DIRECT_BASELINE_PASS; BOARD_B_GATEWAY_DIRECT_BASELINE_PASS; ROLE_SWAP_PHYSICAL_PENDING`

Canonical board-write procedure: `docs/development/N3W_ESP32C6_EXACT_ARTIFACT_BOARD_WRITE_RUNBOOK_V1.0_20260922.md`

## Purpose

Synchronize Board A to the exact physical-harness firmware already used for the final Board B PR #437 physical runs, then test the opposite role assignment:

```text
Board B = Direct / Gateway
Board A = Relay Child after Direct loss
```

This route is independent of Gateway Selection V1 source implementation. It tests the current PR #437 role symmetry with the exact already-validated harness artifact.

## Exact firmware authority

```text
SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_BLOB=37654481747b21ca51ccecc246bf84ca437ab7a9

WORKFLOW_RUN_ID=35553142523
ARTIFACT_ID=10619047221
ARTIFACT_NAME=n3w-pr437-4270f24-boardb-exact-source
ARTIFACT_ZIP_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895

APPLICATION_SIZE=1145984
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Fresh GitHub metadata on 2026-09-22 shows artifact `10619047221` is still available and expires at `2026-09-28T02:12:40Z`.

Despite the historical artifact name containing `boardb`, the payload was compiled from the generic Phase4 physical target. The board-specific identity and credentials remain in product NVS and are not replaced by this write route.

## Write scope

Only:

```text
0x9000  <- ota_data_initial.bin
0x10000 <- firmware.bin
```

Explicitly excluded:

```text
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

Post-write application readback must match the exact firmware artifact hash and the partition table must remain unchanged. Post-boot OTA-data byte equality is explicitly not a valid verifier because the firmware legitimately updates the OTA-data partition after boot.

## Target-safety sequence

The current Board-B writer cannot be reused unchanged because it deliberately hard-binds the historical Board B identity.

The Board-A executor therefore uses:

1. fresh ROM identity read;
2. ESP32-C6 / 8 MB / security-state / partition-table verification;
3. emit the public-safe fresh silicon hash;
4. explicit operator confirmation that the connected physical target is Board A;
5. require the exact fresh silicon hash to be echoed into the write command;
6. fresh identity re-read immediately before mutation;
7. single-use authorization claim;
8. minimal app + OTA-data write;
9. exact application + partition-table post-write readback; post-boot OTA-data is observation-only and is never compared byte-for-byte with the initial OTA-data image.

The current application contents are deliberately not read or used to distinguish Board A from Board B. Unknown or older pre-write application state is allowed.

A preflight older than 15 minutes cannot be used for the write.

## Role-swap physical sequence after write

Do not move both boards simultaneously.

### P0 — post-write Board A baseline

- boot Board A normally;
- prove Manager-visible Board A Direct telemetry is advancing;
- prove Board B remains healthy;
- keep both in Wi-Fi/Direct coverage long enough to establish a clean baseline.

### P1 — establish Board B as the Gateway side first

- place/keep Board B in the previously validated Direct/Wi-Fi position;
- require stable Board B Direct telemetry before moving Board A;
- no Board B flash, reset, NVS change, or T1 mutation.

### P2 — move Board A to the previous Relay-child position

Keep Board A in the same boot session:

```text
NO_REBOOT=true
NO_POWER_CYCLE=true
NO_USB_REQUIRED=true
```

Move Board A from Direct coverage to the prior remote/no-Wi-Fi test position.

Acceptance:

```text
BOARD_B_SOURCE=direct
BOARD_A_TRANSITION_TO_RELAY=PASS
BOARD_A_RELAY_GATEWAY=BOARD_B
BOARD_A_BOOT_SESSION_UNCHANGED=true
```

Direct -> Relay boundary loss remains allowed by the frozen Option-B contract and must be reported rather than hidden.

### P3 — Relay steady-state

Observe 600 seconds after stable Relay entry.

Required:

```text
BOARD_A_RELAY_600S=PASS
BOARD_A_STEADY_RELAY_MISSING_SEQUENCE_COUNT=0
BOARD_B_DIRECT_REMAINS_HEALTHY=true
MANAGER_RUNTIME_STABLE=true
```

### P4 — optional same-boot return

After the role-symmetry result is captured, moving Board A back into Direct coverage may be used to re-prove Relay -> Direct failback, but it is a separate acceptance sub-step and must not be used to hide a failed B-as-Gateway/A-as-Child result.

## Current stop point

Board A exact-artifact synchronization has completed successfully.

```text
BOARD_A_PREFLIGHT=PASS
BOARD_A_WRITE=PASS
APPLICATION_POSTWRITE_READBACK=PASS
PARTITION_TABLE_POSTWRITE_READBACK=PASS
PRODUCT_NVS_WRITE=false
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
BOARD_A_POSTWRITE_DIRECT_BASELINE=PASS
ROLE_SWAP_PHYSICAL_ACCEPTANCE=NOT_YET_EXECUTED
NEXT_ONE_GATE=N3W_PR437_BOARD_B_GATEWAY_DIRECT_BASELINE_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```


## 2026-09-22 preflight correction

The first fresh Board-A preflight reached the silicon identity guard and stopped before any flash mutation.

```text
ARTIFACT_SIZE_MATCH=PASS
ARTIFACT_SHA256_MATCH=PASS
BOARD_A_PREFLIGHT=STOP
STOP_REASON=historical Board-B hash used as hard exclusion
FLASH_WRITE=false
PRODUCT_NVS_WRITE=false
AUTHORIZATION_CONSUMED=false
```

The stop itself was safe. The admission rule was then reviewed and corrected.

Current rule:

```text
PREWRITE_APPLICATION_HASH_REQUIRED=false
PREWRITE_APPLICATION_HASH_USED_FOR_BOARD_IDENTITY=false
HISTORICAL_BOARD_B_HASH_AS_HARD_EXCLUSION=false
FRESH_ROM_SILICON_HASH_CAPTURE_REQUIRED=true
OPERATOR_TARGET_CONFIRMATION_REQUIRED=true
WRITE_MUST_ECHO_PREFLIGHT_HARDWARE_HASH=true
FRESH_SILICON_REREAD_BEFORE_WRITE=true
```

This supports both existing boards with arbitrary older firmware and future boards whose application region is initially unknown. A blank board with an incompatible or missing partition table remains a separate factory-provisioning case.


## 2026-09-22 Board A write closure

The corrected preflight and one-shot write completed against the operator-confirmed Board A.

```text
BOARD_A_PREFLIGHT=PASS
FRESH_SILICON_IDENTITY_BOUND=true
HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee

BOARD_A_WRITE=PASS
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
APPLICATION_POSTWRITE_READBACK=PASS

OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
OTADATA_POSTBOOT_SHA256=8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
OTADATA_POSTBOOT_BYTE_EQUALITY_ORACLE=false

PARTITION_TABLE_POSTWRITE_READBACK=PASS
PRODUCT_NVS_WRITE=false

AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

The differing post-boot OTA-data hash is expected and is not a failure signal. The application readback and unchanged partition-table readback are the exact post-write byte-level acceptance oracles.

This closes only the Board A firmware synchronization step. It does not yet prove Board A Direct runtime liveness or the B-as-Gateway/A-as-Child role-swap path.

```text
NEXT_ONE_GATE=N3W_PR437_BOARD_A_POSTWRITE_DIRECT_BASELINE_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```


## 2026-09-22 Direct baseline observer stop

The first post-write Direct-baseline observer stopped before the 90-second observation because it attempted to map the connected board's fresh ROM-silicon hardware hash directly through Manager `registrations.hardware_id`.

```text
T1_MANAGER_RUNNING_BEFORE=true
MANAGER_RESTART_COUNT_BEFORE=0
TARGET_MAPPING_COUNT=0
BASELINE_OBSERVATION_STARTED=false
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_AFTER=0
T1_RUNTIME_MUTATION=false
BOARD_MUTATION=false
```

This is classified as an observer-assumption failure, not a Direct-path product failure.

The source review shows that an already-provisioned node loads persisted peer/broker state and operates under its persisted `node_id`. Therefore fresh ROM hardware hash is valid for write-target binding but is not guaranteed to be the correct lookup key for current Manager canonical runtime state.

Corrected observation route:

```text
RUNTIME_NODE_BINDING=BOOT_SESSION_CORRELATION_OR_PERSISTED_NODE_ID
ROM_HARDWARE_HASH_TO_REGISTRATION_DIRECT_JOIN=FORBIDDEN_AS_SOLE_ORACLE
MANAGER_CANONICAL_DURABLE_STATE=AUTHORITATIVE
NEXT_ACTION=CORRECT_OBSERVER_WITHOUT_PRODUCT_MUTATION
```


## 2026-09-22 boot-session correlation race stop

The corrected observer next read the schema-v5 lab diagnostic snapshot and obtained a valid pre-reset boot-session hash, but the subsequent Manager lookup returned zero rows for that boot session.

```text
DIAG_SCHEMA=5
PRE_RESET_BOOT_SESSION_SHA256=8591214425ac4cbb8326f797151e898ba77608d290677417929ff51573d5501b
PRE_RESET_SNAPSHOT_UPTIME_MS=1275797
NVS_FLASH_WRITE=false

T1_MANAGER_RUNNING_BEFORE=true
MANAGER_RESTART_COUNT_BEFORE=0
BOOT_SESSION_MAPPING_COUNT=0
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_AFTER=0
```

Source review shows why this lookup is intrinsically racy: `n3w_canonical_cursors` stores one current row per `node_id`. The esptool NVS read resets the board; if fresh telemetry from the new boot reaches Manager before the old-session lookup runs, the canonical row is overwritten with the new boot session. The replay registry also discards old-session rows when the high-water advances.

Therefore:

```text
PRODUCT_DIRECT_FAILURE_PROVEN=false
OBSERVER_FAILURE_CLASS=CURRENT_ONLY_CURSOR_RESET_RACE
PRE_RESET_BOOT_SESSION_LOOKUP_AFTER_RESET=FORBIDDEN
NEXT_OBSERVER=PRE_SNAPSHOT_CONTROLLED_RESET_BOOT_CHANGE_CORRELATION
```

The next attempt must snapshot Manager first, then deliberately reset only the operator-confirmed Board A, require exactly one canonical node to change boot session and resume fresh Direct telemetry, and only then begin the 90-second same-boot Direct baseline.


## 2026-09-22 Board A post-write Direct baseline closure

The controlled-reset canonical boot-change observer successfully bound the operator-confirmed physical Board A to its live Manager canonical node and completed a 90-second Direct baseline.

```text
BOARD_A_CONTROLLED_RESET=PASS
RESET_PERSISTENT_MUTATION=false

BOARD_A_RUNTIME_BINDING=PASS
BOARD_A_RUNTIME_BINDING_METHOD=CANONICAL_BOOT_CHANGE
BOARD_A_NODE_ID_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5

BOARD_A_CANONICAL_CURSOR_BEFORE=FOUND
BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SEQ_BEFORE=0
BOARD_A_BOOT_SESSION_SHA256_BEFORE=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776

OBSERVATION_SECONDS=90

BOARD_A_CANONICAL_CURSOR_AFTER=FOUND
BOARD_A_SOURCE_AFTER=direct
BOARD_A_SEQ_AFTER=19
BOARD_A_SEQ_DELTA=19
BOARD_A_BOOT_SESSION_SHA256_AFTER=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776
BOARD_A_SAME_BOOT=true

BOARD_A_CANONICAL_ADVANCED=true
BOARD_A_LAST_SOURCE_DIRECT=true
BOARD_A_CANONICAL_DIRECT_BASELINE=PASS

T1_MANAGER_RUNNING_BEFORE=true
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_RESTART_COUNT_UNCHANGED=true
MANAGER_STARTED_AT_UNCHANGED=true

T1_RUNTIME_MUTATION=false
PRODUCT_NVS_MUTATION=false
BOARD_A_FLASH_WRITE=false

N3W_PR437_BOARD_A_POSTWRITE_DIRECT_BASELINE=PASS
```

This result validates the replacement observer contract:

```text
PRE_SNAPSHOT_CONTROLLED_RESET_BOOT_CHANGE_CORRELATION=PASS
ROM_HARDWARE_HASH_RUNTIME_JOIN_REQUIRED=false
PRE_RESET_BOOT_LOOKUP_AFTER_RESET_REQUIRED=false
CURRENT_CANONICAL_CURSOR_RUNTIME_AUTHORITY=true
```

The same boot session established by this baseline is the current Board A physical-acceptance session. Do not reset or power-cycle Board A before the role-swap transition unless this baseline is intentionally discarded and re-established.

```text
NEXT_ONE_GATE=N3W_PR437_BOARD_B_GATEWAY_DIRECT_BASELINE_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```


## 2026-09-22 Board B gateway-side Direct baseline entry

Fresh PR #471 read-back before entry:

```text
PR471_STATE=OPEN_DRAFT
PR471_MERGEABLE=true
PR471_HEAD=dd4be940c241b94adc5b3dc4029f9d216aaecd19
PR471_CI=12_OF_12_PASS
```

Board A same-boot acceptance session remains established from the immediately preceding PASS baseline.

The Board B gateway-side baseline is read-only with respect to T1 and both boards. It does not reset or access Board B physically. Runtime binding uses current Manager canonical state:

- the already-bound Board A public-safe node hash must be present as fresh Direct on the expected same boot;
- exactly one other fresh Direct canonical node must be present;
- that unique other node becomes the Board B candidate for this gate;
- both A and B must remain Direct, same-boot and advancing through a 90-second observation;
- Manager restart count and StartedAt must remain unchanged.

```text
BOARD_A_EXPECTED_NODE_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
BOARD_A_EXPECTED_BOOT_SHA256=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776
BOARD_B_PHYSICAL_RESET=false
BOARD_B_FLASH_WRITE=false
BOARD_A_RESET=false
T1_RUNTIME_MUTATION=false
OBSERVATION_SECONDS=90
```

If there is not exactly one fresh Direct node besides Board A, the observer must stop without guessing Board B identity.


## 2026-09-22 Board B gateway baseline candidate-discovery stop

The first Board-B gateway-side observer required exactly one fresh Direct canonical node other than the already-bound Board A. It stopped safely because no such node was present.

```text
T1_MANAGER_RUNNING_BEFORE=true
MANAGER_RESTART_COUNT_BEFORE=0
OTHER_FRESH_DIRECT_COUNT=0
BOARD_A_RESET=false
BOARD_B_RESET=false
BOARD_A_MUTATION=false
BOARD_B_MUTATION=false
T1_RUNTIME_MUTATION=false
```

This does not prove a Board-B product failure. It proves only that the observation precondition "one other fresh Direct node already visible right now" was not satisfied.

The next observer must enumerate the current canonical inventory before classifying cause. Public output should include only node-id SHA-256, source, sequence, boot-session SHA-256 and cursor age. It must distinguish:

```text
BOARD_B_NOT_PRESENT
BOARD_B_STALE
BOARD_B_PRESENT_NON_DIRECT
MULTIPLE_OTHER_NODES
OBSERVER_BINDING_AMBIGUOUS
```

No Board-B reset, movement, flash/NVS access or identity guess is allowed until this inventory is classified.


## 2026-09-22 Board B canonical inventory resolution

The read-only canonical inventory resolved the earlier zero-fresh-peer stop without any board reset or runtime mutation.

```text
CANONICAL_NODE_COUNT=3

FRESH_BOARD_B_CANDIDATE_NODE_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
FRESH_BOARD_B_CANDIDATE_SOURCE=direct
FRESH_BOARD_B_CANDIDATE_SEQ=59
FRESH_BOARD_B_CANDIDATE_BOOT_SESSION_SHA256=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
FRESH_BOARD_B_CANDIDATE_AGE_SECONDS=4.7

BOARD_A_NODE_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
BOARD_A_SOURCE=direct
BOARD_A_SEQ=224
BOARD_A_BOOT_SESSION_SHA256=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776
BOARD_A_EXPECTED_BOOT_MATCH=true

STALE_OTHER_NODE_SHA256=73cd4e91562d425ec90acd114b622ee448680b5e011742744eb15fe54e9dd497
STALE_OTHER_NODE_SOURCE=direct
STALE_OTHER_NODE_AGE_SECONDS=595750.1

T1_RUNTIME_MUTATION=false
BOARD_A_MUTATION=false
BOARD_B_MUTATION=false
```

The fresh non-A node hash exactly matches the repository-frozen public-safe Board B node hash from the historical Board B closeout. The third canonical node is stale by roughly 6.9 days and is excluded from the live role-assignment set.

```text
BOARD_B_RUNTIME_BINDING=PASS
BOARD_B_RUNTIME_BINDING_METHOD=FROZEN_PUBLIC_NODE_HASH_PLUS_FRESH_CANONICAL_STATE
STALE_NODE_EXCLUDED_FROM_LIVE_ROLE_SET=true
PRODUCT_FAILURE=false
```

The earlier `OTHER_FRESH_DIRECT_COUNT=0` remains a transient observer stop with no proven root cause. It must not be rewritten as a Board-B failure.

```text
NEXT_ACTION=90_SECOND_DUAL_DIRECT_BASELINE_WITH_BOUND_BOARD_B
```


## 2026-09-22 Board B gateway-side Direct baseline closure

The bound Board B candidate remained Direct and same-boot through a 90-second observation while Board A simultaneously preserved its previously established same-boot Direct session.

```text
T1_MANAGER_RUNNING_BEFORE=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_STARTED_AT_BEFORE=2026-09-14T02:46:17.376354998Z

BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SEQ_BEFORE=685
BOARD_A_BOOT_SESSION_SHA256_BEFORE=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776

BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SEQ_BEFORE=520
BOARD_B_BOOT_SESSION_SHA256_BEFORE=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2

OBSERVATION_SECONDS=90

BOARD_A_SOURCE_AFTER=direct
BOARD_A_SEQ_AFTER=703
BOARD_A_SEQ_DELTA=18
BOARD_A_BOOT_SESSION_SHA256_AFTER=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776
BOARD_A_SAME_BOOT=true

BOARD_B_SOURCE_AFTER=direct
BOARD_B_SEQ_AFTER=539
BOARD_B_SEQ_DELTA=19
BOARD_B_BOOT_SESSION_SHA256_AFTER=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
BOARD_B_SAME_BOOT=true

T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_AFTER=2026-09-14T02:46:17.376354998Z

BOARD_A_SAME_BOOT_PRESERVED=true
BOARD_A_DIRECT_REMAINS_HEALTHY=true
BOARD_B_CANONICAL_ADVANCED=true
BOARD_B_LAST_SOURCE_DIRECT=true
BOARD_B_GATEWAY_DIRECT_BASELINE=PASS
MANAGER_RESTART_COUNT_UNCHANGED=true
MANAGER_STARTED_AT_UNCHANGED=true

BOARD_A_MUTATION=false
BOARD_B_MUTATION=false
T1_RUNTIME_MUTATION=false
N3W_PR437_BOARD_B_GATEWAY_DIRECT_BASELINE=PASS
```

The role-swap starting condition is now established:

```text
BOARD_A_CURRENT_ROLE=Direct child candidate
BOARD_B_CURRENT_ROLE=Direct gateway candidate
BOARD_A_SAME_BOOT_SESSION_ESTABLISHED=true
BOARD_B_SAME_BOOT_SESSION_ESTABLISHED=true
BOTH_DIRECT_BASELINE=PASS
```

No reset, power cycle, flash/NVS access, application-serial access, or T1 runtime mutation is permitted between this closure and the same-boot Board-A Direct -> Relay role-swap transition.

```text
NEXT_ONE_GATE=N3W_PR437_BOARD_A_SAME_BOOT_DIRECT_TO_RELAY_ROLE_SWAP_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```


## 2026-09-22 Board A same-boot Direct -> Relay role-swap authorization

Fresh entry authority:

```text
PR471_HEAD=48d540e62539519453dc05edb20575bb46da41ed
PR471_CI=12_OF_12_PASS
PR471_STATE=OPEN_DRAFT
PR471_MERGEABLE=true

BOARD_A_NODE_ID_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
BOARD_A_BOOT_SESSION_SHA256=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776

BOARD_B_NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
BOARD_B_BOOT_SESSION_SHA256=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2

BOARD_A_POSTWRITE_DIRECT_BASELINE=PASS
BOARD_B_GATEWAY_DIRECT_BASELINE=PASS
DUAL_DIRECT_ROLE_SWAP_STARTING_CONDITION=PASS

AUTHORIZED_GATE=N3W_PR437_BOARD_A_SAME_BOOT_DIRECT_TO_RELAY_ROLE_SWAP_20260922_01
PHYSICAL_MOVEMENT_AUTHORIZED=true
AUTO_EXECUTE_RELAY_600S=false
AUTO_EXECUTE_RELAY_TO_DIRECT=false
```

Execution boundary:

- Board B remains stationary in the validated Direct/Wi-Fi position;
- Board A alone is moved to the previously validated no-Wi-Fi / Relay-child position;
- Board A must not reboot or lose power;
- application serial remains closed;
- no Flash/NVS/T1/Broker/Manager/DynSec mutation;
- Manager canonical durable state is the transition authority;
- the first accepted Board A Relay cursor must name the bound Board B node as gateway;
- after first Relay acceptance, require at least two additional Board A Relay sequence advances before PASS;
- stop after Direct -> Relay classification. Do not automatically enter the 600-second Relay continuity gate.

```text
TRANSITION_TIMEOUT_SECONDS=240
POST_RELAY_REQUIRED_SEQ_ADVANCE=2
BOARD_A_POWER_CYCLE=false
BOARD_A_RESET=false
BOARD_B_MOVE=false
BOARD_B_RESET=false
APPLICATION_SERIAL_OPEN=false
```


## 2026-09-22 battery-power transition rebaseline requirement

Before the authorized Board A same-boot Direct -> Relay movement, the operator reported that Board A must be switched from USB power to battery power and that this power-source change necessarily causes one reboot.

Therefore the previously established Board A same-boot baseline is no longer admissible as the transition starting session once the battery switch occurs.

```text
BATTERY_SWITCH_REQUIRES_REBOOT=true
PREVIOUS_BOARD_A_BOOT_SESSION_VALID_FOR_ROLE_SWAP_AFTER_BATTERY_SWITCH=false
PREVIOUS_BOARD_A_DIRECT_BASELINE_REQUIRES_REBASE=true
BOARD_B_GATEWAY_BASELINE_REUSE_ALLOWED_IF_BOARD_B_BOOT_UNCHANGED=true
```

The correct execution order is:

1. keep Board B stationary and powered in the validated Direct/Gateway position;
2. switch Board A to battery power, accepting exactly one reboot;
3. do not move Board A to the Relay-child location yet;
4. from Manager canonical durable state, prove Board A appears on a new boot session and resumes fresh Direct telemetry;
5. prove Board B remains on its existing boot session and remains fresh Direct;
6. observe both for a new bounded Direct baseline;
7. define the new Board A battery boot as the same-boot origin for the subsequent Direct -> Relay movement.

```text
NEXT_ONE_GATE=N3W_PR437_BOARD_A_BATTERY_DIRECT_REBASELINE_20260922_01
AUTO_EXECUTE_ROLE_SWAP_AFTER_REBASELINE=false
```


## 2026-09-22 Board A battery-powered Direct rebaseline entry

Operator-confirmed physical state:

```text
BOARD_A_BATTERY_POWERED=true
BOARD_A_REBOOT_COMPLETED=true
BOARD_A_STILL_IN_WIFI_COVERAGE=true
BOARD_B_UNCHANGED=true
```

Fresh repository gate state:

```text
PR471_HEAD=1ba4fc70872bfae47f7de2ae2d3d46b571601d96
PR471_CI=12_OF_12_PASS
PR471_STATE=OPEN_DRAFT
PR471_MERGEABLE=true
```

The previous USB-powered Board A boot session is intentionally invalidated for the upcoming same-boot role-swap claim.

This gate must:

- bind the new battery-powered Board A boot from Manager canonical durable state;
- require fresh Direct telemetry on that new boot;
- preserve Board B's previously bound boot/session and Direct path;
- observe both for 90 seconds;
- perform no board/T1 persistent mutation;
- stop after the new battery Direct baseline is established.

```text
NEXT_ONE_GATE=N3W_PR437_BOARD_A_BATTERY_DIRECT_REBASELINE_20260922_01
AUTO_EXECUTE_ROLE_SWAP_AFTER_PASS=false
```


## 2026-09-22 Board A battery-powered Direct rebaseline closure

The operator-confirmed Board A battery-power reboot was followed by a clean 90-second dual-Direct rebaseline.

```text
BOARD_A_BATTERY_POWERED=true
BOARD_A_REBOOT_COMPLETED=true
BOARD_A_STILL_IN_WIFI_COVERAGE=true
BOARD_B_UNCHANGED=true

BOARD_A_BATTERY_BOOT_BOUND=true
BOARD_A_OLD_BOOT_REPLACED=true

BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SEQ_BEFORE=55
BOARD_A_BOOT_SESSION_SHA256_BEFORE=51382692150b4a9feb6f49587fa24825b55036723b1aa5fc67a82a82201a56b1
BOARD_A_AGE_SECONDS_BEFORE=1.7

BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SEQ_BEFORE=767
BOARD_B_BOOT_SESSION_SHA256_BEFORE=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
BOARD_B_AGE_SECONDS_BEFORE=2.8

OBSERVATION_SECONDS=90

BOARD_A_SOURCE_AFTER=direct
BOARD_A_SEQ_AFTER=74
BOARD_A_SEQ_DELTA=19
BOARD_A_BOOT_SESSION_SHA256_AFTER=51382692150b4a9feb6f49587fa24825b55036723b1aa5fc67a82a82201a56b1
BOARD_A_SAME_BATTERY_BOOT=true

BOARD_B_SOURCE_AFTER=direct
BOARD_B_SEQ_AFTER=786
BOARD_B_SEQ_DELTA=19
BOARD_B_BOOT_SESSION_SHA256_AFTER=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
BOARD_B_SAME_BOOT=true

T1_MANAGER_RUNNING_BEFORE=true
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true

BOARD_A_BATTERY_DIRECT_BASELINE=PASS
BOARD_A_BATTERY_SAME_BOOT_ORIGIN_ESTABLISHED=true
BOARD_B_GATEWAY_DIRECT_REMAINS_HEALTHY=true
MANAGER_RESTART_COUNT_UNCHANGED=true
MANAGER_STARTED_AT_UNCHANGED=true

BOARD_A_MUTATION=false
BOARD_B_MUTATION=false
T1_RUNTIME_MUTATION=false

N3W_PR437_BOARD_A_BATTERY_DIRECT_REBASELINE=PASS
```

The new Board A battery boot session supersedes the earlier USB-powered boot session for all subsequent same-boot role-swap evidence.

```text
OLD_BOARD_A_BOOT_SESSION_SHA256=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776
CURRENT_BOARD_A_BATTERY_BOOT_SESSION_SHA256=51382692150b4a9feb6f49587fa24825b55036723b1aa5fc67a82a82201a56b1
CURRENT_BOARD_B_BOOT_SESSION_SHA256=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2

NEXT_ONE_GATE=N3W_PR437_BOARD_A_SAME_BOOT_DIRECT_TO_RELAY_ROLE_SWAP_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```
