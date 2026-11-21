# N3-W T1 Broker OTA B5 CLOSED_PASS → B6 Target Image/Manifest + Isolated A→B Simulation 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

本文只记录 2026-11-21 Broker OTA B1–B5 的本轮增量和后续继续入口。长期产品行为继续以 T1 Core Stack OTA V1.2、当前 working context/current state 和 fresh exact GitHub evidence 为准。

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”N3-W 的 T1 Core Stack OTA V1.2。Broker OTA 在 HA 路径基础上首次开发，本轮目标是完成 B1–B5 的 Generic V2 Broker 基础能力、持久状态恢复、宿主重启接管和 exact recovery-support package。当前对话上下文较长，因此在 B5 exact CI 全绿并完成 GitHub 状态对齐后切换新会话。
- 已完成到：
  - B1/B2：冻结 `IMAGE_ONLY_V1`，Broker legacy-static → `GH_BROKER_IMAGE` dynamic binding convergence；PR #816 exact head `9c58cc1dada31488d70e1d15b3d263b5f077781c`，13/13 SUCCESS。
  - B3：transaction-bound Broker Recovery Point，保护 `/var/lib/n3wfc4-broker` 平面 regular-file 集合，至少含 `dynamic-security.json` 和 `mosquitto.db`；target 可能写盘后失败会恢复静止快照；PR #817 exact head `b79ec0ffc4f118ccffc94f2bcc328ab2715ab140`，13/13 SUCCESS。
  - B4：`recover-broker-pending` 宿主自动接管；持久 `rollback_source_phase`；stopped Broker 恢复时仍重新获取 certificate-lifecycle guard；Recovery Point 终态 retirement 使用 crash-resumable `.retired` tombstone；PR #818 exact head `b5716c7899755338f4ab1cae62c57dd7495c9924`，14/14 SUCCESS。
  - B5：deterministic exact recovery-support package，包含 `t1-core-updater.pyz + n3wfc4-core-updater-broker-recovery.service + manifest.json`；专用 EXACT workflow 完成 build → upload → re-download → verify → packaged pyz execution；PR #819 executable head `e650f5db373d5cd65fd601c676f3f605998ba132`，14/14 SUCCESS。
  - GitHub 状态对齐已完成到 docs-only head `bca7df8ba8c693187e810eb9e6ef5fff68cedb31`：`N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md`、B5 设计文档均已更新为 B1–B5 CLOSED_PASS。
- 当前状态：**可继续**。B1–B5 无 CI pending；B5 源码与 exact package 已 CLOSED_PASS。当前所有实现仍位于 stacked Draft PR，未合并到 `main`、未安装到 T1、未选择或冻结 Broker target release。新会话直接进入 B6 源码/模拟阶段，不需要再次逐门申请开发授权。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - canonical `main` fresh rebind: `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`
  - V1.2 alignment Draft PR #815: `feat/t1-ota-v1-2-alignment-20261120` @ `9dc2eed89cfb3ccdb9d08c3d3555b61668dcbb1d`
  - B1/B2 Draft PR #816: `feat/t1-broker-ota-b1-b2-20261121` @ `9c58cc1dada31488d70e1d15b3d263b5f077781c`
  - B3 Draft PR #817: `feat/t1-broker-ota-b3-recovery-point-20261121` @ `b79ec0ffc4f118ccffc94f2bcc328ab2715ab140`
  - B4 Draft PR #818: `feat/t1-broker-ota-b4-host-recovery-20261121` @ `b5716c7899755338f4ab1cae62c57dd7495c9924`
  - B5 Draft PR #819: `feat/t1-broker-ota-b5-recovery-support-package-20261121`
- 核对时 main／本任务源码：
  - `MAIN=4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`
  - `B5_EXECUTABLE_SOURCE_HEAD=e650f5db373d5cd65fd601c676f3f605998ba132`
  - `B5_STATE_ALIGNMENT_DOCS_HEAD=bca7df8ba8c693187e810eb9e6ef5fff68cedb31`
  - 新会话必须 fresh rebind PR #819 最新 head，并先证明从 `e650f5d...` 到最新 head 只有文档/交接增量；如果出现 executable/source drift，重新按 exact head 取证，不得沿用本交接的 B5 CI 结论。
- 证据入口：
  - B5 exact workflow run: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44914839856
  - B5 artifact ID: `14711625754`
  - artifact name: `n3w-t1-core-updater-broker-recovery-support`
  - artifact digest: `sha256:77f440f3da068dca61d5f12b44fb704ca29690a16be0a95322024657beadf949`
  - artifact size: `254039` bytes
  - package manifest SHA256: `092af89974e3ce0584933e18a10288386ce5ff8cfddd2c36a19c66e67f142cf2`
  - updater pyz SHA256: `5a13a910cdfdb4d07b23fb7bd8c5bac1bb31a59a310787e4dd2dbf617df7dd4a`
  - recovery unit SHA256: `d5bea0c625edfcf46729170eac30872ae8a11c59fce14c89c6c585d46438ce19`
  - state alignment:
    - https://github.com/chrenguo-stack/HomeAssistant/blob/bca7df8ba8c693187e810eb9e6ef5fff68cedb31/docs/development/N3W_CURRENT_STATE.md
    - https://github.com/chrenguo-stack/HomeAssistant/blob/bca7df8ba8c693187e810eb9e6ef5fff68cedb31/docs/development/N3W_CURRENT_STATE_INDEX.md
    - https://github.com/chrenguo-stack/HomeAssistant/blob/bca7df8ba8c693187e810eb9e6ef5fff68cedb31/docs/development/N3W_T1_BROKER_OTA_V1_0_B5_RECOVERY_SUPPORT_EXACT_PACKAGE_20261121.md

## 3. 必须继承的结论

- 已证实：
  - T1 Core Stack OTA V1.2 继续是产品实现与验收的上位 authority；最终只允许 `SUCCESS` 或 `FAILURE`，status/checker/UI 不能成为恢复引擎的上游依赖。
  - Broker OTA 首版固定为 `IMAGE_ONLY_V1`；复用 `T1_Core_Updater + Generic V2`，不建立 Broker 专用 daemon、第二套事务账本或第二套状态机。
  - Broker runtime-template 可从 legacy-static 原子收敛到 `GH_BROKER_IMAGE`，收敛前后 predecessor effective image 不变，回滚可恢复原 exact static bytes。
  - target Broker 一旦可能启动/写盘，回滚必须恢复 B3 静止 Recovery Point；仅恢复 predecessor image 不足够。
  - Recovery Point 保护当前 Broker writable root `/var/lib/n3wfc4-broker` 的平面 regular-file 集合，至少包括 DynSec 与 persistence 数据；TLS/CA、固定 mosquitto config、Manager/HA 数据不属于该 Recovery Point。
  - 断电/进程退出后宿主可以根据 durable transaction + runtime facts 接管；`rollback_source_phase` 防止“binding 已回 predecessor、但 target 曾写过数据”的断点漏恢复。
  - Broker 恢复即使现场已 stopped，也必须重新进入 Broker quiesce/certificate-lifecycle exclusive lock，重新证明 Manager/HA/Broker writers 全部静止。
  - COMMITTED Broker 事务不能使用旧 Recovery Point 做普通显式 rollback；提交后的合法 DynSec/retained state 不能被旧快照覆盖。
  - terminal Recovery Point cleanup 不得反转已经成立的业务终态；B4 retirement 使用原子 tombstone，可在删除中断后继续清理。
  - B5 exact package 已证明自包含 Broker recovery module，固定路径为 `/opt/n3w-t1-core-updater/t1-core-updater.pyz` 与 `/etc/systemd/system/n3wfc4-core-updater-broker-recovery.service`；安装模拟只允许 daemon-reload + enable，不允许 enable --now/start/stop/restart。
  - B2/B3/B4/B5 exact heads 的 CI 分别为 13/13、13/13、14/14、14/14 SUCCESS。
  - 没有发生 T1 access、systemd live enable、Broker live apply、服务停机、重启、merge 或 release。
- 待确认：
  - **Broker target release/version 尚未冻结。** B6 首先读取现有 Broker build/release authority、当前 image source 和兼容性约束，再确定一个明确 successor。若仓库/上位规划不能唯一决定目标版本且存在真实产品取舍，仅在“target 选择”这一决策点暂停用户确认；其余不依赖版本的 B6 测试框架/manifest contract 可继续。
  - target ARM64 image/archive、portable identity、`gh.n3w-t1-core-updater-target/2` manifest、compatibility evidence 尚未建立。
  - isolated Mosquitto A→B success/rollback/process-death/restart deterministic simulation 尚未完成。
  - B5 support package 尚未安装/enable 到任何 T1；真实 boot takeover 尚无 Broker OTA 实机证据。
- 已排除：
  - 不为 Broker 增加 USB 路径、TLS/CA migration、DynSec schema migration 或独立在线升级服务。
  - 不用“当前 binding 是 predecessor”替代 target-write 历史事实；必须保留并使用 `rollback_source_phase`。
  - 不用 stale COMMITTED Recovery Point 回退已提交 Broker。
  - 不用直接 recursive delete 作为终态 Recovery Point 生命周期；已改为验证 → 原子 rename tombstone → 删除。
  - 不把 B5 recovery-support package 当作 Broker target package；B5 不含 target Broker image。

## 4. 执行范围与授权

- 可继续：
  - 用户已明确要求后续任务链路写入交接并在新会话继续推进。
  - 在不触及下面暂停边界的前提下，可连续执行 B6/B7 的源码开发、仓库复核、确定性模拟、隔离 Docker/Mosquitto 测试、CI、独立源码复核、GitHub 分支/PR/文档归档；无需逐门申请。
  - CI 若失败且原因明确、局部、无歧义、不会扩大范围，直接修复并验证。对同一轮 CI 主动轮询最多 3 次，未终态则停止轮询并给运行链接。
- 暂停边界：
  - 任何真实/备用 T1 访问，即使只读，先进入单独 B8 read-only preflight 边界并向用户给出访问/Terminal 执行方式或取得明确 T1 只读授权。
  - 在 T1 安装 recovery-support package、`systemctl enable`、Broker image load/apply、服务 stop/start/restart、真实 Broker downtime、真实回滚、重启/断电试验均为 live/physical mutation，必须在对应 B9/B10 边界取得明确授权。
  - 重要合并、stacked PR 合并、主分支整合、发布和部署必须单独授权。
  - 不得复用 2026-11-05/06 或更早 HA/T1 一次性授权；历史授权不携带到 Broker OTA。
- 授权状态：
  - `SOURCE_DEVELOPMENT_CHAIN_AUTHORIZED=true`
  - `DETERMINISTIC_SIMULATION_AUTHORIZED=true`
  - `GITHUB_ARCHIVE_AUTHORIZED=true`
  - `T1_READONLY_AUTHORIZED=false`
  - `T1_MUTATION_AUTHORIZED=false`
  - `BROKER_LIVE_APPLY_AUTHORIZED=false`
  - `REBOOT_POWER_LOSS_TEST_AUTHORIZED=false`
  - `MERGE_AUTHORIZED=false`
  - `RELEASE_AUTHORIZED=false`

## 5. 下一步

- 行动：

  **B6 — Broker target image / target manifest / isolated A→B deterministic package simulation**
  1. fresh rebind `main`、PR #815–#819、B5 executable head 和 docs-only handoff head；确认 B5 之后没有 executable drift。
  2. 读取当前 Broker image build/source、production mosquitto config、DynSec/persistence mounts、Generic V2 target schema 与 B1–B5 设计。
  3. 冻结一个明确的 Broker successor：source/version、linux/arm64 image identity、exact archive SHA256、predecessor image、compatibility evidence。若目标版本存在实质性产品取舍且无上位 authority，暂停该决策而不是猜测。
  4. 建立 Broker target manifest 和 exact artifact/package binding；不得修改 TLS/CA、固定 mosquitto config 或 DynSec schema。
  5. 在隔离环境执行真实 Mosquitto A→B deterministic simulation，至少覆盖：
     - 正常 target activation + commit；
     - target start/health failure 自动恢复 predecessor image + Recovery Point；
     - target 已写 DynSec/persistence 后失败；
     - process death / updater restart during activation and rollback；
     - binding 已回 predecessor、服务仍 stopped 的断点；
     - certificate lifecycle lock contention；
     - Recovery Point tamper/space rejection；
     - commit 后 stale rollback 拒绝；
     - terminal cleanup failure不触发第二次业务回滚；
     - Manager/HA peer identity/runtime contract 不漂移。
  6. 归档 exact artifact/manifest/simulation evidence，并保持 T1 access=false。

  **B7 — 独立源码复核 + exact candidate/CI closure**
  1. 对 B2–B6 做独立复核，重点检查 Generic V2 事务阶段、Recovery Point 原子性、boot takeover、证书锁、目标 artifact/manifest 绑定、无第二状态机及 fail-closed 路径。
  2. 对 B3 已知的两个复核点重新判断是否需要 source hardening：source scan→copy 的 opened-fd metadata race；Recovery Point source-root metadata hash/restore invariant。
  3. 形成用于备用 T1 的 exact candidate package/evidence set；artifact 必须可重新下载复验并与 exact source head 绑定。
  4. 全部适用 CI 通过后关闭 B7。
  5. B7 完成后**停止在真实 T1 之前**，除非用户已在新会话明确进入 B8。

  **B8 — 备用 T1 只读预检（明确暂停边界）**
  - 需要用户/T1 只读授权或由用户执行给出的 Terminal 指令。
  - 只读核对实际 Broker predecessor image/platform、binding mode、运行健康、state root shape/size、磁盘余量、certificate-lifecycle lock/unit、target image prestate、B5 support-package 安装前条件、恢复路径可用性。
  - 不安装、不 enable、不 stop service、不 load target image。

  **B9 — 备用 T1 recovery-support 安装 + Broker A→B 代表性验收（单独写入授权）**
  - 先安装 exact B5/B7 recovery support，并验证只 enable、不意外 start。
  - 再按独立一次性授权执行正常 Broker A→B；核对目标版本、Broker TLS/DynSec/persistence、Manager/HA 重新认证和受影响业务。
  - 用另一笔独立授权验证一个实质 target failure 自动回滚；不得把第一次授权重放为第二次测试。

  **B10 — 重启/断电恢复代表性实机验收（单独物理授权）**
  - 在已冻结的关键断点验证 host reboot/power-loss continuation，重点覆盖 target 已可能写盘以及 rollback 中断。
  - 只要求代表性高价值断点；不为了“全枚举”制造过度实机测试。

  **B11 — Broker standalone → Core Stack 多组件整合 / 产品级验收**
  - Broker standalone acceptance 通过后，再接入 V1.2 whole-release commit。
  - 验证多组件最后一项失败时恢复为完整前代组合；所有适用组件通过后才持久提交新组合。
  - 汇总 V1.2 三问：版本正确、受影响功能恢复、受保护数据保留。

  **B12 — 合并与发布准备**
  - fresh rebind stacked PR lineage，整理/squash 方案、main 目标、release artifact 与验收证据。
  - 到此必须取得明确 merge/release 授权；未授权不得合并 #815–#819 或后续 PR，不得部署/发布。

- 完成条件：
  - B6/B7：Broker target artifact/manifest 已精确冻结，isolated A→B 正常与回滚/中断路径有确定性证据，candidate package/source/CI exact-bound，GitHub 归档完整。
  - B8：只读实机现场与候选材料无漂移，明确 B9 所需目标、回滚入口和授权。
  - B9/B10：代表性成功、失败自动恢复、重启/断电续办均有真实业务与数据证据。
  - B11：Standalone Broker 证据可被 whole-release commit 复用，且多组件失败/成功终态符合 V1.2。
  - B12：main、拟发布工件和验收证据精确对应。
- 失败／停点：
  - source/CI 小问题：局部修复、重新验证、更新 exact head。
  - 任何无法安全分类的 transaction/runtime state、Recovery Point 身份/完整性不明、target artifact 漂移、TLS/CA/DynSec 兼容性需要迁移、或 target release 选择出现实质产品取舍：停止受影响步骤并记录最小恢复/决策入口。
  - B8/B9/B10/B12 未授权时不得跨越；停止不等于取消已运行的远端 CI。

## 6. 必读定位与归档

- 仓库规则：
  - 根目录 `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - 如 B6 新建模块或重构模块，补读 `docs/development/module-lifecycle-rules.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
- 任务资料：
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`：重点第 1、3、5、6、9、10、11 节与附录 A。
  - `docs/development/N3W_CURRENT_STATE.md` 与 `N3W_CURRENT_STATE_INDEX.md`：先读顶部 2026-11-21 Broker B1–B5 条目。
  - `docs/development/N3W_T1_BROKER_OTA_V1_0_B1_DESIGN_AND_B2_DYNAMIC_BINDING_20261121.md`
  - `docs/development/N3W_T1_BROKER_OTA_V1_0_B3_PERSISTENT_STATE_RECOVERY_POINT_20261121.md`
  - `docs/development/N3W_T1_BROKER_OTA_V1_0_B4_HOST_RECOVERY_AND_RECOVERY_POINT_LIFECYCLE_20261121.md`
  - `docs/development/N3W_T1_BROKER_OTA_V1_0_B5_RECOVERY_SUPPORT_EXACT_PACKAGE_20261121.md`
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：B6/B7 至少复核 KF-100 certificate-lifecycle 共享锁；遇到新 false oracle/恢复缺陷时按规则新增或更新 KF。
  - 源码重点：`tools/n3w_t1_core_updater_v2*.py`、`tools/n3w_t1_core_updater_host.py`、`tools/n3w_t1_core_updater_broker_recovery.py`、`tools/n3w_t1_core_updater_broker_support.py`、`infra/n3w-t1/production/docker-compose.fresh.yml`、Broker mosquitto config/build source。
- 已归档：
  - B5 source/package exact authority: https://github.com/chrenguo-stack/HomeAssistant/tree/e650f5db373d5cd65fd601c676f3f605998ba132
  - B1–B5 state alignment: https://github.com/chrenguo-stack/HomeAssistant/commit/bca7df8ba8c693187e810eb9e6ef5fff68cedb31
  - PR #819: https://github.com/chrenguo-stack/HomeAssistant/pull/819
  - B5 exact CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44914839856
- 未归档重要资料：无。当前对话中 continuation-critical 的 B1–B5 状态、CI、artifact binding、设计结论、授权边界和后续任务链路已写入 GitHub。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=not-required
PRIVATE_RAW_EVIDENCE_PRESENT=false
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=not-required
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=true
UNARCHIVED_CRITICAL_KNOWLEDGE=0
B5_EXECUTABLE_HEAD=e650f5db373d5cd65fd601c676f3f605998ba132
STATE_ALIGNMENT_HEAD=bca7df8ba8c693187e810eb9e6ef5fff68cedb31
REMOTE_EXACT_BINDING=PASS
LOCAL_WORKTREE_AUDIT=NOT_APPLICABLE:GITHUB_API_WORKFLOW
NEXT_SAFE_ENTRY_POINT=N3W_T1_BROKER_OTA_B6_TARGET_IMAGE_MANIFEST_AND_ISOLATED_A_TO_B_SIMULATION_20261121_01
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。fresh rebind `main`、PR #815–#819 和本交接所在最新 docs-only head，确认 `e650f5db...` 之后没有 executable drift；然后直接进入 B6 Broker target image/target manifest + isolated Mosquitto A→B deterministic package simulation。在明确授权范围内连续推进源码、测试、CI、独立复核和 GitHub 归档；到 B8 真实 T1 只读边界、任何 live mutation、重启/断电、合并或发布边界时停止并请求相应授权。
