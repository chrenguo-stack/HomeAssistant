# N3-W T1 KF-147 U5 Writable Mount Restoration Source Design / Preexecution Progress
# 2026-11-11

## Result

```text
TASK=N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_SOURCE_DESIGN_AND_PREEXECUTION_20261111_01
PR=807
BASE_SOURCE_HEAD=b72985f7570afc6ac3183090d3888742998789e9
SOURCE_HEAD=b84621714ba910da5b0bd401f85c677f00159275
DESIGN_FROZEN=true
PRODUCT_DAEMON_IMPLICIT_REMOUNT=false
DEDICATED_ONE_SHOT_RESTORATION_EXECUTOR_REQUIRED=true
SOURCE_REPAIR_REQUIRED=true

U5_PREFLIGHT_FORBIDDEN_OPTIONS=ro,noload,norecovery
RW_NORECOVERY_REGRESSION_TEST=true

TARGET_BINDING_RUN=43035002529
TARGET_BINDING_SOURCE=SUCCESS
TARGET_BINDING_EXACT=IN_PROGRESS
MANAGER_A_TO_B_RUN=43035002483
MANAGER_SOURCE=SUCCESS
MANAGER_EXACT_MANAGER_SLICE=IN_PROGRESS
FAST_CONTRACT_RUN=43035002462
FAST_CONTRACT=SUCCESS
CI_POLL_LIMIT_REACHED=true

T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
U4_TO_U5_TRANSITION=false
INSTALL=false
MERGE=false
```

## Design disposition

Existing product source does not convert an already-correctly-mounted recovery filesystem from read-only to writable. Changing that behavior would introduce implicit USB mutation into a general reopen path. The frozen design instead uses a dedicated one-shot restoration executor with a read-only preflight mode and a separately authorized execute mode.

The live mutation sequence is intentionally explicit: claim one-shot authority, unmount the exact recovery mount, rebind the same UUID/public fingerprint/root-excluded USB, fresh-mount ext4 with `rw,nodev,nosuid,noexec`, verify exact target/U4/runtime continuity, and stop before U5. If the transition fails after unmount, only one bounded rollback to `ro,noload,nodev,nosuid,noexec` is permitted; no retry loop.

A fresh normal ext4 writable mount may perform journal recovery. This is considered USB mutation and is why the later live step requires separate authorization.

## CI disposition

The source-level target-binding job and fast contract job passed at the new source head. The applicable exact jobs were still in progress at the third status check, so active polling stopped per project rules. No live T1 execution is permitted or attempted from this progress state.

Target binding run: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43035002529
Manager A-to-B run: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43035002483
Fast contract run: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43035002462

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_EXECUTOR_SOURCE_REPAIR_AND_CI_20261111_01
NEXT_GATE_MODE=REPOSITORY_ONLY
T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
MERGE=false
```
