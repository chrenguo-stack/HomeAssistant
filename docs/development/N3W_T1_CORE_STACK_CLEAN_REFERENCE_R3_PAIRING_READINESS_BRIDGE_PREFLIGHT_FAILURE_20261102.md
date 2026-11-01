# N3-W T1 Core Stack Clean Reference
# R3 Pairing-Readiness Bridge Read-Only Preflight Failure — 2026-11-02

## 0. Result

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_PAIRING_READINESS_BRIDGE_READONLY_PREFLIGHT_20261102
RESULT=STOP_PRECLAIM

PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R2A_CONTROL_HEAD=abeb6c31147bcf249361dcec7e9536eaed6106a6
R2B_CONTROL_HEAD=e15c64ac8f0f5f482a6c8538072031734002a559
R3_OBSERVER_CONTROL_HEAD=da9124fe18774cdb5822f9eb3afee40120cfb04f
BRIDGE_CONTROL_HEAD=37e269300d6fadeee7ad85476374813f879cdb23

R2_REFERENCE_SHA256=89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
FACTORY_ACCEPTED_CREATED=false
PAIRING_WINDOW_OPENED=false
BOARD_ACCESS=false
```

The bridge stopped during read-only inspect before any one-shot claim or product marker creation.

## 1. Exact bridge authority

```text
CI_RUN=41322028703
CI_RESULT=SUCCESS
TEST_COUNT=17

ARTIFACT_ID=13090105684
ARTIFACT_NAME=n3w-t1-clean-reference-pairing-readiness-bridge-37e269300d6fadeee7ad85476374813f879cdb23
ARTIFACT_DIGEST=sha256:c43d0bbd144d6d0e6e8ec5770e1b47f69e85d7e9dd7b4b72a5240d0e1055a7e8
PACKAGE_MANIFEST_SHA256=9f965a6efd191aa8166f9044527efbd5fe06ea986a0e0f8832d4a0ff079aeec3

R2A_BYTE_CONTINUITY=PASS
R2B_BYTE_CONTINUITY=PASS
R3_OBSERVER_BYTE_CONTINUITY=PASS
DEVICE_PROVISIONING_BLOB_BINDING=PASS
FIRST_PAIRING_ONBOARDING_BLOB_BINDING=PASS
```

## 2. Live preflight evidence

Before bridge inspect:

```text
R2_REFERENCE_LOCAL_AUTHORITY=PASS
BRIDGE_ARTIFACT_AUTHORITY=PASS
BRIDGE_LOCAL_EXACT_PACKAGE=PASS

TRANSPORT_RESIDUAL_COUNT_BEFORE=0
BRIDGE_STATE_PRESENT=false
FACTORY_ACCEPTED_PRESENT=false
FIRST_PAIRING_TRANSACTION_PRESENT=false
SUCCESSOR_RECOVERY_PRESENT=false
PRODUCT_MUTATION=false
BOARD_ACCESS=false
```

The bridge inspect then failed at:

```text
private_root_invalid:/var/lib/n3w-t1-provisioning
```

During exception handling, a second source error surfaced:

```text
NameError: name 'sqlite3' is not defined
```

Final script state:

```text
PAIRING_READINESS_INSPECT_RC=1
PAIRING_READINESS_AUTHORIZATION_CLAIMED=false
FACTORY_ACCEPTED_CREATED=false
PAIRING_WINDOW_OPENED=false
BOARD_ACCESS=false
```

Local shell session-save output is unrelated to T1/product behavior.

## 3. Proven source defect

Exact source review of `37e269300d6fadeee7ad85476374813f879cdb23` proves:

- the bridge calls `sqlite3.connect(...)`;
- the bridge catches `sqlite3.Error`;
- the module does **not** import `sqlite3`.

Therefore:

```text
SOURCE_DEFECT_SQLITE3_IMPORT=PROVEN
SOURCE_DEFECT_REQUIRED_REPAIR=true
T1_RUNTIME_DEFECT_FROM_SQLITE3=false
```

Why CI passed:

- `py_compile` validates syntax but does not resolve the missing global name;
- existing tests did not execute the real security-state SQLite path or the error handler with `sqlite3.Error`.

A repaired test set must execute those paths.

## 4. Proven invalid design assumption

The bridge V1 assumed the current Clean Reference already had the frozen standard device-provisioning authority in state `DEVICE_READY`.

Fresh source review proves the frozen product contract is:

```text
DEVICE_PROVISIONING_TRANSACTION_ROOT=/var/lib/n3w-t1-provisioning
MISSING_TRANSACTION_ROOT => UNPROVISIONED
TRANSACTION_ROOT_CREATED_ONLY_BY_EXPLICIT_DEVICE_PROVISIONING_START=true
DEVICE_READY_REQUIRES_COMPLETED_DEVICE_PROVISIONING_RECORD=true
```

The live preflight proved:

```text
/var/lib/n3w-t1-provisioning=ABSENT
```

Therefore:

```text
CURRENT_DEVICE_PROVISIONING_STATE=UNPROVISIONED_BY_FROZEN_CONTRACT
BRIDGE_ASSUMPTION_DEVICE_READY=INVALID
PROVISIONING_ROOT_ABSENCE_IS_NOT_RANDOM_DIRECTORY_LOSS=true
```

This does **not** prove T1 product identity is absent. R1/R2 successfully run the product stack and the R2 reference is healthy. It proves only that the old explicit device-provisioning state machine was not executed on this Clean Reference route.

## 5. Why the bridge must not simply create the missing directory

Creating an empty `/var/lib/n3w-t1-provisioning` directory would not produce a legitimate `DEVICE_READY` record.

The frozen device-provisioning verifier requires completed provisioning records and exact live host binding.

Therefore:

```text
EMPTY_PROVISIONING_ROOT_CREATION=FORBIDDEN
FAKE_DEVICE_READY_RECORD=FORBIDDEN
OLD_DEVICE_PROVISIONING_START_ON_RUNNING_R2=NOT_AUTHORIZED
```

The identity authority must be redesigned from existing Clean Reference evidence or through a separately justified bounded authority bridge.

## 6. Current safe state

```text
R2=CLOSED_PASS
R2_COMMON_REFERENCE=CLOSED_PASS
R3=IN_PROGRESS

FACTORY_ACCEPTED_CREATED=false
BRIDGE_AUTHORIZATION_CLAIMED=false
BRIDGE_AUTHORIZATION_CONSUMED=false
FIRST_PAIRING_TRANSACTION_PRESENT=false
PAIRING_WINDOW_OPENED=false
BOARD_ACCESS=false

T1_PRODUCT_RUNTIME_MUTATION_FROM_BRIDGE=false
```

The live command used temporary transport files under `/var/tmp`. Cleanup was registered in the Mac script, but no final residual-count output was reached after the early STOP.

Therefore:

```text
TEMP_TRANSPORT_CLEANUP_EXPECTED_BY_TRAP=true
TEMP_TRANSPORT_RESIDUAL_COUNT=UNKNOWN_FRESH
TEMP_TRANSPORT_REQUIRES_FRESH_READONLY_RECHECK=true
```

## 7. Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_PAIRING_READINESS_BRIDGE_SOURCE_REPAIR_AND_IDENTITY_AUTHORITY_REDESIGN_20261102_01
```

Purpose:

1. repair the proven missing `sqlite3` import;
2. add tests that execute the real security-state SQLite path and exception path;
3. fresh-readonly recheck temporary transport residue and current no-marker/no-claim state;
4. determine the correct Clean Reference authority for `host_instance_id` and `system_id` without pretending legacy device provisioning already ran;
5. update bridge design/source accordingly;
6. run dedicated CI and freeze a new exact artifact.

This gate does **not** authorize:

- creating `FACTORY_ACCEPTED.json`;
- starting legacy device provisioning;
- opening pairing window;
- Board access;
- pairing;
- service restart;
- reboot;
- merge.

## 8. Stop boundary

```text
AUTO_EXECUTE_LIVE_MARKER_CREATION=false
AUTO_EXECUTE_BOARD_GATE=false
AUTO_EXECUTE_PAIRING=false
AUTO_MERGE=false
```

After repaired source/CI, stop before any live marker creation unless a new bounded live gate is explicitly authorized.
