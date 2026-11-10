# 温室环境监测系统（ESP32-C6）
# N3-W / T1 Home Assistant mandatory-USB OTA / R7A A1 rollback closure → successor authorization
# 新会话交接文档 V1.0 — 2026-11-08

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文符合 historical exact handoff process authority `4300890dff0ce63d5a547df21426e287d084d9ee` 中的 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 与 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`。  
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先停止执行、完成 fresh rebind。

---

## 0. 会话切换结论

本轮已经完成 A1 _01 现场失败分类、自动回滚真实状态确认、restart container-convergence 根因修复与 exact-head 25/25 CI。用户明确要求：**本会话不建立新的 A1 一次性授权**；先同步 GitHub 并输出 handoff，在下一会话 fresh rebind 后再建立新的 A1 successor authorization，随后继续 activation。

```text
CURRENT_STAGE=R7A_A1_01_ROLLED_BACK_HEALTHY_AND_RESTART_SETTLE_REPAIR_CLOSED_PASS
CURRENT_STOP_POINT=BEFORE_SUCCESSOR_A1_AUTHORIZATION
NEXT_ONE_GATE=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_SUCCESSOR_LIVE_AUTHORIZATION_BINDING_20261108_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘全部历史；先 fresh rebind authorities，再只进入 `NEXT_ONE_GATE`。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护产品路线、exact source/runtime authority 与 authorization ledger；
- 判断 A1 successor 是否仍满足当前 live baseline；
- 设计 distinct one-shot successor authorization，并防止 replay _01；
- 根据后续 closure 做 PASS / FAIL / STOP；
- 区分 product defect、executor readiness defect、CI transient 与真实 live recovery；
- 不把 acceptance/tooling 复杂度扩展成新的产品架构。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- 运行必要 Git/GitHub/测试命令；
- mutation 只能发生在用户明确批准的 exact successor authorization 内；
- live activation 之前必须重新绑定 exact repaired source、CI 与 fresh live preflight；
- 第一处 substantive mismatch fail-closed STOP；
- 不自行修复、不 replay consumed _01、不自动进入 USB PREPARE/U2+。

### 1.3 DSL execution semantics

```text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
```

当前 A1 路径已有 audited executor；DSL compilation 用于 fresh rebind、authorization binding、evidence capture 与必要的最小命令，不得另造平行执行框架。

### 1.4 标准交互循环

```text
高阶模型：fresh rebind / gate / successor authorization design
        ↓
用户：批准 exact successor authorization
        ↓
Codex：bind exact authorization → CI → fresh live preflight → one-shot activation
        ↓
高阶模型：复核 closure / 决定下一步
```

---

## 2. Product North Star

当前产品路线：

```text
R7A_PREPARE_U1_TO_U4_SOURCE
→ accepted Manager successor
→ narrow host-side privileged daemon
→ Manager non-root read-only Unix-socket OTA control path
→ later mandatory-USB PREPARE transaction
```

最终阶段目标：

```text
普通用户可通过产品控制面执行 Home Assistant mandatory-USB OTA；
Manager 保持 UID/GID 999:999、无 Docker socket、无 block-device 权限；
host-side T1 Core Updater 独占特权 USB/镜像/恢复操作；
升级与数据 rollback 可证明、可恢复、fail-closed。
```

当前不得进入：

```text
REAL_USB_FORMAT
PREPARE_INTENT
CONFIRM_USB_ERASE
U2_PLUS_INSTALL
BOARD_ACCESS
MERGE
A1_01_REPLAY
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
MAIN_TREE=f15bec7c33c4d44d27c7068e5579b07027dd5ea5
PR799_HEAD=462018cbf341f1b762a35f82a87a7c98e4a8b615
PR800_EXECUTABLE_REPAIR_HEAD=922a106bd32ce98a07d2280cf08a6a9f116a11a6
PR800_EXECUTABLE_REPAIR_TREE=3712bbcf20e47f7cf1f92fc26ce238eed6e95fd8
PR800_EXECUTABLE_REPAIR_CI=25_SUCCESS_0_FAILURE_0_PENDING
PR800_STATE=OPEN_DRAFT
```

PR #800 是 stacked PR，base authority 为 PR #799 head；新会话必须同时 fresh rebind main、PR #799 与 PR #800，禁止把 PR #800 head 误报为 main。

### 3.2 Candidate / artifact / image

```text
MANAGER_TARGET=local/greenhouse-manager:fresh-bf38e388497b
MANAGER_TARGET_RUNTIME_IMAGE_ID=sha256:e88a22b29b93b0db0d3b4f592cb0fd773169d1dc0f043219f14d5247ed859dff
HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_RUNTIME_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
BROKER=local/n3w-mosquitto:2.1.2-3184566d
BROKER_RUNTIME_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
ARCH=linux/arm64
```

A0 package historical exact authority remains artifact `13564899377`; it is not the next execution input.

### 3.3 Successor / deployment material

```text
A1_EXECUTOR_PATH=tools/execution_packages/n3w/r7a/host_a1_live_activation/executor.py
A1_MANIFEST_PATH=tools/execution_packages/n3w/r7a/host_a1_live_activation/manifest.json
A1_REPAIR_EXECUTABLE_HEAD=922a106bd32ce98a07d2280cf08a6a9f116a11a6
A1_REPAIR_EXECUTABLE_TREE=3712bbcf20e47f7cf1f92fc26ce238eed6e95fd8
A1_LIVE_EXECUTION_AUTHORIZED=false
A1_REPAIR_SCOPE=120S_BOUNDED_CONTAINER_SETTLE_WAIT_AFTER_ACTIVATION_AND_ROLLBACK_RESTART_ONLY
A1_PREFLIGHT_SETTLE_WAIT=false
```

### 3.4 Target host / runtime authority

```text
TARGET_HOST=PRODUCTION_T1_OPERATOR_BOUND_PRIVATE_LOCATOR
TARGET_ARCH=aarch64
PRIVATE_HOST_LOCATOR_AUTHORITY=OPERATOR_LOCAL_NOT_GITHUB
SSH_TRANSPORT=tools/n3w_t1_ssh_transport.py
SSH_TRANSPORT_BLOB=dec4c9159195e2008094d94fef3fc76c4b977e46
```

不得把 T1 私有 endpoint、known_hosts 本地路径或 host-key hash 写入 GitHub 文档/评论。

---

## 4. Current Live Baseline

该 baseline 来自 A1 _01 自动 rollback 后的 fresh read-only live classification，不是历史推断。

```text
MANAGER_STATE=running
MANAGER_IMAGE=local/greenhouse-manager:fresh-bf38e388497b
MANAGER_IMAGE_ID=sha256:e88a22b29b93b0db0d3b4f592cb0fd773169d1dc0f043219f14d5247ed859dff
MANAGER_USER=999:999
MANAGER_RESTART_COUNT=0
MANAGER_OTA_ENV_PRESENT=false
MANAGER_OTA_MOUNT_PRESENT=false
MANAGER_DOCKER_SOCKET_PRESENT=false
MANAGER_BLOCK_DEVICE_ACCESS_PRESENT=false

HOMEASSISTANT_STATE=running
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
HOMEASSISTANT_RESTART_COUNT=0

BROKER_STATE=running
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
BROKER_RESTART_COUNT=0
BROKER_CONTAINER_CONTINUITY=true

A1_HOST_UNIT=not-found/inactive
A1_SERVICES_DROPIN_PRESENT=false
A1_ACTIVATION_ENV_PRESENT=false
A1_APPROVED_MANIFEST_PRESENT=false
A1_RUNTIME_ROOT_PRESENT=false
A1_RUNTIME_SOCKET_PRESENT=false

MANAGER_V2_TRANSACTION_COMPONENT=manager
MANAGER_V2_TRANSACTION_STATUS=COMMITTED
MANAGER_LEGACY_TRANSACTION_STATUS=ABSENT
HA_USB_TRANSACTION_PRESENT=false
HA_PREPARE_STATE_PRESENT=false
USB_LIKE_DISK_COUNT=0

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

```text
CURRENT_LIVE_BASELINE_REQUIRES_FRESH_READONLY_REBIND_BEFORE_SUCCESSOR_LIVE_ACTIVATION=true
```

---

## 5. Proven Current Facts

```text
A0_LIVE_APPLY_RESULT=PASS
A0_AUTHORIZATION_CONSUMED=true
A0_REPLAY_ALLOWED=false

A1_01_AUTHORIZATION_CLAIMED=true
A1_01_ACTIVATION_INVOKED=true
A1_01_SECOND_ACTIVATION_INVOKED=false
A1_01_ORIGINAL_FIRST_FAILED_OPERATION=container_cardinality_invalid
A1_01_AUTOMATIC_ROLLBACK_INVOKED=true
A1_01_ORIGINAL_ROLLBACK_PASS=false
A1_01_ORIGINAL_RECOVERY_REQUIRED=true

READONLY_CLASSIFICATION=ROLLED_BACK_HEALTHY_FALSE_ROLLBACK_FAILURE
READONLY_RECOVERY_REQUIRED=false
T1_RECOVERY_MUTATION_REQUIRED=false

KF143_ROOT_CAUSE_PROVEN=true
KF143_SOURCE_REPAIR_HEAD=922a106bd32ce98a07d2280cf08a6a9f116a11a6
KF143_SOURCE_REPAIR_CI=25_SUCCESS_0_FAILURE_0_PENDING
A1_LIVE_EXECUTION_AUTHORIZED=false
```

`A1_01_ORIGINAL_RECOVERY_REQUIRED=true` 是原 executor 在 rollback validator 过早检查时产生的保守 closure；后续更高 authority 的 fresh read-only live evidence 已证明当前真实状态 `recovery_required=false`。

---

## 6. Current Root Cause / Blockers

### Blocker A — successor A1 authorization 尚未建立

```text
ROOT_CAUSE=NOT_A_DEFECT;INTENTIONAL_SESSION_STOP_BOUNDARY
PROVEN_BY=user_requested_handoff_before_new_authorization
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

当前没有 live recovery blocker。

### Blocker B — fresh live rebind 尚未在下一次 activation 前重新执行

```text
ROOT_CAUSE=NEW_LIVE_MUTATION_REQUIRES_FRESH_PRECHANGE_AUTHORITY
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

---

## 7. Closed / Forbidden Routes

```text
A1_01_REPLAY=CLOSED:authorization_claimed_and_activation_invoked
T1_MANUAL_RECOVERY_NOW=CLOSED:read_only_live_classification_proved_healthy_rollback
A1_FALSE_ROLLBACK_FAILURE_AS_REAL_RECOVERY=CLOSED:fresh_live_evidence_supersedes_executor_race
PRELIGHT_SETTLE_WAIT=CLOSED:repair_must_not_mask_preexisting_runtime_drift
GENERIC_V2_REGEX_BROADENING=CLOSED:A0_authorization_drift_was_locally_repaired
USB_PREPARE_OR_FORMAT_NOW=CLOSED:A1_scope_only
BOARD_ACCESS=CLOSED:not_required
```

不得仅因为新会话开始而重新进入这些路线。

---

## 8. Authorization Ledger

### A0 Manager successor

```text
AUTHORIZATION=N3W_T1_CORE_UPDATER_R7A_MANAGER_SUCCESSOR_A0_LIVE_APPLY_20261107_02
CLAIMED=true
CONSUMED=true
RESULT=PASS_EXECUTOR_FALSE_STOP_POSTCHECK_REPAIRED
REPLAY_PERMITTED=false
SUPERSEDED_BY=NOT_APPLICABLE
```

### A1 first live activation

```text
AUTHORIZATION=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261107_01
CLAIMED=true
CONSUMED=true
RESULT=STOP_CONTAINER_CARDINALITY_RACE_WITH_ACTUAL_HEALTHY_AUTOMATIC_ROLLBACK
REPLAY_PERMITTED=false
SUPERSEDED_BY=PROPOSED_SUCCESSOR_A1_AUTHORIZATION
```

### Proposed successor A1 authorization

```text
PROPOSED_AUTHORIZATION=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=false
READY_FOR_NEW_AUTHORIZATION=true
```

`READY_FOR_NEW_AUTHORIZATION=true` 不等于授权已批准。下一会话必须先向用户明确请求 exact successor authorization。

---

## 9. Rollback Authority

下一次 A1 live activation 仍是 live mutation gate。

```text
ROLLBACK_BASELINE=FRESH_LIVE_PRE_A1_STATE_MATCHING_SECTION_4
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=A1_EXECUTOR_PRIVATE_ROLLBACK_INVENTORY_PLUS_FRESH_PREFLIGHT
NORMAL_PATH_RESTART_ALLOWED=SERVICES_OWNER_ONCE
ROLLBACK_ONLY_RESTART_LIMIT=SERVICES_OWNER_ONCE
BROKER_RESTART_ALLOWED=false
MANAGER_IMAGE_ROLLBACK_ALLOWED=false
SECOND_ATTEMPT_ALLOWED=false
```

Rollback 顺序：

```text
stop/disable host OTA daemon
→ restore exact pre-A1 files from fresh hash-verified rollback inventory
→ systemctl daemon-reload
→ restart n3wfc4-services-activation.service once
→ bounded <=120s Manager/HA container convergence
→ verify exact Manager/HA/Broker runtime + Broker continuity
→ verify Manager OTA env/mount absent
→ verify USB=0 and HA-USB/PREPARE state absent
→ STOP
```

Rollback failure：

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
SECOND_ACTIVATION_FORBIDDEN=true
```

Container convergence timeout failure必须先做 read-only runtime classification；不得自动把短暂 cardinality 0 再解释为永久 recovery failure。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_SUCCESSOR_LIVE_AUTHORIZATION_BINDING_20261108_01
```

### 10.1 Purpose

在**不访问 T1、不执行 activation**的前提下，fresh rebind main/PR #799/PR #800、确认 repaired exact head 与 25/25 CI 未漂移，然后向用户请求并在获得明确批准后，把 distinct successor A1 one-shot authorization 绑定到 exact repaired source。该 gate 只建立下一次 live execution authority，不执行 live activation。

### 10.2 Frozen inputs

```text
MAIN_EXPECTED_AT_HANDOFF=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
PR799_HEAD_EXPECTED_AT_HANDOFF=462018cbf341f1b762a35f82a87a7c98e4a8b615
PR800_REPAIR_HEAD_EXPECTED_AT_HANDOFF=922a106bd32ce98a07d2280cf08a6a9f116a11a6
PR800_REPAIR_TREE_EXPECTED_AT_HANDOFF=3712bbcf20e47f7cf1f92fc26ce238eed6e95fd8
PR800_REPAIR_CI_AT_HANDOFF=25_SUCCESS_0_FAILURE_0_PENDING
A1_MANIFEST_LIVE_EXECUTION_AUTHORIZED=false

PROPOSED_AUTHORIZATION=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02
PROPOSED_CONFIRMATION=EXECUTE R7A HOST DAEMON COMPOSE A1 LIVE ACTIVATION: YES
```

### 10.3 Required proof / operations

```text
1. fresh read main, PR #799, PR #800 state/head/base; classify any drift.
2. verify PR #800 repair head/tree and exact-head 25/25 CI.
3. verify executor repair remains:
   - bounded 120s settle wait after activation restart;
   - bounded 120s settle wait after rollback restart;
   - no settle wait in preflight;
   - no USB/PREPARE/U2+ scope expansion.
4. verify manifest live_execution_authorized=false.
5. verify consumed A1 _01 remains non-replayable.
6. present exact proposed successor authorization to user.
7. STOP until explicit user approval of that exact ID.
8. only after explicit approval: create repository authorization-binding commit limited to manifest + matching regression test.
9. run exact authorized-head CI.
10. STOP before real T1 SSH/activation.
```

### 10.4 PASS

```text
SUCCESSOR_A1_AUTHORIZATION_BINDING=PASS
NEW_AUTHORIZATION_EXPLICITLY_GRANTED=true
AUTHORIZED_HEAD=<new exact head>
AUTHORIZED_CI=PASS
READY_FOR_A1_SUCCESSOR_LIVE_ACTIVATION=true
STOP_BEFORE_REAL_T1_ACTIVATION=true
```

### 10.5 FAIL

```text
SUCCESSOR_A1_AUTHORIZATION_BINDING=FAIL_<EXACT_CLASS>
READY_FOR_A1_SUCCESSOR_LIVE_ACTIVATION=false
STOP=true
```

Codex 不得自动进入 real T1 activation。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub/repository fresh read
- exact head/tree/blob verification
- exact-head CI read/retry for transient external CI failure
- source-only review
- after explicit user approval only: bounded authorization-binding repository commit
- PR #800 public-safe status/comment synchronization
```

### FORBIDDEN

```text
- any T1 SSH before successor authorization-binding gate closes PASS
- any T1/service/Docker/systemd mutation
- A1 _01 replay
- USB access/format/mount
- PREPARE intent
- CONFIRM_USB_ERASE
- U2+
- board/serial/flash/NVS/RF access
- merge / auto-merge
- publishing private T1 endpoint, local known_hosts path, host-key hash or private evidence path
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
REPOSITORY_MUTATION=ONLY_AFTER_EXPLICIT_SUCCESSOR_AUTHORIZATION
```

---

## 12. Codex DSL Execution Contract

本节是 self-contained execution protocol。

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required for the
successor-authorization-binding gate.

Mechanically compile this DSL into the minimum necessary GitHub/Git
commands using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not access T1.
Do not retry old A1 _01.
Do not enter real activation.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

A1_01_CONSUMED=true
A1_01_REPLAY_PERMITTED=false
SUCCESSOR_AUTHORIZATION_GRANTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

============================================================
1. FROZEN INPUTS
============================================================

repository=chrenguo-stack/HomeAssistant
main_at_handoff=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
pr799_at_handoff=462018cbf341f1b762a35f82a87a7c98e4a8b615
pr800_repair_head_at_handoff=922a106bd32ce98a07d2280cf08a6a9f116a11a6
pr800_repair_tree_at_handoff=3712bbcf20e47f7cf1f92fc26ce238eed6e95fd8
repair_ci_at_handoff=25/25_success

proposed_successor_authorization=
N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02

============================================================
2. HARD SCOPE
============================================================

ALLOW:
- fresh repository/PR/CI reads
- exact repair review
- public-safe PR comment
- after explicit approval only, manifest/test authorization-binding commit

FORBID:
- T1 SSH
- activation
- service restart
- Docker mutation
- USB/PREPARE/U2+
- board access
- merge
- replay A1_01

============================================================
3. FRESH REBIND
============================================================

Read current:
- main
- PR #799
- PR #800
- A1 executor
- A1 manifest
- focused A1 tests
- exact-head CI

If material source drift exists beyond docs-only authority movement:
STOP and return to high-level model.

============================================================
4. REPAIR AUTHORITY
============================================================

Prove:
- post-activation Manager+HA lookup uses bounded settle wait
- rollback Manager+HA lookup uses bounded settle wait
- preflight remains strict/immediate
- Broker continuity remains exact
- USB mutation/PREPARE/U2+ remain absent
- manifest live_execution_authorized=false before new approval

============================================================
5. SUCCESSOR AUTHORIZATION REQUEST
============================================================

Present exactly:
N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02

Do not infer approval from this handoff.
Wait for explicit user approval.

============================================================
6. AFTER EXPLICIT APPROVAL ONLY
============================================================

Create exact authorization-binding source commit:
- live_execution_authorized=true
- successor authorization exact ID
- one-shot stop boundary
- matching focused regression test update

No executor/runtime asset changes.

Run exact authorized-head CI.

============================================================
7. HARD STOP
============================================================

STOP before any real T1 SSH or activation.

Return structured closure.
```

---

## 13. Expected Closure

```text
=== R7A A1 SUCCESSOR AUTHORIZATION BINDING CLOSURE ===

GATE=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_SUCCESSOR_LIVE_AUTHORIZATION_BINDING_20261108_01

MAIN_REBOUND=
PR799_REBOUND=
PR800_REBOUND=

REPAIR_HEAD=
REPAIR_TREE=
REPAIR_CI=

OLD_AUTHORIZATION=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261107_01
OLD_AUTHORIZATION_CONSUMED=true
OLD_AUTHORIZATION_REPLAY_PERMITTED=false

SUCCESSOR_AUTHORIZATION=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02
SUCCESSOR_AUTHORIZATION_EXPLICITLY_GRANTED=
SUCCESSOR_AUTHORIZATION_BOUND=
AUTHORIZED_HEAD=
AUTHORIZED_TREE=
AUTHORIZED_CI=

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_SUCCESSOR_LIVE_ACTIVATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=false
```

授权 binding PASS 仅表示可以进入新的 real-T1 activation gate；仍需 fresh live preflight，并不得复用历史 rollback snapshot。

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
KF_ID=KF-143
DOMAIN=R7A_A1_HOST_DAEMON_COMPOSE_ACTIVATION
SYMPTOM=container_cardinality_invalid_after_activation_restart_and_again_during_rollback_validation
ROOT_CAUSE=TYPE_SIMPLE_SYSTEMD_RESTART_RETURNS_BEFORE_MANAGER_HA_CONTAINER_CONVERGENCE
FIX_OR_GUARD=bounded_120s_container_settle_wait_after_activation_and_rollback_restarts_only;strict_preflight_retained;read_only_classification_before_recovery_mutation
STATUS=OPEN
```

---

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_A1_ROLLBACK_HEALTHY_TO_SUCCESSOR_AUTHORIZATION_NEW_CHAT_HANDOFF_V1.0_20261108.md》。

同时读取 exact historical handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #799
- PR #800
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

本轮继续采用“高阶模型思考 + Codex 低阶模型执行”。
Codex 可将 exact DSL execution contract 机械编译为最低必要命令；
PREWRITTEN_EXECUTOR_REQUIRED=false。

当前只进入：
NEXT_ONE_GATE=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_SUCCESSOR_LIVE_AUTHORIZATION_BINDING_20261108_01

先 fresh rebind：
- main at handoff=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
- PR #799 at handoff=462018cbf341f1b762a35f82a87a7c98e4a8b615
- PR #800 repaired executable head at handoff=922a106bd32ce98a07d2280cf08a6a9f116a11a6
- repaired executable tree=3712bbcf20e47f7cf1f92fc26ce238eed6e95fd8
- repaired exact-head CI=25/25 SUCCESS

重要现场：
- A1 _01 authorization 已 consumed，禁止 replay；
- A1 _01 自动 rollback 后 fresh read-only classification=
  ROLLED_BACK_HEALTHY_FALSE_ROLLBACK_FAILURE；
- T1_RECOVERY_REQUIRED=false；
- 当前 Manager successor / HA / Broker 均 running；
- A1 host wiring 已撤销；
- USB=0，HA-USB/PREPARE state absent；
- KF-143 restart convergence race 已在 repaired head 修复并 25/25 CI PASS。

本会话没有建立新的 A1 authorization。

下一步 proposed successor authorization：
N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02

先完成 fresh rebind 和 repair review；
然后向我请求对上述 exact authorization 的明确授权。
在我明确授权前：
LIVE_MUTATION_DEFAULT=false
T1_ACCESS=false
BOARD_ACCESS_DEFAULT=false

不要自动重放 _01，不要自动进入 real T1 activation，不要进入 USB PREPARE/U2+，不要 merge。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=R7A_A1_01_ROLLED_BACK_HEALTHY_REPAIR_CLOSED_PASS
CURRENT_STOP_POINT=BEFORE_SUCCESSOR_A1_AUTHORIZATION

SOURCE_DEFECT_PROVEN=true:KF143_EXECUTOR_READINESS_RACE
SOURCE_REPAIR_HEAD=922a106bd32ce98a07d2280cf08a6a9f116a11a6
SOURCE_REPAIR_TREE=3712bbcf20e47f7cf1f92fc26ce238eed6e95fd8
SOURCE_REPAIR_CI=25_SUCCESS_0_FAILURE_0_PENDING

CURRENT_BLOCKER=SUCCESSOR_A1_AUTHORIZATION_NOT_YET_GRANTED

LIVE_SYSTEM_STATE=PRE_A1_BASELINE_RESTORED_AND_HEALTHY
T1_RECOVERY_REQUIRED=false

A1_01_AUTHORIZATION_CONSUMED=true
A1_01_REPLAY_ALLOWED=false

PROPOSED_SUCCESSOR_AUTHORIZATION=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02
PROPOSED_SUCCESSOR_AUTHORIZATION_GRANTED=false

NEXT_ONE_GATE=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_SUCCESSOR_LIVE_AUTHORIZATION_BINDING_20261108_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_STANDARD_VERSION=1.0
```

---

## 18. Handoff Compliance Audit

```text
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
```
