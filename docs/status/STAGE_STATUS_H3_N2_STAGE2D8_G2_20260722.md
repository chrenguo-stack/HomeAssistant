# H3/N2 Stage 2D-8 G2 专用测试板实板验收状态

- **状态文件版本：** V1.9
- **更新日期：** 2026-07-22
- **权威性：** 本文件是本活动阶段唯一权威 `STAGE_STATUS`
- **阶段状态：** `prepared_waiting_d2_attempt2_authorization`
- **当前结论：** `inconclusive`
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
FROZEN_SOURCE_MODIFIED=false
CANDIDATE_REBUILT=false
EVIDENCE_PR=172
PRODUCTION_ENVIRONMENT_MODIFIED=false
```

PR `#166`、`#167`、`#168` 的冻结分支未修改。本阶段继续只维护上述唯一证据分支；Git 只保存脱敏 L1 摘要、manifest、状态和索引。

## 2. 范围与禁止事项

目标仍为：在精确、不可重放的 D2 授权下，对已绑定专用板完成目标预检、全片擦除、V64 G2 写入、verify-flash、preboot 64 KiB 回读、一次串口证据启动、postboot 64 KiB 回读和私有证据闭环。

继续禁止：修改或重建冻结候选；`PREPARE_CANDIDATE`、`ACTIVATE_PROFILE`、`CLEANUP_TEST_STATE`；测试密钥、可写 NVS、Wi-Fi、MQTT、Broker、Home Assistant、API、OTA、mDNS；任何 eFuse 读取或写入；启用 Secure Boot 或 Flash Encryption；M401A、T1、Mosquitto、greenhouse-manager 和生产环境操作；Ready、合并或发布。

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

Artifact manifest 继续保持 `gate=LOCKED`，其内部所有执行授权均为 `false`。外部 D2 不修改 Artifact。

## 4. U1 本机 Artifact 校验

```text
U1_RESULT=passed
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

## 5. D2 尝试 1：已退役

```text
D2_ATTEMPT1_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-01
D2_ATTEMPT1_RESULT=inconclusive
D2_ATTEMPT1_GOVERNANCE_STATUS=attempted_inconclusive_retired
D2_ATTEMPT1_REPLAY_PERMITTED=false
FAILURE_CLASS=RuntimeError
FAILURE_MESSAGE_REDACTED=command failed: version
FAILURE_STAGE=local_esptool_version_preflight
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

尝试 1 在本机工具检查处 fail closed。当前没有板卡、固件、Artifact 或 Flash 失败证据。原授权文件、执行包和命令组永久禁止重放。

## 6. U7 根因诊断

```text
U7_RESULT=passed
U7_SCRIPT_VERSION=V3
PYTHON_VERSION=3.11.9
DISTRIBUTION_ESPTOOL_VERSION=not_installed
DISTRIBUTION_PYSERIAL_VERSION=not_installed
DISTRIBUTION_CLICK_VERSION=not_installed
ESPTOOL_IMPORT=false
ESPTOOL_IMPORT_EXCEPTION_CLASS=ModuleNotFoundError
MODULE_VERSION_COMMAND_RETURN_CODE=1
MODULE_HELP_COMMAND_RETURN_CODE=1
ESPTOOL_CONSOLE_PRESENT=false
ORIGINAL_D2_REPLAYED=false
BOARD_ACCESSED=false
SERIAL_ACCESS_ATTEMPTED=false
FLASH_OPERATION_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
```

根因确认：尝试 1 所绑定的原开发虚拟环境没有安装 esptool、pyserial 或 click。

## 7. U8 独立 esptool 环境

```text
U8_RESULT=passed
U8_BATCH_PACKAGE_ID=U8_STAGE2D8_G2_ESPTOOL_ENVIRONMENT_PREPARE_V2
U8_SCRIPT_SHA256=d311c5705fc03152aa6def8d16ce3a13aba1f5e94cee8a0a112a1361ce2cc08e
BASE_PYTHON_VERSION=3.11.9
DOWNLOADED_ESPTOOL_SDIST_SHA256=125781f36e6a2d08c484524a45f340694675368b5eeead9d0cb21b2034a91d98
DOWNLOADED_ESPTOOL_SDIST_SHA256_MATCH=true
INSTALLED_ESPTOOL_VERSION=5.3.1
INSTALLED_PYSERIAL_VERSION=3.5
INSTALLED_CLICK_VERSION=8.4.2
TARGET_MARKER_SHA256=320ecd5f88b4207be39ee8660117f553c80ddf22d9ded9f33f1b147df89cb3a1
ENVIRONMENT_DISTRIBUTION_COUNT=19
ENVIRONMENT_ALL_DISTRIBUTIONS_SHA256=bdd8912af8a954f84a1794769c759a60b7165a6bef085854d6731b3f3db59ac2
MODULE_VERSION_COMMAND_RETURN_CODE=0
CONSOLE_VERSION_COMMAND_RETURN_CODE=0
HOST_PYPI_HTTPS_NETWORK_ATTEMPTED=true
BOARD_ACCESSED=false
SERIAL_ACCESS_ATTEMPTED=false
FLASH_OPERATION_ATTEMPTED=false
EFUSE_COMMAND_ATTEMPTED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```

U8 只修改用户本机独立虚拟环境，不连接测试板，不访问串口，不操作 Flash、eFuse 或生产环境。

## 8. D2 尝试 2 审核包

```text
D2_ATTEMPT2_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-02
D2_ATTEMPT2_AUTHORIZATION_STATUS=pending
D2_ATTEMPT2_REVIEW_PACKAGE_SHA256=939bf62e87aa05e8adbc6b5c20882ce8f7430a124226ab9b76e69cb7039b1ebb
D2_ATTEMPT2_EXECUTION_SCRIPT_SHA256=903a39ee896cbeee273a398f4db1441d0c71b3e8afa84b07c6690b3f992cf47a
D2_ATTEMPT2_COMMAND_GROUP_SHA256=c1417d7d16a37521f0fc57d0161e61fdaf4645a281c9ac30010b8aef7b2e1731
D2_ATTEMPT2_STOP_CONDITIONS_SHA256=31b48f3238856b6eb406d102821cc49a5729fcd0c6f4bff67bb0d560ed4fa246
D2_ATTEMPT2_ENVIRONMENT_MARKER_SHA256=320ecd5f88b4207be39ee8660117f553c80ddf22d9ded9f33f1b147df89cb3a1
D2_ATTEMPT2_ENVIRONMENT_DISTRIBUTIONS_SHA256=bdd8912af8a954f84a1794769c759a60b7165a6bef085854d6731b3f3db59ac2
D2_ATTEMPT2_PRIVATE_TARGET_BOUND=true
D2_ATTEMPT2_PRIVATE_SERIAL_BOUND=true
D2_ATTEMPT2_PRIVATE_BINDINGS_REDACTED_IN_GIT=true
D2_ATTEMPT2_REVIEW_MODE_PY_COMPILE=passed
D2_ATTEMPT2_REVIEW_MODE_RESULT=passed
D2_ATTEMPT2_EXECUTION_GATE=LOCKED
```

尝试 2 改用 U8 独立环境，通过 marker 与完整发行版指纹冻结工具链；使用新的脚本文件名、命令组和停止条件；运行时不调用 eFuse，目标私有身份与既有 G1 安全证明保持受控私有绑定。

## 9. S0—S8 状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| S0 基线确认 | `passed` | 冻结 source、V64、证据分支和禁止事项已确认 |
| S1 范围与验收设计 | `passed` | 验收项、停止条件、证据分层已冻结 |
| S2 非实板证据准备 | `passed` | manifest、索引和证据模板已建立 |
| S3 本地 Preflight | `passed` | U1、U7、U8 均闭环 |
| S4 GitHub CI | `passed` | Draft PR #172 继续保持 Draft；公共安全门持续执行 |
| S5 候选冻结 | `passed` | 仅引用不可变 V64，不重建候选 |
| S6A 隔离验证 | `passed` | host fault matrix、边界门、可复现性和尝试 2 review mode 通过 |
| S6B 实板验收 | `wait_attempt2_authorization` | 尝试 1 已退役；尝试 2 审核包就绪，尚未授权或执行 |
| S7 归档/发布 | `not_run` | 禁止 Ready、合并和发布 |
| S8 阶段关闭 | `not_run` | 等待尝试 2 D2 与实板证据闭环 |

## 10. 决策门

```text
D1_SCOPE_DECISION=resolved
D2_ATTEMPT1=retired_no_replay
D2_ATTEMPT2=pending_exact_authorization
D3_RISK_WAIVER=not_required
D4_READY_MERGE_RELEASE=prohibited
```

## 11. 助手开发队列

| ID | 状态 | 内容 |
|---|---|---|
| A1-A5 | `done` | 冻结基线、U1、尝试 1 证据与根因闭环 |
| A6 | `done` | 修正版执行链、可诊断失败阶段和完整 recovery 逻辑 |
| A7 | `done` | U7/U8 环境诊断与独立 esptool 环境冻结 |
| A8 | `done` | 尝试 2 审核包、脚本、命令组和停止条件 |
| A9 | `blocked_on_d2_attempt2` | 收到精确授权后签发新的不可重放授权 JSON 与自包含执行包 |
| A10 | `blocked_on_physical_result` | 实板结果后形成最终 L1 结论 |

## 12. 用户操作队列

```text
TASK_ID=D2_ATTEMPT2_REVIEW_AND_AUTHORIZATION
STATUS=ready_for_review
RISK_CLASS=D
BOARD_OPERATION_AUTHORIZED=false
AUTHORIZATION_REQUIRED=true
EXPECTED_RETURN=exact authorization text bound to attempt-2 review package SHA-256
```

当前不要连接或操作测试板，不要运行任何尝试 1 文件，也不要运行尝试 2 的 `--execute`。

## 13. 实板验收标准保持不变

- 冻结哈希、私有目标身份、芯片和 Flash 型号容量匹配；
- erase/write/verify/preboot readback 成功；
- preboot 64 KiB 与 seed 逐字节一致；
- 串口包含冻结 boundary、snapshot 和 `stage2d8_g2_probe=pass`，且无失败标志；
- `key_loaded=false`、`wifi=false`、`mqtt=false`、`writes=0`；
- 全部 MQTT session=false，`reboot_required=false`；
- postboot 64 KiB 与 seed、preboot 逐字节一致；
- recovery 未执行，或仅在许可失败条件下准确执行一次；
- eFuse、网络和生产环境操作均未发生；
- 证据完整、脱敏、可追溯。

## 14. 当前结论

```text
STAGE_STATUS=prepared_waiting_d2_attempt2_authorization
FINAL_RESULT=inconclusive
U1_HOST_ARTIFACT_VERIFICATION=passed
D2_ATTEMPT1_STATUS=attempted_inconclusive_retired
D2_ATTEMPT1_REPLAY_PERMITTED=false
U7_ROOT_CAUSE_CONFIRMED=true
U8_DEDICATED_ESPTOOL_ENVIRONMENT=passed
D2_ATTEMPT2_REVIEW_PACKAGE=prepared
D2_ATTEMPT2_AUTHORIZATION_RECEIVED=false
D2_ATTEMPT2_PHYSICAL_EXECUTION_STARTED=false
DESTRUCTIVE_BOUNDARY_ENTERED=false
PHYSICAL_ERASE_PERFORMED=false
G2_FLASH_PERFORMED=false
VERIFY_FLASH_PERFORMED=false
PREBOOT_READBACK_PERFORMED=false
G2_BOOTED=false
POSTBOOT_READBACK_PERFORMED=false
RECOVERY_PERFORMED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```
