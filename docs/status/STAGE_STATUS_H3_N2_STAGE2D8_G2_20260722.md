# H3/N2 Stage 2D-8 G2 专用测试板实板验收状态

- **状态文件版本：** V2.4
- **更新日期：** 2026-07-22
- **权威性：** 本文件是本活动阶段唯一权威 `STAGE_STATUS`
- **阶段状态：** `physical_acceptance_passed_evidence_closed`
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
D2_ATTEMPT2_USB_PREFLIGHT_REACHED=false
D2_ATTEMPT2_DESTRUCTIVE_BOUNDARY_ENTERED=false
D2_ATTEMPT2_PRIVATE_ARCHIVE_SHA256=fd8e97db174de759a964e276ff7cb1d534fa64a2f6e2d48dd385eb6e57a7fb0a
D2_ATTEMPT2_REPLAY_PERMITTED=false
```

尝试 1、2 均在板卡访问和破坏性边界前 fail closed，未擦除、写入、校验、回读或执行 recovery。

## 4. D2 尝试 3 实板验收

```text
D2_ATTEMPT3_REQUEST_ID=D2-H3N2-STAGE2D8-G2-V64-20260722-03
D2_ATTEMPT3_STATUS=consumed_passed_retired
D2_ATTEMPT3_REPLAY_PERMITTED=false
D2_ATTEMPT3_EXECUTION_PACKAGE_SHA256=569186c27436b37dd82b2fd4dd8d911653f81e5d1070cf1df831df2a0841d02e
D2_ATTEMPT3_AUTHORIZATION_BINDING_SHA256=7c5b154cae8199f07426464422b7b0be2048e47cbefd25fb2660436ecc393f66
D2_ATTEMPT3_PRIVATE_ARCHIVE_SHA256=a29db874961f9baa34137837fdbd31f1018d4fd8b7f01a2b5922bf512790a6fb
D2_ATTEMPT3_PRIVATE_SUMMARY_SHA256=82986306ea898b7bcb88df9ce69ad3c2377ad15a42abe53ad9f72921d687097a
D2_ATTEMPT3_SERIAL_LOG_SHA256=a6189a4e0667ea169b8b452f3f1422576b0ef4a6997314d9ef635d99e195c3b2
D2_ATTEMPT3_PREFLIGHT_LOG_SHA256=279386765a0ed944f79cb851654536bb170a436f3547916dda19fb6e05a181bd
D2_ATTEMPT3_DESTRUCTIVE_LOG_SHA256=baa5631e2704ec0cef8c3720e8397c45b8715542273dcfa7122c2f2a4354d1ca
```

### 4.1 预检和 Flash

```text
PREFLIGHT_STATUS=passed
HOST_ENVIRONMENT_PRESENT=true
USB_PREFLIGHT_PRESENT=true
FLASH_ID_PRESENT=true
AUTHORIZATION_CONSUMED=true
DESTRUCTIVE_BOUNDARY_ENTERED=true
ERASE_SUCCESS=true
WRITE_SUCCESS=true
VERIFY_FLASH_SUCCESS=true
```

### 4.2 分区不变性

```text
PREBOOT_READBACK_SHA256=1f7016fe98cf69ca879a72069e63869863d1a4c8580ba0c8931aef133de3c928
PREBOOT_MATCHES_SEED=true
POSTBOOT_READBACK_SHA256=1f7016fe98cf69ca879a72069e63869863d1a4c8580ba0c8931aef133de3c928
POSTBOOT_MATCHES_SEED=true
POSTBOOT_MATCHES_PREBOOT=true
```

### 4.3 串口冻结标志

```text
SERIAL_BOUNDARY_MATCH=true
SERIAL_SNAPSHOT_MATCH=true
SERIAL_PROBE_PASS=true
SERIAL_PROBE_FAIL_ABSENT=true
SERIAL_PARTITION_INIT_ERROR_ABSENT=true
SERIAL_BOUNDARY_COUNT=1
SERIAL_SNAPSHOT_COUNT=1
SERIAL_PROBE_PASS_COUNT=1
SERIAL_PROBE_FAIL_COUNT=0
```

冻结串口证据确认：`key_loaded=false`、`wifi=false`、`mqtt=false`、`write_authorization=false`、`partition_readonly=true`、`read_only=true`、`persistence=empty`、全部 generation=0、`writes=0`、全部 MQTT session=false、`reboot_required=false`。

### 4.4 启动观察

用户未按物理 RESET。U9 私有串口证据确认：

```text
RESET_REASON=USB_UART_HPSYS
BOOT_MODE=SPI_FAST_FLASH_BOOT
PHYSICAL_RESET_PRESSED=false
```

串口采集阶段发生了 USB UART 高性能系统自动复位。精确 boundary、snapshot、probe=pass 及启动前后分区不变性均通过，因此不影响验收结论。

### 4.5 保护边界

```text
RECOVERY_PERFORMED=false
RECOVERY_COUNT=0
EFUSE_COMMAND_ATTEMPTED=false
NETWORK_OPERATION_ATTEMPTED=false
WIFI_CONNECTED=false
MQTT_CONNECTED=false
BROKER_STARTED=false
TEST_KEY_LOADED=false
WRITABLE_NVS_OPENED=false
PREPARE_CANDIDATE_EXECUTED=false
ACTIVATE_PROFILE_EXECUTED=false
CLEANUP_TEST_STATE_EXECUTED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```

## 5. S0—S8 状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| S0 基线确认 | `passed` | 冻结 source、V64、分支和禁止事项已确认 |
| S1 范围与验收设计 | `passed` | 验收项、停止条件、证据分层已冻结 |
| S2 非实板证据准备 | `passed` | manifest、索引和证据模板已建立 |
| S3 本地 Preflight | `passed` | U1、U7、U8 均闭环 |
| S4 GitHub CI | `passed` | Draft PR #172 公共安全门通过 |
| S5 候选冻结 | `passed` | 仅引用不可变 V64，不重建候选 |
| S6A 隔离验证 | `passed` | 编译、review、授权和 ZIP 自检通过 |
| S6B 实板验收 | `passed` | 擦除、写入、校验、回读、串口及不变性通过 |
| S7 证据归档 | `passed` | 私有证据 SHA 和脱敏 L1 已闭环 |
| S8 阶段关闭 | `passed` | 执行门关闭；PR 保持 Draft |

## 6. 决策门

```text
D1_SCOPE_DECISION=resolved
D2_ATTEMPT1=retired_no_replay
D2_ATTEMPT2=retired_no_replay
D2_ATTEMPT3=consumed_passed_no_replay
D3_RISK_WAIVER=not_required
D4_READY_MERGE_RELEASE=not_requested_and_prohibited
```

## 7. 最终结论

```text
STAGE_STATUS=physical_acceptance_passed_evidence_closed
FINAL_RESULT=passed
EXECUTION_GATE=CLOSED_CONSUMED_NO_REPLAY
PHYSICAL_ACCEPTANCE=passed
EVIDENCE_CLOSURE=passed
PR_172_STATE=open_draft
READY_MERGE_RELEASE_AUTHORIZED=false
PRODUCTION_ENVIRONMENT_MODIFIED=false
```
