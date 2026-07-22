# H3/N2 Stage 2D-8 G2 专用测试板实板验收状态

- **状态文件版本：** V1.4
- **更新日期：** 2026-07-22
- **权威性：** 本文件是本活动阶段唯一权威 `STAGE_STATUS`
- **阶段状态：** `prepared_waiting_d2_authorization`
- **结论状态：** `not_run`
- **执行门：** `LOCKED`

## 1. S0 基线

```text
STAGE=H3/N2 Stage 2D-8 G2 专用测试板实板只读验收执行与证据闭环
REPOSITORY=chrenguo-stack/HomeAssistant
BASE_SHA=6cf37c29311601f4f83238cc8401c81ea7b9a1f0
SOURCE_SHA=6cf37c29311601f4f83238cc8401c81ea7b9a1f0
BRANCH=evidence/h3-n2-stage2d8-g2-physical-acceptance-20260722-v1
FROZEN_SOURCE_PR=168
FROZEN_ARTIFACT_GENERATION=V64
FROZEN_ARTIFACT_NAME=stage2d8-g2-immutable-locked-v64
EXECUTION_GATE=LOCKED
PRODUCTION_ENVIRONMENT_MODIFIED=false
FROZEN_SOURCE_MODIFIED=false
CANDIDATE_REBUILT=false
EVIDENCE_PR=172
PUBLIC_SAFETY_STATUS=passed
```

PR `#166`、`#167`、`#168` 的冻结分支不得修改。本证据分支从准确的冻结源码提交创建，只允许保存脱敏状态、manifest、L1 证据摘要和 Artifact 索引。

## 2. 范围

### 必须完成

1. V64 Artifact 本机完整校验；
2. 私有目标身份与安全状态预检；
3. 收到一次精确、不可重放的 D2 授权；
4. 一次批量执行擦除、G2 写入、verify-flash、preboot 回读、串口采集、postboot 回读和证据收集；
5. 仅在规定失败条件下允许一次锁定 recovery；
6. 形成脱敏 L1 证据闭环和 `passed|failed|inconclusive` 结论。

### 明确不做

- 不修改、重建或替换冻结源码与 V64 Artifact；
- 不执行 `PREPARE_CANDIDATE`、`ACTIVATE_PROFILE`、`CLEANUP_TEST_STATE`；
- 不加载测试密钥，不打开可写 NVS；
- 不启用 Wi-Fi、MQTT、Broker、Home Assistant、API、OTA 或 mDNS；
- 不读写 eFuse，不启用 Secure Boot 或 Flash Encryption；
- 不操作 M401A、T1、Mosquitto、greenhouse-manager 或生产环境；
- 不将 Draft PR 标记 Ready，不合并，不发布。

## 3. 冻结 Artifact 身份

```text
ARTIFACT_ZIP_SHA256=662d9d4d850eea603d5defafb2b3c84a8bc07fae3a4b51229479b2a0a71e8ea9
G2_MERGED_SHA256=a3ff73ddc11115849e160637cd63e2f44c699e595c5c6aa43575f9d7626ed47d
RECOVERY_MERGED_SHA256=5f6ca3024d35dea9b48679a3882a55a20ec2bc67137d6dd58cbf19c2474994ed
G2_APPLICATION_SHA256=e5a707753117819f7e2a71d78d7c5813f6a5932f52b6d92047bc36c525eb92df
RECOVERY_APPLICATION_SHA256=3c8165e03077213c5f0f64ac66fecec0a964bdb8761f785b1409ffff66e97fa2
PARTITION_BINARY_SHA256=d59f8cff987dee266d2df9340867ff56369c2dfd28c93e12d5a93b10277c2a72
NVS_SEED_SHA256=1f7016fe98cf69ca879a72069e63869863d1a4c8580ba0c8931aef133de3c928
ARTIFACT_MANIFEST_SHA256=bd0b138710c178cc6d166e2eb8ab2e5b419bf167a5ad19c0aaebc9940c6e2561
REPRODUCIBILITY_REPORT_SHA256=325580af692416f3e16c29bee7f14135ce4eaa04026c6441f4e8b794033a3bd1
```

Artifact manifest 固定为 `gate=LOCKED`，所有执行授权均为 `false`；V64 两次 clean build 的 bootloader、partition 和 application 均逐字节一致。

## 4. U1 本机 Artifact 校验闭环

用户于受控本机执行批量包 `U1_STAGE2D8_G2_V64_HOST_ARTIFACT_VERIFY_V1`，完整结果满足：

```text
BOARD_ACCESSED=false
FLASH_OPERATION_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
ZIP_SHA256_MATCH=true
ZIP_MEMBER_COUNT=19
ZIP_MEMBER_SET_MATCH=true
SHA256SUMS_CHECKED=18
SHA256SUMS_ALL_MATCH=true
MANIFEST_SCHEMA_MATCH=true
MANIFEST_SOURCE_SHA_MATCH=true
MANIFEST_GATE_LOCKED=true
MANIFEST_TARGET_MATCH=true
MANIFEST_FLASH_AUTHORIZED=false
MANIFEST_MQTT_AUTHORIZED=false
MANIFEST_PERSISTENT_WRITE_AUTHORIZED=false
MANIFEST_READ_ONLY_PROBE_AUTHORIZED=false
MANIFEST_TEST_PARTITION_PRE_POST_READBACK_AUTHORIZED=false
MANIFEST_WIFI_AUTHORIZED=false
CLEAN_BUILDS_BYTE_IDENTICAL=true
REPRODUCIBILITY_STATUS=pass
TEST_PARTITION_OFFSET=0x400000
TEST_PARTITION_SIZE=0x10000
TEST_PARTITION_READONLY=true
NVS_SEED_SIZE=65536
STAGE2D8_G2_V64_HOST_ARTIFACT_VERIFICATION=PASS
```

```text
U1_RESULT=passed
U1_PRIVATE_LOG_TIMESTAMP_UTC=2026-07-22T09:16:10Z
U1_CONTROLLED_PRIVATE_OUTPUT_SHA256=6930cb6e52ada91f92ccf487c35319856abffd2e2d8ee17fe43641bbb9ce619e
U1_RAW_LOCAL_PATHS_IN_GIT=false
```

该摘要只保存结论与哈希；完整输出和本机路径保留在受控私有证据中。

## 5. S0—S8 状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| S0 基线确认 | `passed` | 冻结 source SHA、V64 Artifact、分支和禁止事项已确认 |
| S1 范围与验收设计 | `passed` | 验收项、停止条件、双队列和证据分层已冻结 |
| S2 非实板证据准备 | `passed` | 脱敏 manifest、Artifact 索引和证据模板已建立 |
| S3 本地 Preflight | `passed` | 助手独立复核与用户 U1 本机完整校验均通过 |
| S4 GitHub CI | `passed` | Draft PR #172 已建立；证据分支公共仓库安全门通过 |
| S5 候选冻结 | `passed` | 继承且只引用 PR #168 的不可变 V64，不重新生成候选 |
| S6A 隔离验证 | `passed` | V64 CI 的 host fault matrix、边界门和可复现性已通过 |
| S6B 实板验收 | `wait_authorization` | U1 已通过；等待 D2 精确单次授权，尚未触碰实板 |
| S7 归档/发布 | `not_run` | 禁止 Ready、合并和发布 |
| S8 阶段关闭 | `not_run` | 等待实板结论和证据闭环 |

## 6. 决策门

```text
D1_SCOPE_DECISION=resolved
D2_PHYSICAL_EXECUTION_AUTHORIZATION=pending
D3_RISK_WAIVER=not_required
D4_READY_MERGE_RELEASE=prohibited
```

D2 必须绑定受控私有目标指纹、私有串口、source SHA、ZIP/G2/recovery SHA、完整命令组、停止条件、一次 recovery 范围、有效期和不可重放标志。D2 未收到前，擦除、写入、verify-flash、Flash 回读和运行实板继续禁止。

## 7. 助手开发队列

| ID | 状态 | 内容 |
|---|---|---|
| A1 | `done` | 核对冻结源码提交、PR #168 与 V64 Artifact 身份 |
| A2 | `done` | 独立下载并校验 ZIP、18 项 `SHA256SUMS`、manifest 与可复现性证据 |
| A3 | `done` | 建立单一权威状态文件、脱敏 Artifact 索引和结构化证据模板 |
| A4 | `done` | Draft PR #172 已建立并保持 Draft；公共仓库安全门通过 |
| A5 | `ready_at_d2` | U1 已审核通过；准备 D2 精确单次授权与完整批量执行包 |
| A6 | `blocked` | 等待实板批量包结果后形成 L1 结论和阶段关闭材料 |

## 8. 用户操作队列

### U1：V64 本机 Artifact 校验

```text
TASK_ID=U1_STAGE2D8_G2_V64_HOST_ARTIFACT_VERIFY
STATUS=done
RESULT=passed
RISK_CLASS=A
CAN_RUN_IN_PARALLEL=true
AUTHORIZATION_REQUIRED=false
CONTROLLED_PRIVATE_OUTPUT_SHA256=6930cb6e52ada91f92ccf487c35319856abffd2e2d8ee17fe43641bbb9ce619e
```

### U5：精确授权后的完整实板批量包

```text
TASK_ID=U5_STAGE2D8_G2_ONE_SHOT_PHYSICAL_ACCEPTANCE
STATUS=wait_authorization
RISK_CLASS=D
CAN_RUN_IN_PARALLEL=false
DEPENDS_ON=U1 passed + exact D2 authorization
ESTIMATED_DURATION=10-20 minutes
AUTHORIZATION_REQUIRED=true
EXPECTED_RETURN=complete machine-readable summary plus controlled private evidence archive
```

## 9. 实板验收必须同时成立

- 冻结哈希全部匹配；
- 私有目标身份、安全状态、Flash 型号与容量匹配；
- erase/write/verify/preboot readback 成功；
- preboot 64 KiB 与 seed 逐字节一致；
- 串口出现所有冻结成功标志且无失败标志；
- `key_loaded=false`、`wifi=false`、`mqtt=false`、`writes=0`；
- `active_session=false`、`candidate_session=false`、`probe_session=false`；
- `reboot_required=false`、`stage2d8_g2_probe=pass`；
- postboot 64 KiB 与 seed、preboot 逐字节一致；
- 未执行 recovery，或 recovery 仅在许可失败条件下准确执行一次；
- 生产环境保持未修改；
- 证据完整、脱敏、可追溯。

## 10. 当前结论

```text
STAGE_STATUS=prepared_waiting_d2_authorization
FINAL_RESULT=not_run
U1_HOST_ARTIFACT_VERIFICATION=passed
D2_AUTHORIZATION_RECEIVED=false
PHYSICAL_ERASE_PERFORMED=false
G2_FLASH_PERFORMED=false
VERIFY_FLASH_PERFORMED=false
PREBOOT_READBACK_PERFORMED=false
G2_BOOTED=false
POSTBOOT_READBACK_PERFORMED=false
RECOVERY_PERFORMED=false
PRIVATE_EVIDENCE_ARCHIVED=true
L1_U1_EVIDENCE_COMMITTED=true
L1_PHYSICAL_EVIDENCE_COMMITTED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```
