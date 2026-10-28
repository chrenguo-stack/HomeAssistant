# 温室环境监测系统（ESP32-C6）/ N3-W
# R10 T1 candidate R2 artifact freeze → pre-live readonly rebind
# 新会话交接文档 V1.0 — 2026-10-28

```text
HANDOFF_STANDARD_VERSION=1.0
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文必须符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`。  
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先停止执行、完成 rebind。

---

## 0. 会话切换结论

当前对话已经完成 R1 exact artifact freeze、Mac 本地验证、T1 staging、首次 live executor preclaim、安全 false-STOP 定位，以及 R2 source repair + exact CI/artifact closure。

现在切换会话是合理停止点，因为：

- R1 live authorization 没有被 executor claim/consume；
- R1 没有进入服务停止、数据库/F4/runtime mutation；
- R1 false-STOP 根因已经 source-repaired；
- PR #718 exact head CI 全部 SUCCESS；
- R2 exact artifact 已生成并完成 GitHub redownload verify；
- R2 artifact 尚未在 Mac 本地重新下载/验证；
- R2 artifact 尚未传入 T1；
- R2 live authorization 尚未重新绑定/授予。

```text
CURRENT_STAGE=R10_T1_CANDIDATE_R2_PRELIVE
CURRENT_STOP_POINT=R2 exact artifact GitHub freeze PASS; Mac local verify and fresh T1 readonly rebind not yet executed
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_ARTIFACT_LOCAL_VERIFY_AND_PRELIVE_READONLY_REBIND_20261028_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘 R1/R2 全部历史，而是从 `NEXT_ONE_GATE` 开始。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护产品路线与架构边界；
- fresh rebind repository / PR / artifact / live runtime authority；
- 设计 gate、scope、authorization、rollback；
- 根据 closure 做 PASS / FAIL / STOP 分类；
- 区分 source/runtime/infrastructure/CI/physical-harness defect；
- 防止 acceptance/tooling 复杂度变成第二套产品架构；
- 不把历史 R1 artifact / authorization 静默升级为 R2 authority。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- 运行必要的 Git/Docker/SSH/Compose/shell/test 命令；
- 使用已安装工具完成最低必要解析与 evidence capture；
- mutation 只能发生在明确授权边界内；
- 第一处 substantive failure 后 fail-closed STOP；
- 返回结构化 closure。

Codex 不得：

- 扩大 scope；
- 自行修复；
- 删除 R1 staging；
- 重放 R1 live authorization；
- 自动进入 R2 live mutation；
- 访问 board/USB/serial/Flash/NVS/RF。

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

本 handoff 的 NEXT_ONE_GATE 是只读/rebind gate；不要求新的预写 executor。

### 1.4 标准交互循环

```text
高阶模型：fresh rebind / gate / authority / authorization
        ↓
用户：仅在需要 mutation 时批准 exact authorization
        ↓
Codex：DSL compile → exact execution → structured closure
        ↓
高阶模型：复核 closure / 决定下一 gate
```

---

## 2. Product North Star

当前产品路线：

```text
N3-W 普通农户可用产品
→ T1 本地主机长期运行
→ ESP32-C6 节点上电即用
→ 首次配网后由用户显式触发 T1 搜索/选择
→ first-registration durable transaction
→ pairing 端口按需打开/关闭
→ MQTT/Home Assistant 连续运行
→ 完全离线也可使用
```

当前 R10 目标：

```text
先把真实 T1 从 predecessor production software
安全升级到支持 scan-triggered first-registration 的 e299 target capability，
再恢复 R10 T1+board 物理验收。
```

最终阶段目标：

```text
LCD QR
→ 手机页面
→ 显式搜索
→ 显式选择真实 T1
→ durable first-registration attempt
→ 47112 临时打开
→ Setup Secret / TLS provision
→ durable COMMIT
→ node provisioned
→ LCD 成功
→ 47112 关闭
→ MQTT/Manager continuity
```

当前不得进入：

```text
- ESP32-C6 board write / NVS mutation
- T1 OS/kernel/bootloader update
- 2.5 GiB fresh-install package 作为 routine upgrade
- 动态 roaming / 主动漫游
- Home Assistant/Broker image upgrade
- R1 artifact 再执行
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e
MAIN_TREE=3064ab74ac96bbce44a0bf880ab53c7afc5bc134

PR718=https://github.com/chrenguo-stack/HomeAssistant/pull/718
R2_SOURCE_HEAD=4a8c2a62be74ec5c9740d37946e770d9464b6cb3
R2_SOURCE_TREE=6d342dea1ee6d8fa5014b60e0879988888dc0227
R2_BRANCH=fix/n3w-r10-t1-candidate-upgrade-preclaim-r2-20261028
PR718_STATE=open/draft/mergeable
```

PR #715/#716/#717 是 R1 package/docs/preexecution 历史 authority；其 R1 artifact 值不得继续作为 R2 live authority。

### 3.2 R2 candidate / artifact / image

```text
R2_WORKFLOW_RUN_ID=40641242797
R2_PACKAGE_CI=SUCCESS
R2_REDOWLOAD_VERIFY=PASS

ARTIFACT_ID=12795906971
ARTIFACT_NAME=n3w-r10-t1-upgrade-4a8c2a62be74
ARTIFACT_SIZE_BYTES=61298136
ARTIFACT_DIGEST=sha256:d5e40fe0295f8bd6844cd50624139dbc2b31082f4dbcf93052924afa7586c0a3
ARTIFACT_EXPIRES_AT=2026-11-27T06:02:43Z

MANIFEST_SHA256=1794a8696663dfaf49a1454cfcf7865ba90cbd8444a508750622d315b5fea64a

PREDECESSOR_SOURCE=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
TARGET_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44

PREDECESSOR_MANAGER_IMAGE=local/greenhouse-manager:fresh-03dab2bd04e7
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-e299c937a7b8

MANAGER_TAR_SHA256=2ba09634ceeb0b88e8a01ddf12325a45ea4315a4e1b966e1fe83ed62d2234a71
MANAGER_TAR_SIZE_BYTES=61196800

MANAGER_IMAGE_ID=sha256:94db48b902c39f1ffa61cd9b5e91e683b18be4eefdd07d4a95a7dbfb5495ceef
MANAGER_IMAGE_SIZE_BYTES=200818585
MANAGER_PLATFORM=linux/arm64

BASE_ARM64_DIGEST=sha256:8f867a1f16776618234a2d0ef41fbb991d0bd0b142c8a95bc37456d8e47104cf
BASE_IMAGE_ID=sha256:04f230affa8877281a7d7351193a85323e4263c0df2d3c8d93033ed46a8d8e00

PYTHON_DISTRIBUTION_COUNT=17
PYTHON_DISTRIBUTIONS_SHA256=c29bbdd603c74aa7c36f33a32f22d86e5dacb6c34ec2266fc55eb8660cac0ae6

R2_EXECUTOR_SHA256=395421920c54666fd5a404d112a67eec8cc931d24af3bd53e61758238ffd77ff
R2_EXECUTOR_SIZE_BYTES=65733
```

重要：

```text
HISTORICAL_E299_MANAGER_BYTE_CONTINUITY_CLAIMED=false
FUTURE_REBUILD_BYTE_IDENTITY_CLAIMED=false
```

R2 authority 是实际 artifact，不是“同 e299 source 未来重建一定同字节”。

### 3.3 R1 superseded artifact

```text
R1_ARTIFACT_ID=12792592683
R1_ARTIFACT_DIGEST=sha256:e4f236387c67a2ac88623bb2166201fcc44589dc99504aded4b9df688ad5dc9c
R1_MANIFEST_SHA256=4c9eca65c535cc7c5fd1f48891844f381338719d2d422d0f5464cc8f7a660664
R1_EXECUTOR_SHA256=214fef4a1feb6c446aad25847d7615a6f48cca054f6d09ce8b5c7b3825d5d1a4

R1_ARTIFACT_AUTHORITY=SUPERSEDED_DO_NOT_EXECUTE
```

### 3.4 Successor / deployment material

R2 live file target集合仍为：

```text
/etc/n3wfc4/docker-compose.yml
/etc/systemd/system/n3wfc4-services-activation.service
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
/etc/systemd/system/n3wfc4-registration-ingress-guard.service
/usr/local/sbin/n3w-registration-ingress-guard
/usr/local/sbin/n3w-trusted-product-lan-authority
```

不修改：

```text
/opt/HomeAssistant
/usr/local/sbin/n3w-t1-f4-activation
Broker image
Home Assistant image
```

### 3.5 Target host / runtime authority

```text
TARGET_HOST=root@armbian
TARGET_ARCH=arm64

EXPECTED_BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
EXPECTED_HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

BROKER_DYNSEC_PATH=/var/lib/n3wfc4-broker/dynamic-security.json
F4_TRANSACTION_PATH=/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json
R10_TRANSACTION_PATH=/var/lib/n3w-t1-provisioning/R10_CANDIDATE_UPGRADE_TRANSACTION.json

R1_STAGING_PATH=/var/lib/n3w-r10-candidate-upgrade-staging/94bcf1823774aa3e
R2_STAGING_PATH=NOT_CREATED
```

---

## 4. Current Live Baseline

以下是切换前最近 direct evidence。

### 4.1 R1 staging

R1 exact package 已经写入 T1 staging，但只属于 bounded filesystem staging，不是 production runtime mutation：

```text
R1_T1_STAGE_VERIFY=PASS
R1_T1_STAGE_FILE_COUNT=10
R1_T1_STAGE_MANIFEST_SHA256=4c9eca65c535cc7c5fd1f48891844f381338719d2d422d0f5464cc8f7a660664
ROOT_FREE_BYTES_AFTER_R1_STAGING=6182494208

BOUNDED_STAGING_FILESYSTEM_WRITE=true
LIVE_RUNTIME_MUTATION=false
```

R1 staging 当前应保留，直到 R2 live gate 明确授权清理/替换；新会话不得先删。

### 4.2 R1 first live invocation

实际执行结果：

```json
{"authorization_consumed":false,"board_access":false,"reason":"target_manager_image_preexisting","schema":"gh.n3w.r10-t1-candidate-upgrade-execution/1","status":"STOP"}
```

该 STOP 发生在 fresh preclaim，早于 one-shot claim。

因此：

```text
R10_UPGRADE_TRANSACTION_CREATED=false
UPGRADE_AUTHORIZATION_CONSUMED=false
SERVICES_STOPPED_BY_R1=false
TARGET_MANAGER_LOADED_BY_R1=false
DATABASE_MUTATED_BY_R1=false
F4_MUTATED_BY_R1=false
BOARD_ACCESS_BY_R1=false
```

### 4.3 Immediate read-only counter-evidence

R1 STOP 后立即只读执行：

```text
docker image inspect local/greenhouse-manager:fresh-e299c937a7b8
```

结果：

```text
No such image: local/greenhouse-manager:fresh-e299c937a7b8
```

因此：

```text
R1_TARGET_IMAGE_PREEXISTING=FALSE
R1_STOP_CLASS=FALSE_STOP
```

### 4.4 Last proven production runtime before false-STOP

R1 preclaim 在 target-image check 之前已经通过 predecessor live checks，因此最近 direct evidence 支持：

```text
MANAGER_IMAGE=local/greenhouse-manager:fresh-03dab2bd04e7
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

SERVICES_ACTIVATION=active
BROKER_ACTIVATION=active
BROKER_INGRESS_GUARD=active/loaded

47110_TCP=0
47111_UDP=0
47112_TCP=0

REGISTRATION_GUARD_PREDECESSOR=absent
REGISTRATION_TLS_PREDECESSOR=absent
TRUSTED_LAN_RUNTIME_PREDECESSOR=absent
```

R1 preclaim 因 false-STOP 在后续 database/F4 checks 之前终止，因此以下状态必须在 NEXT_ONE_GATE fresh readonly rebind：

```text
DATABASE_INTEGRITY_REQUIRES_FRESH_READONLY_REBIND=true
CURRENT_REGISTRATION_COUNT_REQUIRES_FRESH_READONLY_REBIND=true
FIRST_REGISTRATION_TABLE_REQUIRES_FRESH_READONLY_REBIND=true
PAIRING_WINDOW_REQUIRES_FRESH_READONLY_REBIND=true
F4_SERVICES_ELIGIBILITY_REQUIRES_FRESH_READONLY_REBIND=true
BROKER_DYNSEC_SHA_REQUIRES_FRESH_READONLY_REBIND=true
ROOT_FREE_BYTES_REQUIRES_FRESH_READONLY_REBIND=true
```

### 4.5 Board state

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false

R10_BOARD_WRITE_AUTHORIZATION_CONSUMED=false
```

---

## 5. Proven Current Facts

```text
FACT_R1_LOCAL_ARTIFACT_VERIFY=PASS
FACT_R1_T1_STAGE_VERIFY=PASS
FACT_R1_LIVE_EXECUTOR_STOPPED_BEFORE_CLAIM=true
FACT_R1_AUTHORIZATION_CONSUMED=false
FACT_R1_TARGET_IMAGE_WAS_ACTUALLY_ABSENT=true
FACT_R1_STOP_WAS_EXECUTOR_FALSE_STOP=true

FACT_R2_SOURCE_REPAIR_HEAD=4a8c2a62be74ec5c9740d37946e770d9464b6cb3
FACT_R2_PR718_ALL_CURRENT_HEAD_CI=SUCCESS
FACT_R2_PACKAGE_BUILD=SUCCESS
FACT_R2_REDOWLOAD_VERIFY=PASS
FACT_R2_ARTIFACT_ID=12795906971
FACT_R2_ARTIFACT_EXPIRED=false

FACT_R2_MAC_LOCAL_VERIFY_NOT_EXECUTED=true
FACT_R2_T1_STAGING_NOT_EXECUTED=true
FACT_R2_LIVE_AUTHORIZATION_NOT_GRANTED=true

FACT_LIVE_RUNTIME_MUTATION_FROM_R1=false
FACT_BOARD_ACCESS=false
```

推断：

```text
INFERENCE_CURRENT_PRODUCTION_RUNTIME_STILL_PREDECESSOR=true
```

该 inference 很强，因为 R1 在 preclaim 前停止，且后续仅做 read-only inspect；但新会话仍必须 fresh readonly rebind，不把 inference 当 current live fact。

---

## 6. Current Root Cause / Blockers

### Blocker A — R2 artifact 尚未完成 Mac 本地绑定与 fresh T1 pre-live rebind

```text
ROOT_CAUSE=R2 material is new authority and has not yet been locally verified / rebound against current T1
PROVEN_BY=R2 artifact differs from R1 in package head, artifact ID/digest, manifest, executor, Manager tar/image/base identity
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

### Blocker B — R2 live authorization 尚未重新绑定

```text
R1_AUTHORIZATION_MATERIAL_SUPERSEDED=true
R2_NEW_AUTHORIZATION_REQUIRED=true
R2_AUTHORIZATION_GRANTED=false
```

```text
CURRENT_BLOCKER_COUNT=2
```

R1 preclaim false-STOP source defect本身已经被 PR #718 修复并由 exact-head CI 关闭，不再是 current source blocker。

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，下一会话不得重新进入：

```text
R1_ARTIFACT_12792592683=CLOSED:SUPERSEDED_DO_NOT_EXECUTE
R1_EXECUTOR_214fef4a...=CLOSED:FALSE_STOP_PATH_PROVEN
R1_LIVE_AUTHORIZATION_REPLAY=CLOSED:R2_MATERIAL_CHANGED

DELETE_TARGET_IMAGE_TO_FIX_R1_STOP=CLOSED:TARGET_IMAGE_WAS_ABSENT
RETAG_OR_FORCE_LOAD_BEFORE_PRECLAIM=CLOSED:MASKS_PRECLAIM_AUTHORITY

MUTATE_OPT_HOMEASSISTANT=CLOSED:HISTORICAL_PROVISIONING_TREE_MUST_REMAIN_IMMUTABLE
REPLACE_F4_LAUNCHER=CLOSED:NOT_REQUIRED_FOR_BOUNDED_R10_HOST_UPGRADE

HOMEASSISTANT_IMAGE_UPGRADE=CLOSED:OUT_OF_SCOPE
BROKER_IMAGE_UPGRADE=CLOSED:OUT_OF_SCOPE
BROKER_RESTART_AS_NORMAL_UPGRADE_STEP=CLOSED:CONTINUITY_REQUIRED

COMPOSE_OVERRIDE=CLOSED:KF-129_GUARD
FORCE_RECREATE=CLOSED:KF-129_GUARD

BOARD_WRITE_BEFORE_T1_UPGRADE_PASS=CLOSED:HOST_UPGRADE_PRECEDES_BOARD_R10_RESUME
NVS_ERASE_AS_WORKAROUND=CLOSED:FORBIDDEN
```

---

## 8. Authorization Ledger

### 8.1 R1 T1 live upgrade authorization

```text
AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01
GRANTED=true
CLAIMED=false
CONSUMED=false
RESULT=R1_PRECLAIM_FALSE_STOP
REPLAY_PERMITTED=false
SUPERSEDED_BY=N3W_R10_T1_CANDIDATE_UPGRADE_R2_20261028_01
```

虽然 R1 authorization 没有 consumed，但 R2 artifact/runtime authority 已变化，因此禁止把 R1 grant 静默重放到 R2。

### 8.2 Proposed R2 T1 live upgrade authorization

```text
PROPOSED_AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_R2_20261028_01
GRANTED=false
CLAIMED=false
CONSUMED=false
RESULT=NOT_STARTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=
```

只有 NEXT_ONE_GATE PASS 后，才可以请求用户显式批准该 R2 authorization。

### 8.3 R10 board-write authorization

```text
AUTHORIZATION=R10_BOARD_WRITE_AUTHORIZATION
GRANTED=true
CLAIMED=false
CONSUMED=false
RESULT=UNUSED_HOST_UPGRADE_PRECEDES_BOARD_GATE
REPLAY_PERMITTED=false_in_current_host_upgrade_route
SUPERSEDED_BY=
```

该授权与 T1 host upgrade 分离；只有 host upgrade PASS + fresh board preflight 后才重新 rebind。

---

## 9. Rollback Authority

NEXT_ONE_GATE 不做 T1 mutation，只允许：

- Mac 本地新目录下载/解压 R2 artifact；
- GitHub read-only rebind；
- T1 read-only SSH/Docker/systemd/database/F4/status检查。

因此：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_PRELIVE_REBIND_GATE
LIVE_RUNTIME_MUTATION=false
T1_PRODUCT_STATE_MUTATION=false
BOUNDED_MAC_FILESYSTEM_WRITE=true
```

R1 staging 不在 NEXT_ONE_GATE 清理范围。

后续 R2 live gate 才需要 fresh rollback snapshot，不能复用 R1 历史 snapshot（R1 实际未创建 live rollback workspace）。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_ARTIFACT_LOCAL_VERIFY_AND_PRELIVE_READONLY_REBIND_20261028_01
```

### 10.1 Purpose

用新的 R2 exact artifact 完成 Mac 本地 byte binding，并 fresh rebind 当前 T1 predecessor runtime，证明 R1 false-STOP 后现场仍满足 R2 live upgrade 的授权前置条件；本 gate 不删除 R1 staging、不传 R2 package 到 T1、不 claim/live mutate。

### 10.2 Frozen inputs

```text
R2_SOURCE_HEAD=4a8c2a62be74ec5c9740d37946e770d9464b6cb3
R2_WORKFLOW_RUN_ID=40641242797

R2_ARTIFACT_ID=12795906971
R2_ARTIFACT_NAME=n3w-r10-t1-upgrade-4a8c2a62be74
R2_ARTIFACT_SIZE_BYTES=61298136
R2_ARTIFACT_DIGEST=sha256:d5e40fe0295f8bd6844cd50624139dbc2b31082f4dbcf93052924afa7586c0a3

R2_MANIFEST_SHA256=1794a8696663dfaf49a1454cfcf7865ba90cbd8444a508750622d315b5fea64a
R2_MANAGER_TAR_SHA256=2ba09634ceeb0b88e8a01ddf12325a45ea4315a4e1b966e1fe83ed62d2234a71
R2_MANAGER_TAR_SIZE_BYTES=61196800
R2_MANAGER_IMAGE_ID=sha256:94db48b902c39f1ffa61cd9b5e91e683b18be4eefdd07d4a95a7dbfb5495ceef
R2_EXECUTOR_SHA256=395421920c54666fd5a404d112a67eec8cc931d24af3bd53e61758238ffd77ff
R2_EXECUTOR_SIZE_BYTES=65733
R2_DISTRIBUTIONS_SHA256=c29bbdd603c74aa7c36f33a32f22d86e5dacb6c34ec2266fc55eb8660cac0ae6

R1_STAGING_PATH=/var/lib/n3w-r10-candidate-upgrade-staging/94bcf1823774aa3e
TARGET_HOST=root@armbian
```

### 10.3 Required proof / operations

```text
1. fresh rebind main + PR #718 exact head + exact-head CI.
2. fresh rebind artifact ID/digest/expiry from GitHub.
3. create a NEW Mac-only R2 directory; do not overwrite R1 local cache.
4. download artifact ID 12795906971.
5. verify outer artifact ZIP digest.
6. unzip to private local directory.
7. verify:
   - file count = 10
   - manifest SHA
   - Manager tar SHA/size
   - executor SHA/size
   - distribution inventory SHA/count
   - package_head = R2_SOURCE_HEAD
   - Manager image ID/base digest
   - policy: no HA/Broker image, no secrets, no T1 mutation.
8. T1 readonly rebind:
   - R1 staging still exists and R1 manifest is historical R1 binding;
   - R10 transaction absent;
   - R10 live workspace absent;
   - R2 target image exact tag absent;
   - running Manager predecessor image exact;
   - Broker/HA exact expected images;
   - services activation active;
   - Broker activation/ingress guard active;
   - 47110/47111/47112 all zero;
   - registration unit/TLS/trusted runtime absent;
   - pairing window CLOSED;
   - DB integrity PASS;
   - current registration count = 1;
   - first_registration table absent;
   - F4 services eligibility PASS;
   - Broker DynSec regular/readable; capture SHA only;
   - root free bytes measured.
9. no cleanup, no docker load, no service stop/start.
10. structured closure and STOP.
```

### 10.4 PASS

```text
R2_ARTIFACT_LOCAL_VERIFY=PASS
R2_PRELIVE_READONLY_REBIND=PASS
READY_FOR_R2_LIVE_AUTHORIZATION=true
T1_PRODUCT_STATE_MUTATION=false
STOP=true
```

### 10.5 FAIL

```text
R2_PRELIVE_GATE=FAIL_<EXACT_CLASS>
READY_FOR_R2_LIVE_AUTHORIZATION=false
AUTO_REPAIR=false
AUTO_RETRY=false
STOP=true
```

Codex 不得自动删除 R1 staging、请求/claim R2 authorization 或进入 live upgrade。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub read-only PR/commit/CI/artifact rebind
- Mac local R2 artifact download into a fresh private directory
- Mac local unzip/hash/manifest parsing
- T1 SSH read-only commands
- docker inspect / image ls / ps
- systemctl is-active/is-enabled/show
- ss listener inspection
- read-only SQLite integrity/schema/count queries
- F4 eligibility read-only invocation
- hash/read metadata for R1 staging and Broker DynSec
- disk free-space read
- structured closure
```

### FORBIDDEN

```text
- delete/overwrite R1 Mac cache
- delete/overwrite R1 T1 staging
- copy R2 artifact to T1
- docker load / pull / tag / rmi
- service stop/start/restart/reload
- daemon-reload
- write registration TLS
- install/replace Compose/systemd/dispatcher/tools
- iptables mutation
- Manager DB/state mutation
- F4 transaction mutation
- create R10 upgrade transaction
- claim R2 live authorization
- board/USB/serial/Flash/NVS/RF access
- merge PRs
```

```text
LIVE_RUNTIME_MUTATION=false
T1_PRODUCT_STATE_MUTATION=false
BOUNDED_MAC_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=$HOME/N3W_R10_T1_CANDIDATE_R2_PRELIVE_20261028_01
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required for this gate.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry unless explicitly permitted.
Do not enter the next gate.
```

### DSL

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

EXECUTION_ID=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_ARTIFACT_LOCAL_VERIFY_AND_PRELIVE_READONLY_REBIND_20261028_01

LIVE_RUNTIME_MUTATION=false
T1_PRODUCT_STATE_MUTATION=false
BOARD_ACCESS=false

R1_AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01
R1_AUTHORIZATION_CLAIMED=false
R1_AUTHORIZATION_CONSUMED=false
R1_AUTHORIZATION_REPLAY_PERMITTED=false

R2_PROPOSED_AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_R2_20261028_01
R2_AUTHORIZATION_GRANTED=false
R2_AUTHORIZATION_CLAIMED=false
R2_AUTHORIZATION_CONSUMED=false

============================================================
1. FROZEN INPUTS
============================================================

repository=chrenguo-stack/HomeAssistant
main_expected=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e

pr=718
r2_head=4a8c2a62be74ec5c9740d37946e770d9464b6cb3
workflow_run=40641242797

artifact_id=12795906971
artifact_name=n3w-r10-t1-upgrade-4a8c2a62be74
artifact_size=61298136
artifact_digest=sha256:d5e40fe0295f8bd6844cd50624139dbc2b31082f4dbcf93052924afa7586c0a3

manifest_sha256=1794a8696663dfaf49a1454cfcf7865ba90cbd8444a508750622d315b5fea64a
manager_tar_sha256=2ba09634ceeb0b88e8a01ddf12325a45ea4315a4e1b966e1fe83ed62d2234a71
manager_tar_size=61196800
manager_image_id=sha256:94db48b902c39f1ffa61cd9b5e91e683b18be4eefdd07d4a95a7dbfb5495ceef
executor_sha256=395421920c54666fd5a404d112a67eec8cc931d24af3bd53e61758238ffd77ff
executor_size=65733
distribution_sha256=c29bbdd603c74aa7c36f33a32f22d86e5dacb6c34ec2266fc55eb8660cac0ae6

target_host=root@armbian
r1_stage=/var/lib/n3w-r10-candidate-upgrade-staging/94bcf1823774aa3e

============================================================
2. HARD SCOPE
============================================================

ALLOWED:
- repository/PR/CI/artifact read
- Mac fresh-directory artifact download and verify
- T1 read-only runtime/db/F4/status/hash evidence

FORBIDDEN:
- any T1 write
- delete R1 staging
- stage R2
- docker load/pull/tag/rmi
- service mutation
- DB/F4/firewall/systemd mutation
- board access
- merge

============================================================
3. REPOSITORY / ARTIFACT REBIND
============================================================

Prove:
- main exact or STOP_SOURCE_DRIFT
- PR718 head exact or STOP_PR_DRIFT
- all current-head required CI SUCCESS or STOP_CI_NOT_CLOSED
- artifact exists, unexpired, ID/name/size/digest exact or STOP_ARTIFACT_DRIFT

============================================================
4. MAC R2 LOCAL VERIFY
============================================================

Create exactly:
$HOME/N3W_R10_T1_CANDIDATE_R2_PRELIVE_20261028_01

Require path absent before create.

Download artifact ID 12795906971.

Verify:
- outer zip digest exact
- zip size exact
- unzip file count = 10
- manifest SHA exact
- manager tar SHA/size exact
- executor SHA/size exact
- distribution inventory SHA exact
- manifest schema/package_head/source/image/base/policy exact

If mismatch:
FAIL_LOCAL_ARTIFACT_BINDING
STOP

============================================================
5. T1 READONLY PRELIVE REBIND
============================================================

No writes.

Prove R1 staging:
- path exists
- no symlink
- manifest = historical R1 manifest
- file count = 10
Do not delete it.

Prove no R10 mutation residue:
- R10_CANDIDATE_UPGRADE_TRANSACTION.json absent
- /var/lib/n3w-r10-candidate-upgrade absent

Prove target R2 tag absent using exact-reference image listing.
Do not use the R1 buggy inspect/stdout heuristic.

Prove runtime:
- Manager running exact predecessor tag
- Broker running exact expected tag
- Home Assistant running exact expected tag
- services activation active
- broker activation active
- broker ingress guard active/loaded
- 47110/tcp = 0
- 47111/udp = 0
- 47112/tcp = 0
- registration unit/TLS/trusted runtime absent
- pairing window CLOSED
- DB integrity ok
- current active registration count = 1
- first_registration_attempts absent
- F4 eligibility --phase services PASS
- Broker DynSec regular/readable; hash only
- root free bytes captured

Any mismatch:
FAIL_PRELIVE_<CLASS>
STOP

============================================================
6. PASS / HARD STOP
============================================================

If all pass:

R2_ARTIFACT_LOCAL_VERIFY=PASS
R2_PRELIVE_READONLY_REBIND=PASS
READY_FOR_R2_LIVE_AUTHORIZATION=true

Do not request authorization inside Codex.
Do not stage R2.
Do not clean R1 stage.
Do not mutate runtime.
Do not enter live upgrade.

STOP.
```

---

## 13. Expected Closure

```text
=== N3W R10 T1 CANDIDATE R2 PRELIVE CLOSURE ===

EXECUTION_ID=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_ARTIFACT_LOCAL_VERIFY_AND_PRELIVE_READONLY_REBIND_20261028_01

R1_AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01
R1_AUTHORIZATION_CLAIMED=false
R1_AUTHORIZATION_CONSUMED=false
R1_AUTHORIZATION_REPLAY_PERMITTED=false

R2_PROPOSED_AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_R2_20261028_01
R2_AUTHORIZATION_GRANTED=false
R2_AUTHORIZATION_CLAIMED=false
R2_AUTHORIZATION_CONSUMED=false

REPOSITORY_REBIND=
PR718_HEAD_REBIND=
R2_CI_REBIND=
R2_ARTIFACT_METADATA_REBIND=

R2_ARTIFACT_LOCAL_VERIFY=
R2_LOCAL_FILE_COUNT=
R2_MANIFEST_SHA256=
R2_MANAGER_TAR_SHA256=
R2_EXECUTOR_SHA256=

R1_STAGE_PRESENT=
R1_STAGE_HISTORICAL_BINDING=
R10_TRANSACTION_ABSENT=
R10_WORKSPACE_ABSENT=

TARGET_MANAGER_IMAGE_ABSENT=
RUNNING_MANAGER_PREDECESSOR=
BROKER_RUNTIME_EXACT=
HOMEASSISTANT_RUNTIME_EXACT=
SERVICES_ACTIVE=
BROKER_GUARD_ACTIVE=
REGISTRATION_PORTS_CLOSED=
REGISTRATION_SUCCESSOR_STATE_ABSENT=

PAIRING_WINDOW_CLOSED=
DATABASE_INTEGRITY=
CURRENT_REGISTRATION_COUNT=
FIRST_REGISTRATION_TABLE_PRESENT=
F4_SERVICES_ELIGIBILITY=
BROKER_DYNSEC_READONLY_BINDING=
ROOT_FREE_BYTES=

LIVE_RUNTIME_MUTATION=false
T1_PRODUCT_STATE_MUTATION=false
BOARD_ACCESS=false

R2_PRELIVE_GATE=
READY_FOR_R2_LIVE_AUTHORIZATION=
NEXT_ROUTE=RETURN_TO_HIGH_LEVEL_MODEL
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_LIVE_UPGRADE_AUTHORIZATION_AND_EXECUTION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
PROPOSED_AUTHORIZATION=N3W_R10_T1_CANDIDATE_UPGRADE_R2_20261028_01
```

高阶模型必须把新的 R2 exact artifact authority 展示给用户，再请求明确授权。

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

不得清理 R1 staging 或“顺手修现场”。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true

KF_ID=KF-131
DOMAIN=R10 T1 candidate live upgrade preclaim / Docker target-image existence detection
SYMPTOM=R1 live executor returned target_manager_image_preexisting although direct readonly docker inspect immediately proved No such image
ROOT_CAUSE=optional docker image inspect allowed rc=1 but then classified any non-empty stdout as image existence; inspect-miss output could therefore false-STOP
FIX_OR_GUARD=R2 uses docker image ls --no-trunc --quiet --filter reference=<exact tag>; empty=absent, one ID=present, multiple distinct IDs=ambiguous STOP; focused absent/present/dedup tests
STATUS=SOURCE_REPAIR_CLOSED_PASS_R2_ARTIFACT_FROZEN_LIVE_NOT_REEXECUTED
```

---

## 16. New Chat Start Prompt

```text
阅读：
docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_PRELIVE_NEW_CHAT_HANDOFF_V1.0_20261028.md

同时读取 exact handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #718
- PR #715 / #716 / #717 仅作为 R1 历史 stack
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false

必须先承认：
- R1 artifact 12792592683 已 superseded，禁止再执行；
- R1 live authorization N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01 虽未 consumed，但禁止重放到 R2；
- R1 T1 staging 仍保留，当前不得先删除；
- R1 target_manager_image_preexisting 是 KF-131 false-STOP，实际 target image 当时不存在；
- PR #718 R2 exact head=4a8c2a62be74ec5c9740d37946e770d9464b6cb3；
- R2 package CI + redownload verify 已 PASS；
- R2 artifact ID=12795906971；
- R2 artifact 尚未 Mac local verify、尚未 T1 staging；
- R2 live authorization 尚未 granted；
- board authorization 仍单独未 consumed。

当前只进入：
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_ARTIFACT_LOCAL_VERIFY_AND_PRELIVE_READONLY_REBIND_20261028_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先完成 R2 Mac local exact artifact verify + T1 fresh readonly prelive rebind。
不要自动清理 R1 staging；
不要 stage R2；
不要重放 R1 authorization；
不要请求/claim R2 live authorization；
不要访问板卡；
PASS 后返回高阶模型，再单独申请新的 R2 live authorization。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=R10_T1_CANDIDATE_R2_PRELIVE
CURRENT_STOP_POINT=R2 exact artifact frozen in GitHub; local verify + fresh T1 readonly rebind pending

SOURCE_DEFECT_PROVEN=false
KF_131_SOURCE_REPAIR=CLOSED_PASS
CURRENT_BLOCKER=R2_LOCAL_ARTIFACT_VERIFY_AND_PRELIVE_READONLY_REBIND_PENDING

LIVE_SYSTEM_STATE=R1 preclaim stopped before claim; production runtime last proven predecessor; R1 staging remains; R2 not staged

R1_AUTHORIZATION_CONSUMED=false
R1_AUTHORIZATION_REPLAY_PERMITTED=false

R2_AUTHORIZATION_GRANTED=false
R2_AUTHORIZATION_CONSUMED=false

R10_BOARD_WRITE_AUTHORIZATION_CONSUMED=false

NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_R2_ARTIFACT_LOCAL_VERIFY_AND_PRELIVE_READONLY_REBIND_20261028_01

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
