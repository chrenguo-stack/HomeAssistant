# N3-W 温室环境监测系统
# T1 S20 R4 rollback volume drift + readiness transport failure
# 新会话交接文档 V1.0 — 2026-10-11

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`。  
> exact handoff process authority: `4300890dff0ce63d5a547df21426e287d084d9ee`.  
> 如本文与 fresh repository/runtime/live evidence 冲突，以更高 authority 为准，并先 STOP 完成 rebind。  
> 本文不得记录 T1 私有 IP、密码或 secret 内容。

---

## 0. 会话切换结论

本轮 S20 R4 live apply 已失败，R4 一次性 authorization 已永久消耗。外部只读取证证明产品安全状态基本恢复，但 Docker volume exact baseline 未恢复：45 个 volume 变为 46 个，因此 executor 正确进入 `rollback_incomplete_manual_recovery_required`。

同时，本轮首次证明 temporary Broker 已成功启动；真实 transaction failure 已后移到 admin readiness transport。executor 仍硬编码 plain `127.0.0.1:1883`，而 exact live Broker config 只有 TLS `listener 8883`，导致连续 `mosquitto_rr exitCode=1` 并最终 readiness timeout。

下一会话**不重新复盘 R1-R4，也不直接设计/执行 R5**。先只读识别新增 Docker volume 的 exact identity / provenance。

```text
CURRENT_STAGE=S20_R4_POSTFAIL_MANUAL_RECOVERY_PREFLIGHT
CURRENT_STOP_POINT=R4_PRODUCT_STATE_RESTORED_EXCEPT_DOCKER_VOLUME_SET
NEXT_ONE_GATE=N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护当前 clean-product 路线与安全边界；
- 维护 main / PR #541 / exact S20 source / live runtime authority；
- 对 R4 rollback incomplete 做准确分类，不把“日志没看到”当产品故障；
- 设计 manual recovery gate 和后续 R5 source repair；
- 维护 one-shot authorization ledger；
- 禁止在 exact extra-volume provenance 未证明前删除 volume；
- 防止测试夹具修复改变产品 Broker contract。

### 1.2 Codex 低阶执行职责

- 机械执行下一门 exact read-only DSL；
- 只运行必要的 Git/Docker/SSH/read-only shell；
- 输出 volume identity / creation / labels / refs / event correlation；
- 第一处 substantive ambiguity 立即 fail-closed STOP；
- 不删除 volume、不启动容器、不自行修复 readiness。

Codex 不得扩大 scope、重放 consumed authorization、跨入 volume delete 或 R5。

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

### 1.4 标准交互循环

```text
高阶模型：分析 / gate / 最小授权设计
        ↓
只读 gate：无需 live mutation authorization
        ↓
Codex：exact read-only execution → closure
        ↓
高阶模型：确认 exact extra volume identity
        ↓
如需删除：申请新的 bounded recovery authorization
```

---

## 2. Product North Star

当前产品路线：

```text
PRESERVE_EXISTING_ARMBIAN
REDEPLOY_GREENHOUSE_SOFTWARE_FROM_CLEAN_PRODUCT_STATE
EXACTLY_THREE_PRODUCTION_SERVICE_IDENTITIES=
  manager
  provisioning
  homeassistant
ZERO_NODE_CREDENTIALS_BEFORE_REAL_GATE_F_PAIRING
HOMEASSISTANT_AUTO_MQTT_BOOTSTRAP_WITHOUT_MANUAL_PASSWORD_COPY
NO_DIRECT_DOT_STORAGE_EDIT
```

最终阶段目标：

```text
T1 clean greenhouse stack deployable from preserved Armbian
→ Broker / Manager / Home Assistant production runtime
→ exactly three service credentials safely handed off
→ first real board pairing only after T1 acceptance
→ no dependency on historical hand-built T1 state
```

当前不得进入：

```text
R4_AUTHORIZATION_REPLAY
R5_LIVE_APPLY
PRODUCTION_BROKER_START
PRODUCTION_MANAGER_START
PRODUCTION_HOMEASSISTANT_START
BOARD_PAIRING
BOARD_USB_SERIAL_FLASH_NVS_RF
PR541_MERGE
OS_REINSTALL_OR_DISK_WIPE
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee

PR=541
PR_STATE=OPEN_DRAFT
PR_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010

PR_HEAD_BEFORE_HANDOFF_DOC=
5d8ee2433e3d8d10b0a3f38dab93813ee6256b28

PR_AHEAD_OF_MAIN_AT_HANDOFF_INPUT=220
PR_BEHIND_MAIN_AT_HANDOFF_INPUT=0

SOURCE_AUTHORITY_HEAD=
d28129967eafacdab257c3dd00ecf3dc8910f52e

NEW_CHAT_MUST_FRESH_REBIND_PR_HEAD=true
MERGE=false
```

The handoff document itself is a documentation-only successor commit, so new chat must fresh-rebind PR #541 before execution. Product/executor source authority remains the frozen source content below unless source changed.

### 3.2 R4 executor / CI authority

```text
R4_EXECUTOR_PATH=
host/greenhouse-manager/src/greenhouse_manager/ops/t1_s20_real_service_handoff.py

R4_EXECUTOR_BLOB_SHA1=
69aa03770883960e6b2656fe9be88fb8fc9b96e6

R4_EXECUTOR_SHA256=
cc14d78b5771930bb66a3dd8e3527fb0f0e871fcb7c86b786d005752ae42a293

PUBLIC_REPOSITORY_SAFETY_CI=PASS:38065513470
N3W_T1_S20_REAL_SERVICE_HANDOFF_CI=PASS:38065513507
GREENHOUSE_MANAGER_CI=PASS:38065513519
```

Dependency SHA256:

```text
t1_clean_service_credential_bundle.py=
b7e42dd8f4c4a08f107c262ff4b5cf9b50b6b5e166f3ab852d6b32d513b0bc48

dynsec_api.py=
a8e29c0d7c83eeaf2dbb1ad3c119c890ea3eaaed71ad6568d6be86180c9c39f5

service_identity_plan.py=
7c66fb20d50859322598ad9e08ba0436d602b9ef36586895993e980090c0bac5

dynsec_plan.py=
2671fa7d0e3e79816fd2f3d09fa7586c3dbbbe3f08f0db8b829a72ccb19688b9
```

### 3.3 Broker / state authority

```text
BROKER_IMAGE_INDEX_DIGEST=
sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408

BROKER_ARM64_MANIFEST_DIGEST=
sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549

BROKER_CONFIG=/etc/n3wfc4/mosquitto.conf
BROKER_CONFIG_SHA256=
3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6

DYNSEC=/var/lib/n3wfc4-broker/dynamic-security.json
DYNSEC_BASELINE_SHA256=
94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5

S18_BACKUP_SHA256=
93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da

PRE_R4_DOCKER_VOLUME_COUNT=45
PRE_R4_DOCKER_VOLUME_SET_SHA256=
20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

POST_R4_DOCKER_VOLUME_COUNT=46
POST_R4_DOCKER_VOLUME_SET_SHA256=
918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999
```

### 3.4 R1-R4 snapshot authority

All four snapshots are direct live evidence and currently exact baseline copies:

```text
R1=/etc/n3wfc4/private/dynsec-s20-pre-three-service.json
R2=/etc/n3wfc4/private/dynsec-s20-r2-pre-three-service.json
R3=/etc/n3wfc4/private/dynsec-s20-r3-pre-three-service.json
R4=/etc/n3wfc4/private/dynsec-s20-r4-pre-three-service.json

R1_SHA256=BASELINE_EXACT
R2_SHA256=BASELINE_EXACT
R3_SHA256=BASELINE_EXACT
R4_SHA256=BASELINE_EXACT

R1_R2_R3_R4_OWNER_MODE=0:0:600
SNAPSHOT_MUTATION_ALLOWED=false
```

### 3.5 Target host / runtime authority

```text
TARGET_HOST=T1_PRIVATE_TARGET_DO_NOT_STORE_ADDRESS_IN_REPOSITORY
TARGET_ARCH=aarch64
EXPECTED_KERNEL=6.18.26-ophub
EXPECTED_DOCKER_VERSION=29.7.1
```

No private IP or credential is authority in this public repository document.

### 3.6 Current alignment documents

```text
PROGRESS_ALIGNMENT=
docs/development/N3W_T1_S20_R4_READINESS_AND_ROLLBACK_VOLUME_DRIFT_PROGRESS_ALIGNMENT_20261011.md

PROGRESS_ALIGNMENT_COMMIT=
63195a9783bc59da61bb7aacd1f2062e5b3a5030

KNOWN_FAILURES_KF102_COMMIT=
184f79cc69686cec367e6b9ce7cd745388f2ea34

CURRENT_STATE_ALIGNMENT_COMMIT=
2d15838da4cafeb20847cbe8bccd6f866a53d34d

CURRENT_STATE_INDEX_ALIGNMENT_COMMIT=
5d8ee2433e3d8d10b0a3f38dab93813ee6256b28

CURRENT_STATE_HANDOFF_POINTER_COMMIT=
b9d6df48a7d746c5a93b24fec3d07f164b8416bd

CURRENT_STATE_INDEX_HANDOFF_POINTER_COMMIT=
de3b7f25a11c606d292c2cbda1a7ac24c4918570
```

---

## 4. Current Live Baseline

Latest fresh external R4 forensic proves:

```text
DOCKER_CONTAINER_COUNT=0
TRANSACTION_CONTAINER_PRESENT=false

HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0

PRODUCTION_BROKER_STATE=STOPPED
PRODUCTION_MANAGER_STATE=STOPPED
PRODUCTION_HOMEASSISTANT_STATE=STOPPED

REAL_DYNSEC_PRESENT=true
REAL_DYNSEC_BASELINE_EXACT=true
REAL_DYNSEC_OWNER_MODE=1883:1883:600
ROLLBACK_TMP_PRESENT=false

R1_SNAPSHOT_BASELINE_EXACT=true
R2_SNAPSHOT_BASELINE_EXACT=true
R3_SNAPSHOT_BASELINE_EXACT=true
R4_SNAPSHOT_BASELINE_EXACT=true

BROKER_CONFIG_BASELINE_EXACT=true
S18_BACKUP_BASELINE_EXACT=true

PRODUCTION_SECRET_DESTINATION_PRESENT=false
PRODUCTION_SECRET_PARENT_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false

DYNSEC_CLIENT_COUNT=1
DYNSEC_ROLE_COUNT=1
DYNSEC_ADMIN_PRESENT=true
DYNSEC_ADMIN_ONLY=true
TARGET_SERVICE_CLIENTS_PRESENT_COUNT=0
TARGET_SERVICE_ROLES_PRESENT_COUNT=0
NODE_CLIENTS_PRESENT=false

DOCKER_VOLUME_COUNT=46
DOCKER_VOLUME_SET_BASELINE_EXACT=false

NETWORK_n3wfc4-private_CONTAINER_COUNT=0
NETWORK_n3wfc4-services_CONTAINER_COUNT=0

GUARD_ACTIVE=active
GUARD_ENABLED=enabled

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

New chat must fresh-read-only-rebind this baseline before any future mutation design.

---

## 5. Proven Current Facts

### 5.1 R4 temporary Broker startup is proven working

R4 event sequence contains:

```text
create
start
repeated docker exec mosquitto_rr
kill
die exitCode=137
destroy
```

The Broker lived approximately 21 seconds while readiness was retried.

```text
R4_TEMP_BROKER_STARTUP=PASS
R3_TLS_MOUNT_TARGET_BLOCKER=CLOSED
```

### 5.2 R4 readiness failure is exactly bounded

All in-container commands observed before rollback were the readiness command:

```text
mosquitto_rr
-o /run/n3w-s20/admin.conf
-q 1
-W 3
-t $CONTROL/dynamic-security/v1
-e $CONTROL/dynamic-security/v1/response
-s
```

Every readiness exec returned exitCode 1.

No service-role/client mutation command was reached.

```text
SERVICE_DYNSEC_MUTATION_REACHED=false
SERVICE_AUTHENTICATION_TESTS_REACHED=false
```

### 5.3 Readiness transport contract mismatch is proven

Executor client config source freezes:

```text
-h 127.0.0.1
-p 1883
-V 5
```

Exact live Broker config freezes:

```text
listener 8883 0.0.0.0
cafile /mosquitto/config/n3w-ca.pem
certfile /mosquitto/config/n3w-server.pem
keyfile /mosquitto/config/n3w-server.key
tls_version tlsv1.2
```

Therefore:

```text
R4_READINESS_ROOT_CAUSE_STATUS=CONFIRMED
R4_READINESS_ROOT_CAUSE=
ADMIN_CLIENT_CONFIG_HARDCODES_PLAINTEXT_127_0_0_1_1883_WHILE_EXACT_TEMP_BROKER_CONFIG_EXPOSES_TLS_8883_ONLY
```

This is a harness/executor source defect. Do not modify the product Broker config to add plaintext 1883 solely to satisfy the harness.

### 5.4 R4 product/security rollback state is restored

Direct evidence proves exact restoration/cleanup of:

- live DynSec SHA and metadata;
- no service clients/roles;
- no node clients;
- no transaction Broker container;
- no MQTT listeners;
- no production secret destination/parent;
- no transaction directory;
- no rollback temporary file;
- two project networks empty;
- ingress guard active+enabled;
- R1-R4 snapshots intact.

### 5.5 Docker volume baseline is not restored

```text
PRE_R4=45 volumes / set SHA 20fc8457...
POST_R4=46 volumes / set SHA 918671f5...
```

Source order in `_rollback_postcheck()` checks:

```text
container inventory
→ volume count/set
→ networks
→ guard/listeners
→ hashes/state
```

Since external evidence proves zero containers but 46 volumes, the executor's rollback failure point is directly determined as:

```text
rollback_postcheck_volume_set_drift
```

### 5.6 Exact extra-volume identity is NOT yet proven

```text
PROVEN=ONE_ADDITIONAL_VOLUME_EXISTS_RELATIVE_TO_FROZEN_BASELINE
NOT_PROVEN=EXACT_VOLUME_NAME
NOT_PROVEN=EXACT_CREATOR
NOT_PROVEN=SAFE_TO_DELETE
```

Inference only:

```text
INFERENCE_R4_TRANSACTION_CAUSED_EXTRA_VOLUME=HIGH_CONFIDENCE_BUT_NOT_YET_EXACTLY_ATTRIBUTED
```

Do not promote this inference into deletion authority.

---

## 6. Current Root Cause / Blockers

### Blocker A — Docker volume baseline drift / manual recovery

```text
ROOT_CAUSE_OF_ROLLBACK_INCOMPLETE=
ROLLBACK_POSTCHECK_VOLUME_SET_DRIFT

PROVEN_BY=
PRE_R4_45_VOLUME_FROZEN_BASELINE
+
POST_R4_46_VOLUME_EXTERNAL_FORENSIC
+
SOURCE_CHECK_ORDER

SOURCE_DEFECT_PROVEN=PARTIAL
RUNTIME_DRIFT_PROVEN=true
EXACT_EXTRA_VOLUME_IDENTITY_PROVEN=false
MANUAL_RECOVERY_REQUIRED=true
```

This blocker must close before any successor live transaction or production service start.

### Blocker B — Admin readiness transport mismatch

```text
ROOT_CAUSE=
ADMIN_READINESS_USES_PLAINTEXT_1883_BUT_EXACT_BROKER_CONFIG_EXPOSES_TLS_8883_ONLY

PROVEN_BY=
EXACT_EXECUTOR_CLIENT_CONFIG
+
EXACT_LIVE_BROKER_CONFIG
+
REPEATED_MOSQUITTO_RR_EXIT_1
+
BROKER_REMAINED_RUNNING

SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=false
PRODUCT_BROKER_DEFECT_PROVEN=false
```

This is future R5 source-repair work, not the next one gate.

---

## 7. Closed / Forbidden Routes

Unless new direct counter-evidence appears:

```text
R1_REPLAY=FORBIDDEN:authorization consumed
R2_REPLAY=FORBIDDEN:authorization consumed
R3_REPLAY=FORBIDDEN:authorization consumed
R4_REPLAY=FORBIDDEN:authorization consumed

R1_FORCED_DOCKER_UID_ROUTE=CLOSED:defect already removed
R3_TLS_TARGET_PATH_BLOCKER=CLOSED:R4 Broker startup proved working

ADD_PLAINTEXT_1883_TO_PRODUCT_BROKER_FOR_TEST_HARNESS=FORBIDDEN
DELETE_UNKNOWN_DOCKER_VOLUME=FORBIDDEN

START_PRODUCTION_BROKER_BEFORE_VOLUME_RECOVERY=CLOSED_FOR_NOW
START_PRODUCTION_MANAGER_BEFORE_VOLUME_RECOVERY=CLOSED_FOR_NOW
START_PRODUCTION_HOMEASSISTANT_BEFORE_VOLUME_RECOVERY=CLOSED_FOR_NOW

BOARD_ACCESS=FORBIDDEN
PR541_MERGE=FORBIDDEN
```

R2 whole-directory TLS-bind defect remains historical evidence but is not the current blocker.

---

## 8. Authorization Ledger

### R1

```text
AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLED_BACK
REPLAY_PERMITTED=false
SUPERSEDED_BY=R2
```

### R2

```text
AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R2_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLED_BACK
REPLAY_PERMITTED=false
SUPERSEDED_BY=R3
```

### R3

```text
AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R3_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLED_BACK
REPLAY_PERMITTED=false
SUPERSEDED_BY=R4
```

### R4

```text
AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R4_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLBACK_INCOMPLETE_VOLUME_SET_DRIFT
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

### Future

```text
PROPOSED_VOLUME_RECOVERY_AUTHORIZATION=NOT_YET_DESIGNED
GRANTED=false

PROPOSED_R5_AUTHORIZATION=NOT_YET_DESIGNED
GRANTED=false
```

Read-only attribution requires no live mutation authorization.

---

## 9. Rollback Authority

The next gate is completely read-only:

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

However the manual-recovery target baseline is frozen:

```text
RECOVERY_TARGET_DOCKER_VOLUME_COUNT=45
RECOVERY_TARGET_DOCKER_VOLUME_SET_SHA256=
20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

RECOVERY_MUST_PRESERVE=
  REAL_DYNSEC_SHA256 94f3c0a3...
  BROKER_CONFIG_SHA256 3708c6ce...
  S18_BACKUP_SHA256 93c751a7...
  R1/R2/R3/R4 snapshots exact
  zero containers
  zero MQTT listeners
  secret destination absent
  project networks empty
  guard active+enabled
```

No deletion is authorized by this handoff.

For a later bounded volume deletion:

```text
FRESH_PREDELETE_READONLY_REBIND_REQUIRED=true
EXACT_VOLUME_IDENTITY_REQUIRED=true
PROOF_VOLUME_UNREFERENCED_REQUIRED=true
NEW_EXPLICIT_AUTHORIZATION_REQUIRED=true
SECOND_ATTEMPT_ALLOWED=false
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01
```

### 10.1 Purpose

Identify, without mutation, the exact Docker volume that accounts for the 45→46 drift and prove whether it is uniquely attributable to the R4 temporary Mosquitto transaction. Do not delete anything. Do not start any container. This gate only creates a trustworthy recovery target or stops on ambiguity.

### 10.2 Frozen inputs

```text
PRE_R4_VOLUME_COUNT=45
PRE_R4_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

OBSERVED_POST_R4_VOLUME_COUNT=46
OBSERVED_POST_R4_VOLUME_SET_SHA256=918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999

R4_TRANSACTION_CONTAINER=n3w-s20-three-service-transaction
R4_BROKER_IMAGE_INDEX_DIGEST=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408

R4_EVENT_WINDOW_START_APPROX=container create event 1791648912
R4_EVENT_WINDOW_END_APPROX=container destroy event 1791648934
```

### 10.3 Required proof / operations

```text
1. fresh rebind PR #541 OPEN_DRAFT and current main.
2. fresh read-only prove:
   - zero containers;
   - zero MQTT host listeners;
   - live DynSec baseline exact;
   - secret/transaction material absent;
   - current volume count still 46.
3. enumerate all current Docker volume names sorted.
4. docker volume inspect all 46:
   - Name
   - Driver
   - Scope
   - Labels
   - Mountpoint
   - CreatedAt if available
   - Options
5. collect read-only Docker volume events covering the R4 transaction window
   if daemon event history still retains them.
6. inspect exact Mosquitto image Config.Volumes / runtime Docker metadata.
7. determine whether exactly one current volume:
   - was created in the R4 transaction window, or
   - can otherwise be uniquely bound to the R4 temporary container/image,
   - is not referenced by any current container,
   - is not a named/project production volume.
8. do not read secrets or application payload content.
9. do not delete, rename, mount, attach, create, prune, start, stop or restart.
10. if more than one plausible candidate or provenance is not exact:
    STOP with AMBIGUOUS.
```

### 10.4 PASS

```text
R4_EXTRA_DOCKER_VOLUME_ATTRIBUTION=PASS
EXTRA_VOLUME_IDENTITY=<exact volume name>
R4_TRANSACTION_PROVENANCE=true
CURRENT_CONTAINER_REFERENCE_COUNT=0
SAFE_DELETION_NOT_YET_AUTHORIZED=true
READY_FOR_BOUNDED_VOLUME_RECOVERY_AUTHORIZATION=true
STOP=true
```

PASS does not delete the volume.

### 10.5 FAIL

```text
R4_EXTRA_DOCKER_VOLUME_ATTRIBUTION=FAIL_AMBIGUOUS
EXACT_DELETE_TARGET_PROVEN=false
READY_FOR_BOUNDED_VOLUME_RECOVERY_AUTHORIZATION=false
STOP=true
```

Codex must not automatically enter recovery or R5.

---

## 11. Hard Allowed / Forbidden Scope

Default:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub/repository read-only fresh rebind
- SSH read-only host commands
- docker ps / inspect / volume ls / volume inspect / image inspect
- docker events read-only query
- ss/systemctl status/is-active/is-enabled read-only
- sha256sum/stat/find metadata-only as needed
- bounded local parsing from stdin
```

### FORBIDDEN

```text
- docker volume rm
- docker volume prune
- docker system prune
- docker rm/create/run/start/stop/restart
- any volume attach/mount
- any filesystem delete/rename/chown/chmod/write
- DynSec mutation
- secret generation or secret content output
- Broker/Manager/Home Assistant start
- firewall/network/systemd mutation
- R1/R2/R3/R4 authorization replay
- R5 apply
- board/USB/serial/Flash/NVS/RF
- PR merge
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not delete.
Do not retry a live transaction.
Do not enter the next gate.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

EXECUTION_ID=
N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01

AUTHORIZATION=NOT_REQUIRED_READONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

Assert:
R4_AUTHORIZATION_CONSUMED=true
R4_AUTHORIZATION_REPLAY=false

============================================================
1. FROZEN INPUTS
============================================================

MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR=541
PR_EXPECTED_STATE=OPEN_DRAFT

SOURCE_AUTHORITY_HEAD=
d28129967eafacdab257c3dd00ecf3dc8910f52e

PRE_R4_VOLUME_COUNT=45
PRE_R4_VOLUME_SET_SHA256=
20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

OBSERVED_POST_R4_VOLUME_COUNT=46
OBSERVED_POST_R4_VOLUME_SET_SHA256=
918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999

TEMP_CONTAINER=n3w-s20-three-service-transaction
BROKER_IMAGE_INDEX_DIGEST=
sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408

============================================================
2. HARD SCOPE
============================================================

LIVE_MUTATION=false
VOLUME_DELETE=false
CONTAINER_MUTATION=false
FILESYSTEM_MUTATION=false
BOARD_ACCESS=false
PR_MERGE=false

============================================================
3. FRESH LIVE BASELINE
============================================================

Read-only prove:
- container count;
- temp container absent;
- ports 1883/8883/18883 listener count;
- DynSec hash/stat/admin-only inventory;
- secret root/parent/transaction dir absent;
- project networks empty;
- guard active/enabled;
- volume count/set current.

If any product/security baseline regressed beyond the known volume drift:
STOP immediately with BASELINE_DRIFT.

============================================================
4. VOLUME ENUMERATION
============================================================

Get sorted exact volume names.
Inspect every volume.
Capture only metadata needed for identity/provenance:
Name, Driver, Scope, Labels, Mountpoint, CreatedAt, Options.

Do not read payload file contents.

============================================================
5. EVENT / IMAGE CORRELATION
============================================================

Read volume-related Docker event history around the R4 window if retained.
Inspect exact Broker image Config.Volumes.

Correlate current volumes to:
- R4 creation time;
- temporary container/image behavior;
- project labels;
- current references.

============================================================
6. ATTRIBUTION RULE
============================================================

PASS only if exactly one current extra volume has direct, non-ambiguous
R4 transaction provenance and zero current container references.

Creation-time proximity alone is not enough if multiple candidates match.

Do not infer safe deletion from an anonymous-looking name alone.

============================================================
7. HARD STOP
============================================================

Never delete the candidate.
Never start a Broker.
Never execute R5.
Return closure and STOP.
```

---

## 13. Expected Closure

```text
=== N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01 CLOSURE ===

EXECUTION_ID=
N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01

AUTHORIZATION=NOT_REQUIRED_READONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

MAIN_REBOUND=
PR541_HEAD_REBOUND=
PR541_STATE=
PR541_DRAFT=

CONTAINER_COUNT=
TEMP_CONTAINER_PRESENT=
HOST_TCP1883_LISTENER_COUNT=
HOST_TCP8883_LISTENER_COUNT=
HOST_TCP18883_LISTENER_COUNT=

REAL_DYNSEC_BASELINE_EXACT=
PRODUCTION_SECRET_DESTINATION_PRESENT=
TRANSACTION_DIRECTORY_PRESENT=

CURRENT_VOLUME_COUNT=
CURRENT_VOLUME_SET_SHA256=
KNOWN_PRE_R4_VOLUME_SET_SHA256=

VOLUME_EVENT_HISTORY_AVAILABLE=
BROKER_IMAGE_CONFIG_VOLUMES=

CANDIDATE_COUNT=
EXTRA_VOLUME_IDENTITY=
EXTRA_VOLUME_CREATED_AT=
EXTRA_VOLUME_LABELS=
EXTRA_VOLUME_CURRENT_REFERENCE_COUNT=
R4_TRANSACTION_PROVENANCE=

LIVE_RUNTIME_MUTATION=false
VOLUME_DELETE=false
BOARD_ACCESS=false

R4_EXTRA_DOCKER_VOLUME_ATTRIBUTION=
READY_FOR_BOUNDED_VOLUME_RECOVERY_AUTHORIZATION=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=
N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_AUTHORIZATION_DESIGN

AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
```

Only after an exact candidate is proven may the high-level model design a one-volume deletion authorization plus exact 45-volume postcheck.

After recovery closes, the later independent source stage is:

```text
FUTURE_STAGE=
N3W_T1_S20_R5_ADMIN_READINESS_TLS_TRANSPORT_SOURCE_REPAIR
```

Do not skip directly to it.

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_DELETE=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true

KF_ID=KF-102
DOMAIN=T1_S20_TEMP_BROKER_TRANSACTION_HARNESS

FAILURE_A=
ADMIN_READINESS_TRANSPORT_DIVERGED_FROM_EXACT_BROKER_LISTENER_TLS_CONTRACT

FAILURE_B=
TEMP_TRANSACTION_LEFT_DOCKER_VOLUME_SET_DRIFT_AND_CAUSED_ROLLBACK_INCOMPLETE

REGRESSION_GUARD=
EXACT_LISTENER_TLS_BINDING
+
FULL_TEMP_DOCKER_ARTIFACT_INVENTORY
+
EXACT_UNEXPECTED_VOLUME_IDENTITY_ON_ROLLBACK_FAILURE
+
CONSUMED_AUTH_NO_REPLAY
```

GitHub update authority:

```text
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
commit=184f79cc69686cec367e6b9ce7cd745388f2ea34
```

---

## 16. New Chat Start Prompt

Use the following prompt in the new conversation:

```text
阅读：

docs/development/N3W_T1_S20_R4_ROLLBACK_VOLUME_DRIFT_AND_READINESS_FAILURE_NEW_CHAT_HANDOFF_V1.0_20261011.md

同时读取 exact handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #541
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_S20_R4_READINESS_AND_ROLLBACK_VOLUME_DRIFT_PROGRESS_ALIGNMENT_20261011.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W 温室环境监测系统产品化与首次配对验收
支线任务：保留 Armbian，全新部署 T1 温室软件
当前任务：R4 extra Docker volume 只读归因与 manual recovery 准备

必须先承认：
- R1/R2/R3/R4 四个 live authorization 都已 consumed，全部禁止 replay；
- R4 temporary Broker startup 已 PASS；
- R4 失败点是 admin readiness transport：executor plain 127.0.0.1:1883，而 exact Broker config 只有 TLS 8883；
- R4 未进入 service createRole/createClient；
- DynSec / secret / container / listeners / networks 已恢复 baseline；
- 当前唯一已知 rollback residual 是 Docker volume count 45→46；
- exact extra volume identity 尚未证明，禁止删除；
- production Broker/Manager/HA 不得启动；
- 不访问板卡；
- PR #541 保持 OPEN DRAFT，不 merge。

当前只进入：
NEXT_ONE_GATE=N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01

本 gate 只读。
先 fresh rebind，再设计/执行最小 volume metadata/event provenance 取证。
不得自动删除 volume，不得进入 R5。
```

---

## 17. Final Frozen State

```text
PROJECT=N3-W

MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541=OPEN_DRAFT
PR541_SOURCE_AUTHORITY=d28129967eafacdab257c3dd00ecf3dc8910f52e
PR541_HEAD_BEFORE_HANDOFF_DOC=5d8ee2433e3d8d10b0a3f38dab93813ee6256b28
PR_MERGE=false

S19_ISOLATED_IDENTITY_AND_ACL_ACCEPTANCE=CLOSED_PASS
S20_HA_ISOLATED_RUNTIME_ACCEPTANCE=CLOSED_PASS

S20_R1_APPLY=FAIL
S20_R1_ROLLBACK=CLOSED_PASS
R1_AUTHORIZATION_CONSUMED=true
R1_REPLAY=false

S20_R2_APPLY=FAIL
S20_R2_ROLLBACK=CLOSED_PASS
R2_AUTHORIZATION_CONSUMED=true
R2_REPLAY=false

S20_R3_APPLY=FAIL
S20_R3_ROLLBACK=CLOSED_PASS
R3_AUTHORIZATION_CONSUMED=true
R3_REPLAY=false

S20_R4_APPLY=FAIL
S20_R4_ROLLBACK=CLOSED_PARTIAL
R4_AUTHORIZATION_CONSUMED=true
R4_REPLAY=false

R4_TEMP_BROKER_STARTUP=PASS
R4_SERVICE_DYNSEC_MUTATION_REACHED=false

R4_READINESS_ROOT_CAUSE_STATUS=CONFIRMED
R4_READINESS_ROOT_CAUSE=
ADMIN_CLIENT_CONFIG_HARDCODES_PLAINTEXT_127_0_0_1_1883_WHILE_EXACT_TEMP_BROKER_CONFIG_EXPOSES_TLS_8883_ONLY

REAL_DYNSEC_BASELINE_EXACT=true
PRODUCTION_SERVICE_CLIENTS_PRESENT=false
PRODUCTION_SERVICE_ROLES_PRESENT=false
NODE_CLIENTS_PRESENT=false

PRODUCTION_SECRET_DESTINATION_PRESENT=false
TRANSACTION_CONTAINER_PRESENT=false
HOST_MQTT_LISTENER_COUNT=0
PROJECT_NETWORKS_EMPTY=true
GUARD_ACTIVE=true
GUARD_ENABLED=true

PRE_R4_VOLUME_COUNT=45
CURRENT_VOLUME_COUNT=46
DOCKER_VOLUME_BASELINE_EXACT=false
EXACT_EXTRA_VOLUME_IDENTITY_PROVEN=false
MANUAL_RECOVERY_REQUIRED=true

KF_102=OPEN

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=
N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01

HANDOFF_READY_FOR_NEW_CHAT=true
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
