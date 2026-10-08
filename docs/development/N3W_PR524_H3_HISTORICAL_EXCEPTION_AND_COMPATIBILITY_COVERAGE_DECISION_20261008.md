# PR #524 — H3 历史阶段例外与 RC2 兼容性覆盖决策（2026-10-08）

## 任务与边界

```text
TASK=N3W_PR524_H3_HISTORICAL_SCOPE_EXCEPTION_AND_COMPATIBILITY_COVERAGE_DECISION_20261008_01
EXECUTION_MODEL=SOURCE_AND_CI_READONLY_REVIEW_WITH_GITHUB_DESIGN_ARCHIVE
PR474_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR522_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
PR523_HEAD=4c943f072230a47de9f7a7a535a7b5ccacfd91e3
PR524_HEAD=f1c1d62e370b8c2860464022eb09fbba52ceb6e2
PR524_SOURCE_SCOPE=PASS
PR524_GITHUB_CI=11_PASS_3_FAIL
H3_HOST_FAULT_MATRICES=D2_D3_D4_PASS
H3_STRICT_SOURCE_BOUNDARY=D2_D3_D4_FAIL
H3_ESP32_COMPILE_FOR_PR524=SKIPPED
POLICY_EXCEPTION=NOT_APPROVED
COMPATIBILITY_EQUIVALENCE=NOT_PROVEN
ADDITIONAL_COMPATIBILITY_CI=REQUIRED_BEFORE_EXCEPTION_ACCEPTANCE
SOURCE_MERGE=false
T1_ACCESS=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORT=false
P4_FIRST_NORMAL_BOOT=false
STOP=true
```

## 已验证的真实覆盖

旧 H3 三条工作流：
- `.github/workflows/h3-n2-stage2d2-candidate-mqtt-validator-ci.yml`，严格源码门 `tools/h3_n2_stage2d2_candidate_mqtt_boundary_gate_20260721_v50.py`。
- `.github/workflows/h3-n2-stage2d3-activation-transaction-ci.yml`，严格源码门 `tools/h3_n2_stage2d3_activation_boundary_gate_20260721_v51.py`。
- `.github/workflows/h3-n2-stage2d4-profile-lifecycle-integration-ci.yml`，严格源码门 `tools/h3_n2_stage2d4_profile_lifecycle_boundary_gate_20260721_v52.py`。

PR #524 的真实 Actions 结果：11 SUCCESS，3 FAILURE；失败 run 分别为 D2 `37784022805`、D3 `37784022684`、D4 `37784022985`。三次主机 fault-matrix 的编译与行为测试均 SUCCESS，均在随后的 `Verify Stage 2D-N source and production boundaries` 报错。由于 `esp32-c6-compile` 依赖已失败的 host-fault-matrix job，三个 H3 的最小板端配置与完整 RC2 实验目标编译全部为 **SKIPPED**。不允许将其宣称 PASS。

PR #522 新 HEAD 的两条产品 CI 真实成功：
- `F1.0-RC2 firmware CI` run `37781461562`，默认 RC2 配置验证和固件编译 SUCCESS。
- `N3W auto safe fallback production core convergence CI` run `37781461879`，配对/恢复源码合同及 `RC2_CONFIG=f1_0_rc2_n3w_target.yml` 的产品配置与编译 SUCCESS。
- P4 R3 synthetic run `37781461535` SUCCESS；公共仓库安全扫描 run `37781461448` SUCCESS。

以上成功并非旧 H3 三种专用实验目标的完整替代：H3 `f1_0_rc2_h3_candidate_mqtt_validator_board_lab_20260721_v50.yml`、`f1_0_rc2_h3_profile_activation_board_lab_20260721_v51.yml`、`f1_0_rc2_h3_profile_lifecycle_board_lab_20260721_v52.yml` 分别装载旧 H3 的 candidate MQTT、activation、lifecycle 实验组件，分别有独立的 ESP32 IDF 配置与 C++ 依赖；它们均引用共享 `packages/core.yml`、`control.yml`、`buses.yml`、`sensors.yml`、`display.yml`。N3-W 生产目标 `f1_0_rc2_n3w_target.yml` 装载的是 `greenhouse_n3w_product_core` 和独立的 `packages/n3w_product_transport.yml`。默认产品和 N3-W 产品编译不等于专用实验组件的编译。

PR #522 当时另有独立的 M2 node auth board lab CI run `37781461408` FAIL，失败在下载 `pioarduino/esp-idf-v5.5.4.tar.xz` 连续 HTTP 403（`esp32-c6-board-targets` job）；`scope` 和 `validate` 两个 job SUCCESS。归为 `EXTERNAL_COMPILATION_DEPENDENCY_DOWNLOAD_403`，并非已有证据证明 C++ 编译错误，但 CI 结果依然 FAIL。该项需另门处理；不能通过本 H3 例外消除。

## 是否批准“历史 H3 严格范围门”例外？

**结论：当前暂不批准（HOLD）**。理由不是旧 H3 主机功能测试错误，而是 PR #524 将共享 RC2 package 更新从这三条历史 CI 的触发范围移走后，还没有独立证明旧 H3 的板端实验目标仍可在共享配置更新后编译。三个 H3 的旧阶段范围门非常严格，D3/D4 甚至要求精确历史变更集且使用 `origin/main` 为基线，因此它们不适合作为每次 N3-W/P4 产品改动的通用绿色测试。但安全保护仍不可删除。

可接受的例外需要三个独立证据：
1. 三份原始 H3 source boundary Python 文件 Git blob 未变、H3 专属源码/阶段配置及 workflow-self-change 仍触发原门，并保留原 FAIL 日志。
2. 普通 RC2 package 修改所需的 H3 专用实验 **独立兼容编译** 得到真实 CI PASS，兼容性门不得简单报告绿色或跳过关键编译。
3. 精确上游源码、GitHub 实际分支规则及旧 required checks 关系经过新一轮预合并核验；再由独立审批明确接受 PR #524 三项旧范围门 FAIL 属于策略迁移的历史例外。不能由本设计自动批准合并。

当前可见的 GitHub `protect-main` ruleset ID `20514758` 仅作用于默认分支；目标上游 PR #474 修复分支 API 报告 `protected=false`，且 PR #524 `mergeable_state=unstable`。只能确认未观察到同名 H3 required checks，**不能将 `mergeable=true` 解读为所有 CI 合格或已获得审批**。

## 下一门独立兼容性 CI 设计（暂不实施）

建议专设 `H3_RC2_SHARED_PACKAGES_COMPATIBILITY_V1`，独立于原 H3 source boundary gate，不修改三个旧 Python 门，且不以无条件 pass、修改 required-path 集合等方式消除历史失败。

### 触发范围

`pull_request.paths` 优先精确列出 H3 三种实验目标真实引用的五份共享文件：

- `firmware/esphome_rc/f1_0_rc2/packages/core.yml`
- `firmware/esphome_rc/f1_0_rc2/packages/control.yml`
- `firmware/esphome_rc/f1_0_rc2/packages/buses.yml`
- `firmware/esphome_rc/f1_0_rc2/packages/sensors.yml`
- `firmware/esphome_rc/f1_0_rc2/packages/display.yml`

同时监听该新兼容工作流自身路径（保证策略变更可验证）；`push main` 可选同路径进行集成回归。保留 PR 号+workflow 名称为并发组，取消同一 PR 被新 commit 取代的旧 **非精确产物**兼容测试；不同 PR 隔离，`push` 使用独立 run ID，避免不相关编译互相取消。

注意：`packages/n3w_product_transport.yml` 未被上述 H3 专用目标引用，因此它独自变化时不需要触发 H3 特定兼容编译，但必须继续触发 N3-W 生产合同与 RC2 编译。若未来更改 H3 实验目标的 include 结构，应先同步兼容性触发范围并新增回归断言。

### 需要执行的真实测试

- 对 D2、D3、D4 各运行与原历史 workflow **等效的主机 C++ fault matrix**，对三组候选 MQTT / 激活 / 生命周期做真实 compile+execute；不执行仅适用于历史阶段 PR 的 `changed_paths` 严格门。这是两个不同验证目标，禁止互相冒充。
- 每一组分别执行原 `esp32-c6-compile` job 同样的 **最小 ESP32-C6 lab 配置验证及编译**、**完整 RC2 专用实验配置验证及编译**，共三组实验配置、六次编译。坚持 pin `esphome==2026.4.3` 与原版必要 ESP-IDF/ESP32 SDK 配置。
- 采用已有工作流生成**随机、临时且禁用 Wi-Fi 的测试凭据**的机制；不接入真实 T1、Manager、Broker、板卡和 Setup Secret。验证日志无临时凭据/真实证书/敏感令牌，失败只生成脱敏日志且短期保留。
- 使用三组有界 matrix job、独立缓存、明确超时和每 PR 新提交自动替换旧运行；避免增加常态固件编译队列。不能为提高 CI 吞吐省略实际 H3 专用产品编译，不能将 `config PASS` 代替 `compile PASS`。
- 验证正常 P4 配置更新会触发本门，H3 非关联任务不触发；含 H3 专属源码并同时改动受保护共享 package 的 PR 仍会触发原历史 H3 source gate 并可能失败。
- 兼容性独立工作流须独立小 PR/分支、可复现源码与合成触发测试，先真实 PASS 再讨论合入上游与正式例外批准。新工作流只是**产品兼容性保护的继任者**，不是历史 H3 开发阶段范围门的成功复验。

### 工程成本注意

一次涉及上述五份共享 package 的 PR 会额外执行六项实验配置/编译工作，总资源量不小；为避免重现 PR #522 队列积压，必须实施按 PR 新版本替换旧运行和合理 matrix 并发。任何进一步减少构建的方案应说明覆盖损失并获得单独审批；不建议一开始就以源码字符串断言取代六次编译。

## 后续实施次序

1. 在独立分支创建新增的**共享 package 兼容性检查**，完成自测、静态保护与真实 Actions CI。
2. 以 #522 实际产品改动范围作集成回归；确认旧 H3 不会被无关新产品配置反复触发，同时新增的专用兼容性检查真实覆盖至少五份共享配置。
3. 复核 PR #524 完整 diff 和历史失败证据，正式决定是否接受策略迁移产生的旧三项 FAIL；确认分支规则、审阅人批准、和目标分支没有变化，再考虑按需合入。
4. PR #523 两条无线合同 CI 仍是独立优化，不能顺带获得合并许可。PR #522 的独立 M2 403 在其他门处理，不能以 H3 设计结论关闭。
5. P4 实机正常首次启动、QR/Setup Secret 真实操作继续在冻结物理验收门等待独立授权。

```text
NEXT_ONE_GATE=N3W_PR524_H3_RC2_SHARED_PACKAGE_COMPATIBILITY_CI_SOURCE_DESIGN_AND_PREEXECUTION_20261008_01
NEXT_ONE_SCOPE=COMPATIBILITY_WORKFLOW_DESIGN_AND_SOURCE_VERIFICATION_ONLY
POLICY_EXCEPTION=DEFERRED_PENDING_REAL_COMPAT_CI
NO_H3_SOURCE_GATE_BYPASS=true
NO_MERGE=true
NO_PHYSICAL_OPERATIONS=true
STOP=true
```
