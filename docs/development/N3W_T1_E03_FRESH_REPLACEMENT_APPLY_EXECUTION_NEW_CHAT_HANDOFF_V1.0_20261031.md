# 温室环境监测系统（ESP32-C6） / N3-W
# T1 E03 fresh replacement apply execution
# 新会话交接文档 V1.0 — 2026-10-31

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前 E03 fresh replacement apply 阶段增量。长期规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> 本文禁止保存私有 T1 地址、密码、凭据或其他私有 locator。  
> fresh repository/runtime evidence 与本文冲突时，以 fresh 直接证据为准并立即 STOP。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION
CURRENT_STOP_POINT=APPLY_AUTHORIZED_NOT_STARTED
NEXT_ONE_GATE=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

当前会话已经完成 source repair、fresh preauthorization、fresh replacement claim 和 apply readonly preflight R2。实际产品 apply 尚未开始。  
用户于 2026-10-31 明确要求在新会话执行 `N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02`。  
新会话必须先做最小 fresh 只读确认；exact source / transaction / runtime 任一漂移时，当前 apply 授权不得跨漂移继续使用。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=3
STAGE_OVERRIDES=
1. PR740 source branch must stay frozen at exact head 4bec6c071af547615955602ac8d6232f0a54bc63 before apply closure.
2. Existing READY transaction means fresh preauthorization() must NOT be rerun as an apply preflight; use frozen transaction plan plus runtime rebind.
3. User granted apply execution for the new chat only while exact source/transaction/runtime preconditions remain unchanged.
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=T1 production-host E03 Manager successor replacement using exact maintenance transaction, fail-closed runtime binding, and bounded rollback
FINAL_ACCEPTANCE_TARGET=transaction COMMITTED with target Manager runtime accepted; Broker continuity preserved; Home Assistant healthy; reconciled first-registration ledger remains closed
DEFERRED_OR_OUT_OF_SCOPE=board access, firmware/NVS mutation, Broker replacement, architecture redesign, merge, unrelated pairing development
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e
MAIN_TREE=3064ab74ac96bbce44a0bf880ab53c7afc5bc134

CANDIDATE_REF=fix/n3w-t1-portable-image-identity-e03-successor-p0-20261030
CANDIDATE_PR=740
CANDIDATE_PR_STATE=OPEN_DRAFT
CANDIDATE_HEAD=4bec6c071af547615955602ac8d6232f0a54bc63
CANDIDATE_TREE=35e8fa6bd2db9559a34a4de27b3a82e2e7c0a649

SUCCESSOR_EXECUTOR_BLOB=0517454a1c8c973eb7456ef793c0e5493dc1841b
SUCCESSOR_MODULE_SET_SHA256=1e1f9ae691993b6aeafbc4edb7565f3f3fc1dee87b64cf48e5fa21781ecb95b8

TARGET_SOURCE_HEAD=f8876fd87165df731d792690a8288867c3eeef55
ARTIFACT_RUN_ID=40880705472
ARTIFACT_ID=12900601779
ARTIFACT_SHA256=c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183
TARGET_MANAGER_TAR_SHA256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5

DEPLOYED_MANAGER_IMAGE=local/greenhouse-manager:fresh-ff750b3801a2
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-f8876fd87165
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d

CURRENT_RELEASE_ID=4d6925334c4c6d0d741e3a8215954f4b136757f45e2295cbbe50e88996efa744
TARGET_RELEASE_ID=939e92d347a4cb925f760d58bafefdc2a41bfabc478f35ee086813d49da0f798
CURRENT_F4_AUTHORITY_SHA256=e466c257f9385bb906ebef4acac6463b21a0dd0eaf6d3b3fa1410a3a48a9ed28

PREAUTH_PLAN_SHA256=014a4516e022c29dbbf51f71988edceb922a3829a489b67e048539592749e2a5
TRANSACTION_ID_SHA256=bc1673d5de07a6cfe414df478e58cc2ead5c68b8ee81d5ce3083472f9d996d23
TRANSACTION_SHA256=7c9c65a5119022fef5e99687f4708536eb09c4450cff69e2000bc2ec39739802
TRANSACTION_STAGE=READY
TRANSACTION_GENERATION=4

OLD_BLOCKED_REPLACEMENT_SHA256=d1aa38135624092fbc275614e0ea1c0d05a268601b5b05598571cbdf2b071a93
OLD_BLOCKED_REPLACEMENT_STAGE=BLOCKED
OLD_BLOCKED_REPLACEMENT_GENERATION=5

RETIRED_TRANSACTION_SHA256=cf02987fad30b92b97e02a1ee62e529531425e5b97a8b035dac479d393ca176c
RETIREMENT_EVIDENCE_SHA256=ab2d96b73396448e3b18d5d1a69e5b6b41650e06a04a99645c528c683c939d03
```

---

## 4. Current Live Baseline

Latest fresh readonly evidence before handoff:

```text
APPLICATION_SERVICE_REALITY=BEFORE
APPLICATION_SERVICE_ACTIVE=true
MANAGER_CONTAINER_COUNT=1
HOMEASSISTANT_CONTAINER_COUNT=1

MANAGER_IMAGE=local/greenhouse-manager:fresh-ff750b3801a2
MANAGER_RESTART_COUNT=0

BROKER_CONTINUITY=PASS
BROKER_RESTART_COUNT=0
BROKER_STARTED_AT=2026-10-30T14:04:04.311501262Z
BROKER_REBASE_MODE=CURRENT_BOOT_REBASE

PREAUTH_LEDGER_MODE=RECONCILED_TERMINAL
PREAUTH_LEDGER_SHA256=924bb2fdf7a7ca69194217446b6415ba426f67ee30d359b46f820c90f9207bef
PREAUTH_LEDGER_ATTEMPT_COUNT=1
PREAUTH_LEDGER_REGISTRATION_COUNT=0
PREAUTH_LEDGER_UNRESOLVED_COUNT=0
PREAUTH_LEDGER_REGISTRATION_INVENTORY_SHA256=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945

DEPLOYMENT_REALITY=BEFORE
SERVICE_REALITY=BEFORE
GATE_REALITY=BEFORE
NO_OTHER_ACTIVE_TRANSACTION=true

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=NOT_APPLICABLE:BOARD_ACCESS_FORBIDDEN
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=NOT_APPLICABLE:BOARD_ACCESS_FORBIDDEN

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=true:maintenance-ledger claim only; product runtime unchanged
PRODUCT_MUTATION=false
```

新会话在实际 apply 前必须 fresh 复核：

```text
PR740_HEAD_REQUIRES_FRESH_READONLY_RECHECK=true
TRANSACTION_EXACT_SHA_REQUIRES_FRESH_READONLY_RECHECK=true
TRANSACTION_READY_GENERATION4_REQUIRES_FRESH_READONLY_RECHECK=true
BROKER_CONTINUITY_REQUIRES_FRESH_READONLY_RECHECK=true
DEPLOYMENT_SERVICE_GATE_REALITY_REQUIRES_FRESH_READONLY_RECHECK=true
NO_OTHER_ACTIVE_TRANSACTION_REQUIRES_FRESH_READONLY_RECHECK=true
```

---

## 5. Proven Current Facts

```text
FACT_1=Expired replacement transaction was terminally invalidated to BLOCKED generation 5 with no product apply.
FACT_2=Invalidation record is terminal COMMITTED; prior invalidation STOP was wrapper-only postcheck false STOP after the mutation had already committed.
FACT_3=Fresh post-reboot Broker baseline repair is CLOSED_PASS; existing transaction runtime continuity stayed strict.
FACT_4=Fresh preauth ledger repair accepts only exact LEGACY_ACTIVE or exact RECONCILED_TERMINAL states and binds the canonical ledger SHA into the transaction plan.
FACT_5=Exact source head 4bec6c071af547615955602ac8d6232f0a54bc63 passed focused E03 source tests: 297 passed.
FACT_6=Fresh readonly preauthorization R2 PASS: PREAUTH_PLAN_SHA256=014a4516e022c29dbbf51f71988edceb922a3829a489b67e048539592749e2a5.
FACT_7=Fresh replacement claim PASS: transaction READY generation 4; authorization consumed; replay disallowed; operation_seq=0; operations empty; observed_after empty.
FACT_8=Transaction-root forensic PASS: exactly one active transaction exists and it is the current READY/4 transaction; other_active_transaction_count=0.
FACT_9=Apply readonly preflight R2 PASS: runtime rebind true; deployment/service/gate BEFORE; Broker restart_count 0; transaction unchanged.
FACT_10=Actual product apply has NOT started.
FACT_11=User explicitly directed execution of N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02 in the new chat.
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE
ROOT_CAUSE=NONE_CURRENT
PROVEN_BY=apply readonly preflight R2 + transaction-root forensic + exact PR/source rebind
SOURCE_DEFECT_PROVEN=false:all discovered source gaps are repaired and CLOSED_PASS
RUNTIME_DEFECT_PROVEN=false
```

Historical false STOPs are closed and must not be reinterpreted as current blockers.

---

## 7. Closed / Forbidden Routes

```text
OLD_READY_TRANSACTION_REPLAY=CLOSED:old replacement is BLOCKED generation 5 after reboot-baseline invalidation
RERUN_FRESH_PREAUTH_AFTER_CLAIM=CLOSED:preauthorization intentionally rejects any active maintenance transaction; apply must use frozen transaction plan plus runtime rebind
PR740_SOURCE_ADVANCE_BEFORE_APPLY_CLOSURE=FORBIDDEN:would drift executor source authority bound into READY transaction
BLIND_APPLY_RETRY_AFTER_AMBIGUOUS_RESULT=FORBIDDEN:perform readonly recovery/status first
DIRECT_TRANSACTION_FILE_EDIT=FORBIDDEN
BROKER_RESTART_OR_REPLACEMENT=FORBIDDEN
BOARD_ACCESS=FORBIDDEN
MERGE=FORBIDDEN
```

---

## 8. Authorization Ledger

Claim authorization already consumed:

```text
AUTHORIZATION=N3W_T1_E03_FRESH_REPLACEMENT_AUTHORIZATION_CLAIM_20261030_02
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NOT_APPLICABLE
AUTHORIZATION_ID_SHA256=cac21f8d9b561f6f445fdf678d5bf05447983f00092ef5d6e59bd0fd2d0df49a
CLAIM_EXECUTION_SESSION_ID_SHA256=c07796a9b18356f1c5695d04a817b74bb4589eab41e371a5220e0f134d9143f2
```

Actual apply authorization:

```text
AUTHORIZATION=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02
GRANTED=true
GRANTED_BY_USER=true
GRANT_CONTEXT=2026-10-31 request to execute this exact gate in the new chat
CLAIMED=false
CONSUMED=false
RESULT=PENDING_EXECUTION
REPLAY_PERMITTED=false
APPLY_EXECUTION_SESSION_ID=n3w-t1-e03-successor-postreboot-apply-20261030-02
APPLY_EXECUTION_SESSION_ID_SHA256=67a44319e6c3aa8ef9192a42c0f7a7ed771c836bea8991ae0ef9435942364b54
AUTHORIZATION_INVALIDATED_BY_SOURCE_OR_TRANSACTION_OR_RUNTIME_DRIFT=true
```

---

## 9. Rollback Authority

```text
ROLLBACK_BASELINE=exact transaction plan bound by TRANSACTION_SHA256=7c9c65a5119022fef5e99687f4708536eb09c4450cff69e2000bc2ec39739802; deployment BEFORE; predecessor Manager image local/greenhouse-manager:fresh-ff750b3801a2; HA image local/n3w-homeassistant:2026.10.0-0c73235a; Broker frozen continuity baseline
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=current READY transaction plan; rollback policy EXACT_CANDIDATE_TO_EXACT_BEFORE_ONLY
RESTART_SCOPE_ALLOWED=n3wfc4-services-activation.service application services only; Broker restart forbidden
SECOND_ATTEMPT_ALLOWED=false
ROLLBACK_FAILURE_CLASS=BLOCKED_ROLLBACK_UNPROVEN
```

Apply source behavior:

- Failure before `VERIFYING` -> `BLOCKED_REVIEW_REQUIRED`; no automatic blind retry.
- Failure in `VERIFYING` -> automatic rollback attempt.
- Proven rollback -> `ROLLED_BACK`.
- Unproven rollback -> `BLOCKED_ROLLBACK_UNPROVEN`.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02
```

### Purpose

Execute the already prepared exact E03 Manager replacement transaction and prove that the target Manager runtime becomes the accepted production runtime while Broker continuity, Home Assistant health, registration ledger closure, and transaction integrity remain valid.

This gate may prove the replacement is `COMMITTED`, or may close as a proven rollback / blocked recovery state. It does not authorize merge, board access, firmware mutation, Broker replacement, or unrelated architecture changes.

### Inputs

```text
SOURCE_HEAD=4bec6c071af547615955602ac8d6232f0a54bc63
TRANSACTION_SHA256=7c9c65a5119022fef5e99687f4708536eb09c4450cff69e2000bc2ec39739802
TRANSACTION_STAGE=READY
TRANSACTION_GENERATION=4
PREAUTH_PLAN_SHA256=014a4516e022c29dbbf51f71988edceb922a3829a489b67e048539592749e2a5
APPLY_EXECUTION_SESSION_ID=n3w-t1-e03-successor-postreboot-apply-20261030-02
APPLY_EXECUTION_SESSION_ID_SHA256=67a44319e6c3aa8ef9192a42c0f7a7ed771c836bea8991ae0ef9435942364b54
```

### Operations

```text
1. Fresh read-only rebind PR #740 and exact source head/blob/module-set.
2. Fresh read-only load current transaction and require exact SHA, READY/4, authorization_consumed=true, replay_allowed=false, operation_seq=0, no observed_after.
3. Fresh read-only verify no other active transaction, runtime rebind, Broker continuity, ledger binding, deployment/service/gate reality.
4. If and only if all exact preconditions still pass, invoke successor.apply() once using the frozen transaction ID and apply execution session ID.
5. apply() records the apply session, installs activation gate, transitions READY->APPLYING, stops Manager/HA application services, publishes candidate deployment inputs, transitions to VERIFYING, starts services, runs readiness and strict acceptance.
6. On strict acceptance PASS, transaction transitions VERIFYING->COMMITTED.
7. On VERIFYING failure, allow source-defined automatic rollback only.
8. After any connection loss, wrapper error, STOP, BLOCKED, ROLLED_BACK, or ambiguous result, do not invoke apply() again; recover readonly first.
9. Archive exact postexecution evidence to PR #740 without advancing PR #740 source head.
```

### PASS / FAIL / STOP

```text
PASS_IF=transaction stage COMMITTED; reason_code SUCCESSOR_COMMITTED; target runtime accepted; registration_count=0; unresolved_count=0; expected registration inventory; Broker continuity proven; postexecution transaction exact evidence archived
FAIL_RECOVERED_IF=transaction stage ROLLED_BACK with exact predecessor restored; STOP and review; do not retry
FAIL_IF=BLOCKED, BLOCKED_REVIEW_REQUIRED, BLOCKED_ROLLBACK_UNPROVEN, unexpected runtime identity, acceptance failure, or rollback failure
STOP_BOUNDARY=any fresh precondition drift; any ambiguous post-call result; any source/transaction SHA mismatch; any need to modify Broker/board/source/merge scope

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
- One exact execution of N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02 after fresh preconditions PASS
- Maintenance transaction apply execution-session recording
- Activation gate installation required by the transaction
- READY -> APPLYING -> VERIFYING -> COMMITTED transaction transitions
- Stop/start of Manager and Home Assistant application services through the versioned apply path
- Exact candidate deployment-input publication
- Manager container recreation/start through existing systemd/docker-compose application service path
- Readiness and strict runtime acceptance
- Source-defined rollback if VERIFYING fails
- Read-only recovery/status after ambiguous interruption
- GitHub evidence/comments/docs-only archival that does not move PR #740 source head
```

### FORBIDDEN

```text
- Broker stop/restart/recreate/replacement
- docker load / docker tag / docker rmi
- Board access
- Firmware flash
- NVS mutation
- Direct maintenance transaction edit/delete
- Fresh preauthorization() after the current transaction already exists
- Blind second apply attempt after any ambiguous or failed execution
- Product/source repair unless a new proven defect is reviewed as a separate scope decision
- PR #740 source-head advance before apply closure
- Merge
```

```text
LIVE_RUNTIME_MUTATION=true:only inside the exact authorized apply gate
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=maintenance transaction journal, activation gate/drop-in, exact compose env candidate/rollback, application service lifecycle; no Broker/board writes
```

---

## 12. Execution Contract

```text
EXECUTOR=tools/n3w_t1_r10_e03_successor_recovery.py exact blob 0517454a1c8c973eb7456ef793c0e5493dc1841b
EXECUTION_METHOD=mac-terminal
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

New-chat execution rules specific to this gate:

- Use exact source material from `4bec6c071af547615955602ac8d6232f0a54bc63`.
- Do not derive execution authority from a later PR head.
- Run the smallest fresh readonly checks first.
- Do not call fresh `preauthorization()` as an apply preflight.
- Once `apply()` is invoked, treat the apply execution session as one-shot.
- If the wrapper loses connection or returns an ambiguous result after invoking `apply()`, do not rerun. Inspect transaction status and runtime readonly.
- Do not add a post-call assertion that can turn a successful committed mutation into a false STOP without preserving the authoritative transaction result.

---

## 13. Expected Closure

```text
=== N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02 CLOSURE ===

EXECUTION_ID=n3w-t1-e03-successor-postreboot-apply-20261030-02
AUTHORIZATION=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02
AUTHORIZATION_CLAIMED=<true|false>
AUTHORIZATION_CONSUMED=<true|false>

SOURCE_HEAD=4bec6c071af547615955602ac8d6232f0a54bc63
TRANSACTION_ID_SHA256=bc1673d5de07a6cfe414df478e58cc2ead5c68b8ee81d5ce3083472f9d996d23
TRANSACTION_SHA256_BEFORE=7c9c65a5119022fef5e99687f4708536eb09c4450cff69e2000bc2ec39739802
TRANSACTION_SHA256_AFTER=
TRANSACTION_STAGE_AFTER=
TRANSACTION_GENERATION_AFTER=
OPERATION_SEQ_AFTER=
RECOVERY_CLASS=
REASON_CODE=

TARGET_MANAGER_RUNTIME_ACCEPTED=
BROKER_CONTINUITY=
HOMEASSISTANT_HEALTH=
REGISTRATION_COUNT=
UNRESOLVED_COUNT=
REGISTRATION_INVENTORY_SHA256=
DEPLOYMENT_REALITY_AFTER=

LIVE_RUNTIME_MUTATION=true
BOARD_ACCESS=false

APPLY_EXECUTION_RESULT=<COMMITTED|ROLLED_BACK|BLOCKED|INCONCLUSIVE>
NEXT_ROUTE=<postexecution forensic/archive or rollback review>
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=postexecution readonly forensic + GitHub evidence alignment + later merge decision
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true:for any later merge or additional mutation

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false:current blocker count is zero
EXISTING_KF_GUARD_USED=maintenance transaction one-shot/crash-resume/rollback guards; Broker reboot-baseline invalidation guard
NEW_KF_REQUIRED=false:unless actual apply exposes a new proven product/source/runtime defect
```

---

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_NEW_CHAT_HANDOFF_V1.0_20261031.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

fresh rebind：
- repository main
- PR #740
- exact source head 4bec6c071af547615955602ac8d6232f0a54bc63
- PR #740 comments 6528044669, 6528223327, 6528323360, 6528369667, 6528378391
- current T1 maintenance transaction exact SHA 7c9c65a5119022fef5e99687f4708536eb09c4450cff69e2000bc2ec39739802

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

用户已明确要求在本新对话执行：
NEXT_ONE_GATE=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02

先做当前 gate 所需的最小 fresh 只读确认：
- PR #740 source head 仍必须为 4bec6c071af547615955602ac8d6232f0a54bc63；
- transaction 必须仍为 exact SHA 7c9c65a5119022fef5e99687f4708536eb09c4450cff69e2000bc2ec39739802、READY/4、operation_seq=0；
- no other active transaction；
- runtime rebind、Broker continuity、ledger binding、deployment/service/gate reality 必须仍符合冻结 plan。

注意：
- 不要再次调用 fresh preauthorization() 作为 apply preflight；
- 不要移动 PR #740 source HEAD；
- fresh evidence 发生漂移则 STOP，不能跨漂移使用本授权；
- apply() 一旦被调用，不得在结果不明时盲目重试；
- BOARD_ACCESS=false；
- MERGE=false。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

仅在 fresh preconditions 全部 PASS 后，执行一次 exact apply。
不要自动跨越 apply closure 后的下一阶段。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION
CURRENT_STOP_POINT=APPLY_AUTHORIZED_NOT_STARTED
CURRENT_BLOCKER=NONE
LIVE_SYSTEM_STATE=READY/4 transaction; deployment/service/gate BEFORE; Broker continuity PASS; ledger RECONCILED_TERMINAL; product apply not started
NEXT_ONE_GATE=N3W_T1_E03_FRESH_REPLACEMENT_APPLY_EXECUTION_20261030_02

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1

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
