# N3-W T1 OTA V1.2 R6 Home Assistant 整体复核

2026-11-21 起始复核发现收数回执接线、节点静默和前代恢复验收三项阻断点。2026-11-22 已确认修复提交的隔离自检和精确工件 CI 全部通过，普通节点遥测已在后续隔离 ARM64 测试中通过。最终工件复验状态见文末。

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

## ARM64 基线复验与 Manager 启动修复

- `9dc2eed89cfb` 的 CI 终态为 24 项通过、2 项按策略跳过。[HA 原始镜像绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44906870780)通过。该提交的 [ARM64 三镜像基线](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44906896433/artifacts/14708741489)和 [fresh 交付工件](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44906896411/artifacts/14708272328)已通过各自工作流下载复验。三镜像 ZIP SHA-256 `de614a6b0cbbacbe80dbedc8a924e3dd603bd6f89a4ccf83d4106e8ad1e164ee`。fresh ZIP SHA-256 `49f2d168ed852bdcee88c3e4e6d44d3cfec3db28620577434873e22bce4efdd3`。两者属于该历史提交。
- 复核正常 Manager 启动发现，内部基础配置关闭 N3-W，却保留了要求 N3-W 的 OTA 开关。本地用仓库的 Settings 校验复现旧构造失败，并证明修复后保留了外层 OTA 桥接。[修复及隔离回归 `d1dfe7da5d17`](https://github.com/chrenguo-stack/HomeAssistant/commit/d1dfe7da5d17bb4b56215e4aa7e95165be60866f)，源码树 `2bdae150bd7c9d5906630ed531c4ebc967d4a357`。同时更新已知故障索引。
- 本地 412 项通过、2 项跳过、13 项未纳入。已验证隔离测试可收集、容器内启动脚本可编译，并核对了提交中的工作流接线。本地缺少 Docker。现有 exact ARM64 工作流新增回归，使用精确 Manager 镜像、隔离 Broker、打包的 HA 回执组件及 HA 2026.10.0 前代，在空节点状态经正常 Manager 选择器启动并验证挑战回执。HA 容器重建后需再次取得当前进程生成的回执。这一用例对应维护自检，生产动态权限、目标 HA 和备用 T1 仍在其各自验收范围内。
- 首次回归提交 `d1dfe7da5d17` 在 [Manager CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44918971415)和 [ARM64 源码预检](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44918971434)触发原有 Phase 5A 源码断言。合并同一行的配对和 OTA 开关写法导致断言失败，隔离容器用例尚未进入运行。[修复提交 `ccac5b714a22`](https://github.com/chrenguo-stack/HomeAssistant/commit/ccac5b714a22be15fe5b0b639d67a710832be3ba)恢复独立的旧配对开关语句，并用启用与关闭 OTA 的输入验证桥接传递。原有断言、语法及变更文件安全扫描在本地通过。
- `ccac5b714a22` 第三次查询：20 项通过、4 项运行，未见失败。[Manager CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44919242498)和 HA 源码任务通过。[ARM64 容器联调](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44919242572/job/136891453609)正在构建 Manager，回执用例尚未启动。[HA 原始镜像绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44919242576/job/136891745368)仍在复验。
- 同提交 [HA 恢复候选包 14712811990](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44919242576/artifacts/14712811990)已独立回读，ZIP SHA-256 `3675f82dd7ec0c3fd17018e9676fbd6dfb99cc8438be6e4167fbf95e7a87d939`，清单 SHA-256 `6bd494831e32ad0a4346ac27e22474a52f52b0e81cf9d104e961ed53c09403f7`。11 个文件与前版候选逐字节一致，新清单绑定 `ccac5b714a22be15fe5b0b639d67a710832be3ba`。R6 仍等隔离回执与该提交的 CI 结果。

## 隔离 Manager 启动目录修复

- `ccac5b714a22` 最终 23 项通过、1 项失败。[ARM64 运行 44919242572](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44919242572/job/136891453609)观察到 HA 注册和 MQTT 连接完成，随后 Manager 在收到首个维护自检回执前以退出码 1 结束。原用例在清理容器前未采集 Manager 日志。
- 在 `umask 022` 下，由测试脚本隐式创建的套接字父目录为 `0755`。用当前 Manager 的实际校验器复现 `pairing_control_socket_parent_invalid`。 [修复提交 `8df95b507137`](https://github.com/chrenguo-stack/HomeAssistant/commit/8df95b507137361603308db9f26e4b8541f49d6d)显式创建 `0700` 根目录，并在 Manager 退出或回执超时时保留脱敏日志。源码树 `52cd28094fc5a7ed9167f4a6ecbc66fb04bd8b42`。变更仅涉及隔离用例和故障索引。
- 本地用精确 Manager 源码、空节点数据库和新目录通过实际构造与套接字路径校验。日志脱敏和变更文件安全扫描通过。OTA 相关用例 412 项通过、2 项跳过、13 项未纳入。Manager 定向用例 25 项通过，3 项需要打开本地套接字，在当前环境未纳入。
- [新一轮 ARM64 CI 44920633239](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44920633239/job/136895669992)已通过源码预检，成对回执等待容器联调。备用 T1 的 R7 预检继续等待 R6 结果。
- 第三次查询，`8df95b507137` 共 20 项通过、4 项运行、0 项失败。ARM64 Manager 镜像构建及镜像内基础状态初始化通过，当时正在拉取绑定的 HA 和 Broker 镜像。空节点维护自检及 HA 重建后新鲜回执均在等待。另有 [fresh 交付工件](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44920633373)、[HA 目标绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44920633309)和 [M2 板端实验室 CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44920633447)仍在运行。已停止本轮主动轮询，GitHub 工作流继续执行。

## 首次回执超时

- `8df95b507137` 最终 23 项通过、1 项失败。[ARM64 运行 44920633239](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44920633239/job/136895669992)通过前置检查。隔离容器内 Manager 持续运行且重启次数为 0，HA 首次 MQTT 配置成功，首个维护自检回执超时。此轮未进入 HA 重建后验证。
- 检查 Home Assistant 2026.10.0 MQTT 源码发现，没有启用的 MQTT 配置条目时，`async_wait_for_mqtt_client` 会立即返回 `False`。回执组件只依赖 MQTT 集成，与创建条目的 N3-W MQTT 引导可并行启动，因此首次启动可能永久跳过订阅。实际容器中是否触发该路径将由下一轮联调验证。
- [修复提交 `0364f5b20835`](https://github.com/chrenguo-stack/HomeAssistant/commit/0364f5b20835e0c2c9dcde23273bd07aba9c9f66)为 HA 回执组件声明 N3-W MQTT 引导依赖。候选包回归检查这一配置。隔离测试保留原有的两次回执断言，失败时采集 Manager、HA 和 Broker 的脱敏日志。源码树 `8cc86173d8aa23dd0ac2b9767fcdf52ae3e9fc11`，本地 412 项通过、2 项跳过、13 项未纳入。用 HA 2026.10.0 的实际 MQTT 准备函数独立复现空配置返回 `False`、加载后返回 `True`。变更范围为 HA 回执启动依赖、CI 诊断和故障索引。待实际 ARM64 联调确认，新结论仍不作为备用 T1 预检证据。
- 定向模拟调用 HA 2026.10.0 的实际依赖加载函数和 MQTT 准备函数，复现旧顺序漏订阅。修复后模拟首次启动和重建均生成本次回执。
- [恢复包 14714570528](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44922270595/artifacts/14714570528)回读通过。ZIP SHA-256 `a5692657f6bc3e56697c88c2d513b90384cdbb359ce68511d72f4eeabe66c4d8`，清单 SHA-256 `7cbe38be9645b2dd0cebb0d00d3c4f49edfb4c2561706e1259d0d2a2a2cd881d`。11 个文件与本地重建逐字节一致，包内回执组件清单包含新依赖。
- `0364f5b20835` 第三次查询为 21 项通过、1 项失败、2 项运行。[隔离 ARM64 联调](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44922270584/job/136900669934)仍卡首个回执。新日志确认 HA 已订阅，Broker 接收 Manager 的挑战并向 HA 转发。CI 使用 QEMU 10.2.3，正在复核回执写入和校验的进程启动标识是否来自相同的内核视图。

## 回执进程启动标识修复

- CI 日志确认使用 QEMU 10.2.3。[该版本的进程视图实现](https://github.com/qemu/qemu/blob/v10.2.3/linux-user/syscall.c#L8565)在读取自身的 `/proc/self/stat` 或 `/proc/<自身PID>/stat` 时生成模拟数据。[启动时间](https://github.com/qemu/qemu/blob/v10.2.3/linux-user/main.c#L223)来自模拟器任务初始化。另一个进程读取该 PID 时使用内核启动时间。原写入端和校验端可看到不同值。
- [修复提交 `9cb014a9b48c`](https://github.com/chrenguo-stack/HomeAssistant/commit/9cb014a9b48c5fbaf4511d540a9b0ac634b7918f)让 HA 回执写入和宿主验收都读取 `/proc/<pid>/task/<pid>/stat`，保持进程仍存活且启动标识一致的要求。联调失败时只附加回执读取退出状态和脱敏错误，避免输出回执内容。源码树 `6c97f6135e2342a2d080b05f8fd0e9b6e257fdb1`。
- 本地跨进程测试模拟 QEMU 自身路径与内核路径返回不同启动时间。有效回执通过，写入不匹配启动时间的回执被明确拒绝。412 项相关回归通过、2 项跳过、13 项未纳入。源码编译、Git 差异检查和变更文件安全扫描通过。等待同一提交的真实 ARM64 回执验证。
- [恢复包 14714134525](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44923324909/artifacts/14714134525)绑定 `9cb014a9b48c5fbaf4511d540a9b0ac634b7918f`，ZIP SHA-256 `4bdd756b312e5f3504a2cc0c9b30c0e62c654f265737764b14a98abf1dd64686`，清单 SHA-256 `c1e9cab231bb1935827fbf9c99b5f258ec2a638ad5af6c500b1dad79751118df`，pyz SHA-256 `f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84`。11 个包内文件和本地独立重建逐字节一致。包中 HA 组件与 pyz 验收模块均包含相同的内核进程路径修复。
- 第三次查询时 23 项通过、1 项运行、0 项失败。[ARM64 隔离联调步骤](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44923324802/job/136903867551)成功，覆盖空节点首次启动回执、HA 容器重建后新的挑战回执。[三镜像工件 14714677167](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44923324802/artifacts/14714677167)已上传，GitHub 登记 ZIP 摘要 `sha256:b7739e322e77b131898efec3858c4e8b7968b82da9deac99586503b222225130`。最后的工件下载及绑定验证仍在进行。本轮已停止主动轮询，远端工作流继续运行。备用 T1 需按原边界另行预检。

## 修复提交 CI 终态（2026-11-22）

- PR #815 仍为打开的草稿，候选 `9cb014a9b48c5fbaf4511d540a9b0ac634b7918f` 基于 `main@4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。该候选的 24 个 PR 工作流全部通过。[精确 ARM64](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44923324802/job/136903867551)日志回读确认 `HA_EXACT_ARM64_MANAGER_MONITORING_ROUND_TRIP=PASS` 和 `R6_EXACT_ARM64_POST_UPLOAD_BINDING=PASS`。[目标 HA 冻结归档绑定与签名暂存](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44923324909/job/136904062221)同样通过。
- 三镜像工件 `14714677167` 的下载后绑定由 CI 复验。[同提交 fresh 交付工件 `14714912137`](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44923324807/artifacts/14714912137)的 ZIP 摘要为 `sha256:7ac35773578381d7d1a024e7c982237a3a3a2c28e774b681d391de913023e620`。两项是隔离和候选材料证据。
- R6 最初要求同时取得真实隔离容器的无节点自检与普通遥测回执。自检及 HA 重建后的复验已通过，普通遥测目前有模拟和单元证据。继续复用既有 ARM64 三容器用例补实链路验证。R7 只读预检另按设备范围与授权推进。

## 普通遥测容器回归与 R7 预检准备（2026-11-22）

[回归提交 `84da7cd68e2f`](https://github.com/chrenguo-stack/HomeAssistant/commit/84da7cd68e2f65fb011c32db1c3683b76a48112b)的源码树是 `06bdb7ec703daa60546765e5d63f68451f45c533`。先保留两次空节点挑战回执，随后只在隔离 Manager 容器中登记一个模拟节点。节点使用独立测试账号向 Broker 发送正常遥测。Manager 从正常入口生成持久游标和标准遥测，HA 使用常规 MQTT 客户端接收。升级器用实际 HA 回执读者和 Manager 活库的 SQLite 备份关联节点、启动会话、序号和接收时间。测试不会向标准遥测主题注入成品消息。成功时 ARM64 日志记录 `HA_EXACT_ARM64_NATURAL_MONITORING=PASS`。

已在本地用固定 Manager 源码验证模拟节点登记、普通入口、实际 SQLite 备份、HA 收数记录和宿主验收。该模拟替代 Docker 和 MQTT 传输。412 项回归通过、2 项跳过、13 项未纳入；容器测试收集、Git 差异检查和变更安全扫描通过。[ARM64 容器回归](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757245)正在运行。

R7 预检按 [V1.2 第 13 节](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md)组织。只读核对顺序如下。

| 核对项 | 通过证据或分类 |
| --- | --- |
| 候选材料 | 复核 PR 头、三镜像 CI、恢复包清单及目标 HA 2026.10.4 原始归档身份。旧提交的工件只作历史证据。 |
| 备用 T1 和健康基线 | 操作员在本地确认备用机及 SSH 目标；只读核对 ARM64、三项服务状态、镜像引用和 ID、HA 健康、Manager/Broker 会话和已有数据位置，记录可用证据的脱敏摘要。观察到的 HA 版本与拟测前代不符时先分类，不重装。 |
| 事务与恢复前提 | 核对 V2、历史 Manager 和 HA USB 活动记录及恢复服务状态。只读取状态与文件元数据，记录当前运行组合、已有恢复引导和事务状态。活动或无法判定的事务先单独处理。 |
| 内部与 USB 空间 | 核对实际数据根和 Docker 根的容量。仅观察操作员指定介质及已存在的挂载，记录文件系统、介质身份摘要和可读的容量。尚未挂载的盘记录待测可用空间，避免从分区总大小推断可用空间；确认是否足够留到有相应授权的执行步骤。 |
| R8 输入 | 形成前代、目标、测试盘、所需空间、受保护数据和授权的差异单。旧 Manager 缺自检入口或升级组合未就绪时记录准备缺口。准备装载、激活、OTA、故障注入和断电续办各按授权执行。 |

可复用 [U0 基线只读语义](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/docs/development/N3W_T1_CORE_UPDATER_U0_REAL_T1_READONLY_BASELINE_PREEXECUTION_20261104.md)。实际 R7 核对应绑定本次候选和现场。候选 `check-candidate-activation` 要求新版恢复包已落盘且 socket 已运行，适合后续已经安装的状态。本轮 R7 只准备核对顺序，备用机和介质访问等待相应授权。

### 同提交验证进度

- [ARM64 联调步骤](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757245/job/136908307028)已通过。该用例验证两次空节点自检以及普通节点 MQTT 遥测，普通遥测的 HA 回执与 Manager 持久游标一致。第三次查询为 23 项成功、1 项运行，0 项失败；仅三镜像的下载后绑定复验仍在进行。
- [恢复包 `14715501376`](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757335/artifacts/14715501376)绑定 `84da7cd68e2f65fb011c32db1c3683b76a48112b`。ZIP SHA-256 `078500292fba59c2acd187ca3613258a7c6d1c6594113d925e98352d4bc9b055`，清单 SHA-256 `9cfad52a76670474cb328d3d22c0a7d4985f38f3e79fbe68e82a6b6550c8fa48`，pyz SHA-256 `f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84`。11 个交付文件和本地独立重建逐字节一致。
- [三镜像工件 `14715154066`](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757245/artifacts/14715154066)已上传，GitHub 发布的 ZIP 摘要 `sha256:740e66ab1027141e5f8904b308bf695c8fe57172807d84f8627069e6e1926982`。[fresh 交付工件 `14715332642`](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757265/artifacts/14715332642)所在工作流已成功，ZIP 摘要 `sha256:dedd4adfecaae74ab1a98cf6cbf825ff00d10970ea6e80e31f17bc88346692f2`。本轮停止主动轮询，备用 T1 R7 现场预检尚未开始。
