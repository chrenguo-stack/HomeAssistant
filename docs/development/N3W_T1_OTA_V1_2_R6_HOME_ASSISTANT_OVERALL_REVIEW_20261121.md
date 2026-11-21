# N3-W T1 OTA V1.2 R6 Home Assistant 整体复核

2026-11-21。结论为 **待修复**。包、源码和 CI 已绑定。现有 HA 候选仍有收数回执接线、节点静默以及前代恢复验收三个阻断点。备用 T1、实机介质、合并和发布未进入执行。

## 复核对象和验证结果

| 对象 | 固定依据 |
| --- | --- |
| 源码 | [PR #815](https://github.com/chrenguo-stack/HomeAssistant/pull/815) 仍为打开的草稿。主分支 `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`，候选 `4e794161eb7bb5f637c6045b9fba90d98b812b9e`，候选源码树 `8078ef2bd1686a759398e43c2a79b2e736e5b530`。 |
| 设计和用例 | [V1.2 第 5–10 节](N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md) 和 [R5 验收证据](N3W_T1_OTA_V1_2_R5_HOME_ASSISTANT_ACCEPTANCE_EVIDENCE_20261121.md)。 |
| GitHub CI | 当前提交查询到 22 个成功、8 个策略跳过的工作流记录，全部结束。跳过记录来自 fresh install ARM64 与 fresh bootstrap payload 工作流，含重复事件运行。[冻结归档绑定及签名暂存](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44903623767/job/136844710111)通过。 |
| 原始 HA 镜像 | 工件 `13391983948` 内的 HA 2026.10.4 ARM64 归档，835,309,535 字节，SHA-256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`。CI 使用测试签名、模拟宿主与该原始字节。 |
| 宿主恢复包 | [工件 14707120930](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44903623767/artifacts/14707120930)。独立回读的 ZIP SHA-256 为 `21c9c1047e912b000bcc408d237ee0f932262cca52cee90df0a6b837e69f6697`，清单为 `003a9b21f2f0aeb4e0d8a4ec1e2466d734c347ae58707bfc580f698e8ff34e26`，pyz 为 `37301e73dab33254d6fc5318ab0f60729a4c0533d4e697a8ad89bc79707c6e89`。核对清单所列 8 个文件及摘要。 |
| 本地回归 | 405 项通过、2 项跳过、13 项因 Docker、原始大工件、原生套接字或历史源对象等环境条件未纳入本地回归。另做候选包闭合集、已知前代源码与配置、Broker 日志失败的定向核对。 |

## 三个候选阻断点

| 优先级 | 观察与影响 | 关闭条件 |
| --- | --- | --- |
| P1 · 监测回执缺少交付接线 | 安装前必须捕获监测基线。[HA 默认配置](https://github.com/chrenguo-stack/HomeAssistant/blob/4e794161eb7bb5f637c6045b9fba90d98b812b9e/infra/n3w-t1/production/homeassistant-configuration.yaml)只启用原有 MQTT 引导，Compose 未挂载 `n3w_ota_monitoring`，恢复包的八个文件也不含该组件。已通过包字节、源码与配置交叉确认。默认 Stack 前代 Manager 的 [固定源码](https://github.com/chrenguo-stack/HomeAssistant/blob/5b32e1ae82104a42f9e4e6907fe44d9172e87615/host/greenhouse-manager/src/greenhouse_manager/runtime/mqtt_service.py) 未包含本次维护自检的请求入口。以已有默认基线进入安装，HA 无回执时自然消息与自检均不能建立基线，执行器停在首次停服前。签名暂存 CI 只走到 `PREPARE` 准入。现有激活预检只允许 Manager 启用与挂载差异，无法核验 HA 回执接线。 | 绑定前代和目标的 HA 组件、配置及 Manager 自检能力，核对它们的实际启动入口。把前代回执能力检查纳入激活前验证。在隔离环境从真实候选入口证明一次自然收数和一次无节点自检。 |
| P1 · 自然基线后静默会误触发回滚 | [基线选择](https://github.com/chrenguo-stack/HomeAssistant/blob/4e794161eb7bb5f637c6045b9fba90d98b812b9e/tools/n3w_t1_core_updater_ha_acceptance.py#L68)只在自然证据失败后才验证自检。自然基线成功时只持久化自然方法，[新版补验](https://github.com/chrenguo-stack/HomeAssistant/blob/4e794161eb7bb5f637c6045b9fba90d98b812b9e/tools/n3w_t1_core_updater_ha_usb.py#L564)和旧版恢复核对均拒绝调用未预验自检。节点此后按正常节奏静默或离线，即使正式业务路径健康，新版仍可能耗尽补验后回滚，旧版也可能持续等待。既有用例证明未预验自检会被拦截。 | 在停服前绑定可用等效路径。运行验收仍优先自然消息，缺少自然消息时才调用已核准的等效方法。覆盖自然基线后静默但链路健康、以及链路真正中断两种情况。 |
| P1 · 辅助 Broker 日志阻断健康旧版验收 | [前代健康检查](https://github.com/chrenguo-stack/HomeAssistant/blob/4e794161eb7bb5f637c6045b9fba90d98b812b9e/tools/n3w_t1_core_updater_ha_recovery_startup.py#L979)在核对收数和数据之前，仍要求两个 MQTT 客户端的日志认证。Broker 日志到达 10,000 行覆盖上限会抛出 `broker_log_coverage_insufficient`。定向模拟中，三项服务运行，HA 查询返回 200，独立收数探针可返回 PASS，单独注入日志覆盖不足仍让恢复提前中断，收数和数据探针均未调用。已启动的旧版可能持续显示恢复中。 | 用本笔受影响的真实业务证据决定前代验收，辅助日志只留诊断。测试日志缺失且收数成功可结束恢复，日志正常且业务实际中断仍不能结束。 |

## 其他边界

- **事务和恢复。** Manager 只提交准备和安装意图。宿主私有授权、状态锁和持久记录约束首次停服、备份、释放唯一前代、目标写入与最终提交。默认源和模拟覆盖原盘等待及自动续办、错误材料拒绝、前代恢复重入、授权防重放和最终提交重入。U12 未提交时只在验收记录与当前运行身份一并成立的情况下前推。
- **权限。** 候选通过只读目录开放 Unix 套接字及批准投影，套接字核对 Manager UID。路径、镜像、USB 和授权不能由 Manager 请求自填。模拟测试及精确 CI 覆盖签名内容、镜像身份、归档摘要与本地发布序号。正式发布信任根、签名发布端、升级器可信更新及客户启用仍待交付，现有恢复包安装只接受独立提供的清单摘要且只支持首次落盘和字节一致的重试。
- **用户可见状态。** 核心事务可独立于 Manager 恢复；停启期间的本地用户只读入口、缺原盘的具体提示和安全拔盘投影仍待接通。发布投影位于 `/run/n3w/t1-ota`，工程命令负责发布；还需验证重启后的投影重建与安装前准备事务可继续交互。
- **阶段边界。** 本轮只做源码、包及隔离模拟复核。前三项应先做源码和成对回归闭环，再把新的提交、CI 和候选包重新绑定。备用 T1 的部署、断电和回滚验证按专门授权推进。Broker OTA 等 HA OTA 完成后再开发。

## 修复批次回读

- [修复提交 `9dc2eed89cfb`](https://github.com/chrenguo-stack/HomeAssistant/commit/9dc2eed89cfb3ccdb9d08c3d3555b61668dcbb1d)，源码树 `dae190871efe30156991455b2b55342624eca4db`。包携带 HA 回执组件、清单与配置。HA 与 Manager 使用同一 `GH_SYSTEM_ID`，激活预检核对两个只读挂载、默认 HA 配置及正在运行的 Manager 自检入口。实际自检在激活后、首次停服前运行。
- 新事务优先用自然遥测建立基线，并保存一次停服前验证成功的自检证明。试运行和回滚时优先用自然证据，节点静默才调用已预验自检。按本笔业务和数据证据接受前代，历史记录缺少监测方法时仍沿用原有核对。模拟覆盖无证明暂缓、自然转静默且健康、Broker 日志缺失但监测可用和业务真实不可用。
- 本地 412 项通过、2 项跳过、13 项环境相关用例未纳入。临时恢复包的 systemd 单元、变更文件安全扫描及候选 Compose 结构检查通过。
- [HA 候选 14707509111](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44906870780/artifacts/14707509111) 已独立回读。ZIP SHA-256 `b269a0d2d48bc8227546f5dc787876334632c44b155e8fed6dcaf5742e8054d3`，清单 SHA-256 `afc00d8283c89cce99b8fb1dce1e0785afa72ebc73cf1aebbe0242b0db9c3a82`，pyz SHA-256 `9a210a9ea1b6fc6d8fad657c86b89e734338db37c25a2006ac32f7e437a57bc4`。11 个文件摘要及内容均与本地重建一致。
- 第三次 CI 查询时，19 项通过、2 项按策略跳过、5 项运行中。[HA 目标绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44906870780)已通过源码任务，原始镜像绑定仍在运行。现有 [ARM64 基线构建](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44906896433)及 [fresh 交付包构建](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44906896411)已开始。
- 修复源码与模拟证据已归档。后续需取得兼容 Manager 的确切工件、验证 HA 和 Manager 在同一个隔离候选上使用同一条实际收数路径，再推进 R6 结论。R7 实机预检与变更仍依原授权执行。
