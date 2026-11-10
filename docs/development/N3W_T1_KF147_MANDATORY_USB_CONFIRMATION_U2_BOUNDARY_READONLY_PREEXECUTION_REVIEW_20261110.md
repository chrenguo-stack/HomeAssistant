# N3W T1 KF-147 Mandatory USB Confirmation / U2 Boundary read-only preexecution review

Date: 2026-11-10  
PR: #800  
Repository head reviewed: `78e96812868cc13377746ba8d7ac00f6cef51d2f`  
Status: CLOSED_PASS_READONLY / STOP_BEFORE_FRESH_T1_BASELINE

## 1. Final archive CI closure

The five final-archive CI runs named by the V1.4 handoff are terminal SUCCESS on the exact reviewed head:

```text
FINAL_ARCHIVE_CI=CLOSED_PASS

CORE_STACK_CURRENT_AUTHORITY_RUN=42820224638
CORE_STACK_CURRENT_AUTHORITY=SUCCESS

HA_2026_10_4_TARGET_BINDING_RUN=42820224945
HA_2026_10_4_TARGET_BINDING=SUCCESS

FAST_SOURCE_EXACT_CLOSURE_RUN=42820224975
FAST_SOURCE_EXACT_CLOSURE=SUCCESS

MANAGER_A_TO_B_RUN=42820224990
MANAGER_A_TO_B=SUCCESS

PUBLIC_REPOSITORY_SAFETY_RUN=42820224957
PUBLIC_REPOSITORY_SAFETY=SUCCESS
```

Other PR-wide workflows are not substituted for these bounded KF-147 authorities. Historical generic staging/state-binding failures remain outside this gate and do not convert the Stage B physical PASS into a live failure.

## 2. Inherited physical authority

Stage B R3 remains the last physical authority:

```text
R3_EXECUTED_HEAD=675871a0567aca858c8af34f9eecf0a2e79ba063
R3_RESULT=PASS
R3_AUTHORIZATION_CLAIMED=true
R3_AUTHORIZATION_CONSUMED=true
R3_REPLAY_PERMITTED=false

MANAGER_IPC_V3_SUPPORT=true
CAPACITY_SNAPSHOT_PRESENT=true
U1_TRANSACTION_PRESERVED=true
PREPARE_CANDIDATE_PRESERVED=true

USB_MUTATION=false
U2_PLUS=false
ROLLBACK_REQUIRED=false
```

R2 and R3 one-shot authorizations remain permanently non-replayable.

## 3. Last-proven transaction facts are not a fresh baseline

Repository state records the following last-proven values:

```text
LAST_PROVEN_U1_PHASE=U1_PREPARE_REQUESTED
LAST_PROVEN_U1_TRANSACTION_SHA256=6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49
LAST_PROVEN_USB_CONFIRMATION_REQUIRED=true
LAST_PROVEN_USB_CONFIRMATION_CONSUMED=false
LAST_PROVEN_USB_CANDIDATE_MODEL=Extreme
LAST_PROVEN_USB_CANDIDATE_CAPACITY_BYTES=32017047552

LAST_PROVEN_KF147_CAPACITY_PASS=true
LAST_PROVEN_KF147_FREE_BYTES=5811048448
LAST_PROVEN_KF147_REQUIRED_FREE_BYTES=1736515716
LAST_PROVEN_KF147_POST_PEAK_FREE_BYTES=5685145468
```

These values are continuity evidence only. They must not be used as the destructive execution baseline.

```text
T1_NEXT_STAGE_BASELINE=UNKNOWN_FRESH
```

## 4. Independent source-contract review

Reviewed exact-head source includes:

- `host/greenhouse-manager/src/greenhouse_manager/runtime/t1_ota_manager.py`
- `tools/n3w_t1_core_updater_ha_ipc.py`
- `tools/n3w_t1_core_updater_ha_prepare.py`
- `tools/n3w_t1_core_updater_ha_usb_media.py`
- `tools/n3w_t1_core_updater_ha_prepare_host.py`
- relevant USB/IPC/capacity tests.

### 4.1 Manager-side admission

`CONFIRM_USB_ERASE` is accepted only when the public runtime already reports:

```text
phase=USB_REQUIRED_CONFIRMATION
usb_confirmation_required=true
```

The Manager rejects confirmation outside that state.

### 4.2 Host-side admission

The privileged host path rebinds the exact release admission and requires the existing transaction. It does not create or replay PREPARE for confirmation.

Before mutation the prepare controller rechecks:

```text
transaction phase == U1
confirmation_required == true
candidate exists
exactly one fresh eligible candidate exists
candidate fingerprint unchanged
candidate display model unchanged
candidate capacity unchanged
fresh capacity snapshot still admits the candidate
```

A candidate must remain removable mass storage, writable, non-root-backed and not a production mount.

### 4.3 Destructive confirmation contract

The source-owned format confirmation phrase is:

```text
T1_HOMEASSISTANT_USB_FORMAT_ALL_DATA
```

After admission succeeds, the controller persists:

```text
confirmation_required=false
confirmation_consumed=true
```

before invoking the physical media mutation path.

The host mutation order is:

```text
wipefs --all --force
-> sfdisk GPT rewrite
-> udev settle
-> mkfs.ext4 -F -L N3W-UPDATE
-> mount nodev,nosuid,noexec
-> filesystem UUID readback
-> filesystem self-test
-> measured usable-capacity check
```

Only after format/mount/readback and capacity verification does `record_media_bound()` transition the transaction from U1 to U2. The same worker then continues U2 -> U3 -> U4 target preparation when successful.

### 4.4 Failure semantics

Because `confirmation_consumed=true` is durably written before `wipefs`, an interruption or failure after confirmation consumption must not be treated as permission to click/replay the old confirmation automatically.

A successor execution gate must explicitly bind recovery behavior for any failure between confirmation consumption and the U2 durable transaction write.

```text
CONSUMED_CONFIRMATION_AUTO_REPLAY=false
OLD_R2_R3_AUTHORIZATION_REPLAY=false
PREPARE_REPLAY=false
```

## 5. Read-only preexecution verdict

```text
FINAL_ARCHIVE_CI=CLOSED_PASS
SOURCE_CONTRACT_REVIEW=CLOSED_PASS
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false

FRESH_T1_BASELINE_REQUIRED=true
FRESH_T1_BASELINE_ACQUIRED=false
DESTRUCTIVE_EXECUTION_READY=false

USB_CONFIRMATION_AUTHORIZED=false
USB_ERASE_AUTHORIZED=false
USB_PARTITION_WRITE_AUTHORIZED=false
USB_FORMAT_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
T1_LIVE_MUTATION_AUTHORIZED=false
MANAGER_IMAGE_MUTATION_AUTHORIZED=false
HOMEASSISTANT_IMAGE_MUTATION_AUTHORIZED=false
BROKER_IMAGE_MUTATION_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

The source path is suitable for a fresh destructive-gate preflight, but the destructive gate itself is not yet eligible because the real T1 state has not been freshly rebound after the R3/archive closure.

## 6. Fresh T1 evidence required before any destructive authorization

One bounded read-only collection must prove at least:

```text
U1 phase and ACTIVE status
exact transaction file SHA-256
exact transaction_id_sha256
prepare-state transaction/release binding
Extreme candidate fingerprint/model/capacity
confirmation_required=true
confirmation_consumed=false
fresh capacity snapshot
fresh current required bytes / recommendation
host daemon active
services owner active
Manager running + exact image identity
Home Assistant running + exact image identity
Broker running + exact image identity
restart/continuity indicators
no USB mutation already occurred
no U2+ transition already occurred
exact host release-policy/admission continuity
```

Any drift in U1, candidate identity, confirmation state, capacity, release admission, or core-service continuity is a STOP and requires a successor plan rather than destructive continuation.

## 7. Next gate

```text
NEXT_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_USB_CONFIRMATION_U2_FRESH_READONLY_BASELINE_20261110_01
NEXT_GATE_MODE=READ_ONLY
NEXT_GATE_LIVE_MUTATION=false
```

After that read-only gate closes PASS, a separate fresh successor destructive gate, fresh execution identity/state root and explicit one-shot user authorization are required before `CONFIRM_USB_ERASE`.

## 8. Archive status

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=not-required
PRIVATE_RAW_EVIDENCE_PRESENT=false
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=not-required
UNARCHIVED_CRITICAL_KNOWLEDGE=0
```
