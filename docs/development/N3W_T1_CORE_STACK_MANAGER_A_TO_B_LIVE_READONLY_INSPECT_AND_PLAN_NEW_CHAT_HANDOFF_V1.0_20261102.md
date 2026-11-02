# 温室环境监测系统（ESP32-C6）N3-W
# T1_Core_Stack Manager A -> B live read-only inspect / plan
# 新会话交接文档 V1.0 — 2026-11-02

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.4
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

## 0. 会话切换结论

```text
CURRENT_STAGE=POSTMERGE_MAIN_CONVERGED_BEFORE_LIVE_MANAGER_A_TO_B
CURRENT_STOP_POINT=BEFORE_FRESH_T1_CORE_UPDATER_INSPECT_AND_PLAN
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_20261102_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

Repository source, updater and authority have fully converged to main. The real T1 runtime has not been freshly read after that convergence. The next gate therefore rebinds live state with updater `inspect` and `plan` only; it does not apply the upgrade.

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.4
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false
STAGE_SPECIFIC_OVERRIDE_COUNT=0
STAGE_OVERRIDES=NONE
```

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=T1_Core_Stack Manager-only A-to-B live validation, then resume R3 real first-registration
FINAL_ACCEPTANCE_TARGET=Manager B live accepted with HA/Broker continuity, then real ESP32-C6 first-registration closes KF-131 live evidence
DEFERRED_OR_OUT_OF_SCOPE=Board work before Manager B acceptance; HA/Broker/host upgrades; unrelated architecture changes
```

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=092c9fca70df4212110b4ad07eb8fba9e8c9ef9e
TREE=MAIN_FINAL_POSTMERGE_TREE

CANDIDATE_REF=infra/n3w-t1/production/t1-core-stack-current.json
CANDIDATE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
CANDIDATE_TREE=REPOSITORY_MANAGER_B_AUTHORITY

ARTIFACT_ID=13129366972
ARTIFACT_SHA256=sha256:82baaf561632718b02008e6496eb8e7f462fde87bb98561b8645439e9ca367b6

DEPLOYED_SOURCE_HEAD=UNKNOWN_FRESH
DEPLOYED_SOURCE_TREE=UNKNOWN_FRESH

OTHER_REQUIRED_AUTHORITY=infra/n3w-t1/upgrades/manager-3539c8f871e2.json
EXPECTED_PREDECESSOR_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
TARGET_MANAGER_IMAGE_ID=sha256:2a1362b828a1f09b392713ba7fb40e91359e932690e525e4d03fe9873b9c1522
TARGET_MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0
ROLLBACK_COMPATIBLE=true
UPDATER_PYZ_SHA256=5d48460901a5d8115543c0ccfd254d440cbda1075458f2fcbfcfa082245506fc
```

## 4. Current Live Baseline

```text
MANAGER_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

LIVE_MANAGER_IMAGE=UNKNOWN_FRESH
LIVE_A_TO_B_APPLIED=UNKNOWN_FRESH
UPDATER_TRANSACTION_STATE=UNKNOWN_FRESH
TARGET_IMAGE_PRESTATE=UNKNOWN_FRESH

BOARD_A_POWER_STATE=NOT_APPLICABLE
BOARD_A_LOCATION_ROLE=NOT_APPLICABLE
BOARD_B_POWER_STATE=NOT_APPLICABLE
BOARD_B_LOCATION_ROLE=NOT_APPLICABLE

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

The last recorded live Manager A value is historical only and must not be promoted to fresh current state.

## 5. Proven Current Facts

```text
MAIN_CONVERGENCE_COMPLETE=true
MAIN=092c9fca70df4212110b4ad07eb8fba9e8c9ef9e
FINAL_MAIN_TREE_DRIFT_FROM_PR696_HEAD=false
REPOSITORY_MANAGER_B_AUTHORITY_READY=true
UPDATER_SOURCE_REVIEWED=true
UPDATER_PACKAGE_READY=true
FINAL_PR696_AUTHORITY_CI=41455321300:SUCCESS
FINAL_PR696_UPDATER_CI=41455321248:SUCCESS
FINAL_PR696_MANAGER_CI=41455321320:SUCCESS
FINAL_PR696_FAST_SOURCE_CI=41455320803:SUCCESS
KF131_SOURCE_REPAIR_CLOSED_PASS=true
KF131_LIVE_REVALIDATION_PENDING=true
```

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=LIVE_T1_RUNTIME_NOT_FRESHLY_REBOUND_AFTER_REPOSITORY_CONVERGENCE
ROOT_CAUSE=NOT_A_PRODUCT_DEFECT; fresh live evidence intentionally absent
PROVEN_BY=repository authority says successor ready/not live applied; no post-merge live T1 read has occurred
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

## 7. Closed / Forbidden Routes

```text
BOARD_FIRST_REGISTRATION_BEFORE_MANAGER_B_ACCEPTANCE=CLOSED:KF-131 repair is not yet live-proven
OLD_PR700_CONVERGENCE_ROUTE=CLOSED:fully merged to main
HISTORICAL_LIVE_MANAGER_A_AS_CURRENT_FACT=CLOSED:requires fresh live read
OUT_OF_BAND_MANAGER_ONLY_COMPOSE_RECREATE=CLOSED:violates production ownership contract
```

## 8. Authorization Ledger

```text
AUTHORIZATION=READONLY_T1_INSPECT_AND_PLAN
CLAIMED=false
CONSUMED=false
RESULT=NOT_EXECUTED
REPLAY_PERMITTED=true
SUPERSEDED_BY=NONE

PROPOSED_AUTHORIZATION=NONE_REQUIRED_FOR_READONLY_GATE
GRANTED=NOT_APPLICABLE
```

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_20261102_01
```

### Purpose

Freshly prove the real T1 runtime and whether it is safe to propose the Manager-only A->B apply. This gate proves predecessor/runtime/target-plan compatibility only. It does not prove that the upgrade has been applied or that KF-131 is live-closed.

### Inputs

```text
UPDATER_PACKAGE_ARTIFACT_ID=13129366972
UPDATER_PACKAGE_DIGEST=sha256:82baaf561632718b02008e6496eb8e7f462fde87bb98561b8645439e9ca367b6
TARGET_MANIFEST=infra/n3w-t1/upgrades/manager-3539c8f871e2.json
EXPECTED_PREDECESSOR=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
```

### Operations

```text
1. Freshly confirm the exact updater package / pyz and target manifest available for execution without altering product runtime.
2. Run: t1-core-updater inspect
3. Run: t1-core-updater plan --target-manifest <exact local target manifest> [--manager-tar <exact local Manager tar if already staged>]
4. Record public-safe JSON outputs only.
5. Confirm current Manager predecessor, Manager/HA/Broker runtime health, listener contract, target image prestate, rollback availability, and that planned mutations are Manager-only.
```

If the exact package is not already available on T1, do not silently stage it inside this read-only gate. Stop and define a bounded staging gate or a non-persistent execution method first.

### PASS / FAIL / STOP

```text
PASS_IF=inspect.status==PASS AND plan.status==PASS AND mutation==false AND current Manager equals exact predecessor AND target prestate is ABSENT or PRESENT_AND_EXACT AND HA/Broker continuity authority is healthy AND rollback_available==true
FAIL_IF=inspect or plan returns STOP, predecessor mismatch, target tag conflict, transaction blocker, service/ownership/listener mismatch, or any unplanned mutation requirement
STOP_BOUNDARY=BEFORE_ANY_APPLY_OR_ROLLBACK

AUTO_EXECUTE_NEXT_GATE=false
```

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- fresh read-only T1 access
- updater inspect
- updater plan
- read-only verification of exact local updater/manifest/tar when already present
- public-safe result capture
```

### FORBIDDEN

```text
- updater apply
- updater rollback
- Docker image load
- GH_MANAGER_IMAGE rewrite
- Manager/HA/Broker stop/start/restart/recreate
- service/unit mutation
- credential/DynSec mutation
- Board access
- firmware or NVS mutation
- R3 first-registration retry
```

## 12. Execution Contract

```text
EXECUTOR=operator on private T1 access path with assistant-designed exact commands
EXECUTION_METHOD=mac-terminal
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

No public GitHub document may contain private SSH locators, private network addresses, credentials, or raw device identity.

## 13. Expected Closure

```text
=== N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_20261102_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=READONLY_T1_INSPECT_AND_PLAN
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

INSPECT_STATUS=
PLAN_STATUS=
LIVE_MANAGER_IMAGE=
LIVE_MANAGER_IMAGE_ID=
HOMEASSISTANT_IMAGE=
HOMEASSISTANT_IMAGE_ID=
BROKER_IMAGE=
BROKER_IMAGE_ID=
TARGET_IMAGE_PRESTATE=
MANAGER_TAR_VERIFIED=
ROLLBACK_AVAILABLE=
UPDATER_TRANSACTION_STATE=
UNPLANNED_MUTATION_OBSERVED=false

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_APPLY_20261102_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF-131,KF-129,KF-133,KF-134
NEW_KF_REQUIRED=false
```

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_NEW_CHAT_HANDOFF_V1.0_20261102.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- infra/n3w-t1/production/t1-core-stack-current.json
- infra/n3w-t1/upgrades/manager-3539c8f871e2.json
- docs/development/N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_SOURCE_DESIGN_20261102.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh rebind main，然后只进入：
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_20261102_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不要执行 apply/rollback，不要重启产品服务，不要继续 Board 首配。
```

## 17. Final Frozen State

```text
CURRENT_STAGE=POSTMERGE_MAIN_CONVERGED_BEFORE_LIVE_MANAGER_A_TO_B
CURRENT_STOP_POINT=BEFORE_FRESH_T1_CORE_UPDATER_INSPECT_AND_PLAN
CURRENT_BLOCKER=LIVE_T1_RUNTIME_NOT_FRESHLY_REBOUND
LIVE_SYSTEM_STATE=UNKNOWN_FRESH
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_20261102_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.4
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.4
PROJECT_WORKING_CONTEXT_REFERENCED=PASS
LONG_TERM_RULE_DUPLICATION_MINIMIZED=PASS
STAGE_SPECIFIC_OVERRIDES_EXPLICIT=PASS
PRIVATE_CONTEXT_EXCLUDED_FROM_PUBLIC_HANDOFF=PASS
PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS
PROVEN_FACTS_SEPARATED_FROM_INFERENCE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS
AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS
NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
EXECUTION_CONTRACT_SELF_CONTAINED=PASS
CI_CONTINUATION_HARD_RULES_PRESENT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS
KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
TEAM_WORKSPACE_STATUS_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS
HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
