# H3/N2 Stage 2D-9R G3R 串口握手修复合同 V1

## 1. 触发事实

一次性 D2 `D2-H3N2-STAGE2D9R-G3R-SUCCESSOR-20260727-01` 已进入
`CONSUMED_FAILED / LOCKED_RECOVERY_COMPLETED`。冻结固件已完成擦除、写入和
校验，但主机未观察到首次 `stage2d9r_command_ready=PREPARE`；PREPARE 和
VERIFY 的执行计数均为 0。旧授权、旧执行包和旧私密材料不得重放。

## 2. 固件侧修复

V2 执行器保留 V1 的命令格式、分区、NVS、候选摘要、授权绑定和失败关闭
语义。唯一运行时变化是：

- 当状态为等待 PREPARE 时，每 1000 ms 重复输出一次 PREPARE ready 标记；
- 当状态为等待 VERIFY 时，每 1000 ms 重复输出一次 VERIFY ready 标记；
- 命令被接受、进入终态或失败关闭后立即停止重复；
- 重复标记不包含密钥、口令、命令正文、私密路径或串口路径。

该机制把 ready 从一次性启动事件改为等待状态的幂等可观察投影，不增加第二次
命令机会，也不放宽 command replay 门。

## 3. 主机侧修复

源代码提供 `SerialCaptureSession` 和 `RepairedHandshakeController`：

1. 在启动隔离 Broker 前打开并稳定绑定已选串口；
2. 使用同一连续捕获缓冲区等待 PREPARE ready；
3. 仅在 ready 出现后写入一次绑定命令；
4. PREPARE 自动重启后重新选择同一板卡并建立新的 VERIFY 捕获；
5. 所有成功、设备失败和超时路径都写入 mode-0600 的脱敏 transcript；
6. 停止 Broker 时同时关闭串口捕获线程和句柄。

源模块单独运行只输出
`SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_PACKAGE`，不会枚举串口、启动 Broker 或执行
任何物理操作。未来物理执行必须由新的精确 D2 包显式导入并绑定该模块。

## 4. 分阶段错误码

- `PREPARE_READY_MARKER_TIMEOUT`：未观察到 PREPARE ready；
- `PREPARE_RESULT_TIMEOUT`：命令已发送，但未观察到 PREPARE pass；
- `VERIFY_READY_MARKER_TIMEOUT`：自动重启后未观察到 VERIFY ready；
- `VERIFY_RESULT_TIMEOUT`：VERIFY 命令已发送，但未观察到 VERIFY pass。

`DEVICE_EXECUTOR_FAILED` 继续表示固件明确输出失败终态。阶段错误码不得再次合并为
通用 `SERIAL_EXPECTED_MARKER_TIMEOUT`。

## 5. 证据脱敏

超时 transcript 保留启动日志、ready/pass/fail 标记和公开摘要，但任何包含
`GH2D9R_PREPARE_V1` 或 `GH2D9R_VERIFY_V1` 的命令行必须替换为只含 schema 和
`[REDACTED_COMMAND_MATERIAL]` 的记录。公开 Artifact 不得包含原始命令、私钥、
MQTT 密码、unlock preimage、persistence key、串口路径或用户目录路径。

## 6. 新构建边界

修复候选使用新 build binding：

`0a2c96b7615d9f222cf72fcf899b6caf3a7c875f`

因此此前的私密命令、candidate digest、授权记录、immutable image、recovery
绑定和执行包全部不可复用。后续必须依次重新生成并复核新的公开候选、可重现
immutable Artifact、私密托管/U1、baseline 和精确 D2。

## 7. 本 D1 的边界

允许：新分层 Draft PR、源代码、静态/主机测试、ESP32-C6 编译和新的公开
review/compile Artifact。

禁止：连接板卡、USB/串口枚举、esptool、Flash/NVS、主机网络、Broker、
PREPARE、VERIFY、ACTIVATE、CLEANUP、旧 D2 重放、Ready、merge、release、tag
和 deployment。
