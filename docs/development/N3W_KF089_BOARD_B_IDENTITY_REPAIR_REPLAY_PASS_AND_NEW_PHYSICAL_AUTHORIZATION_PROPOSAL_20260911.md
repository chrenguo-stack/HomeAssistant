# N3W KF-089 Board B identity-repair replay PASS and new physical authorization proposal — 2026-09-11

## Scope

This record closes the host-only replay of the ROM identity repair against the private evidence captured by the already-consumed first Board B physical attempt, and defines the next one-time physical authorization proposal. It does not itself grant physical authorization.

## Frozen facts

```text
MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755

OLD_AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
OLD_AUTHORIZATION_CONSUMED=true
OLD_AUTHORIZATION_REPLAY_PERMITTED=false

HOST_ONLY_ROM_IDENTITY_FORENSIC=PASS
FAILURE_CLASS=STDOUT_MULTIPLE_DISTINCT_CANDIDATES
BOARD_IDENTITY_MISMATCH_PROVEN=false

REPAIR_PR=385
REPAIR_REVISION=identity-contract-r1
REPAIR_IMPLEMENTATION_HEAD=af2ed8d5a62e84a83d4ba4593cf2442be3dff97d
BASE_REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
BASE_TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
REPAIR_ADAPTER_GIT_BLOB=c5cf94b4a2de482049e5ea8ceb420a395115e037
REPAIR_TEST_GIT_BLOB=532ae73e364a137607e7864561947311e03fb353

IDENTITY_REPAIR_REPLAY=PASS
AUTHORITATIVE_BASE_MAC_LINE_COUNT=2
AUTHORITATIVE_DISTINCT_BASE_MAC_COUNT=1
EXPECTED_IDENTITY_MATCH=PASS
BOARD_ACCESS_DURING_REPLAY=false
```

The private replay establishes that the already-captured stdout contains repeated authoritative `BASE MAC:` lines for one distinct Base MAC value and that this value matches the private trusted expected Board B identity. The first physical STOP is therefore adjudicated as a host-side parser defect, not a proven Board identity mismatch.

## Physical authorization eligibility

The following prerequisites are satisfied for a new successor authorization proposal:

```text
P0_EFFECTIVE_RESULT=PASS
IDENTITY_REPAIR_HOST_REVIEW_AND_CI=PASS
IDENTITY_REPAIR_REPLAY_AGAINST_CONSUMED_PRIVATE_EVIDENCE=PASS
EXPECTED_BOARD_B_IDENTITY_MATCH=PASS
OLD_AUTHORIZATION_REPLAY=false
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false
```

The successor must use the reviewed v0.2.2 mutation core through the `identity-contract-r1` repair adapter. The repair adapter must fresh-bind the exact reviewed base Git blob before execution.

## Proposed new authorization

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_02
TARGET_ROLE=BOARD_B
REPLAY_PERMITTED=false
PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false
```

This proposed authorization is not a continuation or retry token for the old authorization. It is a new one-time successor authorization created only after the old authorization was consumed and the failure was independently repaired and replay-validated host-only.

## Exact allowed physical workflow after explicit user grant

Before first physical open, fresh rebind all of the following:

```text
MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
BASE_TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
REPAIR_ADAPTER_GIT_BLOB=c5cf94b4a2de482049e5ea8ceb420a395115e037
REPAIR_TEST_GIT_BLOB=532ae73e364a137607e7864561947311e03fb353
REPAIR_REVISION=identity-contract-r1
ESPTOOL_VERSION=5.2.0
FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
EXPECTED_BOARD_B_IDENTITY_SOURCE=EXISTING_PRIVATE_TRUSTED_EVIDENCE
```

Then the only allowed sequence is:

```text
fresh port discovery
→ fresh ROM identity using identity-contract-r1
→ existing app0 exact readback at 0x10000, length 1115648
→ SHA256 compare against frozen firmware authority
→ full 0x2000 otadata pre-read
→ recovery plan
→ same mutation connection:
     identity recheck
     app0 MD5 freshness
     otadata preimage MD5 freshness
→ at most one 32-byte otadata entry mutation
→ full 0x2000 post-readback
→ exact postcondition verification
→ only after PASS: one normal boot
→ bounded Schema-v5 runtime observation
```

## Hard prohibitions

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

If ROM identity mismatches, app0 size/hash mismatches, tool/source binding drifts, or any pre-mutation freshness gate fails: STOP with no mutation.

If failure occurs after entering the mutation boundary: no retry, no automatic rollback, no automatic boot; only the Guard's single bounded read-only failure-state capture is allowed.

## Authorization consumption rule

After explicit user grant, the authorization becomes consumed at the first software open/connection to the selected Board B physical port under this workflow. Any STOP thereafter requires a new adjudication and, if needed, a new explicit authorization. The authorization must never be replayed.

## Current disposition

```text
IDENTITY_REPAIR_REPLAY_RESULT=PASS
NEW_PHYSICAL_AUTHORIZATION_ELIGIBLE=true
PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_EXECUTION=false
NEXT_ONE_GATE=USER_EXPLICIT_NEW_PHYSICAL_AUTHORIZATION
```
