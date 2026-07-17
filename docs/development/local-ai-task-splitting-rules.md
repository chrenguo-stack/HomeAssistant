# 本地开发与 AI 任务拆分规则

**文档状态：** 项目开发工作流规则  
**适用仓库：** `chrenguo-stack/HomeAssistant`  
**适用对象：** 参与本项目开发、测试、审查和交接的 AI 助手与开发者  
**生效原则：** 在不削弱安全、回滚、凭据隔离、CI 门禁和实机验收的前提下，优先利用已部署的本地环境缩短反馈时间。

## 1. 目标

当开发任务中存在可在用户本地 Mac 上安全运行的代码、检查或编译时，AI 应主动拆分任务，把适合本地执行的部分优先安排到本地环境，同时继续推进不依赖其结果的代码、文档、审查或 GitHub 工作。

核心目标：

1. 尽早获得本地快速反馈；
2. 避免每个小改动都推送并等待完整 CI；
3. 复用本地 Python、ESPHome、PlatformIO 和 ESP-IDF 工具链缓存；
4. 保留 GitHub CI 的干净环境复核和 required gate；
5. 不以本地测试替代 Docker、T1、实板或生产阶段门；
6. 在文件和接口互不冲突时拆分独立工作包。

## 2. 本地环境基线

环境可能变化时先执行：

```bash
gh-local status
```

当前已验证的基线：

| 项目 | 基线 |
|---|---|
| 操作系统 | macOS 12.7.6 |
| CPU 架构 | Intel x86_64 |
| 新开发与测试工作区 | `$HOME/HomeAssistant-local-test` |
| 历史工作区 | `$HOME/HomeAssistant`，保留旧分支和历史未跟踪文件，不作为新任务默认工作区 |
| Python | 3.11.9 |
| Python 虚拟环境 | `$HOME/.venvs/greenhouse-homeassistant-dev` |
| 本地统一入口 | `gh-local` |
| ESPHome | 2026.4.3 |
| ESPHome 路径 | `$HOME/.local/bin/esphome` |
| ESPHome 构建缓存 | `$HOME/.cache/esphome-greenhouse` |
| PlatformIO 缓存 | `$HOME/.platformio` |
| Docker | 当前本地不作为受支持测试能力使用 |

已验证能力：

- 公共仓库安全扫描；
- Ruff；
- pytest；
- greenhouse-manager 聚焦测试；
- simulator 测试；
- ESPHome `config`；
- ESP32-C6 最小目标编译；
- 完整 RC2 产品固件编译；
- 临时非生产 secrets 生成、日志泄漏检查与清理；
- 独立 Git worktree 保持干净。

## 3. AI 必须先做的任务分类

每个任务开始时先分为以下四类，不能默认全部串行推送到 GitHub。

### A. 可立即本地运行

- Ruff、格式和静态检查；
- pytest 单元测试和合同测试；
- 公共仓库安全扫描；
- YAML、JSON 和 schema 校验；
- ESPHome `config`；
- 已有缓存可复用的 ESP32-C6 编译；
- 纯 Python 工具、生成器、manifest 和离线检查；
- 不需要 Docker、真实 Broker、T1 或板卡的故障模型测试。

### B. 可在本地重型运行，但应与其他工作并行

- 完整 RC2 固件编译；
- 多个独立 ESPHome 目标编译；
- 较长 pytest 矩阵；
- 大型静态扫描；
- 固件 artifact 生成和校验。

AI 应先给出完整、可复制、带停止条件的本地命令。命令运行期间，可继续处理不修改相同构建输入的工作，例如测试审查、文档、PR 描述、故障分支设计和下一阶段命令准备。

### C. 必须由 GitHub CI 或隔离 Linux 环境完成

- Docker Compose；
- Mosquitto 或 Dynamic Security 隔离集成；
- M0/M1/M2 容器垂直链路；
- Ubuntu 干净环境复核；
- required checks；
- workflow、路径过滤、Runner 和 cache 行为；
- 当前 macOS 环境无法可靠提供的 Docker 能力。

本地通过不能替代这些检查。应在本地 fast 通过后再推送，减少 CI 因基础错误失败的次数。

### D. 必须由用户实机或生产阶段门完成

- ESP32-C6 实板烧录和传感器验证；
- LCD、RS485、Wi-Fi、LoRa 和电源行为；
- T1 只读探测、执行、回滚和提交后审计；
- 真实 Mosquitto、Home Assistant 和 greenhouse-manager 连续性；
- 任何生产凭据、授权或服务变更。

编译通过、模拟测试或本地 MQTT 测试不得表述为实机或生产验收完成。

## 4. 默认开发顺序

```text
确认唯一目标和文件范围
→ 使用独立分支或干净 worktree
→ 运行受影响模块的 focused test
→ 运行 gh-local fast
→ 固件变更运行 ESPHome config
→ 组件或板级变更运行必要本地编译
→ 汇总本地证据
→ 一次推送并创建或更新 PR
→ GitHub CI 完成干净环境和 Docker gate
→ 阶段结束时再执行实板或 T1 gate
```

禁止默认采用：

```text
改一小处 → push → 等 CI → 再改一小处 → 再 push
```

普通 PR 应尽量在 1～3 次远程推送内闭环。

## 5. 本地统一入口

### 5.1 状态检查

```bash
gh-local status
```

以下情况必须先检查状态：

- 新对话开始且本地环境可能变化；
- Python、ESPHome、Git 或缓存异常；
- 工作区或分支不确定；
- 本地结果与 CI 明显不一致；
- 距离上次环境验证较久。

### 5.2 快速测试

```bash
gh-local fast
```

当前入口覆盖：

- 公共仓库安全测试和扫描；
- greenhouse-manager 聚焦 Ruff 和 pytest；
- simulator Ruff 和 pytest；
- 前后 Git 工作区完整性检查。

除非定位具体失败、扩展尚未覆盖模块或修复 `gh-local` 本身，不应反复拼接等价长命令。

## 6. 分支与工作区

新开发默认使用：

```text
$HOME/HomeAssistant-local-test
```

修改前检查：

```bash
set -euo pipefail
cd "$HOME/HomeAssistant-local-test"
/usr/bin/git status --short --branch
```

从最新主分支创建任务分支：

```bash
set -euo pipefail
cd "$HOME/HomeAssistant-local-test"
/usr/bin/git fetch origin --prune
/usr/bin/git switch -c <branch-name> origin/main
```

规则：

1. detached HEAD 只用于验证，不直接开发；
2. 不对历史工作区执行未经确认的 `reset --hard`、清理或覆盖；
3. 不删除历史日志、未跟踪验收证据或缓存，除非单独确认清理范围；
4. 并行任务不得同时写同一文件、同一接口或同一分支；
5. 需要并行写入时使用独立 worktree、分支和明确文件所有权。

## 7. 本地编译

| 变更范围 | 默认本地动作 |
|---|---|
| 纯文档 | 不编译 |
| Python Manager 或 Simulator | `gh-local fast`，必要时扩大 focused pytest |
| YAML 参数或实体定义 | ESPHome `config` |
| external component Python/C++ | ESPHome `config` + 最小目标编译 |
| LCD、传感器、RS485、板级接口 | 完整 RC2 编译 |
| 工具链、ESPHome 或平台版本 | 最小目标 + 完整 RC2 编译 |
| 多个独立固件目标 | 可并行编译，但必须使用独立 build path |

缓存规则：

- 构建目录放在仓库外；
- 不提交 `.esphome`、生成配置或 secret substitution 结果；
- 不因小额清理提示执行 `pio system prune`；
- `$HOME/.platformio` 是已验证工具链缓存，不得默认整体删除；
- 只有磁盘不足或缓存损坏时才制定精确清理方案；
- 不得默认执行 `esphome clean-all` 或删除全部 ESPHome 缓存。

## 8. 临时 secrets

本地配置或编译使用临时非生产 secrets 时必须：

1. 使用保留测试地址和随机非生产值；
2. 创建前拒绝覆盖现有 `secrets.yaml`；
3. 权限设置为 `0600`；
4. 检查日志未打印临时密码；
5. 结束后通过 trap 或显式步骤删除；
6. 最后确认 Git 工作区没有意外变化；
7. 不使用 T1、真实 Wi-Fi、生产 Broker 或节点长期凭据。

## 9. 并行任务拆分

可以并行的条件：

- 输入、文件和接口范围互不冲突；
- 每个工作包有明确完成条件；
- 不依赖另一个尚未冻结的接口结果；
- 不重复执行同一昂贵测试；
- 最终能够通过一个集成 gate 汇总。

推荐示例：

```text
工作包 A：Manager 逻辑和 focused tests
工作包 B：ESPHome 适配器合同和 config 验证
工作包 C：协议、文档和 PR 说明
工作包 D：本地完整 RC2 编译
最终：gh-local fast + GitHub Full CI + 必要实机 gate
```

不得并行：

- 两个任务同时修改同一状态机；
- 一个任务更改 schema，另一个仍按旧 schema 编写 producer；
- 编译运行期间修改相同配置或组件；
- 接口未冻结时并行生成多个生产执行包；
- 任何绕过安全、回滚、授权或实机验证的拆分。

## 10. 给用户本地命令的输出合同

每次要求用户运行本地任务，应提供：

1. 任务目的；
2. 是否只读、是否修改文件；
3. 完整可复制命令；
4. 仓库、分支、虚拟环境和构建目录；
5. 预期成功标志；
6. 失败时需要返回的最小日志范围；
7. 明确停止条件；
8. 对 secrets、T1 和生产服务的影响。

命令应优先使用 `set -euo pipefail`，执行依赖和分支 preflight，输出结构化终态，并在结束后检查工作区变化。

## 11. 测试证据

本地结果至少记录：

- repository SHA；
- 分支名；
- 工作区是否干净；
- Python、ESPHome 和关键工具版本；
- 实际命令或统一入口；
- 通过的测试数量；
- 编译目标；
- 固件大小和 SHA-256；
- 临时 secrets 是否删除；
- 尚未执行的 gate。

PR 描述必须区分：

```text
Local passed/pending
GitHub CI passed/pending
Docker integration passed/pending
Board/T1 live passed/pending
```

不得把 `pending` 写成 `passed`。

## 12. 本地结果与 GitHub CI

- 本地 fast 通过后再推送；
- 本地编译通过后，CI 可按变更范围决定是否重复完整编译；
- required CI 不得因本地通过而跳过；
- CI 失败时先判断环境差异还是代码缺陷；
- 代码缺陷应先本地复现和修复，再推送；
- 不得通过反复 rerun 掩盖失败；
- Docker 相关结果以 GitHub CI 或受支持 Linux 环境为准。

## 13. 实机和生产安全边界

任何提速不得改变：

- 不重放已消费或过期授权；
- 不擅自关闭 anonymous MQTT；
- 不生成、读取或提交生产凭据；
- 不让本地测试连接生产 T1；
- 不让 CI 修改生产服务；
- 不以模拟、配置验证或编译代替实板；
- 不以本地 Broker 代替 T1 提交后审计；
- 写操作必须有明确授权、回滚和终态审计；
- 受保护服务和真实节点修改必须遵守 M2 阶段门。

## 14. AI 默认行为

后续 AI 应：

1. 主动识别可在本地完成的检查；
2. 修改代码前区分本地、CI 和实机三层测试；
3. 对可安全并行的工作明确拆分；
4. 优先复用 `gh-local`、现有虚拟环境和缓存；
5. 本地重型测试期间继续不冲突工作；
6. 本地失败时先定位首个根因，不立即推送试错；
7. 本地通过后尽量一次推送；
8. 明确 Docker、T1 和实板任务不可被本地环境替代；
9. 每轮只汇报增量结果、剩余 gate 和是否需要用户操作；
10. 达到完成条件后停止扩展。

## 15. 每任务检查表

### 开始前

- [ ] 已确认唯一目标和文件范围
- [ ] 已运行或确认 `gh-local status`
- [ ] 已区分本地、CI、实机任务
- [ ] 已识别可并行工作包
- [ ] 已确认安全边界

### 推送前

- [ ] focused test 已通过
- [ ] `gh-local fast` 已通过
- [ ] 固件变更已完成必要 config/compile
- [ ] 临时 secrets 已删除
- [ ] 工作区状态符合预期
- [ ] 本地证据已记录
- [ ] PR 已明确剩余 Docker/CI/Live gate

### 阶段结束

- [ ] GitHub required gate 状态明确
- [ ] 实板/T1 pending 或结果明确
- [ ] 未误报验收状态
- [ ] 缓存未被无必要清理
- [ ] 下一步不依赖隐含上下文

## 16. 与其他规则的关系

本规则补充 `docs/skills/greenhouse-github-development-efficiency/SKILL.md`，重点定义本地 Mac 能力、任务拆分和并行执行方法。

优先级：

1. 系统、开发者和用户明确指令；
2. 生产安全、授权、回滚和凭据隔离规则；
3. 根目录 `AGENTS.md`；
4. 项目开发效率 Skill；
5. 本规则；
6. 单个任务中的临时便利做法。

本规则不构成生产授权，也不允许 AI 自动执行 T1、Broker、Home Assistant、greenhouse-manager 或真实节点写操作。
