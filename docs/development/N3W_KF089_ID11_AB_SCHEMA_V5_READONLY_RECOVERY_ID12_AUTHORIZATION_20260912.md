# N3W KF-089 ID11 A/B Schema-v5 read-only recovery — ID12 authorization — 2026-09-12

User explicitly authorized the bounded dual-board read-only recovery:

```text
AUTHORIZATION_ID=N3W_KF089_ID11_AB_SCHEMA_V5_READONLY_RECOVERY_20260912_12
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGETS=BOARD_B,BOARD_A
PURPOSE=RECOVER_ID11_PERSISTED_SCHEMA_V5_COUNTERS_WITHOUT_REPEATING_RF_TEST
```

Authorized scope:

1. Board B: ROM-only entry, exact identity confirmation, one read-only NVS capture, Schema-v5 decode, evidence persistence.
2. Board A: ROM-only entry, exact identity confirmation, one read-only NVS capture, Schema-v5 decode, evidence persistence.
3. Preserve raw identity command/stdout/stderr/result/validation and raw NVS partition + hashes + decoded snapshot for each board in private evidence storage.
4. Use canonical identity semantics already host-tested: complete `BASE MAC:` lines only, ignore EUI64/generic `MAC:` lines, allow repeated identical BASE MAC lines, require exactly one distinct BASE MAC and trusted expected-identity match.

Forbidden:

```text
APPLICATION_BOOT=false
SECOND_RF_CAPTURE=false
RESET_RETRY=false
AUTO_RETRY=false
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
PAIRING_CHANGE=false
FIRMWARE_REFLASH=false
T1_MUTATION=false
```

Fail closed on any identity mismatch, ambiguous identity, read failure, malformed NVS, schema mismatch, or evidence-persistence failure. Do not run the application between ID11 and successful readback. Do not repeat the RF experiment under this authorization.

The authorization is consumed at the first deliberate Board B or Board A physical access under ID12.
