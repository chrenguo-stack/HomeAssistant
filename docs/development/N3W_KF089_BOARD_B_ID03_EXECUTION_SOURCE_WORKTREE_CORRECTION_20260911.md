# N3W KF-089 Board B ID03 execution-source worktree correction — 2026-09-11

## Root cause

The Board B ID03 host-only preparation failed because the executor was operating from the PR #387 successor-document checkout. PR #387 does not contain the OTA Guard implementation files. The R1 repair implementation lives on PR #385.

This is a checkout/source-materialization error, not a Guard source defect and not a Board B defect.

## Correct execution source

Use a dedicated detached temporary worktree for the exact reviewed repair implementation commit:

```text
REPAIR_IMPLEMENTATION_COMMIT=af2ed8d5a62e84a83d4ba4593cf2442be3dff97d
BASE_TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
REPAIR_ADAPTER_GIT_BLOB=c5cf94b4a2de482049e5ea8ceb420a395115e037
REPAIR_TEST_GIT_BLOB=532ae73e364a137607e7864561947311e03fb353
```

The existing PR #387 checkout may remain untouched and continue to serve as the durable successor/authorization record.

## Required host-only preparation

Before creating the ID03 claim or opening Board B:

1. Fetch PR #385 / `review/n3w-ota-guard-v0.2-20260911`.
2. Verify that commit `af2ed8d5a62e84a83d4ba4593cf2442be3dff97d` exists locally.
3. Create a fresh detached temporary worktree at exactly that commit.
4. In that worktree, verify:
   - `tools/n3w_ota_guard.py` Git blob equals `e7b0019cdb9673fbf4e23653dec561ea40ff757c`;
   - `tools/n3w_ota_guard_identity_contract_repair.py` Git blob equals `c5cf94b4a2de482049e5ea8ceb420a395115e037`;
   - `tests/tools/test_n3w_ota_guard_identity_contract_repair.py` Git blob equals `532ae73e364a137607e7864561947311e03fb353`.
5. Run the repair binding check from that exact detached worktree using the already-approved local Python interpreter.
6. Verify the exact esptool wrapper, firmware artifact, private expected Board B identity, empty private evidence directory, and fully constructed recovery command.
7. Only after every host-only preparation item passes may the executor create the ID03 claim and immediately execute the already-constructed recovery command.

## Authorization state

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_03
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

No new authorization is required while ID03 remains unclaimed.

## Physical limits remain unchanged

- Do not write or reflash app0.
- Verify the existing app0 before any otadata mutation.
- At most one 32-byte otadata mutation.
- No automatic retry or rollback.
- No Board A access.
- No T1 mutation.
