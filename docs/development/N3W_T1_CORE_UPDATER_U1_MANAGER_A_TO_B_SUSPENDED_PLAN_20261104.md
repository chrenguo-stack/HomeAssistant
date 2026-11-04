# N3-W T1 Core Updater — Manager A -> B upgrade plan suspended

Date: 2026-11-04

## 0. Decision

```text
TASK=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_SUSPENSION_20261104_01
U0_RESULT=CLOSED_PASS
U1_MANAGER_A_TO_B_STATUS=SUSPENDED_BEFORE_TARGET_B_SOURCE_REPAIR
U1_PLAN_DISCARDED=false
U1_PLAN_PRESERVED=true
U1_LIVE_APPLY_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MANAGER_SOURCE_MUTATION=false
MERGE=false
```

The Manager A -> B route is intentionally paused before any Manager B source repair, target artifact
build, updater plan, or live T1 mutation.

The pause exists to insert a bounded normal-product-runtime acceptance stage after U0 and before U1.
That stage will exercise Home Assistant local onboarding, real sensor telemetry, an additional normal
node registration, multi-node runtime, and a fresh upgrade-safety revalidation.

U0 remains closed and immutable historical evidence. Normal business use after U0 does not rewrite or
invalidate the archived U0 evidence.

## 1. Preserved U1 authority

```text
MANAGER_A_PRODUCT_SOURCE=b863ddd959090ca139af76bd68dbef31d773e6de
MANAGER_A_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
BASELINE_A_MANIFEST=infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BASELINE_A_BYTES=2275
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
A2_ARCHITECTURE_SHA256=447f57f3563cb7766f145a2ea005d5d79d1beee7585ed07c6572ce2b3a833faa
UPGRADE_TOOL=T1_Core_Updater
DEFAULT_MUTATION_PROFILE=IMAGE_ONLY_V1
UPGRADE_REQUIRES_A_NOT_EQUAL_B=true
```

The already-reviewed updater source authority remains:

```text
A2_REVIEWED_SOURCE_HEAD=4dd39befedce891bd2db3cc84c592d41f778bc51
UPDATER_PYZ_SHA256=54f2e6299fa8905d33033ea86b5d449f16ad4dcd6ae8c7a3e9d647d6001e22fa
```

These values are preserved for provenance. A future U1 entry must still fresh-rebind the repository,
PR and exact artifact rather than assuming old workflow artifacts are still the correct Target B.

## 2. Manager A review result preserved

Independent source review found a real low-risk candidate product improvement:

```text
RECOMMENDED_TARGET_B_CHANGE=DISCOVERY_PUBLISH_FAILURE_RETRY_CORRECTNESS
REAL_PRODUCT_DEFECT_CANDIDATE=true
RED_REGRESSION_TEST_NOT_YET_EXECUTED=true
MANAGER_B_SOURCE_NOT_YET_CREATED=true
DATABASE_MIGRATION_REQUIRED=false
CONFIG_MIGRATION_REQUIRED=false
RUNTIME_TEMPLATE_CHANGE_REQUIRED=false
BROKER_CHANGE_REQUIRED=false
HOMEASSISTANT_CHANGE_REQUIRED=false
BOARD_CHANGE_REQUIRED=false
```

Authority:

`docs/development/N3W_MANAGER_A_PRODUCT_GAP_REVIEW_FOR_U1_TARGET_B_20261104.md`

The candidate defect is that Home Assistant Discovery de-duplication state can be committed before
the MQTT publish result is known. An immediate publish failure can therefore suppress the next
unchanged discovery attempt.

The candidate is not promoted to a formal known failure until a bounded RED regression proves the
failure against Manager A.

## 3. Preserved Manager B development route

When U1 is resumed, continue in this order:

```text
B0 fresh rebind Manager A / current repository / Pre-U1 business reference
B1 add bounded RED regression for Discovery publish failure -> retry
B2 prove RED against Manager A semantics
B3 implement minimum retry-correctness source repair
B4 run focused + full Manager source tests
B5 independent source closure review
B6 build exact linux/arm64 Manager B artifact
B7 bind exact image ID / source / target manifest / package
B8 T1_Core_Updater inspect + plan + simulation against fresh Pre-U1 reference
B9 explicit live-mutation authorization boundary
B10 real T1 Manager A -> B apply
B11 post-upgrade business continuity acceptance
B12 source-owned B -> A rollback validation when required by U1 acceptance
```

No step may manufacture B by retagging identical Manager image content.

## 4. U1 intended live acceptance remains unchanged

The eventual U1 must prove:

- only the Manager image binding changes;
- the existing Manager persistent state remains compatible;
- Broker image/config/state are not mutated;
- Home Assistant image/config are not mutated;
- the existing shared Manager/HA lifecycle ownership is handled as designed;
- all pre-existing registered nodes survive;
- MQTT identities remain bound;
- Home Assistant devices/entities remain continuous;
- normal telemetry resumes after the bounded upgrade interruption;
- rollback B -> A remains possible under the source-owned transaction contract;
- no consumed historical authorization is replayed.

The new Pre-U1 runtime stage strengthens this acceptance by ensuring the upgrade starts from a real
business state rather than a near-empty laboratory state.

## 5. Resume conditions

Manager A -> B may be resumed only after:

```text
PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE=CLOSED_PASS
PRE_U1_BUSINESS_RUNTIME_REFERENCE_FROZEN=true
PRE_U1_UPGRADE_SAFETY_REVALIDATION=PASS
MANAGER_A_TO_B_RESUME_DECISION=true
```

A PASS Pre-U1 stage does not itself authorize Manager source mutation or live U1 apply.

## 6. Current next route

```text
NEXT_ROUTE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE
U1_MANAGER_A_TO_B_STATUS=SUSPENDED
AUTO_RESUME_U1=false
```
