# N3-W Production Multi-Relay Gateway Selection V1
## Physical Validation Preparation — 2026-09-22

Status: `FAIL_CLOSED_ARTIFACT_TARGET_MISMATCH`

## 1. Gate

```text
TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_20260922_01

AUTHORIZED_SCOPE=
PHYSICAL_VALIDATION_PREPARATION_ONLY

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
T1_ACCESS=false
```

This gate was intended to freeze the three-board physical validation plan before any board write.

The preparation found a blocking artifact-target mismatch before physical execution.

No board or T1 operation was performed.

## 2. Frozen R2 source authority

```text
R2_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

R2_SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

SOURCE_REVIEW_R2=PASS
READY_FOR_CORRECT_PRODUCTION_ARTIFACT_BUILD=true
```

Astra independently closed all three R1 source blockers.

The R2 source authority itself is not invalidated by this preparation finding.

## 3. Previously built artifact

```text
ARTIFACT_ID=
10691518958

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-exact-source

WORKFLOW_RUN_ID=
35722701651

APPLICATION_SHA256=
5e0dc5d950061dd6685b11ee972090036a5af6d576920621550582d216ce38e6

ARTIFACT_BUILD_RESULT=SUCCESS
ARCHIVE_HASH_BINDING=PASS
```

The build and archive hashes are internally consistent.

However, this artifact is **not** a valid Gateway Selection V1 production physical candidate because the wrong firmware target was compiled.

## 4. Blocking target mismatch

The workflow compiled:

```text
WRONG_TARGET_CONFIG=
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml

WRONG_TARGET_BLOB=
37654481747b21ca51ccecc246bf84ca437ab7a9
```

That target explicitly loads:

```yaml
external_components:
  - source:
      type: local
      path: ../../components
    components:
      - greenhouse_n3w_core

greenhouse_n3w_core:
  phase4_source_harness: true
  phase4_product_runtime: true
  phase4_lab_diagnostics: true
```

Therefore the built binary is the historical Phase-4/PR437 lab physical harness.

The R2 source repair changed:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/
```

The wrong target does not load that production component.

Consequently:

```text
R2_SOURCE_HEAD_BINDING_IN_MANIFEST=TRUE
R2_PRODUCT_CORE_INCLUDED_IN_BINARY=FALSE
GATEWAY_SELECTION_V1_R2_BINARY_PROOF=FAIL

ARTIFACT_10691518958_GATEWAY_SELECTION_PHYSICAL_USE=FORBIDDEN
```

A source-tree hash match alone is insufficient when the selected YAML does not compose the modified component.

## 5. Correct production target

The correct R2 physical candidate must be built from:

```text
CORRECT_TARGET_CONFIG=
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

CORRECT_TARGET_BLOB=
32a2b3cb29be4e1bce46807d8825b6a4c37999ec
```

That target explicitly loads:

```yaml
external_components:
  - source:
      type: local
      path: ../components
    components:
      - greenhouse_n3w_product_core
```

and includes:

```text
TRANSPORT_PACKAGE=
firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml

TRANSPORT_BLOB=
aa39d4b083f2db1b30a76efb1afef156db355a35

TELEMETRY_PACKAGE=
firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml

TELEMETRY_BLOB=
ce16f2389d146f9b25e95cbb628547e11ce36bd6

PRODUCT_CORE_INIT_BLOB=
7e86aa2f3fb1bff6f5813e431da501970263e33a
```

The production target includes the real F1.0-RC2 sensors and the real N3-W telemetry bridge.

## 6. Correct artifact mechanism

The already proven production artifact route at source `c1b3d9d...` used:

```text
TARGET=
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

COMPILE=
firmware/esphome_rc/f1_0_rc2/tools/rc2.sh compile

BINARY_DEHARNESS_PROOF=true

RELEASE_MEMBER_COUNT=8
```

Expected release members:

```text
MANIFEST.txt
bootloader.bin
firmware.bin
firmware.factory.bin
firmware.ota.bin
flash_args
ota_data_initial.bin
partitions.bin
```

The corrected R2 artifact route should reuse this proven production mechanism while changing only the exact source authority and artifact identifiers.

## 7. Corrected exact-artifact contract

The next artifact build must fail closed unless all of the following are true:

```text
SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

TARGET_CONFIG=
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

TARGET_BLOB=
32a2b3cb29be4e1bce46807d8825b6a4c37999ec

TRANSPORT_BLOB=
aa39d4b083f2db1b30a76efb1afef156db355a35

TELEMETRY_BLOB=
ce16f2389d146f9b25e95cbb628547e11ce36bd6

PRODUCT_CORE_INIT_BLOB=
7e86aa2f3fb1bff6f5813e431da501970263e33a

PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

The workflow must also retain the existing production de-harness proof:

```text
PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false

PRODUCT_CORE_POSITIVE_CONTROL=PASS
REAL_TELEMETRY_BRIDGE_POSITIVE_CONTROL=PASS
```

No binary hash may be predicted or inherited from artifact `10691518958` or from the older `c1b3d9d...` production artifact.

A new build requires a new independent archive/member/hash binding record.

## 8. Artifact disposition correction

```text
ARTIFACT_ID=10691518958

BUILD_INTEGRITY=PASS
ARCHIVE_BINDING_INTEGRITY=PASS
INTENDED_PRODUCT_TARGET_BINDING=FAIL

DISPOSITION=
FROZEN_WRONG_TARGET_NOT_FOR_GATEWAY_SELECTION_PHYSICAL_USE
```

This artifact must not be flashed for Gateway Selection V1 validation.

It may remain in GitHub only as historical evidence of the wrong-target build.

## 9. Physical validation plan remains deferred

The intended later physical plan is still conceptually:

```text
A=Direct Relay candidate
B=Direct Relay candidate
C=Child under test
```

but no board role, placement, RSSI geometry, movement, or acceptance timing becomes executable until a correct production R2 artifact is built and bound.

The later physical route must use the **same newly bound production R2 artifact on all participating boards** unless a later gate explicitly proves a different board-specific artifact contract.

This avoids repeating the earlier risk where A/B were temporarily on different firmware generations.

## 10. Physical scenarios to preserve for the later gate

After the corrected artifact is available and separately authorized, physical acceptance should eventually prove at least:

1. **A/B both Direct, C loses Direct**:
   - C sees both valid Gateway candidates;
   - selection is not merely first-advertisement order;
   - selected Gateway matches the frozen RSSI/3 dB/hash policy.

2. **Clear RSSI winner**:
   - A and B separated enough to create a stable RSSI difference greater than 3 dB;
   - C selects the stronger retained candidate.

3. **Equivalent-quality tie**:
   - A/B within the 3 dB equivalent band;
   - C selects the deterministic SHA-256/hash winner;
   - repeated fresh Discovery runs under equivalent conditions select the same logical Relay.

4. **Healthy Relay stickiness**:
   - after C activates one Relay, move/alter the other Gateway to become stronger;
   - C must not proactively roam while the active Relay remains healthy.

5. **Gateway failure / reselection**:
   - make the active Gateway genuinely unavailable;
   - after the existing failure threshold, C returns to Discovery and can select the surviving Gateway.

6. **Same-boot Direct -> Relay -> Direct**:
   - preserve the already proven PR437 physical acceptance pattern;
   - do not power-cycle the Child during the transition.

7. **Role symmetry**:
   - product source remains role-neutral;
   - A/B may swap Gateway roles without board-specific firmware.

8. **Canonical telemetry**:
   - use Manager canonical durable state as the primary oracle;
   - INFO-log absence alone is not failure.

9. **Real sensor boundary**:
   - because the correct F1.0-RC2 target includes the real telemetry bridge, a later physical product-acceptance gate can explicitly decide whether to include real sensor telemetry;
   - do not silently upgrade communication-only evidence into real-sensor acceptance.

## 11. Later physical acceptance boundaries

The following remain unproven:

```text
THREE_BOARD_GATEWAY_SELECTION_PHYSICAL_ACCEPTANCE=NOT_PROVEN
REAL_RSSI_RANKING_PHYSICAL_ACCEPTANCE=NOT_PROVEN
HEALTHY_RELAY_STICKINESS_PHYSICAL_ACCEPTANCE=NOT_PROVEN
FAILED_GATEWAY_RESELECTION_PHYSICAL_ACCEPTANCE=NOT_PROVEN
R2_SAME_BOOT_DIRECT_RELAY_DIRECT_PHYSICAL_ACCEPTANCE=NOT_PROVEN

REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

The prior PR437 A/B role-swap evidence remains valid only for its frozen PR437 artifact and is not automatically transferred to R2.

## 12. Gate closure

```text
=== N3W GATEWAY SELECTION V1 PHYSICAL VALIDATION PREPARATION CLOSURE ===

TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_20260922_01

R2_SOURCE_REVIEW=PASS

REQUESTED_ARTIFACT_ID=
10691518958

REQUESTED_APPLICATION_SHA256=
5e0dc5d950061dd6685b11ee972090036a5af6d576920621550582d216ce38e6

ARTIFACT_BUILD_INTEGRITY=PASS
ARTIFACT_TARGET_BINDING=FAIL
ARTIFACT_CONTAINS_R2_PRODUCT_CORE=false

PHYSICAL_PREPARATION_RESULT=
FAIL_CLOSED_WRONG_ARTIFACT_TARGET

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
T1_ACCESS=false

AUTO_REBUILD=false
AUTO_BOARD_WRITE=false
AUTO_PHYSICAL_EXECUTION=false
STOP=true
```

## 13. Proposed next ONE gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PRODUCTION_EXACT_ARTIFACT_REBUILD_AND_BINDING_20260922_01

SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

TARGET_CONFIG=
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
```

The corrected artifact gate must stop again after independent artifact binding. A later physical-preflight gate requires a new explicit authorization.
