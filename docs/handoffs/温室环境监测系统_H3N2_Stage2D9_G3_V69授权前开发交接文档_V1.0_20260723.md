# 温室环境监测系统 H3/N2 Stage 2D-9 G3 V69 授权前开发交接文档

- **文档版本**：V1.0
- **归档日期**：2026-07-23
- **项目仓库**：`chrenguo-stack/HomeAssistant`
- **当前默认分支**：`main`
- **当前 main**：`2a5272546f25b1b29cf1d6682cf1fc14f1c1be83`
- **开发分支**：`feature/h3-n2-stage2d9-g3-prepare-candidate-20260722-v1`
- **Draft PR**：`#174`
- **归档前 PR HEAD**：`17c8034b8b593ed92874f13d913b96ff8fbc3b09`
- **对应阶段**：H3/N2 Stage 2D-9 G3 `PREPARE_CANDIDATE`
- **阶段状态**：V69 Artifact 与用户本机 U1 已通过；精确 D2 审核包已生成；等待下一轮对话授权
- **执行门**：`LOCKED_D2_OPERATOR_DECISION_REQUIRED`
- **当前 D2 请求**：`D2-H3N2-STAGE2D9-G3-V69-20260723-01`
- **下一动作**：在新对话中复核本文件和审核包后，由用户决定是否提交精确 D2 授权
- **文档用途**：结束本轮对话后的开发恢复、审计、授权决策和后续实板证据闭环依据

---

## 0. 新会话首条指令模板

新一轮对话上传本文件后，建议直接发送：

```text
阅读《温室环境监测系统_H3N2_Stage2D9_G3_V69授权前开发交接文档_V1.0_20260723.md》，继续推进 H3/N2 Stage 2D-9 G3 V69。

先复核仓库 main、Draft PR #174、当前 PR HEAD、全部 CI、V69 Artifact、V69 U1、私密托管和 D2 审核包状态；不得重放 V67/V68 或任何 Stage 2D-8 D2。

本轮第一个决策门仅为 D2-H3N2-STAGE2D9-G3-V69-20260723-01 的精确授权。用户授权前不得连接测试板、访问串口、执行 Flash、生成授权文件或执行包。授权文本必须与交接文档完全一致；任一 SHA、PR 状态、Artifact、私密托管或 CI 状态变化时立即停止并重新请求授权。

授权后只允许一次 V69 擦除、写入、Flash 校验、自动 hard reset、一次 GH2D9_PREPARE_V2、固件自动重启后一次只读 GH2D9_VERIFY_V2，以及破坏性边界失败后最多一次 locked recovery。无需且禁止按物理 RESET/BOOT。

继续保持 PR #174 为 Draft；未经独立 D4 授权不得 Ready、合并或发布。禁止 Wi-Fi、MQTT、Broker、eFuse、Secure Boot、Flash Encryption、M401A、T1、Home Assistant、Mosquitto、greenhouse-manager 和生产环境操作。

需要我决策或实机执行时通知我；否则持续推进。.py 和 .sh 文件不得复用历史名称。上下文过长时及时归档并输出新的交接文档。
```

---

## 1. 本轮最终结论

本轮从 Stage 2D-8 G2 通过并完成 PR #173 集成后的正式基线继续，完成了 Stage 2D-9 G3 单次 `PREPARE_CANDIDATE` 路径的源码、host 模型、compile-only 固件、不可变 Artifact、用户本机校验、一次失败实板尝试、locked recovery、根因定位、V69 修正链及新的 D2 审核门。

当前结论：

```text
V67_D2_CHAIN=permanently_retired
V68_PHYSICAL_RESULT=failed
V68_RECOVERY=passed_verified
V68_ROOT_CAUSE=confirmed
V69_SOURCE_CORRECTION=passed
V69_ARTIFACT=passed_frozen
V69_USER_HOST_U1=passed
V69_PRIVATE_CUSTODY=installed_preserved_verified
V69_D2_ATTEMPT1=pending_operator_decision
AUTHORIZATION_ISSUED=false
EXECUTION_PACKAGE_GENERATED=false
DEVICE_RECONNECT_AUTHORIZED=false
PR174=open_draft_unmerged
```

本轮没有执行 V69 实板操作，没有签发 V69 授权文件，没有生成 V69 已授权执行包，也没有触碰 eFuse、网络或生产环境。

---

## 2. Git、分支与 PR 状态

### 2.1 正式基线

```text
main=2a5272546f25b1b29cf1d6682cf1fc14f1c1be83
main 来源=PR #173 squash merge
```

PR #173 已按独立 D4 授权完成 Ready 和 squash merge，集成了 Stage 2D-7、Stage 2D-8 G2 源码和脱敏实板证据。该 D4 不包含 Stage 2D-9、发布或删除冻结分支。

### 2.2 当前开发 PR

```text
PR=#174
TITLE=feat(n2): develop Stage2D9 G3 PREPARE_CANDIDATE path
BASE=main
BASE_SHA=2a5272546f25b1b29cf1d6682cf1fc14f1c1be83
BRANCH=feature/h3-n2-stage2d9-g3-prepare-candidate-20260722-v1
ARCHIVE_START_HEAD=17c8034b8b593ed92874f13d913b96ff8fbc3b09
STATE=open
DRAFT=true
MERGED=false
MERGEABLE=true
READY_MERGE_RELEASE_AUTHORIZED=false
```

交接文档自身提交后，PR HEAD 会前移；新对话必须重新读取 PR #174 当前 HEAD，不得仅依赖 `ARCHIVE_START_HEAD`。

### 2.3 冻结分支原则

不得修改、删除或复用以下冻结链：

- Stage 2D-7、Stage 2D-8 G2 的冻结源码与证据分支；
- PR #166、#167、#168、#172 的冻结内容；
- V67、V68 Artifact 与 D2 材料；
- Stage 2D-8 D2 尝试 1～3；
- V68 私有证据归档与 locked recovery 证据。

---

## 3. Stage 2D-9 G3 固定目标和边界

本阶段只验证：将当前空 candidate 状态通过一次受控 `PREPARE_CANDIDATE` 转换为 `PREPARED`，并在自动重启后通过只读检查证明持久状态正确。

```text
ALLOWED_ACTION=PREPARE_CANDIDATE
ACTIVE_GENERATION=0 -> 0
CANDIDATE_GENERATION=0 -> 1
CANDIDATE_STATE=EMPTY -> PREPARED
PARTITION=gh2d8_p2d9
PARTITION_OFFSET=0x400000
PARTITION_SIZE=0x10000
NAMESPACE=gh2d8_s2d9
PREPARE_SCHEMA=GH2D9_PREPARE_V2
VERIFY_SCHEMA=GH2D9_VERIFY_V2
AUTOMATIC_HARD_RESET_TO_BOOT_G3=true
AUTOMATIC_FIRMWARE_RESTART_AFTER_PREPARE=true
MANUAL_RESET_OR_BOOT_REQUIRED=false
MANUAL_RESET_OR_BOOT_AUTHORIZED=false
```

Stage 2D-9 当前不包含：

- `ACTIVATE_PROFILE`；
- `CLEANUP_TEST_STATE`；
- 正式 MQTT 连接；
- Broker 访问；
- eFuse-HMAC provisioning；
- Secure Boot 或 Flash Encryption 变更；
- 生产固件接线；
- Ready、合并或发布。

---

## 4. V67 执行链处置

### 4.1 V67 Artifact 与 U1

V67 Artifact 完成两次 clean build、字节一致性和 host-only U1，但因私密 unlock preimage 未被持久保留，不能继续签发安全执行授权。

### 4.2 D2 尝试记录

```text
D2-H3N2-STAGE2D9-G3-V67-20260722-01=retired_before_authorization
D2-H3N2-STAGE2D9-G3-V67-20260723-02=operator_authorized_but_issuance_failed_closed_retired
AUTHORIZATION_FILE_GENERATED=false
EXECUTION_PACKAGE_GENERATED=false
BOARD_ACCESSED=false
REPLAY_PERMITTED=false
```

V67 全部授权文本、审核包、脚本和私密绑定永久退役。

---

## 5. V68 Artifact、实板失败和 locked recovery

### 5.1 V68 冻结 Artifact

```text
SOURCE_COMMIT=608282bf86fcf8c1d13494437e01f1899d3c494a
ARTIFACT_ZIP_SHA256=3a90f2b1369dafbc5fb0fa20255ab9dc978a335b74d415aa2f51054a3e198c3b
G3_MERGED_SHA256=094d37b01e9ddce1bba26216ffcbb1bae56a3ecbbf075b3e9e3ec57042214ca4
RECOVERY_MERGED_SHA256=54fb10601a0fbf448948d3f7d687281b33e85220c64bcdcabfae896dd3d98a1a
SEED_SHA256=0ea36f26c5048f69b223884a13613fbd645b58c2ce42eafc6f9d9cd55bb089af
```

### 5.2 V68 D2 实板结果

```text
AUTHORIZATION_REQUEST_ID=D2-H3N2-STAGE2D9-G3-V68-20260723-01
AUTHORIZATION_CONSUMED=true
PREFLIGHT_STATUS=passed
ERASE_SUCCESS=true
WRITE_SUCCESS=true
VERIFY_FLASH_SUCCESS=true
PREPREPARE_SEED_MATCH=true
PREPARE_SUCCEEDED=false
VERIFY_COMMAND_SENT=false
FAILURE_STAGE=prepare_serial
FAILURE_MESSAGE_REDACTED=G3 executor emitted fail marker before PREPARE
DESTRUCTIVE_BOUNDARY_ENTERED=true
RECOVERY_PERFORMED=true
RECOVERY_COUNT=1
```

### 5.3 Recovery 闭环

```text
RECOVERY_ERASE=true
RECOVERY_WRITE=true
RECOVERY_VERIFY=true
RECOVERY_SEED_RESTORED=true
RECOVERY_BOOT=true
RECOVERY_MARKER=true
RECOVERY_PARTITION_MATCHES_PREPREPARE=true
RECOVERY_PARTITION_SHA256_EQUALS_SEED=true
FINAL_BOARD_STATE=locked_recovery_seed_restored
PRIVATE_EVIDENCE_ARCHIVE_SHA256=c2a0686e7a52774531c53a674e889f50c8bdef37ee7ea67903dd24c989059321
REPLAY_PERMITTED=false
```

V68 授权已消费并永久退役。测试板恢复后无需再次连接，直到新的 V69 D2 授权签发。

---

## 6. V68 根因和 V69 修正

### 6.1 已确认根因

```text
ROOT_CAUSE=candidate_host_contract_mismatch
V68_CANDIDATE_HOST=stage2d9.invalid
CREDENTIAL_CONTRACT=local_ipv4_or_dot_local
DOT_INVALID_ACCEPTED=false
DOT_LOCAL_ACCEPTED=true
REJECTION_LOCATION=IsolatedDeviceDriver::prepare_candidate bundle.valid
DRIVER_FAILURE=invalid_configuration
MQTT_IN_PREPARE_CALL_PATH=false
```

V68 executor 外层配置允许非空主机名，但正式凭据对象只接受局域网 IPv4 或 `.local` 名称，因此 `stage2d9.invalid` 在持久化写入前被拒绝。

V68 runner 另有独立取证缺陷：异常路径未先保存 PREPARE 串口缓冲。该缺陷不是事务失败根因，但降低了原始证据完整性。

### 6.2 V69 修正

V69 采用唯一组件和构建路径，不修改 V68 冻结文件：

```text
COMPONENT=greenhouse_profile_isolated_device_g3_executor_v69
IMPLEMENTATION_SOURCE_BINDING=f39c3c4c621717a61e0b3cef8b4ec88e59ac13aa
CANDIDATE_HOST=stage2d9.local
PREPARE_SCHEMA=GH2D9_PREPARE_V2
VERIFY_SCHEMA=GH2D9_VERIFY_V2
ACTUAL_PACKAGE_DRIVER_PREPARE_TEST=passed
INVALID_HOST_REJECTED_BEFORE_PERSISTENCE=true
LOCAL_HOST_PREPARE_PATH=passed
MQTT_UNTOUCHED_DURING_PREPARE=true
ATOMIC_SERIAL_EVIDENCE_MATRIX=passed
DEDICATED_COMPILE_ONLY=passed
PRODUCT_BOARD_COMPILE_ONLY=passed
```

串口证据现在在成功、fail marker、超时和 Python 异常路径中均先原子保存，再进入错误处理；runner 区分 host 写入尝试、设备接受和事务成功状态。

---

## 7. 冻结 V69 Artifact

```text
V69_SOURCE_COMMIT=30a15e39164bed4a5b96c50aa5e2e2e6f238c43b
V69_IMPLEMENTATION_SOURCE_BINDING=f39c3c4c621717a61e0b3cef8b4ec88e59ac13aa
V69_WORKFLOW_RUN_ID=29974998633
V69_ARTIFACT_ID=8551229663
V69_ARTIFACT_NAME=stage2d9-g3-immutable-locked-v69
V69_ARTIFACT_ZIP_SHA256=21aa3383a26b66109408576040245dd60c17eb780b65de9847381b73cfb1506b
V69_MANIFEST_SHA256=6719413fc42b43be8dd939d5a7c9333bb04c6f9d143987a89a50d9c89b95c254
V69_G3_MERGED_SHA256=8d99398277ac57680b23791afec67640c5d8e050f474e929cea7724b88b85dbc
V69_RECOVERY_MERGED_SHA256=244f33a9087e41ce8ce2d2b021b9f532336a9774b6ce4c118c28eac955135103
V69_G3_FIRMWARE_SHA256=ab8bc14c7af520ae51d5adb2872db9e8898c1644a87acd93cd42da988cd6a468
V69_RECOVERY_FIRMWARE_SHA256=d9e95857d4de26a18b5beea249cb130eaa303709205a813f4adb6cb4c18e3ab7
V69_SEED_SHA256=0ea36f26c5048f69b223884a13613fbd645b58c2ce42eafc6f9d9cd55bb089af
V69_PARTITION_SHA256=b3964cbbd811d5fa5866638585fa410b53fc74e70a8f92491f43fce0b7a70268
V69_REPRODUCIBILITY_REPORT_SHA256=61dd3f9caa93c778cffa329c14c12f0bc27c62e521dbc81e1153496d9959fb0f
V69_SOURCE_BOUNDARY_REPORT_SHA256=49e1aac91208aa6607a874d4f2aabd7c48ffab1dff96b54cc8d82bc4bc9c4f29
V69_UNLOCK_DIGEST_SHA256=66ce4bd205e8c76159ad839e6f1115e990f18eab2e149427b243e9c5bd541e9e
V69_CLEAN_BUILD_COUNT=2
V69_BYTE_IDENTICAL=true
V69_MEMBER_CHECKSUM_COUNT=19
V69_MEMBER_CHECKSUMS_VERIFIED=true
V69_PRIVATE_MATERIAL_EXCLUSION=passed
V69_ARTIFACT_GATE=LOCKED
```

Artifact 不包含 unlock preimage、私密执行材料、授权文件、串口路径或设备标识。

---

## 8. V69 用户本机 U1 与私密托管

```text
U1_RESULT=passed
U1_TIMESTAMP_UTC=2026-07-23T03:28:26Z
U1_BATCH_PACKAGE_ID=U1_STAGE2D9_G3_V69_ARTIFACT_AND_CUSTODY_VERIFY_V3
U1_PACKAGE_SHA256=8dfd73abf0f3dc1d526658ce9987a71b9d3fd0ab291eacbc08a851928d365782
U1_LAUNCHER_SHA256=48b753a40c9644e57a329b8f96bdf3ce5db911f4e5dda87447896301fe3ffac1
U1_SCRIPT_SHA256=7b5a5cf443ec5f491a411391be27c6bf4ef383280ef2094ecad923d3475b07d5
U1_BINDING_SHA256=d14a741d0cb4be880c8a8b91ee8a5b9571c0b52b2a7c76194598762068610851
PRIVATE_CUSTODY_FILE_SHA256=cfb8164056945869bf9f9e6e340f9e3280ea6d32e3db723df448e4c8a5f4ee5c
PRIVATE_CUSTODY_INSTALLED=true
PRIVATE_CUSTODY_PRESERVED=true
PRIVATE_CUSTODY_UNLOCK_DIGEST_MATCH=true
PRIVATE_CUSTODY_EXECUTION_AUTHORIZED=false
BOARD_ACCESSED=false
SERIAL_ACCESS_ATTEMPTED=false
FLASH_OPERATION_ATTEMPTED=false
EFUSE_COMMAND_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
AUTHORIZATION_FILE_GENERATED=false
EXECUTION_PACKAGE_GENERATED=false
```

私密托管文件仅保留在用户主机受限目录中。其原像、路径和内容不得写入公共 Git、交接文档或聊天输出；新对话只按 SHA-256 复核。

---

## 9. V69 D2 尝试 1 审核门

### 9.1 审核包

```text
AUTHORIZATION_REQUEST_ID=D2-H3N2-STAGE2D9-G3-V69-20260723-01
D2_STATUS=pending_operator_decision
REVIEW_PACKAGE_FILENAME=Stage2D9_G3_V69_D2尝试1精确单次PREPARE实板执行授权审核包_V1.0_20260723.zip
REVIEW_PACKAGE_SHA256=5e7b13dc3e804698f216542b17f4d481a9f8a05285c5c3e6a4475ef1e44e379e
REVIEW_PACKAGE_SIZE=19501
EXECUTION_SCRIPT_SHA256=a24eae615513151437ea1e341259b9cb0ace18a5c8d471788fd22391d9d5083a
LAUNCHER_SHA256=870dfa36eee48b397963cc6cab329b52a0a50940052da4672f2d46e499e07163
COMMAND_GROUP_SHA256=714d6548d15c1fc5c4b8ce11559606e08cd8db36a41bb9e34096adabdf54e9ed
STOP_CONDITIONS_SHA256=d4b93890f952ee37ab95b1abfa45f20681a71cec73c405e1720228e3434f79da
PRIVATE_EXECUTION_MATERIAL_SHA256=1f0924aa6148c66abf94930c51c71fc3a79f4baf75919a821f19dbca5f28292f
PREPARE_COMMAND_SHA256=baaecb7ea5ec3297e338739daa16ca6e92f1a1bab0f87622ddf7af967c7c7bd6
VERIFY_COMMAND_SHA256=3b02cd815b819aeadd3b6357921c5e9d0bcd4a7f7e9ca194dbd83c13fbfcc06e
REVIEW_SELF_TEST=passed
AUTHORIZATION_ISSUED=false
EXECUTION_PACKAGE_GENERATED=false
DEVICE_RECONNECT_AUTHORIZED=false
```

审核包不包含 Artifact、私密托管原像、私密执行材料、授权 JSON 或已签名授权文本，因此不能执行实板操作。

### 9.2 下一轮精确授权文本

新对话复核所有状态不变后，用户可完整复制以下单行文本作出 D2 决策：

```text
我授权执行 D2-H3N2-STAGE2D9-G3-V69-20260723-01。仅允许使用审核包 SHA256=5e7b13dc3e804698f216542b17f4d481a9f8a05285c5c3e6a4475ef1e44e379e 所绑定的 SOURCE_SHA=30a15e39164bed4a5b96c50aa5e2e2e6f238c43b、ARTIFACT_ZIP_SHA256=21aa3383a26b66109408576040245dd60c17eb780b65de9847381b73cfb1506b、G3_MERGED_SHA256=8d99398277ac57680b23791afec67640c5d8e050f474e929cea7724b88b85dbc、RECOVERY_MERGED_SHA256=244f33a9087e41ce8ce2d2b021b9f532336a9774b6ce4c118c28eac955135103、PRIVATE_CUSTODY_FILE_SHA256=cfb8164056945869bf9f9e6e340f9e3280ea6d32e3db723df448e4c8a5f4ee5c、EXECUTION_SCRIPT_SHA256=a24eae615513151437ea1e341259b9cb0ace18a5c8d471788fd22391d9d5083a、LAUNCHER_SHA256=870dfa36eee48b397963cc6cab329b52a0a50940052da4672f2d46e499e07163、COMMAND_GROUP_SHA256=714d6548d15c1fc5c4b8ce11559606e08cd8db36a41bb9e34096adabdf54e9ed、STOP_CONDITIONS_SHA256=d4b93890f952ee37ab95b1abfa45f20681a71cec73c405e1720228e3434f79da、PRIVATE_EXECUTION_MATERIAL_SHA256=1f0924aa6148c66abf94930c51c71fc3a79f4baf75919a821f19dbca5f28292f、PREPARE_COMMAND_SHA256=baaecb7ea5ec3297e338739daa16ca6e92f1a1bab0f87622ddf7af967c7c7bd6、VERIFY_COMMAND_SHA256=3b02cd815b819aeadd3b6357921c5e9d0bcd4a7f7e9ca194dbd83c13fbfcc06e，在已绑定专用测试板、私有串口和冻结 esptool 环境上执行一次 V69 PREPARE_CANDIDATE 以及自动重启后的单次只读 VERIFY；允许单次擦除、写入、校验、自动 hard reset 和私有分区前后回读；无需且禁止操作物理 RESET/BOOT；进入破坏性边界后发生规定失败时最多允许一次 locked recovery，之后终止且不得重试 V69 G3。授权文件有效期严格为签发后2小时，一次性、不可重放。禁止重放任何 Stage2D8、V67 或 V68 D2，禁止第二次 PREPARE 或 VERIFY、ACTIVATE_PROFILE、CLEANUP_TEST_STATE、Wi-Fi、MQTT、Broker、eFuse、Secure Boot、Flash Encryption、M401A、T1、Home Assistant、Mosquitto、greenhouse-manager、Ready、合并和发布；任一绑定、状态或哈希不一致时立即停止。
```

授权文本必须逐字匹配。授权应在新对话中提交，本轮不得签发。

---

## 10. 授权后的唯一允许执行流程

仅在新对话收到精确授权并完成签发后：

```text
A. 复核实际审核包 SHA 和授权文本 SHA
B. 复核 V69 Artifact、U1、私密托管、环境和专用测试板绑定
C. 只读确认测试分区仍等于 V68 recovery 后冻结 seed
D. 单次擦除、写入、Flash 校验 V69 G3
E. esptool 自动 hard reset，禁止物理按键
F. 单次发送 GH2D9_PREPARE_V2
G. PREPARE 成功后固件自动重启
H. 单次发送 GH2D9_VERIFY_V2，只读检查 PREPARED 状态
I. 保存串口、分区前后回读和脱敏 summary
J. 如进入破坏性边界后发生规定故障，最多一次 locked recovery；之后终止
```

预期成功状态：

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate_digest_match=true
active_unchanged=true
mqtt_operation_attempted=false
recovery_performed=false
```

---

## 11. 固定停止条件和禁止项

任一以下情况发生时立即停止，不得临时修补后继续：

- PR #174 不再为 open Draft；
- PR HEAD、Artifact SHA、review package SHA 或任何绑定变化；
- CI 不为 success；
- 私密托管文件缺失或 SHA 不匹配；
- 测试板绑定、USB 或 Flash 身份不匹配；
- 授权过期、已消费或文本不匹配；
- 测试分区不等于冻结 seed；
- 发现第二次 PREPARE/VERIFY 风险；
- 发现 Wi-Fi、MQTT、Broker、eFuse 或生产路径；
- locked recovery 已执行一次后仍失败。

固定禁止：

```text
STAGE2D8_D2_REPLAY=false
V67_D2_REPLAY=false
V68_D2_REPLAY=false
SECOND_PREPARE=false
SECOND_VERIFY=false
MANUAL_RESET_OR_BOOT=false
ACTIVATE_PROFILE=false
CLEANUP_TEST_STATE=false
WIFI=false
MQTT=false
BROKER=false
EFUSE=false
SECURE_BOOT_CHANGE=false
FLASH_ENCRYPTION_CHANGE=false
M401A_OPERATION=false
T1_OPERATION=false
HOME_ASSISTANT_OPERATION=false
MOSQUITTO_OPERATION=false
GREENHOUSE_MANAGER_OPERATION=false
PRODUCTION_OPERATION=false
READY=false
MERGE=false
RELEASE=false
```

---

## 12. 公开证据与私密证据边界

### 12.1 已提交公共仓库

- `docs/status/STAGE_STATUS_H3_N2_STAGE2D9_G3_20260722.md`
- `docs/acceptance/h3-n2-stage2d9-g3-public-manifest-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-acceptance-template-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-d2-authorization-request-index-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-v68-d2-attempt1-failure-l1-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-v68-d2-attempt1-u2-private-detail-l1-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-v68-root-cause-l1-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-v69-artifact-l1-summary-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-v69-private-custody-l1-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-v69-u1-l1-summary-v1.json`
- `docs/acceptance/h3-n2-stage2d9-g3-v69-d2-attempt1-authorization-request-v1.json`
- 本交接文档。

### 12.2 仅用户本机保存

不得上传公共 GitHub：

- V68 私有 evidence tar.gz；
- V69 私密托管原像；
- 私密执行材料；
- 私有 PREPARE/VERIFY 命令正文；
- 原始板卡标识和串口路径；
- 新授权 JSON 和授权执行包；
- 原始串口和 esptool 日志。

公共仓库只保存 SHA-256、脱敏 L1 摘要、状态、索引和边界证明。

---

## 13. 最终 CI 状态

归档前 HEAD `17c8034b8b593ed92874f13d913b96ff8fbc3b09` 的 PR 工作流全部 `completed/success`：

| 工作流 | Run ID | 结果 |
|---|---:|---|
| H3 N2 Stage2D9 G3 PREPARE CI | 29977902221 | success |
| H3 N2 Stage2D9 G3 V69 Correction CI | 29977902229 | success |
| H3 N2 Stage2D9 G3 Compile CI | 29977902183 | success |
| H3 N2 Stage2D9 G3 V69 Artifact CI | 29977902168 | success |
| H3 N2 Stage2D9 G3 V68 Artifact CI | 29977902238 | success |
| H3 N2 Stage2D9 G3 V67 Artifact CI | 29977902202 | success |
| Public repository safety CI | 29977902211 | success |
| F1.0-RC2 firmware CI | 29977902163 | success |
| N1 ESP32-C6 MQTT firmware CI | 29977902177 | success |
| H3 N2 Stage2B3 Pairing Runtime CI | 29977902198 | success |
| greenhouse-manager CI | 29977902210 | success |
| M0 vertical slice CI | 29977902208 | success |
| M2 Dynamic Security CI | 29977902173 | success |

交接文档提交会触发新的 CI；新对话签发 D2 前必须重新确认最新 HEAD 的必需 CI 均为 success。

---

## 14. 后续路线

```text
当前自然断点
V69 D2 精确授权决策
        ↓
授权签发与单次 V69 实板 PREPARE + VERIFY
        ↓
私有证据只读提取与脱敏 L1 闭环
        ↓
Stage 2D-9 G3 物理验收结论
        ↓
独立 D4：PR #174 是否 Ready / squash merge
        ↓
后续阶段另行规划
```

无论 V69 实板结果成功或失败，都必须先完成证据闭环，不得直接进入 Ready、合并、发布、eFuse provisioning 或生产接线。

---

## 15. 交接结论

本轮开发成果已经形成完整且可恢复的自然断点：

- V68 失败、recovery 和根因已闭环；
- V69 修正源码、compile-only、host 合同测试和 Artifact 已冻结；
- V69 用户本机 U1 和私密托管已通过；
- 新 D2 审核包已经生成并自检；
- 当前无有效授权文件、无执行包、无设备操作权限；
- PR #174 保持 Draft；
- 精确授权明确移交到下一轮对话。

新对话的第一项工作不是重新开发、重新构建或连接测试板，而是读取本文件、复核最新 Git/CI 状态，并处理 `D2-H3N2-STAGE2D9-G3-V69-20260723-01` 的操作员决策门。
