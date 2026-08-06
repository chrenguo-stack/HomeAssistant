# C-06 历史投影故障矩阵状态

## 当前门

`D1-C06B3-PR269-REAL-ISOLATED-MQTT-HA-RECORDER-FAULT-MATRIX-RETRY-RESTART-RECONCILIATION-AND-CLEANUP-STACKED-DRAFT-IMPLEMENTATION-20260806-01`

精确堆叠基线：PR #269 HEAD `0cc8daa58fdf1d1200af3c3c2c3ed53db2963b41`。

## 唯一目标

在不修改 C-06 运行时代码和默认值的前提下，验证历史投影链面对错误绑定、迟到或重复响应、Home Assistant 暂时不可用、Manager 重启、Broker 重启和 worker 单次异常时能够失败关闭、持久 retry、恢复并完成精确读回。

## 测试分层

- Fast：MQTT RPC 精确绑定、迟到/重复响应、pending stop、worker 异常隔离。
- Full/isolated：临时 Mosquitto、完整 Home Assistant、Recorder 和正式 Manager 入口；revision 2 注入、HA 不可用 retry、Manager/HA 重启恢复、Broker 重启幂等验证和彻底清理。
- Live：不执行；T1 和生产验收继续 pending。

## 安全边界

- C06-B2 运行默认值保持关闭且不变。
- 不访问 T1、生产 Broker、Home Assistant、Recorder 或 Manager 数据库。
- 不修改 PR #260—#269。
- 不生成生产凭据、授权包或部署包。
- 不执行 Ready、merge、release、tag、deploy 或版本激活。

## 停止条件

若真实隔离故障矩阵发现运行时代码缺陷，本门只冻结失败阶段、清理结果和脱敏证据；运行时修复必须使用新的精确后继授权。
