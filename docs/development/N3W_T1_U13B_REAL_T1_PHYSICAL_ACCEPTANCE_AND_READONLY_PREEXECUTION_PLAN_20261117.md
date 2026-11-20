# N3-W T1 U13B real-T1 physical acceptance and read-only preexecution plan — 2026-11-17

## 1. Purpose and entry authority

This document defines the boundary between the closed U13B repository source work and any future real-T1 physical acceptance.

Entry authority:

```text
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
DEFAULT_MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
STAGE_D_SOURCE_HEAD=a47fc818eaea84a7357d158e2c4f92b2367d8d44
READONLY_PREEXECUTION_EXACT_HEAD=c02335e728797c953e623cf439d314c0affc3d32
READONLY_PREEXECUTION_CI=16_OF_16_SUCCESS
HA_TARGET_BINDING_RUN=44042455343
MANAGER_A_TO_B_RUN=44042455250
CORE_STACK_CURRENT_AUTHORITY_RUN=44042455186

LAST_PROVEN_LIVE_TRANSACTION_PHASE=U13A_COMMITTED
LAST_PROVEN_LIVE_TRANSACTION_TERMINAL=true
NEXT_LIVE_FRESHNESS=UNKNOWN_FRESH

T1_ACCESS=false
T1_MUTATION=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

The successful U13A production transaction is not a rollback fixture. It must not be reopened, rewritten, replayed, or deliberately damaged merely to exercise U13B.

## 2. What this stage does and does not prove

The immediate next stage has two independent goals:

1. bind the repository-closed U13B read-only preexecution logic to fresh real-T1 facts without mutation;
2. prepare a controlled physical rollback acceptance scenario that starts from a new clean OTA transaction.

This stage does not itself authorize:

- a new destructive OTA claim;
- a live U13B rollback;
- service/image/data mutation;
- an artificial production outage;
- board access;
- PR merge.

Repository source and physical acceptance remain separate authorities.

## 3. Why the current U13A transaction cannot be used

The current durable historical result is:

```text
PHASE=U13A_COMMITTED
STATUS=COMMITTED
RECOVERY_REQUIRED=false
```

The U13B controller explicitly treats U13A as terminal, and the read-only preexecution classifier excludes U13A from the rollback domain.

Therefore a fresh read-only check against an unchanged current T1 is expected to stop as outside the U13B rollback domain. That is a correct safety result, not a failed U13B implementation.

A physical rollback test must start from a new transaction whose destructive authorization belongs only to that transaction.

## 4. Target selection rule for physical acceptance

The first rollback physical-acceptance transaction must use a target that is distinct from the current predecessor.

Required:

```text
TARGET_EXACT_RELEASE_AUTHORITY=true
TARGET_PLATFORM=linux/arm64
TARGET_ARTIFACT_HASH_BOUND=true
TARGET_ARTIFACT_SIZE_BOUND=true
TARGET_IMAGE_IDENTITY_BOUND=true
TARGET_DISTINCT_FROM_PREDECESSOR=true
TARGET_SOURCE_REVIEWED=true
```

Forbidden for the first rollback physical acceptance:

```text
REUSE_CURRENT_U13A_TRANSACTION=false
SAME_IMAGE_REAPPLY_AS_ROLLBACK_PROOF=false
UNBOUND_TEST_IMAGE=false
UNVERIFIED_LOCALLY_BUILT_IMAGE=false
STALE_TARGET_MANIFEST=false
```

A same-image reapply can exercise transaction plumbing but cannot prove real predecessor-image recovery. It is therefore not accepted as the primary physical U13B rollback proof.

If no distinct exact target authority is available, physical mutation stops before a new U9 claim.

## 5. Gate sequence

### P0 — repository/archive alignment

Closed by this document set.

Required durable facts:

```text
READONLY_PREEXECUTION_EXACT_HEAD=c02335e728797c953e623cf439d314c0affc3d32
READONLY_PREEXECUTION_CI=16_OF_16_SUCCESS
CURRENT_STATE_ALIGNED=true
PHYSICAL_ACCEPTANCE_PLAN_ARCHIVED=true
```

No T1 access.

### P1 — fresh real-T1 read-only binding

Purpose: establish current truth before generating a live-bound preexecution package.

Read only:

- current Host transaction document and hash;
- current phase/status/transaction ID;
- current bound USB presence and filesystem UUID;
- USB transaction metadata hashes when the bound medium is present;
- current recovery-content identities;
- current Manager/Broker/Home Assistant runtime identities;
- current persistent Home Assistant binding;
- current service/restart state required by the observer.

The binding probe must not:

```text
HOST_TRANSACTION_WRITE=false
USB_METADATA_WRITE=false
USB_FORMAT=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
U13B_TRANSITION=false
```

If the machine is still at U13A, the expected classification is a safe terminal/outside-domain STOP. The probe must not reinterpret that state as rollback eligible.

P1 output is a sanitized fresh binding record plus private evidence binding where required.

### P2 — exact-bound U13B read-only preexecution package

Only after P1 fresh facts exist, build a package pinned to:

- exact preexecution source head and file hashes;
- exact Host transaction ID/hash/phase;
- exact USB filesystem UUID;
- exact USB transaction metadata hashes;
- exact target/predecessor/backup recovery identities;
- expected current runtime and persistent binding identities;
- explicit read-only contract;
- explicit no-live-rollback authorization.

Package result must be content-addressed and fail closed on any fresh drift.

At current U13A, the package is expected to STOP outside the rollback domain. It must never write Host simply to manufacture an admissible state.

### P3 — clean OTA physical-acceptance transaction preparation

This is a future mutation gate and requires separate explicit authorization.

Start a new independent OTA transaction using the exact distinct target selected under Section 4.

The normal product path must create and verify:

- exact target archive on the bound ext4 USB;
- exact predecessor recovery archive;
- authenticated pre-upgrade HA data backup;
- recovery-content manifest;
- production prestate;
- capacity admission;
- one-shot transaction authorization.

Do not reuse the consumed authorization from the successful U13A transaction.

The first physical rollback acceptance should proceed only to:

```text
U11_TARGET_INSTALLED_STARTED
```

and stop before U12 target acceptance / U13A commit.

### P4 — real-T1 U13B read-only preexecution at U11

With the new transaction durably exact at U11, generate a fresh package bound to that transaction and execute only the repository-closed read-only preexecution logic.

Expected result:

```text
STATUS=U13B_READONLY_PREEXECUTION_PASS
ACTION=ROLLBACK_ELIGIBLE
RECONCILIATION_REQUIRED=false
ROLLBACK_EXECUTION_REQUIRED=true
HOST_TRANSACTION_WRITE=false
USB_METADATA_WRITE=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
```

Any authority drift, media mismatch, recovery-content mismatch, runtime mismatch, Host/USB divergence or observer error stops before rollback authorization.

### P5 — controlled rollback-mechanics physical acceptance

This gate is separately authorized from P4.

For the first physical rollback test, use an acceptance-only fault-injection decision at U11:

```text
FAILURE_CODE=target_health_acceptance_failed
ROLLBACK_ENTRY_ORIGIN=U11_TARGET_INSTALLED_STARTED
```

The fault injection must not corrupt the target image, USB metadata, recovery archives, HA data backup, network configuration, Broker or Manager merely to create failure evidence.

The acceptance harness may deliberately withhold the forward acceptance decision and invoke the already reviewed `U13BAutomaticRollbackCoordinator` with the bounded failure code.

This proves the real rollback mechanics:

```text
U11
-> U13B0_ROLLBACK_IN_PROGRESS
-> U13B1_TARGET_CLEANUP_COMPLETE
-> U13B2_PREDECESSOR_IMAGE_RESTORED
-> U13B3_HA_DATA_RESTORED
-> U13B4_PREDECESSOR_RUNTIME_STARTED
-> U13B_ROLLED_BACK
```

It does not by itself prove that a naturally failing Home Assistant target is automatically detected. Therefore a PASS here must be labeled:

```text
U13B_ROLLBACK_MECHANICS_PHYSICAL_PASS=true
U13B_NATURAL_FAILURE_AUTO_TRIGGER_PHYSICAL_PASS=false
```

No result from P5 may be described as full end-to-end automatic-failure acceptance.

### P6 — post-rollback read-only audit

Terminal PASS requires:

- Host phase/status exactly U13B_ROLLED_BACK/ROLLED_BACK;
- USB phase and mirrored Host transaction exact;
- same transaction ID and filesystem UUID;
- authorization remains claimed + consumed + non-replayable;
- target runtime/image cleanup matches the bounded contract;
- exact predecessor image/runtime ID restored;
- persistent Home Assistant binding selects predecessor;
- production /config mounted;
- Manager/Broker peers exact and running;
- HA restart count zero;
- Manager MQTT authenticated;
- Home Assistant MQTT authenticated;
- Home Assistant HTTP ready;
- restored HA data exactly equals the protected pre-upgrade recovery point under the Stage B verifier;
- no unrelated image/service/data mutation.

Only then may the rollback-mechanics physical gate close.

## 6. Host/USB split-write physical acceptance

The D3/D4 split-reconciliation path is not silently claimed by a normal no-crash P5 run.

A separate later physical fault-injection gate must create one controlled crash/process interruption after USB successor metadata is durable but before Host successor persistence.

Required read-only observation:

```text
CLASSIFICATION=USB_ONE_PHASE_AHEAD_RECONCILABLE
ACTION=HOST_RECONCILIATION_REQUIRED
ROLLBACK_OPERATION_REPLAY=false
```

Only after that read-only evidence may a separately authorized D3/D4 recovery run repair the Host using the exact mirrored successor and continue the normal controller.

This gate is intentionally deferred until the normal U11 -> terminal rollback mechanics pass.

## 7. Natural target-failure trigger acceptance

A later full end-to-end acceptance must verify the real target-health failure detector, not only a decision-layer injected failure.

That gate must use a separately reviewed deterministic failure mechanism that does not weaken the normal product path. Examples may be evaluated later, but no production fault-injection bypass is authorized by this plan.

Until that gate passes:

```text
U13B_NATURAL_FAILURE_AUTO_TRIGGER_PHYSICAL_PASS=false
FULL_U13B_END_TO_END_PHYSICAL_ACCEPTANCE=false
```

## 8. Power-loss/resume matrix

After the normal rollback-mechanics physical PASS, a later staged matrix should cover at least:

- interruption before U13B0 Host persistence;
- interruption after U13B1;
- interruption after U13B2;
- interruption after U13B3;
- interruption after U13B4;
- representative USB-one-phase-ahead split;
- bound USB temporarily absent;
- bound USB reinserted with same filesystem UUID;
- wrong USB present;
- recovery-content drift.

Each case requires a fresh read-only classification before any resumed mutation.

No already consumed physical authorization may be replayed to manufacture a second run.

## 9. Mandatory STOP conditions

Stop immediately if any of the following is true:

- current successful U13A transaction would need to be modified for the test;
- no distinct exact target authority exists;
- repository source drifts after package binding;
- fresh T1 facts do not equal the bound package;
- Host transaction is missing/invalid;
- bound USB is missing/ambiguous/wrong/read-write when strict RO is required;
- USB filesystem UUID or metadata authority drifts;
- target/predecessor/backup recovery identity drifts;
- current runtime/persistent binding is inconsistent;
- P1/P2/P4 read-only package attempts any production mutation;
- P4 does not return exact `ROLLBACK_ELIGIBLE`;
- user has not separately authorized the P3 or P5 live mutation gate;
- any live result cannot be reconciled to durable Host/USB evidence.

## 10. Authorization separation

The following are distinct grants and must not be collapsed:

```text
P1_REAL_T1_READONLY_BINDING_AUTHORIZATION
P3_NEW_CLEAN_OTA_TRANSACTION_AUTHORIZATION
P5_CONTROLLED_U13B_ROLLBACK_PHYSICAL_AUTHORIZATION
SPLIT_WRITE_FAULT_INJECTION_AUTHORIZATION
NATURAL_FAILURE_TRIGGER_ACCEPTANCE_AUTHORIZATION
```

A read-only authorization never implies a mutation authorization.

A consumed OTA authorization is transaction-scoped and never grants a second destructive claim.

## 11. Evidence and archive rules

Public GitHub may contain:

- source/test/doc commit hashes;
- package file hashes;
- sanitized transaction hashes/IDs;
- USB filesystem UUID only if project policy permits public exposure; otherwise use a private-evidence binding;
- public-safe recovery identities;
- structured PASS/STOP result;
- CI run IDs;
- mutation flags.

Secrets, credentials, protected HA backup contents and raw private evidence remain outside the public repository.

Every meaningful physical attempt, including a useful STOP, must be archived before the next physical boundary begins.

## 12. Immediate next gate

Repository planning is complete when this document and CURRENT_STATE are durably committed.

The next live-facing gate is:

```text
NEXT_ONE_GATE=N3W_T1_U13B_REAL_T1_READONLY_BINDING_PREFLIGHT_20261117_01
SCOPE=FRESH_REAL_T1_READONLY_BINDING_ONLY
T1_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

That gate may prove the current T1 is still terminal U13A and therefore not rollback eligible. That outcome is expected and safe.

Only after a separately authorized fresh clean OTA reaches U11 may the same read-only preexecution contract be expected to return `ROLLBACK_ELIGIBLE`.
