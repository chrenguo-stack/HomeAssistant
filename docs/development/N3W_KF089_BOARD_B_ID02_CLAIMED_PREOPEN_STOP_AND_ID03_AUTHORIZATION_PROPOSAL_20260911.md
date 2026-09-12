# N3W KF-089 Board B — ID02 claimed pre-open STOP and ID03 authorization proposal — 2026-09-11

## Result of ID02 attempt

The executor successfully constructed the private expected Board B identity argument without exposing the real MAC, but stopped before any physical device open because the one-time authorization claim for ID02 already existed.

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_02
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
EXPECTED_IDENTITY_ARGUMENT_CONSTRUCTION=PASS
PHYSICAL_DEVICE_OPEN_OCCURRED=false
ROM_IDENTITY_BINDING=NOT_EXECUTED
FLASH_READ=false
FLASH_WRITE=false
OTADATA_MUTATION=false
NORMAL_BOOT=false
RESULT=STOP
FIRST_FAILED_STAGE=AUTHORIZATION_ANTI_REPLAY_PREOPEN
```

## Adjudication

Although ID02 was not consumed by a physical device open, its claim already exists. Under the active anti-replay rule, a claimed one-time authorization may not be started again. Therefore ID02 is retired and must not be reused.

```text
ID02_REUSABLE=false
ID02_RETIRED=true
NEW_PHYSICAL_AUTHORIZATION_REQUIRED=true
```

This corrects the earlier interpretation that an unconsumed authorization could always be reused after a pre-open STOP. The stricter anti-replay rule is authoritative for this workflow: claim existence is sufficient to prevent a second start.

## Proposed successor authorization

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_03
TARGET_ROLE=BOARD_B
REPLAY_PERMITTED=false
PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_AUTHORIZATION_CLAIMED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false
```

The physical scope is unchanged from ID02:

1. Fresh-bind reviewed Guard base + `identity-contract-r1`, local toolchain, firmware authority, and private Board B identity.
2. Use the already-proven expected-identity construction path.
3. Discover Board B port and perform a fresh ROM identity check.
4. Read existing app0 only; do not write or reflash app0.
5. Require exact app0 size/hash match before any otadata mutation.
6. Read full otadata preimage and prepare recovery plan.
7. On the mutation connection, recheck identity, app0 freshness, and otadata freshness.
8. Allow at most one 32-byte otadata entry mutation.
9. Read back and verify exact postcondition.
10. Only after PASS, permit one normal boot and bounded Schema-v5 observation.

Hard limits remain unchanged: no app0 reflash, no second app0 flash, no mutation retry, no automatic rollback, no Board A access, and no T1 mutation.

## Current state

```text
EXPECTED_IDENTITY_ARGUMENT_CONSTRUCTION=PASS
ID02_RETIRED=true
NEW_PHYSICAL_AUTHORIZATION_ELIGIBLE=true
PHYSICAL_AUTHORIZATION_GRANTED=false
NEXT_ONE_GATE=USER_EXPLICIT_ID03_PHYSICAL_AUTHORIZATION
```
