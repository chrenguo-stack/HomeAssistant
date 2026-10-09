# N3-W P4 / T1：对照 KF-098 成功部署与全新部署备选路线（2026-10-09）

## 结论和授权边界

用户明确同意先复核 GitHub 中 2026-09-28 成功的 KF-098 T1 Manager 部署执行器；如果现有恢复路线持续不通，愿意考虑“对 T1 执行全新部署，把所有旧环境、旧数据都清理掉”。

**本轮只读比较与方案设计。** 将“全新部署”理解为条件性备选方向，而**不是已经授权立即清除任何 T1 数据、重装系统、删除 HA/Broker/Manager、撤销身份或烧写实板**。未来若触及真实删除，须先审定逐项清理边界、保留/销毁清单、可用性影响、备份可恢复性，并取得明确的执行授权。本轮没有 T1 访问、生产变更、源码修复、PR 合并。

```text
TASK=N3W_P4_T1_KF098_SUCCESSFUL_DEPLOYMENT_COMPARATIVE_REVIEW
MODE=GITHUB_SOURCE_ONLY_READONLY_COMPARISON_AND_DOCUMENTATION
KF098_PROVEN_SUCCESS_DATE=2026-09-28
KF098_LIVE_RESULT=FINAL_APPLY_RESULT_PASS
KF098_REAL_BOARD_ACCEPTANCE=KF098_CLOSED_PASS
R4_PRELIVE_CURRENT_RESULT=NO_GO_A6_OPEN
LIVE_T1_MUTATION_THIS_GATE=false
DELETE_OLD_RUNTIME_OR_DATA=false
BROKER_MUTATION=false
HA_MUTATION=false
BOARD_BOOT_OR_RESET=false
SETUP_SECRET_IMPORT=false
PR_MERGE=false
```

## 成功案例的原始证据

1. `docs/development/N3W_KF098_T1_LIVE_CUTOVER_PROGRESS_ALIGNMENT_20260928.md` at main. `MAIN_AT_CUTOVER=88e9d140e5baddba543a961f003d12f7ce563ed2`; exact artifact `ARTIFACT_RUN_ID=36329597775`; successful live `FINAL_APPLY_RESULT=PASS`, `T1_RUNTIME_MUTATION=true`, `ROLLBACK_ATTEMPTED=false`, `MANAGER_EXACT_IMAGE=true`, `MANAGER_PAIRING_AUTO=true`, `MANAGER_MOUNTS_PRESERVED=true`, `MANAGER_HEALTH=PASS`, `BROKER_PRESERVED=true`, `R5_PRESERVED=true`.
2. `docs/development/N3W_KF098_DYNAMIC_DISCOVERY_REAL_TRAFFIC_ACCEPTANCE_CLOSURE_20260928.md` at main. Physical Board B UDP 47111 discovery, TCP 47112 handshake, `/v2/pairing/hello` HTTP response observed; `KF098_ROUTE_STATUS=CLOSED_PASS`. Existing identity / Setup Secret approval boundary remained separate; successful communications did not imply unrestricted re-pair.
3. Immutable successful executor source at commit `88e9d140e5baddba543a961f003d12f7ce563ed2`:
   - `tools/execution_packages/n3w/kf098/t1_live_cutover/executor.py`
   - `tools/execution_packages/n3w/kf098/t1_live_cutover/remote_cutover.py`
   - `tools/execution_packages/n3w/kf098/t1_live_cutover/TASK.md`
   - `tools/execution_packages/n3w/kf098/t1_live_cutover/manifest.json`
4. `infra/n3w-t1/README.md` (main): same Docker Compose project can contain `fc4-homeassistant`, managed from a **different** Compose authority. That HA service is explicitly not an orphan and must not be removed/stopped/recreated by Broker activation; `--remove-orphans` is inappropriate.
5. `docs/adr/0008-n3w-pairing-recovery-simplification-v2.md`: pairing/session recovery is separate from MQTT credential rotation, application-key rotation and system trust rotation. Stable hardware/node identity, credential/ACL authority, Setup Secret proof, replay protection and retirement/revocation semantics are retained.

## Exact source comparison

| 关注点 | KF-098 成功执行器 | 当前 R4（待修复 A6） |
|---|---|---|
| 目标 | 升级已有 Manager，**保留旧业务状态和六挂载** | 以三套新的空白可写源替换 Manager，保留三个只读秘密挂载；原旧 Manager 与旧状态供回退 |
| 本地事务路径 | `remote_cutover.apply()` 统一管理镜像校验、旧 Manager 停止/删除、候选创建/启动、后检查；失败进入同函数的 `rollback()` | `fresh_manager_operator` 触发 systemd oneshot 执行 `fresh_manager_deploy.execute_transaction`；失败依靠 `ExecStopPost` 的 `fresh_manager_recovery`，末尾独立 final check |
| 外层操作预算 | Mac `executor.remote_phase`: 预检 180 秒；**apply 900 秒**；单独 rollback 600 秒 | systemd startup 420 秒，stop-post 120 秒；operator 580 秒；远程预检 120 秒、执行 660 秒；SSH 920 秒 |
| 自动回退 | 新候选出错时，`apply()` 同进程立即调用 `rollback(prestate)`；保存失败/回退分类 | 一次性受监控 service 中断后，`ExecStopPost` 调用独立恢复；可能在不同 systemd 限时阶段被中断 |
| 旧版本保留方式 | 旧镜像标记 + `manager.env` 备份 + 原状态/挂载快照；旧容器被删除，回退是重建 | 旧容器按 exact ID 停放，原三可写状态不删除，必要时原容器恢复名称/运行 |
| 就绪判据 | 有界 `/healthz`（30 秒内轮询），UDP 47111/TCP 47112、Broker ID/restart、R5 防火墙 | R4 增加空白注册/凭据/重放/relay-key 数据验收、六挂载、镜像、Broker ID/restart、服务状态等 |
| 实际证据 | **T1 成功替换且实板通信验收** | 141 synthetic tests PASS，**R4 尚未真实部署**，A6 预检 NO GO |

### KF-098 可借鉴的东西

- **同一事务内完成候选部署和自动回退**，而不是让一个较短的 systemd 超时支配完整回退过程。
- 将预检、部署、人工 rollback 的远程操作预算分别定义；有界超时返回明确 STOP，失败证据留在私有目录。
- 开始改动前以**真实运行中的六挂载容器**为重新创建依据，不采用可能丢掉挂载的过时 Compose Manager 定义。
- 对外宣称 PASS 前必须有实在的 Manager 本地健康/TCP/UDP、Broker 延续与安全配置状态证明。
- Docker 默认表示差异只允许经实证的等价归一化（例如 `OomKillDisable=None/False`），不能放松真正的安全配置。

### KF-098 不可直接复制的东西

- KF-098 的旧容器删除与 `manager.env` 原址改写：R4 原本保留旧容器供**同 ID 原样回退**，现在还要保持三个历史只读秘密挂载和独立新空白业务状态。
- KF-098 的保持原业务数据，不等于 P4 首次配对的 `0/0/0` 和空 relay-key 初始状态。
- KF-098 源码的 900/600 秒**只是已验收历史执行器的外层限时**，不能单靠这些数字证明现有 R4 独立切换、所有 Docker 操作或真实 T1 自动回退的绝对安全。

## 两条候选路线：优先低风险、避免不断加码

**路线 A：在保留现有系统上简化 R4（优先评估）**

1. 精确保留 R4 已经做好的：原 Manager 原容器及三旧 RW 留存、R5 私有回退备份、R2/R3 不可改历史证据、独立三个空 RW、原三 RO 秘密挂载、精确镜像/身份、安全检查及不可重放事务。
2. 先进行 source-only 设计选择：是否以 KF-098 已成功使用的**单进程事务 + 同进程失败回退**代替当前 systemd `ExecStopPost` 对正常异常恢复的主依赖。不能简单复制其 `rm old`，也不能在错误时进行任意 Manager/Broker recreate。
3. 如保留 systemd 作宿主监督层，应证明外层不会在同进程回退正执行时杀进程；真正的崩溃/掉电仍另行依赖受控重启取证/手动恢复，不能声称自动全覆盖。
4. 按成功部署经验分别做源代码测试、timeout/rollback injection、exact artifact/source bind、fresh read-only T1 baseline，再申请单独生产授权。

**路线 B：仅在 A 方案确实不可行或成本不合理时，准备 N3-W 范围内的可审计全新部署**

分级决策，避免把“清空旧业务状态”误解为“清空整台 T1”：

- **B1（首选清洁范围）**：只重建 Manager + 三个 N3-W 可写业务状态源，其实已经接近目前 P4 的“全新首次配对”目标。旧状态离线备份，不主动继承旧注册、凭据、重放和 relay-key。Broker、TLS/CA、Home Assistant、其他 T1 系统服务不动。需要独立首配验收，旧节点身份的冲突和 Broker 旧 ACL 必须先判定；不宣称全面清除历史身份。
- **B2（真正重置 N3-W 业务系统）**：明确批准删除/重建 Manager + Broker 的 N3-W 专属数据、DynSec 账号/ACL、必要的相关身份与密钥来源，可能还需重新完成节点配对与 Home Assistant 关联。必须先验证 Broker TLS/证书信任、与 HA 的关系、网络/防火墙和单一 Compose 项目多份 authority；独立指定保留哪些 CA/private key、哪些系统身份应该轮换。一次“删光 Broker 数据”会使原节点与 HA 可能失去原凭据或状态连续性。
- **B3（整台 T1 操作系统擦除重装）**：只有确定需要解除宿主机底层故障、用户明确逐项确认包括 HA 与其他非温室服务的破坏范围、已验证隔离备份与恢复路径时才可考虑。当前 GitHub 没有证据证明整机重装是必要修复。

无论选择哪一级，**不在源代码比对阶段运行 `docker rm`、`docker volume rm`、`docker system prune`、`--remove-orphans`、清空 `/opt`、删除 Broker CA/key、清除实板 NVS 或复位身份**。绝不把 R2/R3 失败记录、R5 和旧 Manager 数据因“清洁”而无取证删除。历史私有证据可在单独授权、可恢复备份验收之后进入有界保留/销毁流程。

## 推荐下一门，仍然是 SOURCE/DESIGN ONLY

```text
CURRENT_REVIEW_STATUS=COMPARISON_COMPLETE
NEXT_ONE_GATE=N3W_P4_T1_KF098_TRANSACTION_MODEL_REUSE_AND_CLEAN_DEPLOY_B1_B2_FEASIBILITY_DESIGN
GOAL=COMPARE_SIMPLIFIED_SINGLE_PROCESS_ROLLBACK_TO_EXISTING_R4_WITHOUT_WEAKENING_SECURITY
CLEAN_REBUILD_PRIORITY=B1_THEN_B2_IF_JUSTIFIED
FULL_T1_WIPE=B3_NOT_AUTHORIZED
R4_LIVE_AUTHORIZATION=false
T1_MUTATION=false
DELETE_OLD_DATA=false
BOARD_ACCESS=false
BROKER_MUTATION=false
SETUP_SECRET_IMPORT=false
MERGE=false
```

下一步可先做小范围源码设计比对与结构简化判断，给出 A 与 B1/B2 的工序、需保留/销毁数据的精确清单和受影响节点验收清单，再决定是否值得投入 R4 A6 的更多修补。生产环境是否重建以及所有历史凭据是否放弃，均须用户在看到清单后再作明确选择。
