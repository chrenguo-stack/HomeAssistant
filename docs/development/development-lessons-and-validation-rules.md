# 开发经验与验证规则

**文档状态：** 持续维护的项目开发指导  
**适用仓库：** `chrenguo-stack/HomeAssistant`  
**适用对象：** 参与本项目设计、开发、测试、审查、打包、实机验证和交接的开发者与 AI 助手  
**首次建立：** 2026-07-30  
**维护原则：** 发现可复用的经验、验证缺口、流程分叉或重复失误后，应在相关 PR 中同步更新本文件。

## 1. 目的

本文件用于把开发过程中已经付出成本才发现的问题，转化为后续可重复执行的规则、检查项和回归测试，避免同类问题再次消耗开发、CI、授权和实机测试时间。

本文件不是阶段交接文档，也不是某一个 D2 请求的执行记录。它保存跨阶段仍然有效的工程经验，包括：

- 哪类设计容易放大错误概率；
- 为什么原有测试没有发现问题；
- 后续必须增加什么验证；
- 在什么条件下必须暂停继续叠加修复；
- 哪些结论必须进入自动化测试，而不能只留在对话或交接文档中。

## 2. 与其他仓库规则的关系

开发工作还应同时遵循：

- `AGENTS.md`；
- `docs/skills/greenhouse-github-development-efficiency/SKILL.md`；
- `docs/development/local-ai-task-splitting-rules.md`；
- `docs/development/module-lifecycle-rules.md`；
- 当前阶段的 ADR、合同、交接文档和明确授权边界。

系统指令、安全边界、用户明确决策、生产授权和不可重放规则始终优先。本文件不会授权实板、生产、凭据、Broker、Flash、ACTIVATE、CLEANUP、发布或部署操作。

## 3. 何时必须更新本文件

出现以下任一情况时，相关开发 PR 必须评估是否更新本文件：

1. 同一类错误在不同阶段重复出现；
2. CI 通过，但私有包、目标 Mac、实板或生产前检查失败；
3. 单元测试通过，但完整调用链失败；
4. 初始化、绑定、导入或打包顺序改变结果；
5. 公共构建路径与私有交付路径不等价；
6. 错误信息只暴露通用外层错误，无法直接定位叶子原因；
7. 一次性授权因可在 host-only 阶段发现的代码错误被浪费；
8. successor 层数增加，使状态、接口或测试边界难以判断；
9. 用户需要重复执行本可自动化的诊断命令；
10. 发现能明显减少后续开发时间或降低风险的新方法。

## 4. 经验记录格式

新增经验应使用以下格式，历史条目不得静默删除：

```markdown
### LESSON-YYYYMMDD-NNN：标题

- 状态：ACTIVE / SUPERSEDED / RETIRED
- 发现阶段：
- 现象：
- 影响：
- 安全边界：
- 根因：
- 为什么原验证没有发现：
- 永久规则：
- 必须增加的自动化测试：
- 关联 PR / commit / failure code：
- 后续修订：
```

记录应满足：

- 写事实，不写模糊归因；
- 区分直接原因、根本原因和放大因素；
- 明确是否到达 USB、串口、esptool、Flash、Broker、PREPARE 或 VERIFY；
- 不记录秘密值、生产凭据、私密路径或不应公开的授权内容；
- 把经验转化成可执行规则和测试，而不是只写“以后注意”。

## 5. 当前确认的高风险开发模式

### 5.1 多层动态包装器会产生组合风险

当前部分执行链通过上层模块动态覆盖下层模块的：

- `contract`；
- `STAGE`；
- `D2_REQUEST_ID`；
- schema；
- payload 摘要；
- parser；
- `install()`；
- `validate_authorization()`；
- core 常量和环境变量。

因此，单层函数测试通过不等于最终组合正确。任何修改动态绑定的工作，都必须验证最终完整链，而不能只验证当前新增的一层。

### 5.2 初始化顺序可能成为隐含配置

当“先 bind 再生成授权”和“先生成授权再 bind”得到不同结果时，系统存在顺序依赖。顺序依赖必须显式化、冻结并测试，不能依赖调用者记住正确顺序。

### 5.3 公共 CI 与私有交付路径分叉

公共 CI、公共 Artifact、私有包生成、目标 Mac `static-check` 和最终 `execute` 如果使用不同入口或不同字段生成逻辑，CI 通过不能证明私有交付正确。

### 5.4 只修复当前叶子错误会不断增加 successor 复杂度

add-only successor 能保护历史证据和不可变性，但每增加一层，也增加新的绑定、错误转换、打包入口和测试组合。当连续出现 host-only 或 preclaim 失败时，必须先做局部稳定化，而不是继续机械叠加下一层。

### 5.5 一次性授权会放大验证缺口的成本

一次性、不可重放、失败关闭是正确的安全设计。但凡是能够在 host-only 完整预检中发现的错误，都不应留到授权后或用户执行时发现。

## 6. 强制验证方法

### 6.1 先完成绑定和冻结，再生成授权

授权生成前必须按固定顺序执行：

```text
加载完整继承链
→ 完成全部 bind/install
→ 冻结最终执行身份
→ 导出冻结清单
→ 校验各层读取值一致
→ 生成授权
→ 再次校验冻结值未变化
```

冻结清单至少包括：

- `STAGE`；
- `D2_REQUEST_ID`；
- `AUTH_SCHEMA`、`RESULT_SCHEMA`；
- immutable payload TAR SHA-256；
- recovery payload TAR SHA-256；
- execution package SHA-256；
- request binding；
- execution closure；
- Python、OpenSSL、esptool、Mosquitto 等受约束可执行文件摘要；
- 授权字段清单及字段清单摘要。

授权生成函数不得从仍可能被后续 `bind()` 或 `install()` 修改的模块全局变量直接取值。

### 6.2 公共和私有流程必须共用 canonical builder

公共 CI 的测试包、私有交付包和目标 Mac 静态检查应调用同一个 canonical builder。允许不同的只有授权权限和有效期，不允许存在独立复制的字段拼装逻辑。

### 6.3 必须运行真实交付顺序的端到端 host-only 测试

测试入口必须尽量复现用户实际路径：

```text
归档解压
→ shell launcher
→ private outer controller
→ 当前 successor wrapper
→ 全部继承层
→ 原始 inherited authorization validator
→ claim 前停止
```

不得只直接调用中间函数来替代整条路径。

### 6.4 必须设置硬件调用哨兵

host-only 测试中，应把以下边界替换成“调用即失败”的哨兵：

- USB 枚举；
- 串口打开；
- esptool；
- Flash/NVS；
- Broker 启动；
- 网络访问；
- PREPARE；
- VERIFY。

完整 preclaim 通过的同时，所有哨兵调用计数必须为零。

### 6.5 必须保留叶子错误

外层错误可以提供阶段性概括，但结构化结果必须同时保存最内层稳定失败码。禁止只输出类似：

```text
FULL_PREFLIGHT_CHECK_FAILED
```

而丢失真正的：

```text
AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH
```

公开错误结果不得泄露秘密值，但应提供足够的 expected/actual 摘要、失败阶段和安全边界状态。

### 6.6 必须证明交付等价性

至少证明以下三者的执行输入等价：

- CI 验证的执行包；
- 私有包中的执行包；
- 目标 Mac `static-check` 实际验证的执行包。

等价性证据至少包括：

- 文件清单；
- 每个文件 SHA-256；
- 模块入口；
- shell 参数顺序；
- 环境变量清单；
- 最终冻结绑定。

### 6.7 物理决策门必须后移

物理执行决策只能在以下条件全部满足后显示：

1. 公共 exact-head CI 全部通过；
2. load-bearing Artifact 未过期且摘要正确；
3. 私有包创建侧完整真实顺序 preclaim 通过；
4. 目标 Mac `static-check` 通过；
5. 授权未 claim、未 consume；
6. PR、SHA、CI、Artifact 和执行包未漂移；
7. 所有物理哨兵为零。

## 7. 交付前检查清单

### 7.1 公共 PR 前

- [ ] 失败根因已绑定到稳定 failure code；
- [ ] 修复不是只覆盖单一表面症状；
- [ ] 完整继承链测试已设计；
- [ ] 真实 shell 入口已测试；
- [ ] 路径包含空格和 macOS 路径规范化已覆盖；
- [ ] 未包含授权 JSON、秘密值、符号链接或 Python bytecode；
- [ ] 历史失败请求保持不可重放。

### 7.2 私有包创建前

- [ ] 完整链已 bind/install；
- [ ] 最终执行身份已冻结；
- [ ] 授权由冻结身份生成；
- [ ] 生成后冻结值没有改变；
- [ ] 原始 inherited validator 已实际运行；
- [ ] 公共和私有构建器是同一实现；
- [ ] 私有包与公共 Artifact 的继承来源已验证。

### 7.3 请求用户运行 `static-check` 前

- [ ] 创建侧执行了与目标 Mac 相同的入口和参数顺序；
- [ ] 完整 leaf failure 能被结构化输出；
- [ ] 失败不会 claim 或 consume 授权；
- [ ] 所有硬件调用哨兵为零；
- [ ] 命令使用当前活动目录，不使用过期文件目录；
- [ ] 文件名唯一且不覆盖旧证据；
- [ ] 明确说明当前不授权 `execute`。

### 7.4 请求物理执行前

- [ ] 目标 Mac `static-check=PASS`；
- [ ] exact PR/SHA/CI/Artifact 重新复核；
- [ ] 授权和执行决策均在有效期内；
- [ ] 一次性、不可重放、不可自动重试；
- [ ] PREPARE、VERIFY、locked recovery 次数和范围明确；
- [ ] ACTIVATE、CLEANUP、生产、Ready、merge、release、tag、deploy 均未授权；
- [ ] 命令执行后的证据文件和停止条件明确。

### 7.5 失败后

- [ ] 立即停止，不自动重试；
- [ ] 判断授权是否 created、claimed、consumed；
- [ ] 确认是否到达物理边界；
- [ ] 收集最小充分的结构化证据；
- [ ] 旧请求、授权、决策和包的终态明确；
- [ ] 先判断是单点修复还是需要稳定化；
- [ ] 新增回归测试后才能创建后继；
- [ ] 将可复用经验更新到本文件。

## 8. 何时必须暂停 successor 叠加并稳定化

满足以下任一条件时，应暂停创建新的私有包或物理授权，先做局部稳定化：

- 连续两个 successor 在 host-only 或 preclaim 阶段失败；
- 同一字段在不同层被多次覆盖；
- 测试结果依赖导入、bind 或 install 顺序；
- 公共 CI 与私有创建流程使用不同 builder；
- 无法用一张清单说明最终字段来源；
- 外层只能返回通用错误，必须人工复现才能得到叶子错误；
- 新增一层需要同时修改三层以上的 contract、parser 或 validator 绑定；
- 用户连续执行了本应在 CI 或创建侧发现的失败测试。

稳定化的最小目标是：

```text
一个 canonical builder
+ 一个冻结执行身份
+ 一个完整 host-only preclaim 入口
+ 一组硬件哨兵
+ 一份交付等价性证据
```

这类局部稳定化不等于全项目架构重构，但在继续物理测试前是必要条件。

## 9. 初始经验记录

### LESSON-20260730-001：继承接口兼容符号必须在完整安装路径验证

- 状态：ACTIVE
- 发现阶段：H3/N2 Stage 2D-9R G3R D2-14
- 现象：继承的 D2-11 `install()` 访问缺失的 `canonical_package_digest`，在解析和物理操作前退出。
- 影响：一次已授权调用失败，未到达物理边界。
- 安全边界：authorization 未 claim；USB、串口、esptool、Flash、Broker、PREPARE、VERIFY 均未执行。
- 根因：新 contract 没有完整实现继承安装路径所需接口。
- 为什么原验证没有发现：测试覆盖了新层逻辑，但没有实际执行继承的 `install()`。
- 永久规则：新增或替换 contract 时，必须运行完整继承安装路径，并校验所需符号清单。
- 必须增加的自动化测试：真实 shell 驱动的 inherited install preflight。
- 关联 failure code：`CONTRACT_COMPATIBILITY_SYMBOL_MISSING_CANONICAL_PACKAGE_DIGEST`。

### LESSON-20260730-002：新合同通过不能替代原始 inherited validator

- 状态：ACTIVE
- 发现阶段：H3/N2 Stage 2D-9R G3R D2-15
- 现象：静态检查通过，但执行在 preclaim 阶段因 `AUTHORIZATION_STAGE_MISMATCH` 终止。
- 影响：授权被终态消费，但未 claim，未到达物理边界。
- 安全边界：USB、串口、esptool、Flash、Broker、PREPARE、VERIFY 均未执行。
- 根因：静态检查只运行新合同校验和安装预检，没有执行原始 inherited authorization validator。
- 为什么原验证没有发现：把“新层合同正确”误当成“完整继承授权链正确”。
- 永久规则：任何授权包在交付前都必须通过原始 `_BASE_VALIDATE_AUTHORIZATION` 或其唯一 canonical 等价入口。
- 必须增加的自动化测试：完整 inherited field inventory、字段缺失回归、preclaim 非 claim/非 consume 验证。
- 关联 failure code：`AUTHORIZATION_STAGE_MISMATCH`。

### LESSON-20260730-003：授权必须由绑定后冻结的最终身份生成

- 状态：ACTIVE
- 发现阶段：H3/N2 Stage 2D-9R G3R D2-16
- 现象：公共测试通过，但目标 Mac `static-check` 报完整 inherited authorization preflight 失败；精确叶子原因为 payload TAR 摘要不匹配。
- 影响：授权未 claim、未 consume，未到达物理边界，但私有包和授权必须退役。
- 安全边界：USB、串口、esptool、Flash、Broker、PREPARE、VERIFY 均未执行。
- 根因：公共测试在绑定后生成测试授权，私有流程在绑定前生成授权；后续 bind 改变了执行器读取的 payload 摘要。
- 为什么原验证没有发现：CI 与私有交付没有使用相同的真实顺序和 canonical builder。
- 永久规则：必须先完成完整 bind/install 并冻结最终执行身份，再由冻结身份生成授权；生成后任何身份变化都必须失败关闭。
- 必须增加的自动化测试：错误顺序必须失败、正确顺序必须通过、公共与私有 builder 等价性、payload digest 冻结回归。
- 关联 failure code：`AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH`。

## 10. 持续维护规则

1. 新经验优先追加到“经验记录”，并同步把永久规则放入相应章节；
2. 历史记录不删除。结论被替代时标记 `SUPERSEDED`，并链接新条目；
3. 只有已经有证据支持的结论才能写成强制规则；
4. 每条强制规则应尽可能对应自动化测试、CI gate 或结构化 preflight；
5. PR 只写“已吸取经验”不算完成，必须同时有代码、测试、清单或流程变化；
6. 阶段交接文档应引用本文件，而不是复制一份容易过期的完整内容；
7. 每次连续失败或重大流程调整后，应复核本文件是否仍与仓库实际实现一致。

## 11. 开发效率衡量

本文件的目标不是增加文档负担，而是降低以下数量：

- 用户本可避免的命令执行次数；
- 只因字段、顺序或打包分叉造成的 CI 失败；
- 在目标 Mac 才首次暴露的 host-only 错误；
- 因可预检错误而作废的一次性授权；
- 为同一根因重复创建的 successor；
- 需要人工比对的摘要和字段；
- 无法直接定位叶子原因的失败。

新增规则应优先自动化。不能自动化时，才保留人工检查项，并说明为什么当前无法自动化。
