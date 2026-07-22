# H3/N2 Stage 2D-8 G2 阶段状态

**状态文件性质：** 本阶段权威状态文件  
**更新日期：** 2026-07-22  
**流程规范：** `docs/process/温室环境监测系统_分阶段开发指导规范_V1.1_20260722.md`  
**流程规范提交：** `ed985368c9a9404b8183a2d661f9b470d6d490cd`

```text
STAGE=H3/N2 Stage 2D-8 G2 dedicated-board physical acceptance preparation
STATUS=prepared_waiting_D2_authorization
BASE_SHA=464770c16eb78ed58bf304c84e2be797c7c86e29
FROZEN_SOURCE_SHA=6cf37c29311601f4f83238cc8401c81ea7b9a1f0
BRANCH=feature/h3-n2-stage2d8-dedicated-board-acceptance-20260722-v60
PR=168
PR_STATE=open_draft
EXECUTION_GATE=LOCKED
PRODUCTION_IO_ATTEMPTED=false
PHYSICAL_FLASH_WRITES_PERFORMED=false
PHYSICAL_FLASH_READBACK_PERFORMED=false
PHYSICAL_NVS_OPENED=false
PHYSICAL_NVS_WRITES_PERFORMED=false
EFUSE_ACCESSED=false
WIFI_CONNECTED=false
MQTT_CONNECTED=false
BROKER_STARTED=false
PRODUCTION_SERVICES_MODIFIED=false
```

## 1. 阶段结论

Stage 2D-8 G2 的源码、host 模型、故障矩阵、compile-only 固件、可复现构建、不可变制品、恢复镜像、manifest、证据格式和执行边界已经完成。

本阶段只完成了实板验收准备，没有执行任何实板擦除、烧录、Flash 回读、物理 NVS 打开、Wi-Fi/MQTT 连接或生产环境操作。

最终候选源码提交 `6cf37c29311601f4f83238cc8401c81ea7b9a1f0` 必须保持冻结。后续文档、证据和执行记录不得修改该提交或覆盖原有 Artifact。

## 2. GitHub 归档索引

| 对象 | 状态 | 标识 |
|---|---|---|
| Stage 2D-7 隔离验收包 | Draft、冻结 | PR #166，head `ab04d31032403869379d976cd9f250fb3f144f7d` |
| Stage 2D-8 隔离设备驱动 | Draft、冻结 | PR #167，head `464770c16eb78ed58bf304c84e2be797c7c86e29` |
| Stage 2D-8 G2 专用板验收制品 | Draft、冻结 | PR #168，head `6cf37c29311601f4f83238cc8401c81ea7b9a1f0` |
| 流程指导规范 V1.1 | 已合并 main | PR #169，merge `ed985368c9a9404b8183a2d661f9b470d6d490cd` |
| 最终 CI | passed | workflow run `29900632869` |
| 公共仓库安全 CI | passed | final G2 source head |

PR #168 必须继续保持 Draft，不得在下一阶段自动标记 Ready、合并或发布。

## 3. 不可变 Artifact

```text
ARTIFACT_NAME=stage2d8-g2-immutable-locked-v64
ARTIFACT_ID=8521935706
ARTIFACT_EXPIRES=2026-08-21T07:42:27Z
ARTIFACT_ZIP_SHA256=662d9d4d850eea603d5defafb2b3c84a8bc07fae3a4b51229479b2a0a71e8ea9
G2_MERGED_SHA256=a3ff73ddc11115849e160637cd63e2f44c699e595c5c6aa43575f9d7626ed47d
RECOVERY_MERGED_SHA256=5f6ca3024d35dea9b48679a3882a55a20ec2bc67137d6dd58cbf19c2474994ed
G2_APPLICATION_SHA256=e5a707753117819f7e2a71d78d7c5813f6a5932f52b6d92047bc36c525eb92df
RECOVERY_APPLICATION_SHA256=3c8165e03077213c5f0f64ac66fecec0a964bdb8761f785b1409ffff66e97fa2
PARTITION_BINARY_SHA256=d59f8cff987dee266d2df9340867ff56369c2dfd28c93e12d5a93b10277c2a72
NVS_SEED_SHA256=1f7016fe98cf69ca879a72069e63869863d1a4c8580ba0c8931aef133de3c928
MANIFEST_SHA256=bd0b138710c178cc6d166e2eb8ab2e5b419bf167a5ad19c0aaebc9940c6e2561
REPRODUCIBILITY_REPORT_SHA256=325580af692416f3e16c29bee7f14135ce4eaa04026c6441f4e8b794033a3bd1
```

下载后的 ZIP 和 `SHA256SUMS` 共 18 个条目已经独立复核，无摘要不一致。

## 4. 候选冻结内容

- ESP32-C6-WROOM-1-N8，8 MB Flash；
- 原生 USB-Serial/JTAG；
- 独立工厂 application；
- 测试专用 `gh2d8_nvs` 分区：offset `0x400000`、size `0x10000`、read-only flag word `0x00000002`；
- NVS seed 仅包含 `gh2d8_seed/format_version=1`；
- 目标 namespace `gh2d8_state` 在 seed 中不存在；
- G2 固件不配置 Wi-Fi、API、OTA、MQTT、mDNS、web server 或 captive portal；
- 未加载测试密钥；
- 未授权任何持久化写操作；
- recovery 固件保持同一冻结分区表和离线边界；
- ESPHome 2026.4.3；
- esptool 5.3.1；
- `esp-idf-nvs-partition-gen==0.2.0`，wheel hash 已固定；
- 固定审计构建时间 `1784678400`；
- 两轮独立 clean build 的 bootloader、partition、application 逐字节一致。

## 5. 私有目标绑定

实板目标为专用备用自制 ESP32-C6-WROOM-1-N8 PCB。目标绑定由芯片、revision、Chip ID、BASE MAC、Flash ID、容量和 USB transport 共同形成。

```text
PRIVATE_BOARD_BINDING_SHA256=d0f2b644ea03b7e4ce121f4f03101c0039816075574c8707ce489fe0f2d31433
PRIVATE_SERIAL_PORT_RECORDED=true
PRIVATE_IDENTIFIERS_COMMITTED_TO_PUBLIC_GIT=false
```

包含真实 MAC 和本地串口路径的授权包属于私有执行材料，不进入公开 Git。其本地归档索引为：

```text
PRIVATE_AUTHORIZATION_PACKAGE=温室环境监测系统_Stage2D8_G2专用测试板单次执行授权包_V1.0_20260722.md
PRIVATE_AUTHORIZATION_PACKAGE_SHA256=78320dd330e738241cb78c12fd015640bb1ba2cff07ebb15cd3d8747c1c1fd67
PRIVATE_AUTHORIZATION_PACKAGE_SIZE=11552
```

## 6. 已通过 Gate

- source-boundary gate：`passed`；
- Stage 2D-8 C++ driver host fault matrix：`passed`；
- clean build A：`passed`；
- clean build B：`passed`；
- byte reproducibility gate：`passed`；
- deterministic NVS generation A/B：`passed`；
- 8-case partition/NVS artifact fault matrix：`passed`；
- immutable package assembly：`passed`；
- manifest、redaction、checksum verification：`passed`；
- Artifact upload：`passed`；
- Public repository safety：`passed`。

## 7. 尚未运行 Gate

- 本机 Artifact 批量校验：`not_run`；
- D2 精确单次实板授权：`not_run`；
- 目标身份二次预检：`not_run`；
- 实板完整擦除：`not_run`；
- G2 镜像烧录与 verify-flash：`not_run`；
- 启动前 64 KiB 测试分区只读回读：`not_run`；
- G2 USB 串口验收：`not_run`；
- 启动后 64 KiB 测试分区只读回读：`not_run`；
- 锁定 recovery：仅失败时允许，当前 `not_run`。

不得把上述未运行项目写成通过或基本通过。

## 8. 助手开发队列

```text
A1 STATUS=done 归档源码、PR、CI、Artifact 与哈希
A2 STATUS=done 冻结 G2/recovery、分区、seed、manifest 与可复现性证据
A3 STATUS=done 生成私有单次授权包和停止/恢复合同
A4 STATUS=done 输出本状态文件和下一轮交接快照
A5 STATUS=blocked 等待 U1 本机校验和 D2 授权后分析实板证据
```

## 9. 用户操作队列

```text
TASK_ID=U1-STAGE2D8-G2-HOST-ARTIFACT-VERIFY
STATUS=ready
RISK_CLASS=A
CAN_RUN_IN_PARALLEL=false
DEPENDS_ON=downloaded immutable V64 ZIP
ESTIMATED_DURATION=5-10 minutes
AUTHORIZATION_REQUIRED=false
EXPECTED_RETURN=single machine-readable PASS or complete failure log

TASK_ID=U2-STAGE2D8-G2-D2-AUTHORIZATION
STATUS=wait_authorization
RISK_CLASS=D
CAN_RUN_IN_PARALLEL=false
DEPENDS_ON=U1 passed and exact command review
ESTIMATED_DURATION=operator decision
AUTHORIZATION_REQUIRED=true
EXPECTED_RETURN=exact one-shot authorization text

TASK_ID=U3-STAGE2D8-G2-PHYSICAL-ACCEPTANCE
STATUS=blocked
RISK_CLASS=D
CAN_RUN_IN_PARALLEL=false
DEPENDS_ON=U1 passed,U2 granted,target identity unchanged
ESTIMATED_DURATION=15-30 minutes
AUTHORIZATION_REQUIRED=true
EXPECTED_RETURN=one complete evidence package, not fragmented outputs

TASK_ID=U4-STAGE2D8-G2-RECOVERY
STATUS=blocked
RISK_CLASS=D
CAN_RUN_IN_PARALLEL=false
DEPENDS_ON=U3 failed after erase and recovery condition triggered
ESTIMATED_DURATION=10-15 minutes
AUTHORIZATION_REQUIRED=true
EXPECTED_RETURN=recovery summary and final board state
```

## 10. 当前禁止事项

- 不得修改或强制移动 PR #166、#167、#168 的冻结源码提交；
- 不得重建 V64 Artifact 并冒充同一候选；
- 不得用 V63 或更早制品替代 V64；
- 不得在未完成 U1 前执行实板命令；
- 不得把一般性“继续推进”解释成 D2 实板写授权；
- 不得重放历史授权；
- 不得读取或烧写 eFuse；
- 不得启用 Secure Boot 或 Flash Encryption；
- 不得连接 Wi-Fi、MQTT、真实 Broker 或 Home Assistant；
- 不得加载测试密钥；
- 不得打开可写物理 NVS；
- 不得执行 `PREPARE_CANDIDATE`、`ACTIVATE_PROFILE` 或 `CLEANUP_TEST_STATE`；
- 不得操作 M401A、T1、Home Assistant、Mosquitto 或 greenhouse-manager；
- 不得把真实 MAC、本地串口路径、密码、令牌或私钥提交到公开仓库；
- 不得将 PR 标记 Ready、合并或发布，除非收到 D4 明确决策。

## 11. 下一阶段唯一入口

下一阶段名称：

> H3/N2 Stage 2D-8 G2 专用测试板实板只读验收执行与证据闭环

下一阶段应从冻结源码提交 `6cf37c29311601f4f83238cc8401c81ea7b9a1f0` 创建新的唯一命名证据分支，不得修改原候选分支。推荐名称：

```text
evidence/h3-n2-stage2d8-g2-physical-acceptance-20260722-v1
```

在 U1 和 D2 完成前，下一阶段只允许读取、核对、生成脱敏执行 manifest 和证据模板，不允许任何实板写操作。

## 12. 阶段效率记录

```text
BRANCH_COUNT=1 primary development branch plus 1 archive-only branch required to preserve frozen candidate
CANDIDATE_GENERATION_COUNT=1 final V64 candidate; V63 retained only as rejected checkpoint
REAL_MACHINE_RUN_COUNT=0
ROLLBACK_COUNT=0
USER_TASK_COUNT=4
USER_TASKS_COMPLETED=0
BATCH_PACKAGE_COUNT=1 private combined host/preflight/flash/readback/evidence/recovery package
PARALLEL_USER_TASK_COUNT=0
SERIAL_COMMAND_ROUND_COUNT=0
USER_WAIT_ONLY_ROUND_COUNT=0 after package preparation
PRODUCTION_IO_ATTEMPTED=false
WRITES_PERFORMED=false
```
