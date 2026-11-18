# N3-W T1 U13B P3 U10 KF-167 source/CI closure and Attempt 03 freeze

Date: 2026-11-18

## Closure scope

Attempt 02 returned a safe read-only `STOP / ModuleNotFoundError` at `bind_durable_u9`. Receipt SHA-256 is `8f2275e25a1b5be8dfa6fa104ad2d2c529162a0c581585006c00c172d073b9ca`. No U10 transition, destructive cutover, predecessor deletion, target load or service mutation occurred.

KF-167 root cause was isolated-bootstrap import ordering. The durable U9 status path attempted its first `n3w_t1_core_updater_*` import before the exact frozen tools path had been loaded.

## Source repair

```text
KF167_SOURCE_REPAIR_HEAD=b80c7a66af713516f1ca32b6b4417b7f8cb01dd1
ATTEMPT03_EXACT_CANDIDATE=c7c51917d09cc774b5e97e5b7d0f9bcacfe64ea9
```

The repaired durable-U9 status path:
- validates and loads the exact frozen tools authority before its first product-module import;
- retains the historical U8 preclaim ledger binding path;
- keeps U10 preflight read-only, without execute mode or grant path;
- adds a focused import-order regression;
- makes the P3 live/read-only workflow execute the U9/U10 source checks and focused tests.

## Exact-candidate CI

```text
P3_LIVE_READONLY_SOURCE_RUN=44335289581 SUCCESS
CORE_STACK_CURRENT_AUTHORITY_RUN=44335289659 SUCCESS
MANAGER_A_TO_B_RUN=44335289799 SUCCESS
HA_2026_10_4_TARGET_BINDING_RUN=44335289530 SUCCESS
PUBLIC_REPOSITORY_SAFETY_RUN=44335290118 SUCCESS
FAST_SOURCE_EXACT_CLOSURE_RUN=44335289469 SUCCESS
SAME_VERSION_ACCEPTANCE_ARTIFACT_RUN=44335289680 SUCCESS
```

All workflows currently associated with exact candidate `c7c51917d09cc774b5e97e5b7d0f9bcacfe64ea9` completed successfully.

## Frozen physical boundary

```text
CURRENT_LIVE_STAGE=U9_LIVE_AUTHORIZATION_CLAIMED
U9_TRANSACTION_SHA256=2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b
U9_AUTHORIZATION=CONSUMED_NO_REPLAY
ATTEMPT03_MODE=READ_ONLY_ONLY
ATTEMPT03_PHYSICAL_RESULT=PENDING
U10_DESTRUCTIVE_AUTHORIZATION=false
U11_PLUS=false
```

A later operator-approved Attempt 03 must use exact candidate `c7c51917d09cc774b5e97e5b7d0f9bcacfe64ea9`. Documentation-only successors do not replace it. Physical PASS is required to close KF-167, but even that PASS proves only the read-only U10 eligibility contract.

Before destructive U10 can be considered, the customer bounded-recovery delivery requirement must still be reconciled against the recovery acceptance plan, and destructive U10 requires a new explicit authorization.
