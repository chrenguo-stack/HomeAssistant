# H3/N2 Stage 2D-9R G3R D2-17 G14 Target Mac 静态检查验收合同

- 状态：静态检查 PASS，物理执行待显式授权。
- 基线 PR：#251。
- 精确基线 HEAD：`86d660d2c93e97122c52e9eeb0004151aa5184e7`。
- G14 acceptance binding：`44e21d03db295975439c77389f57b89b57e838db74a67c644035822d914adfe4`。
- G14 physical-pending binding：`18b5d0f710ac8cd2bb1c889745795e5820a8df8ffceda0aebe1bb924cb0cc675`。
- authorization record：`47bd58b60acb94ccf3d9e470359936fd8b610987dba99cc81adcddaf09ce1b29`。
- authorization expires：`2026-07-31T15:28:23.051833Z`。

## 验收结论

Target Mac host-only 静态检查返回 `PASS`，authorization 已创建但未 claim、未 consume。
G14 已确认并修复 canonical shell mode `0700` 与 inherited PRECLAIM 全文件 mode `0600` 合同冲突。
专用 execution view 与冻结 canonical execution root 字节等价，全部文件 mode 为 `0600`，且 canonical root 未修改。

## 安全边界

本验收不授权板卡、USB/串口、esptool、Flash/NVS、网络、Broker、PREPARE、VERIFY、recovery、ACTIVATE 或 CLEANUP。
Ready、merge、release、tag 和 deployment 均禁止。

下一精确决策门：

`D1-H3N2-STAGE2D9R-G3R-D2-17-G14-PHYSICAL-EXECUTION-20260731-01`
