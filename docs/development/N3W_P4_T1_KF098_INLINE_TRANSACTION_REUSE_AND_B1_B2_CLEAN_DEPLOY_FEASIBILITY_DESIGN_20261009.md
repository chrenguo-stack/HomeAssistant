# N3-W P4 T1 — KF-098 单流程部署与 B1/B2 清洁部署可行性设计（2026-10-09）

## 0. 决策、范围与真实证据

**结论：采用 A+B1 方案——保留现有 R4 的“三套全新 RW、三套原 RO、旧 Manager 同 ID 保护、Broker 不变”的产品目标，但借鉴 KF-098 已在 T1 实际成功的“单进程完成切换与同进程失败回退”事务控制。暂不重建 Broker，更不重装 T1 操作系统。**

用户批准的当前任务是：
`N3W_P4_T1_KF098_TRANSACTION_MODEL_REUSE_AND_CLEAN_DEPLOY_B1_B2_FEASIBILITY_DESIGN`。
**只做 GitHub 源码可行性设计、只读比较、文档与进度归档。** 不是授权在 T1 上部署、停止/删除容器、清空数据库、撤销凭据、重启系统、修改 Broker/HA、改动板卡/NVS、导入 Setup Secret 或合并 PR。

真实而非模拟的历史证据：
- `docs/development/N3W_KF098_T1_LIVE_CUTOVER_PROGRESS_ALIGNMENT_20260928.md`：2026-09-28 KF-098 成功替换 T1 Manager，`FINAL_APPLY_RESULT=PASS`，六挂载、Broker、R5 维持，`ROLLBACK_ATTEMPTED=false`。
- `docs/development/N3W_KF098_DYNAMIC_DISCOVERY_REAL_TRAFFIC_ACCEPTANCE_CLOSURE_20260928.md`：随后 Board B UDP/47111 发现与 HTTP/TCP47112 通信验收 `CLOSED_PASS`。
- KF-098 可执行源码（成功版本）：
  `88e9d140e5baddba543a961f003d12f7ce563ed2`，
  `tools/execution_packages/n3w/kf098/t1_live_cutover/{executor.py,remote_cutover.py,TASK.md,manifest.json}`。
- 当前待修 R4 源码：精确十一脚本源码 `1528ae970974fd711f8a8a6441c29817a118d825`，
  `tools/execution_packages/n3w/p4_manager_cold_backup/`。
  原 PR #540 仍 `OPEN_DRAFT`。141 项模拟 CI 已通过，但独立复核仍因 A6（120s stop-post 回退预算不覆盖 180s+ 单项等待；systemd 420s 终止宽限及后续监督不足）标记 `NO_GO`。
- `infra/n3w-t1/README.md` 当前 main：Broker 双网络、8883 wildcard + fail-closed guard，`n3wfc4` Compose 由多份 authority 管理，同 project 的 `fc4-homeassistant` 是正常独立服务，不是可清理 orphan。禁止 `--remove-orphans`。
- `docs/adr/0008-n3w-pairing-recovery-simplification-v2.md`：首次注册、普通修复、MQTT 密码轮换、N3-W 应用密钥轮换和 SYSTEM_PEER_KEY 信任轮换是不同生命周期；稳定硬件/节点身份及权限边界仍受保护。

本 Gate 没有访问 T1，所以“旧 Manager 还健康、Broker 仍稳定”仅是先前实测的最后有效快照，**不是今天重新读取的运行事实**。未来任何 T1 操作前都要刷新只读基线。

## 1. 精确代码对比与共性/差异

| 合同 | 已成功 KF-098 | 当前 R4 | 本轮判断 |
|---|---|---|---|
| 目标 | 原 Manager 升级，六挂载**全部延续** | 三个新 RW（业务空白）+ 三原 RO（不变）；旧 Manager 保留 | 不可直接复制 KF-098 数据延续策略 |
| 主事务 | `remote_cutover.apply(): try ... except: rollback(prestate)` 在同一进程内控制已知异常 | `fresh_manager_deploy.execute_transaction()` 正常流程 + systemd `ExecStopPost` 回退；`fresh_manager_operator.execute()` 二次最终检查 | 推荐复用单进程 try/rollback 模式 |
| 旧容器 | 删除旧 Manager；回退时按原镜像与原挂载重建 | `docker stop` + `docker rename` 停放旧 Manager，保持相同 Docker ID 与旧 RW | **保持 R4 同 ID、原样恢复，不能复制删除旧容器** |
| 备份和安全 | 冻结旧运行镜像、旧 Env、六挂载、Broker/R5；旧 shadow + 新 shadow | R5 冷备份、R2/R3 历史文件，当前影子容器、安全对齐 | 把安全/备份预检作为新事务 PRECHECK，不放松 |
| 就绪 | `/healthz` 30s 有界轮询、UDP/47111、TCP/47112、Broker/R5 | 新数据库 0/0/0、relay-key 空、Unix socket、CLI、TLS8883 等 | **组合使用，而不是以 0/0/0 代替真实健康端点** |
| 等待 | Mac phase preflight 180s，apply 900s，人工 rollback 600s | systemd 420s ExecStart、120s stop-post，operator 580s、远端 660s、SSH 920s | 900/600 是成功历史预算**不是可直接当安全证明的常数** |
| 物理验收 | 成功后另做 Board B Discovery/HTTP | 还需要空白首次配对、Setup Secret 交付及正式状态 | 严格分离部署 PASS 与首配 PASS |

精确目标挂载来自 R4 `cutover_contract.py`：
- 新建空白的 RW 挂载目标：`/var/lib/greenhouse-manager-registration`、`/var/lib/greenhouse-manager/n3w`、`/var/lib/greenhouse-manager/n3w/relay-keys`。
- 原封不动的 RO 秘密挂载：`/run/secrets/provisioning_password`、`/run/secrets/broker-ca.pem`、`/run/secrets/gh_manager_mqtt_password`。
- `fresh_state_contract.py` 验收 `registration.sqlite3`、`credential-lifecycle.sqlite3`、`replay.sqlite3` 各目标表行数为 0、relay-keys 为空。空白是 Manager 业务状态**不是 Broker/DynSec 清零的证明**。

## 2. 方案 A+B1：推荐的新执行合同（FEASIBLE_WITH_SOURCE_WORK）

保持现在实际需要的产品行为，不继续在旧 R4 systemd 多层超时上反复打补丁。建议**另建隔离的新执行包/新事务 ID**（不得让 R1–R4 命令和私有目录重放），复用经过验证的模块与测试，而不是直接覆盖历史事实。

### 2.1 核心执行顺序与 STOP 点

```text
PRECHECK_READ_ONLY
  -> exact Manager/Broker runtime identity and Broker TLS 8883 / guard / HA continuity
  -> exact source/image manifest, six mount names+permissions, three RO authorities
  -> original R5 cold backup equality / recoverability, stage/transaction nonreplay
  -> historical R2/R3/R4 evidence present and archived without modification
  -> new three RW host roots exist? require not-exist (then create in PREPARE)
  -> STOP if ambiguity

PREPARE_NONDISRUPTIVE
  -> private journal with old Manager ID/image/Broker ID/start/restart
  -> create separate 0700 fresh registration/n3w/relay-key roots
  -> verify all empty and owned by expected runtime UID/GID
  -> stopped shadow matches exact image + six bind + security + RO config
  -> STOP if mismatch; do NOT stop Manager

CLAIM_AND_INLINE_CUTOVER
  -> capture/verify remaining transaction/rollback budget
  -> stop old Manager by exact ID, verify stopped
  -> rename old to unique rollback name, preserve old 3 RW roots
  -> create new Manager with 3 fresh RW + original 3 RO
  -> start and health-check candidate (/healthz, UDP47111/TCP47112, local pairing socket,
     config/CLI availability, TLS8883 broker session, 0/0/0 and empty relay keys)
  -> reverify Broker identity/start/restart, HA untouched, R5 guard
  -> commit durable journal, set restart policy, keep old Manager parked
  -> PASS only after final independent identity/health check

ON_KNOWN_EXCEPTION_WITHIN_TRANSACTION
  -> inline rollback using the same frozen journal and exact old Manager ID
  -> stop/park transaction-owned candidate (never arbitrary unknown container)
  -> rename original exact ID back, restart old, verify Broker unchanged and health
  -> PASS_ROLLED_BACK only on actual identity + runtime proof
  -> otherwise FAIL_ROLLBACK_INCOMPLETE + stop, no replay

ON_PROCESS_KILL_OR_HOST_CRASH
  -> journal survives and protects phase/IDs, but inline rollback cannot run
  -> a separately versioned recovery mechanism is mandatory
  -> no claim of automatic recovery without testing kill/power/daemon failure paths
  -> STOP and read-only forensic before manually authorized recovery
```

**关键设计原则：**
- 把同进程回退作为**正常可捕获失败**的主恢复机制；外层监督只能作为“进程意外消失”保护或取证入口，**不能设成比完整回退更短的硬截止**。
- 对每个阶段设置截止时间并计算同一次提交的剩余总预算，保留可测算的回退余量；远程 SSH 外层大于「部署 + 内联回退 + 证据确认」上限。不得通过取消所有超时修复 A6。
- 严格区别应用故障、Docker 默认值表示变化、异常退出、SSH 丢线和 Broker 真实漂移；不能把没有日志等同于产品故障。
- 尽量将 R2/R3/R4 历史私有取证变成封存、只读、不可销毁的**审计输入**，而非每次新事务都重新扫描和逐字节比较历史影子容器的**实时前置依赖**。新的执行器以「**当前 Manager/Broker 精确身份 + 最新 R5/恢复快照 + 六挂载 + 新空数据**」为实际安全前置。变更这种前置合同需要单独源码复核，不得在现有 R4 上直接绕过保护。
- 退出码不能单独认定 PASS；应由 durable journal 与当前 Docker/健康/TLS/零状态证据共同证明。
- 与 KF-098 不同，任何正常 rollback 都应优先保留**同 ID 原版容器**；除非另有明确授权，不使用 `docker rm old` 的 KF-098 策略。

### 2.2 模拟测试和真实验收边界

最低测试矩阵：
1. 源码清单、归档备份、六挂载、UID/GID、RO 密钥校验；新 RW 三源真正全空，旧 RW 未触碰；Broker/HA/R5/8883 未发生变化。
2. 在停旧 Manager 之前每个 PRECHECK/PREPARE 失败，旧 Manager 原 ID 仍运行，无候选进程。
3. 旧 Manager 停止后、停放后、候选创建后、候选启动后、零状态检查中、commit 前的逐阶段故障注入；能回退则真 PASS，不能回退则明确残留与 STOP。
4. 某个 Docker 命令“单项成功但耗尽整体预算”；必须保留足够的总回退时间并避免外层抢先超时。高成本（长达数分钟）的等待不通过不断增加外层时间来掩盖。
5. 模拟直接杀掉事务进程、SSH 断开、systemd 单元终止、Docker daemon 不可用、Broker 改变、意外陌生容器占名；严禁任意身份的删除/重启，恢复步骤可读、可独立执行。
6. 真实 T1 授权后先只跑 PRECHECK；另一个有明确提交边界的生产 one-shot；主机验收 PASS 之后再单独授权板卡首次配对和 Setup Secret 交付，不混入部署事务。

**有效工时判断：** 对 A+B1 是“**现有模块重组和安全回归**”，不等价于重建网络、证书、DynSec、Home Assistant。能否只改极少文件需要下一步源码设计确认，不能凭本轮只读复核承诺固定天数。

## 3. B1 纯全新 Manager 部署——事实上的同一业务目标

无需清空宿主机或 Broker。当前 R4 已经实现的 B1 实际状态是：
- Manager 业务数据：**新建**三套 RW host roots，不继承旧注册、凭据生命周期、重放和 relay key。
- Manager 配置/信任：**保留**三个 RO 秘密、Broker TLS/CA、Manager 到 Broker 的身份以及原六挂载目标。
- 原 Manager + 三旧 RW：**保留**，在切换失败时能回到原容器/原数据。
- Broker/DynSec 与 HA：**不动**，因此不能宣称“系统所有历史节点凭据都被删除”。

需要特别区分：
- Manager 0/0/0 + 空 relay key = **Manager 本地干净**；不意味着旧节点已经未配对/没有 NVS。
- Broker 可能仍保留旧客户端、账号、角色、ACL 与密码生成记录。旧节点若仍用旧 NVS 连接，可能产生“Broker 有凭据、Manager 没注册”的历史身份冲突。必须先做 Broker DynSec 与已配对节点只读库存，选择将旧节点隔离、不上电，或对**精确已确认目标账号**另开撤销门。
- 新的首次配对必须遵守 ADR-0008 的随机 pairing ID、Setup Secret PoP、最终收据 COMMIT、安全生命周期。单纯删除 Manager 数据**不自动执行或授权**重新配对。
- 相比 B2，B1 对 Home Assistant、TLS 8883、防火墙、Broker 两网络、系统服务持久化影响最小。

结论：**B1 可行，且其数据面与当前 R4 已实现功能高度相同；应解决执行器，不要为“B1”另造完整部署架构。**

## 4. B2 业务系统全新部署：条件备选，不作为现阶段默认

B2 涉及 Broker/DynSec + Manager 业务态，不能等同于 `docker compose down -v`：

| 资产类别 | B1 | B2 候选处理 | 风险与前提 |
|---|---|---|---|
| Manager registration/credential/replay/relay-key（3 RW） | 新空目录，旧目录封存 | 同 B1 | 板端旧身份可能不匹配 |
| Manager provisioning、Broker CA、Manager MQTT secret（3 RO） | 保留 | 通常先保留，需单独评估是否重签/轮换 | 不能随意销毁信任根 |
| Broker Dynamic Security 用户/组/角色/ACL | 不改 | 只清理可证明属于 N3-W 的旧节点身份，或在明确批准后重建命名空间 | 误删 Manager/HA 账号会断连；要证明命名空间/权限归属 |
| Broker 持久会话、保留消息、Mosquitto 配置 | 不改 | 必须逐项判断可丢弃与需保留 | 可能影响 HA 实体发现/订阅/遥测 |
| Broker TLS CA、私钥、证书、续签 unit | 不改 | 默认保留原信任体系，换代单独审批 | 影响已配对节点与 HA TLS 信任 |
| N3W/FC4 Compose、Broker 双网络、R5 firewall/guard | 不改 | 必须保留已验证拓扑和精确激活所有权 | 曾有 T1 网络、8883 publication 回归 |
| `fc4-homeassistant`、其他 Home Assistant | 不改 | 不在 B2 业务清洁范围 | 同 project 不同 Compose owner，不能当 orphan |
| 固件板卡 NVS/硬件身份/Setup Secret | 不改 | 另开具体物理和安全门 | Broker 清空不会同步清空板卡；不可捆绑 |

B2 可行性需要以下事实，**本轮 GitHub 尚未以最新 T1 现场状态证明**：
1. Broker DynSec 具体账号/ACL/角色与 Manager 和 HA 的所有权对应；
2. 当前 Broker persistence/TLS/CA/activation 实时绑定、双网络与防火墙保护和 HA 客户端依赖；
3. 目标板卡是否已有有效持久凭据、期望保留哪些节点身份、是否有未完成首配状态；
4. 若清理旧身份，能否只处理 N3-W 的旧节点并证明非目标账号/HA 功能不受影响；
5. 可靠冷备份、恢复演练和可接受停机窗口。

如果仅发现旧节点身份冲突，优先**精确撤销/隔离单个旧身份**，而非重建整个 Broker 或 CA。B2 会扩大故障范围，不能作为 A6 设计缺陷的代替修复。

## 5. 进一步极限方案 B3

整机 T1 操作系统擦除重装**没有现有证据支持“必须”**。已知 T1 运行有 Home Assistant、Broker 两网络、Systemd 激活/守护、TLS 生命周期和独立持有的配置。全盘删除要求逐服务清单、备份/恢复验证、HA 业务接受停机、T1 登录/系统/网络重建、根 CA/密钥信任处置，并由用户另行逐项明确授权。不能将用户“如果实在不行可以考虑清除”的条件性态度当作无边界删除许可。

## 6. 推荐下一门与决策点

```text
CURRENT_GATE=N3W_P4_T1_KF098_TRANSACTION_MODEL_REUSE_AND_CLEAN_DEPLOY_B1_B2_FEASIBILITY_DESIGN
FEASIBILITY_DESIGN_RESULT=PASS_WITH_DEFINED_NEXT_SOURCE_GATE
RECOMMENDED_PRODUCT_TARGET=B1_FRESH_MANAGER_3_RW_PLUS_3_EXISTING_RO
RECOMMENDED_EXECUTION_MODEL=KF098_STYLE_SINGLE_PROCESS_INLINE_ROLLBACK_WITH_SAFETY_JOURNAL
REUSE_FROM_R4=EXACT_CANDIDATE_AND_SIX_BIND_CONTRACT_FRESH_ZERO_STATE_OLD_ID_PARKED_AND_BROKER_CONTINUITY
DO_NOT_COPY_FROM_KF098=DELETE_OLD_MANAGER_AND_PRESERVE_OLD_RW_FOR_CANDIDATE
OLD_R2_R3_R4_PRIVATE_EVIDENCE=RETAIN_AUDIT_NOT_AUTOMATIC_LIVE_SHA_CHAIN
BROKER_OR_HA_RESET_REQUIRED=false
BROKER_DYNSEC_LIVE_INVENTORY=NOT_YET_PROVEN
B2_FULL_BUSINESS_RESET=CONTINGENCY_ONLY
B3_OS_REINSTALL=NOT_AUTHORIZED
PR540=OPEN_DRAFT
NO_T1_MUTATION=true
NO_OLD_DATA_DELETION=true
NO_BROKER_OR_HA_CHANGE=true
NO_BOARD_OR_SETUP_SECRET_CHANGE=true
NO_MERGE=true
NEXT_ONE_GATE=N3W_P4_T1_B1_KF098_INLINE_CUTOVER_EXECUTOR_SOURCE_DESIGN_AND_RISK_REVIEW
```

下一门只做**简化单流程执行器的精确源码设计**，先决定新包边界、哪些 R4 模块可原封保留、内联异常恢复和进程崩溃恢复的接口、如何在源码级取消无价值的历史影子容器重复检查但保留取证可恢复性。输出实施文件/测试矩阵、预算边界与独立复核要求；**不直接产出可运行于 T1 的命令**。只有完成源码开发、综合 CI、独立复核、fresh T1 read-only baseline，并另获明确授权后，才能进行下一次生产替换。
