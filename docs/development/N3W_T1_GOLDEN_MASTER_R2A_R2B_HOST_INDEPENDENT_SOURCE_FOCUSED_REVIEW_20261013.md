# N3-W T1 Golden Master R2A/R2B Host-independent Source Focused Review（2026-10-13）

TASK=
`N3W_T1_GOLDEN_MASTER_R2A_R2B_HOST_INDEPENDENT_SOURCE_FOCUSED_REVIEW_20261013`

## 0. Review authority

```text
REVIEW_HEAD=deb930fc9cbb1b68fd60266565a2b0c80387153f
DEDICATED_GOLDEN_MASTER_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
H0_H1_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
EXPLICIT_PROVISIONING_CI=PASS

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

The exact-head full workflow set still had unrelated long-running jobs when the review
started; the named source/compatibility gates above were completed PASS.

## 1. Findings

### A1 — target-specific OS-identity authority was not bound into capture readiness

Status at review head: **BLOCKER**.

`audit_golden_master_seal()` accepted any adapter that returned the expected boolean
identity fields plus an arbitrary audit hash. It did not require proof that the identity
classification came from the exact reviewed target-Armbian contract.

That meant a future generic Linux adapter could return `capture_neutral=true` and allow
`disk_capture_ready=true`, which violates the P2B rule that generic Linux assumptions
are not clone/seal authority.

Required repair:

- identity audit must assert `target_specific=true`;
- identity audit must bind a 64-hex `target_identity_contract_sha256`;
- preparation must bind the same target contract;
- post-seal audit must retain the same target contract;
- seal record must carry that public-safe contract hash;
- drift must fail before marker write.

### A2 — R2A/R2B package is not yet closure-ready

Status: **OPEN IMPLEMENTATION GAP**, not a defect in the new pure module.

The design requires host wrappers, release manifest production, one-shot authorization
ledger semantics, and public-safe build/seal evidence. At the review head only the pure
Seal contract, tests, CI and the R8 master-preflight adapter existed.

Therefore:

```text
R2A_R2B_HOST_INDEPENDENT_SOURCE=CANNOT_CLOSE_YET
R2_LIVE_EXECUTION_NOT_AUTHORIZED=true
```

### A3 — real target-Armbian mutation remains correctly absent

Status: **PASS / HOLD**.

No concrete machine-id, SSH host-key, NetworkManager, journal or random-seed mutation
is present in the pure Seal module. R2C target evidence remains required before that
adapter may be implemented.

## 2. Repair disposition

A1 is repaired immediately in the next source commit.

A2 stays as the next repository-only implementation work after the A1 repair CI.

A3 remains intentionally held for a separately authorized T1 read-only evidence gate.
