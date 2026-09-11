# N3W KF-089 Board B — ID03 physical authorization granted — 2026-09-11

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_03
TARGET_ROLE=BOARD_B
PHYSICAL_AUTHORIZATION_GRANTED=true
PHYSICAL_AUTHORIZATION_CLAIMED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
```

The user explicitly granted ID03 after ID02 was retired by the anti-replay rule before any physical device open.

The already-fixed expected-identity argument construction path must be used. Do not expose the real MAC in public output.

Allowed workflow:
1. Fresh-bind the reviewed Board-B recovery Guard, identity-contract-r1 repair, toolchain, firmware authority, and private Board B identity.
2. Create a fresh empty private evidence directory and a fresh ID03 claim.
3. Discover the Board B port; the port is only a locator.
4. Fresh ROM identity check.
5. Read existing app0 only and verify exact size/hash; app0 write/reflash is forbidden.
6. Read full otadata preimage and prepare the recovery plan.
7. On the mutation connection, recheck identity, app0 freshness, and otadata freshness.
8. Allow at most one 32-byte otadata entry mutation.
9. Read back full otadata and require exact postcondition verification.
10. Only after PASS, allow one normal boot and bounded Schema-v5 runtime observation.

Hard limits:
```text
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false
OTADATA_MUTATION_COUNT_MAX=1
MUTATION_RETRY=false
AUTO_SECOND_ATTEMPT=false
AUTO_ROLLBACK=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

Any failure stops the workflow. No automatic retry or rollback.
