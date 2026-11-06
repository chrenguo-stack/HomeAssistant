# N3-W T1 Core Stack OTA baseline and repository convergence source alignment — 2026-11-06

## 1. Gate

```text
TASK=N3W_T1_CORE_STACK_OTA_BASELINE_AND_REPOSITORY_CONVERGENCE_SOURCE_ALIGNMENT_20261106_01
BASE_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
RESULT=SOURCE_ALIGNMENT_PREPARED

REPOSITORY_MUTATION=DOCS_PROCESS_ONLY
CURRENT_PRODUCTION_AUTHORITY_MUTATION=false
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This document converts the completed read-only convergence review into durable repository authority.
It does not change the accepted T1 runtime, current production image bindings, component artifacts,
or any live upgrade transaction.

## 2. Baseline layering

The project now distinguishes four different authorities. They MUST NOT be collapsed into one
generic "baseline".

```text
LAYER_1=HISTORICAL_CLEAN_REFERENCE
LAYER_2=COMPONENT_UPGRADE_BASELINE
LAYER_3=CURRENT_PRODUCTION_AUTHORITY
LAYER_4=IMMUTABLE_STACK_RELEASE
```

### 2.1 Historical Clean Reference

The historical clean reference is immutable engineering evidence. It is not the current live
release and is not rewritten when a successor is accepted.

### 2.2 Component Upgrade Baseline

A component upgrade baseline is transaction-scoped predecessor authority used by
`T1_Core_Updater` for inspect/plan/apply/rollback/recovery. It does not define the permanent
product version of the complete T1 stack.

### 2.3 Current Production Authority

The current accepted production authority remains:

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
CURRENT_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
```

This gate does not rewrite or supersede that manifest.

### 2.4 Immutable Stack Release

A Stack release is the immutable product-version authority for one exact accepted combination of:

- Manager;
- Home Assistant;
- Broker;
- required runtime contract;
- exact component identities.

The release archive is separate from current live authority. Advancing the accepted current release
must not mutate an older release.

## 3. T1_Core_Stack 1.0.0 role

The semantic-release work in PR #781 assigns the already accepted current production stack the
product version `T1_Core_Stack 1.0.0`.

The convergence rule is:

```text
STACK_1_0_0_ROLE=BOOTSTRAP_ACCEPTED_PRE_OTA_RELEASE
STACK_1_0_0_LIVE_ACCEPTED=true
STACK_1_0_0_REWRITE_REQUIRED=false
STACK_1_0_0_END_USER_OTA_PUBLICATION=false
```

Meaning:

- 1.0.0 names and freezes the already accepted production composition;
- it is the predecessor release authority for future Stack upgrades;
- it is not evidence that the end-user signed OTA publication pipeline already exists;
- later signed OTA releases must use the then-current reviewed release schema/contract;
- a future release must not retroactively edit 1.0.0 merely to add newer OTA metadata.

PR #781 remains unmerged. The exact representation of this role must be aligned while #781 is
converged inner-to-outer; this document does not modify its current unmerged `release.json` bytes.

## 4. Product OTA hierarchy

The frozen relationship is:

```text
PUBLIC_PRODUCT_CONCEPT=T1_Core_Stack_OTA
PRIVILEGED_EXECUTION_ENGINE=T1_Core_Updater

MANAGER_STRATEGY=GENERIC_V2_SUCCESSOR
BROKER_STRATEGY=GENERIC_V2_SUCCESSOR
HOMEASSISTANT_STRATEGY=MANDATORY_USB_SUCCESSOR
```

`T1_Core_Stack OTA` owns product release discovery, signed release authority, user control,
download/staging policy, stack-level transaction/orchestration and stack-level acceptance.

`T1_Core_Updater` remains the sole privileged local execution engine.

## 5. PR #714 disposition

PR #714 is no longer a current implementation authority.

```text
PR714_CURRENT_IMPLEMENTATION_AUTHORITY=false
PR714_DISPOSITION=SUPERSEDED_AFTER_REQUIREMENT_EXTRACTION
PR714_MERGE_REQUIRED=false
```

Two requirements remain valuable and are explicitly carried forward:

```text
PR714_CARRY_FORWARD_1=HA_INDEPENDENT_LOCAL_MAINTENANCE_OR_RECOVERY_SURFACE
PR714_CARRY_FORWARD_2=CONTENT_ADDRESSED_INCREMENTAL_DISTRIBUTION_EVALUATION
```

Interpretation:

1. The final product must retain an HA-independent recovery/control path if Home Assistant itself
   is unavailable during an update or recovery event. The exact UI, local name, TLS and access
   mechanism remain deferred.
2. Content-addressed / missing-layer distribution remains a candidate optimization for end-user OTA.
   It is not yet a frozen V1 transport requirement because the current Stack OTA architecture
   deliberately defers final bandwidth/download policy.

All other PR #714 product-OTA direction is superseded by the current semantic-release and
T1_Core_Stack OTA architecture.

## 6. Active stacked PR convergence

The active successor chain is:

```text
main
-> #779
-> #780
-> #781
-> #782
-> #784
-> #785
-> #786
-> #787
-> #788
```

Convergence MUST follow:

```text
STACKED_PR_CONVERGENCE=INNER_TO_OUTER_ONE_LAYER_AT_A_TIME
UPSTREAM_CI_NOT_REUSABLE_AFTER_TARGET_HEAD_CHANGES=true
DIRECT_PR788_TO_MAIN=false
MERGE_REMAINS_SEPARATE_DECISION=true
```

Each layer must receive fresh exact-head CI/review after its base changes.

PR #781 convergence must incorporate the 1.0.0 role clarification from Section 3 without
retroactively claiming that the complete signed end-user OTA pipeline is already implemented.

PR #788 remains the current Home Assistant mandatory-USB / Stack OTA successor architecture branch.
Its R1-R4 source evidence remains historical exact-head evidence and does not authorize live R5.

## 7. Historical open-PR disposition

Historical open PRs are divided into three classes.

### 7.1 Historical/docs route: closure candidate

```text
CLOSURE_CANDIDATE=
535,539,662,666,671,676,678,710,711,719
```

These primarily preserve historical design, evidence, progress or handoff state. They are not
current execution authority.

### 7.2 Development/test-only route: archive then closure candidate

```text
DEV_ARCHIVE_CANDIDATE=
663,724,726
```

Their development-only or physical-acceptance-only status must remain explicit in the closure
comment. No production eligibility is inherited from these branches.

### 7.3 Source/tool route: focused parity review required before closure

```text
SOURCE_PARITY_REVIEW_REQUIRED=
522,537,538,677,712,713
```

These branches contain source/tool changes. They MUST NOT be closed merely because they are old.
Before closure, focused review must prove each surviving requirement is already present in current
main/successor source or deliberately retired by a later architecture decision.

No PR is closed by this source-alignment gate.

## 8. Repository cleanup rules

```text
HISTORICAL_COMMITS_PRESERVED=true
PR_CLOSURE_IS_NOT_COMMIT_DELETION=true
BRANCH_DELETE_IN_THIS_GATE=false
PR_CLOSE_IN_THIS_GATE=false
MAIN_MERGE_IN_THIS_GATE=false
```

Old branches/PRs are evidence, not current product candidates. Closing a superseded PR records its
disposition; it does not erase its commits.

## 9. Current implementation completeness

```text
MANAGER_REAL_UPGRADE_ACCEPTANCE=PASS
HOMEASSISTANT_MANDATORY_USB_R1_R4_SOURCE=CLOSED_PASS
HOMEASSISTANT_MANDATORY_USB_REAL_LIVE_APPLY=false
HOMEASSISTANT_NEXT_LIVE_BOUNDARY=R5_REAL_T1_READONLY_PREFLIGHT
BROKER_GENERIC_V2_PRODUCT_OTA_COMPLETE=false
FULL_T1_CORE_STACK_OTA_COMPLETE=false
```

Do not describe the complete Manager/Home Assistant/Broker user OTA path as production complete.

## 10. Source-alignment closure target

This gate is complete when:

- this authority is committed on a bounded branch from exact current main;
- Working Context contains the stable four-layer baseline rule;
- the handoff template references the current Working Context version;
- Current State and Current State Index record the source-alignment entry;
- fresh diff proves no production manifest/runtime source/live authority mutation;
- exact-head CI/review is checked;
- merge remains a separate decision.

```text
NEXT_AFTER_SOURCE_ALIGNMENT=
N3W_T1_CORE_STACK_OTA_BASELINE_AND_REPOSITORY_CONVERGENCE_SOURCE_ALIGNMENT_REVIEW_AND_MERGE_DECISION_20261106_01
```
