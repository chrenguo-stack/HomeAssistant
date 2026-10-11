# N3-W T1 最小宿主基线与全新产品 Bootstrap 决策（2026-10-11）

## 0. 决策状态

用户明确冻结新的 T1 正式部署基线：

```text
TARGET_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
DECISION_STATUS=FROZEN_CURRENT_AUTHORITY
T1_DEDICATED_GREENHOUSE_HOST=true
OS_REINSTALL=false
SYSTEM_DISK_ERASE=false
LIVE_BASELINE_ERASE_THIS_GATE=false
LIVE_PRODUCT_BOOTSTRAP_THIS_GATE=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

这里的宿主基线包含维持远程管理和运行 Docker 所必需的 Armbian 宿主能力：现有 Armbian OS/kernel/boot、systemd、SSH 管理通道、NetworkManager/eth0/DHCP/DNS/default route、时间同步，以及 Docker Engine + Compose。它不包含任何温室产品业务状态。

本决策覆盖此前“clean product 预检必须依赖已经存在的 system identity / secret bundle / Manager clean DB / DynSec / ingress guard / frozen Docker volumes”的 staging 前提。那些状态以后必须由正式产品 bootstrap 创建，而不是作为新 T1 安装的先决条件。

## 1. 最小宿主基线

正式产品安装开始前，T1 应满足：

```text
ARMBIAN_OS=PRESENT
SSH_MANAGEMENT=PRESENT
NETWORK_STACK=PRESENT
DOCKER_ENGINE=PRESENT
DOCKER_COMPOSE=PRESENT

GREENHOUSE_CONTAINERS=0
GREENHOUSE_IMAGES=0
GREENHOUSE_VOLUMES=0
GREENHOUSE_DOCKER_NETWORKS=0
GREENHOUSE_BUILD_CACHE=0
GREENHOUSE_PRODUCT_DIRECTORIES=ABSENT
GREENHOUSE_PRODUCT_SYSTEMD_UNITS=ABSENT
GREENHOUSE_PRODUCT_DISPATCHER=ABSENT
GREENHOUSE_PRODUCT_FIREWALL_CHAIN=ABSENT
GREENHOUSE_SYSTEM_IDENTITY=ABSENT
GREENHOUSE_SECRET_BUNDLE=ABSENT
GREENHOUSE_CA_TLS_STATE=ABSENT
GREENHOUSE_DYNSEC_STATE=ABSENT
GREENHOUSE_MANAGER_DATABASE=ABSENT
GREENHOUSE_HOMEASSISTANT_CONFIG=ABSENT
GREENHOUSE_PRODUCTION_LISTENERS=0
```

不要求删除 Armbian 自身包、日志、SSH host keys、NetworkManager 配置、Docker Engine 数据目录本身或非产品系统服务。

## 2. 正式 installer / bootstrap 必须拥有的职责

新的正式部署链必须从最小宿主基线出发，并由 repository-owned installer 自己完成：

1. 只读 host preflight：arm64、Docker/Compose、网络、时间、磁盘、目标端口、目标路径和产品资源均符合 clean-baseline 合同。
2. 创建新的稳定 T1 product/system identity；旧 identity 不作为迁移输入。
3. 在 T1 本地生成新的产品 secret、Broker 私有 CA、TLS key/cert、Manager/HA/Broker 独立凭据和 DynSec 初始状态；秘密不得进入 GitHub artifact。
4. 创建 Manager 的全新数据库与 N3-W replay/authorization/relay-key 状态，业务记录从 0 开始。
5. 创建唯一一套干净 Home Assistant 产品实例。
6. 创建 N3-W Docker networks、Compose/source、systemd units 和 Broker ingress guard；在 guard 就位以前不得开放生产 8883。
7. 从 exact offline payload 本地 load Manager/Home Assistant/Broker 三个 ARM64 镜像；apply 内禁止外部 registry pull。
8. 完成静态 deployment gate、TLS/ACL/loopback、Manager/HA/Broker readiness、空白业务状态和 stopped/activation 边界检查。
9. 仅在独立 live authorization 后进入生产 activation；板卡旧 NVS/首次配对仍是后续独立物理阶段。

## 3. 旧 staging executor 的处置

当前 Run #91 artifact 对“artifact 自身 exact binding”仍是有效证据，但它的 executor preflight 依赖预先存在的：

- 45-volume frozen set；
- system identity；
- 11-file secret bundle；
- Manager clean DB/provenance；
- DynSec；
- ingress guard。

因此它不再符合新的最小宿主基线，不允许直接作为正式部署输入。

```text
RUN91_EXACT_ARTIFACT_BINDING=PASS_AS_ARTIFACT_EVIDENCE
RUN91_DEPLOYMENT_ELIGIBILITY=SUPERSEDED_BY_MINIMAL_BASELINE_DECISION

AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03
AUTHORIZATION_STATE=NOT_GRANTED_SUPERSEDED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_NOT_APPLICABLE=true
```

不为旧 executor 降低 preflight 条件，也不通过预先人工生成产品状态来“满足”旧 preflight。下一版 source 必须把这些产品状态的创建正式收进 bootstrap。

## 4. 当前 T1 清理证据

2026-10-11 已执行已授权的旧 Docker image/build-cache 清理，脱敏结果：

```text
CONTAINER_COUNT_AFTER=0
IMAGE_COUNT_AFTER=0
BUILD_CACHE_AFTER=0
VOLUME_COUNT_AFTER=45
ROOT_AVAILABLE_BYTES_AFTER=11764797440
```

这证明此前容量压力主要来自开发期 Docker image/cache。当前根分区容量已经足够继续产品化设计；但 45 个 Docker volume 和其他预创建产品状态仍不符合新的目标基线，后续需要独立的 exact baseline-normalization manifest 与 live erase gate。

## 5. 不做的事情

本决策不授权：

- 删除 45 个 volume；
- 删除现有 system identity / secret / CA / DynSec / Manager DB；
- 删除产品 systemd/dispatcher/firewall 状态；
- 启动生产服务；
- 使用或 claim `..._03`；
- 板卡/NVS 操作；
- PR merge。

这些 live mutation 必须在新 source design 和 exact clean-baseline delete manifest 完成后，再以明确 gate 进入。

## 6. 下一门

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_DESIGN_20261011_01

GATE_SCOPE=HOST_AND_GITHUB_ONLY
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
```

该 gate 要把现有 staging executor 从“验证预创建产品状态”改造成“验证产品状态不存在，并由 installer 从零创建全部产品状态”的完整 source design，然后再进入实现与 CI。
