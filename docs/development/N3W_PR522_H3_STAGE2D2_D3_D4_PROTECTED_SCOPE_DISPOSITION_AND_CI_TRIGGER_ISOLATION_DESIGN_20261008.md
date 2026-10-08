# N3-W PR #522：H3 Stage 2D-2/3/4 受保护范围失败归因与 CI 触发隔离设计（2026-10-08）

```text
TASK=N3W_PR522_POST_PUBLIC_SAFETY_FIX_CI_REVIEW_AND_H3_PROTECTED_SCOPE_DISPOSITION_DESIGN_20261008_01
RESULT=SOURCE_ONLY_DESIGN_COMPLETE_NOT_IMPLEMENTED
EVIDENCE=EXACT_GITHUB_SOURCE_AND_CI
PR522_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
PR522_BASE_SHA=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR522_BASE_BRANCH=fix/n3w-production-relay-discovery-full-channel-fallback-v1-source-repair-20260924
PR522_STATE=OPEN_DRAFT_UNMERGED
PR523_HEAD=4c943f072230a47de9f7a7a535a7b5ccacfd91e3
PR523_CI=13_OF_13_PASS
PR523_STATE=OPEN_DRAFT_UNMERGED
H3_BOUNDARY_GUARDS_MODIFIED=false
WORKFLOW_TRIGGER_POLICY_MODIFIED=false
H3_REQUIRED_CHECKS_POLICY_READ=NOT_YET_VERIFIED
SOURCE_PR_MERGE=false
PR522_REBASE_OR_RESET=false
BOARD_ACCESS=false
T1_ACCESS=false
REAL_SECRET_IMPORT=false
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
STOP=true
```

## 1. 问题定性

PR #522 当前与上游 PR #474 的分支相比，累计有 **141 个变化文件**。其中实际修改的共享 RC2 配置为：

- `firmware/esphome_rc/f1_0_rc2/packages/core.yml`
- `firmware/esphome_rc/f1_0_rc2/packages/display.yml`
- `firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml`

**没有改动 H3 Stage 2D-2、2D-3、2D-4 任一专属源码/实验文件或对应阶段验收脚本。** 三条历史 H3 CI 的 `pull_request.paths` 均有宽泛触发规则 `firmware/esphome_rc/f1_0_rc2/packages/**`，因此当前非 H3 产品开发也触发旧阶段范围检查。GitHub pull_request 的路径匹配作用于相对 base 分支的 PR 变更集合，不只最近一次 commit 的增量。

H3 Stage 2D-2:
- Workflow `.github/workflows/h3-n2-stage2d2-candidate-mqtt-validator-ci.yml`，blob `769ca390287f592fe1319e4f8ebd22479a1f850f`
- Gate `tools/h3_n2_stage2d2_candidate_mqtt_boundary_gate_20260721_v50.py`，blob `427c7889e97175d25cc75ff544c0bd25122c7048`
- `changed_paths()` 调用 `git diff --name-only origin/$GITHUB_BASE_REF...HEAD`；`ALLOWED_CHANGED_PREFIXES` 仅允许 Stage 2D-2 指定文件及实验目录，不接受 P4 的 `packages/core.yml` / `display.yml` / `n3w_product_transport.yml`。
- 对非 H3 开发，这是范围失败，不等于该模块运行测试失败。

H3 Stage 2D-3:
- Workflow `.github/workflows/h3-n2-stage2d3-activation-transaction-ci.yml`，blob `1c525666ffed02006e0ade6ef48c1e49b65c27d7`
- Gate `tools/h3_n2_stage2d3_activation_boundary_gate_20260721_v51.py`，blob `675c0c53f8a91096a3df2ae89ccecf91082e1997`
- Gate 的 `changed_paths()` 固定计算 `git merge-base HEAD origin/main` 后比较 `base...HEAD`，与 PR #522 的真正 base PR #474 修复分支不一致。
- `unexpected = changed - REQUIRED_PATHS`；`missing = REQUIRED_PATHS - changed`，是专用于当年 *恰好完成 H3 Stage 2D-3 文件集合* 的源范围验收，而不是所有后继产品 PR 的一般回归测试。
- `PROTECTED_PATHS` 特意包含 `core.yml`、`display.yml`；P4 产品版主动改动这些文件而历史 H3 专项不得改动。保留此差异，不准扩大 `REQUIRED_PATHS` 来强行放行。

H3 Stage 2D-4:
- Workflow `.github/workflows/h3-n2-stage2d4-profile-lifecycle-integration-ci.yml`，blob `09d51b2263be97c45ed1afe81235661efcff07d3`
- Gate `tools/h3_n2_stage2d4_profile_lifecycle_boundary_gate_20260721_v52.py`，blob `df027e6c7b8564bf392bb6d648d1a1c02f701d5f`
- 同样以 `origin/main` 为历史差异基线，并要求严格限定 `REQUIRED_PATHS`；`PROTECTED_PATHS` 不仅禁止改动 `core.yml`、`display.yml`，还保护旧配对持久化/候选 MQTT 等源码。
- 不能因 #522 完成了新产品二维码功能，就重新解释旧阶段“不得触碰受保护文件”的原有验收含义。

最近一次相关 CI 仍真实 FAIL：
- D2 run `37781461526`
- D3 run `37781461356`
- D4 run `37781461616`

失败属于 **STAGE_SPECIFIC_SCOPE_GUARD_REJECTION**；不得伪称成功、删除失败历史或忽略其他可能尚未读到的故障。

## 2. 现有产品保护与空白

当共享 RC2 配置变化时，以下**不同于历史 H3 的产品检查**适用：

- `.github/workflows/f1-0-rc2-ci.yml`，blob `691217fddfebe22d3aafe3917e64b1d3a8b15ecc`：`pull_request.paths` 包含 `firmware/esphome_rc/f1_0_rc2/**`，运行 RC2 配置验证与固件编译。
- `.github/workflows/n3w-auto-safe-fallback-production-core-convergence-ci.yml`，blob `60aa945c7bdd60c5cfbd65243e515ac8a4183b96`：显式监听 `packages/core.yml`、`packages/display.yml` 和 `n3w_product_transport.yml`，运行 N3-W 生产合同、KF-050 首次配对启动回归、完整 Setup Secret 首次配对源码合同、Manager 配对 CLI 试验以及完整 RC2 产品配置/编译。
- `tests/n3w_production/test_first_pair_setup_secret_handoff_contract.py`，blob `e01bc9f34521e3563c132779943f68fcfefd1ff2`：实读 `core.yml`、`display.yml`、`n3w_product_transport.yml`，断言二维码状态、扫码交接与秘密导入接口之间的合同。
- 公共仓库安全扫描不放宽：PR #522 head `58107b36...` run `37781461448` SUCCESS；R3 源码模拟 run `37781461535` SUCCESS。

这些产品测试与旧 H3 保护**目标不同**：产品测试允许经过审查的生产配置升级，旧 H3 阶段源范围门故意不允许该历史阶段 PR 触碰生产配置。因此不能把新产品合同测试说成旧 H3 的同等通过证明。必须由后继受保护配置的产品合同接管当前产品变更验收，并保留原 H3 旧阶段限制。

截至本设计核验时，最新 HEAD 的 N3-W 生产收敛与完整 RC2 固件 CI 有运行未终结的记录；**此文件不宣称新 HEAD 的全量产品 CI 已通过**。首次物理配对、Setup Secret 实际导入和 Manager COMMIT 均未授权或发生。

## 3. 方案比较与选择

### 方案 A（推荐）——旧 H3 只在旧 H3 专属源码改变时触发；P4 用生产合同验收

提议在一个**与 PR #522 分离、以 PR #474 的原始上游分支为目标**的极小 CI 源修补 PR 中：

1. 仅从 Stage 2D-2、2D-3、2D-4 三个 workflow 的 `pull_request.paths` 与 `push.paths` 同时移除广泛的 `firmware/esphome_rc/f1_0_rc2/packages/**`。
2. **保留所有 H3 专属源码、阶段单板 lab 配置、历史协议文档和工作流本身的精确路径触发条件**；若未来有 H3 Stage 2D-N 专属修改，仍触发该阶段的原始 source boundary gate、host fault-matrix 和 ESP32-C6 lab 编译。
3. **完全不修改** H3 三个 Python source boundary gate、其 `REQUIRED_PATHS`、`ALLOWED_CHANGED_PREFIXES`、`PROTECTED_PATHS` 或两阶段实验的成功判定条件；任何 H3 阶段范围内 PR 顺带修改受保护生产配置，仍必须 FAIL。
4. 不降低生产产品检查：明确验证上节两条当前有效 RC2/N3-W 产品编译与首次配对合同；保留公共仓库安全扫描；若独立复核发现这些产品检查未守住具体保护契约，先补产品级合同而不是先删除 H3 触发条件。
5. 检查 PR #522 与 PR #523 的 base/head 和仓库分支保护的**实际 required check 名称**，确认移除旧 H3 触发后不会导致 required status check 永远 pending。若这些 H3 工作流属于 required checks，先提交并审核替代检查名字与过渡策略，再允许调整；不可通过无条件 success、skip 或屏蔽失败来“造绿”。
6. 需要单独授权才能合入上游分支 PR #474 的 head。再采用**保留历史的非强制集成**将更新的上游引入 PR #522，确认三条 H3 的触发判断在真正 PR 比较范围下不再匹配，随后对新 HEAD 的 RC2/N3-W/公共安全 CI 进行全量复核。**新规则不追认旧失败，更不能清除历史日志**。

优势：旧 H3 source gate 原封不动，产品配置由当前产品 CI 负责；修改规模只有三个 workflow 的两个触发段，且不会破坏 PR #522 固件冻结源证据。

风险/前提：PR #522 仍是大规模堆叠 PR，单纯调整 `on.paths` 不能自动保证全部 CI 绿；新上游必须确实进入 #522 的 source tree，且需验证 required checks/事件源差异。此项需要独立源码评审与 CI 证据后才能实施。

### 方案 B —— 重组 PR #522 的全部产品功能提交链

拆分 PR #522 中 P4 功能与此前无线/固件功能，以更接近当前产品 authority 的基线建立干净的产品小 PR。虽然长期有助于降低变更面积，但由于 N3-W 首次配对与产品固件依赖较深，拆分历史可能改变已冻结的 exact artifact 绑定，不适合在 P4 clean-board 首次正常启动之前匆忙进行。且 H3 `packages/**` 触发范围本身仍会对任何非 H3 产品配置 PR 产生同类失败，因此重组 PR **不能单独解决问题**。

### 方案 C —— 修改 H3 source gate 的 required/protected 路径或临时放行

**拒绝**。这会把旧阶段的验收条件变成另一个合同，破坏真实 FAIL 证据，无法解释旧 H3 保护含义。禁止删除三个旧 gate、对失败运行伪造 SUCCESS、宽松忽略 `core.yml` / `display.yml` 变更。

## 4. 方案 A 源码变更限制与定向测试矩阵

```text
SCOPE=THREE_H3_WORKFLOW_TRIGGER_FILTERS_ONLY
H3_PYTHON_GATES_MODIFIED=false
FIRMWARE_OR_MANAGER_SOURCE_MODIFIED=false
EXACT_ARTIFACT_SOURCE_MODIFIED=false
PRODUCTION_TESTS_DISABLED=false
BUILD_FLAGS_MODIFIED=false
H3_HISTORICAL_CI_LOGS_DELETED=false
```

验证矩阵（**尚未运行**）：

| 合成 PR 变更集 | 预期行为 |
| --- | --- |
| 只修改 `packages/core.yml` 或 `packages/display.yml` | 触发当前 RC2/N3-W 产品检查；不误触发历史 H3 Stage 2D-2/3/4 |
| 只修改 `packages/n3w_product_transport.yml` | 触发当前 RC2/N3-W 及首次配对合同；不触发 H3 |
| 修改 Stage 2D-2 候选 MQTT 专属源码 | H3 Stage 2D-2 正常触发并执行原严格门 |
| 修改 Stage 2D-3/4 专属源码 | 相应 H3 workflow 正常触发，原 `REQUIRED_PATHS` / `PROTECTED_PATHS` 原样生效 |
| H3 专属源码 + 受保护 `packages/core.yml` | 历史 H3 工作流仍触发，原 source gate FAIL |
| 产品配置修改 + 泄密字面量 | 公共安全扫描及相应当前产品回归正常执行，不得屏蔽 |
| PR #522 引入上游触发策略修补后 | H3 不应被旧 `packages/**` 单独触发；当前产品安全与编译结果必须另行 PASS |
| required status check 仍强制 H3 绿灯 | STOP；先澄清规则，不绕过合并保护 |

同时验证原 H3 配置及源判定脚本的 Git blob 与修补前完全一致（except 3 workflow filter YAML）；验证 PR #523 的原有两条无线 CI `concurrency` 改动与 H3 修改互不冲突。

## 5. 当前执行与 STOP

```text
STAGE=H3_SCOPE_DISPOSITION_DESIGN
DESIGN_CHOICE=OPTION_A_CONDITIONAL_RECOMMENDATION
NEW_H3_WORKFLOW_PATCH=NOT_CREATED
H3_SOURCE_GATES=UNCHANGED
GITHUB_REQUIRED_STATUS_CHECKS=UNVERIFIED
PR522_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
PR523_HEAD=4c943f072230a47de9f7a7a535a7b5ccacfd91e3
PR474_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
MERGE=false
P4_FIRST_NORMAL_BOOT_AUTHORIZED=false
SETUP_SECRET_IMPORT_AUTHORIZED=false
STOP=true

NEXT_ONE_GATE=N3W_PR522_H3_WORKFLOW_TRIGGER_ISOLATION_SOURCE_PRECHECK_AND_REQUIRED_CHECKS_REVIEW_20261008_01
NEXT_SCOPE=READONLY_CHECK_REQUIRED_STATUS_AND_PR_TOPOLOGY_THEN_SEPARATE_WORKFLOW_SOURCE_PR_AND_SYNTHETIC_REGRESSION
```

This record is intentionally isolated on a docs-only GitHub branch, avoiding an additional 28-workflow CI fanout on PR #522. Do not treat this design as an authorized H3 CI rule change, a closed P4 physical gate, or an automatic merge approval.
