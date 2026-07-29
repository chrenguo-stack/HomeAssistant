# H3/N2 Stage 2D-9R G3R PREPARE 证据控制器常量绑定修复合同

决策门：`D1-H3N2-STAGE2D9R-G3R-PREPARE-EVIDENCE-CONTROLLER-CONSTANT-BINDING-REPAIR-20260729-01`

## 前序终态

请求 `-07` 永久保持：

- `CONSUMED_FAILED`
- `LOCKED_RECOVERY_COMPLETED`
- `failure_code=AttributeError`
- `PREPARE_COUNT=0`
- `VERIFY_COUNT=0`
- replay 与 automatic retry 均禁止
- test-partition-only locked recovery 已成功

## 根因与修复

`EvidenceExecutionController.wait_serial_line()` 错误地从冻结核心执行器模块读取
`RESULT_MARKERS`、`DEVICE_FAILURE_MARKER`、`READY_TIMEOUT_CODES` 和
`RESULT_TIMEOUT_CODES`。这些常量实际属于串口握手修复模块。

后继控制器必须显式从
`h3_n2_stage2d9r_serial_handshake_repair_20260727_v1`
读取四组常量，禁止从核心执行器模块读取。任何意外异常必须转为稳定、脱敏的
`<PHASE>_EVIDENCE_CONTROLLER_<SITE>_INTERNAL_ERROR`，不得仅记录 Python 异常类名或原始异常消息。

## 测试要求

真实控制器集成测试必须直接调用安装后的 `wait_serial_line()`，覆盖：

- PREPARE ready 与 pass
- 设备 failure marker
- ready timeout
- result timeout
- 5 秒只读 late-result 窗口
- VERIFY 重新打开串口会话
- 意外异常稳定错误码
- 核心执行器模块不存在握手常量时仍可正常运行

## 后继请求与边界

生成仍未授权的请求：

`D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-08`

本决策仅允许源码、测试、CI、Draft PR、审查 Artifact 和未授权请求。禁止板卡、
USB、串口、esptool、Flash/NVS、Broker、PREPARE、VERIFY、ACTIVATE、CLEANUP、
Ready、merge、release、tag 和 deployment。

immutable 与 recovery payload TAR 字节必须保持不变，locked recovery 仍限定测试分区且最多一次。
