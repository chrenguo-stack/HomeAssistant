# N3W KF-089 Board B identity-r1 physical authorization granted — 2026-09-11

## Authorization

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_02
TARGET_ROLE=BOARD_B
PHYSICAL_AUTHORIZATION_GRANTED=true
PHYSICAL_AUTHORIZATION_CLAIMED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
```

The user explicitly granted this one-time successor authorization after the ROM identity parser defect was repaired and replayed successfully against the consumed private evidence.

## Allowed workflow

1. Fresh rebind reviewed Guard base + identity-contract-r1 repair, local toolchain, firmware authority, and private expected Board B identity.
2. Discover the Board B port; the port is only a locator.
3. Fresh ROM identity check using identity-contract-r1.
4. Read existing app0 at 0x10000 for exactly 1115648 bytes and require SHA-256 `5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b`.
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

If any identity, app0, source/tool binding, or pre-mutation freshness check fails, STOP without mutation.

If failure occurs after entering the otadata mutation boundary, do not retry, do not auto-rollback, and do not auto-boot. Only the Guard's single bounded read-only failure-state capture is allowed.

## Consumption rule

The authorization becomes consumed at the first software open/connection to the selected Board B physical port under this workflow. Any STOP after that requires a new adjudication and, if needed, a new explicit authorization.

## Current state

```text
PHYSICAL_AUTHORIZATION_GRANTED=true
PHYSICAL_AUTHORIZATION_CLAIMED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false
PHYSICAL_EXECUTION=WAITING_FOR_MAC_CODEX
```
