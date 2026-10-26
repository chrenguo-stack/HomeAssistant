# 温室环境监测系统（ESP32-C6）
# N3-W Scan-triggered First Registration — R2A Source Closure → R2B Cross-store Reconciliation
# 新会话交接文档 V1.0 — 2026-10-26

~~~text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
~~~

> 本文符合 docs/development/NEW_CHAT_HANDOFF_STANDARD.md。
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先 STOP、fresh rebind。

---

## 0. 会话切换结论

R1 与 R2A 已分别完成独立源码闭环。R2A 的 durable first-registration ledger 已在 exact reviewed source head 上通过最终独立 closure 与 19/19 CI。随后只发生 current-state/index docs-only alignment；R2B 尚未写源码。

现在切换会话最合适，因为下一阶段从“单库 durable ledger”进入“跨 Registration / Credential / Application-key / DynSec 四域三态对账”，属于新的完整子阶段。

~~~text
CURRENT_STAGE=R2A_SOURCE_CLOSED_PASS
CURRENT_STOP_POINT=R2A_FINAL_CLOSURE_PASS_STOP
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT_20261026_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
~~~

下一会话不是重新复盘 R1/R2A，而是先 fresh rebind，然后只进入上面的 NEXT_ONE_GATE。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护产品路线、R2A/R2B/R2C/R3 边界与 frozen design；
- 维护 main、PR #679/#680/#681 exact authority；
- 定义 R2B 三态分类、oracle 接口、startup/deadline reconciliation 与 cleanup ownership contract；
- 判断 source/design blocker；
- 根据 closure 决定是否进入后续 R2B source implementation；
- 防止直接摸私有数据库/Broker 文件变成新的旁路架构。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- 读取 GitHub source/test/workflow evidence；
- 做最小必要检索、compare、静态 source inspection；
- 不修改源码；
- 不 dispatch workflow；
- 不访问 T1/Board；
- 第一处 substantive mismatch 后 fail-closed STOP；
- 返回结构化 closure。

Codex 不得自行扩大 scope、修复、重放 consumed authorization、自动进入 R2B implementation/R2C/R3。

### 1.3 DSL execution semantics

~~~text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
~~~

### 1.4 标准交互循环

~~~text
高阶模型：分析 / freeze design / gate
        ↓
Codex：read-only DSL compile → exact inspection → closure
        ↓
高阶模型：PASS / FAIL / STOP
        ↓
如需 source mutation，再由用户单独批准下一 gate
~~~

---

## 2. Product North Star

当前产品路线：

~~~text
用户扫描节点 QR
→ 手机只访问节点本地页面
→ 用户确认“联机注册”
→ 节点才开始 bounded T1 discovery
→ 候选 T1 由用户确认
→ 节点 TLS-pin 连接 T1 47110
→ Manager 建立 durable first-registration transaction
→ exact identity/source-bound 47112 privileged window
→ pairing / credential / application-key / DynSec durable commit
→ node final ACK / pending-ACK recovery
→ 成功后进入正常产品运行
~~~

必须保持：

~~~text
IDLE_NODE_DISCOVERY=false
PHONE_GETS_SETUP_SECRET=false
MANUAL_SECRET_COPY=false
GENERIC_RFC1918_AUTHORIZATION=false
SIDE_CAR_FIRST_REGISTRATION_LEDGER=false
UNKNOWN_EQUALS_NOT_COMMITTED=false
AUTO_DELETE_WITHOUT_OWNERSHIP_PROOF=false
~~~

最终阶段目标仍按 PR #679 frozen implementation order：

~~~text
R1  trusted-product-LAN + passive discovery/bootstrap skeleton
R2  durable first-registration journal + cross-store restart/deadline reconciliation + peer-trust baseline
R3  identity-bound 47112 + unified 1800 s deadline
R4  node local registration portal + QR
R5  scan-triggered discovery + multi-T1 selection
R6  node->T1 TLS bootstrap + pending-ACK/status + pairing-client refactor
R7  LCD
R8  simulated E2E/regression/safety
R9  exact artifact + independent review
R10 separately authorized physical acceptance
~~~

当前不得进入：

~~~text
R2C_SYSTEM_PEER_KEY_SOURCE_MUTATION
R3_47112_IDENTITY_BOUND_WINDOW
R4_NODE_PORTAL
R5_SCAN_TRIGGERED_DISCOVERY
R6_NODE_TLS_BOOTSTRAP
R7_LCD
R8_PLUS
T1_LIVE_DEPLOYMENT
BOARD_FLASH_OR_PHYSICAL_ACCEPTANCE
PR680_OR_PR681_MERGE
~~~

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=507dbd49495c558b1344f7d713938b733b3bad18
TREE=NOT_REQUIRED_FOR_THIS_GATE:EXACT_COMMIT_SHA_IS_SOURCE_AUTHORITY

HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD=docs/development/NEW_CHAT_HANDOFF_STANDARD.md
HANDOFF_TEMPLATE=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

PR679_FROZEN_DESIGN_HEAD=81dbf9de789232df7dadf21f4bd37bb5c9fc67d5
PR679_STATE=OPEN_DRAFT_UNMERGED
DESIGN_AUTHORITY=docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md

PR680_R1_REVIEWED_HEAD=e74913056f6c1d54e553e5b1037f7de3ef3172c8
PR680_EXACT_HEAD_CI=25/25_PASS
PR680_STATE=OPEN_DRAFT_UNMERGED
R1_SOURCE_CLOSURE=PASS

PR681_R2A_REVIEWED_SOURCE_HEAD=7c7cdf8bd37ba23201995002c7bcb91fe017bd1e
PR681_EXACT_REVIEWED_SOURCE_CI=19/19_PASS
PR681_STATE=OPEN_DRAFT_MERGEABLE_UNMERGED

R2A_POST_REVIEW_STATE_ALIGNMENT_COMMIT_1=c1e4cde8d9ea8891e131c5a7eb4d5a1ebf58fd4d
R2A_POST_REVIEW_STATE_ALIGNMENT_COMMIT_2=e27effe35d6768c9143c98643950924a2640f7c3
POST_REVIEW_DELTA_FROM_7C7C_TO_E27E=DOCS_ONLY_CURRENT_STATE_AND_INDEX

CURRENT_BRANCH_HEAD_AT_HANDOFF_AUTHORING=e27effe35d6768c9143c98643950924a2640f7c3
CURRENT_BRANCH_HEAD_REQUIRES_FRESH_READONLY_REBIND=true
~~~

本文提交本身会再产生一个 docs-only commit，因此新会话必须 fresh rebind PR #681；不得把 handoff commit 当成新的 reviewed product/source authority。R2A reviewed product/source authority 仍是 7c7cdf8b....

### 3.2 Candidate / artifact / image

~~~text
CANDIDATE_REF=PR681
CANDIDATE_ID=R2_SOURCE_STACK
VERSION=R2A_CLOSED_R2B_NOT_ENTERED
REVISION=7c7cdf8bd37ba23201995002c7bcb91fe017bd1e
ARCH=NOT_APPLICABLE:SOURCE_READONLY_GATE
ARTIFACT_AUTHORITY=NOT_APPLICABLE:NO_BUILD_OR_ARTIFACT_IN_NEXT_GATE
~~~

### 3.3 Successor / deployment material

~~~text
SUCCESSOR_AUTHORITY=NOT_APPLICABLE:SOURCE_READONLY_GATE
~~~

### 3.4 Target host / runtime authority

~~~text
TARGET_HOST=NOT_APPLICABLE:SOURCE_READONLY_GATE
TARGET_ARCH=NOT_APPLICABLE:SOURCE_READONLY_GATE
LIVE_T1_AUTHORITY_REQUIRED=false
BOARD_AUTHORITY_REQUIRED=false
~~~

---

## 4. Current Live Baseline

本轮 R1/R2A source work 没有重新读取 live T1/Board，因此不得把历史 live evidence 冒充当前事实。

~~~text
LIVE_BASELINE_CLASS=NOT_REBOUND_FOR_SOURCE_ONLY_HANDOFF

MANAGER_STATE=NOT_REBOUND
MANAGER_IMAGE_ID=NOT_REBOUND
MANAGER_RESTART_STATE=NOT_REBOUND

BROKER_STATE=NOT_REBOUND
BROKER_IMAGE_ID=NOT_REBOUND
BROKER_RESTART_STATE=NOT_REBOUND

HOMEASSISTANT_STATE=NOT_REBOUND
HOMEASSISTANT_IMAGE_ID=NOT_REBOUND

PAIRING_SERVICE_STATE=NOT_REBOUND
PAIRING_PORT_OWNER_STATE=NOT_REBOUND

LIVE_FACTS_REQUIRED_BY_NEXT_GATE=false
LIVE_FACTS_IF_LATER_NEEDED_REQUIRE_FRESH_READONLY_REBIND=true

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
~~~

---

## 5. Proven Current Facts

~~~text
R1_READY=YES
R2A_READY=YES
R2B_ENTRY_READY=YES

R2A_LEDGER_FILE=host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_first_registration_ledger.py
R2A_LEDGER_TABLE=first_registration_attempts
R2A_LEDGER_SAME_REGISTRATION_SQLITE_DB=true
R2A_LEDGER_SAME_CONNECTION=true
R2A_LEDGER_SAME_RLOCK=true
R2A_OUTER_TRANSACTION_ROLLBACK_DIRECTLY_TESTED=true

R2A_SETUP_SECRET_PERSISTED=false
R2A_RAW_HARDWARE_ID_PERSISTED=false
R2A_MQTT_PASSWORD_PERSISTED=false
R2A_APPLICATION_KEY_MATERIAL_PERSISTED=false
R2A_SYSTEM_PEER_KEY_PERSISTED=false

R2A_PAIRING_ID_PRIMARY_REPLAY_KEY=true
R2A_MAX_ACTIVE_ATTEMPTS=1
R2A_UNRESOLVED_PREDECESSOR_BLOCKS_NEW_ATTEMPT=true
R2A_PRESTATE_REQUIRES_HELLO_OBSERVED=true
R2A_BUNDLE_STAGED_REQUIRES_TWO_PRESTATE_ABSENT_PROOFS=true
R2A_COMMITTED_REQUIRES_PRIOR_COMMITTING=true

R2A_EXPIRED_REASON=expired
R2A_RESTART_INVALIDATED_REASON=replay_detected
R2A_TERMINAL_READER_CORRUPTION_FAIL_CLOSED=true

R2A_CLEAN_STATE_AUTHORITY_UPDATED=true
R2A_REVIEWED_HEAD_CI=19/19_PASS
R2A_GREENHOUSE_MANAGER_TEST=1430_PASS_1_SKIP
~~~

R2B preflight 已直接从 current source 确认：

~~~text
REGISTRATION_PUBLIC_GET_BY_HARDWARE_ID=true
REGISTRATION_PUBLIC_GET_BY_PAIRING_ID=false

CREDENTIAL_PUBLIC_GET_BY_HARDWARE_ID=true
CREDENTIAL_PUBLIC_LIST_BY_HARDWARE_ID=true
CREDENTIAL_PUBLIC_GET_BY_PAIRING_ID=false

APPLICATION_KEY_GLOBAL_AUDIT=true
APPLICATION_KEY_PUBLIC_EXACT_NODE_EPOCH_SECRET_FREE_SNAPSHOT=false

DYNSEC_PRIVATE_TARGET_PRESENCE_EXISTS=true
DYNSEC_TARGET_PRESENCE_ONLY_PROVES_NAMES=true
DYNSEC_PUBLIC_EXACT_PLAN_INSPECTOR=false
~~~

Frozen design 还直接要求：

~~~text
R2B_CLASSIFICATION_VALUES=COMMITTED|DEFINITELY_NOT_COMMITTED|UNKNOWN
UNKNOWN_FAIL_CLOSED=true
ONLY_DEFINITELY_NOT_COMMITTED_MAY_ENTER_AUTOMATIC_DESTRUCTIVE_CLEANUP=true
COMMITTED_REQUIRES_DURABLE_PHASE_COMMITTING=true
RAW_HARDWARE_ID_RECOVERY_MUST_USE_PAIRING_SESSION_BY_PAIRING_ID=true
RAW_HARDWARE_ID_SHA256_MUST_MATCH_LEDGER=true
~~~

推断/提议与 proven fact 分离：

~~~text
PROPOSED_R2B_REGISTRATION_ORACLE=EXACT_UNIQUE_LOOKUP_BY_PAIRING_ID
PROPOSED_R2B_CREDENTIAL_ORACLE=EXACT_UNIQUE_LOOKUP_BY_PAIRING_ID
PROPOSED_R2B_APPLICATION_KEY_ORACLE=SECRET_FREE_NODE_EPOCH_SNAPSHOT
PROPOSED_R2B_DYNSEC_ORACLE=EXACT_DETERMINISTIC_PLAN_INSPECTOR
~~~

这些 PROPOSED_* 尚未实现，NEXT_ONE_GATE 必须先验证接口合同是否充分、是否会引入新的 authority bypass。

---

## 6. Current Root Cause / Blockers

R2A 当前没有 blocker：

~~~text
CURRENT_R2A_BLOCKER_COUNT=0
R2A_SOURCE_DEFECT_PROVEN=false
R2A_RUNTIME_DEFECT_PROVEN=false
~~~

R2B 尚未实现，不把“尚未实现”误写成故障：

~~~text
R2B_IMPLEMENTATION_STATUS=NOT_ENTERED
R2B_CURRENT_BLOCKER_COUNT=UNKNOWN_UNTIL_NEXT_PREFLIGHT
R2B_SOURCE_DEFECT_PROVEN=false
R2B_RUNTIME_DEFECT_PROVEN=false
~~~

NEXT_ONE_GATE 的任务是判断 frozen design + current source seams 是否足以进入 R2B source implementation，或是否需要先做 source-design precision repair。

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，不得重新进入：

~~~text
R1_REOPEN=CLOSED:R1_FINAL_SOURCE_CLOSURE_25_OF_25_PASS
R2A_REOPEN=CLOSED:R2A_FINAL_CLOSURE_19_OF_19_PASS

SIDE_CAR_FIRST_REGISTRATION_LEDGER=FORBIDDEN
RAW_HARDWARE_ID_IN_ATTEMPT_LEDGER=FORBIDDEN
SETUP_SECRET_IN_ATTEMPT_LEDGER=FORBIDDEN

CROSS_STORE_MATCH_WITHOUT_COMMITTING_EQUALS_COMMITTED=FORBIDDEN
UNKNOWN_EQUALS_DEFINITELY_NOT_COMMITTED=FORBIDDEN
READ_FAILURE_EQUALS_NOT_COMMITTED=FORBIDDEN

TARGET_PRESENCE_EQUALS_CLEANUP_OWNERSHIP=FORBIDDEN
ATTEMPTED_CREATE_EQUALS_CLEANUP_OWNERSHIP=FORBIDDEN
DESTRUCTIVE_CLEANUP_WITHOUT_PRESTATE_PLUS_BUNDLE_STAGED_PROOF=FORBIDDEN

RECONCILER_DIRECT_PRIVATE_SQL_AS_DEFAULT_ARCHITECTURE=FORBIDDEN
RECONCILER_DIRECT_DYNAMIC_SECURITY_JSON_PARSE_AS_DEFAULT_ARCHITECTURE=FORBIDDEN

R2C_SYSTEM_PEER_KEY_MUTATION_IN_R2B=FORBIDDEN
R3_47112_WINDOW_MUTATION_IN_R2B=FORBIDDEN

PR680_AUTO_MERGE=FORBIDDEN
PR681_AUTO_MERGE=FORBIDDEN
T1_LIVE_APPLY=FORBIDDEN
BOARD_ACCESS=FORBIDDEN
~~~

历史 PR #664 的 out-of-band Manager recreate live onboarding route 已被 replacement architecture supersede；其 one-shot live authorization 已 consumed，不得 replay。

---

## 8. Authorization Ledger

### 8.1 已完成的 R2A source scope

~~~text
AUTHORIZATION=R2A_SOURCE_IMPLEMENTATION_AND_REPAIR_SCOPE
CLAIMED=true
CONSUMED=true
RESULT=PASS_STOP
REPLAY_PERMITTED=false
SUPERSEDED_BY=R2A_FINAL_CLOSURE_20261026_02
~~~

### 8.2 历史 live onboarding one-shot

~~~text
AUTHORIZATION=PR664_FAILED_LIVE_ONBOARDING_ONE_SHOT
CLAIMED=true
CONSUMED=true
RESULT=FAILED_TERMINAL
REPLAY_PERMITTED=false
SUPERSEDED_BY=SCAN_TRIGGERED_FIRST_REGISTRATION_REDESIGN
~~~

### 8.3 当前 next gate

~~~text
AUTHORIZATION=R2B_SOURCE_DESIGN_AND_PREFLIGHT_READONLY
CLAIMED=false
CONSUMED=false
RESULT=NOT_REQUIRED_FOR_READONLY_GATE
REPLAY_PERMITTED=true
SUPERSEDED_BY=
~~~

### 8.4 未授权事项

~~~text
PROPOSED_AUTHORIZATION=R2B_SOURCE_IMPLEMENTATION
GRANTED=false

PROPOSED_AUTHORIZATION=PR681_MERGE
GRANTED=false

PROPOSED_AUTHORIZATION=T1_LIVE_MUTATION
GRANTED=false

PROPOSED_AUTHORIZATION=BOARD_PHYSICAL_ACCESS
GRANTED=false
~~~

READY_FOR_R2B_ENTRY=true 仅表示可以进入 read-only design/preflight，不等于 source implementation authorization。

---

## 9. Rollback Authority

NEXT_ONE_GATE 完全只读：

~~~text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
LIVE_RUNTIME_MUTATION=false
REPOSITORY_MUTATION=false
SECOND_ATTEMPT_ALLOWED=true
~~~

如果下一会话发现需要源码修改，必须 STOP 并返回高阶模型；不得在本 gate 内自行修复。

---

## 10. Next ONE Gate

~~~text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT_20261026_01
~~~

### 10.1 Purpose

对 frozen R2 reconciliation design 与 current source seam 做独立、只读、从上位合同出发的 preflight，冻结 R2B implementation contract。重点证明四个 authority 能通过窄的 typed/read-only oracle 构成 exact commit classifier，并冻结 startup/deadline reconciliation 与 destructive cleanup 的 fail-closed 顺序。

本 gate 不写源码。

### 10.2 Frozen inputs

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_AT_HANDOFF=507dbd49495c558b1344f7d713938b733b3bad18

FROZEN_DESIGN_HEAD=81dbf9de789232df7dadf21f4bd37bb5c9fc67d5
R1_HEAD=e74913056f6c1d54e553e5b1037f7de3ef3172c8
R2A_REVIEWED_SOURCE_HEAD=7c7cdf8bd37ba23201995002c7bcb91fe017bd1e

PR681_NUMBER=681
PR681_CURRENT_HEAD_MUST_BE_FRESH_REBOUND=true

PRIMARY_DESIGN=docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md

R2A_LEDGER=host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_first_registration_ledger.py
REGISTRATION_AUTHORITY=host/greenhouse-manager/src/greenhouse_manager/runtime/registration.py
CREDENTIAL_AUTHORITY=host/greenhouse-manager/src/greenhouse_manager/runtime/credential_lifecycle.py
APPLICATION_KEY_AUTHORITY=host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_node_application_keys.py
DYNSEC_AUTHORITY=host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_api.py
DYNSEC_PLAN=host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_plan.py
~~~

### 10.3 Required proof / operations

~~~text
1. Fresh rebind main + PR #679 + PR #680 + PR #681.
2. Prove whether PR #681 delta after reviewed R2A source head is docs-only.
   Any unexpected source/test/workflow drift => FAIL_STOP.
3. Re-read frozen design sections:
   - durable ledger
   - ownership before pre-commit mutation
   - final commit oracle
   - three-valued classification
   - startup/deadline reconciliation
   - SYSTEM_PEER_KEY boundary
   - implementation order.
4. Independently inspect current source; do not accept this handoff's preflight conclusions without verification.
5. Freeze RegistrationRegistry read oracle:
   - exact lookup by pairing_id
   - ambiguity/missing semantics
   - returned raw hardware_id only inside Manager process
   - SHA256(raw hardware_id) exact match to ledger
   - exact pairing/node/state/lease predicates.
6. Freeze CredentialLifecycle read oracle:
   - exact pairing_id lookup
   - ambiguity/missing semantics
   - ACTIVE generation-1 exact predicates
   - pending_generation must be null
   - hardware hash + node binding.
7. Freeze Application-key oracle:
   - secret-free exact node_id + ledger epoch snapshot
   - exact ACTIVE/STAGED/GRACE/REVOKED state semantics
   - conflicting ACTIVE/GRACE detection
   - store unreadable/corrupt => UNKNOWN
   - no key material/path emitted to reconciler/public diagnostics.
8. Freeze DynSec exact-plan inspector:
   - deterministic generation-1 plan
   - exact client username/clientid
   - exact client->role assignment
   - exact role ACL structure
   - malformed/unreadable/ambiguous => UNKNOWN
   - name presence alone is insufficient.
9. Freeze classifier truth table:
   COMMITTED / DEFINITELY_NOT_COMMITTED / UNKNOWN.
10. Prove COMMITTED is impossible without durable ledger phase=COMMITTING.
11. Freeze startup/deadline ordering:
    old pairing becomes non-resumable first
    -> classify cross-store state
    -> COMMITTED promotion OR terminal non-commit OR FAILED/UNKNOWN
    -> only exact owned cleanup
    -> cleanup COMPLETE before a fresh transaction.
12. Freeze exact cleanup ownership proof:
    prestate-absent + BUNDLE_STAGED-or-later required for DynSec/application-key deletion.
13. Freeze restart-before-HELLO behavior: ledger tombstone only; no invented pairing-session cleanup.
14. Freeze R2C boundary:
    SYSTEM_PEER_KEY lifecycle is NOT implemented by R2B.
15. Freeze R3 boundary:
    identity-bound 47112 / unified 1800-second wiring is NOT implemented by R2B.
16. Decide whether design/source seams are sufficiently precise for source implementation.
17. Do not modify repository, source, tests, workflows or PR state.
18. Return closure and STOP.
~~~

### 10.4 PASS

~~~text
R2B_DESIGN_PREFLIGHT=PASS
R2B_DESIGN_BLOCKER_COUNT=0
SOURCE_DESIGN_PRECISION_REQUIRED=NO
R2B_IMPLEMENTATION_PLAN_READY=true
REPOSITORY_MUTATION=false
STOP=true
~~~

### 10.5 FAIL

~~~text
R2B_DESIGN_PREFLIGHT=FAIL
R2B_DESIGN_BLOCKER_COUNT=>0
R2B_IMPLEMENTATION_PLAN_READY=false
REPOSITORY_MUTATION=false
STOP=true
~~~

Codex 不得自动设计修补或进入 source implementation。

---

## 11. Hard Allowed / Forbidden Scope

Default：

~~~text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
REPOSITORY_MUTATION=false
WORKFLOW_DISPATCH=false
MERGE=false
~~~

### ALLOWED

~~~text
- GitHub read-only PR/commit/compare/source/test/workflow inspection
- exact source search/read
- frozen design read
- current state/index/known-failures read
- reasoning and interface-contract drafting in closure
- existing CI log read
~~~

### FORBIDDEN

~~~text
- update/create/delete repository files
- source or test mutation
- workflow dispatch/rerun
- PR merge/close/ready-for-review mutation
- T1 SSH/live access
- Broker/Manager/Home Assistant mutation
- Board/USB/serial/flash/NVS/RF access
- R2C peer-trust implementation
- R3 47112 implementation
- physical acceptance
~~~

~~~text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
PR_COMMENT_WRITE=false
~~~

---

## 12. Codex DSL Execution Contract

~~~text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required unless
this protocol explicitly says so.

Mechanically compile this DSL into the minimum necessary read-only commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry mutation because mutation is forbidden.
Do not enter the next gate.

============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT_20261026_01

READ_ONLY=true
REPOSITORY_MUTATION=false
WORKFLOW_DISPATCH=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
MERGE=false

============================================================
1. FROZEN INPUTS
============================================================

repository=chrenguo-stack/HomeAssistant
main_at_handoff=507dbd49495c558b1344f7d713938b733b3bad18
design_head=81dbf9de789232df7dadf21f4bd37bb5c9fc67d5
r1_head=e74913056f6c1d54e553e5b1037f7de3ef3172c8
r2a_reviewed_source_head=7c7cdf8bd37ba23201995002c7bcb91fe017bd1e
pr681=681

Never assume current PR head equals the handoff authoring head.
Fresh rebind first.

============================================================
2. HARD SCOPE
============================================================

Only:
- R2B four-store read-oracle contract
- three-valued classifier
- startup/deadline reconciliation
- exact cleanup ownership
- R2C/R3 isolation
- design/source seam blocker discovery.

Do not:
- write code
- write tests
- write docs
- write PR comments
- dispatch CI
- access live T1/Board
- merge.

============================================================
3. FRESH REBIND
============================================================

Read current:
- main
- PR #679
- PR #680
- PR #681
- PR #681 current head CI
- compare r2a_reviewed_source_head -> current PR #681 head.

If any source/test/workflow file changed after r2a_reviewed_source_head:
  classify exact drift
  STOP with R2A_POST_CLOSURE_SOURCE_DRIFT=true.
Do not silently review a moving source target.

Docs-only handoff/state alignment is permitted evidence drift.

============================================================
4. DESIGN AUTHORITY
============================================================

Read the frozen design at design_head.
Extract exact requirements for:
- sections 6.3-6.7
- cross-store commit oracle
- three-valued classification
- startup/deadline reconciliation
- cleanup ownership
- SYSTEM_PEER_KEY separation
- implementation order.

Do not weaken UNKNOWN semantics.

============================================================
5. CURRENT SOURCE SEAMS
============================================================

Read:
- n3w_first_registration_ledger.py
- registration.py
- credential_lifecycle.py
- n3w_node_application_keys.py
- dynsec_api.py
- dynsec_plan.py
and focused tests.

Determine current public/read-only APIs versus missing narrow APIs.

Do not use private implementation reachability as proof that a safe public oracle already exists.

============================================================
6. FOUR AUTHORITY ORACLES
============================================================

Freeze exact contracts for:
A. RegistrationRegistry pairing_id lookup
B. CredentialLifecycle pairing_id lookup
C. Application-key node/epoch secret-free snapshot
D. DynSec deterministic-plan exact inspector

For each define:
- input
- output
- missing
- ambiguous
- corrupt/unreadable
- exact PASS predicates
- secret/public-output boundary.

============================================================
7. THREE-VALUED CLASSIFIER
============================================================

Freeze:
COMMITTED
DEFINITELY_NOT_COMMITTED
UNKNOWN

COMMITTED requires:
- ledger phase COMMITTING
- every exact cross-store commit predicate readable and PASS.

DEFINITELY_NOT_COMMITTED requires:
- every required store readable and internally consistent
- exact active MQTT credential generation 1 for pairing_id absent
- no contradictory committed evidence.

Everything else is UNKNOWN.

UNKNOWN must never authorize destructive cleanup.

============================================================
8. RESTART / DEADLINE RECONCILIATION
============================================================

Freeze ordering:
old pairing non-resumable
-> classify
-> terminal disposition
-> owned cleanup if and only if authorized
-> prove no active old credential
-> cleanup COMPLETE
-> only then permit successor registration.

Verify restart-before-HELLO tombstone-only case.

============================================================
9. SCOPE ISOLATION
============================================================

R2C_SYSTEM_PEER_KEY_MUTATION=false
R3_47112_MUTATION=false
NODE_FIRMWARE_MUTATION=false
LIVE_DEPLOYMENT=false

============================================================
10. HARD STOP
============================================================

Return only the structured closure.
Do not implement.
Do not repair.
Do not enter successor gate.
~~~

---

## 13. Expected Closure

~~~text
=== N3W_SCAN_TRIGGERED_FIRST_PAIRING_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT CLOSURE ===

EXECUTION_ID=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT_20261026_01

AUTHORIZATION=READ_ONLY_NOT_REQUIRED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

MAIN=
PR679_HEAD=
PR680_HEAD=
PR681_HEAD=
R2A_REVIEWED_SOURCE_HEAD=7c7cdf8bd37ba23201995002c7bcb91fe017bd1e
R2A_POST_CLOSURE_SOURCE_DRIFT=

DESIGN_AUTHORITY_PASS=

REGISTRATION_PAIRING_ID_ORACLE=
CREDENTIAL_PAIRING_ID_ORACLE=
APPLICATION_KEY_NODE_EPOCH_ORACLE=
DYNSEC_EXACT_PLAN_ORACLE=

COMMITTED_CLASSIFIER_CONTRACT=
DEFINITELY_NOT_COMMITTED_CLASSIFIER_CONTRACT=
UNKNOWN_CLASSIFIER_CONTRACT=

STARTUP_RECONCILIATION_ORDER=
DEADLINE_RECONCILIATION_ORDER=
CLEANUP_OWNERSHIP_CONTRACT=
RESTART_BEFORE_HELLO_CONTRACT=

R2C_SCOPE_ISOLATION=
R3_SCOPE_ISOLATION=

R2B_DESIGN_BLOCKER_COUNT=
SOURCE_DESIGN_PRECISION_REQUIRED=
R2B_IMPLEMENTATION_PLAN_READY=

REPOSITORY_MUTATION=false
WORKFLOW_DISPATCH=false
LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
~~~

---

## 14. After PASS / FAIL

### PASS 后

~~~text
AFTER_PASS_NEXT_STAGE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R2B_CROSS_STORE_RECONCILIATION_SOURCE_IMPLEMENTATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
~~~

用户必须单独批准 R2B source implementation；不得因为 preflight PASS 自动改源码。

### FAIL 后

~~~text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
~~~

先修设计/authority precision，再决定是否产生新的 source gate。

---

## 15. KNOWN_FAILURES Updates

交接时：

~~~text
KNOWN_FAILURES_UPDATE_REQUIRED=false
REASON=NO_NEW_PROJECT_OR_LIVE_FAILURE_OPENED_BY_R2A
~~~

R2A review 内发现的 SIM102 lint blocker 与 terminal reader false-PASS 已在同一 source branch 修复并由 regression + exact-head CI 关闭，不新开 KF。

与下一 gate 直接相关的既有 guards 必须保留：
- KF-060：attempted/present object 不是 rollback ownership proof；
- KF-036/KF-041：replay tombstone 不得被恢复流程改写成 fresh identity；
- KF-045：host/container DB path authority 不得混用；
- KF-070/KF-071：runtime/authority classifier 不得靠名称/静态猜测；
- pairing/security lifecycle separation：pairing retry 不得推进 credential/application-key/SYSTEM_PEER_KEY lifecycle。

若 NEXT_ONE_GATE 发现新的真实 source/design failure，再返回高阶模型决定是否需要新 KF；不得预先编号。

---

## 16. New Chat Start Prompt

~~~text
阅读《docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R2A_SOURCE_CLOSURE_TO_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261026.md》。

同时读取：
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false

先 fresh rebind：
- repository main
- PR #679
- PR #680
- PR #681

必须承认：
- frozen design head = 81dbf9de789232df7dadf21f4bd37bb5c9fc67d5
- R1 reviewed head = e74913056f6c1d54e553e5b1037f7de3ef3172c8
- R2A reviewed product/source head = 7c7cdf8bd37ba23201995002c7bcb91fe017bd1e
- R1 CLOSED_PASS
- R2A CLOSED_PASS
- R2B source mutation尚未进入
- PR #680/#681 都没有 merge authorization
- 本 handoff/state alignment 之后允许有 docs-only head advance，但任何 source/test/workflow drift 都必须先 STOP 分类

当前只进入：
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT_20261026_01

本 gate 严格只读：
REPOSITORY_MUTATION=false
WORKFLOW_DISPATCH=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

独立复核 frozen design 和 current source，不能只接受 handoff/PR comment 的结论。

只复核并冻结：
1. RegistrationRegistry pairing_id read oracle
2. CredentialLifecycle pairing_id read oracle
3. application-key exact node/epoch secret-free oracle
4. DynSec deterministic exact-plan oracle
5. COMMITTED / DEFINITELY_NOT_COMMITTED / UNKNOWN classifier
6. startup/deadline reconciliation ordering
7. destructive cleanup ownership contract
8. R2C/R3 scope isolation

不得自动修源码。
不得自动进入 R2B implementation。
不得重放任何 consumed live authorization。

输出 handoff 第 13 节定义的 exact closure，并 STOP。
~~~

---

## 17. Final Frozen State

~~~text
CURRENT_STAGE=R2A_SOURCE_CLOSED_PASS
CURRENT_STOP_POINT=R2A_FINAL_CLOSURE_PASS_STOP

SOURCE_DEFECT_PROVEN=false
CURRENT_BLOCKER=NONE_IN_R2A
R2B_IMPLEMENTATION_STATUS=NOT_ENTERED

MAIN_AT_HANDOFF=507dbd49495c558b1344f7d713938b733b3bad18
FROZEN_DESIGN_HEAD=81dbf9de789232df7dadf21f4bd37bb5c9fc67d5
R1_REVIEWED_HEAD=e74913056f6c1d54e553e5b1037f7de3ef3172c8
R2A_REVIEWED_SOURCE_HEAD=7c7cdf8bd37ba23201995002c7bcb91fe017bd1e
DOCS_ALIGNMENT_HEAD_BEFORE_HANDOFF=e27effe35d6768c9143c98643950924a2640f7c3

R1_CI=25/25_PASS
R2A_CI=19/19_PASS
R2A_READY=YES
R2B_ENTRY_READY=YES

LIVE_SYSTEM_STATE=NOT_REBOUND_NOT_REQUIRED_FOR_NEXT_GATE

NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R2B_CROSS_STORE_RECONCILIATION_SOURCE_DESIGN_AND_PREFLIGHT_20261026_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
REPOSITORY_MUTATION=false
MERGE_AUTHORIZED=false

HANDOFF_STANDARD_VERSION=1.0
~~~

---

## 18. Handoff Compliance Audit

~~~text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.0

EXECUTION_MODEL_EXPLICIT=PASS
HIGH_LEVEL_CODEX_ROLE_BOUNDARY=PASS
DSL_EXECUTION_SEMANTICS_EXPLICIT=PASS

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
~~~
