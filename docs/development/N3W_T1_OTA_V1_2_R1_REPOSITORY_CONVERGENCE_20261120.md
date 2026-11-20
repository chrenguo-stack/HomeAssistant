# N3-W T1 OTA V1.2 R1 旧工程收敛记录

日期 2026-11-20。任务 `N3W_T1_OTA_V1_2_PRE_ALIGNMENT_REPOSITORY_CONVERGENCE`。本记录用于 R2/R3 选取实现和回归证据。

## 对照范围

- 产品合同以 [V1.2 架构](https://github.com/chrenguo-stack/HomeAssistant/blob/8e65bbf21c888eb4aa7e9625e7de8c3ecfd83e5e/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md) 第 1–11 节为准。比较代码基线为 `main@8e65bbf21c888eb4aa7e9625e7de8c3ecfd83e5e`。
- 旧栈尖端与该基线共同祖先为 `bce6bd82023d5f5322eea1ab363a29df8a4cadd8`。从该祖先至 #811 有 494 个变更路径。#807 单独对其 GitHub 基线有 350 个变更路径，其中 123 个位于执行包目录、119 个是开发文档、77 个位于工具测试目录。
- 下表按能力处置。未明确选为复用候选的旧执行包、临时脚本、CI/产物绑定、状态快照和环境专用数据默认只留在旧栈。其他产品模块以 `main` 为准。后来确认的新依赖应记录具体源码和测试后再引入。

| 旧 PR | 基线或上游 | 已核对的 head | 状态 |
| --- | --- | --- | --- |
| [#807](https://github.com/chrenguo-stack/HomeAssistant/pull/807) | `ab277001dc9b31dcccb4d36b1507cec5f26d5a1d` | `7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c` | 开放草稿 |
| [#809](https://github.com/chrenguo-stack/HomeAssistant/pull/809) | #807 | `06332c58de850c590da83e0971d7576291f371b2` | 开放草稿 |
| [#810](https://github.com/chrenguo-stack/HomeAssistant/pull/810) | #809 | `4abebaa61c1db0be41a724c45263e26ac15eb06e` | 开放草稿 |
| [#811](https://github.com/chrenguo-stack/HomeAssistant/pull/811) | #810 | `6642c7202e0757f2e3527b13e32085cff1e54859` | 开放草稿 |

## 能力去向

`KEEP` 为可复用能力，具体接线仍以 R2 为准。`ADAPT` 为保留原语、改造调用或判定。`ARCHIVE_ONLY` 留作证据。`DROP` 从 V1.2 产品入口和交付物排除。

| 能力 | 处置 | 来源和依赖 | 当前证据及引入条件 |
| --- | --- | --- | --- |
| Manager Generic V2、已有受限 OTA IPC | KEEP（沿用 main） | `tools/n3w_t1_core_updater_v2*.py`、`tools/n3w_t1_core_updater_components.py`、Manager 的 `runtime/t1_ota_*` 和宿主 IPC。复用本地身份、运行绑定、互斥和受限命令合同。 | main 已有单组件基础。R3 用现存单元和合同测试固定基线。整套事务与 Broker 运行能力另按实际范围验证。 |
| 宿主持久事务、恢复材料身份、状态锁 | KEEP 原语；ADAPT 阶段接线 | #807 的 `ha_usb_state`、`ha_recovery`、Generic V2 状态存储。需要私有目录、原子落盘、统一互斥和旧版记录解析。 | 复用校验和持久化原语。前置持久意图、进展和终态写入须按 V1.2 补齐。保留历史授权字段供校验，已消费记录始终禁止重放。 |
| USB 准备、重新定位及容量复核 | ADAPT | #807 的 `ha_prepare`、`ha_prepare_host`、`ha_usb_media` 和前代工件身份，依赖宿主挂载核对、双向空间和目标摘要。 | U10 第五次只读预检曾验证绑定及容量。V1.2 要求适用文件系统、UUID 与事务工件、按事务写入和完整回读。只引入符合这些条件的原语。 |
| 首次停服与一致备份 | ADAPT | #807 的 `HaUsbU7BackupController`、`ha_backup`、`U7RuntimeOwner`。加密备份、清单校验和静止写入方为依赖。 | 旧控制器先停服再落盘 U7 事实，普通异常有恢复分支。宿主重启接管只覆盖 U1–U3 和 U9 以后，首次停服至 U9 前需要补齐恢复责任。U7 历史误判和补验用作正反回归。 |
| HA 镜像装载、身份核对及持久提交 | ADAPT | #807 的 `ha_u11`、`ha_u11_host`、U13A 实现及运行工件绑定。依赖可验证的前代材料和受保护数据。 | 有历史 U13A 实机提交记录。将写意图、实际镜像身份、业务验收和持久提交接入同一事务，并用于断电核对。历史版本号和工件不作本轮候选。 |
| U13B 回滚、打开原盘后续办、已恢复服务收敛 | ADAPT | #807 的 `ha_u13b*`、U9+ 协调器及相应 `test_n3w_t1_u13b_*`。依赖原镜像、真正的写入边界、加密备份和实际业务事实。 | 历史记录确认某次 U13B 持久回滚和业务恢复，仍有独立重启复验 STOP。将一次观察失败降级为诊断或限定补验，旧版已健康时保护服务。已提交只收尾。 |
| 核心阶段与状态投影 | ADAPT | #807 的 `ha_ipc` 和 Manager 适配。依赖宿主事务及纯观察接口。 | 复用 U9+ 的阶段识别，重接其容量投影。旧代码仍在部分 U9+ 分支调用准备容量投影，需覆盖该附加字段抛错和服务端启动失败。旧 `ERROR` 或内部紧急状态作为诊断或恢复进度处理。已确认恢复健康后才持久报告升级失败。 |
| KF-168 脱敏 USB 诊断 | KEEP 诊断能力 | #809 在 `ha_prepare_host` 的日志改动，复用对应模拟断言。 | 只带入工具、操作、退出码和安全原因分类。它改善解释，不参与提交或回滚判定。原失败子进程的现场根因仍未确认。 |
| Manager IPC 与 USB 挂载目录隔离 | ADAPT | #810 同时改 daemon、systemd 和 Compose。验证 root 目录属性、只读导出、Manager UID 与容器可见性。 | 有候选源码和测试。#811 记录 #810 的隔离尝试已回退，隔离未保留在实机。整组作为宿主运行合同复核，恢复责任须独立于展示和 IPC 初始化。 |
| IPC 迁移启动与回退就绪 | ADAPT 条件检查；ARCHIVE_ONLY 历史执行器 | #811 的 `kf168_ipc_migration_readiness_repair` 执行包及测试。 | 有模拟和 CI 证据。仅在最终采用独立导出迁移时复用其有界就绪检查和测试。旧执行器、授权和固定材料不进入产品路径。 |
| 旧 Phase-A/B 证据、旧候选和执行包 | ARCHIVE_ONLY | #807–#811 的阶段结果、现场回执、精确工件、旧授权声明和专用 CI。 | 保留固定链接和出处。模拟通过、只读通过、单次实机恢复与完整 V1.2 验收分别记录。 |
| 自动擦盘、全盘标准化、旧验收判据 | DROP | 旧 `SubprocessPrepareBackend.format_and_mount()` 的擦盘和格式化，以及只认固定现场介质位置或信号的流程。 | V1.2 支持可用的既有文件系统和文件，按 UUID 与工件绑定。固定总停机时限、重复认证/日志或界面错误不单独决定升级结果。 |

## 历史证据与本轮验证

- 实机成功提交仅对应已授权的旧候选。[U13A 实机提交](https://github.com/chrenguo-stack/HomeAssistant/blob/6642c7202e0757f2e3527b13e32085cff1e54859/docs/development/N3W_T1_U13A_LIVE_COMMIT_CLOSURE_20261117.md)
- 第一次停服后的应用状态误判、真实只读补验，以及 U10 只读通过都已归档。 [U7 误判与补验](https://github.com/chrenguo-stack/HomeAssistant/blob/6642c7202e0757f2e3527b13e32085cff1e54859/docs/development/N3W_T1_U13B_P3_U7_READONLY_PREFLIGHT_20261118.md) · [U10 第五次只读预检](https://github.com/chrenguo-stack/HomeAssistant/blob/6642c7202e0757f2e3527b13e32085cff1e54859/docs/development/N3W_T1_U13B_P3_U10_READONLY_ATTEMPT05_PHYSICAL_CLOSURE_20261119.md)
- U9+ 独立旧源码复核及 CI 通过，真实复验留有 STOP。#811 只证明就绪条件的源码闭环，文档记录 #810 隔离候选已回退。 [旧源码独立复核](https://github.com/chrenguo-stack/HomeAssistant/blob/6642c7202e0757f2e3527b13e32085cff1e54859/docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_INDEPENDENT_SOURCE_REVIEW_CLOSED_PHYSICAL_ACCEPTANCE_PENDING_20261119.md) · [实机复验 STOP](https://github.com/chrenguo-stack/HomeAssistant/blob/0f50f0b98eefeb6780aca597ddd0da798251159d/docs/development/N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_LIVE_REVALIDATION_STOP_20261120.md) · [#811 源码闭环](https://github.com/chrenguo-stack/HomeAssistant/blob/6642c7202e0757f2e3527b13e32085cff1e54859/docs/development/N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READINESS_SOURCE_REPAIR_CLOSURE_20261120.md)
- 本轮在精确 `main` 上运行 Generic V2 A2、HA USB R1/R2 和 HA IPC 四个模块的聚焦测试。首轮 86 项通过、2 项受环境限制。静态 HA 容器测试依赖未安装的 Docker 命令，Unix socket 往返测试受执行环境限制。排除这两项后 86 项通过，待 R3 在适用环境验证此两项。公开仓库安全扫描通过。

## R2 输入

从现有产品入口和 HA 单组件路径开始。先设计首次停服前的宿主责任落盘、旧版恢复、非格式化介质接入、核心状态投影和按本次影响验收。R2 应明确旧 USB 目录和事务记录的只读兼容方式，后续每个实现批次都配套模拟回归。

本阶段完成源码及历史证据的分类。实机、旧执行器、部署和旧 PR 均未操作。
