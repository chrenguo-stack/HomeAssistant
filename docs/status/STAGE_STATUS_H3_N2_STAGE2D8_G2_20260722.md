# H3/N2 Stage 2D-8 G2 专用测试板实板验收状态

- **状态文件版本：** V1.7
- **更新日期：** 2026-07-22
- **权威性：** 本文件是本活动阶段唯一权威 `STAGE_STATUS`
- **阶段状态：** `d2_attempt_inconclusive_waiting_private_summary`
- **当前结论：** `inconclusive`
- **执行门：** `LOCKED_NO_REPLAY`

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
PRODUCTION_ENVIRONMENT_MODIFIED=false
FROZEN_SOURCE_MODIFIED=false
CANDIDATE_REBUILT=false
EVIDENCE_PR=172
PUBLIC_SAFETY_STATUS=passed
```

PR `#166`、`#167`、`#168` 的冻结分支未修改。本证据分支只保存脱敏状态、manifest、L1 证据摘要和 Artifact 索引。

## 2. 范围与禁止事项

本阶段只允许在精确 D2 授权下，对已绑定专用板执行一次目标预检、全片擦除、V64 G2 写入、verify-flash、preboot 64 KiB 回读、一次启动与串口采集、postboot 64 KiB 回读和私有证据收集。仅在进入破坏性边界后发生规定失败时，最多执行一次 locked recovery。

继续禁止：修改或重建冻结候选；`PREPARE_CANDIDATE`、`ACTIVATE_PROFILE`、`CLEANUP_TEST_STATE`；测试密钥、可写 NVS、Wi-Fi、MQTT、Broker、Home Assistant、API、OTA、mDNS；任何 eFuse 读写；启用 Secure Boot 或 Flash Encryption；M401A、T1、Mosquitto、greenhouse-manager 和生产环境操作；Ready、合并或发布。

## 3. 冻结 Artifact 身份

```text
ARTIFACT_ZIP_SHA256=662d9d4d850eea603d5defafb2b3c84a8bc07fae3a4b51229479b2a0a71e8ea9
G2_MERGED_SHA256=a3ff73ddc11115849e160637cd63e2f44c699e595c5c6aa43575f9d7626ed47d
RECOVERY_MERGED_SHA256=5f6ca3024d35dea9b48679a3882a55a20ec2bc67137d6dd58cbf19c2474994ed
PARTITION_BINARY_SHA256=d59f8cff987dee266d2df9340867ff56369c2dfd28c93e12d5a93b10277c2a72
NVS_SEED_SHA256=1f7016fe98cf69ca879a72069e63869863d1a4c8580ba0c8931aef133de3c928
ARTIFACT_MANIFEST_SHA256=bd0b138710c178cc6d166e2eb8ab2e5b419bf167a5ad19c0aaebc9940c6e2561
REPRODUCIBILITY_REPORT_SHA256=325580af692416f3e16c29bee7f14135ce4eaa04026c6441f4e8b794033a3bd1
```

Artifact manifest 继续保持 `gate=LOCKED` 且内部所有执行授权为 `false`。实板权限来自独立的外部 D2 精确单次授权，不修改 Artifact。

## 4. U1 本机 Artifact 校验闭环

```text
U1_RESULT=passed
U1_PRIVATE_LOG_TIMESTAMP_UTC=2026-07-22T09:16:10Z
U1_CONTROLLED_PRIVATE_OUTPUT_SHA256=6930cb6e52ada91f92ccf487c35319856abffd2e2d8ee17fe43641bbb9ce619e
ZIP_SHA256_MATCH=true
ZIP_MEMBER_COUNT=19
SHA256SUMS_CHECKED=18
SHA256SUMS_ALL_MATCH=true
MANIFEST_GATE_LOCKED=true
CLEAN_BUILDS_BYTE_IDENTICAL=true
REPRODUCIBILITY_STATUS=pass
TEST_PARTITION_OFFSET=0x400000
TEST_PARTITION_SIZE=0x10000
TEST_PARTITION_READONLY=true
NVS_SEED_SIZE=65536
BOARD_ACCESSED=false
FLASH_OPERATION_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
```

## 5. D2 精确单次授权与执行尝试

```text
D2_AUTHORIZATION_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-01
D2_AUTHORIZATION_RECEIVED=true
D2_ISSUED_AT=2026-07-22T09:36:29Z
D2_EXPIRES_AT=2026-07-22T11:36:29Z
D2_ONE_SHOT=true
D2_REPLAY_PERMITTED=false
D2_ALLOWED_RECOVERY_COUNT=1
D2_REVIEW_PACKAGE_SHA256=e2bb1271194c5d73219419b3b86dc274ff0f23d183148cdc35e839e252a06d34
D2_EXECUTION_SCRIPT_SHA256=ce5d1018ef0161b02148e8a4f74fdf1873c528b0ad23827b6ef9c6e85054b8ce
D2_COMMAND_GROUP_SHA256=6c2f4407334c936537824437be7b3e350a50547308e1a1e708d532403aac4685
D2_STOP_CONDITIONS_SHA256=8ece74c8065375184b93a533d11f9d6568304472f06ff8b2f46658abbde6962b
D2_AUTHORIZATION_BINDING_SHA256=ebf6efd2419e8373842571a2eeae58eaa2bdb5ba0c0b90585a7e44a806d759d5
D2_AUTHORIZATION_FILE_SHA256=a35fe5ce8b021049f41b6f9062667473549ebc9e70e9450018f3fd9c4e4be50f
D2_EXECUTION_PACKAGE_SHA256=441634f9e029c55db202845857acbad4f7c6f35be053df82bab3d31ffbd5aa13
```

用户执行批量包后返回：

```text
D2_ATTEMPT_TIMESTAMP_UTC=2026-07-22T09:44:26Z
D2_ATTEMPT_RESULT=inconclusive
DESTRUCTIVE_BOUNDARY_ENTERED=false
PHYSICAL_ERASE_PERFORMED=false
G2_FLASH_PERFORMED=false
VERIFY_FLASH_PERFORMED=false
PREBOOT_READBACK_PERFORMED=false
G2_BOOTED=false
POSTBOOT_READBACK_PERFORMED=false
RECOVERY_PERFORMED=false
RECOVERY_COUNT=0
EFUSE_COMMAND_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
PRIVATE_EVIDENCE_ARCHIVE_SHA256=366ac51f1c754431d6ec1d7bffc1e76b9b8df948b02af79603953599bc37c460
```

该尝试在破坏性边界前关闭，未擦除、未写入、未 verify-flash、未回读、未启动 G2、未执行 recovery。当前摘要未包含 `failure_class` 与 `failure_message`，因此根因尚未闭环。

为遵守不可重放原则，该 D2 授权从治理层面标记为 `attempted_inconclusive_retired`；无论本机 consumed marker 是否建立，均禁止再次运行原授权文件或原批量命令。完成私有摘要诊断后，如仍需实板执行，必须重新生成新的 D2 请求 ID、授权文件和一次性执行包。

## 6. S0—S8 状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| S0 基线确认 | `passed` | 冻结 source SHA、V64 Artifact、证据分支和禁止事项已确认 |
| S1 范围与验收设计 | `passed` | 验收项、停止条件、双队列、证据分层已冻结 |
| S2 非实板证据准备 | `passed` | 脱敏 manifest、Artifact 索引、证据模板已建立 |
| S3 本地 Preflight | `passed` | 助手独立复核和用户 U1 均通过 |
| S4 GitHub CI | `passed` | Draft PR #172 公共仓库安全门通过 |
| S5 候选冻结 | `passed` | 仅引用 PR #168 的不可变 V64，不重建候选 |
| S6A 隔离验证 | `passed` | host fault matrix、边界门和可复现性通过 |
| S6B 实板验收 | `inconclusive_pre_destructive` | D2 尝试在破坏性边界前 fail closed；等待私有摘要诊断 |
| S7 归档/发布 | `not_run` | 禁止 Ready、合并和发布 |
| S8 阶段关闭 | `not_run` | 阶段保持打开，等待根因和后续 D2 决策 |

## 7. 决策门

```text
D1_SCOPE_DECISION=resolved
D2_PHYSICAL_EXECUTION_AUTHORIZATION=attempted_inconclusive_retired
D3_RISK_WAIVER=not_required
D4_READY_MERGE_RELEASE=prohibited
```

当前不请求 D3。根因诊断仅读取本机私有证据归档，不连接测试板，不触发 Flash、网络或生产环境操作。

## 8. 助手开发队列

| ID | 状态 | 内容 |
|---|---|---|
| A1 | `done` | 冻结源码、PR #168 与 V64 身份核对 |
| A2 | `done` | Artifact 独立复核 |
| A3 | `done` | 权威状态、manifest、索引和证据模板 |
| A4 | `done` | Draft PR #172 与公共安全门 |
| A5 | `done` | U1、D2 审核包、精确授权和一次性批量包 |
| A6 | `done` | 记录首轮 D2 尝试为破坏性边界前 `inconclusive` |
| A7 | `blocked_on_private_summary` | 等待脱敏 `failure_class`、`failure_message` 和授权消费状态后修复执行链 |

## 9. 用户操作队列

### U6：只读提取私有摘要诊断字段

```text
TASK_ID=U6_STAGE2D8_G2_PRIVATE_SUMMARY_REDACTED_DIAGNOSTIC
STATUS=ready
RISK_CLASS=A
BOARD_ACCESS_REQUIRED=false
FLASH_OPERATION_ALLOWED=false
NETWORK_OPERATION_ALLOWED=false
AUTHORIZATION_REQUIRED=false
EXPECTED_RETURN=redacted diagnostic fields only
```

禁止重放原 D2 授权或再次运行原批量包。

## 10. 实板验收仍需同时成立

- 冻结哈希、目标身份和 Flash 型号容量匹配；
- erase/write/verify/preboot readback 成功；
- preboot 64 KiB 与 seed 逐字节一致；
- 串口包含冻结 boundary、snapshot 和 `stage2d8_g2_probe=pass`，且无失败标志；
- `key_loaded=false`、`wifi=false`、`mqtt=false`、`writes=0`；
- 全部 MQTT session=false，`reboot_required=false`；
- postboot 64 KiB 与 seed、preboot 逐字节一致；
- recovery 未执行，或仅在许可失败条件下准确执行一次；
- eFuse、网络、生产环境操作均未发生；
- 证据完整、脱敏、可追溯。

## 11. 当前结论

```text
STAGE_STATUS=d2_attempt_inconclusive_waiting_private_summary
FINAL_RESULT=inconclusive
U1_HOST_ARTIFACT_VERIFICATION=passed
D2_AUTHORIZATION_RECEIVED=true
D2_AUTHORIZATION_STATUS=attempted_inconclusive_retired
D2_REPLAY_PERMITTED=false
PHYSICAL_EXECUTION_STARTED=true
DESTRUCTIVE_BOUNDARY_ENTERED=false
PHYSICAL_ERASE_PERFORMED=false
G2_FLASH_PERFORMED=false
VERIFY_FLASH_PERFORMED=false
PREBOOT_READBACK_PERFORMED=false
G2_BOOTED=false
POSTBOOT_READBACK_PERFORMED=false
RECOVERY_PERFORMED=false
PRIVATE_EVIDENCE_ARCHIVED=true
PRIVATE_EVIDENCE_ARCHIVE_SHA256=366ac51f1c754431d6ec1d7bffc1e76b9b8df948b02af79603953599bc37c460
L1_PHYSICAL_ATTEMPT_EVIDENCE_COMMITTED=true
PRODUCTION_ENVIRONMENT_MODIFIED=false
```
