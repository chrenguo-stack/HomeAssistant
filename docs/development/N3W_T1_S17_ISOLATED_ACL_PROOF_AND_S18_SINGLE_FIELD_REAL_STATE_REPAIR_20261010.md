# N3-W T1 S17 关闭与 S18 真实 DynSec 单字段原子修复（2026-10-10）

## S17 T1 现场证据：PASS

用户执行仅限一次性数据库/一次性管理员、无宿主网络的动态权限官方命令实测：

```text
S17_PRECHECK=PASS
REAL_DYNSEC_SHA_MATCH=True
REAL_ADMIN_PASSWORD_CONTENT_READ=False
S17_ISOLATED_EXIT_CODE=0
OFFICIAL_DYNSEC_COMMAND=PASS
CANDIDATE_DEFAULT_publishClientSend=False
CANDIDATE_DEFAULT_publishClientReceive=False
CANDIDATE_DEFAULT_subscribe=False
CANDIDATE_DEFAULT_unsubscribe=True
THROWAWAY_CANDIDATE_REMOVED=True
REAL_DYNSEC_STATE_UNCHANGED=True
REAL_ADMIN_PASSWORD_UNCHANGED=True
DOCKER_VOLUMES_PRESERVED=True
HOST_8883_PUBLICATION=False
PRODUCTION_BROKER_STARTED=False
BOARD_ACCESS=False
S17_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

S17 证明 Mosquitto 2.1.2 中在线 `mosquitto_ctrl dynsec setDefaultACLAccess publishClientReceive deny` 正常运行、落盘且只读读取能确认最终 ACL 四元组；**不能**宣称生产 DynSec state 已修复，S16 记录的生产 JSON SHA 仍为：
`93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`。

## S18 下门：克隆真实状态→隔离执行官方命令→精确差异验收→先备份后原子替换

允许明确范围内的唯一真实生产状态修改：`defaultACLAccess.publishClientReceive`: `true` → `false`，其余 JSON 内容在解析语义上必须**完全一致**；不创建/删除/修改管理账号、角色、权限细则、随机凭据或其它系统文件。

S18 进入门：
- 45 个受保护 Docker volume 的确切集合、无容器、`n3wfc4-private` 与 `n3wfc4-services` 无容器、TCP 8883/18883 均未监听、网络基础服务与 `n3wfc4-broker-ingress-guard` 服务 active、enabled、INPUT/DOCKER-USER 首条规则转入护栏且 owned chain 以 DROP 结尾。
- 使用固定 linux/arm64 Mosquitto 2.1.2 本地 image ID `sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408`，不执行 pull；`/etc/n3wfc4/mosquitto.conf` SHA256 必须为 `3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6`。
- 原始 `/var/lib/n3wfc4-broker/dynamic-security.json` 必须 SHA-256 精确匹配 S16 的 `93c751a...`，UID 1883 / mode 0600，目录 UID1883 mode 0700。管理员密码文件 root UID 0 mode 0600，root-only parent mode 0700；若存在未知 staging/backup，STOP，无覆盖。
- 只在 T1 进程内从 root-only 私有文件读入**当前**管理员密码，经标准输入传给短暂隔离容器；仅在其 private tmpfs 内暂时创建 0600 客户端配置，不输出、写 GitHub/本地日志或把口令写入容器环境变量/命令 argv。禁止挂载真实密码文件、CA 密钥、服务器私钥、Docker socket。
- 在 UID1883 隔离容器中以 `--network none --pull never --read-only --cap-drop ALL --security-opt no-new-privileges` 启动临时 loopback `127.0.0.1:18883` 候选 Broker；`/var/lib/.n3wfc4-s18-candidate-*` 目录是生产 DynSec JSON 的**复制品**。对候选执行一次官方命令；停止进程、删除临时容器并精确比较候选 JSON 与生产快照。只有四个默认值中**唯一** `publishClientReceive` 从 true→false，其他 JSON 对象完全相同，才允许进入生产持久状态修补。
- 在真实文件修改前，以 `O_NOFOLLOW|O_EXCL` root 0600 将 exact old bytes 备份到 `/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json`，fsync 后校验 SHA；不涉及 OS/SSH/guard 或其它 Docker 对象。然后在同一真实文件目录内以 UID1883/mode0600 写入并 fsync 新 JSON，通过重新核验 preimage SHA 和主机 STOP 约束后，`os.replace` 原子替换，fsync 目录。旧备份永久保留到后续显式数据清理门。
- 成功后核对真实 JSON 精确语义、四个默认 ACL、唯一 admin、原始管理员口令文件权限与字节内容 hash 不变、临时容器不存在、网络和入口防护不变、45 volumes 集合不变；删除本阶段临时复制状态，仅留下真实新文件+root-only 备份。失败或超时 STOP，不自动重试，不清理可能的部分敏感 stage。
- 本门虽然短暂在 **隔离容器** 内运行了测试 Broker，但不启动生产 Broker、不发布任何 TCP 8883 或宿主18883 端口。不会修改 Manager/HA/节点，也不创建三服务账号。

## 结果边界与后续

```text
S17_RESULT=PASS
S18_NEXT_ONE_GATE=N3W_T1_S18_DYNSEC_EXACT_STATE_SNAPSHOT_ONE_DEFAULT_ACL_ATOMIC_FIX
S18_PRODUCTION_CHANGE_SCOPE=ONE_DEFAULT_ACL_BOOLEAN
S18_KEEP_ADMIN_IDENTITY=TRUE
S18_RETAIN_ROOT_ONLY_OLD_STATE_BACKUP=TRUE
S18_ISOLATED_BROKER_ONLY=TRUE
S18_PRODUCTION_BROKER_START=FALSE
S18_HOST_8883_PUBLICATION=FALSE
S18_BOARD_ACCESS=FALSE
PR541=OPEN_DRAFT
```

S18 通过后另门进行三个业务账号/ACL 的隔离矩阵与生产初始化。官方 DynSec 命令在真实服务未启动时不能凭空执行，必须经候选 + 严格源目标校验进行安全提升。命令脚本仅经本地对话执行；GitHub 保存脱敏设计和审核证据。


## S18 真实执行：候选超范围变更 STOP

用户于 2026-10-10 在 T1 执行 S18 时，**候选差异门失败**：

```text
S18_PRECHECK=PASS
OLD_DYNSEC_SHA_MATCH=True
REAL_ADMIN_PASSWORD_PRINTED=False
S18_ISOLATED_EXIT_CODE=0
STOP_CANDIDATE_MODIFIED_MORE_THAN_ONE_FIELD
SSH_OR_REMOTE_EXIT_CODE=1
```

上一版 S18 控制流已在候选`new_obj != expected_obj`时主动 `SystemExit`，该判定早于 `BACKUP` 新建、`NEW_STATE` 建立和 `os.replace`。因此**脚本已停止于生产写入前**，但仍需下一只读门核对真实 JSON SHA、备份/暂存路径确实未出现、临时无网络容器确实已删除。临时 `/var/lib/.n3wfc4-s18-candidate-*` 包含 production DynSec 的机密**复制品**，应以 sensitive artifact 看待，禁止重跑 S18、删除/上传/打印该目录或其全部 JSON、修改原数据库或创建业务账号。

失败分类：`ISOLATED_CONTROL_RETURNED_SUCCESS`，但`EXACT_ONE_FIELD_SEMANTIC_DIFF=FAIL`。**不能推断具体额外变化**；Mosquitto 插件可能进行状态规范化/补充，需现场最小范围读取 JSON 的结构差异（只列经过过滤的 JSON 路径和数据类型，不输出任何密码、盐值、哈希或客户端凭据），比较真实 SHA 固定值`93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`。目标 default ACL 仍为 `false,false,false,true`，但不能放宽其他字段变化准入直到安全分类清楚。

```text
S18_PRECHECK=PASS
S18_ISOLATED_EXIT_CODE=0
S18_EXACT_ONE_FIELD_COMPARE=FAIL
S18_RESULT=STOP
S18_PRODUCTION_STATE_PROMOTED=NO_SCRIPT_PATH
S18_REAL_STATE_INTEGRITY=NEXT_READONLY_PROOF_REQUIRED
S18_SENSITIVE_CANDIDATE_STAGING=LIKELY_PRESENT
NEXT_ONE_GATE=S18_R1_CANDIDATE_STRUCTURAL_DIFF_READONLY_FORENSIC
S18_R1_T1_MUTATION=false
S18_R1_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S18-R1 只读取证：19 项候选差异

2026-10-10 用户提供真实 T1 S18-R1 只读结果：

```text
REAL_STATE_SHA_MATCH=True
REAL_STATE_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
S18_BACKUP_EXISTS=False
S18_NEW_STATE_STAGING_EXISTS=False
S18_CANDIDATE_DIRECTORY_COUNT=1
REAL_CLIENT_COUNT=1
CANDIDATE_CLIENT_COUNT=1
CANDIDATE_DEFAULT_publishClientSend=False
CANDIDATE_DEFAULT_publishClientReceive=False
CANDIDATE_DEFAULT_subscribe=False
CANDIDATE_DEFAULT_unsubscribe=True
ADDITIONAL_CHANGE_COUNT=19
ADDITIONAL_CHANGE_OUTPUT_TRUNCATED=False
EXACT_ONE_FIELD_COMPARE=FAIL
REAL_STATE_UNCHANGED=True
PASSWORD_CONTENT_READ=False
CANDIDATE_CONTENT_PRINTED=False
CANDIDATE_PRESERVED=True
DOCKER_CONTAINER_CREATED=False
T1_MUTATION=False
BOARD_ACCESS=False
S18_R1_READONLY_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

新增 19 处键位/取值差异类型归纳：

- 顶层 `changeIndex` 新增 integer，`groups` 新增 array：2。
- 唯一管理员客户端的 `textName`→`textname` 为旧键移除/新键新增：2。
- 角色 ACL 8 项均新增 `priority`：8。
- 角色 ACL 中相同**数组索引**的 `acltype` 改变：2；`topic` 改变：4。这不自动意味着权限真正改变，可能是插件保存时 ACL 重排序；但在完整 ACL 集合（type/topic/allow/priority）核对前**不得判断等价**。
- 角色新增 `allowwildcardsubs` bool：1。
- 总计 19。

`S18_REAL_STATE=UNMODIFIED` 已由现场 SHA 再次确认；正式备份、新文件暂存路径均不存在。候选临时目录一个，属于包含真实管理员口令哈希的敏感副本，禁止输出、删除或上传 JSON 原始内容。源状态 admin_only 1、候选 admin_only 1。

项目外上游参考：`https://github.com/eclipse-mosquitto/mosquitto/blob/master/plugins/dynamic-security/migrate_to_dynsec.py` 将 ACL 映射为 `acltype,priority,allow,topic`，role 含 `allowwildcardsubs`、`textname`，顶层含 `groups`；官方 README 定义六种 ACL 类型与默认权限。该来源可解释 schema 变化可能性，但不构成本机新旧 ACL 的等价证明。

下一门限只读的 S18-R2：比较 ACL 多重集合（含 acltype、topic、allow 及默认优先级），排除数组重排的假差异；检查客户端 `textName`→`textname` 的值恒等、`groups` 新增是否为空、`allowwildcardsubs` 值、`changeIndex` 类型与范围；再将**严格受控**的格式归一化后整个 JSON 与唯一预期 default ACL 变化进行对比。除有限布尔/计数/哈希外，不得输出任何密码、密码哈希、salt、管理员凭据、私有 Topic 具体值。继续禁止 S18 重跑及真实数据库原地编辑/晋升。

```text
S18_R1_READONLY_RESULT=PASS
S18_REAL_STATE_SHA_MATCH=true
S18_PRODUCTION_BACKUP_EXISTS=false
S18_REAL_STATE_PROMOTED=false
S18_ADDITIONAL_CHANGES=19
S18_ROOT_CAUSE=PROBABLE_SERIALIZATION_NORMALIZATION_UNCONFIRMED
NEXT_ONE_GATE=S18_R2_ADMIN_ROLE_ACL_MULTISET_NORMALIZATION_READONLY_CLASSIFICATION
S18_R2_T1_MUTATION=false
S18_R2_DOCKER_RUN=false
S18_R2_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S18-R2 管理员 ACL 规范化等价取证：PASS

用户实机 S18-R2 只读报告：

```text
S18_R2_PRECHECK=PASS
OLD_ACL_COUNT=8
CANDIDATE_ACL_COUNT=8
ACL_MULTISET_EQUAL=True
ACL_ORDER_CHANGED=True
CANDIDATE_ACL_NONZERO_PRIORITY_COUNT=0
CLIENT_TEXTNAME_VALUE_PRESERVED=True
GROUPS_ADDED_EMPTY=True
ROLE_WILDCARD_DEFAULT_TRUE=True
CHANGEINDEX_ADDED_VALID=True
CANDIDATE_DEFAULTS_CORRECT=True
WHOLE_JSON_NORMALIZED_EQUAL=True
SERIALIZATION_NORMALIZATION_CLASSIFICATION=COMPATIBLE
REAL_STATE_UNCHANGED=True
PASSWORD_CONTENT_READ=False
JSON_SECRET_VALUES_PRINTED=False
CANDIDATE_PRESERVED=True
DOCKER_CONTAINER_CREATED=False
T1_MUTATION=False
BOARD_ACCESS=False
S18_R2_READONLY_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

**结论分类：** ACL 完整 8 项多重集合不变（忽略排列并为旧项补默认 priority=0），管理员显示名称值不变；新增空组、默认 wildcard 标志、合法 `changeIndex` 与已知 JSON schema 归一化后，完整 JSON 对象仅有 `defaultACLAccess.publishClientReceive=true→false` 的目标权限语义变更。**不能说候选原始文件只有一个字段变化**，其序列化在 S18-R1 实际变化 19 项。生产原始数据库截至本次读取依旧 SHA256 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`，未被晋升。

## S18-R3 执行门：经重复等价确认的候选数据原子晋升

不再运行候选 Broker 或读取业务账户。S18-R3 只做：
1. 复核入口守护 active/enabled、宿主 8883/18883 未监听、容器集合空、45 volumes、两条空项目网络、image id、生产配置 SHA、原始 DynSec SHA/UID/mode、管理员密码根目录与文件 0600。
2. 找到**唯一**保留的 `/var/lib/.n3wfc4-s18-candidate-*` staging，并要求目录为 UID1883 0700、只有经辨认的 `candidate.conf` 与 `dynamic-security.json` 两个文件；候选 DynSec UID1883 0600，不得为符号链接，且校验摘要与二次读取一致。不能再创建或执行 Docker 容器。
3. 在 T1 进程内再次实施 S18-R2 的严格 canonical 对比；同时检测唯一管理员、两个 ACL 集合每条 type/topic/allow/priority 一致，新增 groups=[]、changeIndex 合法、textName 映射恒等、allowwildcardsubs True。
4. 仅当所有精确约束成立且原始备份与暂存文件均不存在时，把**原始文件字节**以 root-only 0600 通过 O_EXCL|O_NOFOLLOW+fsync 写入 `/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json`。核对摘要并 fsync 备份目录。
5. 将已验证候选字节写入原真实数据目录新的 UID1883 0600 隐藏暂存文件，fsync、比较摘要，重验真实文件旧 SHA、防护和管理员密码文件 SHA，最后 `os.replace` 到 `/var/lib/n3wfc4-broker/dynamic-security.json` 并 fsync 目录。
6. 后置再次比较 JSON 目标默认 ACL、唯一管理员、完整 canonical 语义，校验备份/口令 SHA、不变的 volume/网络/guard/port；只有这些全部 PASS，才安全删除**精确**已验证的 stage 两文件和其临时目录。原始 root-only 备份继续保留，禁止自动回滚/覆盖或删除。
7. 错误时 STOP，**不要重跑**；任何可能留下的 backup、new-state 或 sensitive staging 要按新实际状态只读取证，防止因重试覆盖身份。S18-R3 的结果不构成 Broker 正式启动或三个业务服务 ACL 已初始化。

```text
S18_R2_READONLY_RESULT=PASS
S18_R2_NORMALIZATION_COMPATIBLE=true
S18_R3_NEXT_ONE_GATE=N3W_T1_S18_R3_EXACT_CANDIDATE_ATOMIC_PROMOTION
S18_R3_EXPECTED_SEMANTIC_DELTA=ONLY_DEFAULT_PUBLISH_CLIENT_RECEIVE_ALLOW_TO_DENY
S18_R3_ORIGINAL_BACKUP=ROOT_ONLY
S18_R3_PRODUCTION_BROKER_START=false
S18_R3_PORT_PUBLICATION=false
S18_R3_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## S18-R3 实机验收：CLOSED_PASS

用户 T1 2026-10-10 最新执行：

```text
S18_R3_PRECHECK=PASS
ADMIN_ACL_EQUIVALENCE=PASS
NORMALIZED_ONLY_TARGET_DEFAULT_CHANGED=True
CANDIDATE_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
OLD_STATE_SHA256_MATCH=True
ROOT_ONLY_BACKUP=PASS
REAL_DEFAULT_publishClientSend=False
REAL_DEFAULT_publishClientReceive=False
REAL_DEFAULT_subscribe=False
REAL_DEFAULT_unsubscribe=True
REAL_DYNSEC_NEW_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
ORIGINAL_BACKUP_PRESERVED=True
ADMIN_AND_ROLES_PRESERVED_SEMANTICALLY=True
ADMIN_PASSWORD_UNCHANGED=True
SENSITIVE_CANDIDATE_REMOVED=True
DOCKER_VOLUMES_PRESERVED=True
GUARD_PRESERVED=True
PRODUCTION_BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S18_R3_RESULT=PASS
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

验收结论：S18 修复正式完成；生产 Dynamic Security JSON 新 SHA256 为 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`，四项默认权限 `false,false,false,true`。此前 19 个序列化差异已通过 ACL 8 项多重集合、缺省值与全 JSON 规范化等价比较证明没有额外权限语义变化。原始 state 字节副本仅保存在 root 私有 `/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json`；其先前 SHA256 为 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`，按 S18-R3 输出备份未丢、管理员密码未变。候选敏感阶段数据已删除。仍没有实际运行生产 Broker 或新的业务身份认证证据。

下一门 S19：使用已审查 `service_identity_plan.py`、`dynsec_api.py` 作为三类独立服务身份与 ACL source authority；不复用旧服务账号、管理员或临时凭据。只在隔离 Broker、仅限短命凭据中测试 provisioning、manager、homeassistant 的角色、客户端 ID 约束与正反例 ACL，现有生产 DynSec 保持 SHA256 不变，禁止节点板卡访问。真实首次配对节点账号按节点单独创建，不能预先生成一个共用 node 密码。正式 Broker TCP 8883 的启动仍属后续独立验收门。

```text
S18_RESULT=CLOSED_PASS
S18_REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
S18_ORIGINAL_BACKUP=RETAINED_ROOT_ONLY
S18_ADMIN_IDENTITY=PRESERVED
S18_DEFAULTS_DENY=PASS
S18_PRODUCTION_BROKER_STARTED=false
NEXT_ONE_GATE=S19_SERVICE_IDENTITY_ACL_ISOLATED_PREEXECUTION
S19_NO_PRODUCTION_DYNSEC_MUTATION=true
S19_NO_HOST_PORT_PUBLICATION=true
S19_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
