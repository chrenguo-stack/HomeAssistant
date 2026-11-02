# 温室环境监测系统（ESP32-C6）/ N3-W
# T1_Core_Stack Clean Reference / T1_B R0 Fresh Armbian
# 新会话交接文档 V1.1 — 2026-11-01

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.3
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文 supersedes:
> `docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_FRESH_ARMBIAN_NEW_CHAT_HANDOFF_V1.0_20261101.md`
>
> fresh repository/runtime evidence 与本文冲突时，以 fresh 直接证据为准并停止跨 Gate 执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=T1_CORE_STACK_DUAL_T1_CLEAN_REFERENCE_PREPARATION
CURRENT_STOP_POINT=WAITING_FOR_OPERATOR_T1_B_FRESH_ARMBIAN_ONLY
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_T1B_FRESH_ARMBIAN_READONLY_BASELINE_20261101_01

T1_A_ROLE=LEGACY_UPGRADE_AND_FAILURE_SPECIMEN
T1_A_WIPE=false
T1_A_MUTATION=false

T1_B_ROLE=CLEAN_REFERENCE_AND_CLEAN_UPGRADE_TARGET
T1_B_WIPE_AND_REINSTALL_ARMBIAN=true
T1_B_R0_MUTATION=false

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

新会话只对 T1_B 做 Fresh Armbian R0 只读基线。T1_A 保留原状，不参与 R0。

---

## 1. 本阶段关键架构修正

```text
T1_CORE_STACK=T1_Core_Stack
T1_CORE_STACK_COMPONENTS=greenhouse-manager,Home Assistant,Mosquitto Broker

UPGRADE_TOOL=T1_Core_Updater
UPGRADE_TOOL_CLI=t1-core-updater

CLEAN_REFERENCE_IS_NOT_UPGRADE=true
UPGRADE_REQUIRES_EXPLICIT_BASELINE_A_AND_TARGET_B=true
DEFAULT_UPGRADE_SCOPE=ONE_T1_CORE_STACK_COMPONENT
DEFAULT_FIRST_REAL_UPGRADE_TARGET=MANAGER
```

Clean T1_Core_Stack 用来找稳定不变量，不是为了“升级自己”。

真正升级验证在 Clean Reference 收敛后开始：

```text
MANAGER_A -> MANAGER_B
HOME_ASSISTANT_MUTATION=false
MOSQUITTO_MUTATION=false
HOST_PLATFORM_MUTATION=false
```

以后再分别设计 Home Assistant A -> B、Broker A -> B。

---

## 2. 双 T1 物理角色

### T1_A — Legacy / Dirty Upgrade Specimen

```text
T1_A_WIPE=false
T1_A_ROLE=LEGACY_UPGRADE_AND_FAILURE_SPECIMEN
T1_A_FRESH_RUNTIME_RECHECKED=false
```

已证明的保留价值：

- 真实经历过 successor-upgrade E03；
- 存在历史 BLOCKED transaction / recovery 证据；
- 第二次 successor retry 已成功 publish candidate deployment 后在 service_start 阶段失败；
- failure reason 为历史 recovery exemption 失效后 gate 出现
  `multiple_active_transactions`;
- 新 retry transaction 已 terminal BLOCKED / replay forbidden；
- 私有 maintenance 证据已另行归档。

不要假设 T1_A 仍然存在“首次注册 E03”业务 Bug。若未来要把它作为 Manager
A -> B 真实业务修复样本，必须先 fresh read-only 证明 T1_A 当前版本/数据确实可复现该问题。

### T1_B — Clean Reference

```text
T1_B_WIPE=true
T1_B_REINSTALL=OFFICIAL_ARMBIAN
T1_B_PRODUCT_DEPLOYMENT_BEFORE_R0=false
T1_B_DOCKER_INSTALL_BEFORE_R0=false
```

T1_B 承担：

```text
R0=Fresh Armbian
R0H=Minimum host runtime
R1=Clean T1_Core_Stack first-running reference
R2=Post-reboot reference
R3=Normal-runtime reference
A1=Stable-invariant classification
A2=Per-module upgrade architecture
U1=Clean upgrade validation
```

---

## 3. 两个不同语境的 E03

项目历史中存在两个不同语境的 E03，后续禁止混用。

### 3.1 Manager first-registration E03

```text
DOMAIN=MANAGER_PRODUCT_BUSINESS_LOGIC
SYMPTOM=stale ACTIVE registration / registration_busy
ROOT_CLASS=ACTIVE_TRANSACTION_CREATED_BEFORE_DURABLE_DEADLINE_OWNER
SOURCE_REPAIR=HISTORICAL_COMPLETE
CURRENT_T1_A_PRESENCE=UNPROVEN_FRESH
```

它属于 Manager 产品逻辑 Bug。

### 3.2 Successor-upgrade E03

```text
DOMAIN=T1_UPGRADE_MAINTENANCE_CONTROL
T1_A_REAL_EVIDENCE=true
```

已发生两类 live failure：

1. service-stop lifecycle：
   `failed/enabled/0/0` 实际表示 Manager/HA 已停止，但旧 executor 只认可
   `inactive/enabled/0/0`，导致 false BLOCKED。

2. retry gate conflict：
   candidate publish 后，历史 recovered BLOCKED transaction 的 exemption 失效；
   gate 同时看到历史 BLOCKED 与新 VERIFYING transaction，返回
   `multiple_active_transactions`；service_start 未执行成功，新 transaction terminal BLOCKED。

PR #745 对第二类旧架构问题已有 source repair，但当前保持 open/unmerged，仅作为 incident/source evidence，
等待新的 T1_Core_Updater 架构决定是否需要选择性吸收。

---

## 4. Frozen repository authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant

CANDIDATE_REF=test/n3w-r8-full-simulated-e2e-safety-20261028
PRE_HANDOFF_CANDIDATE_HEAD=9cbf011ee363a7115422f486743fd5299f0d0321
CANDIDATE_HEAD=FRESH_REBIND_REQUIRED:HANDOFF_COMMIT_ADVANCES_DOCS_ONLY

PR705=OPEN
PR745=OPEN_UNMERGED_ARCHITECTURE_HOLD
PR745_HEAD=a6691aedf13f9a6c77167c6a022ec5eb49ef0268
PR745_AUTO_MERGE=false
PR705_UPWARD_MERGE=false

MAIN=FRESH_REBIND_REQUIRED
```

Required public authorities:

```text
docs/development/N3W_PROJECT_WORKING_CONTEXT.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_AND_STABLE_INVARIANTS_DESIGN_20261031.md
docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_DEVELOPMENT_PLAN_20261101.md
```

---

## 5. Artifact/cache authority

The old 2026-10-15 large artifact is explicitly historical:

```text
HISTORICAL_LOCAL_ARTIFACT_ID=11954286988
HISTORICAL_LOCAL_ARTIFACT_ZIP_SHA256=047a40ed640bc1bfcbc8adb7007da2a4eea1f8abedffbc3cb2e2a4d9f6817928
HISTORICAL_LOCAL_ARTIFACT_REUSE_ALLOWED=false
```

Cache mechanism remains selected:

```text
MAC_EXACT_ARTIFACT_CACHE_MECHANISM_REUSE_ALLOWED=true
NEW_T1_CORE_STACK_EXACT_ARTIFACT=NOT_FROZEN
NEW_LARGE_ARTIFACT_POLICY=FRESH_FREEZE_THEN_DOWNLOAD_ONCE_VERIFY_CACHE_REUSE
```

R0 must not download or deploy any product artifact.

---

## 6. Pre-wipe evidence and T1_A preservation

```text
PREWIPE_PRIVATE_EVIDENCE_ARCHIVED=true
PREWIPE_PRIVATE_EVIDENCE_SHA256=711359c2b6a3522daac4ce9697a20b9876b71f202b44d6c79f65eda79f67025c
PUBLIC_REPOSITORY_CONTAINS_PRIVATE_ARCHIVE=false
T1_A_WIPE=false
```

The archive is backup evidence. It does not replace preservation of T1_A's physical legacy state.

---

## 7. Offline-install boundary

```text
T1_CORE_STACK_IMAGE_DEPLOYMENT_OFFLINE_CAPABLE=true
FRESH_ARMBIAN_END_TO_END_AIRGAPPED_INSTALL=false
```

Current three product images can be staged/loaded offline. Fresh Armbian may still need network
APT sources for Docker/Compose/host packages. Full air-gapped host installation remains later O1 work.

---

## 8. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_T1B_FRESH_ARMBIAN_READONLY_BASELINE_20261101_01
```

### Purpose

Read the actual T1_B immediately after official Armbian installation and before Docker/product mutation.

### Inputs

```text
INPUT_1=OPERATOR_PREPARED_T1_B_WITH_OFFICIAL_ARMBIAN_ONLY
INPUT_2=FRESH_GITHUB_REBIND
INPUT_3=CLEAN_REFERENCE_DESIGN_AND_DEVELOPMENT_PLAN
```

### Read-only observations

- OS release / architecture / kernel;
- storage/filesystem capacity;
- default route / network manager / time sync;
- Docker/Compose presence or absence;
- product containers/images/volumes/networks absence;
- product paths/units/listeners absence;
- unexpected residuals.

Do not collect or publish raw secret/identity values when a presence flag/hash is sufficient.

### PASS

```text
R0_PASS_IF=
T1_B_OFFICIAL_ARMBIAN_BASELINE_READABLE
AND_T1_CORE_STACK_NOT_DEPLOYED
AND_NO_R0_MUTATION
```

If Docker or product residuals unexpectedly exist, STOP and classify them. Do not clean them automatically in R0.

---

## 9. Hard allowed / forbidden scope

### ALLOWED

```text
- GitHub fresh read-only rebind
- T1_B read-only SSH inventory
- read-only package/service/listener/filesystem/container/image inspection
- public-safe evidence hashing
- GitHub documentation/archive of R0 result
```

### FORBIDDEN

```text
- any T1_A mutation
- T1_A cleanup/recovery/retry
- apt update/install
- Docker install
- docker load/pull/build/create/start/stop/rm
- T1_Core_Stack deployment
- product provisioning
- systemd mutation
- board/USB/serial/flash/NVS/RF access
- old artifact reuse
- consumed E03 authorization replay
- PR #745 merge
- PR #705 upward merge
- auto-enter R0H after R0
```

---

## 10. Execution contract

```text
EXECUTION_METHOD=mac-terminal-to-T1_B-ssh
R0_MUTATION=false
T1_A_MUTATION=false
BOARD_ACCESS=false
CI_POLL_MAX=3
AUTO_EXECUTE_NEXT_GATE=false
```

The next session should first fresh rebind GitHub, then provide one bounded complete read-only Mac
Terminal batch for T1_B.

---

## 11. Expected R0 closure

```text
=== N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_T1B_FRESH_ARMBIAN_READONLY_BASELINE_20261101_01 CLOSURE ===

TARGET=T1_B
AUTHORIZATION=NOT_REQUIRED:READONLY

R0_OS_RELEASE=
R0_ARCH=
R0_KERNEL=
R0_STORAGE_CLASS=
R0_DEFAULT_ROUTE_PRESENT=
R0_TIME_SYNC_STATE=
R0_DOCKER_PRESENT=
R0_COMPOSE_PRESENT=
R0_PRODUCT_CONTAINER_COUNT=
R0_PRODUCT_IMAGE_COUNT=
R0_PRODUCT_VOLUME_COUNT=
R0_PRODUCT_NETWORK_COUNT=
R0_PRODUCT_PATH_RESIDUAL_COUNT=
R0_PRODUCT_UNIT_RESIDUAL_COUNT=
R0_PRODUCT_LISTENER_RESIDUAL_COUNT=
R0_UNEXPECTED_RESIDUALS=

T1_A_MUTATION=false
T1_B_MUTATION=false
BOARD_ACCESS=false

R0_T1B_FRESH_ARMBIAN_BASELINE=PASS|FAIL
NEXT_ROUTE=R0H_HOST_RUNTIME_ESTABLISHMENT_DESIGN_OR_RESIDUAL_REVIEW
STOP=true

=== END ===
```

---

## 12. After R0

R0 PASS does not authorize installation.

```text
AFTER_R0_PASS_NEXT_STAGE=R0H_HOST_RUNTIME_ESTABLISHMENT
AUTO_EXECUTE_AFTER_PASS=false
NEW_T1_B_MUTATION_AUTHORIZATION_REQUIRED=true
```

Later phases:

```text
R0 -> R0H -> S0 -> S1 -> R1 -> R2 -> R3 -> A1 -> A2
-> U0 baseline A / target B
-> U1 clean Manager A->B on T1_B
-> U2 legacy/dirty validation on T1_A
-> O1 full air-gapped installation
```

---

## 13. New-chat start prompt

```text
阅读《N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_T1B_FRESH_ARMBIAN_NEW_CHAT_HANDOFF_V1.1_20261101.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_AND_STABLE_INVARIANTS_DESIGN_20261031.md
- docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_DEVELOPMENT_PLAN_20261101.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

物理角色已经冻结：
T1_A=保留，不清空，用作未来 Legacy/Dirty Upgrade Target；
T1_B=已清空并只安装官方 Armbian，用作 Clean Reference。

先 fresh rebind repository main、PR #705、PR #745 和上述 authority。

只进入：
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_T1B_FRESH_ARMBIAN_READONLY_BASELINE_20261101_01

本 Gate 只读取 T1_B。
不要安装 Docker/软件包，不要部署 T1_Core_Stack，不要操作 T1_A，不要访问板卡，
不要复用旧 artifact，不要重放任何 consumed authorization，不要合并 PR #745，
不要自动跨入 R0H。
```

---

## 14. Final frozen state

```text
CURRENT_STAGE=T1_CORE_STACK_DUAL_T1_CLEAN_REFERENCE_PREPARATION

T1_A_ROLE=LEGACY_UPGRADE_AND_FAILURE_SPECIMEN
T1_A_WIPE=false

T1_B_ROLE=CLEAN_REFERENCE_AND_CLEAN_UPGRADE_TARGET
T1_B_EXPECTED_NEXT_STATE=OFFICIAL_ARMBIAN_ONLY

UPGRADE_TOOL=T1_Core_Updater

CURRENT_BLOCKER=NONE
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_T1B_FRESH_ARMBIAN_READONLY_BASELINE_20261101_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.3
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 15. Handoff compliance audit

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.3
PROJECT_WORKING_CONTEXT_REFERENCED=PASS
DUAL_T1_ROLES_EXPLICIT=PASS
T1_A_PRESERVATION_EXPLICIT=PASS
T1_B_R0_TARGET_EXPLICIT=PASS
UPGRADE_TOOL_NAMED=PASS
CLEAN_REFERENCE_AND_UPGRADE_VALIDATION_SEPARATED=PASS
TWO_E03_CONTEXTS_SEPARATED=PASS
OLD_ARTIFACT_REUSE_FORBIDDEN=PASS
NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
AUTHORIZATION_REPLAY_GUARD=PASS
PRIVATE_EVIDENCE_BOUNDARY=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
TEAM_SHARE_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true
```
