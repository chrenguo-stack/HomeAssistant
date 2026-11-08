# 温室环境监测系统（ESP32-C6）
# R7A repaired Manager A0R/A1R preexecution → A0R fresh live read-only eligibility
# 新会话交接文档 V1.0 — 2026-11-08

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
PROJECT_WORKING_CONTEXT_VERSION=2.4
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

## 0. 会话切换结论

```text
CURRENT_STAGE=R7A_REPAIRED_MANAGER_A0R_A1R_PREEXECUTION_CLOSED_PASS
CURRENT_STOP_POINT=BEFORE_FRESH_REAL_T1_READONLY_ELIGIBILITY
NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_A0R_FRESH_LIVE_READONLY_ELIGIBILITY_20261108_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

A0R/A1R source/preexecution and focused CI are closed. The next conversation starts with
fresh real-T1 read-only eligibility only; no Manager deployment is authorized by this handoff.

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=2.4
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false
STAGE_SPECIFIC_OVERRIDE_COUNT=0
STAGE_OVERRIDES=NONE
```

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=repair Manager first, then separately restore OTA wiring, then later resume mandatory-USB PREPARE
FINAL_ACCEPTANCE_TARGET=real T1 repaired Manager + stable A1R without KF-144 recurrence
DEFERRED_OR_OUT_OF_SCOPE=Boundary B PREPARE, USB erase/format, U2+, board mutation, merge
```

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
TREE=UNKNOWN_FRESH:rebind main before execution

CANDIDATE_REF=feat/n3w-ha-usb-r7a-prepare-pipeline-20261107
CANDIDATE_HEAD=813acb95401612585fc73455e05c81e3e6b86009
CANDIDATE_TREE=fdea2402ab30f1f6139268d2d450eb75a9f85226

ARTIFACT_ID=13616844356
ARTIFACT_SHA256=sha256:3c07406cd51258c8ef95f02e1e6cc80d09eb7235c218e7ead74a02a5521442fd
DEPLOYED_SOURCE_HEAD=UNKNOWN_FRESH
DEPLOYED_SOURCE_TREE=UNKNOWN_FRESH

OTHER_REQUIRED_AUTHORITY=repaired Manager source 7807271e4c48161f2fad96a7886fa4c24b038321; exact ARM64 artifact 13615963302; A0R package run 42480154921
CURRENT_PRODUCTION_AUTHORITY=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_STACK_RELEASE=repository compatibility authority remains 5b32 line; live predecessor last confirmed bf38
STACK_RELEASE_ROLE=compatibility authority is not a fresh live assertion
COMPONENT_UPGRADE_BASELINE=infra/n3w-t1/clean-reference/r7a-repaired-manager-predecessor-bf38-baseline-20261108.json
```

The derived component baseline is preexecution evidence only and must not substitute for a
fresh live read-only check.

## 4. Current Live Baseline

```text
MANAGER_STATE=UNKNOWN_FRESH:last confirmed recovered OTA-disabled Manager fresh-bf38e388497b
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH:last confirmed expected Broker running
HOMEASSISTANT_STATE=OPERATOR_EVIDENCE:web login PASS after reboot; exact runtime UNKNOWN_FRESH

BOARD_A_POWER_STATE=NOT_APPLICABLE
BOARD_A_LOCATION_ROLE=NOT_APPLICABLE
BOARD_B_POWER_STATE=NOT_APPLICABLE
BOARD_B_LOCATION_ROLE=NOT_APPLICABLE

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false

MANAGER_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
BROKER_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
HOMEASSISTANT_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
```

## 5. Proven Current Facts

```text
A0R_A1R_PREEXECUTION=CLOSED_PASS
REPAIRED_MANAGER_SOURCE_REPAIR=CLOSED_PASS
A0R_PACKAGE_AUTHORITY=run 42480154921 artifact 13616844356
A0R_TARGET=local/greenhouse-manager:fresh-7807271e4c48
A0R_PREDECESSOR=local/greenhouse-manager:fresh-bf38e388497b
A0R_A1R_AUTHORIZATION_HASH_CHAIN=EXECUTOR_ENFORCED
FOCUSED_CI_RUN=42482476119
FOCUSED_CI_SOURCE=SUCCESS
FOCUSED_CI_EXACT_MANAGER_SLICE=SUCCESS
FOCUSED_CI_PRE_U1_SIMULATION=SUCCESS
LIVE_T1_MUTATION_IN_PREEXECUTION=false
```

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=KF-144 real-T1 live revalidation not yet completed
ROOT_CAUSE=simplified compatibility Settings copy disabled runtime while retaining OTA flag before base Settings.validate
PROVEN_BY=incident logs + source path + exact source repair
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=true
```

The source defect is repaired; the remaining blocker is live deployment/revalidation, not
unresolved root-cause analysis.

## 7. Closed / Forbidden Routes

```text
OLD_A0_EXECUTION_PACKAGE=CLOSED:historical one-shot authority
OLD_A1_EXECUTION_PACKAGES=CLOSED:consumed/retired and non-replay
OLD_BOUNDARY_B_AUTHORIZATION=CLOSED:invalidated/non-replay
DIRECT_A1R_BEFORE_A0R=CLOSED:A1R requires exact A0R transaction authorization hash
DIRECT_USB_PREPARE=CLOSED:KF-144 live repair chain must close first
```

## 8. Authorization Ledger

```text
AUTHORIZATION=historical A0/A1 authorizations
CLAIMED=true
CONSUMED=true
RESULT=historical evidence only
REPLAY_PERMITTED=false
SUPERSEDED_BY=A0R/A1R successor chain

PROPOSED_AUTHORIZATION=N3W_T1_CORE_UPDATER_R7A_REPAIRED_MANAGER_A0R_LIVE_APPLY_20261108_01
GRANTED=false

PROPOSED_A1R_AUTHORIZATION=N3W_T1_R7A_REPAIRED_MANAGER_A1R_LIVE_REACTIVATION_20261108_01
A1R_GRANTED=false
```

The next read-only gate does not grant either mutation authorization.

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

For the later A0R mutation gate, a fresh prechange snapshot is mandatory and Generic V2
internal bounded rollback remains the only automatic Manager rollback path.

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_A0R_FRESH_LIVE_READONLY_ELIGIBILITY_20261108_01
```

### Purpose

Freshly prove that the rebooted T1 is still eligible for the frozen A0R Manager-only upgrade.
This gate cannot prove the repaired Manager works live because it must not deploy it.

### Inputs

```text
CANDIDATE_HEAD=813acb95401612585fc73455e05c81e3e6b86009
EXPECTED_MANAGER=local/greenhouse-manager:fresh-bf38e388497b
EXPECTED_MANAGER_RUNTIME_ID_LAST_CONFIRMED=sha256:e88a22b29b93b0db0d3b4f592cb0fd773169d1dc0f043219f14d5247ed859dff
EXPECTED_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
EXPECTED_HOMEASSISTANT_RUNTIME_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
EXPECTED_BROKER=local/n3w-mosquitto:2.1.2-3184566d
EXPECTED_BROKER_RUNTIME_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
```

### Operations

```text
1. fresh rebind repository main / PR #800 / candidate head.
2. real T1 read-only: host architecture/system state and services-owner/broker-owner state.
3. read-only exact Manager/HA/Broker image + runtime IDs + restart state.
4. confirm Manager UID/GID 999:999, no Docker socket, no OTA env, no /run/n3w/t1-ota mount.
5. confirm A1 host service/drop-in/activation env/runtime root/socket/approved manifest absent.
6. read-only Generic V2/legacy/HA-USB transaction state; require terminal/recovery clear and no HA-USB successor state.
7. confirm USB-like disk count = 0 and PREPARE state absent.
8. compare fresh facts against the frozen A0R predecessor requirements.
9. STOP before package staging, plan/apply or service mutation.
```

### PASS / FAIL / STOP

```text
PASS_IF=fresh T1 exactly satisfies A0R predecessor/recovery/OTA-disabled/zero-USB contract
FAIL_IF=any image/runtime/recovery/residue/USB drift exists
STOP_BOUNDARY=BEFORE_ANY_REMOTE_FILE_WRITE_OR_MANAGER_APPLY

AUTO_EXECUTE_NEXT_GATE=false
```

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
```

### ALLOWED

```text
- repository/GitHub read-only rebind
- real-T1 SSH read-only inspection
- docker/systemd/lsblk/stat/cat read-only evidence
- local evidence capture if needed
```

### FORBIDDEN

```text
- remote staging or file write
- updater plan/apply/rollback that can alter state
- Docker image/container mutation
- service restart/enable/start/stop
- A1R activation
- PREPARE or CONFIRM_USB_ERASE
- USB insert/write/format/mount
- board access
- merge
```

## 12. Execution Contract

```text
EXECUTOR=prefer bounded read-only inspection; do not reuse live A0R executor because it stages files
EXECUTION_METHOD=chat-tool/read-only SSH evidence
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

## 13. Expected Closure

```text
=== N3W_T1_R7A_REPAIRED_MANAGER_A0R_FRESH_LIVE_READONLY_ELIGIBILITY_20261108_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=NOT_APPLICABLE:READONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

MANAGER_EXACT=
HOMEASSISTANT_EXACT=
BROKER_EXACT=
OTA_WIRING_ABSENT=
UPDATER_RECOVERY_CLEAR=
HA_USB_TRANSACTION_ABSENT=
PREPARE_STATE_ABSENT=
USB_LIKE_DISK_COUNT=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

A0R_FRESH_LIVE_READONLY_ELIGIBILITY=
NEXT_ROUTE=SEPARATE_A0R_LIVE_APPLY_AUTHORIZATION_OR_STOP
STOP=true

=== END ===
```

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_R7A_REPAIRED_MANAGER_A0R_LIVE_APPLY_AUTHORIZATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF-144
NEW_KF_REQUIRED=false
```

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_T1_R7A_REPAIRED_MANAGER_A0R_A1R_PREEXECUTION_TO_A0R_FRESH_LIVE_READONLY_ELIGIBILITY_NEW_CHAT_HANDOFF_V1.0_20261108.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh rebind repository main、PR #800 和 candidate head，然后只进入：

NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_A0R_FRESH_LIVE_READONLY_ELIGIBILITY_20261108_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不要重放 consumed authorization，不要复活旧 A0/A1，不要写入 T1，不要自动进入 A0R apply。
```

## 17. Final Frozen State

```text
CURRENT_STAGE=R7A_REPAIRED_MANAGER_A0R_A1R_PREEXECUTION_CLOSED_PASS
CURRENT_STOP_POINT=BEFORE_FRESH_REAL_T1_READONLY_ELIGIBILITY
CURRENT_BLOCKER=KF-144 live revalidation pending
LIVE_SYSTEM_STATE=UNKNOWN_FRESH; operator HA web-login PASS after reboot
NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_A0R_FRESH_LIVE_READONLY_ELIGIBILITY_20261108_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=2.4
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=2.4

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
