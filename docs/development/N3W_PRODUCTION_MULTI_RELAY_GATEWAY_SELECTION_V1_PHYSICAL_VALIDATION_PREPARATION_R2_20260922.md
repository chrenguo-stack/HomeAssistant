# N3-W Production Multi-Relay Gateway Selection V1
## Physical Validation Preparation R2 — 2026-09-22

Status: `PHYSICAL_VALIDATION_PREPARATION_AUTHORITY`

## 1. Gate scope

```text
TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_R2_20260922_01

AUTHORIZED_SCOPE=
HOST/GITHUB PHYSICAL-PLAN PREPARATION ONLY

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
RF_EXECUTION=false
T1_ACCESS=false
T1_MUTATION=false
MERGE=false
```

This gate freezes the later three-board write/preflight and physical-validation plan
against the corrected production R2 artifact.

No board, USB, serial, RF, T1, Manager, Broker, credential, NVS, OTA-data or flash
operation occurs here.

## 2. Exact source and artifact authority

```text
SOURCE_BASE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

SOURCE_REVIEW_R2=PASS

CORRECT_PRODUCTION_ARTIFACT_ID=
10693728323

CORRECT_PRODUCTION_ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-8c445f2-exact-source

OUTER_ARTIFACT_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

FIRMWARE_BIN_SIZE=
1392960

FIRMWARE_BIN_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

FIRMWARE_FACTORY_BIN_SHA256=
d8aa60082eca0482fe14806d8f4445223d3ccd4f87ba05d433b3ef31c187d304

PARTITIONS_BIN_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

MANIFEST_SHA256=
eefa4580940302094d74e5e6228e82c683ba9b2a4c3c5e5b8d59fbee5ad0851e
```

The artifact composes:

```text
TARGET_CONFIG=
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

PRODUCT_CORE=
greenhouse_n3w_product_core

REAL_TELEMETRY_BRIDGE=true

N3W_GATEWAY_SELECTION_R2_LINK_PROOF=PASS
N3W_PRODUCTION_BINARY_DEHARNESS_PROOF=PASS
```

The earlier artifact `10691518958` remains forbidden for this physical route:

```text
ARTIFACT_10691518958_DISPOSITION=
FROZEN_WRONG_TARGET_NOT_FOR_GATEWAY_SELECTION_PHYSICAL_USE
```

## 3. Product behavior being physically validated

The R2 production firmware freezes:

```text
GATEWAY_CANDIDATE_WINDOW_MS=6500
GATEWAY_SELECTION_TRANSACTION_MAX_MS=30000
MAX_GATEWAY_CANDIDATES=8

RSSI_EQUIVALENT_BAND_DB=3
PRIMARY_SELECTION=ARITHMETIC_MEAN_RSSI
EQUIVALENT_BAND_TIE_BREAK=SHA256_GWSEL_V1
FINAL_DIGEST_COLLISION_TIE_BREAK=RELAY_NODE_ID_LEXICOGRAPHIC

ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true
PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false

OPTION_B_EVERY_SAMPLE_DURABILITY=false
```

The F1.0-RC2 production target emits real telemetry every:

```text
N3W_TELEMETRY_INTERVAL=60s
```

Physical timing windows must account for that 60-second application cadence. They
must not reuse the old Phase-4 5-second telemetry expectations.

## 4. Three-board topology

Full Gateway Selection V1 physical acceptance requires three production-compatible
ESP32-C6 nodes:

```text
BOARD_A_ROLE=
STATIONARY_DIRECT_RELAY_CANDIDATE

BOARD_B_ROLE=
STATIONARY_DIRECT_RELAY_CANDIDATE

BOARD_C_ROLE=
PORTABLE_CHILD_UNDER_TEST

THREE_PHYSICAL_BOARDS_REQUIRED=true
TWO_BOARD_SUBSTITUTE_FOR_MULTI_GATEWAY_SELECTION=false
```

A and B must both remain Direct + MQTT healthy during dual-Gateway selection tests,
because production runtime only advertises Relay capability while the node is
actually eligible to act as a Gateway.

C starts each route from a fresh Direct baseline and is then moved, without reboot,
to a location where Wi-Fi Direct is unavailable but ESP-NOW communication with both
Gateway candidates remains possible.

For the cleanest RSSI comparison:

```text
A_B_USE_SAME_WIFI_AP=true
A_B_EXPECTED_WIFI_CHANNEL_SAME=true
```

This prevents AP/channel differences from becoming an uncontrolled variable in the
first multi-Gateway tests.

If a third suitable physical board is not available:

```text
RESULT=STOP_PENDING_THIRD_BOARD
```

Do not substitute a host runtime, simulator, historical Board B result, or a
two-board role swap and call it multi-Gateway physical acceptance.

## 5. Same-artifact rule

Before any Gateway-selection RF test:

```text
BOARD_A_ARTIFACT_ID=10693728323
BOARD_B_ARTIFACT_ID=10693728323
BOARD_C_ARTIFACT_ID=10693728323

A_B_C_SAME_EXACT_ARTIFACT_REQUIRED=true
```

The earlier situation where physical roles temporarily used different firmware
generations must not recur.

No board-specific product firmware is allowed. A/B/C role assignment is runtime and
physical-topology only.

## 6. Write safety and partition compatibility

The corrected production artifact has:

```text
PARTITION_TABLE_SIZE=0xC00
PARTITION_TABLE_OFFSET=0x8000
PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTADATA_OFFSET=0x9000
APP0_OFFSET=0x10000
APP0_SIZE=0x3C0000
APP1_OFFSET=0x3D0000
APP1_SIZE=0x3C0000
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
```

The partition-table digest exactly matches the historical PR437 board-write authority.

That is useful compatibility evidence, but it is not a substitute for a fresh
readback from each current physical board.

### Frozen write policy

The later write route may use the historical minimal application update pattern only
after a fresh per-board preflight proves exact partition compatibility and acceptable
security state:

```text
WRITE_OTADATA_AT_0x9000=
ota_data_initial.bin

WRITE_APPLICATION_AT_0x10000=
firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
FACTORY_IMAGE_WRITE=false
```

Required post-write readback:

```text
APPLICATION_READBACK_SIZE=1392960
APPLICATION_READBACK_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

OTADATA_READBACK_SIZE=8192
OTADATA_READBACK_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

### Fail-closed rules

If any board reports a different partition table:

```text
AUTO_PARTITION_WRITE=false
AUTO_FACTORY_FLASH=false
AUTO_FULL_ERASE=false
RESULT=STOP_FOR_PARTITION_MIGRATION_REVIEW
```

If secure boot / flash encryption / ROM security state makes the historical raw
application-write route unsafe or invalid:

```text
AUTO_BYPASS=false
RESULT=STOP_FOR_SECURITY_COMPATIBILITY_REVIEW
```

The flat release bundle's `flash_args` must never be executed blindly. It contains
build-tree-relative file names and is evidence, not a directly executable release
script.

## 7. Next board preflight contract

The next physical-facing gate is read-only with respect to persistent storage.

Important: a ROM/bootloader-level silicon or partition-table read may require a
temporary reset or bootloader entry on ESP32-C6. That is not a Flash/NVS mutation,
but it is still a physical state disturbance and must be explicitly authorized in
that later preflight gate if the selected read method requires it.

The preflight should prefer a proven no-write/no-erase method and must report whether
a reset or ROM/bootloader entry actually occurred.


It must inspect A, B, and C separately and bind each physical board to an operator
label before any write.

For each board:

```text
OPERATOR_PHYSICAL_LABEL=A|B|C
FRESH_ROM_SILICON_IDENTITY_REQUIRED=true
USB_PORT_IS_LOCATOR_ONLY=true

EXPECTED_CHIP=ESP32-C6
EXPECTED_FLASH_SIZE=8MB

PARTITION_TABLE_READBACK_REQUIRED=true
EXPECTED_PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

SECURE_BOOT_STATE_REQUIRED=true
FLASH_ENCRYPTION_STATE_REQUIRED=true
CURRENT_OTA_SELECTION_READ_REQUIRED=true

RAW_NVS_DUMP_PUBLIC=false
RAW_MAC_PUBLIC=false
RAW_NODE_ID_PUBLIC=false
PRIVATE_USB_PATH_PUBLIC=false
```

Any board-target mismatch is a STOP, not a reason to reinterpret historical USB port
mapping.

A/B historical role labels are convenience labels only, not identity authority.

## 8. Pairing/NVS preservation

The preferred application + OTA-data update deliberately preserves product NVS.

After write, each node must prove a normal Direct runtime baseline using its existing
provisioned state.

If any board cannot reach the expected Direct/MQTT state because provisioning is
absent, incompatible, or stale:

```text
AUTO_NVS_ERASE=false
AUTO_REPAIR_PAIRING=false
AUTO_COPY_CREDENTIALS=false
RESULT=STOP_FOR_SEPARATE_PROVISIONING_GATE
```

Do not mix pairing repair into Gateway-selection physical acceptance.

## 9. Post-write three-board Direct baseline

After a separately authorized same-artifact write, but before C is moved:

```text
A_DIRECT_MQTT_BASELINE=REQUIRED
B_DIRECT_MQTT_BASELINE=REQUIRED
C_DIRECT_MQTT_BASELINE=REQUIRED

A_RELAY_CAPABLE_PRECONDITION=true
B_RELAY_CAPABLE_PRECONDITION=true

MANAGER_RESTART_COUNT_UNCHANGED=true
T1_RUNTIME_MUTATION=false
```

Because production telemetry is 60 seconds, use:

```text
DIRECT_BASELINE_OBSERVATION_SECONDS=180
MIN_CANONICAL_SEQ_ADVANCEMENT=2
```

for each node before physical movement.

Primary oracle:

```text
MANAGER_CANONICAL_DURABLE_STATE
```

INFO-log absence alone is not a failure oracle.

## 10. Manager evidence model

Manager's Relay ingress explicitly carries a `gateway_id`, and canonical state
persists `last_gateway_id`.

The physical observer should therefore record C using public-safe board labels rather
than publishing raw IDs:

```text
C_LAST_SOURCE=direct|relay
C_LAST_GATEWAY_LABEL=NONE|A|B
C_BOOT_SESSION_SHA256=<public-safe digest>
C_SEQ=<integer>
C_UPDATED_AT=<time>

A_DIRECT_HEALTH=true|false
B_DIRECT_HEALTH=true|false
MANAGER_RESTART_COUNT=<integer>
```

The observer may privately map actual Gateway identity to A/B. Raw NODE_ID,
gateway_id, MAC, credentials, private T1 locator and raw private logs must not be
committed to the public repository.

## 11. Candidate-RSSI observability boundary

R2 production source consumes ESP-NOW receive RSSI internally and uses it to populate
the candidate table.

However, the de-harnessed production artifact does **not** expose the per-candidate
RSSI averages through Manager canonical state or a dedicated production diagnostic
surface.

Therefore:

```text
EXACT_INTERNAL_CANDIDATE_RSSI_PHYSICAL_OBSERVABILITY=false
```

This has an important acceptance consequence.

A production end-to-end run can prove:

- both Gateways are physically usable;
- C selects A or B;
- changing the RF geometry changes the selected Gateway;
- the selected Gateway remains sticky while healthy;
- failure of the active Gateway causes reselection;
- C returns to Direct in the same boot.

It cannot, by Manager canonical state alone, prove that C's internal arithmetic mean
was exactly X dBm or that two internal means differed by exactly 3 dB.

The exact arithmetic, exact 3 dB boundary, digest serialization and deterministic
tie-break remain source/host-test authorities already covered by R2 review and CI.

Do not falsely label a geometry-based physical run as:

```text
EXACT_3DB_INTERNAL_RSSI_BOUNDARY_PHYSICALLY_MEASURED
```

unless a later separately designed RF-instrumentation gate provides a trustworthy
measurement at the Child receiver.

This is a test-observability limitation, not a source blocker.

## 12. Physical acceptance sequence

The later physical route should be split into bounded stages. Do not execute all
stages automatically after one PASS.

### Stage P0 — three-board artifact synchronization

Purpose:

- prove A/B/C all run artifact `10693728323`;
- prove exact application readback;
- preserve partition table, bootloader and NVS;
- establish three fresh Direct baselines.

Stop after Direct baseline.

### Stage P1 — individual Gateway qualification

At the intended C Relay location, prove independently that:

```text
C_CAN_RELAY_THROUGH_A=true
C_CAN_RELAY_THROUGH_B=true
```

Use one available Gateway at a time.

This prevents a dual-Gateway run from being misread when one candidate was never
physically usable.

After each qualification, return C to Direct without power-cycle before starting the
next controlled round when practical.

### Stage P2 — dual-Gateway geometry A-strong

Place A physically favored and B physically disadvantaged while both remain Direct
and both have already passed individual qualification.

Then move C from Direct to the Relay-only location in the same boot.

Required result:

```text
C_SOURCE=relay
C_GATEWAY_LABEL=A
A_DIRECT_HEALTH=true
B_DIRECT_HEALTH=true
```

This is strong physical evidence that the multi-Gateway path works and the physically
favored candidate can win.

It is not an exact numeric 3 dB measurement.

### Stage P3 — dual-Gateway geometry B-strong

Return C to a fresh Direct baseline in the same boot if possible.

Swap the controlled RF geometry so B is favored and A is disadvantaged, while both
remain individually usable candidates.

Required result:

```text
C_SOURCE=relay
C_GATEWAY_LABEL=B
A_DIRECT_HEALTH=true
B_DIRECT_HEALTH=true
```

P2 + P3 together prove that Gateway choice is not permanently pinned to one board
identity.

### Stage P4 — healthy Relay stickiness

After C has selected an active Gateway, make the alternate Gateway physically more
favorable without making the active Gateway fail.

Required behavior:

```text
ACTIVE_GATEWAY_STAYS_UNCHANGED=true
PROACTIVE_ROAMING_OBSERVED=false
```

Steady-state observation:

```text
RELAY_STEADY_STATE_SECONDS=600
MIN_STEADY_CANONICAL_SEQ_DELTA=8
STEADY_STATE_MISSING_SEQUENCE_COUNT=0
```

The exact observed counts/times must be recorded.

### Stage P5 — active Gateway failure and reselection

Make only the active Gateway genuinely unavailable while the alternate Gateway
remains healthy and C remains outside Direct Wi-Fi coverage.

Required behavior:

```text
C_RETURNS_TO_DISCOVERY=true
C_RESELECTS_SURVIVING_GATEWAY=true
C_SOURCE=relay
C_GATEWAY_LABEL=<surviving A or B>
```

Do not power-cycle C.

### Stage P6 — same-boot Relay -> Direct recovery

Restore C to normal Wi-Fi coverage without reboot.

Required behavior:

```text
C_SOURCE=direct
SAME_BOOT_RELAY_TO_DIRECT=true
RELAY_AFTER_FIRST_DIRECT_OBSERVED=false
```

This extends the earlier PR437 same-boot proof to the corrected R2 production artifact.

## 13. Timing windows

The production telemetry interval is 60 seconds and selection transaction budget is
30 seconds.

Use bounded but non-fragile observation windows:

```text
DIRECT_TO_RELAY_MAX_OBSERVATION_SECONDS=300
GATEWAY_RESELECTION_MAX_OBSERVATION_SECONDS=300
RELAY_TO_DIRECT_MAX_OBSERVATION_SECONDS=300

POST_TRANSITION_CONFIRMATION_MIN_SEQ_ADVANCEMENT=2
RELAY_STEADY_STATE_SECONDS=600
```

A path transition is not PASS from one isolated telemetry row.

After first canonical evidence of the new path, require at least two later sequence
advancements before calling the transition stable.

Actual observed timing and sequence gaps must be reported even when within the
allowed window.

## 14. Option-B reliability interpretation

The physical route must preserve the already frozen contract:

```text
DIRECT_TO_RELAY_BOUNDARY_ZERO_LOSS=NOT_GUARANTEED
END_TO_END_EVERY_SAMPLE_DELIVERY=false
```

A small transition sequence gap is not automatically a Gateway-selection failure.

However, once Relay steady state is established, the 600-second continuity stage is
expected to show no missing sequence inside the measured steady window.

Do not silently convert transition loss into a source regression unless evidence
shows a violation of the frozen Option-B behavior.

## 15. Equivalent-quality/hash physical evidence

A near-equal-RSSI run may be performed as supporting evidence if geometry can be made
reasonably symmetric.

For each fresh Discovery round, the expected tie winner can be calculated privately
from the exact child/relay NODE_ID inputs and then reported only as:

```text
EXPECTED_TIE_WINNER_LABEL=A|B
OBSERVED_GATEWAY_LABEL=A|B
```

Raw identity inputs remain private.

But without direct measurement of C's internal candidate RSSI means:

```text
HASH_TIEBREAK_PHYSICAL_SUPPORT=OPTIONAL
EXACT_3DB_BOUNDARY_PHYSICAL_CLOSURE=NOT_REQUIRED_FOR_CORE_E2E_PASS
```

The exact 3 dB and SHA behavior remains covered by source review, host tests and fixed
hash-vector regression.

If strict RF-level proof of the exact boundary is later required, create a separate
instrumented test gate rather than adding lab diagnostics to this production artifact.

## 16. Real-sensor end-to-end acceptance

The corrected R2 artifact includes the real F1.0-RC2 telemetry bridge.

Therefore the later physical route has an opportunity to close the historical
real-sensor gap without changing firmware.

Communication-path PASS does not require every sensor to be present or healthy.

To additionally claim real-sensor end-to-end acceptance, require at least one actual
C measurement key that is finite and `quality=ok` in the Direct baseline and later
appears through Relay canonical ingress in the same boot.

For example, any available real measurement may qualify:

```text
air_temperature_c
air_humidity_pct
co2_ppm
illuminance_lx
soil_temperature_c
soil_moisture_pct
soil_ec_us_cm
...
```

Only if that evidence exists may the later closure say:

```text
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=PASS
```

Otherwise:

```text
COMMUNICATION_PHYSICAL_ACCEPTANCE=<independent result>
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

Do not make missing/disconnected sensors invalidate an otherwise valid communication
test.

## 17. Hard stop conditions

Any of the following stops the physical route:

```text
FAIL_ARTIFACT_HASH_MISMATCH
FAIL_WRONG_ARTIFACT_10691518958
FAIL_NOT_THREE_PRODUCTION_COMPATIBLE_BOARDS
FAIL_OPERATOR_TARGET_NOT_CONFIRMED
FAIL_NOT_ESP32_C6
FAIL_FLASH_SIZE_NOT_8MB
FAIL_PARTITION_TABLE_HASH_MISMATCH
FAIL_SECURITY_STATE_INCOMPATIBLE_WITH_WRITE_ROUTE
FAIL_APPLICATION_READBACK_HASH_MISMATCH
FAIL_OTADATA_READBACK_HASH_MISMATCH
FAIL_POSTWRITE_DIRECT_BASELINE
FAIL_A_NOT_DIRECT_MQTT_HEALTHY
FAIL_B_NOT_DIRECT_MQTT_HEALTHY
FAIL_C_REBOOT_DURING_SAME_BOOT_TEST
FAIL_MANAGER_RUNTIME_DRIFT
FAIL_EVIDENCE_INSUFFICIENT
```

On physical failure:

```text
AUTO_REPAIR=false
AUTO_REFLASH=false
AUTO_NVS_ERASE=false
AUTO_RETRY=false
AUTO_SOURCE_CHANGE=false
STOP_AND_REVIEW=true
```

## 18. Forbidden shortcuts

```text
USE_ARTIFACT_10691518958=false
BLIND_RELEASE_FLASH_ARGS_EXECUTION=false
FACTORY_BIN_FULL_FLASH_WITHOUT_SEPARATE_REVIEW=false
PARTITION_TABLE_WRITE=false
BOOTLOADER_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false

HISTORICAL_USB_PORT_AS_IDENTITY=false
HISTORICAL_OPERATOR_OVERRIDE_REUSE=false

TWO_BOARD_RESULT_AS_MULTI_GATEWAY_PROOF=false
MANAGER_INFO_LOG_ONLY_AS_FAILURE_ORACLE=false

EXACT_3DB_PHYSICAL_CLAIM_WITHOUT_INTERNAL_RSSI_EVIDENCE=false

AUTO_EXECUTE_NEXT_PHYSICAL_STAGE=false
```

## 19. Expected write-preflight closure

The next gate should return one sanitized block per board:

```text
=== N3W GWSEL V1 THREE BOARD WRITE TARGET PREFLIGHT ===

ARTIFACT_ID=10693728323
ARTIFACT_BINDING=PASS

BOARD_A_PRESENT=
BOARD_A_OPERATOR_CONFIRMED=
BOARD_A_CHIP=
BOARD_A_FLASH_SIZE=
BOARD_A_PARTITION_TABLE_SHA256=
BOARD_A_SECURITY_STATE=
BOARD_A_OTA_STATE_READ=
BOARD_A_PREFLIGHT=

BOARD_B_PRESENT=
BOARD_B_OPERATOR_CONFIRMED=
BOARD_B_CHIP=
BOARD_B_FLASH_SIZE=
BOARD_B_PARTITION_TABLE_SHA256=
BOARD_B_SECURITY_STATE=
BOARD_B_OTA_STATE_READ=
BOARD_B_PREFLIGHT=

BOARD_C_PRESENT=
BOARD_C_OPERATOR_CONFIRMED=
BOARD_C_CHIP=
BOARD_C_FLASH_SIZE=
BOARD_C_PARTITION_TABLE_SHA256=
BOARD_C_SECURITY_STATE=
BOARD_C_OTA_STATE_READ=
BOARD_C_PREFLIGHT=

RAW_BOARD_IDENTITIES_PUBLIC=false
RAW_NVS_PUBLIC=false
FLASH_WRITE=false
PERSISTENT_BOARD_MUTATION=false
ROM_OR_BOOTLOADER_ENTRY_OCCURRED=
APPLICATION_RESET_OCCURRED=
T1_ACCESS=false

THREE_BOARD_WRITE_TARGET_PREFLIGHT=
PASS | STOP

STOP=true
=== END ===
```

## 20. Preparation closure

```text
=== N3W GATEWAY SELECTION V1 PHYSICAL VALIDATION PREPARATION R2 CLOSURE ===

TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_R2_20260922_01

SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

ARTIFACT_ID=
10693728323

CORRECT_TARGET_BINDING=PASS
R2_BINARY_LINK_PROOF=PASS

THREE_BOARD_TOPOLOGY_FROZEN=true
SAME_ARTIFACT_RULE_FROZEN=true
WRITE_SAFETY_POLICY_FROZEN=true
PARTITION_COMPATIBILITY_AUTHORITY_FROZEN=true
MANAGER_CANONICAL_ORACLE_FROZEN=true
PHYSICAL_STAGE_ORDER_FROZEN=true
TIMING_WINDOWS_FROZEN=true
RSSI_OBSERVABILITY_BOUNDARY_FROZEN=true
REAL_SENSOR_ACCEPTANCE_RULE_FROZEN=true

PHYSICAL_VALIDATION_PREPARATION_R2=PASS

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
RF_EXECUTION=false
T1_ACCESS=false

AUTO_NEXT_GATE=false
STOP=true
=== END ===
```

## 21. Next ONE gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_THREE_BOARD_WRITE_TARGET_PREFLIGHT_20260922_01

ARTIFACT_ID=
10693728323

EXPECTED_PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
PERSISTENT_BOARD_MUTATION=false
FLASH_WRITE=false
NVS_WRITE=false
T1_ACCESS=false
PHYSICAL_RF_EXECUTION=false

ROM_OR_BOOTLOADER_ENTRY_MAY_REQUIRE_RESET=true
EPHEMERAL_RESET_IF_REQUIRED_MUST_BE_EXPLICITLY_AUTHORIZED=true

EXPLICIT_AUTHORIZATION_REQUIRED=true
```

The next gate may identify and inspect A/B/C only. It must stop before artifact
synchronization or any write.
