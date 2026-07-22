# H3/N2 Stage 2D-8 G2 专用测试板实板验收状态

- **状态文件版本：** V2.3
- **更新日期：** 2026-07-22
- **权威性：** 本文件是本活动阶段唯一权威 `STAGE_STATUS`
- **阶段状态：** `attempt3_passed_pending_private_detail_closure`
- **当前结论：** `passed`
- **执行门：** `CLOSED_CONSUMED_NO_REPLAY`

## 1. 冻结基线

```text
STAGE=H3/N2 Stage 2D-8 G2 专用测试板实板只读验收执行与证据闭环
REPOSITORY=chrenguo-stack/HomeAssistant
SOURCE_SHA=6cf37c29311601f4f83238cc8401c81ea7b9a1f0
BRANCH=evidence/h3-n2-stage2d8-g2-physical-acceptance-20260722-v1
FROZEN_SOURCE_PR=168
FROZEN_ARTIFACT_GENERATION=V64
FROZEN_ARTIFACT_NAME=stage2d8-g2-immutable-locked-v64
ARTIFACT_ZIP_SHA256=662d9d4d850eea603d5defafb2b3c84a8bc07fae3a4b51229479b2a0a71e8ea9
G2_MERGED_SHA256=a3ff73ddc11115849e160637cd63e2f44c699e595c5c6aa43575f9d7626ed47d
RECOVERY_MERGED_SHA256=5f6ca3024d35dea9b48679a3882a55a20ec2bc67137d6dd58cbf19c2474994ed
PARTITION_BINARY_SHA256=d59f8cff987dee266d2df9340867ff56369c2dfd28c93e12d5a93b10277c2a72
NVS_SEED_SHA256=1f7016fe98cf69ca879a72069e63869863d1a4c8580ba0c8931aef133de3c928
FROZEN_SOURCE_MODIFIED=false
CANDIDATE_REBUILT=false
EVIDENCE_PR=172
PRODUCTION_ENVIRONMENT_MODIFIED=false
```

PR `#166`、`#167`、`#168` 的冻结分支未修改。Git 只保存脱敏 L1 摘要、manifest、状态和索引。

## 2. 禁止事项

继续禁止：修改或重建冻结候选；重放 D2 尝试 1、2 或 3；`PREPARE_CANDIDATE`、`ACTIVATE_PROFILE`、`CLEANUP_TEST_STATE`；测试密钥、可写 NVS、Wi-Fi、MQTT、Broker、Home Assistant、API、OTA、mDNS；任何 eFuse 读取或写入；启用 Secure Boot 或 Flash Encryption；M401A、T1、Mosquitto、greenhouse-manager 和生产环境操作；Ready、合并或发布。

## 3. 退役尝试

```text
D2_ATTEMPT1_STATUS=attempted_inconclusive_retired
D2_ATTEMPT1_FAILURE_STAGE=local_esptool_version_preflight
D2_ATTEMPT1_DESTRUCTIVE_BOUNDARY_ENTERED=false
D2_ATTEMPT1_REPLAY_PERMITTED=false

D2_ATTEMPT2_STATUS=attempted_inconclusive_retired
D2_ATTEMPT2_FAILURE_STAGE=authorization
D2_ATTEMPT2_AUTHORIZATION_CONSUMED=false
D2_ATTEMPT2_DESTRUCTIVE_BOUNDARY_ENTERED=false
D2_ATTEMPT2_REPLAY_PERMITTED=false
```

尝试 1、2 均在板卡访问和破坏性边界前 fail closed。

## 4. D2 尝试 3 实板结果

```text
D2_ATTEMPT3_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-03
D2_ATTEMPT3_RESULT=passed
D2_ATTEMPT3_AUTHORIZATION_CONSUMED=true
D2_ATTEMPT3_REPLAY_PERMITTED=false
D2_ATTEMPT3_EXECUTION_PACKAGE_SHA256=569186c27436b37dd82b2fd4dd8d911653f81e5d1070cf1df831df2a0841d02e
D2_ATTEMPT3_EXECUTION_SCRIPT_SHA256=f40911b27bdd7105f1e1b636c538d1cf18719cbc42f8a1a80edd73346659430d
D2_ATTEMPT3_LAUNCHER_SHA256=42cdd0a02f2e13f8da026753cefdb91ac7d217ce6e119715a0dcc626f64fc558
D2_ATTEMPT3_AUTHORIZATION_BINDING_SHA256=7c5b154cae8199f07426464422b7b0be2048e47cbefd25fb2660436ecc393f66
D2_ATTEMPT3_PRIVATE_ARCHIVE_SHA256=a29db874961f9baa34137837fdbd31f1018d4fd8b7f01a2b5922bf512790a6fb
DESTRUCTIVE_BOUNDARY_ENTERED=true
PHYSICAL_ERASE_PERFORMED=true
G2_FLASH_PERFORMED=true
VERIFY_FLASH_PERFORMED=true
PREBOOT_READBACK_PERFORMED=true
PREBOOT_MATCHES_SEED=true
G2_SERIAL_CAPTURE_PASSED=true
POSTBOOT_READBACK_PERFORMED=true
POSTBOOT_MATCHES_SEED=true
POSTBOOT_MATCHES_PREBOOT=true
RECOVERY_PERFORMED=false
RECOVERY_COUNT=0
EFUSE_COMMAND_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```

runner 只有在目标、环境、Artifact、USB、芯片与 Flash 身份预检通过，erase/write/verify 成功，preboot 与 seed 一致，冻结串口 boundary/snapshot/probe 标志全部通过，且 postboot 与 seed、preboot 均一致时才返回 `PASS`。

## 5. 未按物理 RESET 的说明

```text
SERIAL_CAPTURE_PROMPT_PRINTED=true
PHYSICAL_RESET_PRESSED=false
BOOT_AND_FROZEN_MARKERS_OBSERVED=true
ACCEPTANCE_IMPACT=none
```

用户未按 RESET，流程仍立即捕获了完整冻结启动标志。当前判定为串口打开时 DTR/RTS 或 USB-Serial/JTAG 状态切换导致的自动启动/复位行为。该触发机制不改变验收目标：G2 已实际启动，串口证据通过，postboot 只读分区仍逐字节保持不变。U9 仅从私有归档读取 reset-line 和完整结构化摘要，以关闭该细节；禁止再次连接或运行测试板。

## 6. S0—S8 状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| S0 基线确认 | `passed` | 冻结 source、V64、分支和禁止事项已确认 |
| S1 范围与验收设计 | `passed` | 验收项、停止条件、证据分层已冻结 |
| S2 非实板证据准备 | `passed` | manifest、索引和证据模板已建立 |
| S3 本地 Preflight | `passed` | U1、U7、U8 均闭环 |
| S4 GitHub CI | `passed` | Draft PR #172 继续保持 Draft |
| S5 候选冻结 | `passed` | 仅引用不可变 V64，不重建候选 |
| S6A 隔离验证 | `passed` | 编译、review、授权和 ZIP 自检通过 |
| S6B 实板验收 | `passed_pending_private_detail_closure` | 尝试 3 实板 PASS；等待 U9 只读细节索引 |
| S7 归档/发布 | `not_run` | 禁止 Ready、合并和发布 |
| S8 阶段关闭 | `pending_u9` | 等待私有摘要和 reset-line 脱敏闭环 |

## 7. 决策门

```text
D1_SCOPE_DECISION=resolved
D2_ATTEMPT1=retired_no_replay
D2_ATTEMPT2=retired_no_replay
D2_ATTEMPT3=consumed_passed_no_replay
D3_RISK_WAIVER=not_required
D4_READY_MERGE_RELEASE=prohibited
```

## 8. 当前结论

```text
STAGE_STATUS=attempt3_passed_pending_private_detail_closure
FINAL_RESULT=passed
EXECUTION_GATE=CLOSED_CONSUMED_NO_REPLAY
D2_ATTEMPT3_AUTHORIZATION_CONSUMED=true
D2_ATTEMPT3_REPLAY_PERMITTED=false
PHYSICAL_ERASE_PERFORMED=true
G2_FLASH_PERFORMED=true
VERIFY_FLASH_PERFORMED=true
PREBOOT_MATCHES_SEED=true
SERIAL_FROZEN_MARKERS_PASSED=true
POSTBOOT_MATCHES_SEED=true
POSTBOOT_MATCHES_PREBOOT=true
RECOVERY_PERFORMED=false
EFUSE_COMMAND_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```
