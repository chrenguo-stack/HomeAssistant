# ADR-0010：T1 逐台 fresh Armbian 与自动产品部署

- 状态：项目所有者已批准 / 当前生产路线
- 日期：2026-10-14
- 决策：停止 Golden Master 整盘克隆，改为逐台安装官方 Armbian 并自动部署产品
- 取代：ADR-0009 的 Golden Master / Final Seal / disk capture / clone production route
- 保留：历史源码、测试、证据和安全守卫，不删除、不重写历史结论
- 本 ADR 不授权：T1 访问或修改、服务启动、凭据操作、板卡访问、PR 合并

## 1. 背景

Golden Master 整盘克隆的原始目标是减少每台 T1 的部署操作。但是，为了证明一块已经
启动过的 Armbian 磁盘可以安全清除母机身份、封存、复制并在 clone boot 后生成唯一稳定
身份，项目引入了 R2C probe/executor、Final Seal、disk capture、clone-write verification、
clone boot uniqueness 和多机 factory acceptance 等高成本 gate。

当前直接证据表明：

- R2C 的严格只读取证、安全边界和可复现执行包已经消耗大量开发与 CI 成本；
- 最新 target capture 仍只有 E8 complete，E1 需要修复后重观察，其余多项仍为 UNKNOWN；
- 即使继续投入，也不能在没有 controlled clone boot 的情况下证明最终效果；
- 对当前设备规模，克隆节省的单机人工时间不足以抵消开发和长期维护成本；
- 每次升级 Armbian 都可能重新打开 target-specific identity evidence 和 clone acceptance。

另一方面，官方 Armbian 镜像本来就为每台设备的独立首次启动设计。逐台安装官方镜像，
让每台 T1 正常完成自己的 OS first boot，再自动部署相同产品软件，可以避免把母机
machine-id、SSH host keys 和网络身份复制给其他设备。

## 2. 架构决策

新的正式生产路线冻结为：

```text
OFFICIAL_ARMBIAN_IMAGE_SELECTED
→ IMAGE_HASH_VERIFIED
→ PER_DEVICE_MEDIA_FLASHED
→ DEVICE_FIRST_BOOT_COMPLETED
→ HOST_READINESS_VERIFIED
→ AUTOMATED_PRODUCT_DEPLOYMENT
→ EXPLICIT_PRODUCT_PROVISIONING
→ PRODUCT_SERVICES_ACTIVATED
→ DEVICE_ACCEPTANCE_PASSED
→ USER_ONBOARDING / ACTIVE
```

核心原则：

```text
RAW_DISK_CLONE_PRODUCTION_ROUTE=false
PER_DEVICE_OFFICIAL_ARMBIAN_INSTALL=true
ARMBIAN_FIRST_BOOT_PER_DEVICE=true
PRODUCT_DEPLOYMENT_AUTOMATED=true
PRODUCT_PROVISIONING_EXPLICIT=true
SOURCE_CONTROLLED_REPAIR_REQUIRED=true
ON_TARGET_UNTRACKED_PATCH=false
```

“逐台安装”只指 OS 镜像写入和必要的首次启动操作。Home Assistant、Manager、Broker、
产品配置、身份、秘密、服务定义和验收仍由 repository-owned 自动化流程完成，不退回到
逐项人工配置。

## 3. 正式退役的路线与 gate

以下 gate 统一标记：

```text
GOLDEN_MASTER_BUILD_FOR_CLONING=RETIRED_BY_PRODUCT_DECISION
MASTER_VALIDATED_FOR_CLONING=RETIRED_BY_PRODUCT_DECISION
R2C_TARGET_ARMBIAN_SEAL_ADAPTER=RETIRED_BY_PRODUCT_DECISION
R2C_TARGET_ARMBIAN_READONLY_EVIDENCE=RETIRED_BY_PRODUCT_DECISION
R2C_PROBE_EXECUTOR=RETIRED_BY_PRODUCT_DECISION
FINAL_SEAL=RETIRED_BY_PRODUCT_DECISION
DISK_IMAGE_CAPTURE=RETIRED_BY_PRODUCT_DECISION
CLONE_WRITE_VERIFICATION=RETIRED_BY_PRODUCT_DECISION
CLONE_BOOT_UNIQUENESS=RETIRED_BY_PRODUCT_DECISION
MULTI_CLONE_FACTORY_ACCEPTANCE=RETIRED_BY_PRODUCT_DECISION
```

退役含义：

- 不再作为当前产品发布阻断项；
- 不再申请新的 R2C target authorization；
- 不再继续实现 writable OS-identity neutralization adapter；
- 不再执行 Final Seal、raw disk capture 或 controlled clone boot；
- 除非项目所有者以后作出新的产品决策，否则不得自动重新进入。

以下成果保留为历史和可复用参考：

```text
R2A_R2B_SOURCE=RETAINED_REFERENCE
R2C_PROBE_EXECUTOR_SOURCE_DISPOSITION=ARCHIVED_DIAGNOSTIC_REFERENCE
R2C_PRIVATE_EVIDENCE=RETAINED_PRIVATE_BY_EXISTING_POLICY
R2C_PUBLIC_CLOSURES=RETAINED_GITHUB_HISTORY
EXPLICIT_PROVISIONING_SOURCE=RETAINED_FOR_PER_DEVICE_ROUTE
FRESH_BOOTSTRAP_SOURCE_AND_TESTS=RETAINED_FOR_REPAIR_AND_REUSE
```

历史 one-shot authorization 仍保持 consumed/no-replay；路线退役不会恢复任何授权。

## 4. OS 与产品身份边界

逐台 official Armbian 首次启动负责建立 OS/host 层身份。自动产品 provisioning 负责建立
产品层身份和秘密。两层仍然分离：

| 层级 | 由谁建立 | 验收重点 |
| --- | --- | --- |
| Armbian OS/host | 官方镜像的每机首次启动 | machine-id、SSH host key、网络和时间正常 |
| 产品公共软件 | 自动部署器 | exact HA/Manager/Broker 版本、配置和权限 |
| 产品实例身份 | 显式 provisioning | SYSTEM_ID、MANAGER_ID、CA、TLS、MQTT credentials、DynSec 唯一 |
| 用户数据 | onboarding 后运行产生 | 不从其他 T1 或测试实例复制 |

新路线不再要求证明“从已启动母盘清除身份后再生成”。它只要求每台 fresh install 在验收时
拥有非空、稳定且未与设备台账冲突的 OS 和产品身份。

## 5. 自动部署合同

自动部署必须从以下最小前提开始：

```text
ARMBIAN_OS=PRESENT
DEVICE_FIRST_BOOT_COMPLETED=true
SSH_MANAGEMENT=PRESENT
NETWORK_STACK=PRESENT
TIME_SYNCHRONIZED=true
DOCKER_ENGINE_AND_COMPOSE=PRESENT_OR_INSTALLABLE_BY_APPROVED_STEP
GREENHOUSE_PRODUCT_STATE=ABSENT_OR_EXACTLY_CLASSIFIED
```

部署器负责：

1. read-only host readiness；
2. exact source/release/image binding；
3. 以适合 T1 磁盘容量的方式逐个取得并验证镜像；
4. 安装公共程序、Compose、systemd unit 和 ingress guard；
5. 显式创建每机产品身份、秘密、空白 Manager/HA/Broker 状态；
6. 在 guard 和 credentials 就位后启动产品服务；
7. 验证 TLS、ACL、HA MQTT bootstrap、Manager/Broker/HA readiness 和空白业务状态；
8. 输出公开安全的验收结果和私有设备台账记录。

现有一次性完整离线 payload 同时占用压缩包、三个 image tar 和 Docker/containerd 数据，
在已观察 T1 上存在 3.44 GB admission 缺口。新路线不得把旧 R8 transport 当作已经可用。
下一 source gate 必须在以下方案中选择最小可行的一种并冻结：

```text
A=target pulls exact published image digests when registry availability is proven
B=Mac streams and loads one exact image at a time, releasing each staging copy immediately
```

不得默认继续“完整 payload 全量落盘并解压三个 tar”的高峰值模型。

## 6. 实机演练与现场修复决策

允许把新流程在一台 fresh Armbian T1 上完整跑一遍，但本 ADR 本身不授权该执行。

实机阶段必须按以下顺序进入：

```text
SOURCE_DESIGN_AND_CI_PASS
→ FRESH_T1_READONLY_PREFLIGHT
→ EXPLICIT_ONE_SHOT_LIVE_DEPLOYMENT_AUTHORIZATION
→ AUTOMATED_DEPLOYMENT_REHEARSAL
→ SERVICE_ACTIVATION_AND_ACCEPTANCE
```

现场遇到问题可以继续修复，但“现场修复”定义为：

```text
capture bounded evidence
→ stop at first substantive mismatch
→ repair repository source/tests
→ pass fresh CI and build a new exact artifact
→ perform fresh preflight
→ obtain a new authorization when prior authorization was consumed
→ rerun from a proven baseline
```

禁止把临时命令直接改出的 T1 状态冒充正式修复；禁止只在 Mac 临时目录或聊天中保存
关键代码；禁止重放 consumed authorization。必要的 read-only diagnosis 可以在当前授权边界
内执行，任何新增 mutation 都必须有明确权限。

## 7. 复用与迁移

优先复用：

- minimal-host baseline 和 read-only preflight；
- exact image/source/release binding；
- Manager/HA/Broker fresh state constructors；
- explicit provisioning 的 inspect/start/resume/verify authority split；
- single-initializer lock、durable transaction 和 marker-last commit；
- TLS、DynSec、service credential、ingress guard 和 HA MQTT bootstrap tests；
- rollback、no-replay、public/private evidence 和 public repository safety guards。

不再继续：

- Seal ledger 和 sealed-master release state；
- OS identity neutralization；
- raw disk image provenance；
- clone-write marker/readback contract；
- clone-specific firstboot 和跨 clone 唯一性 harness。

实施时应删除新路线中的死分支和不再需要的复杂接口，但历史文件和 git history 保留。

## 8. 后果与权衡

收益：

- 删除 R2C/Seal/clone 的主要开发和维护成本；
- OS identity uniqueness 回归官方 Armbian 每机首次启动边界；
- 故障范围缩小为单台 host readiness、产品部署和 provisioning；
- 现场问题可以通过同一台 T1 的可复现实机演练快速暴露；
- 每次修复进入 GitHub、CI 和新 artifact，不形成设备雪花状态。

代价：

- 每台设备需要人工写入并首次启动 Armbian；
- 单机部署时间高于整盘克隆；
- 需要可靠的操作清单和设备台账；
- 自动部署路径当前仍有 transport/capacity blocker，必须先修复并实机验收。

这是有意接受的权衡。当前产品规模优先选择可理解、可维护和可现场修复，而不是追求尚未
达到经济拐点的整盘克隆效率。

## 9. 当前下一门

```text
NEXT_ONE_GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F0_SOURCE_REBIND_AND_GAP_REVIEW_20261014_01
GATE_SCOPE=GITHUB_AND_LOCAL_SOURCE_ONLY
T1_ACCESS=false
LIVE_MUTATION=false
BOARD_ACCESS=false
AUTO_EXECUTE_NEXT_GATE=false
```

F0 只负责重新审查现有 fresh-bootstrap、explicit provisioning、image delivery、activation
和 acceptance 源码，冻结最小修复清单与镜像交付方案。实机执行必须在后续 gate 单独进入。
