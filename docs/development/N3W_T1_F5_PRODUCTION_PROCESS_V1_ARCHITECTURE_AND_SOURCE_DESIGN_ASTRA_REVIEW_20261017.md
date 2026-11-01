# N3W T1 F5 V1 量产流程架构与源码设计复核

日期：2026-10-17  
任务：N3W_T1_F5_PRODUCTION_PROCESS_V1_ARCHITECTURE_AND_SOURCE_DESIGN_ASTRA_REVIEW_20261017_01  
性质：独立只读复核与设计建议；尚未批准、实现或完成 F5 实机验收。

**独立结论：建议采用 Mac 上的薄编排程序，加 T1 上现有的权威执行工具。当前源码不能直接宣布为可重复使用的 F5 量产流程。主要缺口是生产授权、完整入口和发布环境绑定；现有 F3/F4 实证继续有效。**

另有一个必须先纠正的体验目标：仅靠 SSH 连接复用，不能在 T1 重启后继续使用重启前的认证连接。V1 最小方案是“重启前输入一次密码，重启后再输入一次密码”；这不增加第二次生产授权。如果坚持整个流程只输入一次密码且重启后无人操作，就需要改变当前远程认证约束，不能把它当作已经解决。

~~~text
F5_ARCHITECTURE_REVIEW_RESULT=CONDITIONAL_DESIGN_RECOMMENDATION
F5_CURRENT_MAIN=cdd597e43149e872e26f81c63bc72f4320e61bcc
F5_MAIN_DRIFT=NONE_AT_REVIEW
F5_SOURCE_BLOCKER=OPEN:PRODUCTION_AUTHORITY;ORCHESTRATION;RELEASE_ENVIRONMENT_BINDING
F5_PRODUCTION_RUN_AUTH_MODEL=AUTHENTICATED_EXPLICIT_RUN_APPROVAL_PLUS_TARGET_DURABLE_PHASE_CLAIMS
F5_ORCHESTRATOR_LOCATION=MAC_OPERATOR_HOST
F5_NORMAL_OPERATOR_ENTRYPOINT=n3w-t1-production run --release <approved-release.json>
F5_HUMAN_CONFIRMATION_COUNT=ONE_PRODUCTION_APPROVAL_PLUS_FIRST_HOST_KEY_VERIFICATION
F5_SSH_MODEL=ONE_PASSWORD_PER_CONNECTION_EPOCH;TWO_FOR_ONE_REBOOT
F5_OVERRIDE_MODEL=STATIC_CHECK_POLICY_STRICT_FAIL_CLOSED
F5_INITIAL_OVERRIDE_ALLOWLIST=EMPTY
F5_T1B_REPEATABILITY_MODEL=T1A_ACCEPTED_PRIMITIVES_PLUS_FINAL_ARTIFACT_CI_PLUS_FRESH_T1B
F5_BOARD_ACCESS_REQUIRED=false
F5_MINIMUM_SOURCE_CHANGE_SET=FOUR_NEW_LOGICAL_MODULES_PLUS_EXISTING_TOOL_ADAPTERS_AND_PACKAGING
F5_TEST_STRATEGY=FOCUSED_UNIT_AND_NEGATIVE;REAL_SSH_INTEGRATION;TWO_FRESH_SANDBOX_RUNS;ONE_T1B_RUN
F5_LIVE_ACCEPTANCE_STRATEGY=FRESH_BASELINE_TO_DURABLE_REBOOT_ACCEPTED
F5_REPOSITORY_CONVERGENCE_STRATEGY=ONE_COHERENT_SOURCE_PR_PLUS_BOUNDED_EVIDENCE_ALIGNMENT
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_ARCHITECTURE_CONTRACT_FREEZE
SOURCE_MUTATION=false
REPOSITORY_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP_AFTER_ARCHITECTURE_SOURCE_DESIGN_REVIEW=true
~~~

上述 NEXT_ONE_GATE 是建议，不在本轮自动执行。尤其不能用本报告替代未来 T1-B 的明确实机授权。

## 1 事实基线与证据边界

### 1.1 本轮重新核实的 GitHub 状态

| 项目 | 重新读取的结果 |
|---|---|
| main | cdd597e43149e872e26f81c63bc72f4320e61bcc |
| main tree | f55c60969c0a5d570aff193db57325bdcb3a2421 |
| PR #609 | CLOSED / MERGED |
| PR #609 head | 97239c1cfc500e70c4231a0d52a45ef44beb4785 |
| PR #609 merge | cdd597e43149e872e26f81c63bc72f4320e61bcc |
| 对齐内容是否已进入 main | 是；该 head 是当前合并提交的直接父提交 |
| F4_REPOSITORY_CLOSURE_FINAL | true，按照已冻结的 terminating closure rule 推导 |
| KF-121 | 公开关闭证据为 CLOSED_PASS_DURABLE_REBOOT_ACCEPTED |
| 本轮实时 T1 状态 | 未访问；不把历史实证冒充本轮探测 |

PR #609 的合并与父提交关系，足以消除冻结账本中 F4_REPOSITORY_CLOSURE_FINAL=false 的歧义，不需要再做一次“对齐的对齐”。

[PR #609](https://github.com/chrenguo-stack/HomeAssistant/pull/609)；[当前 main 提交](https://github.com/chrenguo-stack/HomeAssistant/commit/cdd597e43149e872e26f81c63bc72f4320e61bcc)。

### 1.2 指定 authority 与源码绑定

下表均重新从当前 main 的树及文件读取，与你提供的 blob 一致。

| 文件 | Git blob |
|---|---|
| docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md | 3d7407d908c982d91810698e22e0eac9e1388522 |
| docs/development/N3W_T1_PRODUCTION_CONTROLLED_OVERRIDE_FRAMEWORK_DESIGN_20261014.md | bec864ae1d1ec0e92d35486d82b274f58e722a4d |
| docs/development/N3W_T1_PRODUCTION_SSH_CONNECTION_REUSE_V1_DESIGN_20261014.md | 7228d1c0b5043bb1569d8ef6e0d83d72ae5da557 |
| docs/development/N3W_T1_F3_R4_LIVE_APPLY_CLOSURE_20261015.md | f3faf1047b4105d022d8dbe980ae3bcd78cc2416 |
| tools/n3w_t1_fresh_product_bootstrap.py | 278a5f9935e91d0674166a6098ee6c25f8efee04 |
| tools/n3w_t1_device_provisioning_host.py | 6e63d03027a251248bbe418b60175f9f241a2865 |
| tools/n3w_t1_f4_activation_host.py | 2314a20b4560dc2f9ea6c3918c5f91b4f23b5ec7 |
| tools/n3w_t1_f4_reboot_authority.py | 54d6d596f3ca4f03dd7f61a2a318f7ca5aafd7d1 |
| tools/n3w_t1_f4_reboot_verify.py | 0f0f67c985197cce9b7d5abb55d0ca958e8ec5a0 |

同时检查了 F2 executor、F3 Mac 传输程序、host baseline、firstboot 合同、F4 两个打包器、相关工作流、现有测试、当前三本账及相关关闭文档。结论是源码与已有证据复核；本轮没有运行产品测试、触发 CI 或执行实机命令。

### 1.3 上位规划如何约束本次设计

- V0.5 的共同底线是通用软件、逐机独立凭据、普通用户不理解底层运维。它的历史身份或无线方案不能覆盖后继决策。
- V0.7 第 0、3、6、7 章要求区分规划和验收事实、保持初始化与长期服务职责分离、维护系统身份和秘密的恢复边界。
- 2026-08-16 架构收敛规划第 9 章明确提出“一个计划、一次批准、领取授权、执行、验证、终态”，同时保留领取后不静默重放。F5 顶层 run 正是这一原则的产品化，不应再扩大为大量 successor 包。
- ADR-0010 是当前生产路线：逐台官方 Armbian、逐台 OS 首启、公共软件自动部署、显式产品初始化、激活及验收。Golden Master、Final Seal、整盘克隆不进入 F5。

### 1.4 F3/F4 保持关闭

F3 R4 的 source 为 6ac82ae0872b05644e59470ffef7307dad14d359，artifact 为 11942497052，digest 为 sha256:1a8813b788fc4d597acfaafee417daa4bf6fc4bd3ea547d22dd1d689c462c4af。三张镜像逐个加载并删除暂存 tar；只部署公共软件；未生成实例秘密、未启动产品服务；原授权已消费。

Provisioning 关闭文档证明 DEVICE_READY、只调用一次 start、生产服务未启动。一次本地结果解析失败后来由设备持久记录及 verify 证明不是产品初始化失败。

F4 后续完成激活、运行、持久化、证书、受控 reboot、重启后验收及最终落账。最终 accepted claim 为 48bb962b2d979f0e6f80a36bfc4f33aff6eca77e1b3a655f5773a9c4ebb879e9，终态为 REBOOT_ACCEPTED。F5 不撤销这些结论。

## 2 独立源码发现与优先级

| 编号 | 当前事实及源码位置 | 对 F5 的影响 | 分类 |
|---|---|---|---|
| B1 | fresh_product_bootstrap 第 20、170、1795、1822 行附近及 deployable workflow 第 65、430 行附近固定 R4 authorization | 发布包与某次研发操作绑在一起，缺少真正逐机逐次的生产许可 | 必改 |
| B2 | F3 ledger 绑定 ID、source、manifest；F4 _transaction_document、_activate、_validate_successor_authorization 校验 ID 形式及历史；provision start 使用固定确认文本 | 这些是已有人工受控流程的守卫，尚不是统一的生产 run 授权；给 ID 加随机后缀不能补齐它 | 必改 |
| B3 | F3 Mac wrapper、provision CLI、F4 CLI、reboot actuation 与 finalizer 分散；F4 命令列表混有 repair | 缺少完整正常生产入口与最终结果收口 | 必改入口和适配；不重写底层 |
| B4 | fresh_host_baseline._check 接受可运行的包版本；execute_install 在 apt update 后取当时 Candidate | 同一产品包跨日期可能使用未经该发布验证的 Docker/Compose | F5 发布环境合同缺口 |
| D1 | SSH 设计强调一次密码；最终体验又包含 reboot 后自动重连 | 原控制连接无法跨服务器重启；在不保留密码、不增加登录凭据条件下不能同时满足 | 先修正设计承诺 |
| B5 | staging wrapper 多处直接 ssh/scp；F2 ssh_stream 另有认证选项；F2 EXPECTED_BLOBS 固定当前工具版本 | 新编排若只给最外层加连接复用，内层仍可能另行认证；新源变更还会触发旧 blob 拒绝 | 统一传输入口及发布绑定 |
| B6 | 缺少覆盖全部阶段、人工放行、设备比较的 F5 结果合同 | 无法可靠区别“程序结束”“设备通过”“流程完整结束” | 必补；可在一个模块内完成 |

**对 G2 的纠正：** 旧 ID 并不一定在另一台 fresh T1 上被程序拒绝，因为另一台没有第一台的本地 ledger。它不能“合法继续生产”的原因是该历史授权已消费，而且当前记录缺少跨设备生产 run 绑定。不是简单把常量改成参数就够了。

**对 G1 的判断：** 成立，但源码已有多种 T1 orchestrator 名称，主要用于特定迁移或恢复，不能仅靠文件名判断已有正常量产入口。本轮检查的 F2/F3/provision/F4 正常路径没有统一覆盖到最终 F5 关闭。

输入中只实际定义了 G1、G2；结尾提到 G1～G6，没有提供其余四项的正式定义。本报告用独立 B/D 编号记录，不虚构另外四项原结论。

以下只是体验改进，不应被说成现有产品故障：进度条、中文提示、隐藏内部参数、减少复制命令、统一文件名。repair CLI 的存在本身也不是缺陷。

## 3 推荐架构及正常操作

### 3.1 职责分配

| 位置 | 职责 | 不承担 |
|---|---|---|
| Mac 生产入口 | 发布包校验、目标确认、SSH 生命周期、阶段调度、状态展示、公开报告与私有索引 | TLS/密码生成、重写 Broker/Manager 状态逻辑 |
| T1 run authority 小模块 | 记录明确批准、核实目标和发布绑定、逐阶段领取一次性许可、阻止重复/越级、记录最终 run 状态 | 重新实现 F3/F4 |
| 已有 T1 工具 | 公共软件部署、实例初始化、激活、运行检查、持久化、证书检查、reboot 验收与最终落账 | 推断用户是否授权整次生产 |
| 现有启动服务 | 只恢复已合法开始的初始化事务、验证已就绪设备、按已启用合同启动服务 | 从 UNPROVISIONED 偷偷开始新生产 |

采用 Mac 编排，是因为大 artifact、交互密码和设备台账都在操作端；T1 不需要新增长期量产守护进程。目标端仍保留最小 durable authority，避免 Mac 中断后仅凭本地记忆决定是否重来。

### 3.2 建议命令面

以下是待实现的命令合同，不是当前可执行命令：

~~~text
n3w-t1-production run --release <approved-release.json>
n3w-t1-production inspect --record <private-run-record>
n3w-t1-production verify --record <private-run-record>
~~~

正常生产只使用 run。目标在私有交互中输入，不要求操作员填写 source、manifest、phase ID 等十几个参数。inspect 只读。verify 只做有界检查和生成本地报告，不重新部署、不重启、不重新落账；确需补写设备终态时走明确受控的恢复操作。

run 的顺序是：

1. 本地验证完整发布描述和文件集合。
2. 获取已可信核验的 SSH host key，连接目标；输入第一次密码。
3. 只读检查 OS 首启、机器身份、网络/时间、权限、存储、Docker 基线和产品残留。
4. 展示目标短指纹、发布号，以及“将安装、初始化身份、启动服务、启用持久化并重启一次”的完整计划。
5. 操作员一次明确确认 START PRODUCTION RUN，并核对设备短码。
6. 自动领取并完成各阶段；每次转阶段都验证设备端持久结果。
7. 达到 PRE_REBOOT_READY 后领取 reboot authority，并发起一次 reboot。
8. 有界等待 SSH 可达，核对原 host key，提示第二次密码；不重复请求生产批准。
9. 执行重启后验收、durable finalization 和独立 terminal verification。
10. 关闭控制连接、生成最终报告，输出 PASS、PASS_WITH_OVERRIDE 或 FAIL。

这里的生产完成是设备工厂验收完成。现有 F4 报告中 product_pairing_enabled=false，不能顺手把用户 onboarding、打开配对窗口或 ESP32 注册也算进本次生产授权。

### 3.3 最少人工操作

正常新机器有一次首次 host-key 核验、一次生产批准、两次密码输入。目标输入不是授权；密码输入是连接认证，也不是重新授权。

首次主机密钥已有可信台账时不必再次人工核验；仍自动严格比对。初始 override 白名单为空，因此正常路径没有放行询问。错误密码、断线和工程恢复不计入“正常次数”，但必须记录额外交互。

一次批准可以覆盖全部正常阶段，前提是批准摘要明确列出实例初始化、服务启动、持久化、证书检查及一次 reboot。若计划或目标后来发生实质变化，原批准不得自动扩权。

## 4 可复用且不可重放的生产授权

### 4.1 发布物与一次生产操作分离

**不可变发布物**包含：source head、Mac 程序、T1 工具、F3/F4/reboot 子包及其哈希、三张 ARM64 镜像、受支持 OS 与包版本、检查政策、结果 schema。它不包含任何真实设备身份、实例秘密或实际 run 的授权。

**私有 run record**包含：随机 run ID、已批准计划哈希、发布清单哈希、目标 host-instance 安全绑定、SSH host-key 指纹、批准时间/有效期、允许阶段及前序状态、reboot 预算、消费与关闭记录。

同一份经过审核的发布物可以反复用于不同设备；每台每次只生成新的私有数据记录，不改代码、不重编译。

### 4.2 ID 不是授权凭据

PRODUCTION_RUN_ID 建议使用操作端系统安全随机源产生的 256 位随机数，配显示用短码。随机性解决碰撞，不证明权限。

V1 的信任起点是：已核验的 T1 host key、已认证且有既有管理权限的 SSH 会话、操作员明确批准，以及经过校验的仓库程序。不是另建工厂 PKI。

目标端批准入口必须检查完整计划、当前目标身份、受支持发布绑定和现态，随后由管理员权限创建保护目录中的批准记录。后续命令仅携带 run/phase 索引；目标端必须查验该已有记录。不得根据调用者随便传来的 authorization 字符串现场“补出许可”。

该模型防误用、错机、重放、并发和未经批准的普通调用，不承诺防止已获得 root 权限的人任意改程序或擦除台账。不能把文件哈希包装成能防 root 篡改的数字签名。

### 4.3 两端记录及领取顺序

Mac 先持久保存完整批准计划和待领取状态；T1 在任何系统安装、Docker 变更或产品变更之前，以独占锁、排他创建、权限检查、fsync 文件及目录，持久领取顶层 run。

顶层记录应至少有：

- run_id、schema、policy_digest、plan_digest；
- source head、发布清单及各子包 digest；
- 目标 host-instance digest、host-key fingerprint、起始 boot digest；
- approved_at、expires_at、max_duration；
- 允许的阶段集合、reboot_budget=1；
- run_claimed、run_consumed、replay_allowed=false；
- last_completed_phase、terminal_state、failure_class；
- 不可变初始记录及后续事件链摘要。

领取消息丢失时，Mac 查询原目标 durable ledger；查不到或状态无法证明时按 UNKNOWN 停止，不重新发出 mutation。

仅为了校验/传输产生的、已界定且可清理的暂存目录，不等于 product mutation；必须如实报告暂存写入。真正的 durable claim 写入本身就是已授权写操作。不得在顶层 claim 前运行 apt install 或 Docker load。

### 4.4 阶段许可与现有台账对接

| 阶段 | 每次必须绑定 | 复用的原有事实 |
|---|---|---|
| HOST_BASELINE/F3 | run、目标、exact payload、阶段 ID、fresh prestate | F3 ledger、逐镜像请求/加载记录 |
| PROVISION | F3 成功报告 digest、release、同一目标 | transaction.json、FIRSTBOOT_COMPLETE.json |
| F4_PREPARE | DEVICE_READY、实例身份摘要、F4 子包 | FACTORY_ACCEPTED、F4_ACTIVATION_TRANSACTION |
| F4_ACTIVATE/ACCEPT | 上一阶段报告与事务摘要、独立 phase ID | 原有 activation/runtime claims 与 report |
| PERSIST/CERT_AUDIT/TIMER | 原有阶段及完整性条件 | 原有 persistence/certificate 字段 |
| REBOOT_CONTROL/REBOOT | 当前 F4 事务 hash、控制包、原 boot、只重启一次 | control claim、REBOOT_PENDING |
| FINALIZE | 新 boot、pending claim hash、原控制包、验收报告 | 原 finalizer 和 REBOOT_ACCEPTED |
| CLOSE_RUN | terminal verify、所有阶段记录、override、交付证据 | 新 F5 终态；不改写旧 F4 验收含义 |

phase ID 可以由 run ID、固定 phase 名、计划哈希派生。需要兼容现有 F4 前缀时，形成规范的 N3W_T1_F4_<run>_<phase>。其安全性仍来自目标端批准记录，不来自名字。

目标端只允许一次从 READY 到 CLAIMED/APPLYING 的执行权转换。领取后写明 consumed；成功才进入 SUCCEEDED。已领取但结果不明不得再次执行。同一 run 后续未执行阶段仍可按原完整批准继续，不能把“顶层已消费”误解释成后续阶段全都无权执行。

**特别守卫 F3 claim→apply 缝隙：** 当前 execute_apply 可以识别同 payload 的 preclaimed marker。这是交接机制，不能直接作为通用“多次 apply 许可”。F5 必须增加一次性 apply 状态/执行锁，防两个进程或失败重试利用同一个 marker 再次进入。

### 4.5 最少双层状态

F5 记录只保存 run/phase 权限、必要引用和最终结果；细节仍由 F3/provision/F4 台账负责。避免在顶层复制一整套初始化、容器和证书内部状态。

跨文件不假装有数据库原子事务：先持久 claim，再调用原 primitive，再写成功引用。任何中间崩溃都保持 consumed/unknown；恢复只读取和核对原始事实。最终确认可以有独立补记流程，绝不通过重做原 mutation 来修复丢失的返回值。

原 firstboot 的“已开始事务恢复”继续保留；boot 不能开始新事务。F5 失败后不主动用 reboot 或 resume 来试错；若系统本身恢复了已有初始化，必须把该状态纳入工程诊断，不能自动把失败 run 改成完整 fresh PASS。


## 5 SSH V1 的具体设计

### 5.1 必须修正的承诺

OpenSSH 的 ControlMaster 复用的是同一条网络连接；ControlPersist 只是让该连接在后台继续存在。它不是密码缓存，也不是服务器重启后的重新认证机制。

因此本报告建议在 F5-0 将原设计精确修订为：

~~~text
NORMAL_DEPLOYMENT_PASSWORD_PROMPTS_BEFORE_REBOOT=1
POST_REBOOT_PASSWORD_PROMPTS=1
NORMAL_FULL_RUN_PASSWORD_PROMPTS=2
PRODUCTION_AUTHORIZATION_PROMPTS=1
PASSWORD_PERSISTED=false
NEW_SSH_LOGIN_KEY=false
~~~

“重启后自动等待、自动核验 host key、再提示输入密码”可实现；“重启后全自动重新登录且没有任何可复用认证材料”不可承诺。若今后坚持全程一次输入，必须另行评估短期登录凭据或其他认证机制，不能暗中保存密码实现。

### 5.2 连接所有权与本地文件

- 由 Mac production orchestrator 唯一管理 master 子进程、socket、SSH 配置和 cleanup；底层 wrapper 不创建第二个 master。
- 使用本机短路径的随机私有目录，例如系统临时目录下 n3w-ssh-<随机值>；0700、当前用户所有、拒绝 symlink、检查真实路径长度。不要把 socket 放在仓库、共享盘、同步盘或过长 Documents 路径下。
- 若 macOS 的系统临时路径太长，使用 /private/tmp 下由安全临时目录函数独占创建的短目录。严禁复用别人预先放置的路径。
- socket 名不含真实地址；目录与 run、用户、目标绑定，不在不同设备之间共用。
- known_hosts 是私有信任记录；socket 是短期会话资料。关闭连接不删除长期已核验的 host-key 记录。
- Mac 只执行编排与传输；T1 的 root/sudo -n 能力必须在批准前验证。SSH 密码不能被再次拿去喂 sudo，也不自动改 sudoers、root 登录政策或创建管理账号。

### 5.3 第一次 host key 如何建立信任

首选在该台 T1 完成 Armbian first boot 的本地控制台读取 SSH 公钥指纹，记录到对应物理设备的私有工位台账。Mac 收到网络公钥后与该可信指纹比对，再写专用 known_hosts。

没有可信指纹时暂停在连接信任边界，要求操作员通过本地控制台或已有可信入库记录核验。不能把同一条未经验证的网络连接读出的 fingerprint 再拿来“证明自己”。

ssh-keyscan 只能取候选公钥，不是信任证明；不使用 accept-new 自动接受所有陌生设备来代替此核验。OpenSSH 官方手册明确提示，未经验证就把 keyscan 结果建成 known_hosts 会留下中间人风险。

已知 host key mismatch 必须停止。不能删掉旧记录后重试、不能自动换 alias 绕过已知冲突。确实重新刷机的设备，需要单独记录新安装身份及新 key 的核验；旧 run 仍保持不可重放。

### 5.4 复用及禁止静默回退

主连接使用明确受控配置启动，密码由 OpenSSH 直接从终端读取。程序不读取密码字符串，不使用 sshpass/expect，不把密码放进环境、参数、日志、文件或 artifact。

所有 ssh/scp，以及今后若使用的 rsync，统一走一个经过测试的 transport adapter，传入同一个 ControlPath、known_hosts、目标与用户。初期继续使用当前所需的 ssh/scp，不为统一接口额外引入 rsync。

仅设置 ControlMaster=no 或 BatchMode=yes 不够：前者在 socket 丢失时仍可回退成正常连接，后者只禁止交互，仍可能用其他密钥登录。建议对子会话加“复用失败即失败”的配置，例如复用请求带固定 ProxyCommand=/usr/bin/false，并禁用可回退的密码、交互、公钥及 agent 路径；先做 master check，再执行，但不能只靠这个存在检查消除竞态。

该配置必须在实际支持的 macOS OpenSSH 版本及 CI sshd 集成中验证；禁止直接假设较新 OpenSSH 选项在用户 Mac 上可用。主连接与子会话分开配置，主连接不能带阻断新连接的 ProxyCommand。

显式提供独立配置，避免默认 ~/.ssh/config 中的 ProxyJump、Match exec、转发、agent 等改变路径。不得把“没有提示密码”误判成“确实复用了原连接”。

### 5.5 正常 reboot 与异常断线

| 情形 | 动作 |
|---|---|
| 已有合法 reboot claim，准备重启 | 私有记录持久化后，原子取得唯一 actuation 权，至多发送一次 reboot |
| reboot 后连接消失 | 只说明断线，不能据此宣布重启成功 |
| 预期 reboot 等待 | 有界等待网络/SSH，可见倒计时；不循环尝试密码 |
| SSH 回来 | 比对同一 host key，显式输入第二次密码，重建 master |
| 重连后 | 核对 host-instance 不变、boot_id 改变及原 pending claim；再调用原 verifier |
| 非预期断线 | 停止调度新 mutation，记录当前 phase 的已知/未知状态 |
| 操作员明确重连 | 先只读取证；不得因此重新发出已执行或不确定的命令 |
| Mac 崩溃后重新启动入口 | 查已有记录；默认 inspect，不能把旧 run 当新 run 自动重跑 |

reboot actuation 需要额外的小边界：现有 reboot_authority 负责 claim，刻意不直接重启主机。F5 目标端 dispatcher 应在锁内持久标记 actuation_attempted，再发起一次固定 reboot 动作；丢失响应后不补发第二次。该标记不应改动 F4 已冻结、跨 reboot 校验的 transaction hash。

预期重启后的认证提示不算生产失败；超过冻结期限、host key 改变或设备身份不符才进入失败/待工程处理状态。

### 5.6 清理与最终结果

成功、失败、Ctrl-C 均执行有界 cleanup：向本 run 的 master 发 exit，等待退出，必要时仅终止本程序持有的 master 进程，确认没有活连接，再删除本 run 的 socket/临时配置。严禁 pkill ssh 或广泛删除 ~/.ssh。

- master 仍存活、socket 所属不明、凭据或控制通道清理无法证明：overall=FAIL，保留 device_acceptance=PASS 的独立事实，停止工位后续生产。
- 已证明 master 死亡，只有一个无敏感内容的空临时目录删不掉：WARNING，记录后续工位清理。
- 失败证据目录不能随 socket cleanup 一起删除。
- Mac 被强制结束时，有限 ControlPersist/超时作兜底；下次启动先清理可证明属于旧 run 的资源。

## 6 Controlled Override 的首版政策

**INITIAL_OVERRIDABLE_ALLOWLIST=EMPTY。** 首版实现分类、询问、记录、传播和结果计算框架，但不为了演示功能降低真实门槛。测试可注入一个仅在测试环境中的可放行政策，生产包不携带它。

下面的 CHECK_ID 是建议冻结的新名称；右列指出当前真实检查来源，不宣称源码已经存在这些 ID。

| 建议 CHECK_ID | V1 分类 | 对应真实检查及处理 |
|---|---|---|
| RELEASE.EXACT_BINDING | HARD_STOP | F3 _load_manifest、wrapper 的 artifact/manifest/文件集合校验 |
| HOST.OS_ARCH | HARD_STOP | F2 accept 的 OS/Armbian/architecture；host baseline._validate_target_host |
| HOST.FIRSTBOOT | HARD_STOP | F2 armbian-firstrun inactive/disabled/success/exit=0 |
| HOST.IDENTITY | HARD_STOP | F2 machine-id、SSH key 配对与权限；provision._host_identity |
| HOST.IDENTITY_UNIQUE | HARD_STOP | 新增跨设备台账重复判断；缺少必须证据不能当 PASS |
| HOST.SSH_TRUST | HARD_STOP | host key 匹配及受控会话 |
| HOST.PRIVILEGE | HARD_STOP | 现有工具 root_required；批准前证实非交互管理权限 |
| HOST.NETWORK_TIME | HARD_STOP | F2 route/DNS/NTP；未知时钟不能拿来判断证书与授权期限 |
| HOST.DOCKER_CONTRACT | HARD_STOP | Docker/Compose 来源、批准版本、daemon 与空状态 |
| HOST.PRODUCT_ABSENT | HARD_STOP | F2 residue、容器/镜像/卷/网络、路径、监听与 unit |
| HOST.STORAGE_AUTHORITY | HARD_STOP | wrapper 确认实际 Docker/containerd root、文件系统、非 tmpfs |
| CAPACITY.TRANSPORT_PEAK | HARD_STOP | transport manifest 中 tar/load 尺寸及逐镜像空间准入 |
| CAPACITY.POST_PEAK_RESERVE | HARD_STOP | 现有 5 GiB 安全余量；V1 不下调 |
| AUTH.RUN_PHASE | HARD_STOP | 顶层批准、phase、目标、source、manifest、前序台账与消费状态 |
| PROVISION.DEVICE_READY | HARD_STOP | firstboot transaction、marker、身份一致性；不得自动开启服务 |
| F4.INSTALLED_MATERIAL | HARD_STOP | _verify_installed_material 与 package/factory binding |
| F4.TLS_ACL | HARD_STOP | TLS、service identity、认证否定测试、ingress guard |
| F4.TOPOLOGY_STATE | HARD_STOP | 三服务、网络/端口、挂载、空业务状态、HA 单一 MQTT entry |
| F4.PERSIST_CERT | HARD_STOP | persistence、首次 audit、timer enable-only 的已有合同 |
| REBOOT.DURABLE_ACCEPTANCE | HARD_STOP | boot 变化、身份不变、verifier、finalizer、terminal verify |
| EVIDENCE.COMPLETENESS | HARD_STOP | 关键结果缺失、报告与台账不一致、公开结果泄密 |
| SSH.CONTROL_CLOSED | HARD_STOP | 无法证明已结束受控登录通道 |
| DIAG.ARTIFACT_CACHE_MISS | WARNING/信息 | wrapper 已支持 MISS_POPULATED_VERIFIED；下载成功且校验通过无需放行 |
| DIAG.APT_INDEX_DEFERRED | WARNING/信息 | F2 已允许 fresh apt index 为空但可信源配置完整；后续包安装及版本必须通过 |
| DIAG.EXTRA_EXPOSED_METADATA | WARNING/信息 | F4 已允许镜像声明额外 ExposedPorts 而无额外实际 publication；不能放行真实端口暴露 |
| DIAG.EMPTY_TEMP_DIR_REMAINS | WARNING | 仅在无活连接、无敏感文件且所有权明确后成立 |

“Docker 已存在”本身不是 OVERRIDABLE：当前 F2 本来就允许来自受支持安装源、daemon 正常、对象为空的 Docker 基线。符合合同是正常 PASS，不应人为变成带例外通过。

“镜像带额外 EXPOSE 元数据”也不等于额外开放宿主机端口；保留现有语义检查，不把无风险元数据误报成产品故障。

### 6.1 容量双阈值的后续位置

现有 transport 已有每张镜像 required_free_bytes=tar_size+loaded_size+5 GiB，且每次传输前、加载后重新检查。不能用一个随意的“磁盘剩余几 GB”替换。

F5 V1 保持这条严格合同，并把公共 payload、F4/reboot 小包、依赖安装、已加载镜像累计占用和结果记录纳入空间评估。按每个真实文件系统分别计算，不混加不同盘的可用空间。

将来若要降低安全余量，需要 exact artifact 的分阶段峰值模型和观测数据，覆盖 Docker/containerd 临时副本、解压与文件系统开销、包安装、日志及最终留存。定义：

~~~text
absolute_minimum = verified_peak_increment + measured_required_operating_reserve
recommended = verified_peak_increment + conservative_reserve
~~~

只有证据足够并通过新的政策审查后，中间区间才成为 OVERRIDABLE。目前不填写一个假定最低数值。

### 6.2 放行决策不可传播

未来每次允许放行须绑定 check_id、policy digest、run、phase、输入/实际值摘要、固定原因、操作员决定和时间；只能影响该次检查，不能覆盖后续空间、TLS 或状态检查。

拒绝、没有终端、超时和未知 ID 均停止。只要有一次放行，即使后续全部通过，也永久保留 PASS_WITH_OVERRIDE。任何 HARD_STOP 失败都覆盖它，终态为 FAIL。

## 7 失败与重试合同

区分“原样继续等待/只读取证”“恢复已经合法开始的事务”“再次执行 mutation”。这三件事不能共用一个模糊 retry 按钮。

| 失败类别 | 授权状态 | 允许原地做什么 | 再次 mutation | 何时必须重新刷 Armbian |
|---|---|---|---|---|
| PRECLAIM_FAILURE | 已证明两端均未领取，则未消费；不明则 UNKNOWN | 修正连接、下载、目标输入等前置问题后重新只读检查 | 计划/目标/artifact 未变且未过期可使用原批准；有变化重新批准 | 不需要 |
| CLAIMED_PREMUTATION_FAILURE | 已消费，哪怕尚未修改产品 | 读取台账、核实未执行和暂存所有权 | 新 run/新批准；不得复用旧许可 | 仅当不能证明基线未被改变 |
| PARTIAL_MUTATION_FAILURE | 已消费 | 有界取证；只允许原工具已批准、所有权清楚的 cleanup | 源码修复、CI、新包、新批准；工程恢复与正式 fresh 重验分开 | 在 T1-B 最终 clean 验收中，已安装依赖/载入镜像/提交产品且不能证明回到原 fresh 基线时重刷 |
| POST_PROVISION_FAILURE | 已消费；身份事务必须保留 | verify 或检查 INITIALIZING/DEVICE_READY；工程恢复不重建新身份 | 不能第二次 start；恢复须沿原事务合同与新恢复授权 | 若最终安装器在此前路径有缺陷，正式 clean 复验应重刷；只丢本地报告而设备状态完整则不必 |
| POST_ACTIVATION_FAILURE | 已消费 | 调用已批准的原 F4 fail-closed 收尾，验证服务/监听是否真的停止 | 禁止自动 repair 或直接重开服务；需新恢复授权 | 产品/安装路径 defect 修复后要重新证明完整 fresh 路径时重刷；纯取证或终态补记问题不自动重刷 |
| POST_REBOOT_FAILURE | reboot 许可已消费 | 有界重新认证、只读核对 boot/claim/服务与证书 | 不重发 reboot；finalizer 补记需准确分类及受控权限 | 身份/基线污染或需重验前面安装步骤时重刷；仅 SSH 取证失败、终态写入失败不默认重刷 |

补充规则：

1. 顶层 run 进入终态 FAIL 后不能改回 PASS。后续恢复结果另建记录并关联它；历史失败仍保留。
2. 预期 reboot 后等待第二次密码不是失败。非预期断线的当前命令结果不明时，禁止自动执行后继 mutation。
3. 当前 F4 已有停止服务、禁用 persistence/timer、检查监听消失的失败处理，应复用。Mac 无法连回时，不宣称目标服务已停止。
4. 允许清理的只是本次 run 持有且合同声明可删的暂存内容，以及原 primitive 已审查过的回退对象。禁止自动 docker prune、删除 identity/TLS/DynSec、删除 authorization ledger、擦盘或网络/SSH 重配置。
5. 重刷不是“清掉 ledger 就重新获得旧授权”。Mac 私有台账保留所有失败 run；新 OS identity/new host key 经重新核验，建立新的 install identity 和 run。
6. T1-B 在尚未交给用户的测试期可作为重刷对象，但重刷需独立批准；该设备一旦开始承载用户数据，不能沿用本报告的 fresh 清理假设。
7. 源码 defect 的正确链为：有界取证→停止→仓库修复及测试→新 exact artifact→必要时重刷→新预检→新批准。临时 shell patch 后通过不能算正式验收。

## 8 生产结果与证据结构

建议 schema 为 gh.n3w-t1-production-result/1，由一个生产合同模块统一验证。顶层 status 取 RUNNING、WAITING_FOR_REAUTH、STOPPED、COMPLETED；只在终态设置 outcome 为 PASS、PASS_WITH_OVERRIDE 或 FAIL。不要把“还没验证”装进 PASS。

| 字段组 | 至少包含 | 公开规则 |
|---|---|---|
| 标识 | schema、production_run_id、policy_digest、plan_digest | 随机 run ID 与非秘密摘要可公开 |
| 目标 | install identity 摘要、host-instance 摘要、可信 host-key 绑定结果、physical asset reference | 地址/用户名/实体资产关联仅私有；公开用不含位置的别名或批准指纹 |
| 发布 | review_main、product_source_head、orchestrator digest、各 primitive source/digest、release manifest digest | 公开 |
| 构建 | workflow run ID、artifact ID/digest、子包 manifest、平台、镜像 tar 与 image/content digests | 公开；必须区分 GitHub workflow_run_id 和 production_run_id |
| 环境 | 官方 OS 镜像来源/hash、OS/内核、Docker/Compose 实际版本及 approved policy 结果 | 脱敏后公开 |
| 授权 | approved_at/expires_at、claimed/consumed、no-replay、phase claims、predecessor/result hash | 不公开 capability 等潜在授权材料 |
| 各阶段 | F2、F3、provision、F4 prepare/activate/runtime、persistence、certificate、reboot、finalize、terminal verify | 输出固定结构及证据摘要 |
| 检查 | check_id、severity、policy、expected/observed 安全摘要、result、error_code | 白名单字段，不直接拷贝 stderr |
| 放行 | 独立决策 ID、check/phase/input 摘要、显式 approve/reject、时间 | 操作员实际身份按私有政策处理 |
| 稳定性 | pre/post boot digest、身份稳定、容器稳定窗口、证书状态、HA entry 唯一 | 不公开业务数据 |
| 重复性 | software_exact_binding、approved_delta、identity_unique、comparison_scope、reference evidence hashes | 值相等/不等及非秘密 fingerprint |
| 终态 | device_acceptance、operator_session_closed、evidence_complete、overall outcome、failure_class | 不能只留一个笼统 PASS |
| 追踪 | started_at、ended_at、last_completed_phase、event sequence、previous hash、final report hash | 公开安全摘要 |
| 私有证据绑定 | presence、digest、size、creation time、purpose、path_class | 不公开具体 private locator/path |

### 8.1 私有与公开分开生成

私有设备台账保存必要的设备定位、信任绑定、授权原件和受保护原始证据。密码与产品私钥没有必要被复制到台账；产品秘密仍留在现有受保护目录，不因“私有记录”而扩大秘密拷贝范围。

公开证据从固定字段白名单生成，不是先把所有原始数据写出去再正则涂黑。错误原因使用固定代码，原 stderr/stdout 留在受保护诊断区。异常文本、SSH target、证书 SAN、tar 路径、环境变量、MQTT metadata 都必须纳入泄漏测试。

### 8.2 审计与防改写

目标端记录 root 所有、0700/0600、拒绝 symlink/hardlink、独占锁、原子创建或比较旧 hash 后替换，并 fsync。Mac 私有记录采用单工位独占锁和有序追加。

最终报告由目标端验收证据和 Mac 会话关闭记录共同确定，生成一次后不可原位覆盖。更正记录写为 successor，保留原摘要。公开摘要后续提交 GitHub，形成外部时间线锚点。

hash chain 能发现未协调篡改和损坏；没有外部锚点时不能保证抵抗同时控制 Mac 与 T1 的管理员。V1 不为了夸大防篡改能力再增加 PKI。

### 8.3 软件与秘密的比较

- 软件 hash 用普通摘要。
- SSH/TLS 私钥的唯一性优先比较对应公钥指纹，不读取、导出私钥。
- 原始 machine-id、SYSTEM_ID、Manager identity 可在目标端生成安全摘要，公开仅留必要关系。
- MQTT 密码不公开明文，也不公开便于离线猜测的普通密码 hash。跨机核验若没有现成证据，用仅限私有审计的 keyed fingerprint 比较，公共报告只输出 DIFFERENT/UNKNOWN。
- 候选比较机制只在下一阶段明确授权的取证中执行，本轮没有读取任何生产秘密。


## 9 文件级最小改造计划

以下是建议范围，不是本轮已经修改的文件。文件名使用稳定职责，不新增带日期或迭代后缀的一次性执行器。

### 9.1 建议新增四个逻辑模块

| 建议路径 | 责任及最小内容 | 对应测试 |
|---|---|---|
| tools/n3w_t1_production.py | Mac run/inspect/verify、阶段调度、一次批准、预期 reboot 等待、结果收口；包内提供 n3w-t1-production 启动入口 | tests/tools/test_n3w_t1_production.py |
| tools/n3w_t1_production_authority.py | T1 批准/领取/phase dispatch/关闭；锁、目标与发布绑定、无重放；唯一 reboot actuation；调用现有 primitives | tests/tools/test_n3w_t1_production_authority.py |
| tools/n3w_t1_ssh_transport.py | master 生命周期、host-key 固定、ssh/scp 统一调用、有界错误与 cleanup | tests/tools/test_n3w_t1_ssh_transport.py，加实际 sshd 集成 |
| tools/n3w_t1_production_contract.py | 发布/计划/结果 schema，静态 CHECK_ID 和 severity，override 数据验证，公开结果白名单 | tests/tools/test_n3w_t1_production_contract.py |

政策和结果先放一个纯模块内，避免为每个字段新建文件。若已有通用持久写入助手满足合同则复用；不要为了四个新模块再建立通用工作流框架。入口必须由最终 artifact 实际调用，不允许只被 pytest 导入却没有生产调用链。

### 9.2 必须适配的现有源码与构建

| 当前路径 | 具体修改 | 必须保持 |
|---|---|---|
| tools/n3w_t1_fresh_product_bootstrap.py | 去掉真实 R4 ID 对可复用 manifest 的依赖；接受经过目标 authority 验证的 phase context；ledger 增加 run/device/phase；claim→apply 单次执行权 | 原 exact 文件/镜像校验、只部署公共软件、候选目录 ownership、原 cleanup |
| tools/n3w_t1_fresh_product_staging_host.py | 所有远程调用接入统一 SSH adapter；完整 release 输入；区分 workflow run 与 production run；上层 phase context；复用既有缓存与逐镜像运输 | 每次最多一份镜像 tar、哈希验证、容量复核、未知 claim 停止 |
| tools/n3w_t1_fresh_host_baseline.py | 输入经批准的 OS/包版本政策；安装锁定的包版本，已安装也核对；报告真实安装版本；管理 mutation 受 run authority 约束 | 不启动产品服务、不改 SSH/网络、不自动换 OS |
| tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py | 将可复用 checks/accept 接入生产入口；expected blobs 从经批准 release 导出；所有 SSH 接入统一 adapter；保留工程入口兼容 | 当前 host/身份/fresh 状态检查；只读不得变成 apt update/install |
| tools/n3w_t1_device_provisioning_host.py | 正常生产 start 必须验证已领取的 PROVISION context，记录与既有 transaction 的绑定；不靠注入固定 confirm 文本证明授权 | start/resume/verify 分离；DEVICE_READY 不启服务；已 ready 不能再 start |
| tools/n3w_t1_f4_activation_host.py | 正常 mutation 入口校验生产 phase context，原 transaction 关联 parent run；只在边界接入，不复制函数体 | 原阶段锁、guard→Broker→readiness→services 顺序、rollback、证书及持久化检查 |
| tools/n3w_t1_f4_reboot_authority.py | 关联 parent/phase，冻结 finalizer 权限；与 F5 actuation 记录互相绑定 | 原 claim/finalize/terminal verification 合同；不把 verifier 改成会重启 |
| tools/n3w_t1_f4_package_builder.py | 把运行所需的 authority/contract 依赖按 exact 文件集合打入包，处理安装位置与完整性绑定 | manifest exact inventory；不包秘密、不自动激活 |
| tools/n3w_t1_f4_reboot_successor_package_builder.py | 同步必要的模块依赖及当前四个已验证控制文件；避免新依赖在部署后缺失 | 已验证证书 runtime guard/drop-in |
| .github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml | 从 release 内容删除实际研发 authorization；产出可复用包；锁定构建输入、绑定 host policy；生成总发布索引 | exact ARM64、运输模型、独立重新下载校验 |
| .github/workflows/n3w-t1-f4-exact-control-package.yml | 同一冻结 source 产出 F4 与 reboot 子包，供总索引引用；依赖变更更新 path filters | 原 consumer 验包及 transport hash |
| 现有 F2/F4/explicit-provisioning source-ci.yml | 纳入新增公共依赖和调用链测试；准确触发，避免遗漏新文件或无差别扩大固件测试 | 既有安全与正常路径回归 |

F3 内嵌的 runtime-source、Mac wrapper、T1 安装位置和 F4/reboot builder 都必须同步检查依赖；“仓库里有该模块”不等于目标包中能 import。测试应运行实际打包后的入口。

旧研发授权从新生产发行合同中退役；历史记录保持原 ID、consumed/no-replay。任何历史工程兼容入口都要显式、受控，不允许“找不到生产 run 记录就自动退回旧模式”。

### 9.3 原则上直接复用、不主动修改

- host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py：保留单 initializer、原子记录、marker-last 和 resume 合同。若 wrapper/sidecar 足以绑定 parent run，不改其业务状态机；确需添加只读 provenance 字段时才做最小可选扩展并补兼容测试。
- host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py：复用 public staging 和 before_mutation 钩子，不改身份生成与失败 cleanup 的职责。
- tools/n3w_t1_f4_reboot_verify.py：复用现有重启后检查，原则上保持字节不变；F5 外层校验 run 引用，不删除 verifier 的条件。
- tools/n3w_t1_f4_certificate_runtime_guard.py 及现有 systemd/drop-in：保持证书状态演进合同。
- Manager/Broker/HA 的业务状态、TLS、DynSec、身份生成及 MQTT 协议：不为新 UI 重写。
- ESP32 固件、板端注册、无线状态机、Golden Master/Seal/clone 工具：不在范围。
- F4 历史 repair 入口保持工程维护用途；正常 F5 的固定命令白名单不包含 repair-*，输入不能指定任意方法、shell 或阶段跳转。

### 9.4 发布与可持续使用

正常生产不能依赖“最新 CI artifact”。现有 F3 工作流保留 30 天，F4 控制包保留 14 天；F3 已有可校验本地缓存，因此不能说 artifact 一过期现有缓存必然失效。但仅靠临时 CI 留存仍不构成长期发布交付。

F5-7 应生成一个经审核的 approved-release.json，引用全部子包与镜像的不可变 digest，并准备受控、可恢复的发布归档/工位离线副本。发布物从可信 GitHub commit 或批准记录取得摘要；不是由任意本地 manifest 自我背书。CI artifact 到期、缓存丢失时必须还能取到相同字节，否则停止并走新发布，不为每台机器重新构建。

OS/Docker 版本政策按发布冻结。V1 可以先仅批准 T1-A 实际验证、T1-B 将使用的一组版本；以后扩大兼容范围是发布政策与测试变更，不是现场 override。apt 中锁定版本不可用时停止，不自动安装新版。无需在本轮引入整套 OS 快照服务。

容量预检要尽可能证明完整 run 可完成，而不仅是第一张镜像可加载。当前逐步检查能安全阻断空间不足；总发布计划还应保守计入之前已加载镜像、F4/reboot 包、依赖安装和结果空间，避免前置通过后在后半段必然耗尽。

## 10 Plan B 的最小充分实机验收

**T1-A 的既有完整底层证据，加最终 F5 包的隔离验证，再加 T1-B 的一次完整 fresh 路径，可以关闭当前定义的 F5_SECOND_FRESH_INSTALL_REPEATABILITY。默认不需要第三台设备，也不需要擦除 T1-A。**

准确表述是：“当前正式逐台 fresh 安装路线已有两台设备完成，其中第二台使用最终 F5 V1 操作入口。”不能表述为“两台都使用同一个最终 F5 artifact 完成实机安装”，因为事实并非如此。

### 10.1 软件不同不等于不可重复

T1-A 的 F3 起点是旧 6ac82ae…，后续 F4 经修复收口；T1-B 将使用包含 F5 新代码的后继发布。两台 source head、控制工具或整包 manifest 不可能被强行要求相等。

| 比较内容 | 正确要求 |
|---|---|
| 每台 source / artifact / manifest | 分别严格匹配该台批准记录；禁止混用来源 |
| F5 前后的软件差异 | 形成 A→B 的明确差异表；只允许已评审 F5 改造及声明的依赖变化 |
| 相同组件 | 能沿用原 image digest 时沿用；声明未变化的组件必须证明字节或已冻结内容合同一致 |
| 发生重建的 Manager 镜像 | 若 digest 因构建/标签等变化，不擅自说“还是同一个”；验证内容与配置并对差异做测试 |
| 服务拓扑 | 同样的三服务、网络、端口、权限、持久卷与 ingress guard 语义 |
| TLS/ACL | 信任链、主机名验证、独立 service 身份、默认拒绝、认证否定测试均通过 |
| Provisioning/业务状态 | 每机独立初始化，节点/配对等业务状态为空，HA MQTT entry 无重复 |
| reboot | 每台 boot 发生变化，OS/product identity 稳定，持久化和证书生命周期恢复 |
| 最终状态 | 每台有与其准确版本绑定的已接受证据；B 另有完整 F5 终态 |
| 整盘 SHA | 不比较，不作为门槛 |

因此 CI 必须用**相同最终 F5 artifact**在两个全新隔离目标中完整运行，确保重用同一包而不改源码；两个目标分别生成身份与 run。隔离结果补充 B 的物理结果，但不得冒充第二台最终包实机证据。

### 10.2 必须不同的身份

至少核对 OS machine identity、SSH host key、SYSTEM_ID、Manager identity、系统及 Broker CA 公钥、服务器 TLS 公钥、服务凭据身份和密码比较关系。每台还需证明证书/密钥内部匹配、信任关系正确和所有权/权限合格。

仅比较证书文件 hash 不够：序列号或时间不同也能让证书 hash 不同，而密钥仍可能被复制。必须比较公钥身份。仅比较两台 SYSTEM_ID 不同也不能证明所有 MQTT 密码不同。

T1-A 的已有公开关闭证据没有逐项给出全部跨机比较材料。本轮不据此虚构“所有秘密已不同”。下一阶段先复用其已经留存的私有证据；若缺个别必要项，只在另行授权后做 T1-A 的最小只读补证，不重装、不重启、不修改身份。若确实拿不到某项，记录 UNKNOWN 并暂停对应唯一性结论，不能用第三台机器替代缺失事实。

### 10.3 T1-B 的验收路线

1. 官方 Armbian 来源和下载 hash 固定，逐台刷写和首启证据齐全。
2. B 身份与 A 台账不同；Host Key 可信绑定；F2 fresh/readiness 通过。
3. 同一个冻结的 F5 release 使用正常入口，完成一次批准。
4. 完成公共部署：三镜像 exact binding、逐个加载/释放 tar、无实例秘密、无产品服务。
5. 显式 provisioning 到 DEVICE_READY；证明未提前激活。
6. 原 F4 prepare→activate→runtime→persistence→certificate audit→timer 顺序通过。
7. 新 run 中正常路径不调用任何 repair-*，无 shell patch。
8. 一次受控 reboot；第二次密码只用于重新认证；host key/实例身份不变，boot_id 改变。
9. 原 reboot verifier、finalizer、terminal verifier 都通过；不是只看 SSH 可达或日志关键字。
10. 完成 cross-device comparison、安全公开结果和私有台账，关闭 control master。
11. 报告 overall=PASS；由于白名单为空，首轮正式 clean 验收预期不应产生 PASS_WITH_OVERRIDE。

### 10.4 测试长度与板卡范围

当前 _manager_runtime_stability 已有 10 秒窗口，每秒检查同一容器实例/StartedAt 与恰好一个 MQTT 连接；reboot verifier 另有最长 300 秒的部分服务等待。这些是当前程序事实，不代表已经完成长时间老化。

F5 最小门槛复用这些检查并保留每段有界 deadline。没有新增服务启动机制、存储机制或证书定时行为时，不默认加第二次 reboot、数小时 soak 或硬断电。

若实测出现再次重启后才暴露的重复初始化、timer 重入、服务重启增长或落盘不确定性，再针对该风险加一项测试。断电耐久、长期老化、整机上市资格仍属于上位产品验证；F5 流程重复性关闭不能替代它们。

本阶段不需要 ESP32 参与。BOARD_ACCESS=false。T1 验收已有主机认证与运行检查；不要为了证明安装流程再引入节点注册、无线移动或固件烧录。

## 11 F5-0 至 F5-12 实施路线

保留所列阶段名以便追踪，但 F5-1～F5-6 应在一个连贯源码工作包内实现，聚焦测试随改动完成。阶段不是“每项一个 PR/一次人工批准”。只在源码、实机、合并这些实质边界停止。

### 11.1 目标 修改 测试 证据

| 阶段 | 目标与仓库改动 | 测试/检查 | 应产生的证据 |
|---|---|---|---|
| F5-0 | 冻结本报告的授权/SSH/失败/验收合同；更新两份 F5 设计与 current state；按项目规则记录架构决策 | 逐条核对 A1～A15、首次信任、两次密码、状态与责任归属 | 设计 commit、文件 allowlist、批准的验收计划 |
| F5-1 | 实现 run/phase authority；泛化 F3；接 provision/F4；绑定目标与前序台账 | 重放、并发、跨机、过期、篡改、claim/响应丢失、claim→apply 竞态 | 授权合同与聚焦测试结果 |
| F5-2 | 实现 Mac 统一入口与固定正常步骤；repair 隔离；host policy 接入 | 完整正常调用链、越级拒绝、无 TTY、程序重启、子命令异常 | 状态转换表、实际调用链与 CLI 示例 |
| F5-3 | 接入 SSH adapter、首次 key 绑定、主连接/子会话、reboot 重新认证 | 实际 sshd 集成；Mac 兼容；socket 消失不回退；密码不被程序捕获 | 认证次数、连接复用、断线与 cleanup 结果 |
| F5-4 | 静态 CHECK_ID/policy；空 production allowlist；结果传播 | HARD_STOP 不可放行；测试政策下 approve/reject/timeout；unknown ID | check catalog、policy digest、override 测试报告 |
| F5-5 | 固定 result schema、公开/私有分离、最终写入与索引 | 秘密/私有地址泄漏注入、结果不可覆盖、损坏/遗漏检测 | schema、脱敏样例、证据链合同 |
| F5-6 | 合并整体测试、修复首次缺陷，完成 PR 聚焦/full CI | 同一最终候选在两个 fresh 隔离目标；正常链、故障矩阵、包装后入口、原 F3/F4 回归 | exact source 的 CI 与独立源码复核 |
| F5-7 | 从冻结 source 构建完整 release；总索引和依赖/OS policy；工位可恢复缓存/归档 | 下载后独立验 digest/文件集合、ARM64、包依赖、来源、容量；无秘密/真实 run | approved release、source/tree、artifact/manifest/image digest |
| F5-8 | 未来只读核对 B 的 fresh/identity/host readiness；复用 A 证据并补差异表 | 首次 key、首启、空状态、版本、空间、管理权限、A/B 唯一性资料 | B 预检报告、A 参考证据、最新 source/artifact 复核 |
| F5-9 | 对准确 B、准确 release、完整计划建立实机批准与 durable claim | 批准摘要与目标短码一致；期限、阶段、重启预算；两端记录持久化 | 私有批准/run record、公开安全绑定 |
| F5-10 | B 完整执行公共部署、显式 provisioning、F4 直到 PRE_REBOOT_READY | 正常路径无 repair；每阶段已有 check 与台账；空间/版本无 drift | 各阶段结果、消费状态、pre-reboot 快照 |
| F5-11 | 一次 reboot、重连认证、重启后验收、durable finalization、终验及会话关闭 | boot 变化/身份不变；三服务/HA/证书/台账；跨机唯一性；control cleanup | REBOOT_ACCEPTED、完整 F5 result、A/B comparison |
| F5-12 | 整理 source/tests/design/evidence，main 集成及一次终止式对齐 | fresh base/head、required CI、树/文件差异、实际验收包与合并源码一致性 | PR/merge/源内容绑定、当前状态与明确停止点 |

### 11.2 权限 通过 停止 重试 下一门

| 阶段 | 实机 mutation 与授权边界 | PASS 标准 | STOP 与失败后处理 | 下一门 |
|---|---|---|---|---|
| F5-0 | 无 T1；下一轮须获设计/文档写入授权，本轮不执行 | 关键取舍明确，尤其两次密码及信任模型 | 仍承诺无法实现的一次密码跨 reboot，或授权根含糊，停在设计 | F5-1 |
| F5-1 | 仅本地/仓库源码测试 | 每阶段新许可且不可重放；同包可用于两设备 | 先修本地 source/tests，不进入实机 | F5-2 |
| F5-2 | 同上 | 全链可由一个正常入口驱动，实际连接已验证模块 | 复制 F4、暴露任意 repair/命令、丢阶段记录即停 | F5-3 |
| F5-3 | 仅隔离 sshd 与 Mac 测试；不连生产 T1 | 每个连接期只认证一次；重启后明确再认证；无回退 | 发现隐式 key/agent fallback 或密码泄漏，修复后重测受影响项 | F5-4 |
| F5-4 | 无 T1 | 空白名单仍能严格完成正常流程 | 任何全局 force 或未知错误放行即停 | F5-5 |
| F5-5 | 无 T1 | 公开输出只含允许字段；终态可验证 | 缺结果/泄漏/可静默覆盖终态即停 | F5-6 |
| F5-6 | 无真实 T1；测试环境可写 | 受影响测试及 required CI 终态通过，独立 review 无 blocker | 修首个根因，不靠反复 rerun 掩盖；包未冻可继续源码迭代 | F5-7 |
| F5-7 | 无 T1；构建不是实机授权 | 全部 exact 输入与产物绑定、可重复取得、包可执行 | 源/包变化后使旧 release 失效；新包重新绑定 | F5-8 |
| F5-8 | 只有另行授权的只读 T1 访问；无 claim | B 符合 fresh profile，目标/包/空间/身份无未知 | 不运行 apt update 或清理；修预检/准备基线后重新查；必要 A 只读补证另行约束 | F5-9 |
| F5-9 | 顶层 durable claim 是第一项 authority mutation | 明确批准、记录落盘，两端能确认 consumed/no-replay | 领取结果不明即停；查台账；绝不重发同一领取后的 mutation | F5-10 |
| F5-10 | 原批准内安装、身份、服务与持久化变更 | 原工具各阶段通过，无 ad-hoc patch，达到 PRE_REBOOT_READY | 首个实质不符停；按第 7 节分类；修源码须新包/新批准，必要时重刷 | F5-11 |
| F5-11 | 原批准内一次 reboot 和最终台账写入 | durable REBOOT_ACCEPTED、独立终验、会话关闭及证据完整 | 不补发 reboot；纯证据缺陷与产品缺陷分开，必要恢复独立授权 | F5-12 |
| F5-12 | GitHub 写入/合并需相应授权；无 T1 | exact reviewed tree 进入 main，验收绑定不漂移，对齐内容 reachable | 非文档 source drift 重新评估；只补受影响检查，不无限重做完整实机链 | NONE / STOP |

F5-10 与 F5-11 在未来正常生产中是一条连续运行路径，不因表中分段再向操作员索要批准。F5-9 的批准必须一开始就包含它们。当前本轮仅完成设计 review，没有进入其中任何实施或实机 gate。


## 12 源码级测试矩阵

本表是待执行计划，不是本轮测试结果。已有 F3/F4 用例复用；新测试优先测真实边界、进程与打包后的入口，不用大量“字符串包含某关键字”代替行为验证。

| 组别/用例 | 测试方式 | 必须观察的结果 |
|---|---|---|
| 正常 fresh 路径 | 同一候选包对全新隔离目标执行完整入口 | F2→F3→DEVICE_READY→F4→reboot acceptance→终态；无 repair |
| 同包两目标 | 两个独立空根/虚拟机，完全相同 release bytes | 无每机改代码；不同 run/identity；相同软件绑定 |
| 已安装 Docker | 受支持版本、空容器/镜像/卷/默认网络 | 正常通过，不记 override，不重复安装 |
| 缺 Docker | 可信源、锁定包可取得 | claim 在安装前；安装后再次检查版本和存储 |
| OS/包版本漂移 | 不支持 OS、错误架构、未批准 candidate | 无自动升级/降级/override；mutation 前停止 |
| 打包调用链 | 从实际解包目录执行，无仓库额外 sys.path | 所有依赖都在 exact manifest；入口可到达全部正常步骤 |
| unique run | 多次生成及持久领取 | ID 不重复，记录分别绑定设备/计划 |
| arbitrary ID | 仅传随机字符串或合法 F4 前缀 | 没有对应批准记录即拒绝 |
| duplicate claim | 两进程并发领取同 run/phase | 一个成功，另一个明确拒绝；不能两次 mutation |
| apply replay | 复用同 payload marker、同 run 或换目录 | 拒绝第二次 apply；旧 marker 不是长期通行证 |
| wrong device | 复制 A 的批准记录给 B | 当前 OS/SSH/host-instance 绑定不符即停止 |
| wrong artifact/source | 篡改清单、源 head、执行器或子包 | 完整性检查失败且不领取阶段 mutation 权 |
| wrong phase/predecessor | 未 provision 就 activate，或替换上阶段报告 | 目标端拒绝，不依赖 Mac 自觉排序 |
| stale run | 到期、时钟回退、时间不可证明 | 不开始新 phase；记录停止原因 |
| consumed run | 成功/失败/未知后的重新执行 | 只允许 inspect/合规验证，不能重做 mutation |
| ledger 篡改 | 权限、owner、symlink、hardlink、截断、重复 JSON key、未知字段 | 按严格 schema/文件合同停止，不忽略错误字段 |
| claim 崩溃 | 写入前、fsync 前后、返回前注入退出 | 最多一次领取；未知不能显示 reusable |
| Mac/目标账不一致 | 一端落账后另一端失败 | 保留原始证据，只读核对；不得以新 ID 隐藏旧执行 |
| first host-key bind | 网络 key 与可信控制台 fingerprint 比较 | 相同才接受；缺可信值停在信任建立前 |
| known host-key match | 匹配专用 known_hosts | 正常连接，不再人工信任确认 |
| host-key mismatch | 更换 sshd key、同地址换设备 | 密码输入前拒绝；不删除旧 key |
| 密码次数 | 隔离 sshd 日志计数，使用非生产测试凭据 | reboot 前一次认证；reboot 后第二次认证；子步骤零次 |
| ControlMaster reuse | 多次 ssh/scp，核对服务器连接/认证事件 | 确实同一 master，不仅是“没有弹密码” |
| socket loss 竞态 | master check 后删 socket/杀 master | 后续操作失败；没有新直连、agent/key/password 回退 |
| 超时 | 握手慢、密码等待、命令慢分别注入 | 超时分类明确；交互等待不误判产品故障；无无限等待 |
| 非预期断线 | 传输/claim/执行/返回各边界断开 | 停止后继 mutation，状态 UNKNOWN 时不可重放 |
| 预期 reboot | 合法 claim 后切断/恢复 sshd，并模拟新 boot | 有界等待；第二次认证；不重复 actuation |
| SSH cleanup | 正常、Ctrl-C、异常、master 卡住、目录删除失败 | 只处理本 run；活连接未关闭则 overall FAIL |
| 密码与地址泄漏 | 将测试 secret/locator 放入 stdout/stderr/异常/参数模拟 | public JSON、报告、CI 日志、artifact 均不出现 |
| HARD_STOP 放行攻击 | 对 TLS/hash/identity 使用 override 参数 | 永久拒绝；不能修改严重级别 |
| 白名单 approve/reject | 仅测试环境加载可放行 check | 显式批准才继续；拒绝/超时/无 TTY 停止 |
| unknown CHECK_ID | 输入未注册 ID、未知异常 | HARD_STOP |
| override 范围 | 把同一决策重放给下一 phase/不同实际值 | 拒绝；不串用，不存在全局忽略 |
| PASS_WITH_OVERRIDE | 已放行后所有阶段通过，再重新读取结果 | 仍为 PASS_WITH_OVERRIDE，不能降成 PASS |
| claim 前失败 | 无凭据、下载错、预检不通过 | 证明未消费，零系统/产品 mutation |
| claim 后未执行失败 | claim fsync 后故障 | consumed/no-replay，新批准方可再试 |
| partial deployment | 依赖安装、镜像加载、公共提交各点失败 | 失败分类准确，清理只限本 run，未启产品服务 |
| provisioning 失败 | identity/state/DynSec/commit/marker 各点中断 | transaction 保留；不第二次 start；不自动激活 |
| activation 失败 | guard、Broker readiness、services 失败 | 原 F4 rollback 可验证；无法验证时明确 UNKNOWN |
| runtime 验收失败 | TLS/错误凭据/网络/挂载/HA entry/空状态不符 | 不能进入 persistence；保留原停止与 rollback 证据 |
| persistence/certificate 失败 | enable/audit/timer 边界注入 | 原 fail-closed；timer 不提前 active；身份不被重建 |
| reboot 未发生 | SSH 断了但 boot_id 未变 | 拒绝“已重启”结论 |
| post-reboot 失败 | 身份变化、证书变、timer 异常、HA 重复 | 不落 REBOOT_ACCEPTED，不自动二次 reboot |
| finalizer 崩溃 | 写 accepted 前后、返回丢失 | 原子记录；terminal read 能区分已成功与未完成 |
| verify 只读性 | 对 verify 加文件/进程写操作监测 | 不重启、不启服务、不改 target ledger |
| 缺失报告 | exit=0 但 JSON 缺字段、重复/乱序事件 | 不以退出码单独判 PASS |
| 终态不可覆盖 | 重复保存、旧 report 替换新 report | 拒绝覆盖；合法更正另建关联记录 |
| public/private split | 含 locator、原始身份、秘密的私有原件 | 公开只保留允许字段与必要摘要 |
| 容量不足 | 每张镜像前后、F4 包、目标文件系统变化 | 不降低 5 GiB；不得进入必然失败阶段；不泛删镜像 |
| 跨机软件一致性 | 相同最终包双环境 + A/B delta mapping | 共同软件 exact；变化项有批准差异，不比较整盘 hash |
| 跨机身份不一致性 | 故意复制公钥/同密码/系统 ID 测试样本 | 能检出复制，即使证书序列不同也拒绝同 key |
| 未引入 A 秘密 | 扫描发布集合及输入 provenance；模板混入身份样本 | artifact 拒绝任何实例材料；B 唯一性检查失败 |
| 原有 F3/F4 回归 | 复用现有 bootstrap/provision/activation/reboot tests | 原关闭缺陷不回归；旧记录可查、不恢复历史授权 |

建议分层：

- 本地 fast：纯合同、schema、权限/状态模拟、focused pytest、格式及公开仓库安全扫描。
- 隔离 Linux CI：真实 sshd 连接复用、容器 TLS/DynSec/HA 运行合同、打包后的正常入口。
- 虚拟机/隔离系统环境：systemd、重启、两目标同包安装与崩溃注入。不能用一个只会返回 PASS 的假执行器证明完整安装。
- ARM64 构建与兼容：沿用现有构建基础，验证最终三镜像与安装器；Mac 做 transport 兼容，不要求 Mac 承担 Docker 测试。
- 实机：唯一计划中的 T1-B 完整路径；既有 T1-A 不重复做破坏性测试。
- CI 没有真实 reboot/目标能力时明确写 SIMULATED/PENDING，缺的物理项由 T1-B 完成，不能悄悄省略。

## 13 A1 至 A15 逐项答复

| 问题 | 结论 |
|---|---|
| A1 总体架构 | Mac 薄编排 + T1 最小生产 authority + 已有权威 primitives。T1 不新增长期生产管理服务。 |
| A2 唯一入口 | n3w-t1-production run --release <approved-release.json>；目标交互输入。inspect/verify 用于只读诊断，不暴露正常阶段细节。 |
| A3 F3 授权泛化 | 真实 run 授权移出不可变 artifact；目标端持久批准、run/device/source/manifest/phase 绑定及一次性 apply，禁止字符串即许可。 |
| A4 顶层 run | 需要。它连接各既有台账，不复制其业务状态；各 mutation phase 有独立消费记录。 |
| A5 一次人工批准 | 可以，完整摘要必须明确 provisioning/activation/persistence/reboot。首次 key 核验及重启后密码认证另计。 |
| A6 文件范围 | 第 9 节列出四个新增逻辑模块及现有工具/打包/工作流适配；不为 UI 重写 F4。 |
| A7 repair 隔离 | 保留原工程维护入口；F5 固定正常调用白名单，不接受任意 repair 参数或自定义远程命令。 |
| A8 SSH | 同一连接期一次密码；一次 reboot 的完整 run 预计两次密码。首次通过独立可信指纹固定 key；失配和复用失败停止。 |
| A9 override | 初始白名单为空；原已支持的 Docker/元数据情况按正常合同处理；5 GiB 不降。 |
| A10 evidence | 一个稳定结果合同，设备验收/会话关闭/证据完整分别记录，严格公开白名单及私有台账。 |
| A11 Plan B | 足够关闭第二次 fresh 路线重复性，需最终同包双环境 CI、A→B 软件差异审查和必要跨机唯一性证据；不默认第三台。 |
| A12 B 失败 | claim 后禁重放；产品安装路径 defect 修复后通常重刷 B 做 clean 重验；纯连接/结果补记问题不自动擦盘。 |
| A13 扩展测试 | 一个受控 reboot 加既有稳定检查足够本 F5 范围；第二次 reboot/soak/断电仅在具体风险要求时增加。 |
| A14 板卡 | 不需要，BOARD_ACCESS=false。主机工厂流程验收不等于板端 E2E 重新验收。 |
| A15 阻断区分 | 真缺口为通用生产授权、稳定全流程入口/传输、发布环境及结果绑定；SSH 跨 reboot 一次密码是设计冲突。界面美化与隐藏内部命令属于体验改进。 |

## 14 收敛与停止规则

1. F5 设计冻结后，从最新 main 建一个范围清楚的源码工作分支；本轮没有建立该分支。
2. 授权、编排、SSH、check/result、测试和包装依赖放进一个连贯 PR；不按本报告 13 个阶段建 13 个 PR。
3. 独立复核与 required CI 通过后冻结候选 source，构建一个完整 release；T1-B 使用这一准确候选，不用 latest。
4. T1-B 如发现源码 defect，在同一工作脉络修复；旧失败记录永久保留，新包重新绑定，实机按新授权执行。
5. 实机通过后整理公开证据及私有绑定，fresh rebind main/base/head，复核实际验收源与候选内容。
6. 合并方法和 checks 以届时真实仓库规则为准；不得拿本轮只读报告授权合并。
7. 若合并后只是 docs 元数据前进，做产品路径/树等价证明即可，不因 commit SHA 改了就重复安装。若产品字节有实质变化，重做受影响审查和测试。
8. 对齐采用同一 terminating closure rule：准确对齐内容进入 main 即完成，不再产生无限的 post-merge alignment。
9. 固定 F5_PROCESS_CLOSURE=PASS 与 DEVICE_ACCEPTANCE=PASS 的区别。后续用户 onboarding、板卡、OTA、规模化工厂管理仍按各自路线推进。
10. 本报告只读交付，不宣称已成为 GitHub authority。依照本轮禁止仓库修改的要求，没有写入 current state、KF 或 PR 评论；应在下一次获准的设计冻结中归档本报告并绑定摘要。

**当前停止点：架构与源码设计复核完成；实施、CI、T1-B 访问、实机写入与合并均未开始。**

## 15 进一步消除容易误用的细节

### 15.1 UNKNOWN 不是“确定没执行”

结果 schema 应允许 claimed/consumed 的事实值为 UNKNOWN 或 null，同时明确 authorization_reusable=false、replay_allowed=false。执行政策把它按“不可再用”处理，但不能在证据里伪造确定已执行或确定未执行。

正常 read-only retry 不新增 mutation；不因多读一次 ledger 就换 run ID。相反，已领取且执行结果未知时，换一个随机 ID 直接再做同样动作同样不合法。

### 15.2 单工位边界

V1 先按一个受控生产工位、一次处理一台设备设计。Mac 台账用独占锁，T1 也有每设备锁。多台 Mac 并发生产同一设备、复制/丢失整个工位台账、跨工厂全局去重不作为隐含已实现能力。

重刷后的 OS identity 变化必须由物理资产台账关联到同一硬件。机器身份摘要标识的是这次 OS 安装，不是假定不可更改的硬件序列号。两端台账都丢失时不能凭空证明全历史不可重放，应停止并按新的受控登记/恢复决策处理。

### 15.3 最终落账与 SSH 关闭的先后

目标端先完成 durable device acceptance，并在 run ledger 固定目标端阶段事实；Mac 验证并取得报告后关闭连接。Mac 最后生成综合结果，绑定目标端报告 hash 和本地 session_closed 结果。

因此若设备已通过但 Mac cleanup 失败，保留设备已通过事实，综合流程仍 FAIL。不要为了让两端字段一模一样，在关掉连接后再重新连接修改目标账，也不要假装两个文件有分布式原子提交。

### 15.4 认证与授权材料不能混用

产品 CA/TLS 私钥不能用于登录或工位审批。SSH host key 用于确认“连的是谁”，SSH 登录权限用于确认管理者有权操作，run record 用于限制“这次允许做什么”。这三层各有职责。

本方案不新增持久登录密钥、不关闭 password authentication、不建立工厂 CA、不改变账户生命周期。

## 16 复核来源

所有下列仓库链接固定到本轮读取的 main，避免后续移动分支改变引用含义。

### 16.1 正式路线与关闭证据

- [ADR-0010 正式生产路线](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md)
- [F3 R4 实机关闭](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/development/N3W_T1_F3_R4_LIVE_APPLY_CLOSURE_20261015.md)
- [显式逐机 Provisioning 关闭](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/development/N3W_T1_EXPLICIT_PER_DEVICE_PROVISIONING_LIVE_START_CLOSURE_20261015.md)
- [F4 重启后验收](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/development/N3W_T1_F4_REBOOT_SUCCESSOR_LIVE_AND_POSTREBOOT_ACCEPTANCE_CLOSURE_20261016.md)
- [F4 durable 终态与终验](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/development/N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_LEDGER_FINALIZATION_LIVE_AND_TERMINAL_VERIFY_CLOSURE_20261017.md)
- [F4 post-merge 终止式对齐](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/development/N3W_T1_F4_POSTMERGE_STATE_ALIGNMENT_20261017.md)
- [Controlled Override 设计](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/development/N3W_T1_PRODUCTION_CONTROLLED_OVERRIDE_FRAMEWORK_DESIGN_20261014.md)
- [SSH 复用设计](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/docs/development/N3W_T1_PRODUCTION_SSH_CONNECTION_REUSE_V1_DESIGN_20261014.md)

### 16.2 直接支持源码发现的文件

- [F3 授权与公共部署](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/n3w_t1_fresh_product_bootstrap.py)：AUTHORIZATION_ID、_load_manifest、_claim_authorization、execute_claim、execute_apply。
- [Mac artifact/运输/容量与 SSH wrapper](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/n3w_t1_fresh_product_staging_host.py)：_download_artifact、_transport_contract、_plan_transport、_remote_claim_authorization、main。
- [主机依赖安装](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/n3w_t1_fresh_host_baseline.py)：_check、execute_install。
- [F2 现有只读门](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py)：EXPECTED_BLOBS、validate_source、ssh_stream、accept。
- [Provisioning host](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/n3w_t1_device_provisioning_host.py)：_host_identity、_reconcile、main。
- [Firstboot 合同](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py)：start_device_provisioning、resume_device_provisioning、verify_device_ready。
- [F4 激活及验收](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/n3w_t1_f4_activation_host.py)：_prepare、_activate、_accept_runtime、_enable_persistence、_certificate_first_audit、_enable_certificate_timer、_downstream_fail_closed。
- [Reboot authority](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/n3w_t1_f4_reboot_authority.py)：claim_reboot、verify_reboot_claim、finalize_reboot_acceptance、verify_reboot_accepted。
- [重启后 verifier](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/tools/n3w_t1_f4_reboot_verify.py)：verify。
- [F3 构建工作流](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml)
- [F4 精确控制包工作流](https://github.com/chrenguo-stack/HomeAssistant/blob/cdd597e43149e872e26f81c63bc72f4320e61bcc/.github/workflows/n3w-t1-f4-exact-control-package.yml)

### 16.3 用户提供的规划文件

- 温室环境监测系统_分阶段技术开发路线_V0.5_双产品线与接口冻结版(1).docx：第 0、1、6、7 章的产品/身份/运维边界。
- 温室环境监测系统_分阶段技术开发路线_V0.7.docx：第 0、3、6、7、14、15 章及相关职责表。
- 温室环境监测系统_全系统工程简化与架构收敛执行规划_V1.0_20260816(1).md：第 9、15、19、21、27 章，尤其 session+claim+evidence 与复杂度预算。
- 粘贴的文本 (1)(20261017-022839).txt：本轮任务、约束与问题清单。

### 16.4 外部技术核实

- [OpenSSH ssh_config 官方手册](https://man.openbsd.org/ssh_config)：ControlMaster/ControlPersist、BatchMode、StrictHostKeyChecking、ProxyCommand。
- [OpenSSH ssh 官方手册](https://man.openbsd.org/ssh)：控制连接管理与认证。
- [OpenSSH ssh-keyscan 官方手册](https://man.openbsd.org/ssh-keyscan)：未经独立验证的扫描结果不能证明主机身份。

外部手册支持连接与主机密钥的技术语义；具体生命周期、两次密码安排、双端记录及文件拆分是本报告针对当前项目提出的设计建议，仍须按测试矩阵在所支持 Mac/T1 环境验证。