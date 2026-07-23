# H3/N2 Stage 2D-9 V68 PREPARE 失败源码诊断

## 1. 最终结论

```text
PHYSICAL_PREPARE_RESULT=failed
PRIVATE_EVIDENCE_CLOSURE=passed
LOCKED_RECOVERY_VERIFICATION=passed
FINAL_BOARD_STATE=locked_recovery_seed_restored
ROOT_CAUSE=candidate_host_contract_mismatch
ROOT_CAUSE_STATUS=confirmed_by_frozen_source_and_actual_cpp_host_test
RUNNER_OBSERVABILITY_DEFECT=confirmed_independent_defect
DEVICE_RECONNECT_AUTHORIZED=false
V68_RETRY_AUTHORIZED=false
```

本结论仅基于冻结源码、已脱敏 U2 证据和 host-only 源码测试。没有重新连接测试板、重放授权或执行新的设备操作。

## 2. 实板证据结论

1. 实板身份、V68 Artifact、专用构建环境和 Stage 2D-8 seed 连续性预检通过。
2. V68 G3 擦除、写入和 Flash 校验通过。
3. PREPARE 前 64 KiB 测试分区与冻结 seed 完全一致。
4. host runner 发起过一次 PREPARE 串口写入尝试。
5. executor 在 PREPARE 成功标志出现前输出 fail marker，runner 在 `prepare_serial` 阶段 fail closed。
6. PREPARE 成功、candidate generation=1、PREPARED 状态和 digest 匹配均未得到证明；VERIFY 未执行。
7. 唯一一次 locked recovery 的擦除、写入、Flash 校验、seed 恢复、启动和 `stage2d9_recovery=locked` 标志全部通过。
8. recovery 后分区字节与 PREPARE 前分区及冻结 seed 完全一致。
9. eFuse、网络和生产环境操作均未发生。

## 3. 确定性根因

冻结 V68 executor 构造测试候选时设置：

```text
broker_host=stage2d9.invalid
broker_tls_server_name=stage2d9.invalid
```

外层 `IsolatedCandidateProfile::valid()` 只要求这两个字段非空且长度合规，因此测试配置可被加载。PREPARE 随后把候选转换为正式 `RamCredentialBundle`；该对象的 `valid()` 强制要求 Broker 主机和 TLS 名称均通过 `PairingClientCore::valid_local_host()`。

`valid_local_host()` 只接受受支持的本地 IPv4 地址或以 `.local` 结尾的主机名，明确不接受 `.invalid`。因此 PREPARE 在持久化写入前执行 `bundle.valid()` 时返回 false，driver 记录 `invalid_configuration`，package 折叠为 `prepare_failed`，executor 最终输出 `reason=command_execution`。

调用链如下：

```text
executor build_configuration(stage2d9.invalid)
→ package.load_test_configuration：通过
→ authorization_binder.grant：可通过
→ package.prepare_candidate
→ driver.prepare_candidate
→ bundle_from_candidate
→ RamCredentialBundle::valid
→ valid_local_host(stage2d9.invalid)=false
→ driver failure=invalid_configuration
→ package failure=prepare_failed
→ executor failure=command_execution
```

## 4. Host 证明

新增两项 host-only CI 证明：

```text
SOURCE_ROOT_CAUSE_GATE=passed
ACTUAL_CPP_HOST_CONTRACT_TEST=passed
STAGE2D9_V68_INVALID_HOST_REJECTED=true
STAGE2D9_V69_LOCAL_HOST_ACCEPTED=true
MQTT_IN_PREPARE_CALL_PATH=false
```

实际 C++ 测试直接编译冻结的 `pairing_client_core.cpp` 和 `pairing_ram_credentials.cpp`：

- `stage2d9.invalid` 被正式凭据合同拒绝；
- `stage2d9.local` 被同一合同接受；
- V68 根因是外层候选合同与内层正式凭据合同不一致。

同时，冻结 driver 源码确认 MQTT `configure()` 仅在后续 `begin_validation()` 中调用，不在 PREPARE 路径内。因此 Null MQTT port 不是本次根因。

## 5. 独立 runner 取证缺陷

```text
RUNNER_SERIAL_LOG_PERSISTENCE_DEFECT=confirmed
PREPARE_SERIAL_LOG_PRESENT=false
VERIFY_SERIAL_LOG_PRESENT=false
```

V68 runner 仅在 PREPARE 捕获循环正常结束后写入 `g3-prepare-serial.log`。executor fail marker 触发异常后，函数在写日志之前退出，因此：

- 顶层 `prepare_command_sent` 保留 fail-closed 默认值；
- `PREPARE_COMMAND_SENT_ONCE=true` 只能证明 host 发起过一次串口写入尝试；
- 完整设备侧 failure 行没有进入私有归档。

该缺陷没有造成 V68 PREPARE 失败，但降低了失败证据精度，必须与固件根因同时修复。

## 6. V69 修正要求

任何 V69 或更高版本进入 Artifact 构建前，必须完成：

1. 新 executor 使用符合正式凭据合同的不可路由本地占位名称，例如 `stage2d9.local`；
2. 不修改或复用冻结 V68 executor、runner、launcher 和 Artifact 路径；
3. executor 输出细分、脱敏的 config、authorization、persistence 和 postcondition failure 标志；
4. runner 在 `finally` 中原子保存串口缓冲，无论 success、fail marker、timeout 或异常；
5. summary 分离 `host_write_attempted`、`device_command_accepted` 和 `transaction_succeeded`；
6. 实际 C++ host 合同测试覆盖 `.invalid` 拒绝和 `.local` 接受；
7. actual package/driver PREPARE 正常路径与故障注入测试通过；
8. 完成唯一命名源码 CI 后重新生成不可变 Artifact；新 U1 通过后才允许提出新 D2。

## 7. 当前处置

```text
V68_AUTHORIZATION=consumed_failed_recovery_verified_retired
V68_REPLAY_PERMITTED=false
V68_G3_RETRY_PERMITTED=false
BOARD_RECONNECT_AUTHORIZED=false
NEW_D2_REQUEST=none
V69_SOURCE_CORRECTION=in_progress_host_only
PR_174_STATE=open_draft
READY_MERGE_RELEASE_AUTHORIZED=false
```

V68 私有归档和 U2 日志应继续保留。测试板无需再次连接；其测试分区已恢复为冻结 seed，并运行 locked recovery 固件。
