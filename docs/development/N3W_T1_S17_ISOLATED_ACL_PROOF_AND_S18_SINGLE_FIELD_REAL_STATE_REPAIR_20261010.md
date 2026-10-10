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
