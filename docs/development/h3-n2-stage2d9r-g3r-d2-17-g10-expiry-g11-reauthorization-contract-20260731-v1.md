# H3/N2 Stage 2D-9R G3R D2-17：G10 超期未执行与 G11 后继授权合同

## 结论

G10 一次性授权于 `2026-07-31T06:43:11.473014Z` 到期。到期前虽收到物理执行授权，但剩余安全窗口不足以完成公共物理决策固化、执行包生成与双格式校验、操作员执行和证据终结，因此没有启动 G10 物理执行。

冻结事实：

- G10 authorization 已创建；
- `authorization_claimed=false`；
- `authorization_consumed=false`；
- `physical_decision_created=false`；
- 未创建 G10 physical runtime；
- board、USB、serial、esptool、Flash/NVS、Broker、PREPARE、VERIFY 和 recovery 均未发生；
- G10 static-check 保持 `PASS`，但其授权和全部私有材料不得重放或复用。

## G10 处置

G10 状态永久冻结为：

`EXPIRED_UNEXECUTED_RETIRED_NO_REPLAY`

处置绑定：

`eca6986ee9fba51bcd877969a924203fd10f3f5f2954e6be1d1fc2f669282b5b`

G10 私有包、authorization、static-check runtime、terminal、result 和 marker 均为不可变历史材料。不得修改、删除、移动、重新签名、重新打包或复用。

## 为什么必须使用 G11

修改 G10 授权到期时间会改变 authorization 文件、authorization record、static-check terminal 关联和私有交付根绑定。继续称为 G10 会破坏一次性授权与 generation-local runtime 隔离。

G11 必须重新创建：

1. 全新的私有 package；
2. 全新的 Target Mac runtime；
3. 全新的 execution identity；
4. 全新的 authorization 与 authorization-created marker；
5. 一次 host-only static-check；
6. claim 前 terminal 和公开导出摘要。

G11 不得读取或复用 G10/G09 私有材料。

## 当前决策边界

本公共处置不创建 G11 私有材料，也不授权物理执行。下一唯一决策门为：

`D1-H3N2-STAGE2D9R-G3R-D2-17-G11-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`

待该决策在 G10 到期状态冻结后重新明确批准，才允许创建 G11 私有 package、authorization 和 Target Mac static-check runtime。物理操作仍需后续独立授权。
