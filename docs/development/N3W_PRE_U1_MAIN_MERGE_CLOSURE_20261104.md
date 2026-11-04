# N3-W Pre-U1 main merge closure

Date: 2026-11-04

## Result

```text
PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE=CLOSED_PASS
PR774_MERGED=true
PR773_MERGED_TO_MAIN=true
PR773_HEAD=a5d959deefc42afb5fdc96fa1ad9c46d36de526b
PR773_MERGE_COMMIT=d910e3b389f447c3e3d664dc6514d1ebe4b33ff2
MAIN_MATCHES_PR773_MERGE_COMMIT=true

U0_REOPEN=false
U1_AUTO_RESUME=false
```

PR #774 was first merged into the stacked R3/A1/A2 branch. PR #773 then converged that entire stacked branch to `main` after its exact head passed all relevant CI. The final merge was locked with `expected_head_sha=a5d959deefc42afb5fdc96fa1ad9c46d36de526b`.

Post-merge verification confirmed that `main` is identical to merge commit `d910e3b389f447c3e3d664dc6514d1ebe4b33ff2`.

The frozen Pre-U1 business runtime reference remains:

```text
infra/n3w-t1/clean-reference/pre-u1-business-runtime-reference-20261104.json
```

The Pre-U1 acceptance remains fully closed PASS across G0-G5. The Node A post-G4 boot-session change is recorded as operator-initiated. No Pre-U1 gate is reopened by the repository convergence.

## Current boundary

```text
NEXT_ONE_GATE=UNSELECTED_AFTER_PRE_U1_MAIN_CONVERGENCE
AUTO_EXECUTE_NEXT_GATE=false
U1_MANAGER_A_TO_B_MAY_BE_RECONSIDERED=true
U1_AUTO_RESUME=false
STOP=true
```

No new live T1 mutation, board mutation, updater apply, updater rollback, or product runtime change is performed by this post-merge documentation alignment.
