# 温室环境监测系统（ESP32-C6）/ N3-W
# T1 S19 隔离服务账号与权限验收关闭 → S20 三服务生产凭据交付只读预检
# 新会话交接文档 V1.0 — 2026-10-10

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
NEXT_ONE_GATE_ONLY=true
```

本交接按 exact process authority `4300890dff0ce63d5a547df21426e287d084d9ee` 中的 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 与 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` 编写。所有实时结论以 exact GitHub、T1 当前只读证据为准；历史记录与未来推断不得被冒充为现有事实。

## 0. 会话切换结论

用户主动结束当前对话，并要求对齐 GitHub、新建正式 handoff，S20 留待新对话执行。2026-10-10 S19 隔离的 Provisioning、Manager、Home Assistant、临时合法测试节点身份/ACL/通信正反例全部完成。生产三服务账号 **尚未创建**，正式 Broker **尚未启动**，不能宣布 T1 整机部署完成。

```text
CURRENT_STAGE=T1_SOFTWARE_FRESH_REDEPLOY_PRESERVE_ARMBIAN
CURRENT_STOP_POINT=S19_ISOLATED_SERVICE_IDENTITY_ACL_CLOSED_PASS__S20_PENDING
NEXT_ONE_GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话从这个 **唯一**只读 gate 开始，不回到 S0/S14/R2/R4，也不自动进入生产账号写入阶段。

## 1. 执行模式

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
HIGH_LEVEL_MODEL_WRITES_DESIGN_GATE_AND_SOURCE=true
CODEX_ROLE=EXACT_LOW_ORDER_EXECUTOR_AND_RESULT_REPORTER
CODEX_CODE_AUTHORING=false
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
```

高阶模型负责架构、authority、授权、源代码/部署决策、回滚和 PASS/FAIL/STOP；Codex 只机械编译本交接 `12` 精确 DSL 合同为最低必要命令，收集只读事实，第一处不符 STOP，不设计修复、不扩大 scope、不重放一次性授权。Mac Terminal 是操作者执行通道；SSH 若不可用，请求一次必要的脱敏输出，不能虚构现场结果。命令块不要注释。进度与证据在 GitHub 留痕，不依赖对话记忆。

原则：**test product, not the test framework**。除非字节级原子性等需要 exact executor，本门不制作复杂预写执行器。

## 2. Product North Star

保留 T1 Armbian OS、SSH、NetworkManager、Docker、原有必要网络保护；只重建已经证明属于温室系统的软件及业务数据。最终只一套 Home Assistant。Broker 具有受控 TLS 与默认拒绝权限，三类服务独立账户：Provisioning、Manager、HA；未来量产为工厂自动安装、自检，用户通电联网及首次添加节点，不运行当前研发期手工脚本。每台真实 ESP32-C6 只在 Gate F 首次配对时生成唯一节点凭据。

```text
OS_REINSTALL=false
WHOLE_HOST_ERASE=false
ARMBIAN_PRESERVE=true
ONE_HOMEASSISTANT=true
FUTURE_PRODUCT_INSTALLATION_AUTOMATED=true
NODE_CREDENTIALS_PER_REAL_NODE_AT_GATE_F_ONLY=true
```

本门不进行真实账号创建、生产 Broker 上线、HA UI 操作、ESP32-C6 实板配对。

## 3. Frozen Authorities

### 3.1 Repository / exact main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_EXACT_SHA=d423211b6196c2f2f0f01dff072c4f877fbe58ee
TREE=NOT_REQUIRED_FOR_THIS_READONLY_GATE; EXACT_COMMIT_IS_SOURCE_ANCHOR
PR_NUMBER=541
PR_STATE=OPEN_DRAFT
PR_HEAD_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
PR_HEAD_BEFORE_HANDOFF=0e59ec423f3b94426e98b410cbb6122401f7ad65
PR_MERGE=false
HANDOFF_PROCESS_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
```

新会话需重新获取 PR 当前 HEAD；提交本 handoff 会令 HEAD 变化，`PR_HEAD_BEFORE_HANDOFF` 是历史对齐点，不可当作执行时 latest HEAD。2026-10-10 最近一次比较 main→PR 分支无 behind，分支领先，main 当前 exact SHA 如上。

### 3.2 Candidate / artifact / image

```text
BROKER_IMAGE_REF=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine
ISOLATED_BROKER_LOCAL_IMAGE_ID=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
BROKER_IMAGE_OS=linux
BROKER_IMAGE_ARCH=arm64
BROKER_MOSQUITTO_VERSION=2.1.2
UPSTREAM_MANIFEST_PROVENANCE=NOT_YET_CLOSED_FOR_PRODUCT_DEPLOYMENT
MANAGER_PRODUCTION_IMAGE=UNBOUND
HOMEASSISTANT_PRODUCTION_IMAGE=UNBOUND
```

隔离测试成功不等于正式部署运行镜像或供应链 provenance 已闭环。

### 3.3 Successor / deployment material

- 当前 S19 权威：`docs/development/N3W_T1_S19_ISOLATED_SERVICE_IDENTITY_INIT_PREEXECUTION_20261010.md`。
- S20 准备：`docs/development/N3W_T1_S20_PRODUCTION_SERVICE_CREDENTIAL_HANDOFF_READONLY_PREFLIGHT_20261010.md`。
- 状态：`docs/development/N3W_CURRENT_STATE.md`、`docs/development/N3W_CURRENT_STATE_INDEX.md`，PR #541 分支的文件顶部已新增 S19 CLOSED / S20 pending current snapshot。main 上同名文件的旧快照不是当前 T1 stage。
- 软件专用重装权威：`docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md`；旧 `N3W_T1_FULL_FRESH_INSTALL_DIRECTION_AND_EXECUTION_PLAN_20261010.md` 内整机擦盘方案为 `SUPERSEDED_OS_WIPE_PLAN`。
- 失败保护：`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`（当前 PR 分支含 KF-101、KF-102）。
- 产品服务 ACL：`host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py`，main blob `19d95cfe59c12ee0abeaddf8c777fb663a5bd399`。
- 动态权限命令：`host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_api.py`，main blob `6a75b60de88689524ec3b6d0105e0b3f66f5a682`。
- Manager 配置：`host/greenhouse-manager/src/greenhouse_manager/runtime/config.py`，main blob `fabb2affa9fb8ce76aa8ed94ce4f4ea9745402cd`。
- 旧经理密码所有权标准：`protocols/pairing/gh-t1-manager-runtime-secret-ownership-gate-v1.md`，main blob `02b001967c7356adc0d6adee53854f3fb3643bb7`，须对 fresh T1 重新验证，并非已部署事实。
- 节点权限：`host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_plan.py`；下一会话重新绑定 exact blob。
- 历史迁移包：`host/greenhouse-manager/src/greenhouse_manager/ops/t1_migration_package.py`，main blob `3714a63f13f38f3f82a5f6c54a274ccebc23a3ca`；此工具生成三服务账号**连同一个节点**，不得直接用于 clean-product T1 首次配对。

```text
SUCCESSOR_PATH=NOT_APPLICABLE:READONLY_SCOPE_NO_EXECUTOR_ARTIFACT
SUCCESSOR_SHA256=NOT_APPLICABLE:NOT_AUTHORIZED_TO_APPLY
```

### 3.4 Target host / runtime

```text
TARGET_HOST=T1_PRIVATE_OPERATOR_SSH_IDENTITY
PRIVATE_SSH_IP=DO_NOT_COMMIT
TARGET_ARCH=arm64
T1_OS=Armbian_26.05.0_resolute
T1_KERNEL=6.18.26-ophub
T1_DOCKER_VERSION=29.7.1
BROKER_CONFIG_PATH=/etc/n3wfc4/mosquitto.conf
BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
REAL_DYNSEC_PATH=/var/lib/n3wfc4-broker/dynamic-security.json
REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
S18_ROOT_ONLY_BACKUP=/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json
S18_BACKUP_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
EXISTING_ADMIN_PASSWORD_FILE=/etc/n3wfc4/private/dynsec-admin-password
TLS_CA=/etc/n3wfc4/tls/ca.pem
TLS_SERVER_CERT=/etc/n3wfc4/tls/server.pem
TLS_SERVER_KEY=/etc/n3wfc4/tls/server.key
EXPECTED_DOCKER_VOLUME_COUNT=45
NETWORK_1=n3wfc4-private
NETWORK_2=n3wfc4-services
GUARD_UNIT=n3wfc4-broker-ingress-guard.service
```

以上哈希是当日已验证**最后一轮**现场证据；不表示新会话 live rebind 已完成。严禁读取/打印这些路径中的秘密正文、私钥或 Docker ENV 值。

## 4. Current Live Baseline

截至 T1 最后一次 S19-R6B 现场 PASS（2026-10-10 12:17+08:00）：

```text
BASELINE_AUTHORITY=LAST_OPERATOR_REPORT_S19_R6B
LIVE_BASELINE_REQUIRES_FRESH_T1_READONLY_REBIND=true
BROKER_STATE=NOT_RUNNING
BROKER_IMAGE_ID=NO_PRODUCTION_RUNNING_INSTANCE
BROKER_RESTART_STATE=NOT_APPLICABLE
MANAGER_STATE=NOT_RUNNING_IN_CLEAN_STACK
MANAGER_IMAGE_ID=UNBOUND_NEEDS_FRESH_SOURCE_CHECK
MANAGER_RESTART_STATE=NOT_APPLICABLE
HOMEASSISTANT_STATE=NOT_RUNNING_IN_CLEAN_STACK
HOMEASSISTANT_IMAGE_ID=UNBOUND
PAIRING_SERVICE_STATE=NOT_RUNNING_IN_CLEAN_STACK
PAIRING_PORT_OWNER_STATE=UNVERIFIED_REBIND_REQUIRED
PRODUCTION_SERVICE_CLIENTS_CREATED=false
PRODUCTION_DYNSEC=ONE_ADMIN_ONLY
DOCKER_CONTAINERS_EXPECTED=0
DOCKER_VOLUMES_EXPECTED=45_UNCHANGED
TWO_PROJECT_NETWORKS=EXIST_EMPTY
INGRESS_GUARD=ACTIVE_ENABLED_WITH_FIRST_JUMPS_AND_LAST_DROP
HOST_TCP8883_LISTENER=false
HOST_TCP18883_LISTENER=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

所有 S19 MQTT 交互是在 `--network none` throwaway Broker 内完成，临时目录均已清理；不是生产 Broker 活动的证明。若当前 host 与以上状态漂移，S20 必须失败关闭并首先分类。

## 5. Proven Current Facts

```text
S14_DYNSEC_ADMIN_INITIALIZATION=PASS
S15_REAL_MOSQUITTO_CONFIG_STAGED_AND_VALIDATED=PASS
S17_ISOLATED_DEFAULT_RECEIVE_DENY=PASS
S18_REAL_DEFAULT_RECEIVE_DENY_PROMOTION=PASS
S19_R1_THREE_SERVICE_ROLE_ACL_STATIC=PASS
S19_R2_ORIGINAL_RUNTIME=FAILED_STOP_UNKNOWN_PHASE
S19_R2_POSTFAIL_FORENSIC_AND_CLEANUP=PASS
S19_R3_PROVISIONING_CONTROL_MQTT_RUNTIME=PASS
S19_R4_ORIGINAL_MANAGER_INGRESS=FAILED_STOP
S19_R4_ADMIN_SEND_ACL_READONLY=PASS
S19_R4_EXACT_TEST_STAGE_CLEANUP=PASS
S19_R5_LEGAL_TEST_NODE_MANAGER_HA_ALL_POSITIVE_DELIVERY=PASS
S19_R6A_VALID_ID_WRONG_ID_ANONYMOUS_CONNECT=PASS
S19_R6B_CROSS_TOPIC_SEND_SUBSCRIBE_AND_RECEIVE_DENIAL=PASS
S19_ISOLATED_IDENTITY_AND_ACL_ACCEPTANCE=CLOSED_PASS
S19_TEMPORARY_SENSITIVE_STATES_REMOVED=true
S19_PRODUCTION_THREE_SERVICES_CREATED=false
S19_PRODUCTION_BROKER_STARTED=false
```

ACL 静态设计：Provisioning 10 项、Manager 17 项、HA 9 项；R5/R6 中的临时节点使用 main `dynsec_plan.py` 生成 11 ACL，但正式真实节点尚未创建。四项默认 ACL：`publishClientSend=false`、`publishClientReceive=false`、`subscribe=false`、`unsubscribe=true`。

已核对源码：Manager MQTT 业务认证支持 `GH_MQTT_PASSWORD_FILE`，Provisioning 可另从 `GH_N3W_PROVISIONING_PASSWORD_FILE` 读取密码，同时有独立 Username/Client ID；`GH_MQTT_PASSWORD` 与文件不允许并存。旧 Manager 安全合同要求私有 0600 文件、与运行 UID/GID 一致、只读挂载到 `/run/secrets/gh_manager_mqtt_password`。**fresh T1 当前 Manager/HA runtime、HA 凭据消费者与保存路径尚未取证绑定**。旧迁移工具会创建一个不应在首次配对前存在的 node。

INFERENCE：R2 原始通用脚本不保留失败分段信息，不能确定当时具体失败位置。PROVEN：R4 测试错误用 DynSec 临时管理员向业务 ingress 发送，其角色没有业务 publishClientSend ACL；旧 PUBACK 错误码未记录，R5 合法临时节点身份的实际投递已 PASS。不要把 R4 误当产品缺陷。

## 6. Current Root Cause / Blockers

### Blocker A — 三服务秘密安全交付未闭环

```text
BLOCKER_A=REAL_THREE_SERVICE_SECRET_HANDOFF_BINDING_OPEN
MANAGER_SECRET_FILE_INTERFACE=SOURCE_PROVEN
PROVISIONING_DISTINCT_SECRET_FILE_INTERFACE=SOURCE_PROVEN
ACTUAL_MANAGER_RUNTIME_UID_AND_READONLY_MOUNT=NOT_VERIFIED
ACTUAL_PROVISIONING_CONSUMER_BINDING=NOT_VERIFIED
FRESH_HOMEASSISTANT_MQTT_SECRET_STORAGE_AND_CONSUMER=NOT_VERIFIED
SOURCE_DEFECT_PROVEN=false
LIVE_RUNTIME_DEFECT_PROVEN=false
```

生产账号只能在“三份新密码准确安全交给三个正确消费者，断电/容器重建能恢复”的路径清楚后，再申请新授权。

### Blocker B — 正式 Broker/HA/Manager 部署闸门尚未执行

```text
BLOCKER_B=PRODUCTION_BROKER_TLS_IMAGE_HA_MANAGER_DEPLOYMENT_PENDING
CANDIDATE_ISOLATED_MOSQUITTO_TEST=PASS
PRODUCTION_IMAGE_UPSTREAM_PROVENANCE=OPEN
BROKER_HOST_8883=NOT_ACTIVE
```

本门不运行任何容器、部署或服务。

## 7. Closed / Forbidden Routes

```text
WHOLE_DISK_WIPE=CLOSED_SUPERSEDED
S19_ALL_ISOLATED_POSITIVE_AND_NEGATIVE_MATRIX=CLOSED_PASS
REPLAY_R2_R4_OLD_TEST_SCRIPTS=FORBIDDEN
R4_EXPAND_ADMIN_INGRESS_ACL=FORBIDDEN
PRECREATE_OR_SHARE_NODE_CREDENTIALS=FORBIDDEN
USE_OLD_MIGRATION_PACKAGE_UNMODIFIED=FORBIDDEN
REPLAY_CONSUMED_S18_S19_GRANTS=FORBIDDEN
GATE_F_BOARD_BEFORE_FUTURE_EXPLICIT_AUTH=FORBIDDEN
```

KF-101 T1 S0 Docker inspect 模板数据丢失已有记录；对 host inspect 应限白名单字段并实际校验。KF-102 S19 R4 夹具误用 admin，通过 R5 来源正确的产品节点角色修正，旧 ACK 未被复原。不新造额外验收框架。

## 8. Authorization Ledger

```text
AUTHORIZATION=S14_REAL_DYNSEC_ADMIN_INITIALIZATION
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=S18_REAL_RECEIVE_DENY_PROMOTION

AUTHORIZATION=S18_REAL_DEFAULT_RECEIVE_DENY_PROMOTION
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=S19_THROWAWAY_TESTS_AND_EXACT_TEMP_CLEANUP
CLAIMED=true
CONSUMED=true
RESULT=R3_R5_R6A_R6B_PASS_WITH_R2_R4_HISTORICAL_FAILED
REPLAY_PERMITTED=false
SUPERSEDED_BY=S19_ISOLATED_FINAL_CLOSED_PASS

AUTHORIZATION=S20_SOURCE_AND_T1_HOST_READONLY_PREFLIGHT
CLAIMED=false
CONSUMED=false
RESULT=NOT_EXECUTED
REPLAY_PERMITTED=NOT_APPLICABLE_READONLY
SUPERSEDED_BY=NONE

PROPOSED_AUTHORIZATION=PRODUCTION_THREE_SERVICE_IDENTITY_CREATE
GRANTED=false
CLAIMED=false
CONSUMED=false
RESULT=NOT_AUTHORIZED
REPLAY_PERMITTED=false

PROPOSED_AUTHORIZATION=START_PRODUCTION_BROKER_TLS_8883
GRANTED=false
CLAIMED=false
CONSUMED=false
RESULT=NOT_AUTHORIZED
REPLAY_PERMITTED=false

PROPOSED_AUTHORIZATION=GATE_F_FIRST_PHYSICAL_PAIR
GRANTED=false
CLAIMED=false
CONSUMED=false
RESULT=NOT_AUTHORIZED
REPLAY_PERMITTED=false
```

前期操作批准均为各自有限门的已消费授权；S20 的只读预检不隐含生产 mutation 或板卡使用许可。

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
LIVE_RUNTIME_MUTATION=false
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
ROLLBACK_EXECUTION=false
SECOND_ATTEMPT_ALLOWED=false
```

未来任何真实 DynSec 写入门必须先新建精确 prechange 私有快照、验证 admin 与默认拒绝、证明只删除本事务创建的对象，失败不确定时先 inventory/reconcile；旧 S18 私有备份只是历史安全锚点，**不是自动替代未来最新现场快照**。如回退失败，`ROLLBACK_INCOMPLETE=true`、`MANUAL_RECOVERY_REQUIRED=true`、STOP，不擅自重试。

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
GATE_MODE=SOURCE_AND_T1_RUNTIME_READ_ONLY
PRODUCTION_MUTATION=false
BOARD_ACCESS=false
```

### 10.1 Purpose

只读确认三类账号的生成、DynSec 写入计划、独立私有密码文件持久保存、容器运行 UID/GID、只读挂载与真实消费者配置是否全链路对应，特别是 fresh HA MQTT 凭据保存和使用方式。输出可执行设计结论与**是否具备申请下一门授权条件**，不立即执行下一门。

### 10.2 Frozen inputs

```text
MAIN_EXACT_SHA=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
PR=541_OPEN_DRAFT
SOURCE=service_identity_plan.py;dynsec_plan.py;dynsec_api.py;config.py
TARGET_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
TARGET_BACKUP_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
TARGET_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
```

### 10.3 Required proof / operations

1. GitHub fresh main/PR compare、当前 state/index、S19/S20、KNOWN_FAILURES、主线配置源码、真正 fresh 部署包绑定。
2. T1 只读检验 Armbian/SSH/Docker、无生产容器、两个隔离网络、45 原卷、ingress guard 生效且末尾 DROP、无主机 8883/18883 监听、三个冻结文件 SHA。不能将过往现场事实冒充 fresh SSH 核验。
3. 查清三账号的 Username/Client ID/角色 ACL、密码生成和存储责任；Manager/Provisioning **不同文件**各自 owner 0600 / 只读容器路径及运行消费者；HA MQTT 真实插件/运行时从哪里读取自己独立的凭据，重建如何继续使用。
4. 逐条标识 `PROVEN`、`UNKNOWN`、`SOURCE_GAP`、`RUNTIME_GAP`；不读明文、不记录 ENV VALUE、不先生成正式口令；给未来原子写入与失败恢复建议（仅设计）。
5. 出具结构化 closure 后 STOP。

### 10.4 PASS / FAIL

```text
PASS_CONDITION=FRESH_SOURCE_AND_HOST_GUARDS_MATCH_AND_ALL_THREE_PASSWORD_CONSUMERS_EXACTLY_PROVEN
S20_PREFLIGHT_RESULT=PASS
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=true
PRODUCTION_MUTATION=false
STOP=true

FAIL_CONDITION=ANY_AUTHORITY_DRIFT_OR_UNVERIFIED_CONSUMER_UID_MOUNT_PERSISTENCE_OR_GUARD
S20_PREFLIGHT_RESULT=FAIL_CLOSED
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
PRODUCTION_MUTATION=false
STOP=true
```

如无法访问主机，`S20_PREFLIGHT_RESULT=STOP_REMOTE_EVIDENCE_UNAVAILABLE`，向用户请求最小 Mac SSH 只读取证。不能将“不知道”变为 PASS。

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
GITHUB_WRITE_INSIDE_S20_EXECUTION=false
```

ALLOWED：只读 GitHub fetch/compare；T1 通过操作者 private SSH 执行有限的 service status、Docker metadata 白名单解析、私有文件权限 stat / 三文件 SHA、监听端口与 ingress guard 顺序检查；敏感内容只保留布尔、计数、摘要与源路径，不得输出真实密码或私钥。

FORBIDDEN：创建任何生产账号或秘密文件、运行 Docker 容器、拉镜像、Compose up、systemctl start/stop/restart/reload、修改 iptables、开放 8883、编辑 TLS/证书/默认 ACL、读取密码/DynSec 原文、删卷、变更 Armbian、访问实板 USB/串口/Flash/NVS/RF、合并 PR。未来 GitHub 结果归档只在本只读 gate 停止、经高阶模型裁决后执行独立文档操作。

## 12. Codex DSL Execution Contract

```text
ROLE=LOW_ORDER_EXECUTOR

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required.
Mechanically compile into minimum commands using installed tools.
No comments in delivered shell code blocks.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
AUTO_RETRY=false

=====================================================
0. GATE / AUTHORIZATION
=====================================================
GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
AUTHORIZATION=READ_ONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
ON_DRIFT=STOP

=====================================================
1. SOURCE AUTHORITY
=====================================================
Read handoff standard/template at exact frozen standard commit.
Read current handoff and PR-branch CURRENT_STATE, INDEX, S19,
S20, software-only redeploy authority, KNOWN_FAILURES.
Resolve current main SHA; expect d423211b... .
Read current PR 541 head/branch/Draft status and compare with main.
Fetch exact main role plan, DynSec API, config, Compose/deploy source.
Check that this contract still matches current authority; STOP on drift.

=====================================================
2. T1 LIVE SAFE STATE
=====================================================
Resolve private operator-provided T1 SSH target; do not record IP.
Only read status of Docker/network/SSH and guard services.
Use safe whitelisted docker ps/inspect metadata; never dump raw env,
whole sensitive inspect JSON, or credential-bearing argv.
Confirm 45 Docker volumes by count and exact set without deletion;
confirm n3wfc4-private and n3wfc4-services exist and are empty.
Read only iptables INPUT/DOCKER-USER jump order and ingress last DROP.
Read only listening port ownership for 8883/18883.
Run sha256sum only on frozen production config/DynSec/backup.
Use stat for modes/owners, do not cat any secret.
If SSH unavailable request redacted read-only Mac output, STOP.

=====================================================
3. THREE CONSUMER HANDOFF CHECK
=====================================================
For each: provisioning, manager, homeassistant:
Bind username/client-id/role/ACL from exact source plan.
Resolve planned independent secret generation and storage ownership.
Find real fresh deployment image, process UID/GID, readonly file mount,
private file mode 0600, target program/integration consumer and
recreate/boot persistence. Source-only support is NOT runtime proof.
For Manager verify GH_MQTT_PASSWORD_FILE and GH_MQTT_CLIENT_ID
with GH_MQTT_USERNAME and no inline GH_MQTT_PASSWORD.
For Provisioning verify independent GH_N3W_PROVISIONING_PASSWORD_FILE
and associated username/client ID.
For HA identify real MQTT integration path and credential consumer.
Mark UNKNOWN for any unsupported or absent deployment binding.
Do not generate or inspect password values.

=====================================================
4. READONLY DESIGN DISPOSITION
=====================================================
Ensure future production creation has exactly three service clients.
No node credentials until Gate F.
Describe proposed fresh snapshot, account/role transaction ownership,
secret handoff, ambiguity/reconciliation and independent Broker TLS start
gate. None are authorized for execution now.

=====================================================
5. HARD STOP
=====================================================
Produce Section 13 structured closure only.
PASS only if all required current runtime binds proven; otherwise fail.
Never automatically execute subsequent gate.
STOP=true
```

## 13. Expected Closure

```text
=== N3W T1 S20 SERVICE CREDENTIAL HANDOFF READONLY CLOSURE ===
EXECUTION_ID=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
AUTHORIZATION=READ_ONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
MAIN_EXACT_REBIND=
PR541_STATE_AND_EXACT_HEAD=
SOURCE_PLAN_BOUND=
T1_HOST_FRESH_READONLY_REBIND=
ARMBIAN_SSH_DOCKER_GUARDS_PRESERVED=
DOCKER_VOLUMES_45_PRESERVED=
TWO_PROJECT_NETWORKS_EMPTY=
GUARD_FIRST_JUMPS_LAST_DROP=
REAL_DYNSEC_SHA_MATCH=
S18_BACKUP_SHA_MATCH=
BROKER_CONFIG_SHA_MATCH=
BROKER_STOPPED=
HOST_8883_NOT_PUBLISHED=
MANAGER_ROLE_AND_CLIENT_ID_BOUND=
MANAGER_RUNTIME_UID_SECRET_FILE_MOUNT_CONSUMER=
PROVISIONING_ROLE_AND_CLIENT_ID_BOUND=
PROVISIONING_SEPARATE_SECRET_FILE_CONSUMER=
HA_ROLE_AND_CLIENT_ID_BOUND=
HA_FRESH_MQTT_SECRET_FILE_AND_INTEGRATION_CONSUMER=
SECRETS_READ=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
S20_PREFLIGHT_RESULT=PASS|FAIL_CLOSED|STOP_REMOTE_EVIDENCE_UNAVAILABLE
S20_FAILURE_CLASS=NONE|SOURCE|RUNTIME|SECRET_CONSUMER|GUARD|TOOLING|UNKNOWN
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false|true
NEXT_ROUTE=RETURN_TO_HIGH_LEVEL_MODEL
STOP=true
=== END ===
```

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=S20_REAL_THREE_SERVICE_SECRET_HANDOFF_DESIGN_AND_EXPLICIT_AUTHORIZATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AFTER_FAIL_NEXT_STAGE=S20_SCOPED_MISSING_CONSUMER_OR_DEPLOYMENT_BINDING_REVIEW
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

PASS 只是可提出下一门明确授权，不是创建服务账号的通行证。FAIL 后高阶模型判别是否产品/部署/测试缺口，不能绕过验证继续写正式数据库。

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
KF_ID=KF-102
DOMAIN=PHYSICAL_HARNESS
SYMPTOM=S19_R4_MANAGER_INGRESS_FAILED_WITH_ADMIN_TEST_PUBLISHER
ROOT_CAUSE=R4_FIXTURE_ADMIN_LACKS_ORDINARY_INGRESS_PUBLISH_PERMISSION
FIX_OR_GUARD=USE_SOURCE_PLAN_LEGAL_NODE_TEST_PUBLISHER_AND_SAFE_REASON_ORACLE
STATUS=RESOLVED
```

PR #541 分支的 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 已更新 KF-102。R2 原始失败具体步骤及 ACK 仍 UNKNOWN，不能强行归因为 KF-102；旧记录不删除。KF-101 为历史 S0 Docker inspect 模板读数失败，已具备 JSON allowlist 只读取证替代路线。

## 16. New Chat Start Prompt

将以下内容复制到新对话：

```text
阅读《docs/development/N3W_T1_S20_PRODUCTION_SERVICE_CREDENTIAL_HANDOFF_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261010.md》。

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #541
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_S19_ISOLATED_SERVICE_IDENTITY_INIT_PREEXECUTION_20261010.md
- docs/development/N3W_T1_S20_PRODUCTION_SERVICE_CREDENTIAL_HANDOFF_READONLY_PREFLIGHT_20261010.md
- docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md

继续“温室环境监测系统（ESP32-C6）”N3-W。

每次回复先写：
主线任务：N3-W 温室环境监测系统产品化与首次配对验收
支线任务：保留 Armbian，全新部署 T1 温室软件
当前任务：S20 三服务凭据交付与生产部署只读预检

必须承认：
S19 隔离权限验收 CLOSED_PASS；
旧 R2/R4 失败作为历史证据保留，R4 错误管理员发送端是测试夹具问题；
正式 T1 仍只有 DynSec 管理员，三生产服务账号未创建；
Broker 没有启动，宿主 8883 没开放，45 卷及安全防护保持；
S20 尚未完整执行，不得宣称 HA/Manger/Provisioning 的生产密码交付闭环；
保留 Armbian，不做整机擦盘、不碰 ESP32-C6 实板。

EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

只进入：
NEXT_ONE_GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT

先完成 exact GitHub 和 T1 的只读 fresh rebind；只查 Manager/Provisioning/HA 三份独立密码文件从安全生成、保存、只读容器挂载到实际消费者的闭环与部署路径。Codex 机械编译 handoff DSL 即可，不默认生成大执行器。没有明确新授权，不得创建正式账号/密码、运行 Broker、开放 8883、修改 T1、合并 PR 或触板。先读后判，首处异常 STOP，不重放旧授权。用具体中文报告，Mac Terminal 为主要命令工具，命令块不写注释。
```

## 17. Final Frozen State

```text
CURRENT_STAGE=S19_ISOLATED_SERVICE_IDENTITY_ACL_ACCEPTANCE_CLOSED_PASS
CURRENT_STOP_POINT=S20_PENDING_NOT_EXECUTED_IN_PREVIOUS_CHAT
SOURCE_DEFECT_PROVEN=false
R4_TEST_FIXTURE_DEFECT_PROVEN=true
CURRENT_BLOCKER=THREE_SERVICE_SECRET_HANDOFF_SOURCE_TO_RUNTIME_BINDING_INCOMPLETE
LIVE_SYSTEM_STATE=LAST_REPORTED_ARMBIAN_PRESERVED_NO_PRODUCTION_BROKER_NO_THREE_SERVICE_CLIENTS
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541=OPEN_DRAFT
PR_HEAD_PRE_HANDOFF=0e59ec423f3b94426e98b410cbb6122401f7ad65
NEXT_ONE_GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_STANDARD_VERSION=1.0
```

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
