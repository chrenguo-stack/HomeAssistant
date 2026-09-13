# 温室环境监测系统（ESP32-C6）
# N3-W / KF-089 Manager Relay DynSec ACL Repair
# 新会话交接文档 V1.2 — 2026-09-13

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
NEXT_ONE_GATE_ONLY=true

STAGE_SPECIFIC_EXECUTION_OVERRIDE=true
DSL_EXECUTION_MODEL=false
PREWRITTEN_EXECUTOR_REQUIRED=true
DSL_COMPILATION_AUTHORIZED=false
REPOSITORY_VERSIONED_EXECUTOR=true
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
RAW_EVIDENCE_FIRST=true
```

> 本文符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 的 section/order/completeness 要求。  
> 该标准的通用 DSL 默认值在本阶段被更严格的 stage-specific contract 覆盖：ID24 live DynSec mutation 已经有经过审计和 exact-head CI 接受的 repository-versioned executor，因此下一会话不得让 Codex 临时编译/改写 mutation sequence。  
> 如本文与 fresh exact repository/runtime/live evidence 冲突，以 fresh exact evidence 为准并先 STOP / rebind。

---

## 0. 会话切换结论

本轮已经完成 ID24 repair package 的 Host/GitHub 收口、PR/CI acceptance、中央状态文档对齐以及最终只读一致性审计。切换新会话的唯一原因是保持后续 live authorization / mutation 阶段的上下文清晰，不是重新打开已关闭路线。

```text
CURRENT_STAGE=KF089_ID24_PRELIVE_AUTHORIZATION
CURRENT_STOP_POINT=HOST_PACKAGE_ACCEPTED_CENTRAL_AUTHORITY_ALIGNED_FINAL_READONLY_AUDIT_PASS

PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE=PASS
NEXT_ONE_GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_EXECUTE_NEXT_GATE=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘 ID21/ID22/ID23，也不是重新做 RF localization；应先 fresh rebind GitHub authority，然后只进入 authorization discussion gate。

---

## 1. 执行模式

### 1.1 高阶模型职责

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
```

高阶模型负责：产品路线、exact authority、gate/scope、authorization、rollback、PASS/FAIL/STOP 分类，以及任何后续 source/executor repair。若未来 live execution 暴露新的 executor/source defect，必须返回高阶模型修改 GitHub code，形成新 commit，重新 exact-head acceptance 后才可再次执行。

### 1.2 Codex 低阶执行职责

```text
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
REPOSITORY_VERSIONED_EXECUTOR=true
```

Codex 只允许机械执行已经接受的 exact repository-versioned executor，并返回 closure。不得：

- 自行编写或修改 ID24 executor/mutator；
- 扩大 ACL scope；
- 自动 repair/retry；
- 重放 consumed authorization；
- 跨入下一 gate；
- 访问 Board/USB/Serial/Flash/NVS/RF；
- 将 private raw evidence 发布到 GitHub。

### 1.3 Stage-specific execution semantics

本阶段显式覆盖 handoff standard 的通用 DSL 默认值：

```text
GENERIC_STANDARD_DSL_DEFAULT=true
STAGE_SPECIFIC_OVERRIDE=true

DSL_EXECUTION_MODEL=false
PREWRITTEN_EXECUTOR_REQUIRED=true
DSL_COMPILATION_AUTHORIZED=false
DSL_TO_COMMAND_COMPILATION=false

REPOSITORY_VERSIONED_EXECUTOR=true
```

覆盖原因：ID24 是 transaction / rollback-sensitive live DynSec mutation，且 exact executor 已经通过审计、focused tests 与 dedicated CI。重新由 Codex 从 DSL 临时编译 mutation sequence 会降低可验证性。

### 1.4 标准交互循环

```text
高阶模型：fresh rebind → 展示 exact authorization scope
        ↓
用户：明确批准或不批准 exact one-shot T1 mutation authorization
        ↓
若批准：高阶模型再次确认 exact accepted head 未漂移
        ↓
Codex：仅执行 repository-versioned ID24 executor → structured closure
        ↓
高阶模型：判定 PASS / STOP / rollback status / next route
```

当前 handoff 只允许进入第一步的 authorization discussion；不得自动进入 live execution。

---

## 2. Product North Star

当前产品路线：

```text
DIRECT_PREFERRED
-> DIRECT_UNAVAILABLE
-> AUTONOMOUS_RELAY_DISCOVERY
-> AUTHENTICATED_RELAY_ACQUISITION
-> BOARD_SIDE_RELAY_FORWARDING
-> BROKER/MANAGER_RELAY_INGRESS
-> CANONICAL_TELEMETRY
```

最终阶段目标：

```text
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
```

已证明到：

```text
BOARD_SIDE_RELAY_CHAIN=PROVEN
```

当前 blocker：

```text
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
```

当前不得进入：

```text
FULL_CUSTOM_RADIO_OWNERSHIP=DEFERRED
BOARD_RF_REPLAY=FORBIDDEN_WITHOUT_NEW_EVIDENCE_AND_AUTHORIZATION
BROAD_MANAGER_GATEWAY_ACL=FORBIDDEN
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
MAIN_TREE=91d2e4767887dad86525cf521e476d4a1234551a

HANDOFF_STANDARD_COMMIT=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_VERSION=1.0
```

`main` 必须在新会话开始时 fresh query；若已推进，不得把本文中的历史 `MAIN` 误报为 fresh main。

### 3.2 Product / diagnostic source authority

```text
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
```

### 3.3 Evidence / package lineage

```text
ID21_EXECUTION_PACKAGE_COMMIT=9ebe5968e2f06f23a657abbeeb68c4094b445a66
ID22_EXECUTION_PACKAGE_COMMIT=23b3dc63dc112979a8e94928185daf8af2da6640
ID23_EXECUTION_PACKAGE_COMMIT=17709dca4dec4dc5d4f8fceb4c6dbfc135becfa4
```

### 3.4 ID24 repair authority

```text
ID24_REPAIR_PR=400
ID24_REPAIR_PR_STATE=OPEN_DRAFT_UNMERGED
ID24_REPAIR_BASE=17709dca4dec4dc5d4f8fceb4c6dbfc135becfa4
ID24_EXACT_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e

ID24_EXECUTOR=tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/executor.py
ID24_MUTATOR=tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/remote_dynsec_acl_mutator.py
ID24_MANIFEST=tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/manifest.json
ID24_TASK=tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/TASK.md

ID24_DEDICATED_CI_RUN=34764719402
ID24_DEDICATED_CI=PASS
ID24_PUBLIC_REPOSITORY_SAFETY_RUN=34764719347
ID24_PUBLIC_REPOSITORY_SAFETY=PASS
ID24_HOST_ACCEPTANCE_COMMENT_ID=5654195052
```

### 3.5 Central-state documentation authority

P4 前冻结的 exact documentation head：

```text
CENTRAL_ALIGNMENT_PR=401
CENTRAL_ALIGNMENT_PR_STATE=OPEN_DRAFT_UNMERGED
CENTRAL_ALIGNMENT_PRE_HANDOFF_HEAD=5eba333f4fbbd90d1fd73c480b907c61282d7ee1
P3_ACCEPTANCE_COMMENT_ID=5654348361
```

本文自身加入 PR #401 后会推进该 branch head，因此新会话必须 fresh read-back PR #401 head；不得把 `CENTRAL_ALIGNMENT_PRE_HANDOFF_HEAD` 当成当前 branch tip。

### 3.6 Target host / deployment authority

```text
TARGET_HOST_CLASS=T1_PRODUCTION_HOST
TARGET_ARCH=aarch64
DEPLOYED_MANAGER_SOURCE_AUTHORITY=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
MANAGER_CONTAINER_AUTHORITY=greenhouse-manager
BROKER_COMPOSE_PROJECT=n3wfc4
BROKER_COMPOSE_SERVICE=broker
```

不得在 public GitHub 写入 private target locator、credential、raw DynSec state 或 private filesystem paths。

---

## 4. Current Live Baseline

交接前 P4 是 GitHub-only read-only audit，没有重新访问 T1。因此 live runtime 状态只保留最近 direct evidence，并明确要求 future live execution fresh rebind。

```text
T1_FRESHLY_ACCESSED_DURING_P3_P4_P5=false

LAST_PROVEN_MANAGER_STATE=RUNNING_AT_ID23
LAST_PROVEN_BROKER_STATE=RUNNING_AT_ID23
LAST_PROVEN_MANAGER_RUNTIME_STABLE=true
LAST_PROVEN_BROKER_RUNTIME_STABLE=true

CURRENT_MANAGER_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_LIVE_EXECUTION
CURRENT_BROKER_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_LIVE_EXECUTION
CURRENT_DYNSEC_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_LIVE_EXECUTION

BOARD_A_CURRENT_POWER_STATE=UNKNOWN
BOARD_B_CURRENT_POWER_STATE=UNKNOWN
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
LIVE_DYNSEC_MUTATION=false
```

ID21/ID22 已经提供 board-side proof；修复 Manager DynSec blocker 不需要重新访问板卡。

---

## 5. Proven Current Facts

```text
ID21_RESULT=PASS
B_AUTHENTICATED_RELAY_ACQUISITION=PROVEN
B_RELAY_TELEMETRY_SUBMISSION=PROVEN
B_UNICAST_TX_COMPLETION=PROVEN
A_COMPACT_RX=PROVEN
A_COMPACT_DECODE=PROVEN
A_COMPACT_FORWARD_SUBMIT=PROVEN
BOARD_SIDE_RELAY_CHAIN=PROVEN

ID22R2_RESULT=STOP
FIRST_FAILED_OPERATION=T1_MANAGER_RELAY_ACCEPTANCE
BOARD_SIDE_RELAY_CHAIN_PROVEN_IN_ID22_SESSION=true
MANAGER_RELAY_INGRESS=NOT_PROVEN

ID23_EXECUTOR_RESULT=STOP
ID23_POSTEXEC_OFFLINE_ADJUDICATION=PASS
ACTIVE_MANAGER_EXACT_MATCH_COUNT=1
DYNSEC_DEFAULT_SUBSCRIBE_DENY=true
DYNSEC_DEFAULT_PUBLISH_CLIENT_RECEIVE_DENY=true
ACTIVE_MANAGER_RELAY_SUBSCRIBE_ALLOW_COUNT=0
ACTIVE_MANAGER_RELAY_RECEIVE_ALLOW_COUNT=0
LIVE_T1_NODE_SELF_GATEWAY_PUBLISH_ACL=PROVEN_FOR_ALL_3_NODE_CLIENTS

MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING

PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE=PASS
ID24_SOURCE_CONTRACT_REPAIRED=true
ID24_PRECHANGE_SHA256_AUTHORITY_PRESENT=true
ID24_EXACT_LEAST_PRIVILEGE_POSTCHECK_PRESENT=true
ID24_ROLLBACK_AFTER_ANY_STARTED_MUTATION_FAILURE_PRESENT=true
ID24_TRANSACTION_ORCHESTRATION_GUARD_TESTS_PRESENT=true

KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

推断边界：

```text
INFERENCE_NO_ADDITIONAL_DOWNSTREAM_DEFECT=NOT_PROVEN
```

证明当前 blocker 不等于证明修复后一定没有其他下游问题，因此 live repair PASS 后仍必须做 bounded subscription reactivation / E2E verification。

---

## 6. Current Root Cause / Blockers

### Blocker A — Manager Relay DynSec receive ACL missing

```text
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
SOURCE_DEFECT_PROVEN=true
LIVE_RUNTIME_ROLE_MATCH_PROVEN=true
```

Source contract 与 live active Manager role 同时证明缺少 Relay receive coverage；DynSec default subscribe / publishClientReceive 均为 deny。

Repair contract 只允许 exact topic：

```text
gh/v1/<system_id>/ingress/gateway/+/+/frame
```

以及 exact receive trio：

```text
subscribePattern
publishClientReceive
unsubscribePattern
```

### Blocker B — end-to-end confirmation after repair

```text
POST_REPAIR_BROKER_TO_MANAGER_RELAY_INGRESS=NOT_YET_PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

该项不是当前 ACL mutation gate 的失败事实；它只是 repair PASS 后仍需验证的下一层。

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，下一会话不得重新进入：

```text
B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX_AS_FIRST_UNPROVEN_STAGE=CLOSED:ID21_PROVEN
BOARD_SIDE_RELAY_CHAIN_DIAGNOSIS=CLOSED:ID21_AND_ID22_SESSION_PROVEN
NODE_SELF_GATEWAY_PUBLISH_ACL_MISSING_AS_CURRENT_BLOCKER=CLOSED:ALL_3_NODE_CLIENTS_PROVEN
T1_RUNTIME_CONVERGENCE_DETOUR=CLOSED_PASS
ID23_REPLAY=CLOSED:AUTHORIZATION_CONSUMED
ID22R2_REPLAY=CLOSED:AUTHORIZATION_CONSUMED
BROAD_MANAGER_GATEWAY_ACL_REPAIR=FORBIDDEN:LEAST_PRIVILEGE_CONTRACT
FULL_CUSTOM_RADIO_OWNERSHIP=DEFERRED:NO_NEW_EVIDENCE_REQUIRES_IT
BOARD_RF_REPLAY=FORBIDDEN_FOR_CURRENT_REPAIR_ROUTE
```

旧 local handoff V1.0/V1.1 若与本文或 fresh GitHub authority 冲突，只能作为历史证据，不得作为 current authority。

---

## 8. Authorization Ledger

```text
AUTHORIZATION=ID22_ORIGINAL_LIVE_EXECUTION
CLAIMED=true
CONSUMED=true
RESULT=STOP
REPLAY_PERMITTED=false

AUTHORIZATION=ID22R1_LIVE_EXECUTION
CLAIMED=true
CONSUMED=true
RESULT=STOP
REPLAY_PERMITTED=false

AUTHORIZATION=ID22R2_LIVE_EXECUTION
CLAIMED=true
CONSUMED=true
RESULT=STOP_T1_MANAGER_RELAY_ACCEPTANCE
REPLAY_PERMITTED=false

AUTHORIZATION=ID23_LIVE_READONLY_DYNSEC_FORENSIC
CLAIMED=true
CONSUMED=true
RESULT=STOP_FAIL_CLOSED_THEN_OFFLINE_ADJUDICATION_PASS
REPLAY_PERMITTED=false

AUTHORIZATION=PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE_HOST_GITHUB_ONLY
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

当前尚未授予：

```text
PROPOSED_AUTHORIZATION=KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION
GRANTED=false
CLAIMED=false
CONSUMED=false
READY_FOR_NEW_AUTHORIZATION=true
```

`READY_FOR_NEW_AUTHORIZATION=true` 不等于授权。下一会话不得把本 handoff 或 PR acceptance 当成 live mutation authorization。

---

## 9. Rollback Authority

当前 `REQUEST_*_AUTHORIZATION` gate 本身不访问 T1、无 mutation：

```text
CURRENT_GATE_ROLLBACK_AUTHORITY=NOT_APPLICABLE:AUTHORIZATION_DISCUSSION_ONLY
```

若用户随后显式批准 ID24 live mutation，批准范围必须绑定以下已经接受的 rollback contract：

```text
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
PRECHANGE_DYNSEC_SHA256_REQUIRED=true
PRESTATE_DEFECT_MUST_STILL_MATCH=true
MUTATION_TARGET_ACL_COUNT=3
MUTATION_TARGET_TOPIC=gh/v1/<system_id>/ingress/gateway/+/+/frame
MANAGER_RESTART_ALLOWED=false
BROKER_RESTART_ALLOWED=false
SECOND_ATTEMPT_ALLOWED=false
```

Rollback 顺序由 exact repository-versioned executor 实现：

```text
fresh exact prestate snapshot + SHA256
-> begin exact target ACL mutation
-> if any started mutation path does not reach exact repaired poststate
-> remove exact transaction-owned target ACL type/topic pairs
-> independently re-read live DynSec state
-> prove restoration of the proven prestate semantics
-> STOP
```

Rollback failure：

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
AUTO_RETRY=false
```

Historical ID23 raw state 不能替代 future live mutation 前的 fresh rollback snapshot。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION
```

### 10.1 Purpose

只做 authorization discussion：fresh rebind PR #400 exact accepted package authority，向用户展示未来一次性 T1 DynSec mutation 的 exact scope / rollback / forbidden actions，并取得明确批准或不批准。该 gate 本身不触发 Codex live execution。

### 10.2 Frozen inputs

```text
PR400=400
EXPECTED_ACCEPTED_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
EXPECTED_ID24_EXECUTOR=tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/executor.py
EXPECTED_ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
EXPECTED_TARGET_ACL_COUNT=3
EXPECTED_LIVE_AUTHORIZATION_GRANTED=false
```

### 10.3 Required proof / operations

```text
1. Fresh read-only rebind repository main, PR #400 state/head, PR #401 current docs head.
2. Confirm PR #400 remains open/draft/unmerged and exact head remains b973934b....
3. Confirm exact-head Host/CI acceptance remains valid and no source/executor drift occurred.
4. Present the one-shot authorization scope to the user:
   - T1 access allowed only for exact ID24 executor;
   - fresh runtime/DynSec preclaim before mutation;
   - exact three ACL adds only;
   - no Manager/Broker restart;
   - no credential change;
   - no Board/RF access;
   - bounded rollback; no second attempt.
5. Ask for explicit approval.
6. STOP. Do not execute mutation in the same logical gate.
```

### 10.4 PASS

只有用户明确批准 exact scope 时：

```text
REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION=PASS
LIVE_T1_MUTATION_AUTHORIZATION_GRANTED=true
AUTHORIZATION_BOUND_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
READY_FOR_ID24_LIVE_EXECUTION=true
LIVE_EXECUTION_STARTED=false
STOP=true
```

### 10.5 STOP / FAIL

若未明确批准：

```text
LIVE_T1_MUTATION_AUTHORIZATION_GRANTED=false
READY_FOR_ID24_LIVE_EXECUTION=false
STOP=true
```

若 exact package/PR/head/CI 漂移：

```text
AUTHORIZATION_GATE_RESULT=STOP_AUTHORITY_DRIFT
LIVE_T1_MUTATION_AUTHORIZATION_GRANTED=false
RETURN_TO_HIGH_LEVEL_MODEL=true
STOP=true
```

Codex 不得自动进入 live execution。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED — current authorization gate

```text
- GitHub read-only rebind of main / PR #400 / PR #401 / exact-head CI.
- Read-only inspection of public-safe package files and acceptance comments.
- High-level-model presentation of exact authorization scope.
- User approval / rejection discussion.
```

### FORBIDDEN — current authorization gate

```text
- T1 SSH/access.
- DynSec read or mutation.
- Broker/Manager restart/recreate/config mutation.
- Credential change/rotation.
- MQTT application probe.
- Board A/B access.
- USB/serial/Flash/NVS access.
- RF execution.
- PR #400 merge.
- PR #401 merge.
- Any Codex execution of ID24 before explicit user authorization.
- Any automatic transition into the live execution gate.
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
```

---

## 12. Codex DSL Execution Contract

当前 next gate 是 high-level authorization gate，**不调用 Codex 执行 live operation**。为满足 execution semantics 的显式性，当前 gate 的 Codex contract 是硬停止合同：

```text
ROLE:
Low-order executor.

STAGE_SPECIFIC_OVERRIDE=true
DSL_EXECUTION_MODEL=false
PREWRITTEN_EXECUTOR_REQUIRED=true
DSL_COMPILATION_AUTHORIZED=false

CURRENT_GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION

Do not access T1.
Do not read or mutate live DynSec.
Do not access boards.
Do not run RF.
Do not create a substitute executor.
Do not compile a mutation DSL.
Do not claim or consume a live authorization.
Do not enter ID24 live execution.

HARD_STOP=true
```

未来只有在用户完成本 authorization gate、明确批准且 high-level model 再次 rebind exact accepted head 后，Codex 才能机械执行 repository 中的 exact ID24 executor。任何 source/executor drift 都使旧 authorization binding 无效，必须 STOP 返回高阶模型。

---

## 13. Expected Closure

当前 authorization gate 预定义 closure：

```text
=== KF089 MANAGER RELAY DYNSEC ACL REPAIR T1 MUTATION AUTHORIZATION CLOSURE ===

GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION

MAIN_REBIND=
PR400_REBIND=
PR400_STATE=
PR400_EXACT_HEAD=
PR400_EXACT_HEAD_ACCEPTANCE=
PR401_REBIND=

EXPECTED_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
AUTHORIZATION_SCOPE_PRESENTED=
AUTHORIZATION_GRANTED=
AUTHORIZATION_BOUND_REPAIR_HEAD=

LIVE_EXECUTION_STARTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
RF_EXECUTION=false

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

该 closure 必须足以让高阶模型在下一条消息判断是否可以准备 live execution；不得依赖 Codex重新解释 raw log。

---

## 14. After PASS / FAIL

### PASS 后

若用户明确批准且 exact authority 未漂移：

```text
AFTER_PASS_NEXT_STAGE=ID24_MANAGER_RELAY_DYNSEC_ACL_REPAIR_LIVE_EXECUTION
AUTO_EXECUTE_AFTER_PASS=false
SAME_AUTHORIZATION_MAY_BE_CLAIMED_ONCE=true
NEW_AUTHORIZATION_REQUIRED=false
```

执行前仍必须 fresh preclaim；若 head/source/executor/target authority 漂移：

```text
AUTHORIZATION_BINDING_INVALID=true
NEW_AUTHORIZATION_REQUIRED=true
RETURN_TO_HIGH_LEVEL_MODEL=true
```

### STOP / FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
LIVE_EXECUTION_STARTED=false
```

如果未来 ID24 live repair PASS，其下一阶段只允许：

```text
PREPARE_KF089_MANAGER_RELAY_SUBSCRIPTION_REACTIVATION_PACKAGE
```

不得把 ACL repair PASS 直接升级为 `KF089_END_TO_END_RELAY_TELEMETRY=PROVEN`。

---

## 15. KNOWN_FAILURES Updates

本轮已经完成中央 known-failures 对齐：

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
KNOWN_FAILURES_ALREADY_ALIGNED=true
KF_ID=KF-089_CURRENT_ADDENDUM
DOMAIN=MANAGER_RELAY_DYNSEC_RECEIVE_ACL
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
STATUS=OPEN_UNTIL_LIVE_REPAIR_AND_END_TO_END_RETEST
```

当前 authority：

`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`

专项 public-safe addendum：

`docs/development/N3W_KF089_MANAGER_RELAY_DYNSEC_ACL_FAILURE_AND_GUARDS_20260913.md`

---

## 16. New Chat Start Prompt

新会话可直接使用：

```text
阅读《N3W_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PRELIVE_AUTHORIZATION_NEW_CHAT_HANDOFF_V1.2_20260913.md》。

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #400
- PR #401
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W / KF-089。

每次回复先写：
主线任务：
支线任务：
当前任务：

本阶段继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
REPOSITORY_VERSIONED_EXECUTOR=true

注意 stage-specific override：
DSL_EXECUTION_MODEL=false
PREWRITTEN_EXECUTOR_REQUIRED=true
DSL_COMPILATION_AUTHORIZED=false

当前只进入：
NEXT_ONE_GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
LIVE_T1_MUTATION_AUTHORIZATION_GRANTED=false

先 fresh rebind authority，然后只向我展示 exact one-shot T1 mutation authorization scope 并请求批准。
不要访问 T1，不要执行 DynSec mutation，不要访问板卡/RF，不要合并 PR，不要重放任何 consumed authorization，也不要自动进入 live execution。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=KF089_ID24_PRELIVE_AUTHORIZATION
CURRENT_STOP_POINT=FINAL_HOST_GITHUB_CLOSEOUT_COMPLETE

MAIN_AT_P4=7478e0fbcf893761ab76cc9952e09e77cda22755
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57

PR400=OPEN_DRAFT_UNMERGED
ID24_EXACT_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
ID24_HOST_ONLY_PREPARE=PASS

PR401=OPEN_DRAFT_UNMERGED
CENTRAL_ALIGNMENT_PRE_HANDOFF_HEAD=5eba333f4fbbd90d1fd73c480b907c61282d7ee1
CENTRAL_STATE_ALIGNMENT=PASS

BOARD_SIDE_RELAY_CHAIN=PROVEN
SOURCE_DEFECT_PROVEN=true
LIVE_MANAGER_ROLE_DEFECT_MATCH_PROVEN=true
CURRENT_BLOCKER=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN

NEXT_ONE_GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION
LIVE_T1_MUTATION_AUTHORIZATION_GRANTED=false

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_EXECUTE_AFTER_PASS=false

PR400_MERGE_AUTHORIZED=false
PR401_MERGE_AUTHORIZED=false

HANDOFF_STANDARD_VERSION=1.0
STAGE_SPECIFIC_EXECUTION_OVERRIDE=true
DSL_EXECUTION_MODEL=false
PREWRITTEN_EXECUTOR_REQUIRED=true
DSL_COMPILATION_AUTHORIZED=false
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.0

EXECUTION_MODEL_EXPLICIT=PASS
HIGH_LEVEL_CODEX_ROLE_BOUNDARY=PASS
DSL_EXECUTION_SEMANTICS_EXPLICIT=PASS
STAGE_SPECIFIC_DSL_OVERRIDE_EXPLICIT=PASS

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
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
