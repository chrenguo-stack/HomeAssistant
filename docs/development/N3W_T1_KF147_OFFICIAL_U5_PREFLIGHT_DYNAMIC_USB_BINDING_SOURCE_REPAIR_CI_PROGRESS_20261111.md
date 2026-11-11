# N3-W T1 KF-147 Official U5 Preflight Dynamic USB Binding Source Repair / CI Progress
# 2026-11-11

## 1. Boundary result

```text
TASK=N3W_T1_KF147_OFFICIAL_U5_PREFLIGHT_DYNAMIC_USB_BINDING_SOURCE_REPAIR_AND_CURRENT_MOUNT_VALIDATION_20261111_01
PR=807
SOURCE_REPAIR_HEAD=b72985f7570afc6ac3183090d3888742998789e9
SOURCE_REPAIR_TREE=92e47f86cd2549cb28f14207984af92dc5403eb6
SOURCE_REPAIR_COMMIT=fix(kf147): bind U5 preflight to stable USB identity

EXECUTOR_BLOB=5f84233de74f36c1473a7dddc638e91db3d3143a
MANIFEST_BLOB=5746e3d67cac4e937c7f5083a9d1f7972223a199
TEST_BLOB=4f2fb90f94c13513552f0810b9125522b801e06c

FIXED_DEV_SDX_AUTHORITY_REMOVED=true
UUID_UNIQUE_BINDING_REQUIRED=true
TRANSACTION_USB_PUBLIC_FINGERPRINT_REQUIRED=true
USB_PARENT_PROPERTIES_REQUIRED=true
ROOT_DEVICE_EXCLUSION_REQUIRED=true
FILESYSTEM_CONTRACT_REQUIRED=true
ACTUAL_MOUNT_TARGET_SOURCE_REQUIRED=true
MOUNT_NAMESPACE_MATCH_REQUIRED=true
U5_WRITABLE_MOUNT_REQUIRED=true

OFFICIAL_U5_PREFLIGHT_PASS=false
T1_PREFLIGHT_EXECUTED=false
CURRENT_MOUNT_FRESH_STATE=UNKNOWN_FRESH
SOURCE_DEPLOYMENT=false
SERVICE_RESTART=false
U4_TO_U5_TRANSITION=false
USB_WRITE_OR_REMOUNT=false
HOMEASSISTANT_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

The source repair removes historical `/dev/sdb1` equality as an identity authority. The current
partition is located from the transaction-bound filesystem UUID, then bound to one USB parent disk
and checked with the product's public-fingerprint algorithm. USB/removable/read-only properties,
root-disk exclusion, ext4/`N3W-UPDATE`, transaction-derived mount target, actual mounted source
`MAJ:MIN`, and the OTA service mount namespace are all fail-closed checks.

The repair intentionally does **not** treat the prior U4 recovery mount as writable install
readiness. Product source `revalidate_and_request_install()` creates the U5 transaction state and
then calls `sync_transaction_metadata(u5, media)`, which writes transaction metadata to the bound
USB. Therefore an observed `ro,noload,nodev,nosuid,noexec` recovery mount is sufficient for the
completed read-only recovery verification but is not eligible for the U5 install-intent transition.
The repaired preflight requires `rw,nodev,nosuid,noexec` and rejects `ro` or `noload`. It does
not remount or otherwise mutate the media.

## 2. Regression coverage

The focused test now covers:

- same USB and UUID surviving `/dev/sdb1 -> /dev/sda1` renumbering;
- wrong USB fingerprint;
- duplicate UUID;
- non-USB, non-removable, or read-only parent block device;
- root-device collision;
- non-ext4 filesystem contract;
- unmounted media and media mounted at another target;
- actual mount-source mismatch by `MAJ:MIN`;
- preflight/service mount namespace mismatch;
- read-only/no-journal-replay mount rejection for U5 writable eligibility;
- absence of fixed `usb_partition` authority.

The new target-binding source job ran the KF-147 test set on exact head
`b72985f7570afc6ac3183090d3888742998789e9` and reported `331 passed in 2.71s`.

## 3. CI state at polling stop

```text
TARGET_BINDING_RUN=43031942495
TARGET_BINDING_SOURCE=SUCCESS
TARGET_BINDING_EXACT=IN_PROGRESS
TARGET_BINDING_POLL_LIMIT_REACHED=true

MANAGER_A_TO_B_RUN=43031941993
MANAGER_SOURCE=SUCCESS
MANAGER_EXACT_MANAGER_SLICE=SUCCESS
MANAGER_PRE_U1_V2_SIMULATION=SUCCESS

FULL_REPAIR_CI_PASS=false
T1_PREFLIGHT_ALLOWED=false
```

Per the repository CI polling rule, the target-binding exact job remained non-terminal after three
active checks, so no further automatic polling was performed. The bounded T1 preflight is not
permitted until the new source head's applicable target-binding CI reaches terminal SUCCESS.

## 4. Next safe entry

After an explicit later status check confirms target-binding run `43031942495` is fully SUCCESS:

1. fresh rebind PR #807 and exact source head;
2. fresh bind the private T1 SSH locator/known-host/host-key authority;
3. execute only the repaired bounded read-only official U5 preflight;
4. if the current mount is still `ro,noload`, expect a fail-closed
   `usb_mount_not_u5_writable` result and STOP;
5. do not remount, deploy source, restart service, transition U4->U5, install, enter U6+, access
   boards, or merge.

A PASS, if a fresh writable mount is already present without mutation by this task and all other
contracts match, must still stop at `FRESH_EXPLICIT_U5_INSTALL_AUTHORIZATION_REQUIRED`.

## 5. Archive audit

```text
ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=true
PRIVATE_RAW_EVIDENCE_PRESENT=false
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=not-required
REGRESSION_GUARD_ARCHIVED=true
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
SOURCE_REMOTE_HEAD=b72985f7570afc6ac3183090d3888742998789e9
SOURCE_REMOTE_EXACT_BINDING=PASS
NEXT_SAFE_ENTRY_POINT=TARGET_BINDING_RUN_43031942495_TERMINAL_SUCCESS_THEN_FRESH_BOUNDED_READONLY_PREFLIGHT
```

## 6. CI closure update

```text
CHECKED_AFTER_USER_REPORTED_SUCCESS=true
TARGET_BINDING_RUN=43031942495
TARGET_BINDING_SOURCE=SUCCESS
TARGET_BINDING_EXACT=SUCCESS
MANAGER_A_TO_B_RUN=43031941993
MANAGER_A_TO_B=SUCCESS
FULL_REPAIR_CI_PASS=true
PR_SOURCE_BRANCH_HEAD=b72985f7570afc6ac3183090d3888742998789e9
SOURCE_DRIFT_AFTER_REPAIR=false
T1_PREFLIGHT_ALLOWED=true
OFFICIAL_U5_PREFLIGHT_PASS=false
CURRENT_MOUNT_FRESH_STATE=UNKNOWN_FRESH
```

This supersedes the earlier polling-stop state in section 3. The source/test/CI boundary is now
closed PASS. The next action is the already-authorized private-identity-bound bounded read-only T1
preflight. It must not perform any mount-mode change or other mutation.

## 7. Real T1 current-mount validation

```text
T1_PREFLIGHT_EXECUTED=true
T1_ACCESS=true
READ_ONLY_PREFLIGHT=true
STATUS=STOP
REMOTE_RETURNCODE=2
REASON=Stop:usb_mount_not_u5_writable:nodev,noexec,norecovery,nosuid,relatime,ro
CURRENT_MOUNT_FRESH_STATE=READ_ONLY_NO_RECOVERY
OFFICIAL_U5_PREFLIGHT_PASS=false

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_EXECUTION_AUTHORIZED=false
REMOTE_STAGING=false
HOST_SOURCE_MUTATION=false
USB_MUTATION=false
HOMEASSISTANT_MUTATION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false
SSH_MASTER_CLEANUP=true
```

The real T1 result matches the repaired fail-closed contract. The current USB mount is read-only,
so it cannot admit U5 because the product U4→U5 path persists transaction metadata to the bound
media. The earlier recovery operation therefore remains valid as recovery evidence only.

The operator-local private evidence root was not copied into the public repository. The public
closure records only the sanitized terminal result supplied by the operator.

No remount or installation follows from this STOP. The next gate is
`N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_SOURCE_DESIGN_AND_PREEXECUTION_20261111_01`.
