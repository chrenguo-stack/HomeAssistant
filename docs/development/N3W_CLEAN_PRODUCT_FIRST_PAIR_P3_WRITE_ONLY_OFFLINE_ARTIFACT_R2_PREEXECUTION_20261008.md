# N3-W Clean Product First-Pair — P3 Write-Only Offline Exact-Artifact R2 Preexecution — 2026-10-08

```text
STATUS=AUTHORIZED_NOT_EXECUTED
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_OFFLINE_ARTIFACT_R2_20261008_01
ORIGINAL_P3_WRITE_ONLY_AUTHORIZATION_GRANTED=true
ORIGINAL_P3_WRITE_ONLY_AUTHORIZATION_CLAIMED=false
ORIGINAL_P3_WRITE_ONLY_AUTHORIZATION_CONSUMED=false
ORIGINAL_P3_WRITE_ONLY_AUTHORIZATION_SUPERSEDED=true
ORIGINAL_P3_WRITE_ONLY_AUTHORIZATION_REPLAY=false
OFFLINE_R2_PHYSICAL_AUTHORIZATION_GRANTED=true
OFFLINE_R2_AUTHORIZATION_CLAIMED=false
OFFLINE_R2_AUTHORIZATION_CONSUMED=false
BOARD_ACCESS=false
FLASH_ERASE=false
FLASH_WRITE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
AUTO_RETRY=false
AUTO_P4=false
STOP=true
```

## 1. Observed host-only download failure

The operator executed the exact original P3 Write-Only executor `481a368f1879e1e9f86bfc70ff36912128a8aaaa` and supplied a structured JSON closure:

```text
STAGE=P3_WRITE_ONLY_SUCCESSOR_NO_PRODUCT_BOOT
ERROR=ARTIFACT_DOWNLOAD_FAILED
ESPTOOL_VERSION=5.3.1
ARTIFACT_BINDING_PASS=false
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_PRECLAIM_PASS=false
FLASH_WRITE_ATTEMPTED=false
POTENTIAL_PARTIAL_WRITE=false
FOUR_REGION_WRITE=false
FULL_CHIP_ERASE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
STOP=true
```

The exact executor's download function runs `gh run download 37594598870 -R chrenguo-stack/HomeAssistant -n n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source` before enumerating or opening the serial port. The function reports only `ARTIFACT_DOWNLOAD_FAILED` when `gh` exits nonzero; the underlying Mac CLI stderr was not in the submitted structured closure. Therefore the **exact local download failure cause is not yet proven**. This is a host/artifact acquisition failure, not evidence of a product, Flash or USB issue.

## 2. Fresh GitHub artifact proof / independently verified bytes

```text
PR=522
PR_STATE_AT_REBIND=OPEN_DRAFT_UNMERGED
ARTIFACT_ID=11469977052
ARTIFACT_NAME=n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source
ARTIFACT_EXPIRED=false
ARTIFACT_EXPIRES_AT=2026-11-06T08:37:25Z

OUTER_ARTIFACT_SIZE=4341432
OUTER_ARTIFACT_SHA256=8587c7bf130f2f17e81b4e4f7652780f372f6a61697cc240e72a6af7392a7dc8
INNER_RELEASE_SIZE=4340810
INNER_RELEASE_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
OUTER_MEMBER_COUNT=2
INNER_MEMBER_COUNT=8
FOUR_REGION_BIN_LENGTH_AND_SHA256_MATCH=PASS
```

The outer ZIP was freshly obtained through the connected GitHub API and independently hashed and unpacked read-only. The four binaries match the exact artifact authority. The verified outer ZIP is made available to the operator as a chat file transfer. This does not by itself grant or execute a physical write.

## 3. Narrow offline artifact successor

```text
EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p3_write_only_offline_artifact_r2/executor.py
EXECUTOR_BLOB_SHA=d6c8d63e20a53b3c8a626bd9d7d23f36b3fa24fc
EXECUTOR_STATIC_SCOPE_CHECK=PASS
EXECUTOR_LOCAL_PYTHON_COMPILE=NOT_YET_EXECUTED
EXECUTOR_PHYSICAL_EXECUTION=false
OFFLINE_R2_PHYSICAL_AUTHORIZATION_GRANTED=true
OFFLINE_R2_AUTHORIZATION_CLAIMED=false
OFFLINE_R2_AUTHORIZATION_CONSUMED=false
```

Only the host-side artifact source is changed relative to the original exact write-only executor. Instead of issuing `gh run download`, the new executor requires `--outer-artifact` pointing at the locally downloaded **exact original outer ZIP**. Before any board access it requires matching outer exact size/SHA256, the exact two outer ZIP members, exact inner release size/SHA256, the sidecar digest, and all the existing frozen manifest/binary checks.

The unchanged physical contract remains:
- ROM/no-stub `get-security-info`, exact expected silicon binding and security-state guard.
- Stub flash-id to confirm 8 MB and stub blank probe 0x8000/0x1000 before claim.
- Only one exact four-region `write-flash` with flasher stub.
- Stub-based four exact-length SHA256 readbacks.
- `--before no-reset`, `--after no-reset`, no product boot.
- Any failure STOP; after claim authorization is consumed, even on partial write.
- No erase-flash, no erase-region, no T1 / Manager / Broker mutation or P4.

```text
EXPECTED_SILICON_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
BUILD_RUN_ID=37594598870
ARTIFACT_ID=11469977052
FULL_CHIP_ERASE_AGAIN=FORBIDDEN
CURRENT_BOARD_STATE=ERASED_UNWRITTEN
P3_R3_STATUS=CLOSED_PASS
```

## 4. Authorization / execution stop

The previous authorization is still **unclaimed and unconsumed** because all failures occurred before board access and before its write claim boundary. However, the previous approval was bound to executor blob `481a...`. Since this offline R2 executor has a different exact blob, the operator explicitly approved the new blob in the current project chat. The former original executor authorization remains unclaimed/unconsumed but is now superseded and must not be used or replayed.

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_OFFLINE_ARTIFACT_R2_20261008_01
NEXT_GATE_TYPE=EXACT_EXECUTOR_REBIND_THEN_ONE_SHOT_OPERATOR_AUTHORIZED_EXECUTION
OFFLINE_R2_PHYSICAL_AUTHORIZATION_GRANTED=true
OFFLINE_R2_AUTHORIZATION_CLAIMED=false
OFFLINE_R2_AUTHORIZATION_CONSUMED=false
AUTO_EXECUTE=false
AUTO_RETRY=false
AUTO_ERASE=false
AUTO_P4=false
STOP=true
```

Following explicit approval, the Mac must first save the known original outer ZIP locally and verify its SHA256, then fetch this exact executor blob, compile, and run it once with the expected silicon and `--outer-artifact`. On any mismatch or local failure before claim, return for review without board write. No success is claimed until actual four-region readbacks pass.


## 5. Explicit offline R2 authorization — 2026-10-08

The operator confirmed transfer to the exact offline artifact executor after the earlier host-only artifact download failure. **The original authorized executor's unclaimed status is not reused as a second active permission; the original permission is superseded, not consumed.**

```text
OFFLINE_R2_AUTHORIZATION_GRANTED=true
OFFLINE_R2_AUTHORIZATION_CLAIMED=false
OFFLINE_R2_AUTHORIZATION_CONSUMED=false
ORIGINAL_WRITE_ONLY_AUTHORIZATION_SUPERSEDED=true
ORIGINAL_WRITE_ONLY_AUTHORIZATION_CLAIMED=false
ORIGINAL_WRITE_ONLY_AUTHORIZATION_CONSUMED=false
ORIGINAL_WRITE_ONLY_AUTHORIZATION_REPLAY=false

EXACT_EXECUTOR_BLOB_SHA=d6c8d63e20a53b3c8a626bd9d7d23f36b3fa24fc
EXPECTED_SILICON_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
EXPECTED_OUTER_ARTIFACT_SHA256=8587c7bf130f2f17e81b4e4f7652780f372f6a61697cc240e72a6af7392a7dc8

ALLOWED=ONE_EXACT_STUB_FOUR_REGION_WRITE_AND_FOUR_EXACT_LENGTH_SHA256_READBACK
FULL_CHIP_ERASE_AGAIN=FORBIDDEN
AUTO_RETRY=false
AUTO_ERASE=false
AUTO_WRITE=false
AUTO_P4=false
PRODUCT_NORMAL_BOOT=false
STOP=true
```

Current product board still has not been accessed by the offline executor. Actual local ZIP presence, ZIP bytes, exact executor Git blob, Python syntax, serial port ownership, silicon identity, 8 MB flash and 4096-byte blank preclaim must be checked in that order before the new write claim. Any preclaim failure leaves the new authorization unclaimed; any failure after claim consumes the one-shot authorization. No automatic re-execution or P4 authorization is implied.
