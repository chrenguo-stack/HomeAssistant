# N3-W T1 Core Stack OTA V1.2 架构权威 → main 合并新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

DATE=2026-11-20
PROJECT=温室环境监测系统（ESP32-C6）/ N3-W
TASK=N3W_T1_CORE_STACK_OTA_V1_2_ARCHITECTURE_AUTHORITY_MAIN_ALIGNMENT_AND_MERGE

## 1. 目标与停点

- 任务／交接原因：
  - 已确认 T1_Core_Stack OTA 最新产品架构版本是 **V1.2**，不是 V1.4；V1.4 是新会话交接模板版本。
  - V1.2 已于 2026-11-19 定稿，但尚未进入 `main`。
  - 用户已同意：先把 V1.2 架构权威以 docs-only 方式正式确立到 `main`，再开始旧 OTA 分支工程收敛和 V1.2 代码对齐。
  - 本交接用于切换到干净新对话执行上述第一门。
- 已完成到：
  - fresh 核对 `main` 与架构分支。
  - 已证明架构分支相对 `main`：`ahead_by=6`、`behind_by=0`，当前仅新增 V1.1.4 与 V1.2 两个架构文档，没有执行源码、CI、Docker/systemd、T1 或 USB 运行配置变更。
  - 已确认 V1.2 文档中不存在旧 `Phase-A` / `Phase-B` 产品阶段命名；V1.2 明确采用实际受影响功能验收、可观察进展、有限重试/停止条件，并明确“不对用户承诺统一的升级或恢复分钟数”。
  - 已确认旧 OTA 开发栈 #807 → #809 → #810/#811 仍为 OPEN/DRAFT/UNMERGED，暂不合并。
- 当前状态：
  - `READY_FOR_V1_2_ARCHITECTURE_AUTHORITY_MAIN_ALIGNMENT_AND_MERGE`
  - 尚未创建本轮 V1.2 authority alignment PR。
  - 尚未修改 `N3W_CURRENT_STATE.md` / `N3W_PROJECT_WORKING_CONTEXT.md`。
  - 尚未合并 V1.2 到 `main`。

## 2. 代码与证据

- 仓库：
  - `chrenguo-stack/HomeAssistant`
- 核对时 `main`：
  - `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - commit: `Merge pull request #803 ... adopt the N3-W V1.4 handoff template`
- V1.2 架构分支：
  - `docs/t1-core-stack-ota-architecture-v1-1-20261119`
  - 架构源码 head（本交接提交之前）：`480afb109de59477b11f6d1cdf794f656eb39805`
  - commit: `docs: adopt impact-based field acceptance in T1 Core Stack OTA V1.2`
- compare（交接创建前）：
  - `BASE=main@3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - `HEAD=480afb109de59477b11f6d1cdf794f656eb39805`
  - `AHEAD_BY=6`
  - `BEHIND_BY=0`
  - changed files:
    1. `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.1.4_20261119.md`
    2. `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`
- V1.2 固定证据：
  - path: `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`
  - blob: `82479d9723aace8555df0f24550c738b1074c977`
  - fixed URL: https://github.com/chrenguo-stack/HomeAssistant/blob/480afb109de59477b11f6d1cdf794f656eb39805/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md
- V1.1.4 直接前版：
  - path: `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.1.4_20261119.md`
  - blob: `3dd6b790d1792f1f4508f7d038205b2615892515`
- 当前 `main` 中旧总体架构：
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md`
  - blob: `1d923e4db39aa783a70a85fa7c84e791fc0eb80a`
- 正式 handoff 模板：
  - `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`
  - version: `1.4`
  - blob: `885fd63131e80936e5e1fe907378be08a0060f12`

旧 OTA 代码栈（本门不得合并）：

| PR | 状态 | head | 关系 |
|---|---|---|---|
| #807 | OPEN / DRAFT / UNMERGED | `7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c` | 旧 HA OTA 长期开发栈，350 files / 865 commits（先前核对） |
| #809 | OPEN / DRAFT / UNMERGED | `06332c58de850c590da83e0971d7576291f371b2` | 基于 #807；KF-168 USB diagnostics |
| #810 | OPEN / DRAFT / UNMERGED | `4abebaa61c1db0be41a724c45263e26ac15eb06e` | 基于 #809；永久 IPC isolation |
| #811 | OPEN / DRAFT / UNMERGED | `6642c7202e0757f2e3527b13e32085cff1e54859` | 基于 #810；install/rollback readiness repair |

## 3. 必须继承的结论

### 已证实

1. **最新 OTA 产品架构权威是 V1.2。**
   - V1.2 明确以 V1.1.4 为直接基线。
   - “V1.4”只对应新会话交接模板，不是 OTA 架构版本。
2. **V1.2 尚未进入 `main`。**
   - `main` 中存在 V1.0，但不存在 V1.2 文件。
3. **V1.2 架构分支当前是 docs-only。**
   - 对 `main` 0 behind，原始 architecture delta 只有两个架构文档。
4. **V1.2 的产品语义已经替代旧 Phase-A / Phase-B 体系。**
   - V1.2 文档没有 `Phase-A` / `Phase-B` 命名。
   - OTA 最终结果只有 `SUCCESS` / `FAILURE`。
   - 过程可显示准备、安装、验证、恢复等进度，但不形成第三种终态。
   - 每个动作使用可观察进展、有限重试和停止条件；慢速但有有效进展时继续。
   - 产品不对用户承诺统一的升级或恢复分钟数；实际停机时长保留为实验室/性能改进数据。
5. **旧路线中的底层能力不能简单丢弃。**
   - U13B 自动回滚、USB 恢复材料、持久事务、受保护数据恢复、KF-168 diagnostics、IPC isolation、bounded readiness 等应在后续 V1.2 repository convergence 中分类为 KEEP / ADAPT / ARCHIVE_ONLY / DROP，而不是先整体合并或整体删除。
6. **当前应先建立架构权威，再做代码收敛。**
   - 不应先合并 #807～#811。
   - 不应直接在 #811 上继续叠加 V1.2 新实现。

### 待确认

- 新会话开始后 fresh rebind：
  - `main`
  - `docs/t1-core-stack-ota-architecture-v1-1-20261119`
  - #807 / #809 / #810 / #811
  - 是否已有与该架构分支关联的新 PR。
- 交接文件提交后架构分支 head 会比 `480afb...` 多一个 docs-only handoff commit；以 fresh GitHub evidence 为准。
- 合并前需要确认本次 authority alignment delta 仍然严格 docs-only。

### 已排除

- 不采用“先把 #807→#811 全部合并 main，再做 V1.2”的路线。
- 不继续为旧 `PHASE_A_OVERALL=PASS` 补开发。
- 不开发旧 `PHASE_B_FRESH_CONTINUOUS_DOWNTIME_ACCEPTANCE`。
- 不把固定“≤15 分钟”作为 V1.2 OTA Core Gate。
- 不把 V1.2 文档合并误表述为“V1.2 源码已经实现”或“真实 T1 已部署 V1.2”。

## 4. 执行范围与授权

- 可继续：
  - 用户已明确同意上一轮方案：**先把 V1.2 架构权威合并进 `main`**。
  - 允许在 V1.2 架构分支上做必要的 docs-only authority alignment：
    - 更新 `N3W_CURRENT_STATE.md`
    - 更新 `N3W_PROJECT_WORKING_CONTEXT.md`
    - 必要时更新 `N3W_CURRENT_STATE_INDEX.md`
    - 建立/更新 docs-only PR
    - 执行适用 CI / public-safety / docs checks
    - 在 exact scope、CI 与复核通过后合并该 V1.2 架构权威 PR 到 `main`
    - 归档 merge 后 exact authority
- 建议明确写入的状态：
  ```text
  CURRENT_T1_CORE_STACK_OTA_ARCHITECTURE=
  docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md

  ARCHITECTURE_VERSION=V1.2
  ARCHITECTURE_STATUS=PRODUCT_ARCHITECTURE_AUTHORITY
  ARCHITECTURE_AUTHORITY=V1.2
  IMPLEMENTATION_STATUS=NOT_YET_ALIGNED
  LIVE_RUNTIME_ALIGNED_TO_V1_2=false
  ```
- 暂停边界／禁止项：
  - `T1_ACCESS=false`
  - `T1_MUTATION=false`
  - `REAL_USB_MUTATION=false`
  - `DOCKER_RUNTIME_MUTATION=false`
  - `SERVICE_RESTART=false`
  - `EXECUTABLE_OTA_SOURCE_MUTATION=false`
  - 不合并、不关闭 #807 / #809 / #810 / #811。
  - 不开始永久 IPC isolation 的实机部署。
  - 不进入旧 Phase-A / Phase-B。
  - 不把旧的一次性授权重新认领或 replay。
- 授权状态：
  ```text
  AUTHORIZATION_SOURCE=USER_EXPLICIT_APPROVAL_2026-11-20
  AUTHORIZED_TASK=V1_2_ARCHITECTURE_AUTHORITY_MAIN_ALIGNMENT_AND_MERGE
  DOCS_ONLY_MUTATION=true
  PR_CREATE_OR_UPDATE=true
  APPLICABLE_CI=true
  MERGE_TO_MAIN=true
  OLD_OTA_STACK_MERGE=false
  LIVE_T1_AUTHORIZATION=false
  ```

## 5. 下一步

- 行动：
  1. fresh rebind `main`、V1.2 architecture branch、#807/#809/#810/#811。
  2. 读取 V1.2，重点第 1、3、5、6、9、10、11 节。
  3. 读取当前 `N3W_PROJECT_WORKING_CONTEXT.md`、`N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md` 的 OTA 相关部分。
  4. 在架构分支补最小 docs-only authority alignment，明确：
     - V1.2 已是产品架构权威；
     - 当前 executable/runtime 尚未对齐 V1.2；
     - 旧 OTA 栈保持独立待分类。
  5. 确认 compare 仍严格 docs-only。
  6. 创建或更新仅用于 V1.2 authority merge 的 PR。
  7. 跑适用 CI；若 CI 等待，遵循项目三次轮询上限。
  8. 复核无 executable/T1/runtime drift 后合并 `main`。
  9. fresh rebind 合并后的 `main`，归档 exact merge head 与 V1.2 authority。
  10. **在该 merge gate 完成后停止本门。**
- 完成条件：
  ```text
  V1_2_ARCHITECTURE_AUTHORITY_IN_MAIN=true
  ARCHITECTURE_VERSION=V1.2
  IMPLEMENTATION_STATUS=NOT_YET_ALIGNED
  DOCS_ONLY_SCOPE_VERIFIED=true
  APPLICABLE_CI=PASS
  MAIN_MERGE=PASS
  OLD_OTA_STACK_UNCHANGED=true
  T1_ACCESS=false
  T1_MUTATION=false
  ```
- 失败／停点：
  - 若 architecture branch 出现 executable/runtime 文件漂移：STOP，不合并，先隔离 docs-only delta。
  - 若 `main` 已发生会改变 V1.2 语义的架构更新：STOP，先做冲突复核。
  - 若 CI 失败且属于局部、明确、docs-only 小问题，可直接修复并重新验证；若涉及架构语义选择或范围扩大，停止并说明。
  - 合并完成后，下一门才是：
    `N3W_T1_OTA_V1_2_PRE_ALIGNMENT_REPOSITORY_CONVERGENCE`
    用于 #807～#811 的 KEEP / ADAPT / ARCHIVE_ONLY / DROP 分类。

## 6. 必读定位与归档

- 仓库规则：
  - 根目录适用 `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
- 任务资料：
  1. `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`
     - 必读：第 1、3、5、6、9、10、11 节。
     - 用途：本轮唯一最新 OTA 架构语义。
  2. `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.1.4_20261119.md`
     - 按需读取；用于追踪 V1.2 直接前版。
  3. `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`
     - 必读 OTA authority、minimum new-chat read set。
  4. `docs/development/N3W_CURRENT_STATE.md`
  5. `docs/development/N3W_CURRENT_STATE_INDEX.md`
  6. `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
     - 本门只定位与 OTA authority/旧栈相关条目；不需要展开无关 KF。
  7. 旧 OTA PR：#807、#809、#810、#811
     - 本门只 fresh rebind 状态，不改代码、不合并。
- 已归档：
  - V1.2 fixed architecture:
    https://github.com/chrenguo-stack/HomeAssistant/blob/480afb109de59477b11f6d1cdf794f656eb39805/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md
  - Handoff template V1.4:
    https://github.com/chrenguo-stack/HomeAssistant/blob/3e7faf258d670c9eaf3be6ede9bbb02df2ac009d/docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
- 未归档重要资料：
  - 本交接提交后应以其 GitHub fixed commit 作为新会话入口。
  - 无需要保留在聊天中的私有 T1 locator、凭据或设备身份。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

NEXT_ONE_GATE=
N3W_T1_CORE_STACK_OTA_V1_2_ARCHITECTURE_AUTHORITY_MAIN_ALIGNMENT_AND_MERGE

NEXT_AFTER_GATE=
N3W_T1_OTA_V1_2_PRE_ALIGNMENT_REPOSITORY_CONVERGENCE
```

新会话启动语：

阅读本交接和适用仓库指令，按必读定位恢复任务。fresh rebind `main`、V1.2 architecture branch、#807/#809/#810/#811。只执行 `N3W_T1_CORE_STACK_OTA_V1_2_ARCHITECTURE_AUTHORITY_MAIN_ALIGNMENT_AND_MERGE`：补最小 docs-only authority alignment，验证范围与适用 CI，通过后将 V1.2 架构权威合并进 `main` 并归档 exact merge head。不得修改 executable OTA source、不得访问或修改 T1/USB/runtime、不得合并或关闭 #807～#811。合并完成后停止本门。
