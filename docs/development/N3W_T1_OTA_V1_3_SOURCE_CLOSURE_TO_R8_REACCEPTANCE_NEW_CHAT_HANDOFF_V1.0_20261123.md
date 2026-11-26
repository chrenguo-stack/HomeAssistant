# N3-W T1 Core Stack OTA V1.3 源码闭环 → R8 重新验收新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

DATE=2026-11-23  
PROJECT=温室环境监测系统（ESP32-C6）/ N3-W  
TASK=N3W_T1_OTA_V1_3_SOURCE_CLOSURE_TO_R8_REACCEPTANCE

## 1. 目标与停点

- 任务／交接原因：V1.3 已完成动态 USB 容量设计、源码实现、独立复核、遗留静态容量公式清理和 exact-head CI 闭环；当前对话链过长，转入新会话继续实机前置和 R8 重新验收。完成条件不是“继续旧 R8 即算完成”，而是先安全接管现有 U1、完成实验室 predecessor 10.4 -> 10.0 准备，再用一笔 fresh V1.3 产品路径 10.0 -> 10.4 建立最终 R8 代表性验收。
- 已完成到：
  - OTA 产品架构 authority 已升级为 V1.3；
  - 动态容量准入已实现：target exact size、predecessor 实际 export 测量、quiesced protected-data 同管线 count-only 测量；
  - 固定 generic reserve / whole-transaction static capacity 已退出 V1.3 runtime；
  - 独立复核发现并删除死的 V1.1/R1 `UsbCapacityInputs / assess_capacity / worst_case / removable_media_reserve_bytes` 生产 API，并加入防回归；
  - exact source/test head `51bd2ce8baab2ca0cff4d227765de4583e0f5121` CI 已闭合：19 SUCCESS、0 FAILURE、0 CANCELLED、0 RUNNING、2 expected SKIPPED；
  - spare T1 live 仍停在既有 fresh `U1_PREPARE_REQUESTED`，未部署 V1.3 updater，未推进 U1→U4。
- 当前状态：**源码／测试／CI 可继续；实机写入等待 fresh authorization rebind。** 现有 U1 有效，不重建。旧实机授权绑定旧 source head，不能直接用于 V1.3 artifact。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/824
  - PR base: `review/t1-ota-r8-spare-preflight-20261122` @ `7879981a809cdc2bc51d1aeeb45a7d6336c60214`
- 核对时 main／本任务源码：
  - main: `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`
  - V1.3 executable code head after independent cleanup: `5b45e893181d09deed1f47d588bb1099964e0667`
  - V1.3 exact source/test head: `51bd2ce8baab2ca0cff4d227765de4583e0f5121`
  - 后续 docs-only 对齐提交不得替代上述 executable/source-test authority。
- exact recovery-updater artifact：
  - source head: `51bd2ce8baab2ca0cff4d227765de4583e0f5121`
  - workflow run: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45110450673
  - artifact ID: `14789063554`
  - artifact name: `n3w-t1-ha-recovery-install-51bd2ce8baab2ca0cff4d227765de4583e0f5121`
  - artifact ZIP SHA256: `f7f4c9e874df799e320d823abe89355a4af117de5a686d6fe96398ddf6a964e1`
  - recovery install manifest SHA256: `d0f98dcaa2bdd2747e33b973bf01af622b1fdab1f0d99143a8ee76b3e387d3fc`
  - artifact size: `101709` bytes
- 核心 CI：
  - Manager A-to-B: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45110450626 — SUCCESS；source `253 passed`，包含 V1.3 dynamic-capacity suite；
  - HA target-binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45110450673 — SUCCESS；source `301 passed, 1 skipped`，exact-binding `1 passed`；
  - greenhouse-manager: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45110450636 — SUCCESS；Ruff PASS，`1541 passed, 1 skipped`，附加 slice `8 passed`。
- 证据入口：
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`
  - `docs/development/N3W_T1_OTA_V1_3_DYNAMIC_USB_CAPACITY_SOURCE_ALIGNMENT_20261123.md`
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - PR #824 comment `7091407152`：独立复核、cancelled CI 归因、遗留静态容量 API 清理；
  - PR #824 comment `7090376245`：live U1 `PREPARE_REQUESTED` PASS；
  - PR #824 comment `7087966758`：历史 live authorization，**仅作历史授权证据，不可直接重用到 V1.3 source**。
- live predecessor-preparation target 仍为：
  - current HA: `local/n3w-homeassistant:2026.10.4-5881590f`
  - bounded maintenance target: `local/n3w-homeassistant:2026.10.0-0c73235a`
  - target archive size: `2448553472`
  - target archive SHA256: `e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663`
  - live installed updater remains pre-V1.3, previously observed SHA256 `ffc402f72fe56309b0f108c870230d8288dba740859232b9bc749abc354492b1`；新会话必须 fresh recheck，不可只依赖此历史值。

## 3. 必须继承的结论

- 已证实：
  - V1.3 是当前 OTA 产品设计 authority；V1.2 仅保留历史证据。
  - 产品 USB 要求为 16GB 或更大；runtime machine gate 为 measured usable filesystem >= 14 GiB；该 gate 不是单笔 OTA 空间保证。
  - target、predecessor、protected-data backup 均按各自实际 payload 与当前 free bytes 动态准入；固定 generic reserve 不得代表未来可变 payload。
  - pre-stop U3 容量不足只允许重新测 free，不得 timer 重放写入；同盘释放空间可同事务继续，换更大 USB 只允许用 fresh PREPARE 替换这种 pre-stop capacity-blocked U3。
  - post-stop protected-data 容量不足仍受既有 pre-cutover recovery responsibility 保护，优先恢复/验证 predecessor。
  - 旧 static whole-transaction capacity API 已删除，V1.3 tests 明确阻止其回归。
  - earlier intermediate head 的两个 cancelled workflow 是 PR concurrency `cancel-in-progress: true` 导致的 superseded run，不是测试失败；当前 exact head 同名 workflow 均 SUCCESS。
  - 当前 fresh U1 仍有效；没有 target load、service stop、install authorization claim/consume、USB format、reboot、Broker mutation 或 merge。
  - **R5、R6、R7 不做完整重演。** 历史有效结论继续继承，仅对 V1.3 触及的容量、authority、recovery、status/retry 边界做 targeted regression/read-only recheck。
  - **R8 必须重新验收。** 当前旧 U1 只用于证明 pre-V1.3 transaction 可被 V1.3 updater 安全接管；最终 R8 必须另建 fresh V1.3 产品路径 10.0 -> 10.4 transaction。
- 待确认：
  - spare T1 当前 installed updater SHA、服务健康、U1 phase、candidate spool、target 未加载、authorization claim/consume、USB 原盘绑定与当前 free bytes 均需 fresh read-only rebind；
  - exact recovery artifact `14789063554` 尚未部署；
  - V1.3 final R8 的 near-full/ext4 ENOSPC fault injection 尚未执行；
  - final R8 success、substantive-fault U13B rollback、critical-boundary power-loss resume 和 independent business/protected-data evidence 均待执行。
- 已排除：
  - 旧 `target + predecessor + fixed 1 GiB reserve` U1→U4 command 已退休，**DO NOT RUN**；
  - 不需要从 R5 开始全链重跑；
  - 不得把当前旧 U1 直接声明为最终 V1.3 R8 acceptance；
  - 不得将旧授权 comment `7087966758` 视为 current V1.3 deployment authorization。

## 4. 执行范围与授权

- 可继续：
  - GitHub/source/docs/CI 的只读核对、源码复核、targeted simulation/regression 和归档；
  - spare T1 的 fresh **read-only** rebind，由用户在需要时执行 Terminal 指令并反馈结果；
  - 在 fresh authorization 获得后，按精确 artifact/source binding 继续 bounded V1.3 updater deployment 和 predecessor-preparation transaction。
- 暂停边界：
  - 当前 live mutation 暂停在 `U1_PREPARE_REQUESTED`；
  - **部署 artifact 14789063554 前必须获得新的明确授权**；
  - 继续 U1→U4 前必须确认新 updater 已部署且 transaction/runtime/USB binding fresh PASS；
  - U4 后进入 INSTALL/U5 仍按 predecessor-preparation 的 live gate 单独核对；
  - final R8 fresh 10.0 -> 10.4 transaction 是新的代表性验收边界，不由旧 U1 自动授权；
  - 禁止项继续为：USB format、reboot、power cycle、Broker OTA/mutation、PR #824 merge、production release、无关 T1 mutation，除非用户以后另行明确授权。
- 授权状态：
  - historical authorization: PR #824 comment `7087966758`；
  - historical authorization source head: `044ba31ddeefe7ad7c3e5ed5aedbb409acfd3801`；
  - current V1.3 source/test head: `51bd2ce8baab2ca0cff4d227765de4583e0f5121`；
  - `AUTHORIZATION_SOURCE_DRIFT=true`；
  - `OLD_AUTHORIZATION_REUSE=false`；
  - `FRESH_V1_3_UPDATER_DEPLOYMENT_AUTHORIZATION_REQUIRED=true`；
  - 旧 transaction 的 install authorization 仍未 claimed/consumed；交接本身不授予任何新 live mutation 权限。

## 5. 下一步

- 行动：
  1. 新会话先 fresh rebind repository main、PR #824、current state、exact source/test head `51bd2ce8...` 与 artifact `14789063554`；确认无新的 source drift。
  2. 做 spare T1 **read-only** preflight：健康服务、installed updater SHA、existing U1 exact phase/identity、candidate spool exactness、target 10.0 未加载、authorization false/false、原 USB identity/hash 与当前 free bytes；不得创建/修改 transaction。
  3. read-only PASS 后，向用户请求/确认一笔新的 bounded authorization，必须显式绑定：
     - spare T1；
     - source/test head `51bd2ce8...`；
     - recovery artifact `14789063554`；
     - install-manifest SHA256 `d0f98dcaa2bdd2747e33b973bf01af622b1fdab1f0d99143a8ee76b3e387d3fc`；
     - existing U1 / exact 10.4 -> exact 10.0 predecessor-preparation scope；
     - existing U13B failure recovery；
     - 禁止项保持不变。
  4. 获得授权后，只部署/rebind exact V1.3 recovery updater；**不推进 HA transaction**。立即 read-only 验证 updater bytes/systemd/IPC 与 U1 未变化。
  5. 以现有 U1 做 V1.3 compatibility takeover：签发 fresh V1.3 prepare authority，按动态 target/predecessor capacity gate 继续到 U4 `READY_TO_INSTALL`，在 U4 停止。
  6. 在相应 live gate/授权仍有效且 fresh revalidation PASS 的前提下，继续 maintenance predecessor setup 到健康 exact 10.0；成功终态 U13A，失败使用既有 U13B 自动恢复 exact 10.4。不得把这笔 reverse maintenance transaction 当作 R8 产品升级证据。
  7. R5-R7 只执行 V1.3 影响面的 targeted regression：容量不足 fail-closed、authority binding/stale-authority、pre-cutover restore、status/retry/no-write replay。已由 exact CI 证明的源码级合同不机械重跑；live 只补最小必要 read-only/representative evidence。
  8. 建立 **fresh V1.3 R8 product transaction：exact 10.0 -> exact 10.4**。至少覆盖：
     - normal success / U13A COMMITTED；
     - substantive fault -> automatic U13B rollback；
     - critical-boundary power-loss resume；
     - target space insufficient；
     - predecessor measured-size insufficient；
     - same-USB free-space recovery；
     - larger-USB fresh PREPARE；
     - post-stop protected-data backup insufficient + predecessor recovery；
     - near-full/ext4 ENOSPC fault injection；
     - independent version / affected-function / protected-data / business receive evidence；
     - actual downtime measurement。
  9. R8 完成后再判断 HA single-component OTA 是否正式验收；Broker OTA 继续保持 deferred，不能提前进入。
- 完成条件：
  - V1.3 updater exact artifact 与 live installed bytes 绑定；
  - existing U1 compatibility takeover 有独立证据且 predecessor setup 有明确终态；
  - targeted R5-R7 V1.3 regression 无 blocker；
  - fresh V1.3 R8 同时覆盖 success / rollback / power-loss / dynamic-capacity/ENOSPC，并证明 OTA 后系统回到健康运行状态；
  - 关键证据对齐 `N3W_CURRENT_STATE.md`、index、PR #824 或 successor PR，并满足归档规则。
- 失败／停点：
  - repository/source/artifact drift：STOP，重新绑定；
  - fresh read-only T1 与 handoff 不一致：STOP，不部署；
  - fresh authorization 未明确绑定 V1.3 source/artifact：STOP；
  - capacity gate FAIL：不得越过对应写入边界；
  - post-stop backup/cutover 前异常：优先 predecessor recovery；
  - CI 新 failure：先判断是否局部明确；设计/范围/实机边界变化时 STOP；
  - 同一 exact head CI 最多主动轮询 3 次；到上限记录 run 链接并停止轮询。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
  - 新交接唯一模板：`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4；历史 `NEW_CHAT_HANDOFF_STANDARD.md` 不作为当前新交接 authority。
- 任务资料：
  1. `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md` — V1.3 产品设计 authority；
  2. `docs/development/N3W_T1_OTA_V1_3_DYNAMIC_USB_CAPACITY_SOURCE_ALIGNMENT_20261123.md` — source/CI/artifact/live boundary；
  3. `docs/development/N3W_CURRENT_STATE.md` — 当前 live stop 与 next gate；
  4. `docs/development/N3W_CURRENT_STATE_INDEX.md` — 证据索引；
  5. `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` — 新会话仅按本任务相关 KF/guard 定向读取；
  6. PR #824 comments `7087966758`、`7090376245`、`7090474174`、`7090562285`、`7091407152` — 授权历史、U1 live evidence、V1.2 gap、动态容量决策和独立复核。
- 已归档：
  - source/tests/docs 均在 PR #824 branch；
  - exact CI run 与 artifact identity 已在上述 source-alignment/current-state 文档记录；
  - 本交接文件即本次 continuation authority；初始创建 commit `344d1e8134bd420a9215fa313c00d63bb71ce234`，current-state 绑定 commits `128353bd545d7ec86a7a8cea0e9bb3fd92d2ed73` / `1c9979692f87e4ab5d76df7f61162d2ca3ebb80a`，PR #824 固定归档 comment `7091625137`。
- 未归档重要资料：无。私有 T1 地址、原始 USB UUID、SSH locator 等不写入公开仓库；必要时由私有上下文重新取得，不影响公开交接完整性。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接、`AGENTS.md` 和上列最小任务资料，fresh rebind main / PR #824 / current state / source head `51bd2ce8...` / recovery artifact `14789063554`。第一项只做 spare T1 read-only preflight，不部署、不推进 U1。确认 live state 与交接一致后，再为 V1.3 artifact/source 取得 fresh bounded authorization；旧 authorization 不可直接重用。
