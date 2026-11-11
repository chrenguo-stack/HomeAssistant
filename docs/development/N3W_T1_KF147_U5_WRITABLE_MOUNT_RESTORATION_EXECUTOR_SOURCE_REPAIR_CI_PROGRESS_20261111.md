# N3-W T1 KF-147 U5 Writable Mount Restoration Executor Source Repair / CI Progress
# 2026-11-11

## 1. Source result

```text
TASK=N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_EXECUTOR_SOURCE_REPAIR_AND_CI_20261111_01
PR=807
SOURCE_HEAD=002b5158c525be18ff85b10d4ef1a94e16cc1866
SOURCE_TREE=b55e3c49638bc617d8593a78c98648cfe29e30e2

EXECUTOR_BLOB=00af29e42a71ccc31258a7635ec1267766ec5606
MANIFEST_BLOB=652559684848a004174b2e8bd3ccd5966630bbc3
TEST_BLOB=b2d484cfd7aa91a9c576cc8895f8dd3e4a5fdc80

LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
U4_TO_U5_TRANSITION=false
MERGE=false
```

## 2. Implemented contract

The new package supports a read-only `--preflight-only` mode and a separately gated
`--execute` mode. The committed manifest is intentionally ungranted, so execute mode is rejected
before T1 mutation until a later explicit authorization changes the manifest authority.

The live design encoded in source is:

1. exact U4/source/runtime/USB/recovery-mount preflight;
2. durable one-shot authorization claim;
3. post-claim revalidation;
4. explicit unmount of the exact transaction target;
5. prove the same UUID/fingerprint/root-excluded USB is unmounted across all descendants;
6. fresh ext4 mount with `rw,nodev,nosuid,noexec`;
7. verify writable mount source/target/options, exact target hash, exact U4 transaction and runtime continuity;
8. stop at writable-mount restoration; no U5 transition.

There is no `remount,rw`, no `request_install()`, no service restart, no Docker stop/rm/load and
no product source deployment.

## 3. Independent hardening review

The initial implementation at `af400bb578a96957faba43aa4b354456d5db7099` exposed two local
review findings:

- the post-unmount check only proved the bound partition was unmounted, not every descendant of the USB;
- rollback verification depended on the OTA service MainPID/mount namespace, which could incorrectly classify a safe recovery remount as failed if service drift triggered the original post-validation failure.

Exact source head `002b5158c525be18ff85b10d4ef1a94e16cc1866` repairs both. Rollback additionally checks the exact
U4 transaction SHA-256 after restoring the recovery mount.

## 4. CI state at polling stop

```text
TARGET_BINDING_RUN=43036123164
TARGET_BINDING_SOURCE=IN_PROGRESS
TARGET_BINDING_EXACT=PENDING_SOURCE

MANAGER_A_TO_B_RUN=43036122676
MANAGER_SOURCE=SUCCESS
MANAGER_EXACT_MANAGER_SLICE=IN_PROGRESS

FAST_CONTRACT_RUN=43036122788
FAST_CONTRACT=SUCCESS

PUBLIC_SAFETY_RUN=43036122783
PUBLIC_SAFETY=SUCCESS

CI_POLL_LIMIT_REACHED=true
FULL_SOURCE_GATE_CI_PASS=false
```

Per project rules, active polling stops after three checks without terminal applicable CI. This is
not a source-gate closure and does not authorize T1 access.

Run links:

- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43036123164
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43036122676
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43036122788
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43036122783

## 5. Next safe entry

```text
NEXT_SAFE_ENTRY=CONFIRM_EXACT_SOURCE_HEAD_APPLICABLE_CI_TERMINAL_SUCCESS
AFTER_CI_PASS=N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_READONLY_PREFLIGHT_20261111_01
READONLY_PREFLIGHT_ONLY=true
LIVE_UNMOUNT_OR_RW_MOUNT_AUTHORIZED=false
```

Even after CI PASS, the first real-T1 step is read-only preflight only. A separate explicit
authorization is required later for actual unmount/journal-capable writable mount restoration.

## 6. CI closure update

```text
SOURCE_HEAD=002b5158c525be18ff85b10d4ef1a94e16cc1866
TARGET_BINDING_RUN=43036123164
TARGET_BINDING_SOURCE=SUCCESS
TARGET_BINDING_EXACT=SUCCESS
MANAGER_A_TO_B_RUN=43036122676
MANAGER_SOURCE=SUCCESS
MANAGER_EXACT_MANAGER_SLICE=SUCCESS
MANAGER_PRE_U1_V2_SIMULATION=SUCCESS
FAST_CONTRACT_RUN=43036122788
FAST_CONTRACT=SUCCESS
PUBLIC_SAFETY_RUN=43036122783
PUBLIC_SAFETY=SUCCESS
FULL_SOURCE_GATE_CI_PASS=true
RESTORATION_MANIFEST_LIVE_AUTHORIZED=false
READONLY_PREFLIGHT_ALLOWED=true
```

This supersedes the earlier polling-stop status. The exact-head source gate is now CLOSED_PASS.
The next real-T1 action is read-only restoration preflight only.
