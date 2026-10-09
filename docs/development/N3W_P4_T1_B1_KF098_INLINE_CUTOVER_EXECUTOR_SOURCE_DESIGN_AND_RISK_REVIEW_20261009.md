# N3-W P4/T1 — B1 KF-098 单流程切换执行器源码设计与风险复核（2026-10-09）

## 0. 本门、授权与最终结论

```text
CURRENT_GATE=N3W_P4_T1_B1_KF098_INLINE_CUTOVER_EXECUTOR_SOURCE_DESIGN_AND_RISK_REVIEW
MODE=SOURCE_DESIGN_AND_RISK_REVIEW_ONLY
B1_PRODUCT_TARGET=FRESH_MANAGER_3_RW_WITH_EXISTING_3_RO
DESIGN_DECISION=ISOLATED_B1I1_INLINE_CUTOVER_AND_ROLLBACK
DESIGN_OUTCOME=DESIGN_READY_WITH_EXPLICIT_SOURCE_BLOCKERS
R4_PRODUCTION_RESULT=NO_GO
B1I1_SOURCE_IMPLEMENTED=false
B1I1_LIVE_AUTHORIZED=false
T1_MUTATION=false
OLD_DATA_DELETE=false
BROKER_OR_HOMEASSISTANT_MUTATION=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORT=false
PR_MERGE=false
```

用户批准本门源码设计与风险复核，不包含开发可直接执行 T1 的部署命令、修改 T1、执行清理、恢复历史 R1–R4 事务、切换 Broker、烧写板卡或合并 PR。本报告的执行包名称与内部合同为**设计提案**，不是现有可调用的生产工具。GitHub 历史资料不能证明 T1 此刻的实际状态；一切实机操作之前必须 fresh read-only rebind。

此前设计结论权威：
`docs/development/N3W_P4_T1_KF098_INLINE_TRANSACTION_REUSE_AND_B1_B2_CLEAN_DEPLOY_FEASIBILITY_DESIGN_20261009.md`。
KF-098 真正成功执行器：`88e9d140e5baddba543a961f003d12f7ce563ed2` 的 `tools/execution_packages/n3w/kf098/t1_live_cutover/{remote_cutover.py,executor.py,TASK.md,manifest.json}`，2026-09-28 实测 `FINAL_APPLY_RESULT=PASS`、六挂载、Broker/R5 不变，后续 Board 真实通信验收通过。当前 R4：`1528ae970974fd711f8a8a6441c29817a118d825` 的 11 个受保护脚本。PR #540 保持 Draft；源码模拟测试虽通过 141 项，A6 真实部署仍 NO GO。

## 1. 核心判断：改变编排，保留产品和安全合同

**推荐 B1I1：新建隔离事务，将捕获到的部署异常和完整旧 Manager 恢复放进同一个受宿主管理的事务进程。** 不是再次把几个 systemd 超时值调大；也不是在当前 R4 上直接删掉 supervisor 或跳过历史证据检查。

现有 `fresh_manager_deploy.execute_transaction` 顺序调用 `preflight / prepare_fresh / shadow / stop_old / park_old / create_candidate / start_candidate / postflight / commit`，没有自身的 `try/except -> recover_original`。R4 主要通过 `fresh_manager_systemd_unit.ExecStopPost` 和 `fresh_manager_operator` 的最终检查错误回退，而 `TimeoutStopSec=120` 不覆盖回退逐项最长等待至少 180 秒以及更多检查。KF-098 的 `remote_cutover.apply()` 用同一进程 catch 已知异常后立即 `rollback(prestate)`，有 T1 成功先例；但是 KF-098 会 `docker rm old` 并继承旧数据，**这两点不准复制到 B1I1**。

### 1.1 计划中的新包边界（均非现有文件）

隔离路径提案：`tools/execution_packages/n3w/p4_manager_b1_inline/`。执行器代号 `B1I1`（**不用 R5 以免与已有 R5 冷备份混淆**）。新独立私有 journal、fresh RW 子目录、shadow、parked、failed aliases、运行锁、日志，全部与 R1–R4 和 KF-098 隔离。新授权 ID 必须独立，不允许使用 R4 单次生产授权；禁止旧 R4 launcher、旧 systemd unit 和旧事务 replay。

文件责任建议：

| 待设计/新增模块 | 单一职责 | 保留/替代 |
|---|---|---|
| `b1i1_contract.py` | 固定新事务命名、合法状态、精确镜像/挂载、拒绝重放及安全权限 | 参数化/复用 R4 `cutover_contract` 的纯校验，不复用 R4 全局事务名 |
| `b1i1_preflight.py` | fresh live Manager/Broker/HA/R5/证书与六挂载、镜像、旧状态冷备份可恢复性、Board 断电约束 | 借鉴 R4 `cold_snapshot`、`business_snapshot` 和 KF-098 live snapshot |
| `b1i1_fresh_state.py` | 创建三套独立 0700 RW 并验证空白 + 新 Manager 启动后的 0/0/0 | 复用 R4 `fresh_state_contract` 的只读验证逻辑 |
| `b1i1_transaction.py` | 整体时间预算、耐久 journal、明确 mutation boundary、旧 Manager stop/park、候选 create/start、同进程异常回退、终态证据 | 重组 R4 `fresh_manager_deploy`；KF-098 仅参考事务形态 |
| `b1i1_recovery.py` | 以 frozen old ID / Broker ID / candidate image + ID（如已持久化）恢复旧 Manager；防陌生容器覆盖；手动/宿主事故恢复 | 复用 R4 `fresh_manager_recovery` 的身份检查，不重用 R4 STATE_FILE |
| `b1i1_supervisor.py` | 将事务与 SSH 会话解耦；记录/监测运行、执行时间与异常消失；出事后取证和严格受限的保底恢复 | 不能仍让较短 systemd `ExecStopPost` 作为日常异常回退主路径 |
| `b1i1_launcher.py` + `manifest` + 专项测试/CI | exact commit + Git blob + 构建 artifact、一次性授权、Mac/T1 分离、私有日志脱敏 | 保留 R4 精确文件绑定、KF-098 结构化运行结果 |

**关键：不允许仅修改 R4 全局 `STATE_FILE` 后复用原恢复脚本。** 源码 `fresh_manager_recovery`/operator 目前直接引用 R4 常量，若未把依赖一并改为显式 B1I1 配置，就可能误写 R4 历史证据。建议复用只读、纯净的校验函数，执行器和恢复函数均通过明确同一 `B1I1` context 传入 journal 与 aliases。

历史 R2/R3/R4 失败事务私有文件属于**只读不可覆盖审计资料**。B1I1 的当前安全主依据必须是 fresh live Manager/Broker 的身份和受保护配置、经验证的原冷备份、当前六挂载及新部署准确 artifact，不再把过期 R2 影子容器整份 Docker inspect 的动态 SHA 作为新正确性门槛。替代历史门槛是**明确的安全合同变更**，需要在源码门单独独立复核；不得只因“觉得冗余”而绕过原版同 ID/冷备份验证。

## 2. 产品不变合同（B1 清洁的精确含义）

六个 bind 目标固定，不能依赖旧 Compose 中可能仅有三挂载的 Manager 定义：

- 新建、全空、不同于原 source 的三套 RW：`/var/lib/greenhouse-manager-registration`、`/var/lib/greenhouse-manager/n3w`、`/var/lib/greenhouse-manager/n3w/relay-keys`。
- 同样原 source、原权限、只读的三套 RO：`/run/secrets/provisioning_password`、`/run/secrets/broker-ca.pem`、`/run/secrets/gh_manager_mqtt_password`。

B1 无条件保留原 Manager exact Docker container ID（仅停止并停放）、原三 RW、R5 冷备份，Broker/DynSec、TLS/CA、R5 firewall guard、Broker 两网络、HA 容器、所有不相关 service 和历史证据均不删除。旧板 NVS/节点身份不得随之清空。

`fresh_state_contract` 证明 registration DB、credential-lifecycle DB、replay DB 的要求表及状态行数均为 0，relay-keys 为空。该 `0/0/0` 是 **Manager 本地的首配前业务空白状态**，不证明 Broker DynSec 中无旧账户/ACL，也不证明旧板已解除配对。Broker 账号与旧板冲突需要单独只读身份盘点；如需精确撤销，应另开授权。依据 `docs/adr/0008-n3w-pairing-recovery-simplification-v2.md`，首次配对及 Setup Secret 导入、MQTT 凭据生成、应用密钥、系统信任是独立生命周期，不能因部署自动旋转。

## 3. 原子事务、检查顺序和清楚的 STOP 点

```text
G0  READONLY_PREFLIGHT    current Manager/Broker/HA/R5 + exact source/image + authority
    STOP_0: anything ambiguous, no journal claim, no Manager mutation
G1  PRIVATE_PREPARE       create B1I1-only durable journal; three new blank 0700 RW;
                          stopped shadow creation/identity/config/mount verification
    STOP_1: original Manager remains RUNNING and exact ID; safe forensic preserve
G2  CUTOVER_CLAIM         durable intent for OLD_STOP, recheck same old/Broker and
                          available budget, then stop exact old ID
G3  OLD_PARK             durable intent, rename exact original ID to B1I1 parked name
G4  CANDIDATE_CREATE     durable intent before docker create; record actual new
                          candidate ID once obtained and re-inspect exact identity
G5  CANDIDATE_START      durable intent; bounded Docker start, stable run, real
                          /healthz, UDP47111/TCP47112 and pairing IPC readiness
G6  POSTFLIGHT           exact six binds/3 fresh RW/3 original RO/UID-GID/image,
                          zero rows + relay-keys empty, Broker ID/start/restarts,
                          live TLS8883 session + HA/R5 unchanged
G7  COMMIT               journal records verified current candidate, old parked ID,
                          exact source and successful business postflight
G8  FINAL_READONLY       independent current-status verification, publish PASS;
                          never infer failure solely from a dropped SSH response

KNOWN_EXCEPTION_BEFORE_G2:
  stop with original Manager running, preserve stage and journal; no attempt to
  restart/rename an unrelated container

KNOWN_EXCEPTION_G2..G7:
  same-process inline recovery; recheck exact old/candidate/Broker identities,
  stop and park only transaction-owned candidate; rename/restart the original
  same ID; prove runtime, Broker and HA continuity. Distinguish
  FAIL_ROLLED_BACK from FAIL_ROLLBACK_INCOMPLETE. No automatic replay.

SIGKILL / SSH_LOSS / HOST_CRASH:
  inline handler cannot run. Durable intent must precede every non-idempotent
  Docker action. Separate host-owned supervisor or bounded controlled recovery
  may inspect and recover only when all identities and journal phase match.
  Otherwise UNKNOWN_FROZEN / MANUAL_FORENSIC_REQUIRED; never assume rollback.
```

**源码必须决定并测试：**
- 在 G4 `docker create` 已完成而 candidate ID 还未写入 journal 的窄窗口，靠什么证明候选确实属于这次事务（例如不可伪造的事务标签 + image + mount + 旧 Manager parked ID + 创建时间窗口）；绝不能仅凭容器名字/镜像就随意停删未知容器。任何不确定状态停止处理而非猜测。
- `commit` 的定义：先完成必要的健康与空白验收、写入持久终态，然后才允许上层发布 PASS；不能将“Docker start 返回零”当 commit。commit 已持久化但 SSH 掉线时，必须 read-only reconcile，不得自动再部署。
- **不要让 post-commit 例行观察失败自动取消一份真正已经确认的业务成功**：必须定义 `CANDIDATE_VERIFIED` vs `FINALIZED` 边界，终态记录和实际 runtime 同时支持决策；任何未知终态要保持冻结、只读调查，避免新旧系统反复翻转。
- 必须捕获 Python 正常错误、Docker 超时与子进程非零等已知异常；对于 SIGKILL/断电绝不虚构可执行 `except`，必须有宿主进程消失后的身份受限救援路径。
- Broker/HA 不由切换事务管理，保持 current IDs/started/restart 与 TLS/R5 guard；不得 `docker compose down`、`--remove-orphans`、`docker system prune`、重建 CA 或 Broker。

## 4. 时间预算：一份事务 + 明确保留回退余量

**不直接照搬 KF-098 的 900/600 秒为本方案的“安全数值”。** 它们是 KF-098 已使用的 Mac 外层 phase timeout，不能覆盖 B1I1 的所有新数据库/停放/恢复路径。

拟制定单份 absolute monotonic deadline 文档（全部有限）：

```text
TIME_BUDGET_DESIGN=
  OBSERVATION_PRECHECK + PREPARE +
  MAX_ACTIVE_CUTOVER + RESERVED_INLINE_ROLLBACK + FINAL_EVIDENCE + MARGIN

AT_OLD_STOP:
  require remaining_host_owned_transaction_time >=
      MAX_CUTOVER_FROM_OLD_STOP + GUARANTEED_RESERVED_ROLLBACK + FINAL_EVIDENCE_MARGIN

FOR_KNOWN_EXCEPTION:
  bypass forward progress, enter dedicated bounded rollback budget immediately

HOST_SUPERVISOR_TIMEOUT:
  > whole maximum transaction including one inline rollback,
    but never treated as unconditional proof of successful restore

REMOTE_WAIT_TIMEOUT:
  > host supervisor termination/grace + emergency recovery/forensic deadline

SSH_TIMEOUT:
  > independent preflight + remote wait + safe result-collection margin
```

必须从 **各 Docker stop/rename/create/start/inspect、/healthz、Broker/TLS 及数据库检查**实际的每步超时上界导出总量，并用“每个命令都成功但耗费接近各自上限”模拟验证。普通前台 SSH 进程不可成为生产事务唯一 owner；否则 SSH 断线可能把 Manager 留在停止/停放状态。可设计 host-owned、与 SSH 解耦的受控一次性执行服务，但它的计时必须同时覆盖本进程内联 rollback，emergency `ExecStopPost` 仅是崩溃后兜底，而不是受短 stop timeout 限制的常规回退入口。

## 5. 源码风险复核矩阵

| 风险 | 现有证据 | 本门结论 / 必需关闭方法 |
|---|---|---|
| R1–R4 旧私有文件重复校验导致 false STOP | R3 `r2_shadow_inspect_sha256` 已实测唯一漂移 | **DESIGN_OPEN**：新 B1I1 以当前安全基线为 correctness，历史不可覆盖，独立复核新 snapshot |
| 同进程 rollback 尚不存在于 R4 | `execute_transaction()` 顺序调用；KF-098 `apply()` 有 `except rollback` | **DESIGN_OPEN**：实现且注入 G2–G7 全阶段故障 |
| 外层抢先杀掉回退进程 | R4 systemd stoppost 120s 小于源代码最长串行 180s+ | **DESIGN_OPEN**：总预算包含 inline rollback；host supervisor deadline 层级证明 |
| 进程被强制终止、SSH 断线、T1 掉电 | 同进程异常 handler 对 SIGKILL/掉电无效 | **DESIGN_OPEN**：durable intent + 事故恢复，未知状态保持冻结 |
| candidate ID 持久化窗口 / 不可识别候选 | 旧 R4 callback 记录 candidate ID 在 create 之后 | **DESIGN_OPEN**：中间状态采用事务归属证明，歧义不得动未知容器 |
| Docker 命令成功但已超时 / 状态未知 | KF-098 和 R4 都使用有界 subprocess | **DESIGN_OPEN**：操作后真实 inspect、整个 deadline、禁止按返回值猜测状态 |
| “容器 Running”不等于服务 Ready | KF-098 曾遇 TCP47112 未恢复，后加 bounded `/healthz` | **REQUIRED**：空状态校验外，还要明确健康、TCP/UDP、IPC、TLS8883 |
| 三个新 RW 与原三 RO/旧 RW 混挂 | R4 `plan_isolated_bindings` 和 zero-baseline 校验已有 | **PURE_GUARDS_REUSABLE**：原源不写、新源不交叉重叠、权限 + 安全配置对齐 |
| Broker 历史账户与新 Manager 业务态不一致 | 现有文档区分 Manager 0/0/0 与 Broker DynSec | **READONLY_PREBOARD_GATE**：盘点遗留账户/ACL及板 NVS 约束，不自动清 Broker |
| Broker/HA 非目标服务误删 | T1 `n3wfc4` Compose 项目存在另一 ownership 的 `fc4-homeassistant` | **FORBIDDEN**：不允许 --remove-orphans / Compose project cleanup |
| 旧 Manager 保留原 ID，却被异常重启策略拉起 | 源码原 `unless-stopped` + stop/rename | **DESIGN_OPEN**：回退/成功后需验证旧停放保持停止，避免监听端口争用 |
| 真实数据安全与最小保留范围 | R5 冷备份、旧 3 RW、R2–R4 证据 | **INVARIANT**：只加不删，尤其禁止误当临时目录 prune |
| 结果输出丢失与重复尝试 | R1–R3 已多次一枪 STOP，不能重放 | **INVARIANT**：终态查询而非重复执行；live 需新授权 |
| 回退成功但 Manager 产品状态未恢复 | R4 `controlled_window.resume_original_manager` 主要检查 Running 和 Broker；KF-098 有 `/healthz`、TCP/UDP | **DESIGN_OPEN**：旧 Manager 回退完成也验证真实健康、原六挂载、业务快照 / Broker unchanged |

该矩阵属于**设计阶段开放项**，不代表生产现场正在发生这些故障。

## 6. 下一步编码文件/测试/评审清单（仅规划）

新执行器 source authoring gate：
1. 冻结新 `B1I1` 事务 schema、唯一命名、源码/镜像身份、保留和恢复边界；文件级说明哪些 R4 纯 guard 直接导入、哪些全局状态必须消除并通过测试证明隔离。
2. 实现 B1I1 的 host-owned one-shot + 同进程可捕获异常立即回退、durable intent 以及只读 status/reconcile；不重写 Broker 或 HA 服务。
3. 通过静态/模拟测试：预检与准备失败、每个 G2–G7 失败/恢复、已经 committed 的读取、候选 create/record 中断、陌生占名、长耗时成功命令、SSH 断开、进程中止、Docker down、原 Manager 无法启动、Broker 改变、候选/旧版本复活、日志脱敏和重复授权拒绝。
4. exact source/tree + image artifact bind、编译/语法测试、Manager CI、public safety CI；独立代码审查特别关注正常异常回退与异常消失恢复**不是一条相同路径**。
5. 只有独立源码和 CI 关闭后，申请 T1 read-only prelive gate 以重新确认旧 Manager/Broker/HA/R5 与 Broker DynSec 历史身份；若发现非目标服务、旧凭据冲突或当前生产锚点漂移，STOP 重新设计，不执行删除。
6. 新 live cutover、板卡首次正常 boot、Setup Secret 交付和正式首配各为**单独的物理授权门**。不以 CI 结果代替真实执行证据。

```text
SOURCE_DESIGN_GATE=COMPLETE
PRODUCTION_READY=false
NEXT_ONE_GATE=N3W_P4_T1_B1I1_INLINE_TRANSACTION_AND_RECOVERY_SOURCE_IMPLEMENTATION_WITH_SYNTHETIC_TESTS
NEXT_GATE_SCOPE=SOURCE_TEST_CI_ONLY
NEW_EXECUTOR_AUTHORIZATION=NOT_YET_ISSUED
EXACT_ARTIFACT=NOT_YET_BUILT
EXACT_LAUNCHER=NOT_YET_BUILT
LIVE_ONE_SHOT=false
B2_BROKER_REBUILD=DEFERRED
B3_T1_FULL_WIPE=NOT_AUTHORIZED
T1_DATA_OR_SERVICE_CLEANUP=false
```

本 Gate 所有设计判断都基于已点名的 GitHub 源码和历史部署记录。新的 `B1I1` 路径与事务结构均为待实现设计，**不能被视为真实项目执行器已经存在或通过测试**。
