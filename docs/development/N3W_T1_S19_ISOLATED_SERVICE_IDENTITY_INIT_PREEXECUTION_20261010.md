# N3-W T1 S19：三类服务身份的无网络隔离初始化预执行（2026-10-10）

## S18 事实锚点

S18-R3 已在 T1 实机通过：DynSec 初始 admin 的唯一默认接收权限已修复为 deny，生产 JSON SHA256 = `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`。UID1883/mode0600、根目录 0700，root-only 原字节备份 `/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json`，原备份 SHA256 = `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`。S18 敏感候选已安全删除；正式 Broker 未启动，T1 8883 未监听，45 个 Docker 卷和 ingress guard 保持。

## S19 服务身份权威

源代码只取 `host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py` 和 `dynsec_api.py` 中的三服务身份与 ACL，不新增一套产品权限模型。system_id=`greenhouse`，generation=1：

- provisioning：username `ghs_greenhouse_provisioning`，client id `gh-provisioning-greenhouse`，role `gh-service-greenhouse-provisioning`。仅 DynSec 控制请求和响应权限，明确禁止应用 `gh/#` 和 `homeassistant/#`。
- manager：username `ghs_greenhouse_manager`，client id `gh-manager-greenhouse`，role `gh-service-greenhouse-manager`；节点 ingress、网关 ingress、状态 telemetry 订阅/接收、配对 hello、canonical state/当前两种 HA Discovery 发布；禁止 `$CONTROL/#` 和无关 Topic。
- homeassistant：username `ghs_greenhouse_homeassistant`，client id `gh-homeassistant-greenhouse`，role `gh-service-greenhouse-homeassistant`；接收 HA Discovery 与 canonical state，允许发布 `homeassistant/status`，禁止其他应用写入。
- 每个角色使用 `service_identity_plan.py` 中冻结的准确 ACL type/topic/allow/priority；身份使用相互独立的 32 bytes 随机密码，绑定唯一 MQTT client id。管理员与业务账号相互独立。
- 所有服务的 `publishClientSend`/`publishClientReceive`/`subscribe` 默认拒绝，`unsubscribe` 默认允许。将来节点账号依据 `dynsec_plan.py` 在真实首次配对时按节点单独生成，不在 S19 预先创建节点账号。

## S19-R1 唯一允许的执行动作

首次执行仅在 T1 创建临时私有目录，以**新随机临时管理员**初始化与生产相同版本 Mosquitto 动态权限库，然后在一个 `--network none`（仅容器内部 127.0.0.1:18883）、`--pull never`、`--read-only`、`--cap-drop ALL`、`--security-opt no-new-privileges`、`--user 1883:1883` 的无宿主端口发布容器里，一次提交官方 DynSec 控制 API JSON 命令：设置默认 ACL、创建 3 个服务角色、创建 3 个绑定 client ID/角色/随机密码的服务客户端。命令经容器 stdin 传输，密码不出现在 argv、环境变量或 GitHub。

候选数据库必须检查：恰好 4 个客户端（throwaway admin + 3 services）、4 个角色、4 项默认 ACL 符合强制基线、服务用户名/clientid/角色映射准确、每个角色 ACL 多重集合精确匹配 `service_identity_plan.py`、角色优先级正确、无密码明文、临时目录加密性权限。成功后立即删除**仅该阶段创建**的 throwaway 数据；失败时敏感临时数据原位保留并 STOP，先分类取证，不循环重试。

下一阶段才使用新的短命候选执行 3 服务的认证 client ID 绑定和 Topic 允许/拒绝**运行时矩阵**，不得把 S19-R1 的 JSON 结构检查冒充正反例通信通过。真实 DynSec 数据库完全不动且 SHA 保持 `94f3c0...`；原始 root 0600 备份、管理员口令、CA/server TLS 不进入临时容器。

前后检查：宿主无 Docker containers、45 个原有 Docker volume 名称集合无变、两条 n3wfc4 网络无连接、入口 guard active 且规则首位拦截+终止 DROP、宿主 8883/18883 都无监听、镜像 ID/架构、真实新 JSON SHA、root-only 备份 SHA/元数据、生产 mosquitto.conf SHA；严禁启动正式 Broker、Manager/HA 或触碰板卡。

```text
S18=PASS
S19_R1_NEXT_ONE_GATE=N3W_T1_S19_R1_ISOLATED_THREE_SERVICE_IDENTITY_CREATION_AND_STATIC_ACL_PROOF
S19_R1_ONLY_THROWAWAY_PASSWORDS=true
S19_R1_PRODUCTION_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
S19_R1_PRODUCTION_SECRET_MOUNTS=false
S19_R1_HOST_PORT_PUBLICATION=false
S19_R1_LIVE_SERVICE_START=false
S19_R1_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R1 对话下发执行脚本绑定

本次提供给用户下载、然后通过 Mac Terminal 以 stdin 方式在 T1 执行的独立 Python 标准库脚本：

```text
SCRIPT_FILENAME=N3W_T1_S19_R1_ISOLATED_SERVICE_ACL_TEST.py
SCRIPT_SHA256=16e5e130df6078d4106b3596e71c1526f310d9fc9dd889564fd63359253339ae
PYTHON_SYNTAX_CHECK=PASS
ISOLATED_SH_PARSE_CHECK=PASS
T1_RUNTIME=NOT_YET_EXECUTED
REPOSITORY_EXECUTOR_FILE=NOT_COMMITTED_TO_GITHUB
```

脚本程序由对话下载到用户 Mac，使用 `ssh root@T1 'python3 -' <script.py` 在 T1 运行；GitHub 文件只冻结 **哈希** 和安全约束，避免向仓库提交重复的终端执行脚本。不会下载依赖、安装 Python 包或修改 T1 系统软件。


## S19-R1 实测验收（2026-10-10）

结果：`S19_R1_RESULT=PASS`，`S19_R1_ISOLATED_EXIT_CODE=0`。三类服务的临时账号与独立角色均被成功创建，ACL、客户端 ID 绑定和默认拒绝基线静态核查全部 PASS。原始生产 DynSec SHA 未变化，临时数据已删除，没有启动生产 Broker、发布 8883 端口或访问板卡。

S19-R2 仅验证三类身份在无外部网络的独立临时 Broker 中进行真实 MQTT 正向投递、动态权限控制请求以及错误客户端 ID 和匿名连接的拒绝。跨 Topic 禁止矩阵属于后续 gate。新测试账号均为一次性凭据，不复用真实生产管理员与业务凭据。

```text
S19_R1_RESULT=PASS
S19_R2_NEXT_ONE_GATE=ISOLATED_MQTT_POSITIVE_RUNTIME
S19_R2_SCRIPT_SHA256=a660e8bdb546d70218f6ff2033a70640679e4cfb80bb06afbc58a23aba06f16a
S19_R2_PYTHON_STATIC=PASS
S19_R2_SHELL_PARSE=PASS
S19_R2_T1_RUN=NOT_EXECUTED
S19_R2_PRODUCTION_MUTATION=false
S19_R2_BOARD_ACCESS=false
```


## S19-R2 现场失败与取证入口

2026-10-10 T1 S19-R2 实测：

```text
S19_R2_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
SERVICE_IDENTITY_PLAN_SOURCE=main/service_identity_plan.py
S19_R2_ISOLATED_EXIT_CODE=1
ISOLATED_FAILURE_CLASS=ISOLATED_PROBE_FAILED
STOP_S19R2_RUNTIME_PROBE_FAILED_PARTIAL
SSH_OR_REMOTE_EXIT_CODE=1
```

结论：S19-R2 **FAILED_STOP**，未取得任何可声明为成功的运行时 MQTT 正向或拒绝矩阵证据；不得沿用 S19-R1 的静态 ACL 成果冒充 S19-R2 通过。生产 JSON SHA 仅在 S19-R2 执行前确认，失败后必须 fresh readback，才可声明未变。

读回精确聊天下发的执行脚本 SHA256 `a660e8bdb546d70218f6ff2033a70640679e4cfb80bb06afbc58a23aba06f16a`，发现遇到隔离子进程非零退出时，Python 仅打印满足 `STOP_` 前缀的首行或固定 `ISOLATED_PROBE_FAILED`，没有打印内部已通过的非秘密检查点；它在失败路径也不打印原始 stdout/stderr。Docker run 使用 `--rm`，候选独立目录 `/var/lib/.n3wfc4-s19r2-*` 通常保留敏感状态。此时不能推断确切失败属于 provisioning、Manager、Home Assistant、错误 client id、匿名连接或脚本原因。任何源问题/产品失败结论都须待新鲜现场证据。

下一门仅执行 `S19_R2_R1_POSTFAIL_READONLY_FORENSIC`：核实无 Docker container、45 个原有 volume 集合及安全护栏、无 8883/18883 host listener、两项目网络空、生产配置/真实 DynSec/旧备份 SHA 未漂移；准确计数残留候选目录，检查属主权限、是否仅有 candidate.conf 与 dynamic-security.json；只输出 JSON 角色/客户端总数、三服务 client ID 是否正确绑定、默认 ACL 四元组、角色 ACL 项数。**绝不读取真实管理员密码、打印 JSON/哈希/密码、删除候选/修改 T1 或重跑 S19-R2。** 候选 ACL 已持久化成功最多只证明初始化阶段完成，不能推断之后哪一个通信操作失败。必要时基于源脚本独立修复故障可观察性，并在单独新门验证。

```text
S19_R1_RESULT=PASS
S19_R2_RESULT=FAILED_STOP
S19_R2_ROOT_CAUSE=UNKNOWN
S19_R2_EXECUTOR_DIAGNOSTIC_GAP=CONFIRMED
S19_R2_STAGING=READONLY_FORENSIC_REQUIRED
NEXT_ONE_GATE=S19_R2_R1_POSTFAIL_READONLY_FORENSIC
S19_R2_R1_PRODUCTION_MUTATION=false
S19_R2_R1_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


S19-R2-R1 只读取证脚本由本轮对话交付，`N3W_T1_S19_R2_R1_READONLY_FORENSIC.py`，SHA256 `3d2bb820ef94bcd5cc68a08010236ce9df17013bb2947c410305f79e3c15ed0c`，本地 Python 语法检查 PASS，T1 现场执行状态 PENDING。脚本仅用标准库读取候选 JSON 的非敏感结构、静态账号绑定与 ACL 项数，保留所有现存数据且不运行 Docker 容器。候选三服务身份若存在仅代表持久化，不能反推出是哪一个运行时测试步骤失败。


## S19-R2-R1 失败现场只读恢复

2026-10-10 实测结果：

```text
S19_R2_R1_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
PRODUCTION_BACKUP_SHA_MATCH=True
S19_R2_STAGE_DIRECTORY_COUNT=1
STAGE_EXACT_EXPECTED_FILE_SET=True
CANDIDATE_CLIENT_COUNT=4
CANDIDATE_ROLE_COUNT=4
CANDIDATE_DEFAULT_ACL_MATCH=True
CANDIDATE_ADMIN_PRESENT=True
CANDIDATE_PROVISIONING_BINDING=True
CANDIDATE_PROVISIONING_ACL_COUNT_MATCH=True
CANDIDATE_MANAGER_BINDING=True
CANDIDATE_MANAGER_ACL_COUNT_MATCH=True
CANDIDATE_HOMEASSISTANT_BINDING=True
CANDIDATE_HOMEASSISTANT_ACL_COUNT_MATCH=True
SERVICE_IDENTITIES_PERSISTED=True
REAL_STATE_UNCHANGED=True
PASSWORD_CONTENT_READ=False
CANDIDATE_CONTENT_PRINTED=False
CANDIDATE_PRESERVED=True
DOCKER_RUN_THIS_GATE=False
BOARD_ACCESS=False
S19_R2_R1_READONLY_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

结论：临时 DynSec 候选确实持久化 admin + 三类服务的账号、角色、各自唯一 client ID、正确 ACL 计数和默认拒绝值；真实生产 DynSec SHA256 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`、原始 root-only 备份 SHA256 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da` 均未变化。S19-R2 原执行脚本静态复核亦确认：隔离子进程返回非零时，host Python 只保留第一条 `STOP_` 或 `ISOLATED_PROBE_FAILED`；所有非秘密运行时阶段性 stdout 和 stderr 都没有转存，因此无法恢复失败位置。**尚不能将单项 MQTT runtime 正例/反例标记 PASS 或归因到具体产品缺陷。**

唯一遗留资产：`/var/lib/.n3wfc4-s19r2-*` 的**一个**私有敏感 staging（仅 `candidate.conf` 和 `dynamic-security.json`），宿主无容器；下一门 `S19_R2_R2_SCOPED_STAGING_CLEANUP` 只允许 fresh revalidate 后精确删除这两个临时文件和 stage 本身，不修改生产 state/backup/管理员密码、45 Docker volumes、n3wfc4 网络、守护规则或宿主 8883/18883。对失败后临时账号不会进行认证重试，因为原始随机密码只存于已退出进程内存，不在候选数据库中以明文保存。

后续新测试必须增加阶段标记和白名单错误码输出，**不能**打印 stdout 中的完整 `CONTROL_RESPONSE`、password/hash 或 broker stderr；在独立无网络临时 Broker 中使用新 throwaway 密码，区分：`ADMIN_CONTROL`、`PROVISIONING_CONTROL`、`MANAGER_INGRESS`、`MANAGER_TO_HA_STATE`、`MANAGER_TO_HA_DISCOVERY`、`HA_STATUS`、`WRONG_CLIENT_ID`、`ANONYMOUS`。必须实际验证消息投递，不把账号文件存在等价于连接成功。不重用 S19-R2 旧失败脚本。

```text
S19_R2_R1_READONLY_RESULT=PASS
S19_R2_IDENTITIES_PERSISTED=true
S19_R2_PRODUCTION_DYNSEC_UNCHANGED=true
S19_R2_RUNTIME_FAILURE_STEP=UNKNOWN
NEXT_ONE_GATE=S19_R2_R2_EXACT_SENSITIVE_STAGE_CLEANUP
S19_R2_R2_T1_MUTATION=EXACT_FAILED_THROWAWAY_FILES_ONLY
S19_R2_R2_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R2 精确临时数据清理执行文件

基于 S19-R2-R1 已通过的只读现场取证，在对话中下发专用清理执行脚本，不重跑 S19-R2：

```text
SCRIPT_NAME=N3W_T1_S19_R2_R2_EXACT_STAGE_CLEANUP.py
SCRIPT_SHA256=8ac6c40031b7553b24d924b2a65cd8f6b69b23e0049f82406dbb0925e90fb2d7
PYTHON_SYNTAX=PASS
T1_EXECUTION=NOT_YET_EXECUTED
SCOPE=ONLY_ONE_EXACT_.n3wfc4-s19r2-STAGE
PRODUCTION_DYNSEC_MUTATION=false
PRODUCTION_CREDENTIAL_READ=false
DOCKER_CONTAINER_RUN=false
BOARD_ACCESS=false
```

Script 对 T1 做 fresh 守护规则、两空网络、45 Docker volumes 精确名称集合与生产三文件 SHA 复核；要求遗留 staging 唯一、所属 UID1883/0700、仅两个预定 regular 文件（`candidate.conf` 0644 与 `dynamic-security.json` 0600）、文件无额外硬链接、四客户端/四角色、三套服务身份绑定和 ACL 条目数符合先前取证；仅在全通过后删除本临时目录的两个**精确文件**及目录，随后复核生产 state、S18 root 0600 备份和原 45 volumes 无漂移。异常 STOP，不自动重试。**这不定位此前 S19-R2 哪个 MQTT 运行时步骤失败**。

后续新的运行时测试必须以全新一次性凭据、隔离临时容器和安全阶段标记执行：只返回当前阶段与经白名单筛选的故障码，不在终端/仓库中显示完整 DynSec CONTROL 响应、用户名密码、哈希或其他凭据。不将账号持久化等价于 MQTT 正向投递 PASS。


## S19-R2-R2 遗留临时数据清理：CLOSED_PASS

2026-10-10 T1 执行：

```text
SCRIPT_SHA256=PASS
S19_R2_R2_PRECHECK=PASS
STAGE_EXACT_IDENTITY_SET=PASS
PRODUCTION_STATE_AND_BACKUP_SHA=PASS
EXACT_FAILED_STAGE_REMOVED=True
PRODUCTION_DYNSEC_UNCHANGED=True
PRODUCTION_BACKUP_UNCHANGED=True
DOCKER_VOLUMES_PRESERVED=True
BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S19_R2_R2_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

归档结论：S19-R2-R2 CLOSED_PASS，仅删除在 S19-R2-R1 已完成只读取证并确认精确归属的 throwaway stage 与其测试文件；真实生产 DynSec SHA、S18 root-only 备份、45 个 Docker volumes、入口防护和宿主无 TCP/8883 发布均保持。S19-R2 运行时失败根因仍为 UNKNOWN，不得误计 PASS。

后续仅允许全新一次性隔离身份、独立最小 MQTT 运行时诊断。先聚焦首次控制命令、provisioning 认证和请求/响应，返回**阶段性成功标记和白名单失败类**而不打印 MQTT 控制响应、密码、用户名映射 JSON 或秘密。之后再分门 Manager/HA 正向路由与错误客户端 ID/匿名拒绝。失败后保留候选并 STOP，不重新执行旧脚本。

```text
S19_R2_R2_RESULT=CLOSED_PASS
S19_R2_FAILURE_CLASS=UNKNOWN_RUNTIME_STEP
NEXT_ONE_GATE=S19_R2_R3_ISOLATED_PROVISIONING_RUNTIME_PHASE_PROBE
S19_R2_R3_DYNSEC_PRODUCTION_MUTATION=false
S19_R2_R3_HOST_PORT_PUBLICATION=false
S19_R2_R3_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R3 分段可观察性修复：独立 Provisioning 诊断

S19-R2-R2 现场清理已以 `SCRIPT_SHA256=PASS`、`S19_R2_R2_PRECHECK=PASS`、`EXACT_FAILED_STAGE_REMOVED=True`、`PRODUCTION_DYNSEC_UNCHANGED=True`、`PRODUCTION_BACKUP_UNCHANGED=True`、`DOCKER_VOLUMES_PRESERVED=True`、`S19_R2_R2_RESULT=PASS`、`SSH_OR_REMOTE_EXIT_CODE=0` 关闭。不得将清理 PASS 当作 S19-R2 MQTT 运行时 PASS。

S19-R2-R3 选择**最小可验证复现**：只运行全新 isolated admin + provisioning 两个临时客户端，不复用或上传已删除的旧失败候选。仍沿用 main 的 `service_identity_plan.py` 对 provisioning 的 10 条 ACL、两个互不共享的随机 256-bit 以上口令、按客户端 ID 绑定。`--network none` 容器内 `127.0.0.1:18883`，无宿主 port publication、无生产证书/密钥/DynSec 装载。

安全阶段标记：`STEP_INIT_STATE`、`STEP_ADMIN_AUTH`、`STEP_CREATE_SERVICE_TRANSPORT`、`STEP_PROVISIONING_CONTROL`、`STEP_STOP_BROKER`。失败时经固定白名单仅输出 `SAFE_FAILURE_STEP`；完整 MQTT 控制响应仅作为 T1 进程内 JSON 解析输入，不写终端/本地日志/GitHub。因 S19-R2 原执行脚本捕获并吞掉了容器阶段性 stdout，前序失败位置仍 UNKNOWN，不能凭此推断功能根因。新执行仅针对这个可观察性问题增加阶段确证。

对话下载执行文件：
```text
EXECUTION_FILE=N3W_T1_S19_R2_R3_PROVISIONING_RUNTIME_DIAGNOSTIC.py
EXECUTION_SHA256=19c3820c6fd3c8a8e7b9009b3005be6ba02beea5d34b9d7d8ee73dbfa8153bf7
PYTHON_SYNTAX=PASS
SHELL_PARSE=PASS
POSTRESPONSE_REQUIRED_PHASE_MARKERS=ENFORCED
ROLE_ACL_MULTISET_EQUALITY=ENFORCED
T1_RUNTIME=NOT_YET_EXECUTED
SCOPE=ISOLATED_ADMIN_PLUS_PROVISIONING_ONLY
PRODUCTION_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
S18_BACKUP_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
S19_R2_R3_PRODUCTION_MUTATION=false
S19_R2_R3_HOST_PORT_PUBLICATION=false
S19_R2_R3_BOARD_ACCESS=false
NEXT_ONE_GATE=S19_R2_R3_ISOLATED_PROVISIONING_RUNTIME_DIAGNOSTIC
```

若阶段 FAIL：原位保留唯一 `/var/lib/.n3wfc4-s19r2-r3-*`，先做新只读取证，不重新运行旧或新脚本。若 PASS：核实 1 个临时 service + 1 个临时 admin、独立角色、默认拒绝、原生产 JSON/原备份及 45 volumes 未变化并删除精准隔离 stage；该 PASS **仍不能替代** Manager/HA 正向投递、错误 client ID 和匿名接入拒绝矩阵。


## S19-R2-R3 独立 Provisioning 控制链路：CLOSED_PASS

2026-10-10 用户 T1 现场输出（敏感字段未记录）：

```text
SCRIPT_SHA256=PASS
S19_R2_R3_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
S19_R2_R3_SCOPE=ADMIN_AND_PROVISIONING_ONLY
S19_R2_R3_ISOLATED_EXIT_CODE=0
STEP_INIT_STATE=PASS
STEP_ADMIN_AUTH=PASS
STEP_CREATE_SERVICE_TRANSPORT=PASS
STEP_PROVISIONING_CONTROL=PASS
STEP_STOP_BROKER=PASS
ADMIN_CONTROL_RESPONSE=PASS
PROVISIONING_CONTROL_AUTH=PASS
ISOLATED_SERVICE_CLIENT_COUNT=1
ISOLATED_SERVICE_ROLE_COUNT=1
TEMPORARY_SENSITIVE_STATE_REMOVED=True
PRODUCTION_DYNSEC_UNCHANGED=True
DOCKER_VOLUMES_PRESERVED=True
PRODUCTION_BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S19_R2_R3_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

结论：在新建的无外部网络临时 Broker 中，管理员请求与 `ghs_greenhouse_provisioning` 的真实 `listClients` 动态权限管理控制链路均 PASS，独立服务身份与既有 `service_identity_plan.py` ACL 匹配；临时数据清除且真实生产 DynSec SHA `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5` 未变。旧的 S19-R2 FAILED 不能由此定位到 provisioning 原始代码缺陷：旧脚本没有阶段日志而新脚本已修补，不能断言原故障点被实际重现。S19-R2 仍在分阶段验收中；不得宣布全部测试 PASS。

下一门仅做 `S19_R2_R4_MANAGER_HOMEASSISTANT_RUNTIME_POSITIVE`：使用全新一次性 admin、manager、homeassistant 三个账号，无外部网络，验证 manager ingress receive、manager canonical state→HA、HA discovery 两类 topic 和 HA status publish→admin，真实消息体全程比对，具有安全阶段标记与失败分类。暂不扩展到错误客户端 ID、匿名连接拒绝或其他所有 ACL 负例；后续另 gate。

```text
S19_R2_R3=CLOSED_PASS
S19_R2_ORIGINAL_FAILURE_ROOT_CAUSE=UNCONFIRMED
NEXT_ONE_GATE=S19_R2_R4_MANAGER_HOMEASSISTANT_POSITIVE_MQTT_RUNTIME
S19_R2_R4_PRODUCTION_DYNSEC_MUTATION=false
S19_R2_R4_BOARD_ACCESS=false
S19_R2_R4_HOST_PUBLICATION=false
PR541=OPEN_DRAFT
```


## S19-R2-R4 隔离 Manager/HA 正向链路门

S19-R2-R3 实机 `CLOSED_PASS` 后的唯一下一门，保留正式 Broker 关闭、宿主 8883 不开放、真实 DynSec 与 root-only 备份精确 SHA 不变、45 Docker volumes、网络/防火墙护栏保护。使用新的**独立一次性 admin + manager + homeassistant**（三个候选 client，三个 role；无 provisioning/node）和 `service_identity_plan.py` 冻结的 manager 17 条、Home Assistant 9 条 ACL。

仅在 `--network none`、`--read-only`、UID1883、临时 `/tmp`、无宿主端口映射的本地 image `sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408` 容器中执行、取证阶段：
- INIT_STATE、ADMIN_AUTH、CREATE_IDENTITIES；
- `MANAGER_INGRESS`：候选 admin 向 node ingress 发布，manager 真正通过订阅读取带随机标记的消息；
- `MANAGER_STATE_TO_HA`：manager 发布 canonical state，HA 真正收到；
- `MANAGER_DEVICE_DISCOVERY`、`MANAGER_BINARY_DISCOVERY`：manager 发布当前 device 与 binary_sensor config，HA 真正收到；
- `HOMEASSISTANT_STATUS`：HA 发布上线状态，候选 admin 真正收到；
- STOP_BROKER：隔离进程退出。
- 所有正向 PASS 都依靠客户端读取的带随机标记内容等价，不能凭 publish 命令或日志缺失判定。独立随机密码只经 stdin 输入测试容器，临时 0600 option-file；完整 CONTROL_RESPONSE 仅经宿主 Python 进程内解析，不打印。失败只打印固定白名单 `SAFE_FAILURE_STEP`，保留敏感 staging 并 STOP，不重跑。
- 隔离 MQTT 真实投递通过后再检查三客户端、三角色、完整 26 条 ACL 精确内容、默认拒绝、无明文密码。PASS 则精确删除本门临时数据；FAIL 保留取证。正式生产 DynSec `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5` 与 root-only 旧备份 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da` 保持不变。
- 此门不重测 Provisioning，不测试错误客户端 ID/匿名连接或跨 Topic 禁止矩阵；那些是后续独立 gate，不能将 S19-R2-R4 PASS 冒充 S19-R2 全面验收。

```text
S19_R2_R3_RESULT=PASS
S19_R2_R4_EXECUTOR_FILENAME=N3W_T1_S19_R2_R4_MANAGER_HA_POSITIVE_RUNTIME.py
S19_R2_R4_EXECUTOR_SHA256=5f509002f99fc770b6dac9882f32d1c0fb80c97ac5b2469753b4ea709dcaf7c5
S19_R2_R4_PYTHON_SYNTAX=PASS
S19_R2_R4_SHELL_PARSE=PASS
S19_R2_R4_T1_RUNTIME=NOT_YET_EXECUTED
S19_R2_R4_PRODUCTION_MUTATION=false
S19_R2_R4_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R4 现场失败：管理员误用为节点发送端

T1 2026-10-10 现场：

```text
SCRIPT_SHA256=PASS
S19_R2_R4_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
S19_R2_R4_SCOPE=MANAGER_HOMEASSISTANT_POSITIVE_ONLY
S19_R2_R4_ISOLATED_EXIT_CODE=1
STEP_INIT_STATE=PASS
STEP_ADMIN_AUTH=PASS
STEP_CREATE_IDENTITIES=PASS
SAFE_FAILURE_STEP=MANAGER_INGRESS
STOP_S19R2_R4_ISOLATED_PROBE_FAILED_PARTIAL
SSH_OR_REMOTE_EXIT_CODE=1
```

`S19_R2_R4_RESULT=FAILED_STOP`，禁止冒充 Manager/HA 投递 PASS。由于代码在 `MANAGER_INGRESS` 失败后抛出 `SystemExit`，不执行正式生产更改或候选清理；原有独立 throwaway staging 预期残留，需只读取证。

对精确执行源 `N3W_T1_S19_R2_R4_MANAGER_HA_POSITIVE_RUNTIME.py`、SHA256 `5f509002f99fc770b6dac9882f32d1c0fb80c97ac5b2469753b4ea709dcaf7c5` 的源码审核发现首次投递使用：
- SUBSCRIBER = manager，`gh/v1/greenhouse/ingress/node/+/telemetry`
- PUBLISHER = throwaway **admin**，`gh/v1/greenhouse/ingress/node/r4_probe/telemetry`

Mosquitto 官方的 `dynsec init` 创建的管理员角色仅提供对 `$CONTROL/dynamic-security/#` 的发送授权；虽然有对普通 `#` 的**接收/订阅**授权，**没有**对普通业务 Topic 的 `publishClientSend` 授权。官方原文链接：`https://mosquitto.org/documentation/dynamic-security/`。候选默认 publishClientSend=false，因此这套临时测试的发送端违反最小权限，是 **SOURCE_LEVEL_TEST_FIXTURE_DEFECT_STRONGLY_SUPPORTED**。但目前未得到 S19-R2-R4 实际客户端的 PUBACK/SUBACK 错误码，**不能宣称具体网络返回错误已取证**，不能将 Manager 无消息收取当作 Manager ACL 失效。

正确修正（未来 gate）应使用新的隔离临时节点账号、节点 client id 与 `dynsec_plan.py` 生成的该节点 ingress publish ACL 来代替 admin 发送；管理员仍仅做动态权限配置，保留生产默认拒绝和角色 ACL。优先复用真产品节点准入规则，避免临时 admin 拓展业务权限；这不表示真实节点硬件已可访问。

下门 `S19_R2_R4_R1_ADMIN_SEND_ACL_READONLY` 仅在 T1 本机读取精确失败候选的三客户端、三角色绑定和管理员 `publishClientSend` 规则，给出发送端普通应用 Topic 是否可写与 Manager subscribe/receive ACL 是否存在的布尔证据。还要检查真实生产 DynSec/旧备份/生产配置的 SHA256、既有 45 卷、空容器/两项目网络/入口安全链/宿主 MQTT 端口。**不启动容器、不读取密码、不删除敏感 stage、不输出 Topic ACL 原文，不修改 T1。**

```text
S19_R2_R4=FAILED_STOP
S19_R2_R4_PHASE=MANAGER_INGRESS
S19_R2_R4_SOURCE_DEFECT=ADMIN_USED_AS_APPLICATION_PUBLISHER
S19_R2_R4_RUNTIME_ERROR_CODE=UNOBSERVED
S19_R2_R4_R1_SCRIPT=N3W_T1_S19_R2_R4_R1_ADMIN_SEND_ACL_READONLY.py
S19_R2_R4_R1_SHA256=03c77b480427ba8f064426f0fbb72dd9970084a7dc9f9f47a3d489c9e2ad1ea3
S19_R2_R4_R1_PYTHON_SYNTAX=PASS
S19_R2_R4_R1_T1_EXECUTION=PENDING
NEXT_ONE_GATE=S19_R2_R4_R1_ADMIN_SEND_ACL_READONLY
S19_R2_R4_R1_T1_MUTATION=false
S19_R2_R4_R1_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R4-R1 只读管理员发布权限取证：CLOSED_PASS

2026-10-10 用户 T1 现场脱敏证据：

```text
SCRIPT_SHA256=PASS
S19_R2_R4_R1_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
PRODUCTION_BACKUP_SHA_MATCH=True
EXACT_FAILURE_STAGE_COUNT=1
CANDIDATE_CLIENT_COUNT=3
CANDIDATE_ROLE_COUNT=3
ADMIN_CONTROL_PUBLISH_ALLOWED=True
ADMIN_INGRESS_PUBLISH_ALLOWED=False
MANAGER_INGRESS_SUBSCRIBE_ACL_PRESENT=True
MANAGER_INGRESS_RECEIVE_ACL_PRESENT=True
ORIGINAL_TEST_ADMIN_PUBLISHER_UNAUTHORIZED=True
PRODUCTION_DYNSEC_UNCHANGED=True
CANDIDATE_PRESERVED=True
SECRET_CONTENT_PRINTED=False
DOCKER_RUN_THIS_GATE=False
T1_MUTATION=False
BOARD_ACCESS=False
S19_R2_R4_R1_READONLY_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

结论：`S19-R2-R4` 的首次运行时 MANAGER_INGRESS 失败，对应脚本错误地用临时管理员向 `gh/v1/greenhouse/ingress/node/r4_probe/telemetry` 发送；原生动态安全 init 的管理员角色只有控制主题发布授权，不具备此节点入口发布授权，Manager 节点入口的 `subscribePattern` 和 `publishClientReceive` 则按源设计存在。**已确认测试夹具的发送端身份违规；实际 PUBACK/SUBACK 错误码没有被旧脚本取证，不能把此确定为全部可能失败的唯一原因**，更不应拓宽管理员或 Manager 生产 ACL。正确产品复验使用由 `dynsec_plan.py` 派生的隔离临时节点账号作为发送者，不能预先创建共用节点账号；仍禁止实板接入直到 Gate F。

下一门仅 `S19_R2_R4_R2_EXACT_FAILED_STAGE_CLEANUP`：之前单个 `/var/lib/.n3wfc4-s19r2-r4-*` staging（UID1883/0700）中只存在 `candidate.conf` 与 `dynamic-security.json`，临时 3 客户端（admin+manager+homeassistant）、3 角色。使用前置宿主/volume/ingress guard/网络/端口/生产三文件 SHA 检查，并反复验证候选结构后才精确清理两个临时文件及目录。**不运行 Docker、不开端口、不修改真实数据库、S18 私有备份、管理员密码、45 volume 或系统服务。** 失败 STOP，不重跑旧 R4；本门清理 PASS 不等于 Manager 实际投递 PASS。

```text
S19_R2_R4_R1_RESULT=CLOSED_PASS
S19_R2_R4_CAUSE=TEST_FIXTURE_ADMIN_UNAUTHORIZED_INGRESS_PUBLISH
S19_R2_R4_RUNTIME_ERROR=NOT_OBSERVED
S19_R2_R4_R2_SCRIPT=N3W_T1_S19_R2_R4_R2_EXACT_STAGE_CLEANUP.py
S19_R2_R4_R2_SHA256=ae22295be8718182bfd500aa79c8902b6f7edbffe733167ae3836832ecba2325
S19_R2_R4_R2_PYTHON_SYNTAX=PASS
S19_R2_R4_R2_T1_RUNTIME=NOT_EXECUTED
NEXT_ONE_GATE=S19_R2_R4_R2_EXACT_FAILED_STAGE_CLEANUP
S19_R2_R4_R2_PRODUCTION_MUTATION=false
S19_R2_R4_R2_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R4-R2 失败候选清理：CLOSED_PASS；S19-R2-R5 预执行

2026-10-10 T1 实机返回：

```text
SCRIPT_SHA256=PASS
S19_R2_R4_R2_PRECHECK=PASS
S19_R2_R4_R1_EVIDENCE_COMPATIBLE=True
STAGE_EXACT_IDENTITY_SET=PASS
PRODUCTION_DYNSEC_AND_BACKUP_SHA=PASS
EXACT_FAILED_STAGE_REMOVED=True
PRODUCTION_DYNSEC_UNCHANGED=True
PRODUCTION_BACKUP_UNCHANGED=True
DOCKER_VOLUMES_PRESERVED=True
GUARD_PRESERVED=True
PRODUCTION_BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S19_R2_R4_R2_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

S19-R2-R4-R2 = CLOSED_PASS：此前失败 R4 的唯一临时敏感候选已精确清理，生产 Dynamic Security 数据库 SHA 为 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`，S18 原始 root-only 备份 SHA 为 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`，生产未运行，环境不变。这一门仅关闭清理，不表示 Manager 入口实际数据流 PASS。

S19-R2-R5 为单独的隔离正向投递复验：纠正 R4 测试夹具的临时 admin→ingress 发布身份错误，依托 main 的 `dynsec_plan.py` （GitHub blob `380516ec03c68e055ef06375c36c11686f24a1bb`）给**唯一临时测试节点** `n3w_r5_probe` 构建 `ghn_n3w_r5_probe` / MQTT client id `n3w_r5_probe` / role `gh-node-greenhouse-n3w_r5_probe`，使用源码精确 11 条 ACL；main 的 `service_identity_plan.py`（blob `19d95cfe59c12ee0abeaddf8c777fb663a5bd399`）定义 Manager 17 条、HA 9 条 ACL。独立随机临时 admin/manager/homeassistant/node 共 4 client 与 4 role。节点仅向 `gh/v1/greenhouse/ingress/node/n3w_r5_probe/telemetry` 发送，Manager `+/telemetry` 订阅读取并严格匹配标记。其后依次验证 Manager canonical state→HA、两类 HA Discovery→HA、HA status→临时 admin 订阅读取；真实 MQTT 消息比对后才 PASS。

全部仍在已固定 ARM64 Mosquitto 2.1.2 镜像 + `--network none` 的 UID1883 临时 Broker 中执行，不挂载生产证书/密钥/管理员密码/生产 DynSec，不将节点实板接入，不发布任何宿主 MQTT 端口。前后固定核对 T1 网络防护、无容器、45 Docker volumes 名称集合、两个专用空 Docker 网络、生产证书配置及真实 DynSec/备份 SHA。失败只输出阶段与允许的 `SAFE_DELIVERY_FAILURE` 类别，保留临时目录不自动重跑；PASS 删除该门专属敏感目录。

该 gate 是**研发期最小化故障回归测试**，不是量产用户安装流程。真实账号初始化、TLS、正式 Broker 开放与 ESP32-C6 实机首次配对均未获授权。完成此门后仍需错误客户端 ID/匿名接入/跨 Topic 禁止的独立验收。

```text
S19_R2_R4_R2_RESULT=CLOSED_PASS
S19_R2_R5_NEXT_ONE_GATE=ISOLATED_NODE_MANAGER_HA_POSITIVE_RUNTIME
S19_R2_R5_EXECUTOR_FILENAME=N3W_T1_S19_R2_R5_NODE_MANAGER_HA_POSITIVE_RUNTIME.py
S19_R2_R5_EXECUTOR_SHA256=ed00e520eef77feebbc11f63d1373ac5c07f060defa8c22abd5251dc5d19f0f1
S19_R2_R5_PYTHON_SYNTAX=PASS
S19_R2_R5_SHELL_PARSE=PASS
S19_R2_R5_T1_RUNTIME=NOT_YET_EXECUTED
S19_R2_R5_PRODUCTION_MUTATION=false
S19_R2_R5_HOST_PORT_PUBLICATION=false
S19_R2_R5_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R5 合法节点发送端正向通信实测：CLOSED_PASS

用户 2026-10-10 T1 实机提供完整脱敏执行报告：

```text
SCRIPT_SHA256=PASS
S19_R2_R5_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
S19_R2_R5_SCOPE=NODE_MANAGER_HOMEASSISTANT_POSITIVE_ONLY
S19_R2_R5_ISOLATED_EXIT_CODE=0
STEP_INIT_STATE=PASS
STEP_ADMIN_AUTH=PASS
STEP_CREATE_IDENTITIES=PASS
STEP_MANAGER_INGRESS=PASS
STEP_MANAGER_STATE_TO_HA=PASS
STEP_MANAGER_DEVICE_DISCOVERY=PASS
STEP_MANAGER_BINARY_DISCOVERY=PASS
STEP_HOMEASSISTANT_STATUS=PASS
STEP_STOP_BROKER=PASS
ISOLATED_MANAGER_CLIENT_COUNT=1
ISOLATED_HOMEASSISTANT_CLIENT_COUNT=1
ISOLATED_TEST_NODE_CLIENT_COUNT=1
NODE_TO_MANAGER_INGRESS_DELIVERY=PASS
MANAGER_STATE_TO_HA=PASS
MANAGER_DEVICE_DISCOVERY_TO_HA=PASS
MANAGER_BINARY_DISCOVERY_TO_HA=PASS
HOMEASSISTANT_STATUS_TO_ADMIN=PASS
TEMPORARY_SENSITIVE_STATE_REMOVED=True
PRODUCTION_DYNSEC_UNCHANGED=True
PRODUCTION_BACKUP_UNCHANGED=True
DOCKER_VOLUMES_PRESERVED=True
PRODUCTION_BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S19_R2_R5_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

结果：S19-R2-R5 = CLOSED_PASS。基于 main 的产品节点、manager、homeassistant 三套 ACL，隔离无网络临时 Broker 使用节点身份替代 R4 错用的 admin，从节点到 Manager、Manager 的 canonical state、两类 Home Assistant Discovery、HA status 的实际正向发送与接收全部通过；修复的是**测试夹具发送身份**，并不表示扩大管理员权限或测试了实体 ESP32-C6 实板。临时候选包含密码哈希，已删除；真实 DynSec SHA `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`、S18 备份 SHA `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da` 均未变化。生产 Broker 8883 未启动/发布。

此前 S19-R2 及 R4 旧测试 FAILED 证据保留，不能删除历史；S19-R2-R3 provisioning 动态权限控制实测通过，R5 node/Manager/HA 正向消息投递通过。后续尚需：错误 client ID 和匿名连接拒绝（R6A）、跨 Topic 不合法发布/订阅/接收（R6B）、最终再决定是否晋升真实生产身份，不能把 R5 当作全部 ACL 的完备验证。

```text
S19_R2_R5_RESULT=CLOSED_PASS
S19_RUNTIME_PROVISIONING_CONTROL=PASS_FROM_R3
S19_RUNTIME_NODE_MANAGER_HA_POSITIVE=PASS_FROM_R5
NEXT_ONE_GATE=S19_R2_R6A_ISOLATED_AUTH_REJECTION
S19_R2_R6A_PRODUCTION_DYNSEC_MUTATION=false
S19_R2_R6A_HOST_8883_PUBLICATION=false
S19_R2_R6A_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R6A 账号客户端 ID 与匿名拒绝隔离验收

S19-R2-R5 的现场记录已归档 `CLOSED_PASS`：节点→Manager、Manager→HA 状态、两类设备发现与 HA status 真实消息投递全部 PASS。单独下一门 R6A 仅验证身份认证不被绕过，R6B 才验证跨 Topic ACL 禁止矩阵。

本门使用 main `service_identity_plan.py`、`dynsec_plan.py` 的 4 类一次性产品身份：provisioning、manager、homeassistant、仅隔离节点 `n3w_r6a_probe`；每类独立随机口令与冻结的唯一 MQTT client ID。共 4 服务身份+1 临时管理员，角色 ACL 项数 10/17/9/11，角色对象和 clientid 持久化精确校验。正确 client ID 的 provisioning 运行时 `listClients`、manager/HA/node 有权限 Topic 的 QoS1 发布都须先 PASS，然后以**相同账号密码但错误 client ID** 测试四类身份分别被 MQTT CONNECT 拒绝；未认证匿名客户端必须在 CONNECT 阶段拒绝。仅把客户端命令非零返回视为发布失败不够，测试通过 Mosquitto CLI `-d` 解析 CONNACK 是否非 0，输出纯枚举标记而不输出 broker 调试正文/账号密码/控制响应原文。

全程固定 `--network none`、UID1883、无宿主端口映射、本地 Mosquitto 2.1.2 精确镜像；容器仅加载当前 gate 全新随机测试状态。真实数据库 SHA `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`、S18 root-only 备份 SHA `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`、配置 SHA `3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6` 均须固定。45 volumes、2 空项目网络、入口安全规则不变，宿主 8883/18883 无监听，板卡不可访问。失败仅阶段标记 `SAFE_FAILURE_STEP` 并保留敏感候选目录，禁止重新执行；全 PASS 后仅删除本 gate 的暂存文件。

```text
S19_R2_R5_RESULT=CLOSED_PASS
S19_R2_R6A_NEXT_ONE_GATE=ISOLATED_CORRECT_AND_WRONG_CLIENT_ID_ANONYMOUS_AUTH
S19_R2_R6A_SCRIPT=N3W_T1_S19_R2_R6A_AUTH_REJECTION_RUNTIME.py
S19_R2_R6A_SHA256=09df0ac7e5207d041dce0c74453a7f11a6e7dc4d3a1b0318dd86fc9854b82b60
S19_R2_R6A_PYTHON_SYNTAX=PASS
S19_R2_R6A_SH_PARSE=PASS
S19_R2_R6A_T1_EXECUTION=PENDING
S19_R2_R6A_PRODUCTION_DYNSEC_MUTATION=false
S19_R2_R6A_HOST_PORT_PUBLICATION=false
S19_R2_R6A_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R6A 隔离身份拒绝：CLOSED_PASS

2026-10-10 T1 用户提供的完整脱敏门禁结果：

```text
SCRIPT_SHA256=PASS
S19_R2_R6A_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
S19_R2_R6A_SCOPE=VALID_ID_WRONG_ID_AND_ANONYMOUS_ONLY
S19_R2_R6A_ISOLATED_EXIT_CODE=0
STEP_INIT_STATE=PASS
STEP_ADMIN_AUTH=PASS
STEP_CREATE_IDENTITIES=PASS
STEP_VALID_IDENTITIES=PASS
STEP_WRONG_ID_PROVISIONING=PASS
STEP_WRONG_ID_MANAGER=PASS
STEP_WRONG_ID_HOMEASSISTANT=PASS
STEP_WRONG_ID_NODE=PASS
STEP_ANONYMOUS=PASS
STEP_STOP_BROKER=PASS
CORRECT_CLIENT_IDS_AUTHORIZED=PASS
FOUR_WRONG_CLIENT_IDS_REJECTED=PASS
ANONYMOUS_CONNECT_REJECTED=PASS
DEFAULT_DENY_POLICY_PRESERVED=True
TEMPORARY_SENSITIVE_STATE_REMOVED=True
PRODUCTION_DYNSEC_UNCHANGED=True
PRODUCTION_BACKUP_UNCHANGED=True
DOCKER_VOLUMES_PRESERVED=True
PRODUCTION_BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S19_R2_R6A_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

判定：R6A=CLOSED_PASS；Provisioning、Manager、Home Assistant 与隔离测试节点用正确且与 DynSec state 绑定的 client ID 均可完成已授权测试动作，四种原口令 + 错误 client ID 连接及匿名 MQTT CONNECT 均被拒绝。测试通过后临时凭据数据库已删除。生产 DynSec SHA256 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5` 与 S18 root-only 原始备份 SHA256 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da` 未改变，无生产 Broker/端口/板卡操作。

此门只证明 **身份认证**，未证明跨 Topic 发布、订阅或接收全部拒绝。下门 R6B 使用全新 throwaway Broker/账号，在 MQTT 5 QoS1 场景观察明确 PUBACK/SUBACK 拒绝 reason code，而不是仅凭 CLI 命令非零或缺失消息判 PASS；对于 publishClientReceive 做正向投递对照，确保“没收到”不是发送失败或测试断线。禁止使用动态权限管理员来模拟业务发布者。先保持正式软件与板卡不变。
```text
S19_R2_R6A_RESULT=CLOSED_PASS
S19_R2_R6B_NEXT_ONE_GATE=ISOLATED_CROSS_TOPIC_ACL_NEGATIVE_MATRIX
S19_R2_R6B_PRODUCTION_STATE_MUTATION=false
S19_R2_R6B_PRODUCTION_BROKER_STARTED=false
S19_R2_R6B_HOST_PORT_PUBLICATION=false
S19_R2_R6B_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R6B 负向 MQTT 5 ACK 和默认接收拒绝验收门

S19-R2-R6A 现场身份拒绝 = CLOSED_PASS；此次 R6B 不重复账号错 ID 及匿名拒绝测试，仅针对已正确认证账号的**应用权限边界**运行。

从 main 精确复用 `service_identity_plan.py` 与 `dynsec_plan.py` 的 provisioning、manager、homeassistant、单一临时节点四类产品身份；保持 `publishClientSend=false`、`publishClientReceive=false`、`subscribe=false`、`unsubscribe=true` 默认权限。额外使用**隔离环境专属**临时 audit 账号，角色仅具备 `homeassistant/status` 的订阅与取消订阅 ACL，故意不赋予 `publishClientReceive`：专用于证实“允许订阅也不代表允许接收”，**不属于产品账号或产品 ACL**，成功后连同临时数据删除。

测试内容：
1. 先使用原身份在原有合法 Topic 做正向操作，确认 Broker 能工作、账号可以认证；然后以 MQTT v5 QoS 1 的明确拒绝响应做判定，而非仅仅因为 CLI 退出、超时或消息缺失就报 PASS。
2. 四类服务的越权发布：Provisioning→canonical state、Manager→node ingress、HA→canonical state、node→HA status；另检查 node→别的 node ID 入口，共五项。必须取到原连接的 PUBACK（原因码 135，Not authorized）。
3. 四类服务的越权订阅：Provisioning→canonical state、Manager→DynSec control response、HA→node ingress、node→HA discovery，共四项。必须取到 SUBACK 的 Not authorized 135。
4. Default receive deny 的单独机制测试：临时 audit 账号先成功订阅 `homeassistant/status`（有 subscribePattern），然后 HA 通过自己的合法身份发布一个随机标记消息；admin 作为有权接收的对照实际收到完全相同 payload，audit 在限定窗口内不得收到任何 payload。该测试只证明插件的 default receive fail-close 机制，并不创建新的生产服务身份。
5. 隔离候选 DynSec 状态需检查总客户端/角色数（admin+4类产品一次性身份+1类临时审计身份，共6/6）、所有服务绑定及 role ACL 的完整多重集合、四项默认权限，并在成功后精确删除 throwaway 私有目录；失败只输出安全阶段和白名单原因码，保留 staging 再取证。

安全和范围：只使用本地 Mosquitto 2.1.2 ARM64 镜像，`--network none`、只读根文件系统、UID1883、无宿主 `-p`、隔离 `127.0.0.1:18883`；不装载真实动态权限库、证书/密钥、管理员密码；不得启动生产 Broker，不能访问实板。前后核对 T1 护栏、45 Docker volumes 集合与两个项目空网络，生产新 DynSec SHA256 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`，S18 root-only 旧备份 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`，配置 `3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6`。

参考：Mosquitto 2.1.2 上游测试 `test/broker/14-dynsec-acl.py` 与 `14-dynsec-default-access.py` 均以 MQTT 5 `NOT_AUTHORIZED` PUBACK/SUBACK（135）为拒绝凭据；CLI debug 输出属于内部捕获文本，不复制到 stdout/GitHub。如果具体 CLI 版本没有暴露可识别 ACK，则本 gate FAIL-CLOSED 并报告 `SAFE_NEGATIVE_REASON`，不能用“没有收到消息”替代授权凭据。

```text
S19_R2_R6A_RESULT=CLOSED_PASS
NEXT_ONE_GATE=S19_R2_R6B_ISOLATED_CROSS_TOPIC_ACL_NEGATIVE_RUNTIME
S19_R2_R6B_FILENAME=N3W_T1_S19_R2_R6B_CROSS_TOPIC_ACL_NEGATIVE_RUNTIME.py
S19_R2_R6B_SHA256=88325b5542d39221d69da1be7777e80a604d797b07706a37c67ea69428d43e70
S19_R2_R6B_PYTHON_SYNTAX=PASS
S19_R2_R6B_SHELL_PARSE=PASS
S19_R2_R6B_T1_RUNTIME=NOT_YET_EXECUTED
S19_R2_R6B_PRODUCTION_DYNSEC_MUTATION=false
S19_R2_R6B_PRODUCTION_BROKER_STARTED=false
S19_R2_R6B_HOST_PORT_PUBLICATION=false
S19_R2_R6B_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S19-R2-R6B 实机负例验收与 S19 隔离总收口

2026-10-10 T1 现场脱敏证据：

```text
SCRIPT_SHA256=PASS
S19_R2_R6B_PRECHECK=PASS
PRODUCTION_DYNSEC_SHA_MATCH=True
S19_R2_R6B_SCOPE=CROSS_TOPIC_PUBLISH_SUBSCRIBE_AND_TEST_ONLY_RECEIVE_DENY
S19_R2_R6B_ISOLATED_EXIT_CODE=0
STEP_INIT_STATE=PASS
STEP_ADMIN_AUTH=PASS
STEP_CREATE_IDENTITIES=PASS
STEP_VALID_CONTROLS=PASS
STEP_PROVISIONING_DENIED_PUBLISH=PASS
STEP_PROVISIONING_DENIED_SUBSCRIBE=PASS
STEP_MANAGER_DENIED_PUBLISH=PASS
STEP_MANAGER_DENIED_SUBSCRIBE=PASS
STEP_HOMEASSISTANT_DENIED_PUBLISH=PASS
STEP_HOMEASSISTANT_DENIED_SUBSCRIBE=PASS
STEP_NODE_DENIED_PUBLISH=PASS
STEP_NODE_DENIED_SUBSCRIBE=PASS
STEP_NODE_OTHER_ID_DENIED_PUBLISH=PASS
STEP_AUDIT_RECEIVE_SUBSCRIBE_ALLOWED=PASS
STEP_AUDIT_RECEIVE_DENIED=PASS
STEP_STOP_BROKER=PASS
CROSS_TOPIC_PUBLISH_DENIED=PASS
CROSS_TOPIC_SUBSCRIBE_DENIED=PASS
TEST_ONLY_DEFAULT_RECEIVE_DENIED=PASS
DEFAULT_DENY_POLICY_PRESERVED=True
TEMPORARY_SENSITIVE_STATE_REMOVED=True
PRODUCTION_DYNSEC_UNCHANGED=True
PRODUCTION_BACKUP_UNCHANGED=True
DOCKER_VOLUMES_PRESERVED=True
PRODUCTION_BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S19_R2_R6B_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

**R6B 结论：CLOSED_PASS。** 4 类服务/节点候选的越权发布、订阅，以及临时 audit 客户端订阅可用但默认接收拒绝的对照试验通过。临时 admin 和 audit 仅测试环境内存在；没有生产账号、生产权限或生产 Broker 的写入/启动。没有访问真实 ESP32-C6 板卡。

**S19 隔离验证总收口：PASS（范围仅隔离测试）。** R1 产品 ACL 及 identity 结构，R3 Provisioning 管理链路，R5 合法临时节点→Manager→HA 正向投递，R6A 正确/错误 client ID 与匿名连接拒绝，R6B 跨 Topic 发布/订阅/接收负例均 PASS。原 R2 与 R4 的失败保留为测试夹具/可观察性问题历史证据，已通过后续独立门进行修补和有针对性的重新验收，但不能声称原始运行记录被抹除或整个生产部署通过。

生产状态仍旧：
- `/var/lib/n3wfc4-broker/dynamic-security.json`：SHA256 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`，仅 1 admin，4 项默认 ACL `false,false,false,true`。
- `/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json`：旧 state 精确备份，SHA256 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`。原管理员 root-only 口令不变。
- 新增 production provisioning/manager/HA client **仍为零**；应用使用的三份密码尚未生成/交付，无 Manager/HA 真实连接；原始 45 Docker volumes 与 ingress guard 保持，生产 Broker 未启动、host 8883 无监听。
- 固定产品 ACL 源：`host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py`，管理命令源：`host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_api.py`，Node ACL 源：`dynsec_plan.py`。
- 不把研发阶段多步独立取证转换成量产手工安装教程。量产目标为可信一键/工厂自动初始化 + 自动验收 + 出错安全 STOP，仍需独立实施和验证。

下一门**先只读**：`N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT`，核对 source 与 T1 三业务账号凭据存储、生产 MQTT client ID 和口令注入路径、Broker 单独启动/恢复路径、容器权限/卷/宿主端口/证书身份/host TLS 正确性，并定义原子晋升/失败恢复方案；**此门不得创建生产服务账号、不得读取/传播真实管理员明文、不得启动 Broker 或触碰板卡**。只有经三账号凭据保存及运行时消费路径确认，才进入 S20 的独立 production promotion gate。生产动态安全数据库修改前仍应保留 root-only 快照并精确验前验后。
```text
S19_R2_R6B_RESULT=CLOSED_PASS
S19_ISOLATED_SERVICE_IDENTITY_AND_ACL_ACCEPTANCE=CLOSED_PASS
S19_PRODUCTION_SERVICES_CREATED=false
S19_PRODUCTION_BROKER_STARTED=false
NEXT_ONE_GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
S20_INITIAL_MODE=READ_ONLY_SOURCE_AND_STATE
S20_PRODUCTION_MUTATION=false
S20_HOST_PORT_PUBLICATION=false
S20_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
