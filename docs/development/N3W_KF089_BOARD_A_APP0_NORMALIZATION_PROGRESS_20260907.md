# N3-W KF-089 Board A App0 Normalization Progress — 2026-09-07

Status: `PUBLIC_SAFE_PROGRESS_ARCHIVE`

## Scope

This record archives the latest public-safe physical evidence after the completed Board A serial-free durable diagnostic baseline. It records the successful app0-only normalization and the remaining postcheck boundary. It does not contain raw NVS, board identities, credentials, keys, remote-host details or other private evidence.

## Stable product/source authority

```text
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
FIRMWARE_SIZE=1114144
DIAGNOSTIC_SCHEMA_VERSION=3
```

A fresh compare from product authority `483ff1c...` to repository main `3f3deb6...` found only `docs/development/` descendants. No product/test source change after PR #370 was found at this alignment point.

## Code / source results already archived

No new product-source modification occurred in the physical normalization work documented here. Current code results remain:

```text
PR_369=MERGED
PR_369_PURPOSE=remove live Wi-Fi association as provisioned runtime startup prerequisite
PR_370=MERGED
PR_370_PURPOSE=lab-only relay-discovery observability schema v3
LAST_PRODUCT_SOURCE_CHANGE=PR_370
```

Therefore physical evidence below is bound to the exact PR #370 artifact, not to a later rebuilt or modified product image.

## Board A serial-free Direct baseline — frozen PASS

The prior remote-T1 + durable-snapshot execution established:

```text
T1_DIRECT_ACCEPTED_COUNT=18
T1_DIRECT_REJECTED_COUNT=0
T1_DIRECT_DUPLICATE_COUNT=0
T1_SEQ_FIRST=435
T1_SEQ_LAST=452
T1_INGRESS_SOURCE=direct

DIAG_BOOT_SESSION=11540229135812002993
T1_BOOT_SESSION=11540229135812002993
BOARD_A_DIAG_SESSION_BINDING=PASS
SESSION_ATTRIBUTION=PASS

DIAG_PATH_STATE=DIRECT
DIAG_CURRENT_CHANNEL=11
DIAG_DIRECT_CHANNEL_HINT=11
DIAG_SCAN_ATTEMPTS=0
DIAG_SCAN_SUCCESSES=0
DIAG_SCAN_FAILURES=0

DIAG_ADVERTISEMENT_ATTEMPTS=1304
DIAG_ADVERTISEMENT_SUBMIT_SUCCESS=1304
DIAG_ADVERTISEMENT_SUBMIT_FAILURE=0
DIAG_BROADCAST_COMPLETION_COUNT=1304
DIAG_BROADCAST_COMPLETION_SUCCESS=1304
DIAG_BROADCAST_COMPLETION_FAILURE=0

DIAG_DISCOVERY_RX=0
DIAG_CHALLENGE_TX=0
DIAG_ACCEPT_RX=0
DIAG_RELAY_ACTIVE_COUNT=0

BOARD_A_T1_ACCEPTANCE_BINDING=PASS
BOARD_A_DURABLE_DIAG_BINDING=PASS
BOARD_A_DIRECT_BASELINE=PASS
```

This is a complete Board A Direct baseline for the observability firmware and does not need to be repeated merely because the current chat changes.

## Board A app0-only normalization

Task:

`N3W_KF089_BOARD_A_APP0_NORMALIZATION_AND_POSTCHECK_20260907_01`

Before mutation:

```text
PRE_PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
PRE_OTADATA_SHA256=062f79dd9748aef0e56afddd5db3112af00549478e9d478e38137d5f3232f3a3
PRE_NVS_SHA256=b132280e337fac8b8cbbbf547fab33c28e12069fd96ce19ef072398cf385063d

PRE_APP0_IMAGE_SHA256=524690230c7164c889fd8cc4653c51bcba58132e187358b3685311b725c01825
PRE_APP1_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
PRE_SELECTED_SLOT=1
```

The exact authorized app0 mutation then passed:

```text
APP0_ERASE=PASS
APP0_IMAGE_WRITE=PASS
POST_APP0_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
APP0_IMAGE_VERIFY=PASS
APP0_UNUSED_TAIL_ERASED=true
```

Post-mutation invariants:

```text
POST_PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
POST_OTADATA_SHA256=062f79dd9748aef0e56afddd5db3112af00549478e9d478e38137d5f3232f3a3
POST_NVS_SHA256=b132280e337fac8b8cbbbf547fab33c28e12069fd96ce19ef072398cf385063d
POST_APP1_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
POST_SELECTED_SLOT=1

PARTITION_TABLE_PRESERVED=PASS
OTADATA_PRESERVED=PASS
NVS_PRESERVED_DURING_MUTATION=PASS
APP1_PRESERVED=PASS

BOARD_A_APP0_EXACT_OBSERVABILITY=PASS
BOARD_A_APP1_EXACT_OBSERVABILITY=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
```

No bootloader, partition table, otadata, app1, factory-image, T1 or AP mutation occurred.

## Postcheck did not execute because Board A remained in ROM

After the successful app0 normalization, Board A still responded as a ROM-download target and the remote T1 saw no application telemetry:

```text
POSTCHECK_T1_DIRECT_ACCEPTED=0
POSTCHECK_T1_DIRECT_REJECTED=0
POSTCHECK_T1_DIRECT_DUPLICATE=0
POSTCHECK_T1_SEQ_FIRST=NOT_OBSERVED
POSTCHECK_T1_SEQ_LAST=NOT_OBSERVED
POSTCHECK_T1_INGRESS_SOURCE=NOT_OBSERVED
```

Physical interpretation:

```text
BOARD_A_MODE=ROM_DOWNLOAD_MODE
BOOT_GPIO9_STILL_ASSERTED=true
APPLICATION_START_NOT_OBSERVED=true
PRODUCT_FAILURE=false
```

The postcheck failure classification in the execution closure must not be promoted to a firmware/product failure. The board did not attempt a normal application boot while BOOT/GPIO9 remained asserted.

## Current state and next boundary

```text
BOARD_A_DIRECT_BASELINE=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
BOARD_A_SELECTED_SLOT=1
BOARD_A_CURRENT_MODE=ROM_DOWNLOAD_MODE
BOARD_A_POSTCHECK=PENDING_OPERATOR_RELEASE_BOOT

BOARD_B_OBSERVABILITY_REFRESH=NOT_EXECUTED
KF089_AUTONOMOUS_RELAY_ACQUISITION=OPEN
PRODUCT_FAILURE=false
```

Next ONE gate:

```text
NEXT_ONE_GATE=KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK
```

The next gate must only release BOOT/GPIO9, perform one normal Board A power-cycle/start with BOOT released, and observe the real remote T1. It must not flash, read/write NVS, open serial, modify source, mutate T1, or begin Board B work.

## Harness / process conclusions

- Native-USB serial open was previously observed to reset this board with the reused collector; serial is not needed for the next gate.
- Real remote T1 Manager canonical acceptance is the current live runtime oracle; localhost is not T1 authority.
- Durable `gh_n3w_diag/snapshot` successfully replaced intrusive live-serial observation for the Direct baseline.
- Lab diagnostic NVS writes are expected and must remain separate from `PRODUCT_NVS_MUTATION` classification.
- Channel 11 is a valid current Direct/home channel and belongs to the frozen `{1,6,11}` allowlist.
- The current ROM state is consistent with BOOT/GPIO9 remaining asserted; release it before normal boot. Existing KF-088 remains the relevant central guard.
- No new product source repair is justified by the current evidence.
