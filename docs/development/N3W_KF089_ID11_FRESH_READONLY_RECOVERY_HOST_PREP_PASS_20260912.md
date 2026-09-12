# N3W KF-089 ID11 fresh read-only recovery host prep PASS — 2026-09-12

This record freezes the host-only preparation for recovering the Board B / Board A Schema-v5 diagnostics persisted by the already-consumed ID11 RF window.

```text
IDENTITY_CANONICAL_RULE_BOUND=true
IDENTITY_RAW_EVIDENCE_PERSISTED=true
IDENTITY_FAIL_CLOSED=true

SCHEMA_V5_READER_BOUND=true
NVS_OFFSET_BOUND=true
NVS_SIZE_BOUND=true
RAW_NVS_EVIDENCE_PERSISTED=true
SNAPSHOT_BLOB_EVIDENCE_PERSISTED=true

BOARD_B_READ_SEQUENCE_READY=true
BOARD_A_READ_SEQUENCE_READY=true
APPLICATION_BOOT_REQUIRED=false
SECOND_RF_CAPTURE_REQUIRED=false

WRITE_PRIMITIVE_PRESENT=false
AUTO_RETRY=false

HOST_TESTS_PASS=true
SINGLE_READONLY_AUTHORIZATION_CAN_COVER_BOTH=true
READY_FOR_PHYSICAL_READONLY_AUTHORIZATION=true

REAL_BOARD_ACCESS=false
RESULT=PASS
STOP_REASON=NONE
```

## Frozen identity rule

The physical readback successor accepts identity only from complete six-octet `BASE MAC:` lines, ignores ordinary/EUI64 `MAC:` lines, allows repeated identical BASE MAC lines, requires exactly one distinct BASE MAC, and compares the canonical value against the private expected board identity. USB device paths remain locators only and are never identity authority.

All identity command argv/stdout/stderr/result/validation evidence must be persisted privately before any NVS read proceeds.

## Frozen Schema-v5 readback rule

The successor is read-only and reuses the bound diagnostic reader for:

```text
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
NAMESPACE=gh_n3w_diag
KEY=snapshot
EXPECTED_SCHEMA=5
```

For each board it must persist the raw NVS partition, SHA-256, extracted snapshot blob, SHA-256, decoded snapshot JSON, and exact read-command evidence. Only identity/read-flash operations are permitted. No application boot, flash write, NVS write, otadata write, RF execution, or automatic retry is allowed.

## Physical successor shape

One new explicit read-only authorization may cover:

1. Board B ROM-only entry -> identity PASS -> one NVS read -> stop.
2. Board A ROM-only entry -> identity PASS -> one NVS read -> stop.

The already-consumed ID11 RF capture must not be repeated. Any identity failure stops the workflow immediately. The purpose of the successor is only to recover the persistent Schema-v5 counters left by ID11.
