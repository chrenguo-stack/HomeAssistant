# 本地开发与 AI 任务拆分规则

**文档状态：** 项目开发工作流规则  
**适用仓库：** `chrenguo-stack/HomeAssistant`  
**适用对象：** 参与本项目开发、测试、审查和交接的 AI 助手与开发者  
**生效原则：** 在不削弱安全、回滚、凭据隔离、CI 门禁和实机验收的前提下，优先利用已部署的本地环境缩短反馈时间。

## 1. 规则目标

本规则用于告诉 AI：当一个开发任务中存在可以在用户本地 Mac 上安全运行的代码、检查或编译时，应主动拆分任务，将适合本地执行的部分优先安排到本地环境完成，同时继续推进不依赖该结果的代码、文档、审查或 GitHub 工作，以减少重复等待和不必要的远程 CI 消耗。

核心目标：

1. 尽早获得本地快速反馈；
2. 避免每个小改动都推送并等待完整 CI；
3. 利用本地已缓存的 Python、ESPHome、PlatformIO 和 ESP-IDF 工具链；
4. 保留 GitHub CI 的干净环境复核和 required gate；
5. 不以本地测试替代 Docker、T1、实板或生产阶段门；
6. 在可以安全并行时，把一个大任务拆成多个互不冲突的工作包。

## 2. 当前本地开发环境基线

AI 在规划本地任务前，应先确认以下基线仍然有效；如环境状态不确定，先执行 `gh-local status`，不要凭历史信息直接假定。

| 项目 | 当前基线 |
|---|---|
| 操作系统 | macOS 12.7.6 |
| CPU 架构 | Intel x86_64 |
| 新开发与测试工作区 | `/Users/chenrenguo/HomeAssistant-local-test` |
| 历史工作区 | `/Users/chenrenguo/HomeAssistant`，保留旧分支和历史未跟踪文件，不作为新任务默认工作区 |
| Python | 3.11.9 |
| Python 虚拟环境 | `/Users/chenrenguo/.venvs/greenhouse-homeassistant-dev` |
| 本地统一入口 | `gh-local` |
| ESPHome | 2026.4.3 |
| ESPHome 路径 | `/Users/chenrenguo/.local/bin/esphome` |
| ESPHome 构建缓存 | `/Users/chenrenguo/.cache/esphome-greenhouse` |
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

## 3. AI 必须先做的任务拆分判断

每个开发任务开始时，AI 必须先把工作分为以下四类，而不是直接把所有步骤串行推送到 GitHub：

### A. 可立即本地运行

典型内容：

- Ruff、格式和静态检查；
- pytest 单元测试和合同测试；
- 公共仓库安全扫描；
- YAML、JSON、schema 校验；
- ESPHome `config`；
- 已有缓存可复用的 ESP32-C6 编译；
- 纯 Python 工具、生成器、manifest 和离线检查；
- 不需要 Docker、真实 Broker、T1 或板卡的故障模型测试。

### B. 可在本地重型运行，但应与其他工作并行

典型内容：

- 完整 RC2 固件编译；
- 多个 ESPHome 目标的独立编译；
- 较长 pytest 矩阵；
- 大型静态扫描；
- 生成和校验固件 artifact。

AI 应先准备一个完整、可复制、带停止条件的本地命令，让用户开始执行；在等待输出期间，继续处理不依赖结果的工作，例如：

- 编写或审查测试；
- 更新文档和 PR 描述；
- 审查变更范围；
- 准备下一阶段命令；
- 检查 GitHub 现有代码和 CI 结构；
- 设计失败分支和诊断输出。

不得把用户留在无反馈等待状态，也不得在本地编译运行期间同时修改同一构建输入而导致结果失效。

### C. 必须由 GitHub CI 或隔离 Linux 环境完成

典型内容：

- Docker Compose；
- Mosquitto/Dynamic Security 隔离集成；
- M0/M1/M2 容器垂直链路；
- Ubuntu 干净环境复核；
- required checks；
- 路径过滤、workflow、Runner 和 cache 行为；
- 当前 macOS 12 本地无法可靠提供的 Docker 能力。

本地通过不能替代这些检查。AI 应在本地 fast 通过后再推送，减少 CI 因基础错误失败的次数。

### D. 必须由用户实机或生产阶段门完成

典型内容：

- ESP32-C6 实板烧录和传感器验证；
- LCD、RS485、Wi-Fi、LoRa 和电源行为；
- T1 只读探测、执行、回滚和提交后审计；
- 真实 Mosquitto/Home Assistant/greenhouse-manager 连续性；
- 任何生产凭据、授权或服务变更。

AI 不得把编译通过、模拟测试或本地 MQTT 测试表述为实机或生产验收完成。

## 4. 默认开发顺序

除非任务性质明确要求其他顺序，默认采用：

```text
确认唯一目标和变更范围
→ 在独立分支或干净 worktree 修改代码
→ 运行受影响模块的本地 focused test
→ 运行 gh-local fast
→ 固件相关变更运行 ESPHome config
→ 组件、构建或硬件接口相关变更运行必要的本地编译
→ 汇总本地证据
→ 一次推送并创建/更新 PR
→ GitHub CI 完成干净环境和 Docker gate
→ 阶段结束时再进行实板/T1 gate
```

禁止默认采用：

```text
改一小处
→ push
→ 等 CI
→ 再改一小处
→ 再 push
```

普通 PR 应尽量在 1～3 次远程推送内闭环。

## 5. 本地统一入口

### 5.1 环境状态

```bash
gh-local status
```

AI 在以下情况应先要求执行该命令：

- 新对话开始且环境状态可能变化；
- Python、ESPHome 或 Git 命令异常；
- 工作区、分支或缓存路径不确定；
- 本地结果与 CI 明显不一致；
- 距离上次验证较久。

### 5.2 快速测试

```bash
gh-local fast
```

当前入口包含：

- 公共仓库安全测试；
- 安全扫描器执行；
- greenhouse-manager 聚焦 Ruff 和 pytest；
- simulator Ruff 和 pytest；
- 前后 Git 工作区完整性检查。

AI 不应在每次任务中重新拼接等价的长命令，除非：

- 需要定位某个失败步骤；
- 需要扩展到尚未包含的模块；
- `gh-local` 本身正在开发或损坏；
- 需要单独记录某个 focused test 的证据。

## 6. 分支与工作区规则

1. 新开发默认使用 `/Users/chenrenguo/HomeAssistant-local-test`。
2. 开始修改前必须检查：

```bash
cd /Users/chenrenguo/HomeAssistant-local-test
/usr/bin/git status --short --branch
```

3. detached HEAD 只适合验证，不适合直接开发。修改前应从最新 `origin/main` 创建明确分支：

```bash
/usr/bin/git fetch origin --prune
/usr/bin/git switch -c <branch-name> origin/main
```

4. 不得对历史工作区执行 `git reset --hard`、无确认清理或覆盖。
5. 不得删除旧工作区中的历史日志、未跟踪验收证据、`.DS_Store` 或缓存，除非单独确认其用途和清理范围。
6. 并行任务修改相同文件、相同接口或相同分支时，不得并行写入；应先划分文件所有权或建立独立 worktree/分支。

## 7. 本地编译规则

### 7.1 何时需要编译

| 变更范围 | 默认本地动作 |
|---|---|
| 纯文档 | 不编译 |
| Python Manager/Simulator | `gh-local fast`，必要时扩大 focused pytest |
| YAML 参数或实体定义 | ESPHome `config` |
| external component Python/C++ | ESPHome `config` + 最小目标编译 |
| LCD、传感器、RS485、板级接口 | 完整 RC2 编译 |
| 工具链、ESPHome 版本、平台版本 | 最小目标 + 完整 RC2 编译 |
| 多个独立固件目标 | 可分组并行编译，但避免争用同一 build path |

### 7.2 缓存和构建目录

- 构建目录应放在仓库外；
- 不要把 `.esphome`、生成配置或 secret substitution 结果提交到 Git；
- 不要因为 9～10 MiB 的清理提示执行 `pio system prune`；
- `$HOME/.platformio` 当前约 11 GiB，主要是已验证工具链，应视为加速缓存；
- 只有磁盘空间不足或缓存损坏时，才制定精确清理方案；
- 不得默认执行 `esphome clean-all`、删除整个 `.platformio` 或删除全部 ESPHome 缓存。

### 7.3 临时 secrets

本地配置或编译使用临时非生产 secrets 时，必须：

1. 使用保留测试地址和非生产随机值；
2. 创建前拒绝覆盖现有 `secrets.yaml`；
3. 文件权限设为 `0600`；
4. 检查日志未打印临时密码；
5. 结束后通过 trap 或显式步骤删除；
6. 最后确认 Git 工作区无变化；
7. 不使用 T1、真实 Wi-Fi、生产 Broker 或节点长期凭据。

## 8. 并行任务拆分规则

AI 可以把一个大任务拆为并行工作包，但必须满足：

- 输入和文件范围互不冲突；
- 每个工作包有明确完成条件；
- 不依赖另一个尚未确定的接口结果；
- 不重复执行同一昂贵测试；
- 可在最后通过一个集成 gate 汇总。

推荐拆分示例：

```text
工作包 A：实现 Manager 逻辑和 focused tests
工作包 B：准备 ESPHome 适配器合同和 config 验证
工作包 C：更新协议/文档/PR 说明
工作包 D：本地执行完整 RC2 编译
最终：gh-local fast + GitHub Full CI + 必要实机 gate
```

不推荐拆分：

- 两个任务同时修改同一状态机；
- 一个任务更改 schema，另一个在旧 schema 上写 producer；
- 编译运行期间更改相同配置和组件；
- 未固定接口就并行生成多个生产执行包；
- 为加快速度绕过安全、回滚、授权或实机验证。

## 9. AI 给用户本地命令时的输出合同

每次要求用户运行本地任务，AI 应提供：

1. 任务目的；
2. 是否只读、是否修改文件；
3. 完整可复制命令；
4. 使用的仓库、分支、虚拟环境和构建目录；
5. 预期成功标志；
6. 失败时需要粘贴的最小日志范围；
7. 明确停止条件；
8. 对 secrets、T1 和生产服务的影响说明。

命令应尽量：

- 使用 `set -euo pipefail`；
- 使用明确绝对路径或已验证统一入口；
- 先做磁盘、分支、文件和依赖 preflight；
- 生成结构化终态；
- 结束后检查 `CHANGES=0` 或列出预期变化；
- 避免要求用户手工拼接多个摘要、路径和环境变量。

## 10. 测试证据记录

本地结果至少记录：

- repository SHA；
- 分支名；
- 工作区是否干净；
- Python、ESPHome 和关键工具版本；
- 实际执行的命令或统一入口；
- 通过的测试数量；
- 编译目标；
- 固件大小和 SHA-256；
- 临时 secrets 是否删除；
- 哪些 gate 尚未执行。

PR 描述应区分：

```text
Local passed
GitHub CI pending/passed
Docker integration pending/passed
Board/T1 live pending/passed
```

不得把 `pending` 写成 `passed`。

## 11. 本地结果与 GitHub CI 的关系

本地测试的作用是提前发现问题、减少远程推送和复用缓存；GitHub CI 的作用是提供干净环境、跨平台和 required gate。

规则：

- 本地 fast 通过后再推送；
- 本地编译通过后，CI 可按变更范围选择是否重复完整编译；
- required CI 不得因本地通过而被跳过；
- CI 失败时，先判断环境差异还是代码缺陷；
- 若是代码缺陷，先在本地复现并修复，再推送；
- 不得通过反复 rerun 掩盖失败；
- Docker 相关结果以 GitHub CI 或受支持 Linux 环境为准。

## 12. 实机和生产安全边界

任何提速不得改变以下规则：

- 不重放已消费或过期授权；
- 不擅自关闭 anonymous MQTT；
- 不生成、读取或提交生产凭据；
- 不让本地测试连接生产 T1；
- 不让 CI 修改生产服务；
- 不以模拟、配置验证或编译代替实板；
- 不以本地 Broker 代替 T1 提交后审计；
- 写操作必须有明确授权、回滚和终态审计；
- 受保护服务和真实节点的修改必须遵守现有 M2 阶段门。

## 13. AI 默认行为

后续 AI 在本项目中应：

1. 主动识别可在本地完成的检查，不等待用户提醒；
2. 在修改代码前给出本地、CI、实机三层测试计划；
3. 对可以并行的工作包明确拆分，而不是全部串行等待；
4. 优先复用 `gh-local`、现有虚拟环境和已缓存工具链；
5. 在本地重型测试运行期间继续不冲突工作；
6. 本地失败时先定位首个根因，不立即推送试错；
7. 本地通过后尽量一次推送；
8. 对 Docker、T1 和实板任务明确标记为不可由当前本地环境替代；
9. 每轮只汇报增量结果、剩余 gate 和是否需要用户操作；
10. 达到当前完成条件后停止扩展，不无边界增加测试或重构。

## 14. 每任务检查表

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
- [ ] PR 中明确剩余 Docker/CI/Live gate

### 阶段结束

- [ ] GitHub required gate 状态明确
- [ ] 实板/T1 pending 或结果明确
- [ ] 未误报验收状态
- [ ] 缓存未被无必要清理
- [ ] 下一步不依赖隐含上下文

## 15. 与其他规则的关系

本规则补充 `docs/skills/greenhouse-github-development-efficiency/SKILL.md`，重点定义用户本地 Mac 的能力、任务拆分和并行执行方法。

优先级从高到低：

1. 系统、开发者和用户明确指令；
2. 生产安全、授权、回滚和凭据隔离规则；
3. 仓库根目录 `AGENTS.md`；
4. 项目开发效率 Skill；
5. 本规则；
6. 单个任务中的临时便利做法。

本规则不构成生产授权，也不允许 AI 自动执行 T1、Broker、Home Assistant、greenhouse-manager 或真实节点写操作。
