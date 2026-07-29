# H3/N2 Stage 2D-9R G3R PREPARE 超时证据留存修复合同

## 冻结事实

D2 请求 `...-06` 已永久终止为 `CONSUMED_FAILED / LOCKED_RECOVERY_COMPLETED`，失败码为 `PREPARE_RESULT_TIMEOUT`。授权、合同检查、结果、终端输出和 consumed marker 已相互校验；重放与自动重试均禁止。

结果只保留了 PREPARE 串口捕获和 Broker 日志的 SHA-256，没有保留可阅读的脱敏正文，因此不能从现有证据区分节点复位、Broker 断开、延迟结果、未知结果格式或完全无结果。

## 决策

未来物理后继执行器必须在任何成功或失败终态中持久化：

1. `prepare-serial.redacted.jsonl`：串口事件脱敏记录；
2. `broker.redacted.jsonl`：Broker 事件脱敏记录；
3. `prepare-timeline.json`：命令发送、ready、结果、复位、重枚举、TLS/Broker 连接与断开的有序时间线；
4. `prepare-evidence-manifest.json`：上述文件摘要和分类。

证据必须在 locked recovery 开始之前、临时目录清理之前落盘，并使用目录 `0700`、文件 `0600`、原子替换和 `fsync`。

## 隐私边界

不得保存原始 PREPARE/VERIFY 命令、凭据、MAC、IP、USB 设备路径、用户目录或私密托管路径。已知安全的 `stage2d9r_*` 标记可保留；其他未知行默认只保留 SHA-256。

## 分类

分类固定为：

- `NO_RESULT`：发送命令后没有结果、复位、Broker 断开或可识别未知结果；
- `SERIAL_RESET`：结果前观察到设备复位；
- `BROKER_DISCONNECT`：结果前观察到 Broker/TLS 连接断开；
- `LATE_RESULT`：结果在主截止时间之后、延迟观察窗内出现；
- `UNRECOGNIZED_RESULT`：出现 PREPARE 结果形态但不是已接受的 pass/fail 标记。

## 本轮边界

本轮只增加源码、测试、CI、审查 Artifact 和 Draft PR。不会连接板卡、枚举 USB、打开串口、运行 esptool、修改 Flash/NVS、启动 Broker、执行 PREPARE/VERIFY、创建新物理请求或创建物理授权。immutable/recovery payload 字节保持不变。
