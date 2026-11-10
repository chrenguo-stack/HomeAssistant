# 外部项目工程经验参考库

> 文档性质：外部项目只读研究、架构对标与工程经验归档  
> 适用项目：温室环境监测系统（ESP32-C6 / N3-W / T1）  
> 首建日期：2026-11-10  
> 维护方式：长期滚动更新  
> Authority：REFERENCE_ONLY / NON_AUTHORITATIVE

---

## 0. 文档目的

本文件持续记录其他开源项目、公开产品实现和工程仓库中值得本项目学习的内容，同时记录不适合照搬的设计、已知风险和避坑经验。

目标：

1. 避免重复踩别人已经踩过的坑；
2. 用外部实现检查本项目是否存在架构盲区；
3. 优先吸收已经落地、可测试、可维护的工程实践；
4. 区分“理念值得借鉴”和“具体实现可以迁移”；
5. 把真正有价值的经验转化为本项目 ADR、设计任务、回归测试或产品化要求；
6. 不因外部项目的局部优点破坏本项目已经冻结的产品边界和 authority。

本文件不是 N3W_CURRENT_STATE.md、N3W_PROJECT_WORKING_CONTEXT.md、ADR、KNOWN_FAILURES_AND_REGRESSION_GUARDS.md 或 release / deployment authority 的替代。任何外部经验在进入正式实现前，都必须重新经过本项目自己的设计、源码、测试和安全边界审查。

---

## 1. 使用规则

每个外部项目至少记录：

| 字段 | 要求 |
|---|---|
| 项目名称 | 仓库或产品名称 |
| 来源 | 原始公开 URL |
| 复核版本 | exact commit / tag / release |
| 复核日期 | 实际阅读日期 |
| 关注范围 | 实际阅读的源码、文档、测试、部署文件 |
| 值得借鉴 | 为什么适合本项目 |
| 避坑点 | 潜在失败方式 |
| 不适合照搬 | 与本项目边界冲突的部分 |
| 可转化动作 | 可进入 ADR / design / CI / test / runbook 的候选项 |
| 状态 | CANDIDATE / ADOPTED / REJECTED / NEEDS_VALIDATION |
| License | 是否允许直接复用源码；未知时默认只学习思想 |

### 1.1 证据等级

- E1 — 文档声明：README、设计文档、博客；
- E2 — 源码实现：已经在源码中真实实现；
- E3 — 自动测试：存在针对该行为的测试；
- E4 — CI / 发布验证：进入自动化构建、容器或发布验证；
- E5 — 实际运行证据：有公开、可核验的现场或长期运行数据。

进入本项目设计时优先采用 E2 以上证据。只有 E1 的内容不得因为“写得很好”就视为成熟方案。

### 1.2 迁移原则

    外部发现
    → 本文件归档
    → 与本项目现状对照
    → 判断真实用户价值
    → 形成候选设计
    → 本项目独立源码设计
    → 本项目独立测试
    → 必要时 ADR / regression guard
    → 才成为正式能力

禁止直接照搬外部仓库结构、未经许可证确认复制源码、因外部项目功能丰富而扩大首版范围，或用 README 代替源码和测试复核。

---

# 2. 项目条目：blueteenwang/smarthome（HomeSense / 知家）

## 2.1 来源与复核范围

    PROJECT=blueteenwang/smarthome
    URL=https://github.com/blueteenwang/smarthome
    REVIEWED_BRANCH=main
    REVIEWED_HEAD=4e2050821a77aec138f603d1eaf931522a335062
    REVIEW_DATE=2026-11-10
    LICENSE_DECLARED=false

本轮重点复核 README、ARCHITECTURE、DESIGN、DEPLOY、UPGRADE 文档，Docker/Compose、CI、server.js、lib/ 中的状态/规则/账本/安全模块、对应测试，以及容器 smoke、数据备份迁移脚本。

该项目不是 ESP32 固件项目，而是运行在 Home Assistant 上层的本地智能决策与自动化服务，因此对本项目的主要参考价值集中在 T1 / greenhouse-manager / Home Assistant 主机侧、控制闭环、运行状态与产品化运维。

## 2.2 值得借鉴 A：控制命令区分“已下发”和“已验证”

外部项目把一次控制行为记录为连续生命周期：

    command.requested
    → command.dispatched
    → command.verifying
    → command.verified
       / command.accepted_unverified
       / command.failed

相关事件使用 correlation id 关联。执行接口返回成功后，代码还会有限次读取设备状态确认目标状态，不把一次 HTTP 接受直接等同于物理执行成功。

    E2_SOURCE_IMPLEMENTED=true
    E3_TESTED=true

这与本项目已有 COMMAND → RX_ACK → EXEC_RESULT 方向一致，但提示我们应进一步把控制命令统一成主机侧可审计生命周期。

未来控制节点可考虑：

    REQUESTED
    → RX_ACK
    → EXECUTING
    → EXEC_RESULT
    → FEEDBACK_VERIFIED
    → SUCCESS / FAILED / TIMEOUT / UNVERIFIED

其中 RX_ACK 只表示节点收到，EXEC_RESULT 表示本地输出已执行，FEEDBACK_VERIFIED 才表示外部反馈确认设备达到目标状态。

    STATUS=CANDIDATE_HIGH_VALUE
    TARGET=CONTROL_NODE + GREENHOUSE_MANAGER

## 2.3 值得借鉴 B：新自动化默认先观察，再真实执行

外部项目生成的新自动化默认进入 dry-run / observation：

- 条件真实评估；
- 命中会记录；
- 不实际控制设备；
- 目标设备存在歧义时不能授权；
- 观察命中与真实执行分开统计；
- 用户确认后才进入真实执行。

    E2_SOURCE_IMPLEMENTED=true
    E3_TESTED=true

这项机制非常适合农业现场。用户设置“温度超过 30℃ 开风机”时，直接生效会把阈值错误、传感器异常或设备绑定错误立即变成控制风险。

建议未来自动化生命周期：

    DRAFT
    → OBSERVE
    → READY_FOR_APPROVAL
    → ACTIVE
    → PAUSED / DISABLED

OBSERVE 阶段记录命中时间、计划控制对象、命中持续时间、输入数据新鲜度和冲突情况。

    STATUS=CANDIDATE_HIGH_VALUE
    TARGET=FUTURE_CONTROL_AUTOMATION

这是本轮外部研究最值得新增到本项目产品设计讨论的经验之一。

## 2.4 值得借鉴 C：过期、冲突和未知必须是正式状态

外部项目的状态模型包含更新时间、过期时间、来源和置信信息。证据过期后状态进入 unknown；多个可靠来源冲突时也不会强行得出确定结论。测试还明确覆盖“unknown 不能当成 false”。

本项目无需照搬复杂 confidence 模型，但适合建立更简单的数据新鲜度合同：

    value
    observed_at
    quality = ok | stale | fault | unavailable

自动控制必须满足：

    quality == ok
    AND
    age <= configured_threshold

必须避免：

    RS485 读取失败
    → 错误转换成 soil_moisture=0
    → 自动化判断极度干旱
    → 启动水泵

正确语义应是读取失败后进入 fault/unavailable，旧值不得作为新的可信控制输入。

该机制应建立在本项目已有 canonical state、BOOT_ID + SEQ、防旧路径回退之上，不建立第二套状态 authority。

    STATUS=CANDIDATE
    TARGET=CANONICAL_STATE + FUTURE_CONTROL_SAFETY

## 2.5 值得借鉴 D：关键事务使用轻量运行账本

外部项目使用 SQLite WAL 保存增长型运行事件和决策结果，并统计验证率、失败率和延迟。

本项目不应把环境 telemetry 再复制到 Manager 数据库，历史传感器数据继续优先交给 Home Assistant Recorder。但以下关键事务适合形成独立 Manager ledger：

- pairing；
- credential issuance / rotation / revoke；
- retirement；
- control command；
- config change；
- OTA；
- host deployment；
- recovery / rollback。

候选最小结构：

    event_id
    correlation_id
    node_id
    type
    started_at
    finished_at
    result
    error_code
    metadata

    STATUS=CANDIDATE
    TARGET=GREENHOUSE_MANAGER
    DO_NOT_DUPLICATE_TELEMETRY_HISTORY=true

## 2.6 值得借鉴 E：备份 / 迁移 / 恢复具有 manifest 和校验

外部项目的数据工具实现 backup / migrate / restore，并要求目标目录为新目录、不覆盖已有数据、备份不写入源目录内部、生成 SHA-256 清单、restore 前校验、迁移时保留旧目录用于回退，并要求服务停止后再做一致性备份。

这提醒我们：本项目对 release source、artifact 和部署事务已经很严格，用户运行数据本身也需要明确的恢复合同。

T1 后续应明确必须恢复资产，例如 SYSTEM_ID、系统 CA / key、Manager canonical DB、MQTT credential authority、node registrations、friendly name / area、产品自动化配置和必要升级状态。

候选方向：

    backup_manifest.json
    + file inventory
    + checksum
    + schema/version
    + restore eligibility
    + rollback boundary

外部项目的备份安全级别不能照搬。本项目包含系统 CA 和节点身份，必要时应增加加密备份和更严格 secret handling。

    STATUS=CANDIDATE_HIGH_VALUE
    TARGET=T1_GOLDEN_MASTER + FIRSTBOOT + BACKUP_RECOVERY

## 2.7 值得借鉴 F：CI 验证“删除并重建容器后状态仍存在”

外部项目的 container smoke 不是只做 build 或 restart，而是真正执行：

    build
    → synthetic config
    → isolated container start
    → health check
    → 写入持久化 marker
    → stop
    → rm container
    → create new container
    → health check
    → 验证 marker / SQLite 仍存在

这说明产品化 CI 应持续区分 container restart 与 container rm + recreate。

本项目建议确认长期 CI 中存在或补充：

    CONTAINER_DELETE_RECREATE_PERSISTENCE=PASS

至少覆盖 Manager canonical store、Broker credential store、SYSTEM_ID authority、node registry 和运行配置。

    E2_SOURCE_IMPLEMENTED=true
    E3_SCRIPTED_TEST=true
    E4_CI_INCLUDED=true
    STATUS=CANDIDATE_HIGH_VALUE
    TARGET=T1_CI

## 2.8 值得借鉴 G：现场恢复文档应比研发文档短很多

外部项目的升级 / 回退文档把用户操作压缩成 stop → backup → migrate → start → verify；失败则停止新版、恢复旧备份、使用旧版本启动。

本项目的研发证据与 release integrity 文档继续保持严格，但正式产品还应有面向售后/安装人员的独立短文档：

    T1_FIELD_RECOVERY_RUNBOOK

原则：

- 1～2 页；
- 不讲 ADR 历史；
- 不要求用户理解 Docker / MQTT 内部机制；
- 每一步明确 PASS / FAIL；
- FAIL 时明确 STOP；
- 不与研发 authority 文档混写。

    STATUS=CANDIDATE
    TARGET=PRODUCTIZATION + FIELD_SUPPORT

---

# 3. smarthome 中不建议照搬的部分

## 3.1 不把 AI / 视觉模型变成本项目基础依赖

HomeSense 的核心价值依赖摄像头和模型理解，符合其产品定位；温室系统则必须在 Wi-Fi、T1、MQTT、Internet 均不可用时继续本地采集、LCD 显示和必要保护。未来即使加入 AI 农业建议，也只能是可选上层能力。

    STATUS=REJECT_AS_CORE_DEPENDENCY

## 3.2 不在运行时用模糊名称决定真实控制对象

外部项目源码留下过设备模糊匹配过宽的历史教训。农业现场误控制水泵、风机、加热设备风险更高。

本项目继续坚持：

    friendly_name / area = human display
    NODE_ID / exact entity binding = execution identity

自然语言可以帮助配置阶段找到设备，但授权完成后必须固化为确定目标。

    STATUS=REJECT_RUNTIME_FUZZY_BINDING

## 3.3 不采用超大型单入口服务结构

外部仓库当前 server.js 体量较大，HTTP、设备控制、AI、媒体、自动化和状态逻辑仍有集中。这适合个人原型快速迭代，不适合作为本项目长期方向。

本项目继续保持 Manager / Broker / HA、privileged updater 与 Manager、各 authority 的职责隔离。

    STATUS=REJECT_MONOLITHIC_DIRECTION

## 3.4 不照搬共享 LAN token 作为设备身份安全模型

外部项目的 localhost/LAN token/Bearer/Basic/CORS 模型对单用户家庭原型合理，但不能替代本项目已有 Setup Secret、pairing、独立 MQTT credential、TLS、ACL、revoke 和节点身份生命周期。

值得借鉴的是“扩大监听范围等于扩大信任边界”的原则，不是共享 token 实现。

    STATUS=REJECT_AS_IDENTITY_MODEL

## 3.5 警惕文档与实现漂移

本轮发现该仓库部分早期架构文档仍描述旧的配置和持久化状态，而新代码已出现 environment config、runtime directory、SQLite ledger、backup / migration / restore。

本项目应继续坚持 current state、current state index、ADR、working context、exact source/artifact authority、handoff 和 release integrity，并在架构变化后及时收敛旧文档。

    STATUS=ANTI_PATTERN

---

# 4. 从 smarthome 提炼出的候选工作项

本节只记录候选，不自动改变当前计划或授权。

| ID | 候选工作项 | 价值 | 当前状态 |
|---|---|---:|---|
| EXT-001 | CONTROL_COMMAND_LIFECYCLE_LEDGER | 高 | CANDIDATE |
| EXT-002 | AUTOMATION_OBSERVE_MODE | 很高 | CANDIDATE |
| EXT-003 | CANONICAL_DATA_FRESHNESS_CONTRACT | 高 | CANDIDATE |
| EXT-004 | MANAGER_CRITICAL_EVENT_LEDGER | 中高 | CANDIDATE |
| EXT-005 | T1_BACKUP_MANIFEST_AND_RESTORE_INTEGRITY | 高 | CANDIDATE |
| EXT-006 | CONTAINER_DELETE_RECREATE_PERSISTENCE_CI | 高 | CANDIDATE |
| EXT-007 | T1_FIELD_RECOVERY_RUNBOOK | 中高 | CANDIDATE |

只有正式 source design / ADR / CI 修改完成后，才能把状态改为 ADOPTED。

---

# 5. 跨项目经验索引

以后新增外部项目时，把可复用经验同时归并到本节，避免知识只散落在单个条目中。

| 主题 | 经验 | 来源项目 | 本项目状态 |
|---|---|---|---|
| 控制可靠性 | 下发成功和最终状态验证必须分开 | smarthome | CANDIDATE |
| 自动化安全 | 新规则先观察，后授权真实执行 | smarthome | CANDIDATE |
| 数据质量 | stale / conflict / unknown 显式表达 | smarthome | CANDIDATE |
| 可观测性 | 关键事务使用关联 ID 和运行账本 | smarthome | CANDIDATE |
| 备份恢复 | manifest + checksum + fresh restore | smarthome | CANDIDATE |
| 容器产品化 | rm + recreate 后验证持久化 | smarthome | CANDIDATE |
| 现场维护 | runbook 独立于研发文档 | smarthome | CANDIDATE |
| 控制目标 | 模糊名称不可作为运行时执行身份 | smarthome | GUARD |
| 架构维护 | 文档漂移作为工程风险管理 | smarthome | GUARD |

---

# 6. 新项目追加模板

以后追加项目时至少包含：

    PROJECT=
    URL=
    REVIEWED_BRANCH=
    REVIEWED_HEAD=
    REVIEW_DATE=
    LICENSE_DECLARED=

并依次记录：

1. 项目定位和与本项目的可比层级；
2. 实际复核范围；
3. 值得借鉴的做法及 E1～E5 证据；
4. 避坑点和失败方式；
5. 不适合照搬的部分；
6. 对本项目的 guard；
7. 可转化工作项 EXT-xxx；
8. TARGET / EXPECTED_VALUE / VALIDATION_REQUIRED；
9. 最终状态 CANDIDATE / ADOPTED / REJECTED / NEEDS_VALIDATION。

---

# 7. 维护约束

1. 每次外部项目研究固定到 exact commit / tag，不只写 main。
2. Stars 数量不影响证据等级。
3. 不因为某设计“先进”就默认适合个人开发者和农业现场。
4. 优先记录源码、测试、CI 已证明的工程实践。
5. 失败案例、修复提交和回退经验通常比 feature list 更有价值，应优先记录。
6. 安全、身份、OTA、备份、控制等高风险领域必须独立设计与验证。
7. License 不明确时，只学习思想、接口边界和测试方法，不直接复制实现源码。
8. 经验转化为正式 ADR / regression guard / source design 后，本文件保留来源，但正式 authority 指向内部文件。
9. 允许记录“我们比外部项目做得更好”的部分；目的不是模仿，而是持续减少复杂度、提高可靠性和开发效率。
