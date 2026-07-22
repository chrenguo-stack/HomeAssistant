# H3/N2 Stage 2D-8 G2 专用测试板实板验收状态

- **状态文件版本：** V2.2
- **更新日期：** 2026-07-22
- **权威性：** 本文件是本活动阶段唯一权威 `STAGE_STATUS`
- **阶段状态：** `authorized_awaiting_d2_attempt3_one_shot_execution`
- **当前结论：** `inconclusive`
- **执行门：** `OPEN_EXACT_ONE_SHOT_UNTIL_EXPIRY`

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

继续禁止：修改或重建冻结候选；重放 D2 尝试 1 或尝试 2；拆分或移动尝试 3 授权包内单个文件；`PREPARE_CANDIDATE`、`ACTIVATE_PROFILE`、`CLEANUP_TEST_STATE`；测试密钥、可写 NVS、Wi-Fi、MQTT、Broker、Home Assistant、API、OTA、mDNS；任何 eFuse 读取或写入；启用 Secure Boot 或 Flash Encryption；M401A、T1、Mosquitto、greenhouse-manager 和生产环境操作；Ready、合并或发布。

## 3. 已完成准备

```text
U1_ARTIFACT_VERIFICATION=passed
U1_CONTROLLED_PRIVATE_OUTPUT_SHA256=6930cb6e52ada91f92ccf487c35319856abffd2e2d8ee17fe43641bbb9ce619e
U7_ROOT_CAUSE=original development venv had no esptool
U8_DEDICATED_ENVIRONMENT=passed
U8_ESPTOOL_VERSION=5.3.1
U8_PYSERIAL_VERSION=3.5
U8_CLICK_VERSION=8.4.2
U8_ENVIRONMENT_MARKER_SHA256=320ecd5f88b4207be39ee8660117f553c80ddf22d9ded9f33f1b147df89cb3a1
U8_ENVIRONMENT_DISTRIBUTIONS_SHA256=bdd8912af8a954f84a1794769c759a60b7165a6bef085854d6731b3f3db59ac2
```

## 4. 退役尝试

### 尝试 1

```text
D2_ATTEMPT1_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-01
D2_ATTEMPT1_STATUS=attempted_inconclusive_retired
D2_ATTEMPT1_FAILURE_STAGE=local_esptool_version_preflight
D2_ATTEMPT1_DESTRUCTIVE_BOUNDARY_ENTERED=false
D2_ATTEMPT1_REPLAY_PERMITTED=false
```

### 尝试 2

```text
D2_ATTEMPT2_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-02
D2_ATTEMPT2_STATUS=attempted_inconclusive_retired
D2_ATTEMPT2_FAILURE_STAGE=authorization
D2_ATTEMPT2_FAILURE_CAUSE=authorization JSON absent from instructed Downloads-root path
D2_ATTEMPT2_AUTHORIZATION_CONSUMED=false
D2_ATTEMPT2_USB_PREFLIGHT_REACHED=false
D2_ATTEMPT2_DESTRUCTIVE_BOUNDARY_ENTERED=false
D2_ATTEMPT2_PRIVATE_ARCHIVE_SHA256=fd8e97db174de759a964e276ff7cb1d534fa64a2f6e2d48dd385eb6e57a7fb0a
D2_ATTEMPT2_REPLAY_PERMITTED=false
```

尝试 1、2 均在板卡访问和破坏性边界前 fail closed，未擦除、写入、校验、回读或执行 recovery。

## 5. D2 尝试 3 精确单次授权

```text
D2_ATTEMPT3_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-03
D2_ATTEMPT3_AUTHORIZATION_STATUS=authorized_not_consumed
D2_ATTEMPT3_ISSUED_AT=2026-07-22T12:36:47Z
D2_ATTEMPT3_EXPIRES_AT=2026-07-22T14:36:47Z
D2_ATTEMPT3_ONE_SHOT=true
D2_ATTEMPT3_REPLAY_PERMITTED=false
D2_ATTEMPT3_ALLOWED_RECOVERY_COUNT=1
D2_ATTEMPT3_REVIEW_PACKAGE_SHA256=e23c8a05d4fc58c5c1101ea1a01d2b8fd8860fa1c0246e5da1920229c5ae3ab6
D2_ATTEMPT3_EXECUTION_PACKAGE_SHA256=569186c27436b37dd82b2fd4dd8d911653f81e5d1070cf1df831df2a0841d02e
D2_ATTEMPT3_EXECUTION_SCRIPT_SHA256=f40911b27bdd7105f1e1b636c538d1cf18719cbc42f8a1a80edd73346659430d
D2_ATTEMPT3_LAUNCHER_SHA256=42cdd0a02f2e13f8da026753cefdb91ac7d217ce6e119715a0dcc626f64fc558
D2_ATTEMPT3_COMMAND_GROUP_SHA256=20b257c1dac4baabcda75a64a5ccc87c0116447e5a435dfb7c125aefe8b20c9c
D2_ATTEMPT3_STOP_CONDITIONS_SHA256=8bda28d1e1b404b882d6f886c32ac5a027b1d5fb6b211b3ade8d3ced8be433d3
D2_ATTEMPT3_OPERATOR_AUTHORIZATION_TEXT_SHA256=99b0f5004a027e08560e191c84689672a342e4a9fd032c3eb30fed963735f614
D2_ATTEMPT3_AUTHORIZATION_BINDING_SHA256=7c5b154cae8199f07426464422b7b0be2048e47cbefd25fb2660436ecc393f66
D2_ATTEMPT3_AUTHORIZATION_FILE_SHA256=c099ac351d30e33bb2c06fb7c1bcfcf61dbbb8ace61b51bda94b067b675312cc
D2_ATTEMPT3_TOP_LEVEL_DIRECTORY=Stage2D8_G2_D2_Attempt3_Authorized_V1
D2_ATTEMPT3_PY_COMPILE=passed
D2_ATTEMPT3_REVIEW_MODE=passed
D2_ATTEMPT3_AUTHORIZATION_SELF_CHECK=passed
D2_ATTEMPT3_ZIP_MEMBER_AND_HASH_CHECK=passed
```

尝试 3 授权包包含一个固定顶层目录。用户不得移动、重命名或拆分其中单个文件，只能运行目录内固定 launcher。授权 JSON、私有板卡身份、私有串口和完整私有证据不进入 Git。

## 6. S0—S8 状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| S0 基线确认 | `passed` | 冻结 source、V64、分支和禁止事项已确认 |
| S1 范围与验收设计 | `passed` | 验收项、停止条件、证据分层已冻结 |
| S2 非实板证据准备 | `passed` | manifest、索引和证据模板已建立 |
| S3 本地 Preflight | `passed` | U1、U7、U8 均闭环 |
| S4 GitHub CI | `passed` | Draft PR #172 继续保持 Draft |
| S5 候选冻结 | `passed` | 仅引用不可变 V64，不重建候选 |
| S6A 隔离验证 | `passed` | 尝试 3 编译、review、授权和 ZIP 自检通过 |
| S6B 实板验收 | `authorized_waiting_attempt3_execution` | 等待尝试 3 固定 launcher 单次执行 |
| S7 归档/发布 | `not_run` | 禁止 Ready、合并和发布 |
| S8 阶段关闭 | `not_run` | 等待实板结果和证据闭环 |

## 7. 决策门

```text
D1_SCOPE_DECISION=resolved
D2_ATTEMPT1=retired_no_replay
D2_ATTEMPT2=retired_no_replay
D2_ATTEMPT3=authorized_not_consumed
D3_RISK_WAIVER=not_required
D4_READY_MERGE_RELEASE=prohibited
```

## 8. 尝试 3 执行范围

只允许一次完成：环境、Artifact、目标、USB、芯片及 Flash 身份预检；授权消费；全片擦除；V64 G2 写入；verify-flash；preboot 64 KiB 回读；串口证据启动；postboot 64 KiB 回读；私有证据归档。串口提示出现后，只允许按一次物理 RESET，不按 BOOT。仅在进入破坏性边界后发生冻结失败时，最多自动执行一次 locked recovery。

## 9. 当前结论

```text
STAGE_STATUS=authorized_awaiting_d2_attempt3_one_shot_execution
FINAL_RESULT=inconclusive
EXECUTION_GATE=OPEN_EXACT_ONE_SHOT_UNTIL_EXPIRY
D2_ATTEMPT1_REPLAY_PERMITTED=false
D2_ATTEMPT2_REPLAY_PERMITTED=false
D2_ATTEMPT3_AUTHORIZATION_RECEIVED=true
D2_ATTEMPT3_AUTHORIZATION_CONSUMED=false
D2_ATTEMPT3_PHYSICAL_EXECUTION_STARTED=false
PHYSICAL_ERASE_PERFORMED=false
G2_FLASH_PERFORMED=false
VERIFY_FLASH_PERFORMED=false
PREBOOT_READBACK_PERFORMED=false
G2_BOOTED=false
POSTBOOT_READBACK_PERFORMED=false
RECOVERY_PERFORMED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```
