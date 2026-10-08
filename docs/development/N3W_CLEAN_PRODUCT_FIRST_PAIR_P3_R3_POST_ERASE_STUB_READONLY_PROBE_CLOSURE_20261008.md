# N3-W Clean Product First-Pair — P3 R3 Post-Erase Stub Read-Only Probe Closure — 2026-10-08

```text
STATUS=CLOSED_PASS
SOURCE_OF_LIVE_EVIDENCE=OPERATOR_SUPPLIED_EXACT_EXECUTOR_STRUCTURED_OUTPUT
GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_R3_POST_ERASE_STUB_READONLY_PROBE_20261008_01
PR=522
PR_EXPECTED_STATE=OPEN_DRAFT_UNMERGED
```

## 1. Entry and provenance

The current physical candidate is the successful current-board P1 successor, not the earlier P1 R2 candidate.

```text
P1_SUCCESSOR_STATUS=CLOSED_PASS
P2_PREBOOT_RUNTIME_REFREEZE=PASS
CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc

P3_R2_LAST_COMPLETED_STEP=full_chip_erase
P3_R2_POST_ERASE_NO_STUB_READ_RETURN_CODE=2
P3_R2_POST_ERASE_FAILURE_CLASS=ROM_NO_STUB_SPI_ATTACH_OR_FLASH_ACCESS
P3_R2_USB_RECONNECT_FAILURE=false
P3_R2_FOUR_REGION_WRITE=false
P3_R2_AUTHORIZATION_CONSUMED=true
P3_R2_REPLAY=false

EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p3_r3_post_erase_stub_readonly_probe/executor.py
EXECUTOR_COMMIT=1a756826b4799e560ce67e8788a6e4df420b42ad
EXECUTOR_BLOB_SHA=08adc3bb346e026dcd3b3b9cd192194c8cceae02
ESPTOOL_VERSION=5.3.1
```

GitHub source/blob verification occurred before physical R3 execution. The physical closure below is adjudicated from the operator-provided executor JSON. Private raw stdout, stderr, readback bytes, physical locators and any credentials remain outside public GitHub.

## 2. Actual P3 R3 result

```text
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
BOARD_ACCESS=true

ROM_IDENTITY_PASS=true
SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc

STUB_READ_ATTEMPTED=true
STUB_READ_RETURN_CODE=0
POST_ERASE_PROBE_SIZE=4096
POST_ERASE_PROBE_SHA256=f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6
POST_ERASE_PARTITION_WINDOW_BLANK=true

STUB_READ_STDOUT_SHA256=66b93d3786564b7217449c919de57eee3291100909b4efb398d5e32a07b9bf91
STUB_READ_STDERR_SHA256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

FLASH_ERASE=false
FLASH_WRITE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
AUTO_WRITE=false
AUTO_P4=false

READY_FOR_WRITE_ONLY_SUCCESSOR=true
STOP=true
```

All defined P3 R3 pass predicates are met. The flasher stub was used for a read only, with an ephemeral RAM upload. The 0x8000..0x8FFF partition-table window readback is 4096 bytes of 0xFF. This does **not** independently prove every byte of the full 8 MB flash is blank, and does not prove any firmware write, four-region readback, or normal product boot.

## 3. Disposition / strict STOP

```text
P3_R3_RESULT=CLOSED_PASS
P3_R3_AUTHORIZATION_CONSUMED=true
P3_R3_REPLAY=false
CURRENT_BOARD_STATE=ERASED_UNWRITTEN
FULL_CHIP_ERASE_PREVIOUSLY_COMPLETED=true
FOUR_REGION_WRITE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false

FULL_CHIP_ERASE_AGAIN=FORBIDDEN
REPLAY_P3_R2=FORBIDDEN
REPLAY_P3_R3=FORBIDDEN
ROM_NO_STUB_FLASH_ACCESS_FOR_WRITE_READBACK=AVOID_PROVEN_FAILED_PATH
WRITE_FLASH=false
NORMAL_PRODUCT_BOOT=false
AUTO_WRITE=false
AUTO_P4=false
STOP=true
```

## 4. Successor boundary

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_SUCCESSOR_DESIGN_20261008_01
NEXT_GATE_TYPE=DESIGN_AND_SEPARATE_AUTHORIZATION_ONLY
P3_WRITE_ONLY_SUCCESSOR_AUTHORIZATION_GRANTED=false
P4_AUTHORIZATION_GRANTED=false
```

The proposed successor must rebind exact silicon and exact release artifact, perform **no** further full-chip erase, use the working stub flash access for four-region exact write and exact-length SHA256 readback, preserve `--after no-reset`/no normal product boot, and fail closed on any mismatch. The old P3/R2 authorization cannot cover it. Design approval and separate physical write authorization are required before any board write.
