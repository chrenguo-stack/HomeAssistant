# 温室环境监测系统（ESP32-C6）
# N3-W T1 R7A source repair closed → repaired Manager exact artifact / fresh A1 reactivation preexecution
# 新会话交接文档 V1.0 — 2026-11-08

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_HANDOFF_STANDARD_DOES_NOT_AUTHORIZE_OLD_TEMPLATE=true

FORMAL_TEMPLATE_PATH=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
FORMAL_TEMPLATE_BLOB=613ea57c74521610f25c576f25b7ce738d5a045f
PROJECT_WORKING_CONTEXT_VERSION=2.3
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md

NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。historical handoff standard authority `4300890dff0ce63d5a547df21426e287d084d9ee` 仅用于 process/standard，不回退使用其中旧 template。fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并 STOP。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=R7A_SIMPLIFIED_RUNTIME_OTA_COMPATIBILITY_SOURCE_REPAIR_CLOSED
CURRENT_STOP_POINT=SOURCE_CLOSED;T1_RECOVERED_OTA_DISABLED;NO_FRESH_A1_REACTIVATION
NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_EXACT_ARTIFACT_AND_FRESH_A1_REACTIVATION_PREEXECUTION_20261108_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=2.3
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false
STAGE_SPECIFIC_OVERRIDE_COUNT=0
STAGE_OVERRIDES=NONE
```

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=Home Assistant mandatory-USB OTA; Manager non-privileged control plane; privileged host daemon owns USB/update execution
FINAL_ACCEPTANCE_TARGET=deploy exact repaired Manager under a fresh bounded chain; re-establish A1 safely; then separately re-enter PREPARE-first Boundary B
DEFERRED_OR_OUT_OF_SCOPE=CONFIRM_USB_ERASE;U2+;board work;merge;resident health supervisor
```

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=800
CANDIDATE_REF=feat/n3w-ha-usb-r7a-prepare-pipeline-20261107

SOURCE_REPAIR_HEAD=7807271e4c48161f2fad96a7886fa4c24b038321
SOURCE_REPAIR_TREE=3d2893914d62645011a9a4badc7f939d10f9029e

EXACT_ARM64_RUN_ID=42452239964
EXACT_ARM64_SUCCESS_ATTEMPT=2
ARTIFACT_ID=13615963302
ARTIFACT_SHA256=72b05593b91c75912e05ccd3b00bc72af5bd7ec03e39c283d0ce7acfb513fbe7
MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67

CURRENT_LIVE_MANAGER_IMAGE=local/greenhouse-manager:fresh-bf38e388497b
LIVE_RUNTIME_ROUTE=RECOVERED_OTA_DISABLED

OTHER_REQUIRED_AUTHORITY=
- docs/development/N3W_T1_R7A_SIMPLIFIED_RUNTIME_OTA_COMPATIBILITY_SOURCE_REPAIR_CI_CLOSURE_20261108.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md (KF-144)
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
```

## 4. Current Live Baseline

No fresh live access occurred in the source-closure gate. Last direct production recovery evidence remains:

```text
MANAGER_STATE=RUNNING;OTA_ENV_ABSENT;OTA_MOUNT_ABSENT
HOMEASSISTANT_STATE=RUNNING;HTTP_401
BROKER_STATE=RUNNING;CONTINUITY_PRESERVED
SERVICES_OWNER=active
HA_OTA_SERVICE=inactive/not-found
HA_USB_TRANSACTION=ABSENT
HA_PREPARE_STATE=ABSENT

T1_RUNTIME_MUTATION=false
BOARD_ACCESS=false
```

Fresh read-only recheck is required before any later live mutation.

## 5. Proven Current Facts

```text
FACT_1=KF-144 root cause is internal simplified-runtime Settings compatibility rewrite, not a missing live GH_N3W_RUNTIME_ENABLED flag
FACT_2=repair preserves OTA capability through already-built ota_manager while clearing only base-service compatibility config
FACT_3=A1 postcheck now requires a 15s same-container stability hold
FACT_4=exact ARM64 unchanged rerun passed the full upload/redownload SHA binding path
FACT_5=attempt-1 HA tar SHA mismatch is classified transient CI artifact-roundtrip failure and did not justify weakening exact binding
FACT_6=source repair is CLOSED_PASS; live revalidation remains pending
```

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
ROOT_CAUSE=SOURCE_REPAIRED
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=true
LIVE_REVALIDATION_PENDING=true
```

## 7. Closed / Forbidden Routes

```text
OLD_A1_SUCCESSOR_AUTHORIZATION=CLOSED:CONSUMED_NONREPLAY
OLD_BOUNDARY_B_PREPARE_AUTHORIZATION=CLOSED:INVALIDATED_BY_RUNTIME_RECOVERY
DIRECT_BOUNDARY_B_PREPARE_NOW=CLOSED:A1_OTA_WIRING_NOT_ACTIVE
CONFIRM_USB_ERASE=CLOSED:NOT_AUTHORIZED
U2_PLUS=CLOSED:NOT_AUTHORIZED
MERGE=CLOSED:NOT_AUTHORIZED
```

## 8. Authorization Ledger

```text
PROPOSED_AUTHORIZATION=NOT_APPLICABLE:NEXT_GATE_IS_PREEXECUTION_ONLY
GRANTED=false
REPLAY_OF_OLD_AUTHORIZATION=false
```

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:PREEXECUTION_SOURCE_AND_READONLY_PREPARATION_ONLY
LIVE_MUTATION_ALLOWED=false
```

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_EXACT_ARTIFACT_AND_FRESH_A1_REACTIVATION_PREEXECUTION_20261108_01
```

### Purpose

- bind the exact successful repaired Manager artifact to the next deployment package/authority;
- independently review the repaired Manager package and fresh A1 reactivation prerequisites;
- establish a fresh preexecution state after the prior incident/recovery;
- stop before any real T1 mutation.

### Inputs

```text
SOURCE_REPAIR_HEAD=7807271e4c48161f2fad96a7886fa4c24b038321
ARTIFACT_ID=13615963302
ARTIFACT_DIGEST_SHA256=72b05593b91c75912e05ccd3b00bc72af5bd7ec03e39c283d0ce7acfb513fbe7
MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67
LIVE_BASELINE=RECOVERED_OTA_DISABLED
```

### Operations

```text
1. fresh rebind repository main, PR #800, candidate branch and closure authority.
2. verify artifact/run binding and exact Manager tar identity.
3. construct/review only the bounded repaired-Manager successor package/preexecution authority needed for the current live predecessor.
4. fresh read-only live eligibility may be designed or performed only if separately permitted by the next gate's scope; no mutation.
5. define new one-shot live authorization inputs only after preexecution closes.
6. STOP before Manager deploy, service restart, A1 activation, PREPARE or USB work.
```

### PASS / FAIL / STOP

```text
PASS_IF=exact artifact binding and repaired-Manager/A1 preexecution are internally consistent with no unresolved source blocker
FAIL_IF=artifact/source drift, live-predecessor ambiguity, updater incompatibility, or new false-PASS path is found
STOP_BOUNDARY=BEFORE_ANY_REAL_T1_MUTATION
AUTO_EXECUTE_NEXT_GATE=false
```

## 11. Hard Allowed / Forbidden Scope

```text
ALLOWED=GitHub read/review; source-only package/preexecution work; focused tests; bounded read-only evidence only when explicitly in gate
FORBIDDEN=Manager deployment;service restart;A1 activation;PREPARE;USB insertion/write;CONFIRM_USB_ERASE;U2+;board access;merge
```

## 12. Expected next closure

```text
SOURCE_REPAIR_HEAD=7807271e4c48161f2fad96a7886fa4c24b038321
REPAIRED_MANAGER_ARTIFACT_ID=13615963302
REPAIRED_MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67
PREEXECUTION_RESULT=
NEW_LIVE_AUTHORIZATION_GRANTED=false
LIVE_T1_MUTATION=false
STOP=true
```
