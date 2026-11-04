# N3-W T1 Core Updater U1 R3 / KF-141 exact package closure and read-only runtime-state preexecution

Date: 2026-11-04

## 1. Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R3_KF141_EXACT_PACKAGE_CLOSURE_20261104_01
RESULT=CLOSED_PASS

PR=777
BRANCH=test/n3w-u1-manager-a-to-b-red-regression-20261104

EXACT_PACKAGE_SOURCE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
UPDATER_CI_RUN_ID=41854863798
UPDATER_CI_RUN_NUMBER=217
UPDATER_CI_RESULT=SUCCESS

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
AUTHORIZATION_REPLAY=false
ROLLBACK=false
BOARD_ACCESS=false
MERGE=false
```

This closure proves the repaired KF-141 updater package that will be used for
the next **read-only** real-T1 runtime classification. It does not authorize a
new A->B apply, rollback, service restart, transaction edit/delete or board
operation.

## 2. Exact CI closure

All jobs in updater run #217 passed:

```text
SOURCE_JOB=SUCCESS
EXACT_MANAGER_SLICE_JOB=SUCCESS
PRE_U1_V2_SIMULATION_JOB=SUCCESS
SOURCE_TESTS=135_PASSED
PRE_U1_V2_SIMULATION=1_PASSED
U1_B8_V2_PRE_U1_INSPECT_PLAN_SIMULATION=PASS
U1_B8_V2_TERMINAL_TRANSACTION_ARCHIVE=PASS
```

Same exact head also passed:

```text
CURRENT_AUTHORITY_CI_248=SUCCESS
FAST_SOURCE_CI_474=SUCCESS
PUBLIC_SAFETY_CI_6540=SUCCESS
U1_LIVE_EXECUTOR_CI_32=SUCCESS
```

## 3. Exact package identity

```text
PACKAGE_NAME=n3w-t1-core-updater-manager-v2-5b32e1ae8210
PACKAGE_ARTIFACT_ID=13336359358
PACKAGE_ARTIFACT_DIGEST_SHA256=e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
PACKAGE_SIZE_BYTES=63069383

CONTROL_PLANE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
UPDATER_PYZ_SIZE_BYTES=190325

TARGET_SCHEMA=gh.n3w-t1-core-updater-target/2
TRANSACTION_SCHEMA=gh.n3w-t1-core-updater-transaction/2
BASELINE_FILE_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc

TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
TARGET_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
TARGET_MANAGER_IMAGE_ID=sha256:80d34358094638ce9c8ce5fb2635fe0a5c75ee7cc5e8c628b38ab223134e585f
MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
MANAGER_TAR_SIZE_BYTES=62873600
MANAGER_REBUILT=false

UPSTREAM_MANAGER_ARTIFACT_ID=13319777217
UPSTREAM_MANAGER_ARTIFACT_DIGEST_SHA256=cb8794de2a5dc28f99c44e6369de403bec37db5b251c28e2edeeda22d281ce6c
UPSTREAM_MANAGER_RUN_ID=41826182757
```

## 4. Independent downloaded-artifact review

The final artifact was downloaded independently after CI completion and its ZIP
bytes were hashed again.

```text
DOWNLOADED_ZIP_SHA256=e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
DOWNLOADED_ZIP_MATCHES_GITHUB_DIGEST=true
```

The package contains exactly five files:

```text
greenhouse-manager-arm64.tar
manager-target-v2.json
package-binding.json
t1-core-updater.pyz
upgrade-baseline-a.json
```

Per-file independent hashes:

```text
greenhouse-manager-arm64.tar
SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
BYTES=62873600

manager-target-v2.json
SHA256=6d09dd585cdff9b2f1800b76e6c8a6326d1104a8b448d8739c3873905a44e442
BYTES=1231

package-binding.json
SHA256=b227f2e5bb2f68629442bf1e3f8a190a1956884d4499fb4ecbe13154ab86bba2
BYTES=1246

t1-core-updater.pyz
SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
BYTES=190325

upgrade-baseline-a.json
SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BYTES=2275
```

The downloaded `package-binding.json` binds the exact package to
`CONTROL_PLANE_HEAD=fc1e1bee...`, the unchanged Manager B image bytes, the
exact U0/Pre-U1 Baseline A bytes, and the exact upstream Manager artifact.

## 5. runtime-state command binding

Direct execution of the downloaded exact pyz help returns:

```text
usage: t1-core-updater [-h]
  {inspect,baseline,plan,apply,rollback,status,runtime-state} ...
```

Therefore the exact artifact contains the new updater-owned read-only
`runtime-state` command. No separate side-channel probe or alternate updater
binary is required for the next gate.

## 6. Preserved live boundary

The R3 one-shot apply authorization remains consumed:

```text
AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_U1_V2_20261104_02
CLAIMED=true
CONSUMED=true
REPLAY_PERMITTED=false
```

The last durable live transaction evidence remains:

```text
TRANSACTION_SCHEMA=gh.n3w-t1-core-updater-transaction/2
TRANSACTION_STATUS=FAILED_EMERGENCY
TRANSACTION_PHASE=FAILED_EMERGENCY
RECOVERY_REQUIRED=true
LIVE_RUNTIME_CLASS=UNKNOWN_FRESH
```

Do not infer the current live Manager from the failed transaction alone.

## 7. Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U1_R3_KF141_READONLY_RUNTIME_STATE_CLASSIFICATION_20261104_01

T1_ACCESS=true
T1_RUNTIME_MUTATION=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
SERVICE_RESTART=false
TRANSACTION_WRITE=false
TRANSACTION_DELETE=false
BOARD_ACCESS=false
MERGE=false
```

Purpose: use the exact repaired pyz to classify the real T1 from fresh runtime
facts as one of:

```text
PREDECESSOR_BOUND_RUNNING
TARGET_BOUND_RUNNING
APPLICATION_STOPPED_PREDECESSOR
APPLICATION_STOPPED_TARGET
UNRESOLVED
```

with a separate health state:

```text
HEALTHY
CONVERGING
NOT_RUNNING
FAILED
```

The next gate is read-only. It must not call apply or rollback and must not
modify the current `FAILED_EMERGENCY` transaction.

## 8. Closure

```text
KF141_SOURCE_REPAIR_PACKAGE=CLOSED_PASS
EXACT_PACKAGE_REVIEW=CLOSED_PASS
RUNTIME_STATE_COMMAND_IN_EXACT_PYZ=PASS
LIVE_RUNTIME_CLASSIFICATION=NOT_EXECUTED
NEW_LIVE_APPLY_ALLOWED=false
OLD_AUTHORIZATION_REPLAY_ALLOWED=false
BLIND_ROLLBACK_ALLOWED=false
STOP=true
```
