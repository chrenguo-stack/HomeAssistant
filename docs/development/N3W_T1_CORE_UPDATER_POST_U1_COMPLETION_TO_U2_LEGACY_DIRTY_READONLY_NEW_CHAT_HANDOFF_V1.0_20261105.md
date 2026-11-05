# 温室环境监测系统（ESP32-C6）
# T1 Core Updater post-U1 completion -> U2 legacy/dirty read-only classification
# 新会话交接文档 V1.0 — 2026-11-05

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_HANDOFF_STANDARD_DOES_NOT_AUTHORIZE_OLD_TEMPLATE=true
PROJECT_WORKING_CONTEXT_VERSION=1.4
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。长期工作规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> 本文严格使用当前 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.3。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。  
> 公开 handoff 不包含 SSH、私网地址、密码、凭据、原始设备 locator 或其他私有值。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=T1_CORE_UPDATER_POST_U1_PRODUCT_COMPLETION
CURRENT_STOP_POINT=COMPLETION_AUDIT_ARCHIVED_AND_U2_READONLY_ROUTE_FROZEN
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本会话已完成 U1 R4 / KF-141 / Manager B canonical authority 收口，并完成 post-U1 product completion audit。新会话不要进入 N3-L，也不要重做 generic updater；先完成 U2 legacy/dirty T1_A 的 fresh 只读 classification。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.4
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=1
STAGE_OVERRIDES=U2_GATE_IS_STRICTLY_READONLY_ON_T1_A; any cleanup/apply/rollback/restart/transaction mutation requires a separate gate
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=T1_CORE_UPDATER_GENERIC_V2_COMPLETE -> MANAGER_PRODUCT_PATH_CLOSED_PASS -> U2_LEGACY_DIRTY_READONLY_CLASSIFICATION -> HOMEASSISTANT_PRODUCT_VALIDATION -> BROKER_PRODUCT_VALIDATION -> FINAL_UPDATER_PRODUCT_CLOSURE
FINAL_ACCEPTANCE_TARGET=T1_Core_Updater has product-grade evidence for Manager, Home Assistant and Broker component upgrades, plus bounded legacy/dirty classification/recovery semantics
DEFERRED_OR_OUT_OF_SCOPE=N3-L development; generic updater rewrite; coordinated cross-component upgrade; full air-gapped host installer O1
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
TREE=b82bc89b5c222dfd33c2f91222155a16d4bd3fc5

CANDIDATE_REF=docs/n3w-t1-core-updater-post-u1-completion-audit-handoff-20261105
CANDIDATE_HEAD=e777a1ab08693665cedf8290f6c0f172e8da3d35
CANDIDATE_TREE=53b178f4fca929d1c8d2e3740559541619a6a7ac

ARTIFACT_ID=13336359358
ARTIFACT_SHA256=sha256:e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46

DEPLOYED_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
DEPLOYED_SOURCE_TREE=6497ce2b53be973eaee709092296545765d480a5

OTHER_REQUIRED_AUTHORITY=docs/development/N3W_T1_CORE_UPDATER_POST_U1_PRODUCT_COMPLETION_READONLY_AUDIT_20261105.md@d62eda6e69a854809cd8e01f7cc675ddb914fdc4; docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md@31b0c7061fab63c6fee88eb9a34b3b07be153105
```

`CANDIDATE_HEAD` is the exact pre-handoff documentation state. The handoff file itself is one later documentation commit on the same candidate branch; new chat must fresh rebind the branch before any repository mutation.

---

## 4. Current Live Baseline

本 completion audit 没有访问任何 T1，因此当前 live 状态必须 fresh recheck，不得把最后一次 R4 证据冒充本 gate 的 fresh 状态。

```text
MANAGER_STATE=UNKNOWN_FRESH:last-confirmed Manager B TARGET_BOUND_RUNNING/HEALTHY
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH:last-confirmed accepted Broker unchanged
HOMEASSISTANT_STATE=UNKNOWN_FRESH:last-confirmed accepted Home Assistant unchanged

T1_A_RUNTIME_STATE=UNKNOWN_FRESH
T1_A_TRANSACTION_STATE=UNKNOWN_FRESH
T1_A_REQUIRES_FRESH_READONLY_RECHECK=true

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=UNKNOWN_FRESH

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

---

## 5. Proven Current Facts

```text
FACT_1=T1_Core_Updater architecture and generic V2 core source are complete
FACT_2=Generic component model covers manager, homeassistant and broker
FACT_3=Manager product-grade upgrade path is CLOSED_PASS
FACT_4=KF-141 is CLOSED_PASS and Manager B is canonical repository authority
FACT_5=Home Assistant generic source/test support exists but no HA target manifest/exact product package/live acceptance exists
FACT_6=Broker generic source/test support exists but no Broker target manifest/exact product package/live acceptance exists
FACT_7=U2 no-replay/reconciliation semantics have strong real overlap from KF-141/R3/R4 but preserved T1_A has not received formal fresh classification
FACT_8=No current evidence requires a generic updater rewrite
```

```text
INFERENCE_U2_EXPECTED_SCOPE=A fresh read-only T1_A classification is likely sufficient to decide whether U2 can close without cleanup; this is not yet proven until T1_A is inspected
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE
ROOT_CAUSE=NOT_APPLICABLE
PROVEN_BY=POST_U1_COMPLETION_AUDIT
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

Remaining U2/HA/Broker work is planned product validation, not a blocker or proven defect.

---

## 7. Closed / Forbidden Routes

```text
GENERIC_UPDATER_REWRITE=CLOSED:no current evidence requires reopening architecture/core
MANAGER_U1_REOPEN=CLOSED:Manager product path and canonical promotion are CLOSED_PASS
R4_AUTHORIZATION_REPLAY=CLOSED:consumed authorization is permanently replay-forbidden
U2_AUTOMATIC_CLEANUP=CLOSED:read-only classification first; any mutation requires separate gate
U2_APPLY_OR_ROLLBACK=CLOSED:not part of read-only classification
N3L_ENTRY_BEFORE_UPDATER_CLOSURE=CLOSED:user selected updater completion route first
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_REAPPLY_U1_R4_20261105_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

```text
PROPOSED_AUTHORIZATION=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01
GRANTED=true
AUTHORIZATION_SCOPE=READONLY_T1_A_CLASSIFICATION_ONLY
```

User explicitly selected this next gate and instructed the next conversation to complete U2 read-only classification before HA/Broker product validation.

---

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01
```

### Purpose

- Freshly classify the preserved legacy/dirty T1_A with current V2 updater semantics.
- Determine whether historical updater state is terminal/harmless, directly compatible, needs a separately authorized bounded cleanup, or remains unresolved.
- Prove no consumed historical authorization is treated as reusable.
- This gate cannot prove Home Assistant or Broker upgrade product acceptance and cannot perform cleanup.

### Inputs

```text
INPUT_1=main@5cabdcb50656851f9912685c2f7044cdba3eb774
INPUT_2=docs/development/N3W_T1_CORE_UPDATER_POST_U1_PRODUCT_COMPLETION_READONLY_AUDIT_20261105.md
INPUT_3=docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_DEVELOPMENT_PLAN_20261101.md U2 contract
INPUT_4=exact updater artifact 13336359358 / pyz SHA256 65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46, subject to fresh availability/source-drift confirmation
INPUT_5=private T1_A locator supplied/retained outside public GitHub
```

### Operations

```text
1. Fresh rebind main, candidate/handoff branch and updater source; confirm no updater-source drift invalidates the exact pyz.
2. Freshly identify T1_A only through private/user context; do not publish its locator.
3. Perform minimal read-only connectivity/preflight.
4. Run/read only status, runtime-state and the minimum inspect information needed to classify current T1_A.
5. Read any legacy manager transaction only through updater-supported read-only output; do not edit/delete transaction files.
6. Check whether any historical authorization is terminal/consumed and verify replay is not permitted.
7. Classify LEGACY_STATE_DISPOSITION as NO_ACTION_REQUIRED, DIRECTLY_COMPATIBLE, BOUNDED_CLEANUP_REQUIRED, or UNRESOLVED.
8. Archive closure evidence to GitHub. Stop before any cleanup/mutation.
```

### PASS / FAIL / STOP

```text
PASS_IF=Fresh T1_A runtime/transaction state is classified without mutation and replay risk is explicitly resolved
FAIL_IF=Read-only evidence proves current updater misclassifies legacy state or would permit unsafe replay
STOP_BOUNDARY=Before any apply, rollback, service restart, transaction edit/delete, cleanup, package installation, or other T1 mutation

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- Fresh GitHub read-only rebind
- Read completion audit / current state / known failures
- Read-only T1_A connectivity check
- Read-only updater status/runtime-state/inspect
- Read-only filesystem/process/service/container observations needed for classification
- GitHub documentation archival after classification
```

### FORBIDDEN

```text
- updater apply
- updater rollback
- service restart/stop/start
- transaction edit/delete/rewrite
- cleanup or migration
- image load/pull/remove
- Compose/environment rewrite
- credential mutation
- board access or flash/NVS mutation
- merge without separate authorization
- automatic transition to HA/Broker validation
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
BOUNDED_WRITE_SCOPE=NONE_ON_T1_A
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_WITH_USER_MAC_TERMINAL_FOR_PRIVATE_T1_A_READONLY_COMMANDS
EXECUTION_METHOD=mac-terminal
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

New chat must first fresh rebind before supplying exact commands. Commands must not contain comments. If a read-only observer/executor defect is found, a bounded source/test repair may proceed in the same gate only if it does not widen into T1 mutation.

---

## 13. Expected Closure

```text
=== N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01
AUTHORIZATION_CLAIMED=NOT_APPLICABLE:READONLY
AUTHORIZATION_CONSUMED=NOT_APPLICABLE:READONLY

LEGACY_TRANSACTION_PRESENT=
LEGACY_TRANSACTION_TERMINAL=
RECOVERY_REQUIRED=
CURRENT_RUNTIME_CLASS=
CURRENT_HEALTH_STATE=
CONSUMED_AUTHORIZATION_REPLAY_RISK=
LEGACY_STATE_DISPOSITION=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

U2_READONLY_CLASSIFICATION_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_PRODUCT_GRADE_UPGRADE_VALIDATION_PREPARATION_20261105_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

After Home Assistant product validation closes, Broker product validation is next. Neither is auto-entered from U2.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF-141
NEW_KF_REQUIRED=false
```

If U2 proves a new distinct updater defect, allocate/update a KF only after root cause is established.

---

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_T1_CORE_UPDATER_POST_U1_COMPLETION_TO_U2_LEGACY_DIRTY_READONLY_NEW_CHAT_HANDOFF_V1.0_20261105.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_CORE_UPDATER_POST_U1_PRODUCT_COMPLETION_READONLY_AUDIT_20261105.md
- docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_DEVELOPMENT_PLAN_20261101.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W / T1 Core Updater。

先 fresh rebind repository main 和 handoff candidate branch，确认 completion audit / current state 没有新漂移，然后只进入：

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

本 gate 只读 T1_A。不要 apply、rollback、重启服务、编辑/删除 transaction、cleanup、加载镜像或修改凭据。
先完成 U2 classification 并 STOP；U2 通过后再单独进入 Home Assistant 产品级升级验收，随后 Broker 产品级升级验收。
不要重放任何 consumed authorization，不要重新进入已经 CLOSED_PASS 的 Manager U1/KF-141 路线。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=T1_CORE_UPDATER_POST_U1_PRODUCT_COMPLETION
CURRENT_STOP_POINT=COMPLETION_AUDIT_CLOSED_PASS_HANDOFF_TO_U2_READONLY
CURRENT_BLOCKER=NONE
LIVE_SYSTEM_STATE=UNKNOWN_FRESH:last-confirmed production Manager B accepted/healthy; T1_A requires fresh read-only check
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.4
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

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
