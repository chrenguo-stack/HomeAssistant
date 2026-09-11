# N3W KF-089 Board B identity-r1 physical authorization granted — 2026-09-11

## Authorization

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_02
TARGET_ROLE=BOARD_B
PHYSICAL_AUTHORIZATION_GRANTED=true
PHYSICAL_AUTHORIZATION_CLAIMED=true
PHYSICAL_AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
AUTHORIZATION_RETIRED=true
```

The user explicitly granted this one-time successor authorization after the ROM identity parser defect was repaired and replayed successfully against the consumed private evidence.

The executor later proved expected-identity argument construction, but the workflow stopped before opening Board B because the ID02 claim already existed. Under the active anti-replay rule, claim existence prevents starting the one-time workflow again even though no physical open occurred. Therefore ID02 is retired and must not be reused.

## Allowed workflow (historical scope)

1. Fresh rebind reviewed Guard base + identity-contract-r1 repair, local toolchain, firmware authority, and private expected Board B identity.
2. Discover the Board B port; the port is only a locator.
3. Fresh ROM identity check using identity-contract-r1.
4. Read existing app0 at 0x10000 for exactly 1115648 bytes and require the frozen SHA-256.
5. Read the full 0x2000 otadata preimage and prepare the recovery plan.
6. On the mutation connection, recheck identity, app0 freshness, and otadata-preimage freshness.
7. Permit at most one 32-byte otadata entry mutation.
8. Read the full otadata back and require exact postcondition verification.
9. Only after PASS, allow one normal boot and a bounded Schema-v5 runtime observation.

## Hard limits

```text
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false
BOOTLOADER_WRITE_ALLOWED=false
PARTITION_TABLE_WRITE_ALLOWED=false
NVS_WRITE_ALLOWED=false
OTADATA_MUTATION_COUNT_MAX=1
OTADATA_ENTRY_WRITE_SIZE=32
MUTATION_RETRY=false
AUTO_SECOND_ATTEMPT=false
AUTO_ROLLBACK=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

## Current state

```text
PHYSICAL_AUTHORIZATION_GRANTED=true
PHYSICAL_AUTHORIZATION_CLAIMED=true
PHYSICAL_AUTHORIZATION_CONSUMED=false
AUTHORIZATION_RETIRED=true
REPLAY_PERMITTED=false
PHYSICAL_DEVICE_OPEN_OCCURRED=false
NEXT_ONE_GATE=USER_EXPLICIT_ID03_PHYSICAL_AUTHORIZATION
```
