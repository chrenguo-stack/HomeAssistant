# H3/N2 Stage 2D-9 V68 PREPARE 失败源码诊断

## 1. 结论状态

```text
PHYSICAL_PREPARE_RESULT=failed
PRIVATE_EVIDENCE_CLOSURE=passed
LOCKED_RECOVERY_VERIFICATION=passed
FINAL_BOARD_STATE=locked_recovery_seed_restored
EXACT_FIRMWARE_FAILURE_SUBREASON=unavailable
SOURCE_DIAGNOSIS_STATUS=bounded_but_not_final
DEVICE_RECONNECT_AUTHORIZED=false
V68_RETRY_AUTHORIZED=false
```

本文件仅基于冻结源码和已脱敏 U2 证据。没有重新连接测试板、重放授权或读取新的设备信息。

## 2. 已由证据确认的事实

1. 实板身份、V68 Artifact、专用构建环境和原 Stage 2D-8 seed 连续性预检通过。
2. V68 G3 擦除、写入和 Flash 校验通过。
3. PREPARE 前 64 KiB 测试分区与冻结 seed 完全一致。
4. host runner 发起过一次 PREPARE 串口写入尝试。
5. executor 在 PREPARE 成功标志出现前输出 fail marker，runner 因此在 `prepare_serial` 阶段 fail closed。
6. PREPARE 成功、candidate generation=1、PREPARED 状态和 digest 匹配均未得到证明；VERIFY 未执行。
7. 唯一一次 locked recovery 的擦除、写入、Flash 校验、seed 恢复、启动和 `stage2d9_recovery=locked` 标志全部通过。
8. recovery 后分区字节与 PREPARE 前分区及冻结 seed 完全一致。
9. eFuse、网络和生产环境操作均未发生。

## 3. 冻结 PREPARE 调用链

冻结 executor 的 PREPARE 路径依次执行：

```text
解析与校验私有命令
→ 加载临时持久化密钥
→ 构造并校验测试配置
→ package.load_test_configuration
→ authorization_binder.grant
→ package.prepare_candidate
→ driver.prepare_candidate
→ persistence.prepare_candidate
→ 重开只读存储并恢复验证
→ executor 检查 PREPARED 后置条件
```

`IsolatedAcceptancePackage::prepare_candidate()` 只负责消费 package 侧一次性授权并调用 driver PREPARE；它不启动 MQTT 验证。`IsolatedDeviceDriver::prepare_candidate()` 只执行状态、密钥、镜像授权、候选 bundle 和持久化 PREPARE 检查。MQTT `configure()` 仅在后续 `begin_validation()` 中调用。因此，“Null MQTT port 导致 PREPARE 失败”的早期假设已被源码调用链排除。

## 4. 已确认的 runner 取证缺陷

```text
RUNNER_SERIAL_LOG_PERSISTENCE_DEFECT=confirmed
PREPARE_SERIAL_LOG_PRESENT=false
VERIFY_SERIAL_LOG_PRESENT=false
```

V68 runner 仅在 PREPARE 捕获循环正常结束后写入 `g3-prepare-serial.log`。executor fail marker 触发异常后，函数在写日志之前退出，因此：

- 顶层 summary 未收到正常返回值，`prepare_command_sent` 保留 fail-closed 默认值；
- 已打印的 `PREPARE_COMMAND_SENT_ONCE=true` 只能证明 host 进行过一次串口写入尝试；
- 触发异常的完整串口内容及设备侧细分 failure 字段没有进入私有归档；
- 当前不能从现有证据恢复唯一、确定的固件子原因。

这是确定的取证实现缺陷，不等同于 PREPARE 固件事务的根因。

## 5. 固件失败范围

在不猜测的前提下，冻结源码将故障范围限制在以下位置之一：

1. 测试配置构造、合法性检查或加载；
2. package 与 driver 两侧镜像授权的 grant 或 consume；
3. 测试 NVS namespace 的读写打开、candidate 写入、提交、重开或恢复验证；
4. executor 对 generation、PREPARED、writes、session 或 digest 的后置条件检查。

由于 PREPARE 串口日志未被持久保存，现有证据不足以在这些位置中唯一定位。不得以推测替代根因结论。

## 6. 新源码链必须满足的修正要求

任何后续 V69 或更高版本进入 Artifact 构建前，必须同时完成：

1. **唯一命名源码和脚本**：不得修改或复用冻结 V68 executor、runner、launcher 和 Artifact 路径。
2. **串口日志 finally 持久化**：无论 success、fail marker、timeout 或 Python 异常，均先原子写入捕获缓冲区，再抛出错误。
3. **细分失败标志**：executor 在清除敏感材料前输出脱敏的阶段与枚举名称，例如 config、authorization、persistence write、recovery verify 或 postcondition。
4. **真实调用链 host 测试**：使用实际 package、driver、authorization binder 和 persistence 行为进行 PREPARE 正常路径及故障注入，不只验证抽象 Python 状态模型。
5. **后置条件逐项证据**：generation、recovery status、write count、reboot flag、session flags 和 candidate digest 分开输出和断言。
6. **失败取证测试**：自动测试 fail marker 出现时日志仍存在、SHA 可计算、summary 中记录 host send attempt 与 device acceptance 的区别。
7. **全新不可变 Artifact、U1 与 D2**：源码修正通过 CI 后重新生成唯一 Artifact；完成新的 host-only U1 后才允许提出新的 D2。

## 7. 当前处置

```text
V68_AUTHORIZATION=consumed_failed_retired
V68_REPLAY_PERMITTED=false
V68_G3_RETRY_PERMITTED=false
BOARD_RECONNECT_AUTHORIZED=false
NEW_D2_REQUEST=none
PR_174_STATE=open_draft
READY_MERGE_RELEASE_AUTHORIZED=false
```

V68 私有归档和 U2 日志应继续保留。测试板无需再次连接；其测试分区已通过证据确认恢复为冻结 seed，并运行 locked recovery 固件。
