# N3-W P4 — T1 Manager 单次受监督切换与原版回退设计（2026-10-09）

## 1. 本门任务及明确限制

```text
TASK=N3W_P4_T1_CANDIDATE_MANAGER_DEPLOYMENT_PREPARATION_AND_SINGLE_CONTROLLED_CUTOVER_DESIGN
GATE_TYPE=SOURCE_ONLY_AND_DESIGN
PRODUCTION_MANAGER_REPLACEMENT_AUTHORIZED=false
T1_LIVE_MUTATION=false
BOARD_ACCESS=false
MQTT_DATA_TEST=DEFERRED_NO_POWERED_ESP32_C6
REPEAT_OLD_MANAGER_COLD_BACKUP=false
```

本门为**部署准备与一次性切换方案**，不是现场执行授权。用户明确要求终止重复的零散人工验证。本轮依托已经完成的现场证据，全部设计、测试与复核都在 GitHub 上进行；之后如获批准，只允许一次 Mac Terminal 启动完整任务，自动报告 PASS 或 STOP。

## 2. 已有事实与精确来源

- P4 新 Manager 固件源码来自 PR #538，exact commit `3d86d6bfaf361dc3a3d7295d046f541a544d552d`，其更改继承先前 P4 Pending/QR/expiry-at-use source gates；相关 PR 尚为 Draft，不能把“通过编译”解释为已部署。
- T1 **已有**本地构建候选镜像 `n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d`，已验 `linux/arm64`、镜像 revision、三个 P4 CLI/guard 隔离检查 PASS。不能再次重建或导入覆盖同一 tag；真正部署前仍须绑定 **实际镜像不可变 ID**，而不只是 tag。
- T1 原版 `greenhouse-manager` 使用 host network、无端口映射、只读 rootfs、固定运行用户、六个 bind mount（三个 RW 数据源及三个 RO secret）；Broker 为独立 `n3wfc4-broker-1`。旧版 live 配置和旧镜像 tar 位于此前的 T1 root-private 归档中。
- **关键历史陷阱**：现场旧 Compose Manager 只有 3 个 mount，而真实 Manager 有 6 个、且历史 Compose label 数为 0。历史 KF-098 实际源码合同已指出 Compose 文件不是当前 Manager 的重建权威。部署必须按**当前 live Docker inspect**完整重建，不允许直接 `docker compose up --force-recreate`。
- R5 精确源码 `ca75d6bbc672d9e1e96500c88827ec529855f2b9` 已在 T1 经单次监督真实执行，三持久 RW 源冷备份、isolated restore、业务数据指纹与旧版 Manager 恢复全 PASS。单次成功后 Manager 已重新运行，**那次冷快照不可假定与将来切换时刻的实时数据完全相同**。
- 上次 90 秒 Manager/Broker 运行状态稳定、MQTT TCP 连接存在，但 `replay tuples 475→475`；用户已证实 ESP32-C6 **长期断电**。该观察不可充当活节点业务数据 PASS/FAIL，板端遥测要留给正式产品正常启动后再测。

## 3. 一次切换的总体原则

**保留旧容器与旧数据原状；新版只使用在同一次短暂停写窗口中新建的独立数据副本。**

这比“先删除原容器、让新版直接写旧数据库，失败再从老备份覆盖”更易安全回退。不可为节省几秒钟让两版 Manager 同时对原始注册库、credential/replay 和 relay-keys 写入。

T1 私有工作区（运行时随机标识）内隔离创建三个 RW clone source，分别映射到**原容器相同 Destination**：

| Container Destination | 原版 | 候选版 |
|---|---|---|
| `/var/lib/greenhouse-manager-registration` | 原始 RW Source | 独立 registration clone |
| `/var/lib/greenhouse-manager/n3w` | 原始 RW Source | 独立 n3w clone |
| `/var/lib/greenhouse-manager/n3w/relay-keys` | 原始独立 RW Source | 独立 relay-keys clone |
| 三个 `/run/secrets/*` | 原 RO Source | **同一个原 RO Source，继续只读** |

必须继续保证两个数据库数据树和 relay-keys 虽然**容器 Destination 嵌套**，真实宿主 clone source 仍是独立三个目录。克隆目录须位于可长期保存、仅 root 管理的持久路径；如 Docker bind mount 下容器 UID 无法按预期访问，立即回退，禁止临时放宽 secret 文件权限或用全局 chmod。

## 4. 后续完整执行包的唯一入口（尚未执行）

1. **自动 preflight（旧 Manager 持续运行）**：绑定当前原容器 Id/image/config/六挂载、Broker Id/start/restart/network，读取原私有归档与既有冷备份证据；精确绑定候选 image ID、ARM64/revision、旧 live Config/HostConfig；足够空间、原 secret 依旧 RO、没有外部容器/宿主进程写者证据、恢复单元与名称无冲突。旧历史检查不再要求用户逐项执行。
2. **离线 stopped shadow（旧 Manager 不停）**：创建不含实际数据库数据、尚未启动的三个候选 clone 路径和 temporary **stopped shadow**。从 current live inspect 生成候选六 bind 配置；源代码 `cutover_contract.py` 检查 Secret RW/RO、host networking、env、image labels、tmpfs、caps、资源与只读根目录对等。影子容器不启动，不连接 Broker，不加载业务数据。任何差异在旧服务停止之前 STOP。
3. **一次受监督短暂停写窗口**：systemd 单次工作单元及独立失败恢复后备保护下，停止**原 Manager**，不触碰 Broker。确认所有 SQLite DB/WAL/SHM 不再被任何进程占用；从当时的**真实三个 RW Source**完整复制到事先创建的三份独立 clone（包括动态 sidecars 和所有未知业务文件、权限/UID/GID），原始 Source 在窗口前后 hash/size/attrs 稳定。该步骤是为新版准备最新状态的必要快速复制，**不是重复要求用户再次完成 R5 全套备份和人工验收**。
4. **在 clone 上校验**：核对三个 SQLite `integrity_check`、已知至少五个历史 identity、credential generation、replay 高水位、relay keys、文件清单和原文件拷贝前后内容指纹；阻断任何误连原生产 RW Source。任何失败原容器直接恢复，无后续新版动作。
5. **保留旧容器、切换名称**：将已停止的旧 `greenhouse-manager` 改为唯一可识别的 parked rollback 名称；**不得 docker rm 旧容器/删除旧数据/镜像**。新版 `docker create` 使用经 shadow 证实的当前原版 Config/HostConfig 合同、替换 exact candidate image ID、只替换三条 RW bind Source 为 clone，三个 RO source 不变、host network 不变。只准有一个同名 `greenhouse-manager` 正在运行。
6. **运行态基本验收**：先以不自动重启策略启动候选；确认候选 image ID、6 mounts、3 secrets RO、权限、用户、网络、Broker 容器/端口/启动时间不变、新版 P4 pairing 只读命令与本地健康服务可用、Manager 自身稳定并有到 Broker 的 TCP 会话。**没有上电节点，不要求 5 秒新遥测计数增长。** 成功后才设置长期开机恢复策略，并将 clone 的持久 Source / old parked 容器身份存入 root-private 0600 manifest；用户只收到简短安全 PASS 摘要。
7. **失败回退**：任何 stop / copy / clone / rename / candidate create / start / postflight 失败，立即 STOP 切换；若候选已运行则停止它，明确核对实例 ID 后移走该候选名称；恢复保留的**原容器及未被新版触碰的原始 RW 数据**，验证其稳定运行和 Broker 不变。候选 clone 保留供 private 取证。不盲目执行 `docker rm -f greenhouse-manager`，也不能复用过时 Compose 定义重新创建一个新“旧 Manager”。若原容器无法恢复，独立 systemd 救援尝试并报告 `FAILED_STOP_MANUAL`，不得输出 PASS。
8. **事后边界**：切换成功后 parked 原容器及其完整原始数据暂不删除。若新版开始处理真实生产数据，两个数据树会分叉，届时**不能无条件直接切回过时旧数据**；须另行评估真实数据丢失风险/向下兼容迁移。新 P4 配对/Setup Secret 导入/板端首次正常启动属于后续独立授权，绝不纳入本次无节点的部署窗口。

## 5. 安全审查发现与必关项

- **A1 真实配置权威**：必须以 T1 当前运行 `docker inspect` 和私有 origin 交叉验证，禁止 3-mount historical Compose；需要版本化的**全部有效 create args** 且 shadow 创建后的 live contract equality，不允许仅校验 6 条挂载就宣称其余安全配置等价。
- **A2 源/clone 隔离**：候选 RW bind 不能等于、嵌套于任何原始 Source；三个 clone 互不嵌套，RO secret Source 完全一致（源码 `cutover_contract.py` 已覆盖此静态合同）。
- **A3 新旧数据库兼容性**：不能假设新版在 clone 上迁移后仍可被旧版读取；回退必须保留未修改的原数据库，不回写新 schema。候选 clone 上的 SQLite 检查不能被运行中留存的旧 R5 快照替代。
- **A4 服务与救援**：必须独立的 systemd one-shot + `ExecStopPost` 恢复合同，针对因 SSH 断线、主执行器退出、Docker start 失败、超时建立状态机与私有原子 phase 记录。失去 Docker/systemd/电源时无法保证自动恢复，要有一次明确人工救援步骤。
- **A5 新版实机验收范围**：本门只可证明 T1 host-side 服务就绪。ESP32 全部断电，不能要求真实遥测/实际 P4 Setup Secret import；MQTT TCP establishment 不是自动证明业务数据验收。
- **A6 依赖组件边界**：Broker 双网络、TLS/8883、Home Assistant、证书和已配对节点身份均不被本门重启、重建、更新；失败只能操作 Manager 名称和本门创建的 clone/独立单元。
- **A7 当前审查的硬边界**：`cutover_contract.py` + `test_cutover_contract.py` 是**纯源码合同与模拟单元测试**，不会创建/停止/改名容器；完整真实执行器和对应 failure-injection 单测**尚未实现**。在它们经独立复核并取得**新授权**前，严禁从此文手工执行 `docker stop/rename/create/start`。

## 6. 本门交付物和结果

```text
N3W_P4_T1_MANAGER_CUTOVER_DESIGN=COMPLETE
SOURCE_AUTHORITY=PR538_3d86d6bfaf361dc3a3d7295d046f541a544d552d
CANDIDATE_ARM64_ON_T1=ALREADY_BUILT_AND_ISOLATED_GATES_PASS
OLD_MANAGER_R5_COLD_BACKUP_AND_RESTORE=CLOSED_PASS
OLD_COMPOSE_NOT_RECREATE_AUTHORITY=TRUE
NEW_MANAGER_USE_INDEPENDENT_RW_CLONES=REQUIRED
OLD_CONTAINER_AND_RW_SOURCE_RETAINED_FOR_ROLLBACK=REQUIRED
CONTRACT_SCRIPT=cutover_contract.py
SYNTHETIC_TESTS=test_cutover_contract.py
FULL_SUPERVISED_DEPLOY_EXECUTOR=NOT_YET_IMPLEMENTED
REAL_PRODUCTION_MANAGER_SWITCH=NOT_AUTHORIZED
BROKER_MUTATION=false
ESP32_C6_POWERED=false
NEXT_ONE_GATE=N3W_P4_T1_CANDIDATE_MANAGER_ONE_SHOT_CUTOVER_EXECUTOR_AND_FAILURE_RECOVERY_TEST
```
