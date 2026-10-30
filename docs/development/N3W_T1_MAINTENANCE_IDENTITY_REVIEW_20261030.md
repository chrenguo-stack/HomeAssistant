# N3-W T1 生产维护与 Portable Release Identity V1 独立架构复核

日期：2026-10-30（Asia/Singapore）。性质：只读评审与设计建议；不是已批准的产品合同、部署包或生产恢复授权。

## 1. 结论

根本诊断成立：项目至少三次在不同执行器中把构建端 Docker 镜像 ID 当成跨主机发布物身份，导致正确镜像被拒绝。问题还包括执行器、授权、运行状态、故障恢复之间没有统一边界，不能只把一个 ID 替换成另一个 ID。

建议保留三层身份划分，形成一个主机侧公共镜像校验模块、一个版本化发布合同，以及一个小型、可恢复的主机维护事务工具。复用现有 systemd、Compose 和产品注册协调逻辑；不引入新的常驻平台。

当前 E03 建议保留现场，随后通过**新授权的后继恢复事务**完成恢复；不为旧的一次性事务事后赋予通用 resume 权限。未来新建的维护事务可以在原授权明确涵盖的范围内自动恢复，不需要每次 SSH 会话重新授权。

重要范围修正：ADR-0009 已被 ADR-0010 取代，Golden Master / Final Seal / 克隆路线已退役。公共组件迁移不得重新激活这些路线。当前正式生产路线是逐台官方 Armbian 安装与自动产品部署。

## 2. 证据绑定与限制

| 项目 | 本轮核实值 |
|---|---|
| repository main | `2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e` |
| PR #725 | OPEN / DRAFT；不是 main；基于 R8 测试分支 |
| PR #725 HEAD | `614c08a397462850f0167b77c9da45ae69a323ad` |
| HEAD tree | `9fb33d6ca3e0d665e45924229048b3b502091ccc` |
| live executor blob | `c46a2a180ce62d54d6d1eb3c0e296f9c55bef0f5` |
| SSH transport blob | `dec4c9159195e2008094d94fef3fc76c4b977e46` |
| 目标 Manager 源码 | `f8876fd87165df731d792690a8288867c3eeef55` |
| artifact run / ID | `40880705472` / `12900601779` |
| GitHub artifact SHA256 | `c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183` |
| artifact 状态 | API 核实未过期；归档约 2.54 GB |
| Manager tar SHA256 | `d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5`，来自冻结源码与已有取证 |
| 既有聚焦测试 | 46 passed / 33 deselected；Python 3.12.14 |
| 本轮 T1 / 板卡访问 | 无 |
| 本轮 GitHub 写入、CI dispatch、合并 | 无 |
| 本轮仓库源文件修改 | 无；复核 checkout 保持干净 |

本轮通过 GitHub API 和只读 Git 获取重新绑定了 main、PR、执行器、讨论记录与 artifact 元数据。独立检查了指定历史文档和关键源码、测试，并运行纯本地测试和隔离复现。

**没有重新下载 2.54 GB artifact、重新解析真实 tar，也没有读取当前 T1。** 现场 tar/config/manifest 摘要与生产状态属于 PR 中已归档的实测证据；本轮独立验证的是这些证据与源码行为、上游合同是否一致。不得把本评审写成 fresh T1 acceptance 或完整 artifact 字节复验。

main 的 current state/index 仍以 10 月 27 日 R5 交接为入口；PR 分支含 R10 增量，最新 E03 现场进展主要在 PR Conversation。不能只看 main 的顶部进度就断言 R10 未发生，也不能把 PR 内容说成已合并。

上位来源已核对：V0.7 的首次初始化退出、身份连续性和恢复边界；V0.5 的 T1 备份/健康检查目标；20260816 简化规划的单一事实来源和 session/claim/evidence 收敛原则。其产品目标支持本报告，但不构成现场写入授权。

## 3. 按任务书要求输出

```text
OVERALL_ASSESSMENT=总体方向成立；必须删去退役克隆路线，并先修复事务安全缺口
ROOT_CAUSE_ASSESSMENT=跨主机镜像身份合同错误，加上重复实现和恢复边界缺失
HISTORICAL_RECURRENCE_CONFIRMED=true
RECURRENCE_COUNT_OR_PATTERN=至少3次现场同类误停；KF098已更早具备正确机制
CURRENT_E03_RUNTIME_SAFETY=已有证据支持短期保留旧运行栈；不能承诺长期无故障或首次注册可用
CURRENT_E03_TRANSACTION_DISPOSITION=保留原始记录与已加载镜像；后续追加可审计的切换前终止/接替记录
RESUME_OR_SUCCESSOR_TRANSACTION=当前选择新授权的后继恢复事务；未来正式事务支持预定义resume
THREE_IDENTITY_MODEL=发布内容身份／主机本地对象绑定／生产部署与健康合同
KEEP_CHANGE_OR_REJECT=KEEP_WITH_CHANGES
PORTABLE_IMAGE_IDENTITY_MINIMAL_CONTRACT=可信发布入口→精确tar→已验证的config/manifest内容图→目标本地绑定→运行容器绑定
FIELDS_TO_KEEP=可信manifest摘要、tar摘要与大小、config摘要、适用的manifest/index摘要、平台、顺序diff_ids验证、部署引用
FIELDS_TO_DROP=重复的archive manifest与selected record独立权威字段；重复且无新增证明力的派生哈希
FIELDS_TO_RECLASSIFY_AS_HOST_LOCAL=Docker.Id、container.Image、容器ID、StartedAt、restart_count、tag当前指向、存储后端
MAINTENANCE_TRANSACTION_MODEL=PREPARING→READY→APPLYING→VERIFYING→COMMITTED；ROLLING_BACK→ROLLED_BACK；BLOCKED或ABORTED
AUTHORIZATION_VS_TRANSACTION_MODEL=授权绑定一次事务；事务拥有持久状态；执行会话可多次；代码/目标/范围改变需重新批准
CURRENT_CANDIDATE_PREVIOUS_MODEL=保留三个逻辑角色；一个previous；不保留三份完整tar
DATABASE_MIGRATION_MODEL=首版优先无schema变更；声明旧新读写兼容；必要迁移有一致备份、幂等日志与明确回退门
APP_DOCKER_OS_LIFECYCLE_SPLIT=同意三种维护生命周期；共享全局互斥与兼容检查
COMMON_COMPONENT_BOUNDARY=主机侧标准库Python模块；纯解析/验证与Docker采集分离；不依赖Manager运行
REPOSITORY_AUDIT_REQUIRED=true；已完成54文件候选扫描及关键链路语义复核，尚非全部调用点审计关闭
GLOBAL_REGRESSION_GUARDS=活动入口登记、共用验证调用约束、受控例外、真实双store矩阵、故障注入与反向测试
FALSE_PASS_RISKS=自签式摘要链、仅RootFS/标签校验、事务错绑定、未知Compose覆盖、未验证MQTT就提交
FALSE_STOP_RISKS=单一.Id、空值合成差异、把index当manifest、把暂未就绪当永久失败、用瞬时状态否定健康
OVERENGINEERING_RISKS=复活Golden Master、一次迁移所有历史脚本、三份tar、通用编排平台、无必要多重状态
MINIMAL_PRODUCTION_ARCHITECTURE=一个版本化发布合同＋一个校验模块＋一个主机事务入口＋既有systemd服务owner
CURRENT_E03_RECOVERY_PLAN=源码修复和隔离证明→新只读现场绑定→新授权的后继恢复事务→严格验收
MIGRATION_PLAN_P0=冻结现场；完成当前恢复设计及必要源码安全修复；先形成公共校验的最小内核
MIGRATION_PLAN_P1=完善公共镜像合同与双store测试；已有修复不得再复制为私有版本
MIGRATION_PLAN_P2=迁移当前维护入口，落实日志、重入、回滚、服务owner和业务验收
MIGRATION_PLAN_P3=迁移当前逐台fresh install/bootstrap及其CI生产者，保留首次初始化边界
MIGRATION_PLAN_P4=迁移活动rollback/restore/F4/F5验证；Golden Master仅历史隔离
MIGRATION_PLAN_P5=完成调用点分类、关闭临时例外、禁用已退役生产入口
SOURCE_REPAIR_REQUIRED=true
NEW_BLOCKER_COUNT=4
TOP_BLOCKERS=B1事务错绑定；B2未知Compose覆盖；B3断电恢复与服务owner竞争；B4运行验收不足
NEXT_ONE_GATE=N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_DESIGN_FREEZE_20261030_01
```

计数口径：B1—B4 是本轮在已知 single-.Id 缺陷以外新增确认的源码/维护准入阻断组。已知镜像误停另计；Golden Master 退役和全仓迁移是设计范围修正，不混入新增缺陷计数。B3、B4 阻断将当前执行器作为可靠生产维护入口，不表示本次已发生停机或 MQTT 中断。

## 4. 源码发现与阻断证据

以下路径和行号均绑定 PR HEAD `614c08a3...`。

### 已知问题：single-.Id 在三个环节存在

`tools/n3w_t1_r10_e03_manager_successor_refresh_live.py`：

- 613—615：preclaim 拒绝目标 tag 的非构建端 ID，抛出 `target_tag_wrong_image`。
- 994—995：remote apply 仍要求该单一 ID。
- 1033—1039：切换后 Manager 容器 Image 又与同一个构建端 ID 比较。

因此仅修改 preclaim 会使下一层继续失败；仅修改加载后检查也可能在切换后错误触发回滚。必须让三个阶段消费同一个已验证的目标本地绑定。

PR 最新取证中的 `7751d4...` 与 exact tar 的 OCI manifest 摘要一致，`089153...` 与 config 摘要一致。上游 Moby #51934 的维护者明确解释了 classic config 与 containerd manifest/index 的差异。这支持当前误停归因，不能用该结论推导“任何不同 ID 都应通过”。

### B1：记录了事务权威，却未在 apply 入口完整消费

`read_tx()`（717）校验文件和 schema；`remote_claim()`（742）存入 authorization、executor、source、artifact；`_remote_apply_locked()`（990）只核对 status、consumed、replay 三项。

入口没有核对精确 phase、授权 ID 与其摘要一致性、目标 release/artifact 与运行代码的一致性，也没有把当前执行器绑定回记录中的 executor blob。`remote-apply` 是不接收这些绑定参数的直接入口。

隔离注入不匹配 phase、target source、executor blob 后，入口仍到达 image check。此复现证明入口缺少检查，不声称已经绕过全部后续检查或获得远程攻击权限。威胁是错误工具/错误事务的重入与恢复，不是假设恶意 root 可以被 Python 校验阻止。

**修复条件：** 每次进入都验证 host、transaction、authorization、release、操作范围、允许的 executor 版本和现实状态；互斥锁覆盖所有写入口；旧格式必须显式迁移或拒绝。

### B2：发现未知 Compose 漂移后，回滚可能覆盖它

`restore_compose()`（924—931）只在 `candidate_sha is not None` 时拒绝未知当前摘要。

具体路径：claim 后、apply 前 Compose 被第三方修改；preclaim 或 `preapply_compose_drift` 抛错，此时 `candidate_sha=None`、`stopped=False`；异常处理调用 rollback，再调用 restore_compose；它用刚读到的未知当前摘要作为 atomic_replace 的 expected_sha，把未知内容覆盖成旧备份。

这是可直接复现的越界写入，不只是理论风险。临时文件隔离测试输出 `UNKNOWN_COMPOSE_OVERWRITTEN=True`。

**修复条件：** 没有证明发生本事务写入时，只记录停止，不恢复文件。发生写入后只接受已冻结的 before/after 两种摘要；unknown 保留并 BLOCKED。写前记录候选摘要和操作意图；不要用当前未知文件的摘要临时授权覆盖。

### B3：异常回滚不是断电恢复，且 Compose 发布早于停止 owner

`_remote_apply_locked()`（1000—1032）的 `stopped`、`candidate_sha` 只在内存中。Compose 替换后才写 COMPOSE_REPLACED；systemd stop 后才写 SERVICES_STOPPED。进程被杀、SSH 中断导致远端终止、主机断电等不保证走 Python except；未实现针对这些持久中间阶段的恢复判定器。

更关键的是：候选生产 Compose 先替换，现有前台 Compose owner 后停止。在该窗口，owner 自动重启或主机重启可能读取候选 Compose，越过预期的切换边界。事务锁不约束 systemd 自动启动。仅检查最终 NRestarts 无法防止已经发生的提前启动。

**修复条件：** 原子保存写前意图；加入单机维护互斥及可持久恢复的 activation gate；先禁止 owner 非预期启动并停 Manager+HA，证明静止后再发布候选生产绑定。恢复器在 owner 启动前判定 before/after/unknown；未知时停止受影响的应用组，Broker按兼容条件继续运行。通过独立的主机执行会话完成维护，SSH只查看/控制，不能让连接寿命承担事务寿命。

### B4：当前“提交成功”没有证明 MQTT 和业务连续性

`wait_services()`（910）只等 active unit 和两个运行容器。随后检查端口监听、镜像、网络模式、重启次数、HA MQTT 配置摘要与 E03 ledger，直接写 COMMITTED（1051）。

配置没变不代表 HA 已连上 Broker；端口在监听也不代表 Manager 已认证、订阅和处理数据。没有有界收敛等待与稳定观察，会同时导致瞬时未就绪的误停，以及 MQTT 未恢复却提交成功的风险。仓库 F4 已有进程归属 socket 与稳定窗机制（`_manager_runtime_stability`，3624附近），KF-130也已有就绪竞争的先例，应复用原理。

**修复条件：** readiness允许在期限内等待；acceptance保持严格。验证 Manager/HA 的真实 MQTT 会话或已有认证会话证据、正确进程归属、服务稳定窗口、E03 startup reconciliation和业务状态。若没有已注册节点，telemetry 应明确 NOT_APPLICABLE 并以受控非生产探针证明链路，不能伪造“实节点连续”。

### 其他需要纳入实现的边界

- `image_id()`（300）把所有 inspect 非零退出都变成不存在；应区分 NOT_FOUND、daemon不可达、超时和权限错误。
- `docker load` 在主机包装器中执行，不在远端 apply 的持久阶段记录内；状态中的 `t1_mutation=false` 不能被解释为从未修改过 T1。
- 不能仅修正瞬时错误码，仍把完整根因吞为 `postclaim_failure`；保留经过白名单净化的失败阶段、原因、最后已证明状态、恢复允许动作。
- 当前 R10 缺少完整空间准入和全局维护互斥；公共工具需要补齐，但不据此推断本次是磁盘不足。

## 5. 历史重复与现有组件评价

| 证据/代码 | 真实合同 | 结论 |
|---|---|---|
| 20261011 staging live progress 第11节；KF-106 | exact tar加载成功，单config ID误停并回滚 | 第1个本轮可核实现场案例 |
| 20261012 bootstrap R3；KF-111 | HA加载成功后因跨store ID差异清理 | 第2个现场案例 |
| 20261030 PR725取证 | config与manifest分别对应CI/T1观察值 | 第3个现场案例 |
| KF098 `verify_loaded_exact_image()`（236） | 已冻结config/manifest二选一，另查平台、入口、用户、RootFS | 有可复用思路；仍是硬编码历史专用执行器 |
| staging `_image_report()`（687） | config/target识别，Descriptor存在时核对，平台检查 | 另一套独立实现 |
| fresh bootstrap `_verify_runtime_image()`（468） | 允许任意合法格式的runtime ID，验证平台、顺序RootFS、十个Config字段 | 可抽取纯验证逻辑；它证明内容/行为等价，不是通用的原始config字节身份验证器 |
| deployable payload workflow内嵌Python | 解析tar/config、冻结多种哈希、比较CI inspect | 生产者逻辑也必须收敛；不能只抽运行端 |
| Golden Master build `_image_bindings()` / seal `_verify_images()` | 从artifact复制image_id，seal直接与本地.Id比较 | 潜在同类历史缺陷；路线已退役，不列为当前发布阻断 |
| F5 V2 `n3w_t1_production_v2_contract.py` | 已有release_id、source、artifacts及规范化hash校验 | 优先版本化扩展/引用；不要另建平行的release权威 |

R4/R6 已认识到 RootFS 相同但 Config 不同会改变行为，这个历史结论正确。但“抽取已有代码”不是“原样复制一个旧 validator 并宣布全部闭环”。必须先统一身份语义、输入生产者、目标采集和验证结果。

## 6. 三层身份与最小镜像合同

三层保留，但第三层应称“生产部署与健康合同”，因为端口、重启次数、MQTT和数据库状态不都是身份。

| 层 | 权威 | 使用方式 |
|---|---|---|
| 发布内容 | 可信release manifest及其指向的artifact内容 | 跨主机验证；与Docker本地字段无关 |
| 主机绑定 | 当前host/store epoch上的镜像和容器对象 | 同宿主机连续性、引用固定、回滚定位 |
| 生产合同 | 当前release的Compose/unit/持久状态/实际健康 | 证明正确版本在正确配置下提供业务 |

最小可信链：受信的发布批准或签名 → manifest摘要 → tar摘要/大小 → 从tar实际计算的config、manifest/index及layer绑定 → 目标store中同一内容图 → 被启动容器的本地绑定 → 实际部署合同。

SHA256只能证明内容一致，不能独自证明发布者。若tar和同目录manifest都被替换，互相对得上的哈希没有用。研发P0可以使用来自受信GitHub、已批准精确源码及新恢复计划中冻结的摘要；正式离线交付应校验发布公钥签名或等强的独立可信manifest摘要。信任GitHub账户/发布密钥、主机root和Docker daemon；它们全部失陷时不能承诺“不可伪造”。

| 字段 | 最小处理 |
|---|---|
| release_id、source commit/tree | 保留现有出处绑定；release_id定义唯一，不形成另一个并行身份 |
| tar SHA256、size | 必须；对应确切交付字节；重打tar即是新的交付对象 |
| config digest | 必须；读取原始config字节计算，不hash inspect合成JSON代替 |
| OCI manifest digest | 有OCI manifest时保留，并验证它确实引用上述config及层；Docker-only旧包允许明确为空 |
| OCI index/target digest | 仅artifact存在index时保留；验证选中的linux/arm64子manifest关系；不能和manifest混名 |
| ordered RootFS diff_ids | 必须验证顺序和内容；可从已校验config派生，不必再维护独立手填哈希 |
| Config contract | 保留版本化语义校验与诊断；从可信config派生，通常无需另一个独立权威hash |
| platform | 必须；包括适用variant；不能只看tag |
| tag/deployment ref | 保留为定位和部署约束，不是安全身份 |
| Docker archive manifest/selected-record hash | 可留诊断；在tar摘要和安全解析已完整约束后不必独立冻结为多个authority |
| image.Id、container.Image | 限定在公共适配层解释，并产出host-local binding |

最低实现只支持实际发行的linux/arm64、已知Docker archive/OCI layout；未知格式或无法选择唯一平台时明确STOP，不要尝试猜。解析器需拒绝重复成员、路径穿越、symlink冒充、重复JSON键、缺失blob、摘要/size不一致、歧义平台，并限制资源使用。流式哈希避免内存加载整个tar。

**Q5的取舍：不全面禁用.Id。** 禁止执行器直接用“CI .Id == T1 .Id”作身份判定；允许公共适配层将目标.Id与已由artifact内容证明的config/manifest/index摘要匹配，并验证平台与内容合同。不要仅凭Docker版本猜后端，也不要把任意两个外部字符串加入白名单。

本地表示未被支持时返回 `UNSUPPORTED_REPRESENTATION`，可经已验证的配置/内容读取路径进一步确认；不能降级成“tag对、能启动就PASS”。当前两种已知表示应有直接支持，避免本次误停重复。

Config只对证明等价的null/空形式做规范化。保留Env、Cmd、Entrypoint和layer顺序；不随意排序Env或抹去未知行为字段。新的Docker字段必须有兼容规则。完整inspect对象、Size、GraphDriver、RepoDigests列表、LastTagTime、Descriptor可用性和容器时间戳都不是跨主机release字节身份。

## 7. 最小公共组件和发布格式

公共组件放在主机工具层，使用标准库Python；不放进必须先启动Manager才能调用的运行路径。推荐三个职责，而不是三个部署服务：

1. 纯模块：解析release/image record、tar/OCI、验证摘要关系；无subprocess、网络和生产写操作。
2. Docker适配器：有界读取实际版本、能力、image/container信息，产出规范化观察。
3. 验证入口：返回带schema的 VERIFIED / MISMATCH / UNSUPPORTED / UNAVAILABLE 和host-local binding。

维护工具调用公共模块；自包含执行包打包同一模块及其hash。禁止通过复制源码得到另一份独立实现。升级用的host工具自身版本/hash也必须绑定，不能在事务中途静默更新。

仓库已有F5 V2 release schema。建议通过显式schema升级或引用一个image-set子合同扩展它；既有release文件仍按旧版本解释，不原地修改旧哈希。下面是概念最小结构，不是本轮已实现schema：

```yaml
schema: n3w.app-release/1
release_id: hash-of-defined-canonical-material
source: {commit: exact, tree: exact}
compatibility_profile: tested-host-profile-digest
images:
  manager:
    archive: {sha256: exact, size: exact}
    platform: linux/arm64
    config_digest: exact
    manifest_digest: present-if-available
    index_digest: present-if-available
    deployment_ref: release-scoped-tag
deployment_contract_sha256: exact
state_contract:
  readable_schema: explicit-set-or-range
  writable_schema: explicit-set-or-range
  migration_id: none-or-versioned
  rollback_policy: no-migration-or-tested-compatible
```

签名放外部envelope，避免摘要自引用。公共配置、Compose和unit合同必须被release绑定；不能只有镜像身份而漏掉行为配置。GitHub run/artifact ID适合出处记录，不应成为离线运行时每次启动必须联网查询的条件。

## 8. 维护状态机、断电和授权

PRECHECK是只读动作，不必占一个持久状态。正常持久阶段建议仅：PREPARING、READY、APPLYING、VERIFYING、COMMITTED；补ROLLING_BACK、ROLLED_BACK、BLOCKED、ABORTED。阶段内用versioned operation记录before/after，不为每条命令新增大状态。

每次变更：锁定主机维护权 → 校验现实状态 → 持久写入意图和before/after摘要 → fsync文件/父目录 → 执行动作 → 独立读回 → 写完成。单个原子JSON记录可满足首版，包含generation、操作序号、最后错误和证据摘要；无需新数据库集群或事件平台。

| 中断处 | 重入行为 |
|---|---|
| staging中断 | 校验已到达字节和tag；仅恢复本事务stage；正确镜像可复用，错误同名tag不覆盖 |
| 操作前意图存在、操作可能未发生 | 分别验证before和after；before才执行，after只补记；两者都不符则BLOCKED |
| 应用组停止后断电 | boot恢复器先于activation owner运行；根据持久决定启动旧版或完成已批准切换 |
| 候选已启动、COMMIT未落盘 | 重新POSTCHECK，满足才提交；不从头load或重建业务状态 |
| 回滚中断 | 同样依据before/after继续；原镜像缺失或DB不兼容则BLOCKED |
| COMMIT已落盘、SSH返回失败 | 查询事务终态；不得把成功事务重新执行一次 |

授权、事务、会话三个ID分开。授权绑定目标host、源/目标release、允许的executor或兼容策略、动作范围、回滚范围、有效期和预定义resume规则。一次授权只能claim到一个事务；会话只是某次连接或执行尝试。过期如何处理进行中的恢复应事先声明，不能每次断线重新解释。

维护锁需覆盖app、Docker、OS三类维护以及相关生产变更工具。变更前重新验证关键prestate，但不能把正常增长的telemetry序号或整个活跃DB文件hash要求永远不变。恢复时按业务不变量判定。

服务owner继续使用 `n3wfc4-services-activation.service`，Manager与HA作为现有联合组停启。Broker仅在当前app升级兼容、无需改其配置/凭据时保持运行；Broker自身升级必须有独立维护计划。不要把“Broker永远不能停”冻结为不可能维护的产品规则。

候选隔离检查不仅需要 `--network none`，还应禁止Docker socket、生产秘密和生产写挂载，使用只读根文件系统、限额、临时状态。离线检查不能代替真实MQTT验收。

## 9. Current / Candidate / Previous、空间与数据库

三个逻辑角色值得保留。CURRENT是最后成功提交的期望发布，APPLYING/VERIFYING期间实际运行可能已经是candidate；查询界面必须同时显示事务和观察状态，不把指针当现实。

提交用一个原子records更新，包含current、previous和candidate，避免三个文件半更新。只保留一个previous；它必须包括可启动的旧镜像、旧deployment合同、manifest和状态兼容说明。共享不变的HA/Broker层，不等于三套完整栈复制。

正常不同时保留三份tar。Mac/发布归档保留完整包；T1逐镜像传输，校验后加载并绑定；成功staging后可释放普通tar副本。事务引用的镜像必须保护，拒绝自动prune。**本次失败现场的目标镜像和取证材料例外保留，不在本轮清理。**

空间准入按真实文件系统分别预算：临时传输、压缩content、解包snapshot、数据库备份、日志和恢复余量；不把Docker Size视为峰值，也不假设所有层都能去重。已有fresh transport的一次一个镜像方案可复用。仅在COMMITTED且观察期结束后清理无引用的旧对象；永远先验证下一次rollback所需对象仍存在。

数据库首版最小可靠策略：

- 普通升级优先不改schema；同时检查Manager、HA和Broker各自持久状态兼容性。
- 需要迁移时声明读/写兼容集合、迁移ID、是否事务内完成、回滚方式；不能只给一个 `rollback_compatible=true` 自证。
- SQLite迁移在受控静止写边界或可靠backup API上建立一致备份；不能直接复制活跃WAL数据库主文件。
- 优先新增可选表/列，使旧版仍能读取新状态；只有真实跨版本需要时使用expand→migrate→contract，不把每次发版都变成三期工程。
- 破坏性contract推迟到旧版回滚观察期结束；先做断电/半迁移/旧版启动测试。
- 备份恢复不是免费的image rollback。新版本运行后已有注册、凭据撤销或业务写入时，恢复旧DB可能丢数据或让已撤销节点复活；需同步考虑Registry、key/replay store、DynSec、CA及HA。默认拒绝这类自动旧备份回滚，优先前向修复或单独批准的协调恢复。
- E03启动协调清理与schema迁移分开：让Manager自身完成过期事务协调；不手工DELETE SQLite，不复活原配对attempt。

## 10. App / Docker / OS 生命周期

拆分合理，且符合ADR-0010。发布合同说明兼容条件，不自动执行Docker/OS升级。安装可以冻结一个已验证host profile，app更新使用明确支持的版本/能力集合；不要写无限上界的“Docker >= 某版本”。

image-store backend属于兼容性、容量和本地绑定metadata，不是release内容身份。版本不等于后端：升级机器和全新安装可使用不同store。

Docker重大版本升级先在隔离主机验证：当前与previous镜像load/inspect/create、Compose profile与owner、TLS/MQTT、资源峰值、重启、断电、恢复；迁移store前确认旧镜像在新store是否可用。不得在app事务中顺手切换backend。OS升级作为更高风险维护，保留外部身份/状态备份与恢复途径，不自动引入整盘A/B架构。

## 11. 当前 E03 恢复方案

当前证据支持维持旧栈等待源码修复；没有已证明的紧急重启必要。但新注册被过期ACTIVE占住，旧Manager缺陷未消除，不能将现状长期作为合格产品状态。也不能仅凭restart_count=0承诺数据长期完整。

**选择后继事务的理由：** 原授权明确绑定旧executor和一次性流程，原执行器没有成熟resume合同；现在要改校验、回滚和状态边界。直接追加resume会同时改变执行器权威和授权解释。当前停在切换前，使用一个明确引用旧事务的后继恢复计划更容易审计，也更符合ADR-0010既有规则。

恢复步骤（全部为未来计划，本轮未执行）：

1. 源码阶段修复已知身份缺陷及B1—B4。建立共用校验最小内核，不先复制一个只给R10用的新validator。
2. 冻结新恢复计划：旧authorization hash、旧transaction原始摘要、旧executor blob、新executor/hash、相同目标artifact、新host绑定、允许操作、服务owner和回滚条件。
3. 新只读现场rebind：旧事务仍CLAIMED/AUTHORIZATION_CLAIMED；原始claim未变；目标镜像内容图正确；Compose/unit/env、旧Manager、HA、Broker状态符合；E03仍未提交；磁盘/回滚镜像/DB兼容合格。不要只看phase推断无变更。
4. 新明确授权允许：记录旧事务的终止/接替关系，复用已验证candidate，联合应用组切换、产品启动协调、验收及限定回滚。禁止重用旧authorization或重新remote-claim旧事务。
5. 在全局锁下保留旧记录原始字节；追加 `ABORTED_PRECUTOVER_STAGED_IMAGE_RETAINED` 或等价处置记录，并绑定successor ID。不能写成“从未修改主机”，因为load已经发生；不能删除旧记录为固定TX_PATH腾位置。
6. successor在自己的唯一事务路径下执行；正确已加载镜像直接复用，不再load/tag/rmi。candidate验证后，先控制owner，停Manager+HA，再原子发布绑定并启动。
7. 验证镜像/部署、Broker连续性、Manager与HA MQTT、服务稳定、E03终态EXPIRED/TERMINAL/COMPLETE、unresolved=0以及业务/身份不变量，才COMMIT。首次注册需要新配对会话，不能重放失败会话。
8. 失败时只按可证明的状态回滚；未知Compose、DB或凭据状态保留并BLOCKED。保留所有原始取证和新的净化摘要。

如果日后选择“同一transaction＋新recovery grant”，也必须显式绑定新代码和旧记录，不能称为原授权自然允许。对当前一次恢复，它比后继事务更复杂，故不推荐。

## 12. 全仓审计和CI防回归

首轮在tools、Manager源码和workflows中检索image_id、image inspect、.Id、container.Image，命中54个文件。这是候选范围，不是54个缺陷；字符串扫描也不能证明漏报为零。

| 类别 | 已核实样例 | 处理 |
|---|---|---|
| A artifact/release | R10目标ID、fresh archive producer、KF098目标内容 | 统一公共校验；producer与consumer一起迁移 |
| B host-local continuity | R10 `broker_continuity()`、当前已观测旧Manager/HA/Broker ID | 保留，绑定host/store epoch；不外推跨主机 |
| C container continuity | F4 `_manager_runtime_stability()`中的容器Id/StartedAt | 正确用法，保留 |
| D rollback binding | KF098 `bind_old_rollback_image()`、R10 predecessor引用 | 保留本地绑定，同时证明rollback release内容和可用性 |
| E logging/fingerprint | backup与readonly probe的image元数据 | 可以记录，不把记录自动升级成release authority |
| 易误判的A类元数据检查 | clean_product_deployment_gate的image lock字段比较、R10 preflight目标参数比较 | 比较的是冻结元数据，不等于跨store运行ID比较，不能机械删除 |
| 待追溯调用者 | `ops/n3w_exact_image_one_shot.py`的expected_image_id | 参数可能来自同host，也可能来自构建侧；必须查来源和所有调用点后定性 |
| 退役路线 | Golden Master build/seal、历史诊断包 | 保留历史；禁止成为新生产入口；不为统一而重做功能 |

每个调用点审计记录：路径/函数、producer、consumer、ID类型、来源host、用途A—E、活动/历史状态、所属发布入口、守卫与迁移负责人。函数同时承担多类用途时按调用点拆，不强行按文件只分一类。

CI分层：

- 快速：登记活动维护入口；AST/文本规则找可疑比较、直接Docker inspect和内嵌workflow validator；跨host校验必须调用公共模块。例外记录用途、owner和移除条件。静态规则只做门禁，不能假装理解全部语义。
- 快速行为测试：同config/不同manifest表示合法；错误tag、错误config、同RootFS不同Cmd/Env、错误平台、歧义index、坏layer、重复tar成员必须失败。已加载正确candidate应复用；daemon不可达不能伪装不存在。
- 聚焦故障注入：每个写动作前/后杀进程、记录写失败、磁盘不足、SSH掉线、daemon重启、owner自动重启、重复resume、错host/错事务/错executor、unknown Compose、缺失previous、半迁移。
- 完整隔离矩阵：同一exact tar在受支持classic与containerd真实daemon验证；至少覆盖当前T1所用Docker/Compose组合。不能用两个假.Id字符串替代真实跨store证明。
- 发布验收：新事务连续断线/重启后收敛；旧授权仍不可replay；真正MQTT与状态不变量；不让CI连接生产T1。

已退役Golden Master/Seal/R2C、完成的KF098和旧staging执行包适合保留为历史参考；撤销未来生产入口资格，不直接删除。R10恢复执行器在successor完成且公共入口接管后再归档。fresh install、F4/F5、SSH transport等仍有活动依赖的工具不能凭文件日期旧就移除。

## 13. 威胁模型与验收映射

| 威胁/故障 | 最小防线 |
|---|---|
| artifact与metadata一起替换 | 外部可信manifest摘要/签名；校验具体release批准 |
| 正确tag指向错误image、旧tag污染 | artifact内容图绑定；已存在错误tag拒绝；启动前后再绑本地对象 |
| Docker表示改变 | 类型明确的config/manifest/index适配；未知表示单独报错 |
| 事务重放或错事务resume | 永久claim记录、host/release/executor绑定、唯一事务ID、全局互斥 |
| Compose或运行服务漂移 | before/after/unknown判定；不写未知对象；检查实际mount/env/owner |
| 半迁移、外部凭据变更 | schema兼容、协调状态检查、可恢复迁移；未知时不启动旧版 |
| 断电、daemon重启、自动服务重启 | 持久意图、boot恢复先于activation、应用组停止证明 |
| 磁盘不足 | 按文件系统预算峰值、预留恢复空间、逐镜像stage |
| rollback image被清理 | 事务/previous引用保护，切换前证明实际存在且可启动 |
| 配置存在但MQTT未连接 | 有界readiness、真实会话及业务验收，不能仅hash配置 |

## 14. 分阶段落地与普通用户体验

P0先完成当前恢复方案和必要公共内核/B1—B4修复，不等待全仓历史迁移；P1完善稳定API与真实双store证明；P2接管当前维护入口；P3迁移fresh install的producer/consumer；P4覆盖活动rollback/restore/F4/F5；P5关闭全仓例外。最早从P0/P1就启用“禁止新增复制validator”的增量CI规则，不等P5才防第四次回归。

每阶段以一个小闭环评审：源代码＋有意义测试＋相应合同及公开证据。新旧实现可在只读影子比较中核对差异，但真正生产mutation只能由一个已冻结执行器拥有。旧release保持旧schema，不在现场悄悄重解释。

普通用户：版本发现、下载、完整性检查、空间检查、候选准备和只读健康检查可自动；用户批准一次维护窗口后，工具自动执行已批准的停启、断线恢复和兼容回滚。停机、不可逆状态升级、Docker/OS大版本变更需要事先明确授权；未知状态、身份冲突和无法证明的回滚需要支持人员处理。不要在农户界面暴露digest、SQLite、Compose或几十条取证命令。

提示应符合事实：“正在准备升级”“正在升级”“升级成功”；失败后只有真正证明旧版恢复且业务验收通过，才能显示“系统已恢复上一版本”。若根本未切换，应显示“升级未完成，原版本继续运行”；未知状态应显示需要维护，不虚报回滚成功。

## 15. 验证、引用和归档边界

运行的既有测试：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/n3w-review-deps python -m pytest -q -p no:cacheprovider tests/tools/test_n3w_t1_r10_e03_manager_successor_refresh_live.py tests/tools/test_n3w_t1_fresh_product_bootstrap.py -k 'refresh_live or runtime_image_binding or image_config_contract'
46 passed, 33 deselected in 0.28s
```

其中R10执行器41项、bootstrap身份相关5项。测试未触发Docker、SSH、T1、CI或板卡；完整集成与真实断电矩阵未运行。测试通过不否定上述未覆盖缺口。

隔离复现代码（仅临时文件和替换后的函数；不要当作生产工具）：

```python
import base64
import importlib.util
import tempfile
from pathlib import Path

path = Path('tools/n3w_t1_r10_e03_manager_successor_refresh_live.py')
spec = importlib.util.spec_from_file_location('review_live', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='n3w-review-') as directory:
    m.COMPOSE = Path(directory) / 'compose.yml'
    original = b'original approved compose\n'
    m.COMPOSE.write_bytes(b'external unrecognized change\n')
    tx = {'compose_b64': base64.b64encode(original).decode(),
          'compose_sha256': m.sha_bytes(original)}
    m.restore_compose(tx, None)
    assert m.COMPOSE.read_bytes() == original

class Reached(Exception):
    pass

m.read_tx = lambda: {
    'status': 'CLAIMED', 'phase': 'UNEXPECTED_PHASE',
    'authorization_consumed': True, 'replay_allowed': False,
    'authorization_id_sha256': 'wrong', 'target_source_head': 'wrong',
    'executor_blob': 'wrong'}
def image_probe(reference):
    raise Reached()
m.image_id = image_probe
try:
    m._remote_apply_locked()
except Reached:
    print('MISMATCHED_TRANSACTION_PASSED_ENTRY_GUARD=true')
```

关键源码链接：

- [R10 live executor](https://github.com/chrenguo-stack/HomeAssistant/blob/614c08a397462850f0167b77c9da45ae69a323ad/tools/n3w_t1_r10_e03_manager_successor_refresh_live.py)
- [R10 tests](https://github.com/chrenguo-stack/HomeAssistant/blob/614c08a397462850f0167b77c9da45ae69a323ad/tests/tools/test_n3w_t1_r10_e03_manager_successor_refresh_live.py)
- [fresh bootstrap](https://github.com/chrenguo-stack/HomeAssistant/blob/614c08a397462850f0167b77c9da45ae69a323ad/tools/n3w_t1_fresh_product_bootstrap.py)
- [KF098 validator](https://github.com/chrenguo-stack/HomeAssistant/blob/614c08a397462850f0167b77c9da45ae69a323ad/tools/execution_packages/n3w/kf098/t1_live_cutover/remote_cutover.py)
- [ADR-0010](https://github.com/chrenguo-stack/HomeAssistant/blob/614c08a397462850f0167b77c9da45ae69a323ad/docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md)
- [既有release合同](https://github.com/chrenguo-stack/HomeAssistant/blob/614c08a397462850f0167b77c9da45ae69a323ad/tools/n3w_t1_production_v2_contract.py)
- [本次已归档根因取证](https://github.com/chrenguo-stack/HomeAssistant/pull/725#issuecomment-6511931122)
- [已消费授权](https://github.com/chrenguo-stack/HomeAssistant/pull/725#issuecomment-6511492909)
- [上游Moby存储差异解释](https://github.com/moby/moby/issues/51934)：2026-01-27维护者回复。
- [Docker containerd存储说明](https://docs.docker.com/engine/storage/containerd/)
- [OCI image manifest](https://github.com/opencontainers/image-spec/blob/v1.1.1/manifest.md)
- [OCI image configuration](https://github.com/opencontainers/image-spec/blob/v1.1.1/config.md)

本轮遵守REPOSITORY_MUTATION=false，没有提交报告、评论或修改KF登记；不得宣称GitHub工程归档闭环已完成。下一次获准的源码/文档阶段应把本评审及复现转换成仓库文档和回归测试，再继续到现场恢复。当前一步已完成只读架构评审，尚未完成修复、部署或E03现场恢复。