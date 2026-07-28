# H3/N2 Stage 2D-9R G3R 基线不一致证据修复合同 V1

## 1. 决策与边界

本层落实：

```text
D1-H3N2-STAGE2D9R-G3R-BASELINE-MISMATCH-EVIDENCE-REPAIR-20260728-01
```

它是基于 Draft PR #195 精确 HEAD
`1fd6bc19246481835c1e836f5daaefcaf6c97836` 的源码后继层。仅允许源码、测试、
Draft PR、CI 和公开审查 Artifact。不得连接板卡，不得枚举或打开 USB/串口，不得调用
esptool，不得擦除或写入 Flash/NVS，不得启动 Broker，不得执行 PREPARE、VERIFY、
ACTIVATE、CLEANUP，也不得 Ready、merge、release、tag 或 deployment。

## 2. 前序物理请求的真实终态

物理请求：

```text
D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-03
```

真实终态永久固定为：

```text
status=CONSUMED_FAILED
failure_code=BASELINE_STATE_MISMATCH
authorization_record_sha256=e99382018c416e7fb87c99c7815ee1d366b2880a14fa36285637978d3b3e9e9b
request_binding_sha256=7e92211923ff4f37229a1e608393cbd1f9d3367cfcbaf82b203319277499cee1
terminal_result_sha256=008bff95619c4779f3ddca35492fae140ac067f9fd1f5443758c19534f254668
```

该失败发生在 destructive 标志置位之前：`flash_sha256=null`、PREPARE/VERIFY 均为 0、
Broker 未启动、恢复未尝试。它不是未授权请求，也不得重新解释为“授权前被替代”。

## 3. 请求 -04 的处置

请求：

```text
D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-04
```

永久处置为：

```text
INVALIDATED_BY_PREDECESSOR_TERMINAL_STATE_DRIFT_BEFORE_PHYSICAL_AUTHORIZATION
```

原因是其绑定摘要 `1058abf2...` 包含错误的前序状态
`SUPERSEDED_BY_EXECUTION_CLOSURE_POLICY_BEFORE_AUTHORIZATION`。该请求从未创建物理授权、
从未 claim、从未消费，也未发生物理执行；但其内容不可修补、不可复用，必须由后继请求取代。

H4 本身仍保持 `CONSUMED_PASS` 且不可重放；本层只修正 H4 输出请求的历史解释，不重放 H4。

## 4. 原证据缺陷

冻结执行器先构造基线对象，再立即比较整体摘要；摘要不一致时在函数返回前抛出异常。
调用者的 `baseline_value` 因此仍为 `None`，终端结果只能写出：

```text
observed_baseline_sha256=null
```

这会丢失已经读取到的五项哈希证据：板卡身份、串口身份、chip_id 输出、flash_id 输出和测试分区。

## 5. 证据策略 V2

后继执行器安装器必须在比较整体摘要之前构造并保留 hash-only 证据：

- `board_identity_sha256`；
- `serial_identity_sha256`；
- `chip_id_output_sha256`；
- `flash_id_output_sha256`；
- `test_partition_sha256` 和长度；
- `observed_legacy_baseline_sha256`；
- `expected_legacy_baseline_sha256`；
- `legacy_baseline_matches`；
- `before_destructive_operation=true`。

不保存 esptool 原始输出、设备路径或私密值。即使整体摘要不匹配，终端证据也必须包含上述组件摘要。

## 6. 原因判定不得提前

当前证据只能证明整体基线不一致，不能证明具体变化来源。潜在来源包括：

- 测试分区内容变化；
- USB/串口身份字段变化；
- esptool `chip_id` 或 `flash_id` 输出中包含工具版本、端口文本或格式差异；
- 原规范化对象或工具链边界变化。

在新的只读诊断完成前，不得把原因归结为板卡损坏、README 修改或任何单一字段。

## 7. 下一决策门

下一门仅为：

```text
B1-H3N2-STAGE2D9R-G3R-BASELINE-EVIDENCE-DIAGNOSTIC-READONLY-20260728-01
```

它必须单独精确授权、一次性、限时。授权后只允许：

```text
USB 候选枚举
esptool chip_id
esptool flash_id
read_flash 0x400000 0x10000
```

禁止串口打开、擦除、写入、Broker、网络、PREPARE、VERIFY。诊断只生成 hash-only 基线证据，
不会创建物理请求。预留的后继物理请求标识为：

```text
D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-05
```

只有在诊断结果另行接受并重新冻结执行闭包后，才允许创建该请求。

## 8. 多对话并发保护

任何后继主机门或物理门在创建授权前，必须验证前序请求的实际 terminal result/consumed marker，
而不能只信任源码中冻结的状态常量。发现前序状态变化时必须在 claim 前失败并要求新决策。
