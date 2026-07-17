---
name: greenhouse-github-development-efficiency
description: "Use this skill when developing, testing, reviewing, or releasing the 温室环境监测系统 repository, especially for GitHub Actions, pull requests, ESPHome/ESP32-C6 builds, greenhouse-manager tests, MQTT/Dynamic Security work, T1 live validation, handoff documentation, or any workflow where foreground feedback latency and repeated CI work must be controlled."

IMPORTANT: System, developer, project, security, and user instructions always take precedence over this skill.
---

# Primary Goal

在不削弱生产安全、回滚能力、凭据隔离和实机验收的前提下，提高温室环境监测系统的开发吞吐量，并将普通开发反馈稳定控制在可接受时间内。

默认目标：

- 普通代码或文档修改：首次有效反馈不超过 5～10 分钟；
- 常规 PR 完整检查：不超过 15 分钟；
- 重型 ESPHome、Docker、Dynamic Security 集成检查：不阻塞普通反馈，转入完整检查或夜间检查；
- 一个普通 PR 尽量只进行 1～3 次远程推送；
- 一个前台对话默认只承担一个清晰阶段门，不连续串行完成多个重型 PR；
- 任何提速不得绕过生产授权、回滚、匿名兼容或受保护服务边界。

# Project Safety Boundaries

以下边界不得为了提速而删除、弱化或模拟为已完成：

- 未达到阶段门前保持 MQTT anonymous 兼容；
- 不重放已经消费或过期的生产授权；
- 不在 Git、YAML、CI 日志、进程参数、构建产物中保存生产凭据；
- 不使用生产 T1 作为公共仓库的自托管 GitHub Runner；
- 不让 CI 直接修改生产 Mosquitto、Home Assistant、greenhouse-manager 或节点；
- 生产执行必须保留只读基线、明确授权、回滚和提交后审计；
- 实机验证不能被纯模拟、纯单元测试或编译通过替代；
- 不因追求更少检查而将所有功能重新塞入一个不可诊断的巨大工作流。

# Efficiency Principles

## 1. 先定义完成条件，再开始修改

每个任务开始时必须明确：

- 本轮唯一主目标；
- 允许修改的模块和文件范围；
- 必须通过的最低测试；
- 哪些检查属于 fast、full、nightly、live；
- 哪些结果需要用户决策或实机操作；
- 停止条件。

禁止边开发边无限扩大范围。未影响当前目标的重构、命名调整、文档美化和下一阶段功能，应记录为后续任务，不得顺手并入。

## 2. 以“最小闭环”组织任务，而不是以“最小改动”频繁推送

推荐单位：

```text
一个缺陷/能力
→ 代码
→ 相关测试
→ 必要文档
→ 本地检查
→ 一次推送
```

禁止默认采用：

```text
改一小处 → commit/push → 等 CI → 再改一小处 → 再 push
```

一个普通 PR 的目标是 1～3 次远程推送。中间探索性提交可保留在本地，合并前使用 squash 或整理提交历史。

## 3. 快速检查、完整检查、夜间检查、实机检查必须分层

### Fast CI

每次 PR 更新执行，目标 2～5 分钟：

- 公共仓库安全扫描；
- 格式、静态检查、Ruff；
- 受影响模块的单元测试和合同测试；
- YAML/JSON/schema 校验；
- ESPHome `config` 验证；
- 不需要 Docker、完整 ESP-IDF 编译或真实设备。

### Full PR CI

仅在 Ready for review、手动 full gate、合并队列或明确标签后执行，目标 8～15 分钟：

- 受影响的完整 Python 测试；
- ESP32-C6 ESP-IDF 编译；
- Mosquitto/Dynamic Security 隔离集成测试；
- M0/M1/M2 垂直链路；
- 关键故障注入。

### Nightly Deep CI

定时执行，不阻塞对话：

- 所有固件目标全量编译；
- 全量 Docker 组合；
- 扩展故障矩阵；
- 多版本依赖兼容性；
- 长时间稳定性和重复运行；
- 全仓库安全与生成物一致性审计。

### Live/T1 Gate

仅在阶段闭环时批量执行：

- 生产环境只读探测；
- 候选准备；
- 授权；
- 执行与回滚；
- 提交后审计；
- 实板或 T1 真实环境行为。

不得把每个小修复都升级为一次 T1 操作。

# GitHub Actions Standards

## 1. 所有 PR 工作流必须取消过期运行

每个 PR 工作流加入：

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

要求：

- 新提交到达后取消同一 PR 的旧运行；
- main、release 和生产相关运行不得被不安全取消；
- 不允许旧提交继续占用 Runner 并产生无效结果。

## 2. 使用稳定的“总门”作为分支保护检查

不要让分支保护依赖大量动态、可能被路径过滤跳过的检查名称。

推荐结构：

```text
ci-router
├─ manager-fast
├─ firmware-fast
├─ protocol-fast
├─ integration-full（条件执行）
└─ ci-required（始终执行并汇总）
```

`ci-required` 使用 `if: always()` 汇总所有需要执行的子任务，作为稳定的 required check。

## 3. 路径过滤必须精确，但不能制造永久 pending

工作流或 job 应根据改动范围执行：

- `firmware/**`：固件配置、组件合同、必要编译；
- `host/greenhouse-manager/**`：Manager lint/test；
- `protocols/**`：协议 schema/合同；
- `deploy/**`、Mosquitto 配置：集成测试；
- 纯文档：只跑文档、安全、链接和格式检查。

对于必须作为 required check 的工作流，优先让工作流始终启动，由 router job 判断哪些子 job 跳过；不要仅依赖顶层 `paths` 导致 required check 不出现。

项目内优先使用自有 Python 路由脚本，例如：

```text
tools/ci_changed_scope.py
```

避免为简单路径判断引入未经审计的第三方 Action。

## 4. 先廉价失败，后昂贵执行

工作流顺序：

```text
checkout
→ schema/format/lint
→ focused unit/contract tests
→ dependency-heavy tests
→ Docker integration
→ ESP-IDF compile
→ artifact verification
```

昂贵 job 使用 `needs: preflight`。静态检查失败时，不再启动 ESPHome 编译和 Docker 矩阵。

## 5. 依赖和工具链缓存

必须优先缓存不可变、可验证的依赖：

- pip 下载缓存；
- PlatformIO packages/toolchains；
- ESP-IDF/ESP32-C6 平台包；
- 固定版本的静态工具。

缓存键必须包含：

```text
OS + Python版本 + ESPHome版本 + PlatformIO/ESP-IDF版本 + 依赖锁文件哈希
```

默认不缓存：

- 生产或临时凭据；
- 包含 secret substitution 的生成配置；
- 未经隔离验证的完整 `.esphome/build`；
- 可能跨分支污染的运行时状态。

如果缓存构建中间物，必须证明其中不含凭据，并以源码、配置和工具链哈希精确隔离。

## 6. 重型环境应考虑固定 CI 镜像

当安装 ESPHome、PlatformIO、编译器和系统依赖耗时明显时，可建立项目专用 CI 容器：

- 在 main/nightly 构建；
- 固定版本并按 digest 引用；
- 不内置生产凭据；
- 保留 SBOM/来源信息；
- PR 仅使用已发布、受信任的镜像。

这通常比每个 Hosted Runner 重新安装全部工具更快、更稳定。

## 7. 编译目标并行化与复用

多个独立 ESPHome 目标可使用 matrix 并行：

```yaml
strategy:
  matrix:
    config:
      - greenhouse_mqtt_auth_compile.yml
      - greenhouse_mqtt_auth_runtime.yml
```

规则：

- PR 阶段优先 `fail-fast: true`，尽快停止明显失败；
- nightly 可使用 `fail-fast: false` 收集完整兼容性结果；
- 若后续测试使用相同固件，编译一次并上传 artifact，禁止重复编译；
- artifact 必须具备 SHA、配置和工具链指纹，不得只靠文件名识别。

## 8. 复用安装和测试逻辑

将重复的以下步骤收敛：

```text
setup-python
pip install -e .[dev]
ruff
pytest
```

优先顺序：

1. 仓库内统一脚本；
2. reusable workflow (`workflow_call`)；
3. 经审计的 composite action。

不要在多个 workflow YAML 中复制长段命令并逐渐产生差异。

推荐入口：

```text
./tools/dev preflight <scope>
./tools/dev test fast <scope>
./tools/dev test full <scope>
./tools/dev package t1 <stage>
```

## 9. 合并后检查不得无条件重复 PR 全量检查

默认策略：

- PR：fast + 必要 full；
- main：轻量 smoke、生成版本元数据、发布准备；
- nightly：全量 deep；
- release：签名、发布和正式验收。

只有当 main 合并结果与 PR merge ref 存在实质差异时，才重复相关完整测试。

## 10. 为每个 job 设置超时

每个 job 必须设置合理 `timeout-minutes`：

- fast：5～10；
- full：15～25；
- nightly：按测试矩阵单独设定；
- live：由阶段事务明确限定。

禁止无上限等待网络、Docker、Broker、ESPHome 下载或测试死锁。

# Test Architecture Standards

## 1. 测试必须有明确分类

建议 pytest markers 或等价分类：

```text
unit
contract
integration
fault
compile
live
slow
```

默认 PR fast 不运行 `slow/live`。Full 根据 changed scope 选择。Nightly 运行全部非生产 live。真实 T1 由独立阶段门执行。

## 2. 测试选择必须依据变更影响，而不是全仓库惯性

建立模块到测试的映射，例如：

```text
greenhouse_manager/node_mqtt_* → node auth unit/contract + isolated lab
firmware/components/greenhouse_mqtt_auth → adapter contract + config + compile
mosquitto/dynsec → dynsec integration
protocol schema → schema + producer/consumer contract
```

跨模块公共接口改变时才扩大为全量测试。

## 3. 故障注入与正常路径分离

正常路径先快速确认；故障矩阵单独 job。失败时应能明确识别：

- 安装/环境失败；
- 合同失败；
- Broker 启动失败；
- 认证逻辑失败；
- 回滚失败；
- 清理失败。

不要把全部步骤塞进一个长 shell command，只返回一个笼统退出码。

## 4. 对不稳定测试单独治理

不得通过重复运行整个工作流掩盖 flaky test。

出现偶发失败时：

- 记录测试名、失败阶段、运行环境和频率；
- 只重跑失败 job 判断是否 flaky；
- 修复同步、超时、端口、随机种子或资源清理；
- 在修复前不得把它作为“通常会过”接受。

目标：flaky rate 小于 2%。

# Git and Pull Request Standards

## 1. 一个 PR 对应一个阶段性闭环

PR 应同时包含完成该闭环所需的：

- 实现；
- 聚焦测试；
- 必要合同/文档；
- 版本或阶段状态更新。

避免把同一能力拆成一串高度依赖、每个都触发全套 CI 的微型 PR；也避免把多个不相关能力塞入一个巨大 PR。

## 2. Draft PR 只运行 fast

开发早期可创建 Draft PR，但：

- Draft 上只运行 fast；
- `ready_for_review` 后触发 full；
- 不在 Draft 的每个探索提交上运行完整 ESPHome/Docker 矩阵。

## 3. 提交历史以可审计为准，不追求数量

推荐提交粒度：

```text
实现 + 对应测试
合同/文档修订
CI/工具链调整
```

禁止为了“展示过程”把每个小修补都推到远程。过程证据由本地历史、PR 描述和测试结果承担。

## 4. PR 描述必须给出测试分层

PR 模板至少包含：

```text
Scope
Out of scope
Fast checks
Full checks
Live checks pending
Safety boundaries
Rollback impact
Required user action
```

这样无需反复读取大量提交和日志才能理解状态。

# Script and Tooling Standards

## 1. 停止无限增加一次性 Vxx 脚本

默认使用稳定、参数化、可测试的工具：

```text
gh-m2 audit
gh-m2 prepare
gh-m2 authorize
gh-m2 execute
gh-m2 post-audit
```

版本由包元数据、Git SHA、schema 和 manifest 管理，不以不断复制 `script_v73.py`、`script_v74.py` 作为主要版本控制方式。

只有满足以下条件才允许新增一次性脚本：

- 生产恢复的紧急、不可复用操作；
- 明确标记 disposable；
- 有 checksum、用途、失效条件和清理说明；
- 完成后归档或删除，不继续成为正式入口。

## 2. 工具必须支持 dry-run、幂等和结构化输出

正式工具应具备：

- `--dry-run`；
- 明确输入 manifest；
- JSON 结构化终态；
- 稳定错误码；
- 不输出秘密；
- 同一输入重复准备结果可验证；
- 执行与授权严格分离；
- 回滚可单独验证。

## 3. 生成物使用内容寻址，不使用脆弱硬编码

禁止依赖：

- 固定 patch 文件数量；
- 固定临时目录层级；
- 固定 worktree 相对位置；
- 模糊“最新文件”；
- 只凭文件名识别授权包。

使用：

- SHA-256；
- schema/version；
- repository SHA；
- target identity；
- manifest binding；
- 明确过期时间。

## 4. 将人工命令压缩为单一入口

用户执行命令应尽量是：

```bash
scp <一个包> t1:/tmp/
ssh t1 'python3 /tmp/<入口>.py --manifest /tmp/<manifest>'
```

不要要求用户手工拼接十几个环境变量、路径、摘要和阶段参数。复杂性应封装在已校验包中。

# GitHub Tool/API Efficiency Rules

当通过 GitHub 工具检查仓库和 CI 时，按以下顺序：

1. 获取 commit/PR 元数据；
2. 获取 workflow run 列表；
3. 只获取失败或仍运行的 jobs；
4. 先读取 step summary；
5. 仅对失败 job 下载完整日志；
6. 优先查找第一个根因，不从头通读所有成功日志；
7. 只重跑失败 job，不重跑整个成功矩阵；
8. 确认为 Runner/网络偶发故障后才使用 rerun；
9. 代码缺陷必须修改代码，不得靠反复 rerun 获得绿色结果。

禁止：

- 每隔几秒高频轮询；
- 对所有成功 job 下载数千行日志；
- 同时重复调用多个返回相同状态的接口；
- 在仅需文件统计时获取完整 diff；
- 在仅需失败步骤时读取整个 workflow artifact。

建议轮询间隔：普通 CI 2～3 分钟一次；已知短任务最多检查两次后应转为非阻塞状态。

# Conversation and Feedback Latency Rules

## 1. 前台对话时间预算

默认单轮前台执行预算：10～15 分钟。

在预算内优先完成：

- 范围确认；
- 代码与本地检查；
- 建立 PR/提交；
- 启动 CI；
- 获取首轮状态；
- 给出可继续工作的明确 checkpoint。

不得为了等待一个无须立即决策的 full/nightly CI，把用户前台回复阻塞 50～60 分钟。

## 2. CI 运行时继续非冲突工作

CI 在运行时可继续：

- 文档增量；
- 下一测试用例的本地准备；
- 失败恢复设计；
- artifact/manifest 生成；
- 不依赖当前 CI 结果的代码审查。

禁止连续创建第二个高度依赖当前未通过 PR 的重型 PR。

## 3. 长任务使用条件监控，而不是同步等待

当用户要求持续跟踪时，优先使用可用的条件监控/自动化：

```text
检查指定 PR/commit 的 CI；仅在完成、失败或需要用户决策时通知。
```

如果没有监控能力，应立即给出：

- commit/PR；
- 当前检查状态；
- 剩余 gate；
- 下一步；
- 是否需要用户操作。

## 4. 每轮只汇报增量，不重复全部项目历史

状态输出固定为：

```text
本轮完成
当前阻塞
安全边界
下一步
需要用户操作（没有则明确“无”）
```

完整历史只在阶段交接或用户要求时生成。

# Documentation and Handoff Efficiency

## 1. 使用一个机器可读状态文件作为事实源

建议维护：

```text
docs/development/active-stage.yaml
```

包含：

- current_stage；
- repository_sha；
- manager_version；
- completed_gates；
- pending_gates；
- production_boundaries；
- latest_live_evidence；
- next_action；
- prohibited_replays。

交接文档从该状态生成或引用，不在每轮手工重写全部历史。

## 2. ADR 只记录架构决策

只有影响长期接口、产品边界或安全模型的决策才新增 ADR。普通 bug fix、CI 调整和脚本修复不单独生成冗长设计文档。

## 3. 阶段交接按里程碑生成

以下时机才生成完整交接：

- 阶段门通过；
- 生产状态变化；
- 需要切换对话且上下文接近上限；
- 出现必须长期保留的新阻塞；
- 用户明确要求。

普通 PR 完成后只更新 active stage 和简短 changelog。

# Live Validation Efficiency

## 1. 批量组织 T1 测试

在请求用户执行前，必须确保：

- 仓库 CI 已通过；
- 候选包和 manifest 已生成；
- checksum 已固定；
- 完整命令已准备；
- 预期输出和失败分支已定义；
- 不需要再因文档或小格式修改重新打包。

一次 T1 操作尽量覆盖一个完整阶段门，而不是单个断言。

## 2. 只读探测与写操作分离

可自动、频繁执行的只读审计应收敛成稳定工具。写操作必须少、明确、可授权、可回滚。

## 3. 实机失败优先提取最小诊断

实机失败后，先回答：

- 失败阶段；
- 最后完成阶段；
- 服务是否变化；
- 是否已回滚；
- 是否需要新授权；
- 最小必要诊断。

不要立即生成另一套完整执行链，除非根因已经定位并修复。

# Completion and Stop Rules

任务达到以下条件时立即停止扩展：

- 请求范围内代码完成；
- 必要测试通过；
- 安全边界未破坏；
- PR/commit 状态清晰；
- 下一 live gate 已定义；
- 未发现阻断性缺陷。

禁止在完成后继续：

- 无请求地重命名大量文件；
- 重写已稳定工具；
- 为“更完美”增加第二套实现；
- 新增不影响当前 gate 的测试矩阵；
- 连续开启下一个重型阶段而不先给用户反馈。

# Metrics

每月或每 20 个 PR 审核一次：

| 指标 | 目标 |
|---|---:|
| Fast CI P95 | ≤ 5 分钟 |
| Full PR CI P95 | ≤ 15 分钟 |
| 普通 PR 远程推送次数 | ≤ 3 |
| 过期 CI 自动取消率 | 100% |
| 重复安装/重复测试比例 | 持续下降 |
| 缓存命中率 | ≥ 70% |
| Flaky test 比例 | < 2% |
| 普通前台反馈时间 | ≤ 10～15 分钟 |
| 每阶段 T1 操作批次 | 尽量 1 次 |
| 失败后完整重建证据链 | 仅在绑定内容变化时 |

CI 应在 job summary 输出关键耗时：

```text
queue_seconds
setup_seconds
install_seconds
test_seconds
compile_seconds
artifact_seconds
cache_hit
```

没有测量就不得仅凭感觉继续优化。

# Recommended Implementation Order

## P0：立即执行

1. 所有 PR workflow 增加 `concurrency/cancel-in-progress`；
2. 限制一个普通 PR 远程推送为 1～3 次；
3. 设置 job 超时；
4. GitHub 检查只读取失败 job 日志；
5. 前台对话设置 10～15 分钟预算；
6. 纯文档和小改动不触发 ESPHome/Docker 全量检查。

## P1：本阶段完成

1. 建立 fast/full/nightly/live 四层；
2. 建立 changed-scope router 和稳定 `ci-required`；
3. 合并重复 Manager 安装、lint、pytest；
4. 缓存 PlatformIO/ESP-IDF 工具链；
5. ESPHome 多目标 matrix；
6. Draft PR 只运行 fast；
7. 建立 `tools/dev` 统一入口。

## P2：后续优化

1. 固定项目 CI 容器镜像；
2. 编译 artifact 复用；
3. 测试 marker 和变更影响映射；
4. active-stage.yaml 机器可读状态；
5. 参数化 M2 CLI 替代一次性 Vxx 脚本；
6. nightly 深度测试和定期性能报告。

## P3：只有仍然不足时考虑

使用独立 x86 Linux 自托管 Runner，但必须：

- 不使用生产 T1；
- 与生产网络和凭据隔离；
- 不接受未经批准的外部 PR；
- 使用短生命周期 Runner 或可重建镜像；
- 明确清理 workspace；
- 仅承担受信任分支的重型编译。

# Per-Task Checklist

## 开始前

- [ ] 本轮唯一目标明确
- [ ] 文件和模块范围明确
- [ ] Fast/Full/Live 测试明确
- [ ] 不在范围内的工作已排除
- [ ] 安全边界已确认

## 推送前

- [ ] 本地 fast 检查通过
- [ ] 代码、测试和必要文档已成闭环
- [ ] 没有生产 secret 或路径泄露
- [ ] 不需要再为已知小问题追加下一次 push
- [ ] PR 描述包含 gate state

## CI 期间

- [ ] 旧运行会自动取消
- [ ] 先查看 run/job/step 摘要
- [ ] 只读取失败 job 完整日志
- [ ] 不高频轮询
- [ ] 不用 rerun 掩盖代码缺陷

## 合并前

- [ ] Required gate 稳定出现并通过
- [ ] Full 检查按影响范围完成
- [ ] Live pending 明确标记
- [ ] 回滚和兼容边界未改变
- [ ] 提交历史已整理

## 阶段结束

- [ ] active stage 已更新
- [ ] 只记录增量结果
- [ ] T1 测试已批量准备或完成
- [ ] 临时包、凭据和 workspace 已清理
- [ ] 下一步不依赖隐含上下文

# Expected Assistant Behavior

应用本 skill 时，助手应：

- 优先减少重复工作，而不是简单减少测试；
- 在开始 GitHub 写操作前给出最小、明确的执行计划；
- 尽可能在一次本地修改中完成代码、测试和文档；
- 不因等待完整 CI 长时间阻塞用户；
- 对 CI 失败只读取必要日志并定位首个根因；
- 除非内容绑定发生变化，否则不重建全部证据链；
- 在高风险生产步骤前停止并请求必要授权；
- 达到完成标准后立即汇报，不继续无边界优化。
