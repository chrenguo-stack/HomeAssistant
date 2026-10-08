# N3-W PR #526 P4 六次 H3 编译验收、PR #524 历史例外和安全集成排序（2026-10-08）

```text
TASK=N3W_PR526_EXACT_P4_H3_SIX_BUILDS_CLOSURE_AND_CI_UPSTREAM_INTEGRATION_PLAN_20261008_01
STATUS=SOURCE_AND_REAL_CI_EVIDENCE_CLOSED_PREMERGE_PLANNED
PR474_BASE_SHA=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR522_P4_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
PR523_QUEUE_HEAD=4c943f072230a47de9f7a7a535a7b5ccacfd91e3
PR524_H3_FILTER_HEAD=f1c1d62e370b8c2860464022eb09fbba52ceb6e2
PR525_SUCCESSOR_HEAD=cfffce027739bc15d9b3f5e51c15405f0fd16961
PR526_INTEGRATION_HEAD=a36fa6de55b76c8bdc40140caf05b9c6c0db0b86
PR523_CI=13_OF_13_PASS
PR524_CI=11_PASS_3_LEGACY_SCOPE_FAIL
PR525_CI=12_OF_12_PASS
PR526_CI=12_OF_12_PASS
PR526_H3_REAL_HOST_FAULT_TESTS=3_OF_3_PASS
PR526_H3_REAL_ESP32_COMPILES=6_OF_6_PASS
PR526_H3_COMPILE_LOG_EVIDENCE=6_OF_6_PASS
H3_TECHNICAL_COMPATIBILITY_DEFICIT=CLOSED_ON_EXACT_P4_SOURCE
H3_LEGACY_SCOPE_FAILURES=REMAIN_REAL_UNMODIFIED
H3_POLICY_EXCEPTION=CONDITIONALLY_ELIGIBLE_NOT_BLANKET_APPROVED
UPSTREAM_MUTATION=false
PR_MERGE=false
P4_FIRST_NORMAL_BOOT_AUTHORIZED=false
T1_ACCESS=false
BOARD_ACCESS=false
REAL_SECRET_IMPORT=false
STOP=true
```

## 1. 两套独立的真实 CI 证据

[PR #525](https://github.com/chrenguo-stack/HomeAssistant/pull/525) 新增独立 H3 compatibility CI，基于旧上游 PR #474 分支运行：
- run [37788417973](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37788417973)，12/12 个关联 workflow SUCCESS。
- workflow 里的 `source-contract`、`stage-compatibility (d2)`、`(d3)`、`(d4)` 四项全部 SUCCESS；各阶段原始主机 fault matrix、最小板端与完整 RC2 H3 实验固件编译及脱敏证据核验均 PASS。

[PR #526](https://github.com/chrenguo-stack/HomeAssistant/pull/526) 作为**集成验证专用草稿 PR**，base 为 PR #522 精确 P4 HEAD，HEAD 为 `a36fa6de...`，只有新增 PR #525 的四个文件。实际比较 `58107b3...a36fa6d` 为 1 个新提交、4 个新增路径、0 个既有路径变更。P4 `core/control/buses/sensors/display` 五份共享配置的 Git blob 与原 PR #522 完全相同；PR #525 测试文件、执行程序和工作流的 Git blob 与 PR #525 完全相同。

- run [37791864150](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37791864150)，12/12 关联 workflow SUCCESS。
- GitHub 阶段 D2 job [113361151668](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37791864150/job/113361151668)，D3 job [113361151716](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37791864150/job/113361151716)，D4 job [113361151835](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37791864150/job/113361151835)。
- 每一项真实日志恰好具备以下九个标记：`host compile: PASS`、`host fault matrix: PASS`、`minimal config: PASS`、`minimal ESP32-C6 compile: PASS`、`product config: PASS`、`full RC2 ESP32-C6 compile: PASS`、`minimal compile evidence: PASS`、`product compile evidence: PASS`、`H3 compatibility dN: COMPLETE PASS`。
- 因此实际完成六次 ESP32-C6 配置/固件编译及其两组输出证据核对，**不是只运行字符串断言**。不代表实板上电、配对成功或可靠性运行已验收。

PR #526 永远作为独立集成验收证据，**不得自动合并进 PR #522**。PR #522 冻结 P4 原始 HEAD / source SHA 必须保持可追溯。

## 2. PR #524 历史范围失败的专项技术判定

PR #524 [运行证据](https://github.com/chrenguo-stack/HomeAssistant/pull/524#issuecomment-6062432436)：
- 真实 CI 为 11 SUCCESS / 3 FAILURE；Stage 2D2 / 2D3 / 2D4 的原始 host fault-matrix 均 PASS，随后历史“只允许改动特定阶段文件集”的 `Verify Stage 2D-N source and production boundaries` 均 FAIL，ESP32 编译在旧 workflow 中被跳过。
- 其原因与三个 workflow 各仅移除两处宽泛 `packages/**` 触发项、仍触发 workflow-self-change 检查一致；不能把三项历史 FAIL 改名 PASS，也不能删除旧 gate。
- PR #526 对确切 P4 源完成 6/6 编译与 3/3 fault matrix SUCCESS，关闭了先前缺少的共享 RC2 配置兼容性证据。
- 因而 **旧范围门三个 FAIL 的技术例外“有条件具备资格”**：仅适用于 PR #524 exact `f1c1d62...` 的三个 workflow 各 +0/-2 行、三个 source Python gate blob 完全未变、原 H3 专属路径触发仍在。未来任何 H3 专属源码 + 受保护产品路径混改仍触发原 H3 门并可 FAIL。
- 例外仍不构成“绿灯式强制合并”；需 successor CI **先进入目标上游**，再 fresh rebind 检查 GitHub rule、required status 与基线。PR #524 保持 DRAFT / unmerged。若后续另有 H3 回归、源指纹漂移、CI secret disclosure 或 GitHub 保护规则新增，例外资格失效。

## 3. 精确安全集成顺序

所有独立 PR 目前都基于 PR #474 的 head `d3c158b...`，且 PR #523/#524/#525 的 changed-file 清单两两**无交集**。然而 PR #474 目前仍是 OPEN_DRAFT、存在独立上游源码/物理验收边界，不能仅据文件无交集认定可以自动合并。采用每次最多一个 upstream-only source merge、每次新的完整 rebind 的顺序：

1. **PR #523 — CI 旧运行取代策略**：13/13 PASS；两个无线 radio-contract workflow 只增加同 PR/同 workflow 的 `concurrency` 策略，`push` 使用独立 run ID。可作为第一个候选，以减少后续重复排队。先核对 PR #474 实际 branch policy、当前 head、PR #523 变更文件与 exact CI。如果这些条件漂移，立即停止。合入将改变 PR #474 **分支 HEAD**，因此必须以 source-only 安全门独立决策，不能宣称已保留 PR #474 exact HEAD 不变。
2. **PR #525 — 独立 H3 compatibility successor**：12/12 PASS，全部新 CI/runner/test/doc 文件；还拥有 PR #526 的 exact P4 六次固件编译 6/6 PASS。作为第二候选，合入后必须复验新 workflow 的本地编译、source contract 和适当路径触发条件，冻结 P4 文件不应变。
3. **PR #524 — 收窄历史 H3 CI 触发**：只在 successor 已被实际合入且 GitHub 安全规则完成 fresh rebind、原三个 H3 Python gate Git SHA 仍 unchanged、独立 source review 认可已知三项 FAIL 的*专用例外*时考虑。PR #524 不能被显示为全绿；合并记录必须指向这三条 FAIL 和 PR #525/#526 真实成功的证据。若 required checks 强制需要它们 PASS，不得规避或虚构 SUCCESS，应停止改走正式规则审查。
4. **PR #522 P4**：三项旧 H3 范围门若在上游新触发条件下不再误触发，仍必须独立查明 M2 node-auth board-lab [run 37781461408](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37781461408) 的历史 HTTP 403（`pioarduino/esp-idf-v5.5.4.tar.xz` 依赖下载），并在新的 HEAD/merge ref 上获取真正的 RC2/N3-W/Public Safety 全部回归结果；不能因为 PR #526 12/12 就把 PR #522 原来的 24/28 宣称为全绿。
5. **PR #526**：仅供 PR #522 原始 P4源码精确绑定的保留证据，**不合并**。不要 squash/rebase/reset PR #522 原始 source HEAD 的已有记录；如集成路径需要运行新测试，另建测试用分支并标记 exact source SHA。

## 4. 必需检查和冻结边界

最后一次 GitHub API 只读显示：
- 仓库 `protect-main` ruleset `20514758` 仅作用 `~DEFAULT_BRANCH`；已知检查包括 `esp32-c6-board-targets` / `validate` / `tracked-content-safety` 等，但不包括这些 H3 历史工作流名称。
- 作为当前目标的 PR #474 head branch 显示 `protected=false`。这不是覆盖所有组织级权限或合并策略的绝对证明。
- PR #522/#523/#524/#525/#526 尚为 OPEN / DRAFT / UNMERGED，PR #474 亦然。任何真实 merge 都必须在单独的 source/review gate 下明确记录目标分支来源、合并 commit、回归结果与未闭合风险。

```text
NEXT_ONE_GATE=N3W_PR523_525_UPSTREAM_CI_ONLY_INTEGRATION_PREMERGE_REBIND_20261008_01
NEXT_ACTION=FRESH_REVIEW_PR523_RULES_HEAD_AND_CI_FOR_SINGLE_UPSTREAM_SOURCE_MERGE
H3_HISTORICAL_EXCEPTION=ELIGIBLE_BUT_NOT_MERGED
P4_FIRMWARE_SOURCE_FROZEN=true
BOARD_ACCESS=false
T1_ACCESS=false
SETUP_SECRET_IMPORT=false
MERGE_AT_THIS_GATE=false
STOP=true
```
