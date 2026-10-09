# N3-W / T1 全新部署：替代 R4/B1I1 的正式方案（2026-10-10）

## 0. 路线变更决定

**新的主路线：T1 整机从零部署（FULL_FRESH_T1）。**
用户明确要求“不要再考虑部署失败的回退问题”并“现在把方案改为全新部署 T1”；结合此前“把所有旧环境、旧数据都清理掉”的意图，执行设计采用 **旧 T1 环境和数据不迁移、重新建立宿主系统和温室服务**，不再以旧 Manager、R5 冷备份、R2/R3 影子容器或旧 Broker 状态为新部署前提。

```text
DIRECTION=FULL_FRESH_T1_FROM_ZERO
OLD_PLAN=R4_B1I1_INLINE_ROLLBACK
OLD_PLAN_STATUS=STOPPED_SUPERSEDED_NO_FURTHER_SOURCE_WORK
NEW_GATE=N3W_T1_FULL_FRESH_INSTALL_PREPARATION_AND_INSTALLATION_BLUEPRINT
T1_SCOPE=WHOLE_HOST_OPERATING_ENVIRONMENT
OS_REINSTALL=PLANNED_PENDING_TARGET_IDENTIFICATION
OLD_MANAGER_STATE_MIGRATION=false
OLD_BROKER_DYNSEC_STATE_MIGRATION=false
OLD_HA_CONFIG_MIGRATION=false
OLD_TLS_CA_KEY_REUSE=false
OLD_R1_R2_R3_R4_R5_RUNTIME_RECOVERY_DEPENDENCY=false
ROLLBACK_EXECUTOR_DEVELOPMENT=false
REAL_DISK_WIPE_THIS_GATE=false
REAL_T1_MUTATION_THIS_GATE=false
LIVE_DESTRUCTIVE_EXECUTION_AUTHORIZED=false
BOARD_NVS_RESET_THIS_GATE=false
SETUP_SECRET_IMPORT_THIS_GATE=false
PR_MERGE=false
```

**注意两种不同含义：**
- “放弃旧 T1 运行环境”不等于删除 GitHub 仓库的源码、技术规范、开发日志或历史失败证据。GitHub 仍为研发权威归档；旧 PR 应标记 superseded，禁止复用旧生产 launcher。
- “全新”意味着旧主机上的 Home Assistant 也可能一起消失。已知 T1 上存在 `fc4-homeassistant`，且它与 Broker 在同一 Compose project `n3wfc4` 下由不同 Compose authority 管理。因此本方案将**重新安装并重新配置 HA**，不默认保留它的本地数据。旧 HA 的实体、仪表板、集成与历史记录是否能从别的云端来源重新导入，本轮没有证据，不能承诺恢复。
- 如更换 Broker CA、证书、账户与动态安全库，旧板可能无法用旧信任根/旧凭据连接，后续要按 ADR-0008 进行有界的节点端持久配对信息清理、首次配对与 Setup Secret PoP。不能只清空 T1 就宣称旧板已成为全新节点。

## 1. 权威资料及可复用部分

必须从已验证产品源码**重新部署**，不是复用原来的现场 Docker 层：
- `infra/n3w-t1/README.md`：项目 `n3wfc4`；Manager host-network + 无 ports；Broker 0.0.0.0:8883/tcp 唯一 IPv4 publication；`n3wfc4-private`、`n3wfc4-services` 双网络；Broker Manager loopback TLS；Broker 8883 fail-closed guard；systemd 持久化；Broker 证书生命周期。旧 T1 中 HA 不是 orphan；新安装要显式规划 HA 与 Broker 的独立 Compose ownership。
- `docs/adr/0008-n3w-pairing-recovery-simplification-v2.md`：首次配对必须有当前硬件身份、随机 pairing ID、Setup Secret 证明和最终 COMMIT；节点 MQTT 凭据、应用密钥及 SYSTEM_PEER_KEY 信任变更有独立状态机，不能任意混成一种 reset。
- `docs/development/N3W_KF098_T1_LIVE_CUTOVER_PROGRESS_ALIGNMENT_20260928.md`：曾成功运行 Manager exact image、服务健康检查与 Broker 网络验证，属于产品验收依据，**不再复用其保留旧容器/回退执行器**。
- 正在开发的 Manager/配对/节点固件源码、CI、产品技术协议、正确的 exact image+artifact 可继续复用。T1 上原有业务库、DynSec 库、CA 密钥、容器镜像与系统账户**不再作为迁移输入**。

以上是源码及历史文档所支持的部署要求；尚未确认 OS 发行版、T1 是否物理机或虚拟机、目标系统盘、启动方式、远程恢复方式、网卡实际名称、硬件架构与当前运行中的非温室应用。这些是实装前必查事实，不能猜。

## 2. 全新部署范围及舍弃范围

| 项目 | 新方案 | 结果 |
|---|---|---|
| T1 系统安装盘/OS/系统账户、旧 Docker 与网络配置 | 识别**唯一目标机器与正确磁盘**后按官方镜像重装 | 旧系统和本机数据不迁移 |
| Docker/Compose、systemd、NetworkManager、SSH | 从干净 OS 安装、按版本固定，并创建新的部署目录与专用账户 | 不沿用未知现场历史配置 |
| Broker/Mosquitto + DynSec、保留消息和旧 ACL | 全新安装，生成新账号与最小权限，旧 Broker DB 不导入 | 旧设备凭据可能失效 |
| Broker CA / server cert / Manager MQTT secret | 重新建立经过审批的密钥/证书与受保护秘密文件；GitHub 不存明文 | 新 trust anchor；需节点配对 |
| Manager | 构建并绑定经过 CI 的当前产品镜像，创建全新的三个 RW 数据目录和所需 RO 秘密 | `registrations`、凭据及 replay 初始 0，relay-keys 为空 |
| Home Assistant | 新建独立 Compose authority 的干净实例；重新连接 Broker/实体 | 不继承旧 HA 数据/配置 |
| T1 防火墙/8883 guard、证书生命周期、服务持久化 | 根据仓库现行部署合同重新创建并验证 | 不依赖旧 R5 容器快照 |
| ESP32-C6 Board A/B/C | 物理硬件与唯一硬件身份保留；待 T1 完整验收后按精确板卡步骤解除旧配对、建立新的信任与凭据 | 不在 T1 清盘过程中自动擦板/NVS |
| R1–R4 历史私有文件/R5 冷备份 | 可随目标盘消失；研发结论和非密钥证据应事先留在 GitHub | 新部署完全不依赖旧恢复事务 |
| 其他非 N3-W 服务、HA 用户配置 | 按**整台 T1 全新安装**处理，预期丢失，除非另立明确“不清除例外”清单 | 需要在销毁前列出影响清单 |

**本方案不再研发回退，也不默认备份恢复旧应用业务数据**。但是“确定擦的是哪台设备、哪块磁盘”“避免误删除网络上其他主机”“确认可以从安装介质重新获得访问权限”不是回退设计，而是执行正确性前提，不可省略。

## 3. 执行流程——串行、明确的验收阶段

### F0. 现场目标确认与一次性删除边界确认（只读）

取得来自**T1 本机**的完整只读证据：
1. 机器型号、序列号/稳定标识、物理/虚拟类别、CPU 架构、内存、目标存储设备路径/容量/序列、现有系统盘/启动分区、USB/虚拟控制台/BIOS 可用性。
2. 网络物理连接、T1 IP/MAC、默认路由、DNS/管理网与当前 SSH 的可达性；**重装后**通过本地控制台或带外管理重新进入的办法；不假设当前 DHCP 地址或 SSH key 继续有效。
3. 完整列出 T1 上正在运行的 Docker 容器、数据卷、systemd 用户服务、Home Assistant、其它不相关业务与连接的外部磁盘；列明**清空会导致的停机和数据丢失范围**。
4. 获取要部署的 OS 镜像类型、SHA256、安装介质和镜像启动方式；确认离线/在线依赖可获得；确认新系统管理登录/SSH 与可信网络接入路径。
5. 对非用户明确授权的另一台设备或数据盘，不执行任何更改。

完成 F0 后出具一页清单：`EXACT_T1_ID`、`TARGET_SYSTEM_DISK`、`ERASE_SCOPE`、`HA_DATA_WILL_BE_LOST`、`BROKER_KEYS_WILL_BE_LOST`、`NODE_REPAIR_REQUIRED`、`POSTINSTALL_ACCESS`。在能够准确指出目标设备和磁盘且用户知道不可逆后果前不执行磁盘擦除。**只请求一次明确的实装/销毁授权，之后在批准范围内连续执行，不反复逐步申请**。

### F1. 全新安装 OS / 宿主基础

通过已确认的安装渠道清除**唯一批准的目标 T1 系统盘**并重装匹配硬件的 Linux。优先使用可验证的发行版/长期支持版本与固定安装镜像 SHA。设置时区/NTP、硬盘权限、管理账户/SSH 公钥、网络路由/DNS、系统更新、自动启动/日志持久化、Docker/Compose 与受控防火墙。所有历史业务密钥不导入。

**STOP**：安装后无法从可信管理通道重新登录，或系统磁盘/网络/时间不符合预定合同，不能继续堆叠服务。

### F2. N3-W 基础网络和全新 Broker 信任

新建项目所需网络（`n3wfc4-private` + `n3wfc4-services`）、Broker TLS private CA / key、服务端证书、Broker DynSec 初始化用户及 Manager/HA 专用最小权限账号、受权限保护的秘密文件。严格按 `infra/n3w-t1/README.md` 完成 Broker 唯一 IPv4 8883 publication 及先 guard 后开放入口，loopback TLS 与双网络/重启策略验收。新 CA 不向 GitHub 提交明文。

**STOP**：broker 8883 入口绕过 guard、TLS hostname/IP 认证不匹配、双网络/loopback 无法证明，或者 DynSec 默认开放过宽，拒绝进入 Manager/HA。

### F3. 新 Manager 和独立新数据

使用经过现有 CI/独立源码验收的**实际产品 Manager 镜像**，绝不直接运行先前 R4/B1I1 的旧替换 launcher。构建或下载时固定镜像 digest、source commit、必要环境变量和挂载权限。建立并初始化 3 套全新 RW 数据源：registration、credential/replay、relay-keys；3 套 RO 由刚生成的 provisioning secret、Broker CA、Manager MQTT secret 提供。Manager 使用 host network，不暴露多余 published ports；Broker loopback TLS。要求真实 `/healthz`、TCP 47112、UDP 47111 和配对 IPC，就绪后验证数据库 schema、注册/凭据/重放 0/0/0 和 relay keys 空。

**STOP**：容器 Running 但服务不 Ready、DB 不是全空、挂载不是六个或旧业务数据混入、Broker 身份/CA 不匹配。

### F4. 新 Home Assistant 与开机自启

使用独立 Compose authority 启动干净 HA，以新 Broker 账号连接 MQTT；按产品预期创建集成与自动发现。执行双网络、TLS/ACL、8883 guard、NTP、证书生命周期、Broker 激活单元 enabled、Manager 与 HA 服务存续的**单次受控重启验收**。

**STOP**：重启后 Broker 或 Manager 不自启、证书失效、HA 不能连接或出现异常暴露入口。

### F5. 首次配对与数据链路验收（T1 完成后独立现场阶段）

以完全无历史注册状态的 Manager 与新 Broker 为基准，逐个处理目标 ESP32-C6 板卡的旧持久凭据（必须确认具体板卡）。保留 MAC/硬件唯一标识和产品固件，不混淆“恢复出厂配对状态”和“擦掉所有固件”。依据 ADR-0008 重新完成 Setup Secret PoP、首次注册 COMMIT、DynSec 最小权限生成、直接通信与 ESP-NOW relay、业务遥测，最后验证 HA 实体出现与真实读数持续更新。每个板卡验收独立归档。

**不把 T1 装好等同于温室整套系统物理验收成功。**

## 4. 最终验收合同与进度

```text
F0_HOST_TARGET_AND_ERASE_SCOPE=NOT_YET_VERIFIED
F1_FRESH_OS_INSTALL=NOT_STARTED
F2_FRESH_BROKER_TLS_DYNSEC=NOT_STARTED
F3_FRESH_MANAGER_0_0_0=NOT_STARTED
F4_FRESH_HOME_ASSISTANT_PERSISTENCE=NOT_STARTED
F5_BOARD_FIRST_PAIR=NOT_STARTED
FIRST_DEPLOYMENT_MODEL=CLEAN_INSTALL_ONLY_NO_ROLLBACK
OLD_MANAGER_RUNTIME_OR_R5_REQUIRED=false
GITHUB_SOURCE_AUTHORITY_REQUIRED=true
SOURCE_CI_REQUIRED=true
T1_REAL_MUTATION_THIS_GATE=false
DESTRUCTIVE_ONE_TIME_AUTHORIZATION=NOT_YET_ISSUED
```

### 完工判据

T1 从干净系统启动；可以独立管理；Broker 双网络/TLS/ACL/guard 通过；Manager 镜像源码绑定、`/healthz`、UDP/TCP 和空白业务 DB 均 PASS；HA 可订阅并显示温室数据；重启后自动恢复服务；目标板卡逐个重新配对并能持续上传真实传感器数据（不能以旧空 measurements telemetry 当最终产品验收）。

## 5. 当前 STOP 与下一工作

本次方向切换已由用户批准，可以**连续开展只读资料核查、GitHub 部署包设计、CI 和只读目标清单准备**，无需每一步重复申请。由于当前工具尚无 T1 的真实主机访问和磁盘标识，本轮不能宣称 F0 已完成，也不创建无法确认目标盘的删盘脚本。

```text
NEXT_ONE_GATE=N3W_T1_FULL_FRESH_INSTALL_F0_HOST_TARGET_MEDIA_AND_DESTRUCTION_SCOPE_READONLY
NEXT_GATE=READ_ONLY_REMOTE_HOST_INVENTORY_AND_INSTALL_MEDIA_VALIDATION
NO_OLD_MANAGER_ROLLBACK_WORK=true
NEW_INSTALL_FIRST=true
LIVE_ERASE=ONLY_AFTER_EXACT_T1_DISK_AND_IMPACT_CONFIRMATION
```
