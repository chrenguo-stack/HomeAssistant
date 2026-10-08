# H3 Stage 2D-2/2D-3/2D-4：历史 CI 触发隔离源码修补和独立复核证据（2026-10-08）

```text
TASK=N3W_PR522_H3_LEGACY_WORKFLOW_TRIGGER_ISOLATION_SOURCE_REPAIR_DESIGN_AND_INDEPENDENT_REVIEW_20261008_01
SOURCE_BASE_PR=474
SOURCE_BASE_SHA=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
TARGET_BASE_BRANCH=fix/n3w-production-relay-discovery-full-channel-fallback-v1-source-repair-20260924
PR522_PRECHECK_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
PR523_PRECHECK_HEAD=4c943f072230a47de9f7a7a535a7b5ccacfd91e3
REPAIR_BRANCH=fix/n3w-h3-stage2d234-legacy-workflow-trigger-isolation-20261008

SOURCE_REPAIR=THREE_H3_WORKFLOWS_ONLY
CHANGED_WORKFLOW_FILTER_ENTRIES=6_DELETIONS_ONLY
H3_VALIDATION_SCRIPTS_MODIFIED=false
H3_TEST_COMMANDS_MODIFIED=false
H3_BUILD_ARGS_MODIFIED=false
PR522_SOURCE_MODIFIED=false
PR523_SOURCE_MODIFIED=false
MERGE=false
T1_ACCESS=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORTED=false
STOP=true
```

## 1. 设计来源与根因

完整上游方案：`docs/development/N3W_PR522_H3_STAGE2D2_D3_D4_PROTECTED_SCOPE_DISPOSITION_AND_CI_TRIGGER_ISOLATION_DESIGN_20261008.md`，独立设计分支 `docs/n3w-pr522-h3-protected-scope-disposition-design-20261008`，审阅文档 blob `3cd45397730e200f287af41c3436b205f37087a0`。

PR #522 相对于其实际 base PR #474 分支累计改动 141 个文件；当前产品更改 `core.yml`、`display.yml`、`n3w_product_transport.yml`。三个 2026-07 历史 H3 阶段的 `pull_request.paths` 和 `push.paths` 均宽泛包含 `firmware/esphome_rc/f1_0_rc2/packages/**`，导致新产品共享配置变更触发仅允许旧 H3 文件集的范围门。历史三项失败分别为 D2 `37781461526`、D3 `37781461356`、D4 `37781461616`；真实失败记录继续保留。

## 2. 最小源码差异

仅处理：

- `.github/workflows/h3-n2-stage2d2-candidate-mqtt-validator-ci.yml`，原 blob `769ca390287f592fe1319e4f8ebd22479a1f850f`
- `.github/workflows/h3-n2-stage2d3-activation-transaction-ci.yml`，原 blob `1c525666ffed02006e0ade6ef48c1e49b65c27d7`
- `.github/workflows/h3-n2-stage2d4-profile-lifecycle-integration-ci.yml`，原 blob `09d51b2263be97c45ed1afe81235661efcff07d3`

每个文件只在 `on.pull_request.paths` 与 `on.push.paths` 中各移除一行：
```yaml
      - "firmware/esphome_rc/f1_0_rc2/packages/**"
```

原 H3 阶段专属路径、工作流自触发路径、严格源码边界门、host fault-matrix、ESP32-C6 编译、GitHub `concurrency`、`permissions` 和 `timeout` 原样保留。

三个只读验证门原始 blob 未改：
- D2 `tools/h3_n2_stage2d2_candidate_mqtt_boundary_gate_20260721_v50.py` blob `427c7889e97175d25cc75ff544c0bd25122c7048`
- D3 `tools/h3_n2_stage2d3_activation_boundary_gate_20260721_v51.py` blob `675c0c53f8a91096a3df2ae89ccecf91082e1997`
- D4 `tools/h3_n2_stage2d4_profile_lifecycle_boundary_gate_20260721_v52.py` blob `df027e6c7b8564bf392bb6d648d1a1c02f701d5f`

D3/D4 原门内 `REQUIRED_PATHS`、`PROTECTED_PATHS` 仍拒绝不符合旧阶段权限的修改；没有伪造 PASS。

## 3. 静态合成触发回归（非 GitHub Actions 实测）

在审阅原始 GitHub YAML 后逐条模拟三份工作流的 `pull_request.paths` 条件；每个 Stage 6 个用例均通过，共 `18/18 SYNTHETIC_PASS`：

| 合成变更集 | 原来 | 修补后 |
| --- | --- | --- |
| PR #522 当前 141 条变更路径 | H3 被宽泛共享配置触发 | H3 不再误触发 |
| 仅 RC2 `core.yml`、`display.yml`、`n3w_product_transport.yml` | 触发 H3 | 不触发 H3 |
| 与本阶段无关的非匹配路径 | 不触发 | 不触发 |
| 修改 H3 工作流自身 YAML | 触发 | 仍触发 |
| 修改该 H3 阶段专用实验配置 | 触发 | 仍触发 |
| 修改 H3 专属源码并同时更改受保护 `core.yml` | 触发 | 仍触发，原 source gate 不变 |

验证得到每份 YAML 的共享 glob **原为两处，修改后为零**，且其他源码逐字保持不变。上述测试仅证明触发范围的静态逻辑，不是完整 YAML/Actions 现场回归，也不证明 H3 原门执行成功。

## 4. 独立源码复核与安全边界

**通过源码范围复核的前提：** PR 变更精确限制为这三条历史 H3 workflow 的六行删减，加本审计文档；不得把 `REQUIRED_PATHS`、`ALLOWED_CHANGED_PREFIXES`、`PROTECTED_PATHS` 放宽；必须复核 GitHub 实际 PR diff 和三份 Python 门的原始 blob，并单独查证 required checks。

当前仓库可见 `protect-main` ruleset ID `20514758` 生效范围为 `~DEFAULT_BRANCH`，其中的 required check 清单不含 D2/D3/D4；由于 `branches/main/protection` 接口对 GitHub App 返回权限不足，不以此保证整个仓库所有保护条件均已覆盖。

**预期的单次自触发警报：** 一个仅修改 H3 workflow YAML 的 PR，可能通过这些 workflow 自身的路径规则触发旧门，然后因为历史 `REQUIRED_PATHS` 集合未同时修改而报 FAIL。此 FAIL 应保留为真实事件并复核；不能篡改原门或假装合格。本门在独立草稿 PR 中等待源码和可见 CI 实证后决策，不自动合入 PR #474 的分支。

当 H3 工作流仅在其专属阶段更改时继续运行旧门；对于普通 RC2 产品共享配置修改，由以下独立的产品检查承担本阶段相关验证：
- `.github/workflows/f1-0-rc2-ci.yml` 检验 RC2 配置并编译产品。
- `.github/workflows/n3w-auto-safe-fallback-production-core-convergence-ci.yml` 检查配对/恢复源码合同与 RC2 产品编译。
- `tests/n3w_production/test_first_pair_setup_secret_handoff_contract.py` 检查首次配对二维码与 Manager 交接接口。
这**不等于**旧 H3 验收门得到 PASS。

## 5. 门禁状态与下一步

```text
SOURCE_PATCH=PREPARED
SYNTHETIC_TRIGGER_CASES=18_PASS_SOURCE_SIMULATION
INDEPENDENT_EXACT_DIFF_REVIEW=REQUIRED_AFTER_COMMIT
GITHUB_CI_RESULT=NOT_YET_VERIFIED
SOURCE_GATE_ACCEPTANCE=PRELIMINARY_CONDITIONAL
H3_REQUIRED_SOURCE_GUARDS=UNCHANGED
H3_SCOPE_FAILURES=HISTORICAL_OPEN
PR522_ORIGINAL_RECOVERY_BRANCH=UNCHANGED
PR523_SCHEDULING_PR=UNCHANGED
PR_MERGE=false
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
STOP=true

NEXT_ONE_GATE=N3W_PR522_H3_LEGACY_TRIGGER_ISOLATION_DRAFT_PR_CI_AND_INDEPENDENT_REVIEW_20261008_01
```
