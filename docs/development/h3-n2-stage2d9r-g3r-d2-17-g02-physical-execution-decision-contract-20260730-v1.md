# D2-17 G02 物理执行决策合同

## 边界

本合同落实已经批准的 `D1-H3N2-STAGE2D9R-G3R-D2-17-G02-PHYSICAL-EXECUTION-20260730-01`。
它不修改 G02 私有包、冻结 execution identity、授权记录或执行包。物理决策驱动器只负责补齐继承链运行时上下文，并调用冻结的 canonical outer。

## 执行前强制验证

1. PR #219 exact HEAD、验收 Artifact、G02 私有交付 binding、授权和 execution identity 必须精确匹配。
2. 目标 Python、OpenSSL、esptool、Mosquitto 可执行文件摘要必须保持不变。
3. 目标 Mac static-check、bind/install 幂等证明和硬件哨兵证明必须保持原摘要。
4. 授权必须仍在有效期内，且 authorization marker 和物理决策 marker 均不存在。
5. 驱动器必须在 inherited claim 前完成板卡、串口和 baseline 的只读验证；失败时不得调用冻结 execute。

## 继承链交接修复

冻结 execution package 的模块化 execute 入口需要外层提供：

- `GH_D2_13_LAUNCHER_PACKAGE_ROOT`
- `GH_D2_14_LAUNCHER_PACKAGE_ROOT`
- `GH_D2_15_LAUNCHER_PACKAGE_ROOT`
- `GH_D2_16_LAUNCHER_PACKAGE_ROOT`

同时必须提供 distinct、空白的 immutable、recovery、prepare evidence、delivery evidence 和 terminalization evidence roots，以及冻结的 physical request。

公共 host-only 集成测试必须证明：

- 错误不再停在 `LAUNCHER_PACKAGE_ROOT_MISMATCH`；
- 不再出现 argparse 必填参数缺失；
- 在无授权合成模型中仍停在 claim 前；
- authorization claimed/consumed、board/USB/serial/esptool/Flash 均为 false。

## 一次性约束

preclaim board/baseline 成功后才创建物理决策 marker。随后冻结 execute 最多调用一次。成功或失败均为终端状态，禁止重放、自动重试、ACTIVATE、CLEANUP、Ready、merge、release、tag 和 deployment。
