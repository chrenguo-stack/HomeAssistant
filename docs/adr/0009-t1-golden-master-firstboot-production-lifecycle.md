# ADR-0009：T1 黄金母盘、每机首次初始化与量产生命周期合同

- 状态：项目所有者已批准 / 架构合同冻结；PR #541 合并前仅在候选分支生效
- 日期：2026-10-12
- 决策：`N3W_T1_GOLDEN_MASTER_FIRSTBOOT_ARCHITECTURE_CONTRACT_AND_ADR_DESIGN_FREEZE`
- 上位依据：技术路线 V0.7、V0.5 H0/H1、ADR-0004、已批准 S1 开发计划
- 关联阶段：H0、H1、S1、T1 production image、factory firstboot
- 不授权：T1 访问/修改、R3 清理、生产服务启动、板卡访问、PR 合并、`_08` live apply

## 1. 背景

项目既有路线已经要求：

- H0 建立可恢复、可复制的 T1 主机镜像基线；
- H1 在具体主机上可重复初始化系统身份、Broker 与持久状态；
- 相同公共镜像部署到不同主机后必须产生不同系统身份；
- 销售主机不得共用 MQTT 账号、系统根密钥或系统 CA 私钥；
- `greenhouse-init` 只负责首次初始化，初始化后退出；
- S1 包含黄金镜像、首启初始化、OTA、备份恢复和老化。

ADR-0004 已冻结 H0/H1 首次初始化与可移植恢复合同：首次初始化生成
`SYSTEM_ID`、`MANAGER_ID`、SYSTEM_ROOT_KEY 和独立系统 CA；部分初始化必须失败关闭；
重复初始化只复核并返回原身份；备份恢复保留原系统身份，并对双主机身份冲突失败关闭。

2026-10-11/12 的 R8 fresh bootstrap 将“公共软件安装”和“设备实例初始化”组合成一次
单机 fresh install。这对单台干净 T1 安装是有效工具边界，但不能直接等同于量产黄金母盘。
若把 R8 完成后的实例磁盘原样克隆，会复制产品身份、私钥、MQTT/DynSec 凭据；同时当前
R8 也未拥有 clone 后 `/etc/machine-id`、SSH host keys 等 OS 唯一化生命周期。

因此本 ADR 不推翻 R8/F5 已关闭的安装工具源码问题，而是补齐其上层量产生命周期，并将
单机 fresh install、黄金母盘构建、每机首次初始化和系统恢复明确分离。

## 2. 核心决策

量产架构冻结为：

~~~text
GOLDEN_MASTER_BUILD
→ MASTER_VALIDATED
→ SEALED
→ DISK_IMAGE_CAPTURED
→ CLONED_DEVICE_FIRSTBOOT
→ DEVICE_READY
→ FACTORY_ACCEPTED
→ USER_ONBOARDING / ACTIVE
~~~

这不是一个单一的大状态机。它分为两类 authority：

1. **镜像发布记录**
   `BUILD → VALIDATED → SEALED → CAPTURED`
2. **每机持久初始化状态**
   `UNINITIALIZED → INITIALIZING → DEVICE_READY → FACTORY_ACCEPTED → ACTIVE`

`USER_ONBOARDING_PENDING` 是可观察条件，不额外建立一套会漂移的独立状态 authority：
设备已 `FACTORY_ACCEPTED` 且 Home Assistant 尚无 Owner 时即处于该条件。

## 3. 四类数据边界

### 3.1 A 层：公共黄金镜像

所有合格 T1 可以相同：

- Armbian / kernel / boot / systemd 的已验证公共基线；
- Docker Engine / Compose 与日志轮转等公共配置；
- exact Home Assistant / greenhouse-manager / Broker 镜像；
- `/opt/HomeAssistant` 公共程序、schema、模板和 image lock；
- 公共 Compose 模板；
- systemd unit 定义、Broker ingress guard 程序；
- firstboot、seal、factory-audit、backup/restore、upgrade/rollback 程序；
- 不含设备实例值和秘密的公共 CA 策略、配置模板和版本清单。

### 3.2 B 层：每机 OS / host identity

不得从母盘复制最终值：

- `/etc/machine-id` 最终值；
- SSH host private keys；
- 产品 host instance identity；
- 被产品当作唯一身份使用的 hostname/client-id/network identity；
- 持久 DHCP lease 或构建机专属网络残留；
- 其他经目标 Armbian 版本证明会导致跨克隆冲突的主机唯一状态。

### 3.3 C 层：每机产品实例身份与秘密

不得进入公共母盘：

- `SYSTEM_ID`；
- `MANAGER_ID`；
- SYSTEM_ROOT_KEY；
- 系统 CA 私钥；
- Broker transport CA 私钥；
- Broker TLS server private key；
- Manager / Home Assistant / provisioning MQTT service credentials；
- Broker admin secret；
- 已实例化 DynSec 数据库；
- 设备实例专属 TLS/identity manifest。

系统 CA 与 Broker transport CA 继续保持现有分离合同，本 ADR 不合并两套 CA。

### 3.4 D 层：用户和运行数据

不得从母盘或工厂测试实例复制：

- Home Assistant Owner、token、session、用户家庭资料；
- 测试 `.storage` 身份和 registry 数据；
- Manager registration / pairing / node / relay-key / replay 业务状态；
- 测试节点、retained MQTT 业务状态；
- Home Assistant 历史数据库；
- 用户日志、告警、统计和正式备份。

## 4. GOLDEN_MASTER_BUILD 合同

母盘构建输入是一台合格的干净 T1 / 等价构建目标：

~~~text
ARMBIAN + NETWORK + DOCKER/COMPOSE
~~~

母盘构建阶段负责：

1. 验证 architecture、Docker/Compose、时间和存储；
2. 解析真实 Docker/containerd image-store authority；
3. 拒绝无法确定或带非空 containerd imports 的存储权威；
4. 导入并验证 exact HA/Manager/Broker ARM64 镜像；
5. 安装 `/opt/HomeAssistant` 公共源码/模板；
6. 安装公共 Compose、systemd unit、guard、firstboot/seal/audit 工具；
7. 验证公共软件完整性、权限和镜像绑定；
8. 保持产品实例身份与秘密未生成；
9. 不把用户数据或测试业务状态写入母盘。

R8 的 exact artifact binding、offline image load、F5 image-store authority、portable
RootFS/config binding 等能力迁移到此阶段。

正常量产克隆设备**不再重复执行三镜像 `docker load`**。单机 fresh install 可以作为研发、
灾难重建或受控维修工具保留，但不是批量出厂的必经路径。

## 5. MASTER_VALIDATED 与 Seal 合同

### 5.1 Validation

母盘公共基线验证允许验证：

- Docker 与三个 exact image 存在且绑定正确；
- 公共程序、Compose 模板、systemd 定义、guard、firstboot 程序存在；
- firstboot 的静态依赖、权限和失败关闭合同可执行；
- 业务生产服务默认未开放到外网；
- 不要求留下正式产品实例身份。

完整实例化验证优先在“由候选母盘克隆出的验证机”上进行，而不是先把母盘本体变成正式实例再删除秘密。

### 5.2 Seal 必须不存在

封版时至少必须证明不存在：

- `SYSTEM_ID` / `MANAGER_ID` 的已初始化实例；
- SYSTEM_ROOT_KEY；
- 两套 CA 私钥；
- Broker TLS private key；
- MQTT service passwords / Broker admin secret；
- 已实例化 DynSec database；
- Manager 实例业务 DB；
- pairing/node/relay-key/replay 业务状态；
- HA Owner/token/测试 `.storage`；
- retained 测试业务状态；
- 构建/测试秘密、临时 staging 和远程接入后门；
- 构建机最终 `machine-id`；
- 构建机 SSH host private keys；
- 任何已证明会造成 clone identity collision 的 OS/runtime 唯一状态。

### 5.3 Seal 必须保留

- exact OS / Docker / image / program provenance；
- image lock；
- 公共配置模板；
- firstboot / seal / audit / recovery 工具；
- secret-free build manifest；
- 镜像版本、source SHA、artifact provenance；
- 必要的无秘密工厂诊断定义。

### 5.4 服务状态

Seal 结束时：

- HA / Manager / Broker 不得处于对外生产激活状态；
- ingress guard 的程序和 unit 可以预装；
- 任何未来 Broker 网络开放必须满足“guard 先就位、保护证据成立，再允许监听”的运行合同；
- Docker/containerd 保留已验证镜像，但镜像采集必须在一致、静止状态进行。

Seal 工具必须采用**正面保留清单 + 禁止项审计**，不能把“删除若干已知目录”等价于“无秘密”。

## 6. DISK_IMAGE_CAPTURED 合同

镜像采集属于生产/不可逆 D 类操作：

- 使用明确授权；
- 绑定 exact sealed-master source SHA / build manifest；
- 采集前确认文件系统一致性和静止状态；
- 生成磁盘镜像 SHA-256、大小、分区表/文件系统摘要、目标 T1 兼容范围；
- 记录母盘硬件与目标介质容量要求；
- 不把 host-specific factory evidence 当作镜像内公共数据；
- 未通过 Seal audit 的磁盘禁止采集为 release image。

如果构建介质比目标 eMMC 大，必须有独立的“可收缩/可复制到目标介质”合同；不得因为构建盘空间更大就假定 raw image 可直接写入较小目标。

## 7. 每机 firstboot 合同

### 7.1 firstboot 不是 R8 `_08` 重放

当前 R8 `_08` 是一次性人工 live-apply authorization。产品自动 firstboot 不得复用、清除或重放
`_08` / `_03` 等历史授权。

firstboot 的执行 authority 是：

~~~text
sealed image state
+ local persistent firstboot transaction
+ exact image/version contract
~~~

其授权和重入语义必须由产品代码独立冻结，不以人工一次性授权 ledger 作为每次开机正确性依据。

### 7.2 顺序

每机首次初始化按以下最小顺序：

~~~text
SEALED_CLONE
→ acquire single initializer lock
→ establish OS/host identity
→ create product identity
→ create system/Broker cryptographic materials
→ create service credentials and DynSec
→ create empty Manager/N3W state
→ render instance configuration
→ commit instance state marker-last
→ verify stopped/readiness boundary
→ DEVICE_READY
~~~

必须先生成 OS/host 唯一身份，再允许 SSH 或任何依赖该身份的对外服务成为稳定产品入口。

### 7.3 断电恢复

firstboot 必须有 durable transaction record，并满足：

1. 同一时间只有一个 initializer；
2. transaction 绑定 image release/version、firstboot schema 和本机 host identity；
3. 完整生成并已校验的身份组件重启后复用，不重新生成；
4. 未提交的临时组件只允许在 transaction-owned staging 中恢复/重建；
5. 正式目录出现未知、混合或被篡改状态时 fail-closed；
6. 多目录提交过程中业务服务保持禁止；
7. 关键文件与父目录持久化后，最后写完成 marker；
8. 完成后普通 reboot/upgrade 不得重新进入身份创建；
9. backup restore 与 factory-reset 不能假冒 fresh clone firstboot。

## 8. 每机生成时机

### 8.1 工厂首次初始化生成

- `machine-id`；
- SSH host keys；
- stable host instance identity；
- `SYSTEM_ID`；
- `MANAGER_ID`；
- SYSTEM_ROOT_KEY；
- system CA keypair；
- Broker transport CA keypair；
- Broker TLS key/cert；
- Manager / HA / provisioning service credentials；
- Broker admin secret；
- initial DynSec；
- 空 Manager/N3W state；
- instance-specific configuration。

### 8.2 用户 onboarding 生成/拥有

- Home Assistant Owner；
- 用户密码与访问令牌；
- 用户家庭/地区/通知等资料；
- 后续由用户批准产生的节点 assignment 与节点 credential。

工厂不得为正式交付设备建立后再“删除”的测试 Owner。

## 9. FACTORY_ACCEPTANCE 合同

工厂验收在 firstboot 完成后执行，至少证明：

- OS/host identity 完整且重启稳定；
- 产品身份与密钥 manifest 完整；
- Docker exact images 保持绑定；
- Manager/Broker/HA 配置可解析；
- guard-before-Broker-open 顺序成立；
- Broker TLS / ACL / DynSec 最小权限通过；
- Manager DB 和 N3W state 为空业务状态；
- HA 无 Owner、无测试用户和测试设备历史；
- 服务可在受控工厂验收窗口启动并健康；
- 工厂验收完成后不存在测试业务残留；
- `FACTORY_ACCEPTED` marker 与 image release、host identity、product identity 摘要绑定。

正常用户启动只有在 `DEVICE_READY + FACTORY_ACCEPTED` 或明确的售后/研发例外合同下才允许进入正式产品服务激活。

## 10. Cross-clone 唯一性合同

同一 release disk image 至少写入 A/B 两台合格 T1 后，自动验收必须证明：

- A.machine-id != B.machine-id，且各自 reboot 后稳定；
- SSH host public fingerprints 不同；
- host instance identity 不同；
- SYSTEM_ID 不同；
- MANAGER_ID 不同；
- system CA / Broker CA / Broker TLS public identity 不同；
- SYSTEM_ROOT_KEY、服务密码、Broker admin secret 通过受保护指纹/挑战证明不同；
- A 的 service credential 不能认证到 B，反向亦然；
- 两机 Manager/HA/DynSec/业务数据库初始为空；
- 同时接入同一 LAN 不发生 DHCP identity、hostname、Manager discovery 或 system ownership collision；
- firstboot 重跑不会重新生成已承诺稳定的身份。

公共 CI/文档不得输出私钥、password 或可离线恢复秘密；必要时仅保存摘要或挑战式 PASS 结果。

## 11. 新克隆、备份恢复、恢复出厂和升级必须分开

### 11.1 Fresh clone

生成全新 OS/host identity 与全新产品 SYSTEM_ID/CA/credentials。

### 11.2 Backup restore

遵循 ADR-0004：

- 保留备份中的 SYSTEM_ID、MANAGER_ID、CA、credential lifecycle、registration 和业务状态；
- 目标 T1 的 OS/host identity 属于目标主机，不因恢复而复制旧主机 OS identity；
- 原系统仍在线时，不得未经 identity-claim/takeover 合同让恢复副本同时激活。

### 11.3 Factory reset

不能用“删除 firstboot marker 然后重跑”定义。

必须独立冻结：

- 哪些硬件/工厂 identity 保留；
- SYSTEM_ID/CA/credential 是否轮换；
- 用户/业务数据如何删除；
- 节点端旧归属如何显式退役/失效；
- reset 后进入何种 onboarding 状态。

### 11.4 Upgrade/rollback

- 不重新生成 SYSTEM_ID、MANAGER_ID 或长期 identity；
- upgrade 只迁移程序/配置 schema/DB；
- rollback 必须与备份和版本兼容性成对验证。

## 12. 服务开放顺序

长期生产服务不得仅因为“镜像中 unit 已 enabled”就自动绕过初始化门。

最小顺序：

~~~text
OS/host identity ready
→ product identity/secrets committed
→ guard installed and verified
→ instance config verified
→ factory acceptance contract satisfied
→ production activation permitted
~~~

Broker 的外部 TLS listener 必须晚于 ingress guard 的有效保护。

Home Assistant 可以在正式用户现场处于“无 Owner、等待官方 onboarding”的运行状态；
该状态不得被误判为工厂已经拥有用户所有权。

## 13. 容量合同拆分

原 R8：

~~~text
MIN_POST_PEAK_FREE_BYTES = 5 GiB
~~~

继续作为 R8 安装工具的历史保守策略，不自动升级为产品物理最低需求。

正式冻结三个不同容量问题：

1. `MASTER_BUILD_WORKSPACE_REQUIREMENT`
   - 回答 build/import/extract/verify 的临时空间需求；
   - 只约束母盘构建和单机 fresh install。
2. `PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT`
   - 回答 HA DB、Manager state、Broker persistence、日志和健康运行所需空间；
   - 必须由真实运行增长和维护需求推导。
3. `UPGRADE_ROLLBACK_WORKSPACE_REQUIREMENT`
   - 回答新旧镜像并存、备份、迁移和回滚需要的额外空间；
   - 由升级策略独立定义。

流式 `docker load` 只属于第一项。如果正常母盘构建环境已有足够空间，暂不为量产克隆路径增加此复杂度；
确有构建空间阻断时再单独优化。

## 14. 当前 R8 能力重新归属

| 当前能力 | 决策 |
| --- | --- |
| Docker/containerd/F5 storage authority | KEEP / master-build preflight |
| exact artifact / image binding | KEEP；并新增 final disk-image binding |
| HA/Manager/Broker `docker load` | MOVE_TO_MASTER_BUILD |
| `/opt/HomeAssistant` 公共源码 | MOVE_TO_MASTER_BUILD |
| Compose | MODIFY：公共模板与 instance values 分离 |
| systemd / ingress guard definitions | MOVE_TO_MASTER_BUILD；activation gate 分离 |
| `create_identity` | MOVE_TO_FIRSTBOOT |
| `create_state` | MOVE_TO_FIRSTBOOT |
| `create_broker` | MOVE_TO_FIRSTBOOT |
| `initialize_dynsec` | MOVE_TO_FIRSTBOOT |
| MQTT service credentials | MOVE_TO_FIRSTBOOT |
| system/Broker CA 与 TLS key | MOVE_TO_FIRSTBOOT |
| stopped_postcheck 验证器 | KEEP/MODIFY；拆为 master 与 instance audit |
| 每台量产机传完整 offline payload 并重新 load | RETIRE from normal clone production path |
| R8 `_08` | KEEP only for current bounded live-apply lineage；NOT a firstboot mechanism |

## 15. 对当前 R8/F5 结论的处理

保留：

~~~text
F5=CLOSED_SOURCE
PRODUCT_SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
~~~

其含义仅为：

- current single-host fresh-bootstrap source 的 F5 storage authority/imports 问题已关闭；
- 不代表黄金母盘、Seal、clone firstboot、断电恢复或工厂量产验收已完成。

不重开 KF-111/F5，不把架构分层修复伪装成 F5 regression。

## 16. R3 与 authorization

- R3 `/var/tmp/n3w-fresh-bootstrap.EOmzn8` 是历史取证，不是母盘运行依赖；
- 本 ADR 不授权删除 R3；
- `_03` 已 consumed / no-replay；
- `_04/_05/_06/_07` superseded-ungranted；
- `_08` NOT_GRANTED；
- 删除 marker、ledger 或 staging 不能恢复任何已消费 authorization。

R3 cleanup 以后独立执行。

## 17. 关闭本轮架构 blocker

Astra 独立复核提出的架构 blocker 在本设计层按以下合同关闭：

- AB1 单机安装 / master build / firstboot 职责：本 ADR 第 4、7、14 节关闭；
- AB2 Seal 与无实例秘密合同：第 5 节关闭；
- AB3 firstboot 断电恢复与现有一次性授权混用：第 7 节关闭；
- AB4 工厂验收 / 用户所有权 / 服务开放：第 8、9、12 节关闭；
- AB5 clone / restore / upgrade 语义：第 10、11 节关闭。

状态是：

~~~text
ARCHITECTURE_BLOCKERS=0
IMPLEMENTATION_AND_LIVE_ACCEPTANCE_PENDING=true
~~~

关闭架构 blocker 不代表实现、CI 或真实克隆验收已经通过。

## 18. 后续阶段门

### G2：source decomposition / repair

实现公共 master-build 与 per-device firstboot 两阶段编排，最大化复用现有构造器和验证器。

### G3：golden-master candidate

在独立授权下构建、Seal、离线审计并采集 exact disk image。

### G4：clone A/B acceptance

同一 disk image 写入至少两台 T1，做 identity uniqueness、同时联网和断电恢复。

### G5：factory / onboarding

验证工厂验收、无 Owner 交付、官方 onboarding 和自动项目初始化。

### G6：restore / upgrade

验证 ADR-0004 restore、identity conflict、upgrade/rollback 和运行空间门。

每个 Gate 都有独立 STOP，不把 source PASS 代替 live acceptance。

## 19. 本 ADR 明确不决定的事项

后续实现/实机证据决定：

- 目标 Armbian 上 machine-id 应采用“缺失文件”还是“空文件”等具体 seal 操作；
- SSH unit 与 firstboot 的 exact systemd ordering；
- per-device hostname 的最终格式；
- factory acceptance 是否需要有线离线 jig / isolated LAN；
- `PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT` 的数值；
- `UPGRADE_ROLLBACK_WORKSPACE_REQUIREMENT` 的数值；
- 是否最终实现 streaming image import；
- factory-reset 的完整产品语义。

这些不能通过本 ADR 中的示意值提前宣称完成。
