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
