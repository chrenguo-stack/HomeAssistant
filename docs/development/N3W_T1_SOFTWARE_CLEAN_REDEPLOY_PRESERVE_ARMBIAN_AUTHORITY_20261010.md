# N3-W T1 温室软件环境全新部署：保留 Armbian（2026-10-10）

## 0. 用户明确的新授权与覆盖关系

用户已经确认不重装 Armbian，并同意继续。本文件是 **PR #541 在同一分支内最新的当前执行权威**，覆盖该 PR 早先整机擦盘文档中的 OS_REINSTALL=true / WHOLE_HOST_ERASE 方向。早先文档保留作历史决策记录，不应被引用为当前有效执行要求。

```text
CURRENT_ROUTE=SOFTWARE_STACK_CLEAN_REINSTALL_ON_EXISTING_ARMBIAN
OLD_ROUTE=WHOLE_T1_OS_WIPE_SUPERSEDED
OLD_R4_B1I1_ROLLBACK_ENGINEERING=STOPPED
OS_REINSTALL=false
SYSTEM_DISK_ERASE=false
PRESERVE=ARMBIAN_OS_KERNEL_BOOT_PARTITIONS_ETH0_NETWORK_SSH_DOCKER_ENGINE
FRESH_REDEPLOY=GREENHOUSE_MANAGER_BROKER_DYNSEC_CA_TLS_RELATED_COMPOSE_AND_DATA
HOME_ASSISTANT_REDEPLOY=IN_SCOPE_PENDING_INSTANCE_OWNERSHIP_REVIEW
NODE_FIRST_PAIR=AFTER_NEW_T1_HEALTH
CURRENT_GATE=SOFTWARE_CLEAN_T1_RUNTIME_OWNERSHIP_AND_DATA_DIRECTORY_INVENTORY_READONLY
T1_MUTATION_THIS_GATE=false
OLD_STATE_DELETE_THIS_GATE=false
PRODUCTION_CLEAN_EXECUTION=NOT_YET_AUTHORIZED_UNTIL_EXACT_TARGET_LIST_REVIEWED
PR_540=CLOSED_SUPERSEDED
PR_541=OPEN_DRAFT
```

本轮根据真实 T1 F0 报告确认：`Armbian OS 26.05.0 resolute`，arm64，内核 `6.18.26-ophub`，系统启动 `/dev/mmcblk2p1`、根分区 `/dev/mmcblk2p2`，Docker `29.7.1`，SSH/NetworkManager/Docker 运行。当前无证据证明宿主系统本身必须重装。

## 1. 已知活跃服务与风险

2026-10-10 07:54+08:00 用户的只读 T1 `docker ps -a` 已观察到：
- `greenhouse-manager`：Up
- `greenhouse-manager-p4-shadow`：Created
- `n3wfc4-broker-1`：Up
- `recipes-broker-1`：Exited
- `fc4-homeassistant`：Up
- `homeassistant`：Up

**有两套不同名字的 Home Assistant 容器正在运行。** 现阶段无法推定哪套为正式家庭业务、哪套为温室专用；未经精确映射，不允许按名字批量清理。旧 Broker 也有一个名为 recipes 的停止容器，不能假定其为 N3-W 专用。即便用户已接受温室系统旧数据清理，也不能将非温室容器、宿主软件和数据自动归入该授权范围。

## 2. 保留与重建边界

| 资产 | 处置 |
|---|---|
| Armbian、系统盘、/boot、SSH、eth0 与网络管理、Docker 引擎 | **保留，不重装、不清空、不主动重启** |
| 旧 Manager 及其三个业务 RW 数据目录 | **计划替换为新空白 Manager**，待核实挂载来源和服务归属后执行 |
| 旧 Broker/Mosquitto DynSec/会话/旧 CA 和 N3-W 专用 TLS 凭据 | **计划清理并从零生成**，待核实其与两套 HA、recipes 及其他业务的关系 |
| Home Assistant | 核查两套容器 ownership 后，只处理明确属于温室全新部署范围的实例；其他 HA 默认保留 |
| Docker 网络与匿名/命名卷 | 只删除完全证明由旧温室栈独占的资源；不能按 Compose 项目名推断全部归属，不使用 `--remove-orphans` 或 `docker system prune` |
| 防火墙规则、Broker 激活/证书生命周期 systemd units | 核查现有 ownership 后在新栈内最小范围重新配置；不 flush 全局 iptables/DOCKER-USER |
| ESP32-C6 旧 NVS、Setup Secret | 不随 T1 清理而自动抹除；主机部署 PASS 后逐板单独处理旧配对 |

**安全边界不是旧方案的复杂回退**：这次清洁部署不再保留旧 Manager 作为运行时回退目标。但清理对象必须逐项辨认、确认可重建，以及避免清理无关业务，这是全新安装的必要前置，而不是重新开发回退系统。

## 3. 只读清单需要回答的问题

1. 每个容器的 Docker Compose project/service/config path、镜像、运行状态、host/network mode、挂载源与目标（只看路径与权限，不读取秘密文件内容）。
2. `fc4-homeassistant` 与 `homeassistant` 是否由相同/不同项目管理、是否共享宿主数据目录、是否依赖当前 N3-W Broker。
3. `recipes-broker-1` 是否属于其他应用；绝不能把它跟着温室 Broker 批量删除。
4. 哪些 systemd units 专属 Broker 入口保护、激活、证书生命周期、Manager，哪些是宿主基础服务。
5. 新栈依然需要的宿主端口 8883、Manager UDP 47111 / TCP 47112、Broker loopback TLS、双网络、Manager 六挂载；根据 `infra/n3w-t1/README.md` 与 ADR-0008 重装。
6. 目标数据目录属于 bind mount 还是 Docker volume、是否与其他容器共享；所有匿名 Docker volumes 默认不是“可以全部删除”。

## 4. 下一执行阶段：先只读后限范围清理

```text
S0=EXACT_LIVE_OWNERSHIP_INVENTORY_READONLY
S1=CLASSIFY_GREENHOUSE_ONLY_VS_SHARED_VS_UNRELATED
S2=DRY_RUN_CLEAN_TARGET_MANIFEST_WITH_EXACT_PATHS_AND_CONTAINER_IDS
S3=ONE_EXPLICIT_SCOPE_CONFIRMATION_IF_ANY_IRREVERSIBLE_DELETION
S4=STOP_AND_REMOVE_EXACT_OWNED_CONTAINERS_AND_DATA_ONLY
S5=FRESH_CA_DYNSEC_BROKER_WITH_SECURITY_GUARD_AND_DOUBLE_NETWORK
S6=FRESH_MANAGER_3_RW_0_0_0_WITH_3_NEW_RO_SECRETS
S7=HA_INSTANCE_RESOLUTION_AND_FRESH_GREENHOUSE_INSTANCE
S8=SERVICES_PERSISTENCE_AND_BOARD_FIRST_PAIR_SEPARATE_ACCEPTANCE
```

当前只启动 S0，S1 后的任何实际删除均没有执行。用户希望减少授权频率：一旦清单明确，以一次范围清单确认代替每个容器/目录分别询问。后续可以在既定精确范围内连续完成重新安装与验收。

```text
S0_RESULT=PENDING_REAL_T1_READONLY_OUTPUT
NEXT_INPUT=N3W_T1_SOFTWARE_OWNERSHIP_*.txt
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_READONLY_EVIDENCE_AND_CLEAN_TARGET_DRY_RUN
PRODUCTION_STOP=no deletion before exact owned target set
```


## 5. 2026-10-10 新增产品决策：正式环境仅一套 Home Assistant

用户确认：两套 Home Assistant 是历史原因产生的重复部署，最终生产 T1 **只应存在一套 Home Assistant**。这改变最终清洁部署的目标，但**不构成立即删除任何一套的授权**。

当前 S0 R2 已证明：

- `fc4-homeassistant` 与 `homeassistant` 各自属于不同 Compose project，`/config` 使用不同宿主数据目录；
- `homeassistant` 使用 host network，`fc4-homeassistant` 使用 N3W private network；
- 现有元数据尚不能证明哪套有必须保留的用户配置、外部使用者或 MQTT 依赖；
- `recipes-broker-1` 与运行中的温室 Broker 共享全部六个挂载，不能凭项目名认定可独立清除。

冻结要求：

```text
FINAL_PRODUCTION_HOME_ASSISTANT_INSTANCE_COUNT=1
S1=READONLY_INSTANCE_OWNERSHIP_AND_DEPENDENCY_CHECK
S2=EXACT_SINGLE_HA_KEEP_OR_FRESH_DECISION_AND_CLEAN_MANIFEST
OLD_HA_DATA_DELETE_AUTHORIZED=false
LIVE_RUNTIME_MUTATION=false
R4_B1I1_ROLLBACK_DEVELOPMENT=false
```

S1 只进行现场归属/依赖只读检查，执行命令直接在对话里提供；GitHub 仅归档脱敏决策、取证结果、源码和进展，不新增执行指令文档。


## 6. 2026-10-10 用户确认专用 T1 和旧业务全部重置

用户明确确认：**T1 专用于温室监测系统，并允许永久清除两套 Home Assistant、两个 Broker、旧 Manager 的全部业务数据和凭据**。这在授权的业务范围内覆盖先前「可能保留独立 HA / recipes Broker」的默认保守推断。最终系统必须为 1 套 HA + 1 套 Broker + 1 套 Manager。

冻结执行边界：

- `S2=PREDELETE_EXACT_DRY_RUN`：以新鲜 Docker 完整 ID、源挂载、Systemd/Compose 路径、主机基础服务状态核对清理对象；预检只读，得到可操作的 exact manifest 后 STOP；不再做「旧 HA 哪套更值得保留」的业务取舍分析。
- `S4=SCOPED_OLD_GREENHOUSE_REMOVAL`：只允许移除清单中已经证实的六个旧容器及其业务专有挂载数据、凭据和专属部署服务；共用旧 Broker 的数据按同一业务资源处理一次。该阶段虽有用户的业务数据清理许可，仍需先通过具体清理执行门禁，严禁超范围删除。
- 所有现存 Docker volumes 中，除已关联目标容器的卷外，未独立证明归属的卷暂不删除；`docker system prune`、`compose down -v`、`--remove-orphans` 和按名字/前缀扫删被禁止。
- `Armbian`、系统盘与 /boot、内核、eth0、SSH、NetworkManager、Docker Engine、系统级防火墙不属于清理范围；Broker TCP/8883 的 fail-closed 安全保护不得在旧服务尚对外发布时被提前撤销。
- 清理流程后必须从全新 CA/TLS/DynSec/Manager/HA 业务数据开始；板卡旧 NVS 与首次配对另门处理，不在主机清理阶段触碰。
- 后续所有 Mac Terminal 命令只在用户对话中提供；仓库只存脱敏进度、决策和验收证据，不新增执行指令文件。

```text
T1_DEDICATED_GREENHOUSE_HOST=USER_CONFIRMED
PERMANENT_ERASURE_OF_OLD_HA_BROKER_MANAGER_BUSINESS_STATE=USER_APPROVED
OLD_HA_DATA_DELETE_AUTHORIZED_WITHIN_VERIFIED_MANIFEST=true
FINAL_PRODUCTION_HA_COUNT=1
FINAL_PRODUCTION_BROKER_COUNT=1
FINAL_PRODUCTION_MANAGER_COUNT=1
S2_PREDELETE_LIVE_MUTATION=false
EXACT_S4_DELETION_GATE=NOT_YET_EXECUTED
OS_REINSTALL=false
SYSTEM_DISK_ERASE=false
R4_B1I1_ROLLBACK_DEVELOPMENT=false
BOARD_ACCESS=false
```
