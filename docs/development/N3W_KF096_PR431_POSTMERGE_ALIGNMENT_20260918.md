# N3-W KF-096 PR #431 Post-Merge Alignment

Updated: 2026-09-18  
Status: `CURRENT_PROGRESS_ALIGNMENT`

## Source authority

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
KF096_STATUS=OPEN

PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE_COMMIT=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
PR431_MERGED=true

MERGE_PARENT_MAIN=0f9c64d9e2c5953dbb93c162e08e6601ea0e7d33
MERGE_PARENT_PR431=137303c7b08fff36920d05e77c2f1bcc20b38d1f
```

The merge commit has the exact Astra-approved PR #431 HEAD as its second parent. No source drift occurred between final review and merge.

## Final source review closure

Astra round 3 was bound to exact HEAD `137303c7b08fff36920d05e77c2f1bcc20b38d1f` and concluded:

```text
A1_PARTIAL_INIT_TEARDOWN=CLOSED
A2_STARTUP_UNCONFIRMED_EXIT=CLOSED
REAL_DRIVER_FAULT_INJECTION_COVERAGE=SUFFICIENT
NO_NEW_MERGE_BLOCKER=true
```

The final source repair includes:

- explicit BSSID-lock authority from ESPHome selected configuration rather than runtime IDF `bssid_set`;
- bounded unicast-completion and Relay restore/quiesce exits;
- fresh-boot isolation for abnormal missing ESP-NOW completion;
- explicit `espnow_started_` tracking so partial initialization cannot lose its deinit obligation;
- fail-safe reboot when startup encounters an unconfirmed teardown;
- real driver lifecycle fault-injection host coverage for PMK/callback-registration rollback and repeated deinit failure.

These source-level results do not close KF-096.

## Pre-merge and post-merge CI

Exact PR #431 review HEAD:

```text
PREMERGE_CI_TOTAL=11
PREMERGE_CI_SUCCESS=11
PREMERGE_CI_FAILURE=0

PHASE4_SIMPLIFIED_PRODUCT_RUNTIME=PASS
ESP32_C6_CHILD_COMPILE=PASS
ESP32_C6_RELAY_COMPILE=PASS
ESP32_C6_PHYSICAL_HARNESS_COMPILE=PASS
```

Merge commit post-merge checks:

```text
PUBLIC_REPOSITORY_SAFETY_CI=PASS
PUBLIC_REPOSITORY_SAFETY_RUN=35321513253

GREENHOUSE_MANAGER_CI=PASS
GREENHOUSE_MANAGER_RUN=35321513207

POSTMERGE_PHASE4_SIMPLIFIED_PRODUCT_RUNTIME=PASS
POSTMERGE_ESP32_C6_CHILD_COMPILE=PASS
POSTMERGE_ESP32_C6_RELAY_COMPILE=PASS
POSTMERGE_ESP32_C6_PHYSICAL_HARNESS_COMPILE=PASS
```

## Artifact authority transition

The PR #428 exact artifact remains historical evidence only:

```text
PR428_ARTIFACT_DISPOSITION=FROZEN_HISTORICAL_NOT_FOR_DEPLOYMENT
```

Board B still runs the frozen PR #425 artifact. No PR #428 or PR #431 firmware has been written to Board B.

A new physical candidate must be built from the exact merged PR #431 product source authority:

```text
NEXT_PRODUCT_SOURCE_AUTHORITY=
d1b5c3acbd32cca95483743ffe2edba9aa3f904f
```

A later documentation-only main advancement must not redefine that product-source authority.

## Next gate

```text
NEXT_ONE_GATE=
N3W_KF096_PR431_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260918_01

SOURCE_AUTHORITY=
d1b5c3acbd32cca95483743ffe2edba9aa3f904f

ARTIFACT_BUILD=NOT_EXECUTED
ARTIFACT_BINDING=NOT_EXECUTED

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
T1_MUTATION=false
```

The next gate is host/GitHub artifact preparation only. It must first freeze the exact source, target configuration, toolchain, workflow provenance, expected artifact contents, and hash-binding procedure. Artifact construction/deployment is not implied by this documentation alignment.

## Physical acceptance remains pending

KF-096 remains OPEN until a newly bound exact PR #431 artifact is physically validated.

Required later physical evidence includes:

- Relay steady-state continuity;
- Direct recovery/failback timing;
- synchronous scan duration and main-loop stall;
- sampling cadence and Manager arrival cadence;
- 2 s completion-timeout false-trigger rate and abnormal reboot behavior;
- current radio channel / peer channel / raw ESP-NOW error oracle;
- ordered buffered submission and observable queue exhaustion;
- explicit recognition that an abnormal reboot loses RAM FIFO contents.

```text
KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```
