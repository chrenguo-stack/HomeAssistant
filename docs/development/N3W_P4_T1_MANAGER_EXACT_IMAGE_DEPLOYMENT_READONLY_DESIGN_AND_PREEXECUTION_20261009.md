# N3-W P4 — T1 Manager 精确版本部署：只读设计与执行前检查（2026-10-09）

```text
GATE=N3W_P4_T1_MANAGER_EXACT_IMAGE_DEPLOYMENT_READONLY_DESIGN_AND_PREEXECUTION_20261009_01
GATE_KIND=READ_ONLY_DESIGN_AND_HOST_PREFLIGHT
RUNTIME_IMAGE_REVISION_OBSERVED=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
SOURCE_CANDIDATE_PR=538
SOURCE_CANDIDATE_HEAD=3d86d6bfaf361dc3a3d7295d046f541a544d552d
PR538_CI=12_OF_12_PASS
PHYSICAL_BOARD_P3_FLASH=CLOSED_PASS_20261008
CURRENT_BOARD_P4_NORMAL_BOOT=NOT_PROVEN_NOT_AUTHORIZED_BY_THIS_DOCUMENT
REAL_T1_IP=PRIVATE_NOT_ARCHIVED
REAL_SETUP_SECRET=NEVER_COLLECT_OR_ARCHIVE
T1_RUNTIME_MUTATION=false
IMAGE_BUILD=false
IMAGE_DEPLOY=false
MANAGER_STOP=false
MANAGER_RESTART=false
BROKER_STOP=false
BROKER_RESTART=false
MANAGER_DB_WRITE=false
BOARD_ACCESS=false
BOARD_REFLASH=false
BOARD_FIRST_NORMAL_BOOT=false
REAL_SECRET_IMPORT=false
MERGE=false
STOP_AT_FRESH_EVIDENCE=true
```

## 1. 现场差异的精确根因

用户 Mac Terminal 只读查询确认正在运行的 Manager `Running=true`, `RestartCount=0`, `StartedAt=2026-10-06T15:08:36.478286093Z`; image revision 为 `8fbedc7e0778ce91d146cd5f0772bebdd20ad13a`，与 2026-10-08 已验收的运行连续性相符。本报告不保存实际 T1 IP、image ID 原值、secret、证书或原始数据库路径。

从 GitHub exact revision `8fbedc7e...` 直接核对：
- `registration_cli.py` 没有 `p4-pending-readonly`；
- `n3w_pairing_cli.py` 有 legacy `import --hardware-id/--pairing-id/--setup-secret-stdin`，没有二维码原文 `import-payload --payload-stdin`；
- `runtime/n3w_simplified_pairing.py` 的旧 `import_setup_secret` 不包含 #534 新增的 Registry 锁内 PENDING/expiry-at-use 保护。

因此先前两个 `MISSING` 是新版子命令缺失，与健康的旧 Manager 运行并不矛盾。不得用 legacy import 替代新 QR 流程。

## 2. 源码构建与部署必须区分

候选精确源码：PR #538 HEAD `3d86d6bfaf361dc3a3d7295d046f541a544d552d`，继承 #534/535/536/537 的变更。#537 Manager tests 1262 pass / 1 skipped，#538 仅 Terminal 两文件改动，R3 tests 65/65 PASS，CI 12/12 PASS。所有相关 PR 仍为 Draft、未合并。不能把 PR CI 成功当作已在 T1 运行新版。

允许的后续方案是**独立构建新标签 Manager 镜像、验证 exact source/image binding，然后按 T1 的实际 Compose/运行配置做单实例替换**。不改变固件，不以 bridge-network 仓库旧 `infra/compose/t1/docker-compose.manager.yml` 覆盖实际 host-network Manager。

真正部署前必须先通过三道证据门：
- **R0 现状来源**：正在运行的唯一 Manager/Broker 容器、image ID、source revision、host-network、zero-ports、Compose project/config label，实际容器目的地挂载清单、相关 DB 环境变量*名称和值仅限非秘密路径*、实际 Pending TTL；Broker 原两网络与当前 8883/TLS 配置持续健康。
- **R1 数据与回退**：registration/credential/replay 三个数据库和对应 WAL/SHM、Manager identity/证书资产、Broker/TLS、旧 image ID 与 Compose rendered effective config；只允许完整、同一时间点的可验证数据库备份，不能把运行中 `*.sqlite3` 的裸 `cp` 当作一致备份。先在隔离副本上证明新旧 schema 与迁移/回退兼容；保留旧 image 且回退入口独立。不能重置 replay/high-water、删除旧五身份或重新创建历史节点。
- **R2 exact image 验证**：独立构建标签和 revision，不覆盖正在运行的 `greenhouse-manager:n1`，先在**隔离状态副本**检测新 image 包含 #534 `pending_import_guard`、#536 `p4-pending-readonly`、`import-payload --payload-stdin`；核对实际容器内 `GH_PAIRING_DB_PATH`、`GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH`、`GH_N3W_REPLAY_DB_PATH` 和配对 socket，而不是拿 host 路径冒充 container 路径。仅新镜像 `--help` 检查不足以证明 TTL-at-use guard，必须有准确代码 provenance 和针对性运行时测试。

## 3. Mac Terminal 下一次只读检查

**执行以下代码只读；所有回显仅允许去掉真实目录/私有信息后贴回。** 不启动板，不更改 T1、Broker、Manager。

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'docker inspect --type container --format "MANAGER_RUNNING={{.State.Running}} MANAGER_RESTARTS={{.RestartCount}} MANAGER_STARTED={{.State.StartedAt}} MANAGER_NETWORK={{.HostConfig.NetworkMode}} MANAGER_PORTS={{json .HostConfig.PortBindings}} MANAGER_IMAGE_TAG={{.Config.Image}}" greenhouse-manager'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{json .Config.Labels}}" greenhouse-manager' | python3 -c 'import json,sys; d=json.load(sys.stdin) or {}; print("COMPOSE_PROJECT="+str(d.get("com.docker.compose.project","MISSING"))); print("COMPOSE_SERVICE="+str(d.get("com.docker.compose.service","MISSING"))); print("COMPOSE_FILE_LABEL_PRESENT="+str(bool(d.get("com.docker.compose.project.config_files")))); print("SOURCE_REVISION="+str(d.get("org.opencontainers.image.revision","MISSING")))'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{json .Mounts}}" greenhouse-manager' | python3 -c 'import json,sys,hashlib; a=json.load(sys.stdin); [print("MOUNT_TYPE="+str(x.get("Type"))+" DEST="+str(x.get("Destination"))+" RW="+str(x.get("RW"))+" HOST_SOURCE_SHA256="+hashlib.sha256(str(x.get("Source","")).encode()).hexdigest()) for x in a]'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{range .Config.Env}}{{println .}}{{end}}" greenhouse-manager | grep -E "^(GH_PAIRING_DB_PATH|GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH|GH_N3W_REPLAY_DB_PATH|GH_PAIRING_PENDING_TTL_S|GH_N3W_PAIRING_SOCKET_PATH)=" || true'
```

这组命令没有 `docker exec`、`docker compose up`、`docker build`、`docker stop/restart`、`sqlite3`、读库、写库、重置或刷机。通过的是本地 Python 对 Docker metadata JSON 的**本地**处理，不会通过 SSH 运行或上传 Python 程序。输出仍应人工检查，不要复制其他 `Config.Env` 值（其中可能有密码）。

**STOP 规则：** SSH 失败、inspect 格式错误、找不到 Manager、network 非 host、有 ports、来源或持久挂载不清楚时停止升级准备，不触碰容器。

## 4. 下一阶段部署顺序（本门绝不执行）

1. 收集并复核 §3 只读输出，随后独立读取 Broker 精确网络与 TLS 绑定、实际有效 Compose 来源、三库实际 mount/权限，确认零系统配置变化。
2. 建立精确可回滚的原 Manager 镜像与三库一致备份方案，并在隔离副本演练新版 schema/migration 及旧版回退。没有验证备份 **STOP**。
3. 以 exact #538 镜像来源独立构建不可变新标签/镜像，隔离启动验证命令、UDS 与三库权限；不使用空白初始化替代旧五身份的保留。
4. 制作基于**T1 现场真实 rendered Compose** 的最小 service-only replacement：Manager host network, no ports；Broker 不重建，不改变双网络、TLS 和 advertised auto；更新/回退各有具体镜像/目录/验证证据。
5. 完成独立 review 后才执行一次经新授权的 Manager service 部署及 postflight，确保旧五身份、重放、Broker、Manager 稳定。部署若必须重启 Manager，记录新 `StartedAt` 和合法 restart baseline，不再要求与旧 P2 container ID 一样，避免误判有意升级为意外漂移。
6. 再次做 P4 **新的** preboot readonly check。确认新 code/runtime + P3 板精确硅 ID + 私有 QR channel + 事先独立的 Setup Secret import 授权机制后，才允许第一次产品正常启动。旧 P3 授权已消费，禁重复擦写。产品 boot 与实际 secret import 仍分开。

## 5. 本门结论

```text
ROOT_CAUSE=LIVE_MANAGER_VERSION_BEHIND_P4_SOURCE
SOLUTION_DIRECTION=EXACT_REVISION_MANAGER_ONLY_DEPLOYMENT_AFTER_PROVEN_ROLLBACK
GATE_DESIGN=COMPLETE
FRESH_T1_DEPLOYMENT_LAYOUT=AWAITING_OPERATOR_READONLY_OUTPUT
RUNTIME_IMAGE_REPLACEMENT=NOT_AUTHORIZED_BY_THIS_DESIGN
BROKER_RECREATE=false
DB_MUTATION=false
PRODUCT_FIRST_NORMAL_BOOT=false
SETUP_SECRET_IMPORT=false
STOP=true
```

## 6. 现场第二轮只读取证及 Broker 命令修正（2026-10-09）

操作者从 Mac Terminal 实际读取、未修改 T1：

```text
MANAGER_RUNNING=true
MANAGER_RESTARTS=0
MANAGER_STARTED_AT=2026-10-06T15:08:36.478286093Z
MANAGER_NETWORK=host
MANAGER_PORTS=EMPTY
MANAGER_USER=greenhouse
MANAGER_RESTART_POLICY=unless-stopped
MANAGER_READONLY_ROOTFS=true
MANAGER_INIT=nil
MANAGER_AUTO_REMOVE=false
MANAGER_TMPFS=/tmp:size=16m,mode=1777
MANAGER_CAP_DROP=null
MANAGER_SECURITY_OPT=null
MANAGER_COMPOSE_LABELS=MISSING
BROKER_NETWORK_COMMAND=INVALID_GO_TEMPLATE_NO_BROKER_RESULT
SYSTEMD_N3W_BROKER_ACTIVATION_UNIT=enabled
SYSTEMD_N3W_BROKER_CERTIFICATE_LIFECYCLE_UNIT=static
SYSTEMD_N3W_BROKER_INGRESS_GUARD_UNIT=enabled
REAL_IP_FULL_IMAGE_DIGEST_HOST_SOURCE_HASHES=PRIVATE_NOT_COPIED
T1_MUTATION=false
BOARD_ACCESS=false
SECRET_IMPORT=false
```

**命令错误与责任：**此前提供的 Docker 格式模板中 `range $name,$network := .NetworkSettings.Networks` 触发 `template parsing error: unexpected "," in range`。这是工具命令语法失败，**Broker 容器健康、重启次数、网络连接数量和名称均未获得有效本轮输出**，不能记 Broker FAIL。后续不再使用 Go template 多变量循环，改用 `docker inspect --format '{{json ...}}'`，在 **Mac 本地** Python 只解析公开的非秘密网络名称，不向远程 T1 发送 Python 代码，也不创建新信任检查。

**下一次可直接运行的 Mac Terminal 只读命令：**

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'docker inspect --type container --format "BROKER_RUNNING={{.State.Running}} BROKER_RESTARTS={{.RestartCount}} BROKER_NETWORK_MODE={{.HostConfig.NetworkMode}}" n3wfc4-broker-1'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{json .NetworkSettings.Networks}}" n3wfc4-broker-1' | python3 -c 'import json,sys; obj=json.load(sys.stdin); print("BROKER_NETWORK_COUNT="+str(len(obj))); print("BROKER_NETWORK_NAMES="+",".join(sorted(obj)))'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{json .HostConfig.PortBindings}}" n3wfc4-broker-1' | python3 -c 'import json,sys; obj=json.load(sys.stdin) or {}; print("BROKER_TCP_8883_PUBLICATIONS="+str(len(obj.get("8883/tcp",[])))); print("BROKER_PUBLISHED_PORT_KEYS="+",".join(sorted(obj)))'
ssh -T "$T1_SSH" 'systemctl show n3wfc4-broker-activation.service n3wfc4-broker-ingress-guard.service -p Id -p ActiveState -p SubState --no-pager'
```

前面三条仅读取 Docker 元数据，第 4 条只读取 systemd 状态；不输出真实网络地址、证书、密码、数据库文件、Secret 或绑定宿主机路径。若 `docker inspect` 失败或 Python 解析报错应分类为取证失败，不得臆断 Broker 本身失败或因此自动重启。预期应保留原先 Broker 的完整双网络连接集合，但网络名称与映射必须用当次现场输出决定。因为 systemd 有 Broker activation/ingress guard，绝对禁止在 Manager 单服务升级中隐式重建或更改 Broker。

下一阶段仍需核对 Manager 进程环境、配置/挂载和备份源，在隔离镜像与快照上演练回退，不得凭这一次元数据检查直接修改运行中的服务。

```text
BROKER_NETWORK_CURRENT=UNVERIFIED_BAD_QUERY
BROKER_HEALTH_CURRENT=UNVERIFIED_BAD_QUERY
MANAGER_CREATE_OPTIONS=OBSERVED_READONLY
MANAGER_SOURCE_MATCH=OLD_IMAGE
P4_PRECLAIM_READY=false
MANAGER_DEPLOYMENT=false
BOARD_FIRST_BOOT=false
STOP_AT_NEXT_READONLY_EVIDENCE=true
```

## 7. 第三轮 Broker 现场结果及 Manager 升级前的恢复来源检查（2026-10-09）

操作者最新的**实际只读输出**：

```text
BROKER_RUNNING=true
BROKER_RESTARTS=0
BROKER_NETWORK_MODE=n3wfc4-private
BROKER_NETWORK_COUNT=2
BROKER_NETWORK_NAMES=n3wfc4-private,n3wfc4-services
BROKER_TCP_8883_PUBLICATIONS=1
BROKER_PUBLISHED_PORT_KEYS=8883/tcp
BROKER_ACTIVATION_SERVICE=active/running
BROKER_INGRESS_GUARD_SERVICE=active/exited
BROKER_CURRENT_TLS_HANDSHAKE=NOT_RECHECKED
BROKER_8883_HOST_BIND_ADDRESS=NOT_YET_CLASSIFIED
MANAGER_RUNTIME_MUTATION=false
BROKER_RUNTIME_MUTATION=false
BOARD_FIRST_NORMAL_BOOT=false
```

**证据解释：** Broker 运行、重启次数和精确的双网络连接已核对；8883/tcp 映射数量为 1，但目前尚不知道绑定的 HostIp 是否为 IPv4 wildcard，也未重做当前 TLS server-name 验证。`active/exited` 的 ingress-guard 可以是正常的 oneshot 服务状态，**不是**系统故障证据，也**不等于**该守护规则的当前功能验收。Manager 替换不能重建或重启 Broker，不得按仓库旧 Compose 重新布线。

实际 Manager 则是 `greenhouse` 用户、host 网络、零 ports、readonly rootfs、`/tmp` 16 MiB tmpfs、`unless-stopped`，未发现 Compose label。旧 image ID 必须在现场私有证据中保留，不能假设镜像 tag 可以再次拉取。当前最小只读下一步只确认旧 image 是否仍存在于本地镜像存储、实际 entrypoint/Cmd 的*参数数量*，并将 Broker 8883 的 `HostIp` 分类输出而**不输出具体地址**。

Mac Terminal 可直接执行：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'img=$(docker inspect --type container --format "{{.Image}}" greenhouse-manager) || exit 1; docker image inspect --format "OLD_IMAGE_AVAILABLE=true OLD_IMAGE_BYTES={{.Size}} OLD_IMAGE_REVISION={{index .Config.Labels \"org.opencontainers.image.revision\"}}" "$img"'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{json .Config.Entrypoint}}" greenhouse-manager' | python3 -c 'import json,sys; v=json.load(sys.stdin) or []; print("MANAGER_ENTRYPOINT_ARGS="+str(len(v)))'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{json .Config.Cmd}}" greenhouse-manager' | python3 -c 'import json,sys; v=json.load(sys.stdin) or []; print("MANAGER_CMD_ARGS="+str(len(v)))'
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{json .HostConfig.PortBindings}}" n3wfc4-broker-1' | python3 -c 'import json,sys,ipaddress; d=json.load(sys.stdin) or {}; entries=d.get("8883/tcp",[]); print("BROKER_8883_ENTRY_COUNT="+str(len(entries))); print("BROKER_8883_HOSTIP_TYPES="+",".join("wildcard" if e.get("HostIp","") in ("","0.0.0.0") else ("loopback" if ipaddress.ip_address(e.get("HostIp")).is_loopback else "specific") for e in entries))'
```

**失败处理：** 命令失败只代表没有取得对应证据，不代表服务故障。若本机找不到正在运行的旧镜像，或 Broker 绑定类型异常，停止升级方案，不停止正在运行的服务。即便以上均满足，镜像构建、在线/停机一致备份、回退演练和服务替换仍需独立的操作包，不能直接按本只读输出开始。

```text
BROKER_RUNNING=PASS
BROKER_DUAL_NETWORK=PASS
BROKER_SINGLE_8883_TCP_PUBLICATION=PASS
BROKER_TLS_HANDSHAKE=NOT_RECHECKED
MANAGER_BACKUP_RESTORE=NOT_YET_VALIDATED
MANAGER_EXACT_IMAGE_BUILD=NOT_STARTED
MANAGER_LIVE_DEPLOYMENT=NOT_STARTED
P4_FIRST_NORMAL_BOOT=false
NEXT_ACTION=READONLY_OLD_IMAGE_PRESENCE_AND_8883_BIND_CLASSIFICATION
STOP=true
```

## 8. 旧镜像回退基础及 Broker 8883 绑定取证闭环（2026-10-09）

操作者最新只读输出：

```text
OLD_IMAGE_AVAILABLE=true
OLD_IMAGE_BYTES=59124574
MANAGER_ENTRYPOINT_ARGS=1
MANAGER_CMD_ARGS=0
BROKER_8883_ENTRY_COUNT=1
BROKER_8883_HOSTIP_TYPES=ipv4_wildcard
BROKER_RUNNING_PREVIOUS=true
BROKER_RESTARTS_PREVIOUS=0
BROKER_NETWORKS_PREVIOUS=n3wfc4-private,n3wfc4-services
MANAGER_STOP=false
MANAGER_DEPLOY=false
BROKER_RESTART=false
P4_BOARD_FIRST_BOOT=false
SECRET_IMPORT=false
```

旧 Manager image 仍可通过本地 Docker image store 读到，构成以后回退的**必要但不充分**条件。完成回退还需将相同的容器启动参数、网络、环境变量的**私有完整源**和独立挂载精确重建，最关键是保护已经存在的数据库；不能把旧镜像存在等同回退已准备完成。Broker 唯一 8883/TCP publication 使用 IPv4 wildcard，连同上一轮双网络证明当前基本架构满足预期；但本门未重新验证 TLS handshake、Manager 实际对 Broker 的端到端连接。

**审阅代码后的备份补充发现：** `host/greenhouse-manager/src/greenhouse_manager/ops/t1_backup.py` 的 `COPY_SOURCES` 指向 `mosquitto` 和 `greenhouse-manager:/var/lib/greenhouse-manager`，并通过 `docker cp --archive` 复制。当前 P4 真实注册数据库却是单独的 `/var/lib/greenhouse-manager-registration/registration.sqlite3`，N3W 数据与 relay-keys 又分别绑定在不同位置。该旧备份程序**不适合此运行态**，不能宣称覆盖 P4 三个数据库或保证多个运行中 SQLite/WAL 的一致性。不得依赖未经演练的 `docker cp` / `tar` 拷贝活库作为可靠回退。

**接下来要执行的只读取证：** 先检查三个数据库现存及大小、容器 SQLite 运行库、宿主机 Docker 路径可用磁盘空间。数据库查询与文件复制不在此步骤；不对活数据库运行备份、checkpoint、VACUUM、pragma 写操作。若任何数据库路径不存在，立即标记工具/布局预检失败而非 Manager 产品故障。

Mac Terminal：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'docker exec greenhouse-manager stat -c "SQLITE_FILE_BYTES=%s" /var/lib/greenhouse-manager-registration/registration.sqlite3 /var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3 /var/lib/greenhouse-manager/n3w/replay.sqlite3'
ssh -T "$T1_SSH" "docker exec greenhouse-manager python3 -c 'import sqlite3; print(\"SQLITE_RUNTIME_VERSION=\"+sqlite3.sqlite_version)'"
ssh -T "$T1_SSH" 'd=$(docker info --format "{{.DockerRootDir}}") || exit 1; df -Pk "$d" | awk "NR==2 {print \"DOCKER_DISK_AVAILABLE_KIB=\"\$4}"'
ssh -T "$T1_SSH" 'docker exec greenhouse-manager sh -c "test -S /tmp/greenhouse-manager/pairing.sock && echo PAIRING_SOCKET_PRESENT=true || echo PAIRING_SOCKET_PRESENT=false"'
```

后续必须在 T1 **实际容器配置**基础上设计私有、完整的 service-only replacement 与一致性备份方式，包括 source + destination + readonly 标记、旧镜像私有 ID、DB 与 WAL/SHM、嵌套 relay key mount、Broker/TLS 证书权限、Manager env 值的秘密保护和旧五身份快照。跨三个不同 SQLite 库的原子性不能靠独立逐库在线 backup 假设；优先设计可以验证的单写入者停写窗口，并证明服务关闭后数据完整、可恢复，再重新启用 Manager。部署时仍不可重建 Broker。受控停写/服务替换是**后续另行定义**的变更，不由此只读文档执行。

```text
RUNTIME_BROKER_BASIC=PASS
OLD_IMAGE_AVAILABLE=PASS
ROLLBACK_COMPLETE=false
OLD_GENERIC_T1_BACKUP_SUITABLE=false
BACKUP_SOURCE_DB_EXISTS=PENDING
SQLITE_RUNTIME_TOOLING=PENDING
DISK_CAPACITY=PENDING
MANAGER_LIVE_DEPLOYMENT=false
BOARD_NORMAL_BOOT=false
NEXT_ACTION=MAC_TERMINAL_READONLY_SQLITE_FILES_AND_CAPACITY
STOP=true
```

## 9. P4 三个数据库与工具链预检（2026-10-09）

操作者 Mac Terminal 实际只读证据：

```text
REGISTRATION_DB_MAIN_BYTES=675840
CREDENTIAL_LIFECYCLE_DB_MAIN_BYTES=28672
REPLAY_DB_MAIN_BYTES=8134656
PYTHON_SQLITE_RUNTIME_VERSION=3.46.1
DOCKER_DISK_AVAILABLE_KIB=6153948
PAIRING_SOCKET_PRESENT=true
WAL_SHM_SIDE_CARS=NOT_YET_INVENTORIED
OTHER_MANAGER_PERSISTENT_FILES=NOT_YET_INVENTORIED
T1_SQLITE_BACKUP_CREATION=false
T1_SERVICE_MUTATION=false
MANAGER_IMAGE_BUILD=false
MANAGER_IMAGE_DEPLOY=false
BOARD_NORMAL_BOOT=false
REAL_SETUP_SECRET_IMPORT=false
```

上述数据是三个 **主库文件** 的大小，不包括任何在用 WAL/SHM、其他数据库、密钥或状态文件；磁盘可用空间为 T1 Docker 数据目录所在文件系统可用量，不证明所有目标备份目录有同等容量。`PAIRING_SOCKET_PRESENT=true` 只说明 Unix socket 存在，不证明新 P4 导入子命令部署或其正确处理逻辑。

### 9.1 备份设计与保证边界

- **禁止**直接把三个运行中 SQLite 主库依次 `cp` 或 `docker cp` 当作共同一致、可回退的备份；不得单独运行 WAL checkpoint/VACUUM 改写生产状态。
- SQLite 单库 `Connection.backup` 能产生单库一致快照，**不提供独立三个数据库跨库的原子一致性**；新镜像的升级回退不能仅凭各库单独 `backup()` 判定 PASS。
- 默认设计优先使用有明确停写边界的**一次 Manager 受控停机窗口**，在容器确已停止且无其他写入者的条件下备份全部相关持久目录（含 registration 独立挂载、N3W 挂载与嵌套 relay-keys 挂载、必要证书/Secret 的原始私有源；Broker 独立服务不得停机/重建）。停机后的只读完整性验证及隔离恢复演练均通过后，才进行新版容器替换；如果有其他写入者或旧容器不可重新启动，应 STOP 而非冒险更新。**停机是后续部署动作，本门没有执行或授权。**
- 原始 `docker inspect` 中 Env/HostConfig/Mounts 可能包含敏感信息；后续授权部署包应将完整可复现容器配置以 mode-0600 保存在 T1 本地受保护区域，不上传 GitHub/聊天，公开日志仅记 hash/条件结果。旧镜像的本地可用性已证实，不代表完整回退已证明。

### 9.2 下一组无数据库读写、无服务重启的联合检查

直接在 Mac Terminal 运行：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'docker exec greenhouse-manager sh -c '"'"'for p in /var/lib/greenhouse-manager-registration/registration.sqlite3 /var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3 /var/lib/greenhouse-manager/n3w/replay.sqlite3; do b=${p##*/}; for ext in "" -wal -shm; do f="$p$ext"; if test -f "$f"; then stat -c "DB_SIDECAR=$b$ext STATUS=present BYTES=%s" "$f" || exit 1; else printf "DB_SIDECAR=%s STATUS=absent\n" "$b$ext"; fi; done; done'"'"''
ssh -T "$T1_SSH" 'command -v git >/dev/null 2>&1 && git --version || echo T1_GIT=NOT_AVAILABLE'
ssh -T "$T1_SSH" 'docker buildx version >/dev/null 2>&1 && echo T1_DOCKER_BUILDX=AVAILABLE || echo T1_DOCKER_BUILDX=NOT_AVAILABLE'
ssh -T "$T1_SSH" 'docker exec greenhouse-manager df -Pk /var/lib/greenhouse-manager-registration /var/lib/greenhouse-manager/n3w' | awk 'NR>1 {print "DB_SOURCE_FS_AVAILABLE_KIB="$4}'
```

命令只执行 `stat`、`git --version`、`docker buildx version` 和 `df`；没有 SQLite connection、数据库写入、服务停机、镜像构建或拉取。它只识别现有 WAL/SHM 的大小与数据库挂载源所在文件系统余量，后者不等于未来备份目标的空间。不存在 WAL/SHM **不构成产品故障**；由新镜像升级前可验证备份设计判断。若某个命令取证失败，仅记录没有证据，不把 Manager 判为失败。

这组输出通过后直接实施**源代码层面的** P4 私有备份/镜像构建执行包与合成测试，随后才请求 Mac 现场运行隔离构建/备份演练，不把源码 CI 当成真实回退证据。

```text
THREE_MAIN_SQLITE_DATABASES_PRESENT=true
SQLITE_PYTHON_RUNTIME_AVAILABLE=true
SOCKET_FILE_PRESENT=true
DISK_CAPACITY_BASIC=AVAILABLE_NOT_BACKUP_GUARANTEE
BACKUP_ISOLATION_PLAN=SOURCE_DESIGN_ONLY
WAL_SHM_INVENTORY=WAITING
EXACT_IMAGE_BUILD_TOOLCHAIN=WAITING
ACTUAL_ROLLBACK_REHEARSAL=false
T1_MANAGER_MUTATION=false
P4_BOARD_FIRST_NORMAL_BOOT=false
STOP_AT_FRESH_INPUT=true
```

## 10. P4 数据库附属文件闭环与独立候选镜像构建（2026-10-09）

操作者 Mac Terminal 最新结果：

```text
REGISTRATION_SQLITE_MAIN_BYTES=675840
CREDENTIAL_LIFECYCLE_SQLITE_MAIN_BYTES=28672
REPLAY_SQLITE_MAIN_BYTES=8134656
REGISTRATION_WAL_PRESENT=false
REGISTRATION_SHM_PRESENT=false
CREDENTIAL_WAL_PRESENT=false
CREDENTIAL_SHM_PRESENT=false
REPLAY_WAL_PRESENT=false
REPLAY_SHM_PRESENT=false
PYTHON_SQLITE_VERSION=3.46.1
GIT_VERSION=2.53.0
DOCKER_BUILDX_AVAILABLE=true
DOCKER_DISK_AVAILABLE_KIB=6153948
MANAGER_DB_SOURCE_FS_AVAILABLE_KIB=6153816
MANAGER_REGISTRATION_FS_AVAILABLE_KIB=6153816
PAIRING_SOCKET_PRESENT=true
MANAGER_RUNNING_PREVIOUS=true
BROKER_RUNNING_PREVIOUS=true
MANAGER_IMAGE_UPGRADE=false
```

三库 `-wal/-shm` 当时不存在不能推出未来不会产生，也不能把运行中数据库复制当作共同一致备份。磁盘余量约 5.9 GiB，足以考虑候选镜像**独立准备**，但首次构建实际占用无法事先证明；构建一旦接近磁盘最低余量，必须中断，不能为了腾空间执行 `docker system prune` 或移除现有镜像/容器。

### 10.1 2026-10-09 网络限制修正：先停止上一版 T1 在线构建步骤

现场新增限制：**T1 不能直接访问 GitHub**。因此上一版由 T1 执行 `git fetch` 的命令在该网络条件下不可执行；**上一版 §10.1—10.3 的 T1 在线获取源码与直接 buildx 命令全部撤销，禁止继续执行。**

不仅 `git fetch` 需要 GitHub：现有 `host/greenhouse-manager/Dockerfile` 以 `python:3.11-slim` 为基础，并包含 `python -m pip install --upgrade pip` 和 `python -m pip install .`。如果 T1 没有全部基础层与 Python 依赖缓存，`docker buildx build` 还会需要 Docker Hub / Python 包站点；Dockerfile 并不支持可靠的无网络构建。**无需将 T1 无 GitHub 误判为 Manager、Broker 或 Docker 故障。**

推荐离线部署准备路线：

1. 在 **Mac** （前提是其能访问 GitHub 与构建依赖）取得 PR #538 exact commit，严格校验 SHA：`3d86d6bfaf361dc3a3d7295d046f541a544d552d`。
2. 在 Mac 上，若有可用的 Docker Desktop/Buildx，按 T1 当前生产镜像的实际 `linux/<架构>` 构建 **单架构** 候选镜像，打独立标签与 revision 标签；记录候选完整 image ID 及依赖构建来源。**不要**根据 Mac 芯片架构猜 T1 的架构。
3. 在 Mac 上以 `docker save` 输出候选镜像流，通过已有 SSH 输入送给 T1 `docker load`，不需要 T1 访问任何外网。该操作仅把独立候选镜像添加到 T1 镜像存储，**不会**替换或重启 `greenhouse-manager` 和 Broker。检查镜像 ID、OS/architecture、revision 后做 `--network none`、无实际数据库/秘密挂载的 CLI 和源码 guard 隔离检查。
4. Mac 没有 Docker/Buildx 或不能构建 T1 目标架构时，使用 GitHub Actions 创建明确绑定 exact SHA 的镜像构建产物、通过能访问 GitHub 的 Mac 下载后传送 T1；禁止因为缺少 Mac Docker 就退回 T1 不可用的网络步骤。任何公网构建不得上传 T1 的私有数据库、证书、密码、真实二维码或机器身份快照。
5. 这些步骤仅构建/传送/隔离验证候选镜像。**生产 Manager 单服务替换仍须先通过真实容器配置与三数据库一致备份、离线恢复演练和旧五身份保留审核**；Broker 不重建，P3 实板不启动/不重刷。

### 10.2 下一次 Mac Terminal **只读能力检查**

当前不应直接发送构建指令，因为还未确认 Mac 上有可用 Docker 引擎以及 T1 是 amd64 还是 arm64。下面只读取版本、平台和 Mac 对 GitHub 的基本可达性，不克隆源码、不构建、不传镜像、不操作生产服务。

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
printf 'MAC_CPU_ARCH='
uname -m
git --version
if command -v docker >/dev/null 2>&1 && docker info --format 'MAC_DOCKER_ENGINE_OS={{.OSType}} MAC_DOCKER_ENGINE_ARCH={{.Architecture}}' 2>/dev/null; then echo MAC_DOCKER_ENGINE=READY; else echo MAC_DOCKER_ENGINE=UNAVAILABLE; fi
if command -v docker >/dev/null 2>&1 && docker buildx version >/dev/null 2>&1; then echo MAC_BUILDX=READY; else echo MAC_BUILDX=UNAVAILABLE; fi
curl -L -sS --connect-timeout 5 --max-time 12 -o /dev/null -w 'MAC_GITHUB_HTTP=%{http_code}\n' https://github.com/chrenguo-stack/HomeAssistant
ssh -T "$T1_SSH" 'img=$(docker inspect --type container --format "{{.Image}}" greenhouse-manager) || exit 1; docker image inspect --format "T1_MANAGER_IMAGE_PLATFORM={{.Os}}/{{.Architecture}}" "$img"'
```

`MAC_GITHUB_HTTP` 为基本 HTTPS 探测，不代表 Git fetch 或 PyPI/Docker Hub 可访问；后续以精确 `git fetch` 和构建返回值为准。如果平台或 Mac Docker 引擎未知，STOP，在现有服务不变条件下改走 GitHub Actions 镜像产物路径。不得为了诊断网络而更改 T1 的 DNS/证书、安装代理或重启服务。

```text
T1_GITHUB_DIRECT=UNAVAILABLE_USER_REPORTED
PREVIOUS_T1_GIT_FETCH_INSTRUCTIONS=CANCELLED
PREVIOUS_T1_ONLINE_BUILDX_INSTRUCTIONS=CANCELLED
NEW_ROUTE=MAC_OR_CI_BUILD_SAME_ARCH_IMAGE_THEN_SSH_DOCKER_LOAD
MAC_DOCKER_ENGINE=UNVERIFIED
T1_TARGET_PLATFORM=UNVERIFIED
MANAGER_RESTART=false
BROKER_RESTART=false
THREE_DB_BACKUP=NOT_YET_MADE
BOARD_FIRST_BOOT=false
REAL_SECRET_IMPORT=false
STOP_AT_PLATFORM_CAPABILITY_CHECK=true
```

## 11. GitHub Actions 原生 ARM64 构建产物闭环与 Mac SSH 离线交付（2026-10-09）

**纠正 Mac 检查结果解释**：`MAC_DOCKER=READY ARCH=` 紧接着 `MAC_DOCKER=UNAVAILABLE`，条件分支最终没有通过，不能把 Mac Docker 当作可用。T1 原生产容器镜像经只读确认运行在 `linux/arm64`，`python:3.11-slim` 已缓存，但并不证明 T1 离线构建可下载全部 pip 依赖。上一轮已通过的 T1 Git exact checkout 不再重新执行。

已在 PR #539 新增独立 `push` workflow：
`.github/workflows/n3w-p4-manager-arm64-offline-image-ci.yml`

```text
WORKFLOW_RUN_ID=37894571429
WORKFLOW_RESULT=COMPLETED_SUCCESS
WORKFLOW_URL=https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37894571429
WORKFLOW_SOURCE_SHA=3d86d6bfaf361dc3a3d7295d046f541a544d552d
WORKFLOW_BUILD_PLATFORM=linux/arm64
WORKFLOW_RUNNER=ubuntu-24.04-arm
SYNTHETIC_CLI_AND_PENDING_GUARD_GATES=PASS
IMAGE_TAG=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
ARTIFACT_ID=11599534020
ARTIFACT_NAME=n3w-p4-manager-linux-arm64-3d86d6bf
ARTIFACT_ZIP_SIZE_BYTES=65067601
ARTIFACT_EXPIRES_AT=2026-10-16T06:38:42Z
ARTIFACT_T1_IMPORTED=false
MANAGER_LIVE_DEPLOYED=false
BROKER_RESTART=false
P4_BOARD_FIRST_BOOT=false
SETUP_SECRET_IMPORT=false
```

该 workflow 从 GitHub exact #538 HEAD 独立 checkout，而非构建运行中 T1 的任何镜像/容器；原生 ARM64 build 后做 `--network none`、无 DB/secret mounts 的 CLI 与 pending TTL 守卫检查，再 `docker save | gzip` 输出文件及 SHA256 manifest。**镜像已经在 GitHub 构建完成、合成测试通过；尚未部署到 T1**。本构建并非依赖完全锁定/基础层完全固定的可重现构建，最终传输镜像必须以校验后的本次 artifact 为 authority。

### 11.1 Mac 浏览器下载

打开上述 workflow URL，滚动到 `Artifacts`，下载 `n3w-p4-manager-linux-arm64-3d86d6bf`（约 65 MB），保存至 Mac `~/Downloads/n3w-p4-manager-linux-arm64-3d86d6bf.zip`。下载受 GitHub 认证与 artifact 保留期控制。Mac 不需要 Docker 引擎，也不需要重新构建代码。ZIP 是 GitHub 上传产物的包装层，内含 `n3w-p4-manager-linux-arm64-3d86d6bf.tar.gz` 及 `.sha256` 校验文件。

### 11.2 Mac 校验并 SSH 离线导入（独立镜像，不替换生产容器）

在 Mac Terminal 执行：

```bash
(
set -e
set -o pipefail
NAME=n3w-p4-manager-linux-arm64-3d86d6bf
ZIP="$HOME/Downloads/$NAME.zip"
DIR="$HOME/Downloads/$NAME-verified"
test -f "$ZIP" || { echo ARTIFACT_ZIP_MISSING_STOP=true; exit 11; }
test ! -e "$DIR" || { echo VERIFIED_DIRECTORY_ALREADY_EXISTS_STOP=true; exit 12; }
umask 077
mkdir "$DIR"
unzip -q "$ZIP" -d "$DIR"
cd "$DIR"
test -f "$NAME.tar.gz"
test -f "$NAME.tar.gz.sha256"
shasum -a 256 -c "$NAME.tar.gz.sha256"
gzip -t "$NAME.tar.gz"
echo MAC_ARCHIVE_INTEGRITY=PASS
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
TAG=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
BEFORE=$(ssh -T "$T1_SSH" 'docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}" greenhouse-manager')
ssh -T "$T1_SSH" 'set -eu
TAG=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
if docker image inspect "$TAG" >/dev/null 2>&1; then echo CANDIDATE_TAG_ALREADY_PRESENT_STOP=true; exit 13; fi
test "$(docker inspect --type container --format "{{.State.Running}}" greenhouse-manager)" = "true"
echo T1_IMPORT_PREFLIGHT=PASS'
gzip -dc "$NAME.tar.gz" | ssh -T "$T1_SSH" 'docker load'
ssh -T "$T1_SSH" 'set -eu
TAG=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
test "$(docker image inspect --format "{{.Os}}/{{.Architecture}}" "$TAG")" = "linux/arm64"
test "$(docker image inspect --format "{{index .Config.Labels \"org.opencontainers.image.revision\"}}" "$TAG")" = "3d86d6bfaf361dc3a3d7295d046f541a544d552d"
docker run --rm --network none --read-only --entrypoint greenhouse-manager-registration "$TAG" p4-pending-readonly --help >/dev/null
docker run --rm --network none --read-only --entrypoint greenhouse-manager-pairing "$TAG" import-payload --help >/dev/null
docker image inspect --format "T1_IMPORTED_IMAGE_ID={{.Id}} T1_IMPORTED_IMAGE_BYTES={{.Size}}" "$TAG"
echo T1_OFFLINE_IMPORT_AND_CLI=PASS'
AFTER=$(ssh -T "$T1_SSH" 'docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}" greenhouse-manager')
test "$BEFORE" = "$AFTER" || { echo LIVE_MANAGER_CHANGED_STOP=true; exit 14; }
echo PRODUCTION_MANAGER_IDENTITY_UNCHANGED=PASS
echo BROKER_RESTART_REQUESTED=false
echo P4_FIRST_NORMAL_BOOT=false
)
```

上述命令只向 T1 `docker load` 新镜像和短暂运行**无网络、无持久卷**的 CLI 功能探测。不会触碰 T1 当前运行的 Manager 容器或 Broker 网络，不读取真实数据库，禁止真实 QR/secret 输入。遇到 sha256 校验错误、已有同名候选镜像、SSH 失败、import 失败、架构/来源漂移、隔离探测失败或 Manager 状态变更时立即 STOP，不自动清理镜像、重启容器或重试。失败可能已经导入候选镜像，但不会按此步骤部署到生产 Manager。

### 11.3 剩余生产部署前阻断条件

真实替换前需另行实现：T1 当前容器完整私有 create config、nested binds/Env/secrets/UID/tmpfs/read-only 的版本化离线复制；旧镜像可恢复性；三数据库加 relay-keys 全部持久内容在受控无写入者窗口下做一致备份；还原到隔离数据根目录并验证 schema/五身份/回退；Broker 网络及 loopback TLS 不变；Manager 单服务替换与失败回退脚本。单凭本镜像已导入+CLI --help PASS **不准**直接重建生产 Manager，不准启动 P3 干净实板。

## 12. T1 本地候选镜像构建实际成功：暂停离线导入路径（2026-10-09）

操作者在 T1 完成 §10 原始镜像构建指令，随后执行独立只读查验：

```text
SOURCE_EXACT_HEAD_PREVIOUS=PASS
CANDIDATE_IMAGE_PRESENT=true
CANDIDATE_IMAGE_PLATFORM=linux/arm64
CANDIDATE_IMAGE_BYTES=59097093
CANDIDATE_IMAGE_REVISION=PASS
CANDIDATE_SOURCE_SHA=3d86d6bfaf361dc3a3d7295d046f541a544d552d
MANAGER_RUNNING=true
MANAGER_RESTARTS=0
BROKER_RUNTIME_MUTATION=NO_EVIDENCE_OF_CHANGE
LIVE_MANAGER_IMAGE_REPLACEMENT=false
T1_LOCAL_CANDIDATE_IMAGE=SELECTED
GITHUB_ACTIONS_ARM64_ARTIFACT=SUCCESS_BUT_NOT_NEEDED
P4_BOARD_FIRST_BOOT=false
SECRET_IMPORT=false
```

这里应以**实际观察**为准：T1 先前成功拉取精确 GitHub 源码，且确实已构建本地候选 ARM64 镜像，不能再将“无法从 T1 访问 GitHub”作为已证明的持续阻断条件。但已完成 Git fetch 和 docker image build **不证明**所有网络目的地长期可用，也不证明当前 live Manager 已升级。GitHub Actions 的另一个 ARM64 成品仍保留为备用，**不在现有候选标签上执行重复 `docker load`**。避免用来源不同的两份镜像覆盖同一 tag。

### 12.1 下一唯一现场动作：新镜像无网络、无真实 DB 的 CLI 和源码守卫检查

Mac Terminal 可以直接执行以下程序；无需 Git 下载、构建或导入镜像。它会只创建短暂 `docker run --rm` 容器用于隔离测试（本命令没有 host path binds、真实秘密、MQTT 或 Wi-Fi/实板访问），且在前后对比真实 Manager/Broker 容器状态。若 test exit nonzero 不得继续生产部署，也不得自行删除当前容器或镜像。

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
(
set -e
set -o pipefail
BEFORE_MANAGER=$(ssh -T "$T1_SSH" 'docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" greenhouse-manager')
BEFORE_BROKER=$(ssh -T "$T1_SSH" 'docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" n3wfc4-broker-1')
ssh -T "$T1_SSH" 'set -eu
TAG=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
test "$(docker image inspect --format "{{.Os}}/{{.Architecture}}" "$TAG")" = "linux/arm64"
test "$(docker image inspect --format "{{index .Config.Labels \"org.opencontainers.image.revision\"}}" "$TAG")" = "3d86d6bfaf361dc3a3d7295d046f541a544d552d"
docker run --rm --network none --read-only --entrypoint greenhouse-manager-registration "$TAG" p4-pending-readonly --help >/dev/null
echo P4_READONLY_CLI_IN_IMAGE=PASS
docker run --rm --network none --read-only --entrypoint greenhouse-manager-pairing "$TAG" import-payload --help >/dev/null
echo QR_PAYLOAD_IMPORT_CLI_IN_IMAGE=PASS
docker run --rm --network none --read-only --entrypoint python "$TAG" -c '"'"'import inspect; from greenhouse_manager.runtime.registration import RegistrationRegistry; from greenhouse_manager.runtime.n3w_simplified_pairing import SimplifiedPairingCoordinator; assert callable(getattr(RegistrationRegistry,"pending_import_guard",None)); assert "pending_import_guard" in inspect.getsource(SimplifiedPairingCoordinator.import_setup_secret); print("PENDING_EXPIRY_GUARD_IN_IMAGE=PASS")'"'"'
echo T1_CANDIDATE_SYNTHETIC_TESTS=PASS'
AFTER_MANAGER=$(ssh -T "$T1_SSH" 'docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" greenhouse-manager')
AFTER_BROKER=$(ssh -T "$T1_SSH" 'docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" n3wfc4-broker-1')
test "$BEFORE_MANAGER" = "$AFTER_MANAGER" || { echo LIVE_MANAGER_IDENTITY_CHANGED_STOP=true; exit 31; }
test "$BEFORE_BROKER" = "$AFTER_BROKER" || { echo BROKER_IDENTITY_CHANGED_STOP=true; exit 32; }
echo LIVE_MANAGER_AND_BROKER_UNCHANGED=PASS
)
```

**防止误判：** 此命令检查的是“候选镜像内部能力”，不是 live Manager 是否已经有新 CLI；不连接实际 Unix socket、不读取秘密、不证明真实 P4 import + COMMIT + canonical。命令失败只证明某个隔离检查未通过，不代表正在运行的 Manager 或 Broker 发生故障。

后续需先完成带有确切生效配置的私有备份和跨三库一致恢复演练；尚不允许替换生产 Manager 或启动 P3 干净实板。

```text
T1_SOURCE_AND_NEW_IMAGE_BUILT=PASS
T1_ISOLATED_CLI_GATES=PENDING_OPERATOR
MAC_ACTIONS_DOWNLOAD_AND_DOCKER_LOAD=SKIP_UNNECESSARY
MANAGER_LIVE_DEPLOYMENT=false
BROKER_RESTART=false
DB_MUTATION=false
BOARD_FIRST_NORMAL_BOOT=false
STOP_AFTER_SYNTHETIC_PROOF=true
```

## 13. T1 本地候选镜像隔离验收闭环及真实数据备份设计（2026-10-09）

操作者提供本地构建镜像的真实隔离验收输出：

```text
P4_READONLY_CLI_IN_IMAGE=PASS
QR_PAYLOAD_IMPORT_CLI_IN_IMAGE=PASS
PENDING_EXPIRY_GUARD_IN_IMAGE=PASS
T1_CANDIDATE_SYNTHETIC_TESTS=PASS
LIVE_MANAGER_AND_BROKER_UNCHANGED=PASS
SOURCE_EXACT_SHA=3d86d6bfaf361dc3a3d7295d046f541a544d552d
LOCAL_CANDIDATE_TARGET=linux/arm64
IMAGE_ALREADY_BUILT_AND_AVAILABLE=true
GITHUB_ACTIONS_IMAGE_IMPORT=UNNECESSARY
PRODUCTION_MANAGER_UPGRADE=false
PRODUCT_BOARD_FIRST_NORMAL_BOOT=false
REAL_SETUP_SECRET_IMPORT=false
```

**结论**：构建与镜像内命令、源代码保护入口的隔离检查已经通过，不需要重新编译、反复访问 GitHub、再次下载 CI 镜像、或重复现有基础 Broker 检查。上述 PASS **不是**真实 P4 配对状态迁移的验收，不能代替同一快照内的 SQLite/Relay/identity 数据保护，也不能据此停止当前 Manager。

### 13.1 正式备份必须具备的保护范围

此前真正的 T1 Manager 运行状态检查发现了 **六个 bind mount**：

- 只读 `/run/secrets/provisioning_password`
- 可写 `/var/lib/greenhouse-manager-registration`：registration 主 SQLite DB、以及将来可能存在的 -wal/-shm
- 可写 `/var/lib/greenhouse-manager/n3w`：replay/credential 等 SQLite DB、以及其他持久状态
- 可写 `/var/lib/greenhouse-manager/n3w/relay-keys`：**嵌套独立 bind mount**，不能只复制父目录就认定保留了真实 key 数据
- 只读 `/run/secrets/broker-ca.pem`
- 只读 `/run/secrets/gh_manager_mqtt_password`

完整回退还依赖当前私有的 Manager Docker create 配置（镜像 ID、entrypoint、User、host network、restart policy、readonly rootfs、tmpfs、Env 的全部原值、每条挂载的真实 Source/Destination/RW、可能存在的特权/安全选项等），以及 Broker 的不变性验证。公开 GitHub 只能存不含秘密的命令、状态证据和 hash；**真实 Host Source、私有 Env、证书密码和备份本体均须只存在于 T1 本地受限目录**。

由于生产状态分布于三个 SQLite 库和其他密钥文件，独立 `sqlite3.backup` 只提供**各库内部一致性**，不能假定三库在同一时间点，亦不能保护 relay keys。预定的安全路径：先构建可恢复的**私有容器配置存档**与旧镜像保留策略，明确当前所有持久挂载和其他写入者；随后在**一次受控的 Manager 停写窗口**（不得停止或重建 Broker）复制三个主库及附属 sidecars、完整的两个持久源目录和嵌套的第三个独立源目录，包含权限与所有权；校验内容清单和 SQLite integrity、身份数/高水位/replay 连续性；在隔离目录完成恢复演练；最后才允许部署新版本并做运行态验证。遇到失败，先判断旧镜像和旧数据能否在安全原状下启动，不能自动擦库或清空身份。

### 13.2 现场下一动作：持久挂载与文件数量只读检查

Mac Terminal 执行以下命令，无文件内容、真实 host source、真实 Env、真实身份值输出：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'docker inspect --type container --format "{{range .Mounts}}MOUNT_DEST={{.Destination}} TYPE={{.Type}} RW={{.RW}}{{println}}{{end}}" greenhouse-manager'
ssh -T "$T1_SSH" 'docker exec greenhouse-manager sh -c '"'"'for d in /var/lib/greenhouse-manager-registration /var/lib/greenhouse-manager/n3w /var/lib/greenhouse-manager/n3w/relay-keys; do if test ! -d "$d"; then printf "PERSIST_DIR=%s STATUS=missing\n" "$d"; exit 21; fi; count=$(find "$d" -type f | wc -l); size=$(du -sk "$d" | cut -f1); printf "PERSIST_DIR=%s FILE_COUNT=%s SIZE_KIB=%s\n" "$d" "$count" "$size"; done'"'"''
ssh -T "$T1_SSH" 'docker inspect --type container --format "MANAGER_RUNNING={{.State.Running}} MANAGER_RESTARTS={{.RestartCount}} MANAGER_NETWORK={{.HostConfig.NetworkMode}}" greenhouse-manager'
ssh -T "$T1_SSH" 'docker inspect --type container --format "BROKER_RUNNING={{.State.Running}} BROKER_RESTARTS={{.RestartCount}}" n3wfc4-broker-1'
```

注意，`du` 针对 `/var/lib/greenhouse-manager/n3w` 的统计会包含内嵌 relay-keys 文件，不允许将相邻统计简单相加作为真实备份大小；真正备份必须按每一个 bind source 单独取源，不能跨嵌套路径误拷贝。任何 `missing` 或命令失败先归类取证错误并 STOP，不直接判定产品故障。

**此操作不会创建备份、不会停止/重启现有 Manager、不会访问实板或导入真实 Setup Secret。** 结果回来后应准备独立源码及测试可审的备份/回退执行包，而不是直接执行容器停止和不安全的活库拷贝。

```text
P4_CANDIDATE_ISOLATED_GATES=PASS
RUNNING_MANAGER_UNCHANGED=PASS
RUNNING_BROKER_UNCHANGED=PASS
PERSISTENT_MOUNTS=NEEDS_FRESH_RUNTIME_LAYOUT_CONFIRMATION
ALL_PERSISTENT_STATE_BACKUP=NOT_YET_EXECUTED
ISOLATED_RESTORE_DRILL=NOT_YET_EXECUTED
MANAGER_REPLACEMENT=false
BOARD_FIRST_BOOT=false
NEXT_ACTION=MOUNT_AND_PERSIST_DIR_READONLY_INVENTORY
STOP_ON_LAYOUT_DRIFT=true
```

## 14. 六挂载与持久目录现场收敛；第一阶段仅备份旧镜像与容器配置（2026-10-09）

用户从 T1 Mac SSH 实际报告：

```text
MOUNT_DEST=/var/lib/greenhouse-manager/n3w TYPE=bind RW=true
MOUNT_DEST=/var/lib/greenhouse-manager/n3w/relay-keys TYPE=bind RW=true
MOUNT_DEST=/run/secrets/broker-ca.pem TYPE=bind RW=false
MOUNT_DEST=/run/secrets/gh_manager_mqtt_password TYPE=bind RW=false
MOUNT_DEST=/run/secrets/provisioning_password TYPE=bind RW=false
MOUNT_DEST=/var/lib/greenhouse-manager-registration TYPE=bind RW=true
REGISTRATION_DIR_FILE_COUNT=1
REGISTRATION_DIR_SIZE_KIB=664
N3W_DIR_FILE_COUNT_WITH_NESTED_MOUNT=11
N3W_DIR_SIZE_KIB_WITH_NESTED_MOUNT=8056
RELAY_KEYS_DIR_FILE_COUNT=5
RELAY_KEYS_DIR_SIZE_KIB=24
MANAGER_RUNNING=true
MANAGER_RESTARTS=0
MANAGER_NETWORK=host
BROKER_RUNNING=true
BROKER_RESTARTS=0
```

N3W 父目录统计已经包含嵌套 relay-keys 挂载，不要将这两个空间数字直接相加后称为去重后的大小；5 个 relay key 目录文件**不是**对历史已配对身份数量的重新取证。多个独立 bind sources 必须分别保护。三个只读秘密挂载也需要在真正回退时以原始 host source、文件权限、存续条件验证，但**不能复制或上传真实秘密到 GitHub**。

### 14.1 安全的阶段 A：在 T1 本地私有目录冻结运行定义和原版 Manager 镜像

与正式数据库备份分离，先行保存**完整私有 Docker inspect 与旧镜像本体**。实际 Manager 运行不停止，不触及注册库、replay/credential、relay keys、Broker 网络。创建的只是 T1 的 root 私有文件，可能包含秘密配置信息，绝对不可上传 GitHub、不贴终端文件内容。Docker inspect 不具备秘密值自动脱敏，故只能写入 `0700` 私有目录，禁止在终端输出本体。给出 Mac Terminal 命令：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'set -eu
umask 077
FREE=$(df -Pk /root | awk "NR==2 {print \$4}")
if test -z "$FREE" || test "$FREE" -lt 524288; then echo ROOT_BACKUP_SPACE_LOW_STOP=true; exit 21; fi
BEFORE_MANAGER=$(docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" greenhouse-manager)
BEFORE_BROKER=$(docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" n3wfc4-broker-1)
test "$(docker inspect --type container --format "{{.State.Running}}" greenhouse-manager)" = "true"
test "$(docker inspect --type container --format "{{.State.Running}}" n3wfc4-broker-1)" = "true"
OLD_IMAGE=$(docker inspect --type container --format "{{.Image}}" greenhouse-manager)
docker image inspect "$OLD_IMAGE" >/dev/null
DIR=$(mktemp -d /root/n3w-p4-manager-rollback-prep-XXXXXXXX)
docker inspect --type container greenhouse-manager > "$DIR/manager-inspect-private.json"
docker inspect --type container n3wfc4-broker-1 > "$DIR/broker-inspect-private.json"
docker image save --output "$DIR/old-manager-image.tar" "$OLD_IMAGE"
sha256sum "$DIR/old-manager-image.tar" > "$DIR/old-manager-image.tar.sha256"
chmod 600 "$DIR"/*
test -s "$DIR/manager-inspect-private.json"
test -s "$DIR/broker-inspect-private.json"
test -s "$DIR/old-manager-image.tar"
test "$BEFORE_MANAGER" = "$(docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" greenhouse-manager)"
test "$BEFORE_BROKER" = "$(docker inspect --type container --format "{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}" n3wfc4-broker-1)"
echo PRIVATE_MANAGER_CONFIG_SAVED=PASS
echo OLD_MANAGER_IMAGE_ARCHIVE_SAVED=PASS
echo LIVE_MANAGER_BROKER_UNCHANGED=PASS
printf "T1_PRIVATE_ROLLBACK_PREP_DIR=%s\n" "$DIR"
echo DATABASE_BACKUP=NOT_STARTED'
```

本阶段需要 root /root 目录有至少 512MiB 余量（仅作保护阈值，不保证文件最终大小）；产生约旧镜像体积量级的 tar，以及含秘密的 JSON。失败按错误路径停止，不重复盲跑、不自动删除旧私有目录、不删除旧 Docker 镜像或清理缓存。真实备份/恢复尚不可宣称通过。

### 14.2 真正的数据快照仍需第二阶段的受控停写

当前 3 个可写挂载实际数据根目录位于宿主机上不同 bind Source，原始 Source 和文件所有权权限应从私有 inspect 记录解析，不向 GitHub 或聊天传播。下一阶段必须先准备与审查确切恢复动作，并确保有单写入者的受控停写窗口；仅在 Manager 的唯一写入者已经停止且 Broker 保持运行时，对三个独立 host source 各做完整文件/属性/必要 SQLite -wal/-shm 拷贝，并验证 db integrity、旧五身份、高水位及 credentials/replay、全部 relay keys、secrets source 可读性，再在隔离目录演练恢复和回退。若其他进程也能写相同 DB，仍需额外协调；不能靠 `docker stop` 假设全局无写入者。不能直接使用历史 `t1_backup.py`。

```text
P4_NEW_IMAGE_SYNTHETIC=PASS
T1_SIX_MOUNTS_READONLY_INVENTORY=PASS
ROOT_LOCAL_PRIVATE_RUNTIME_CONFIG_BACKUP=AWAITING_OPERATOR
ROOT_LOCAL_OLD_IMAGE_ARCHIVE=AWAITING_OPERATOR
THREE_DB_CONSISTENT_BACKUP=false
ISOLATED_RESTORE_DRILL=false
LIVE_MANAGER_REPLACEMENT=false
BOARD_FIRST_NORMAL_BOOT=false
SECRET_IMPORT=false
NEXT_ACTION=SAVE_PRIVATE_INSPECT_AND_OLD_IMAGE_WITHOUT_SERVICE_MUTATION
STOP_ON_FAILURE=true
```

## 15. Phase A 私有运行定义与旧镜像归档已完成；进入数据备份安全门（2026-10-09）

操作者从 Mac Terminal 提供的**真实 T1 输出**：

```text
PRIVATE_MANAGER_CONFIG_SAVED=PASS
OLD_MANAGER_IMAGE_ARCHIVE_SAVED=PASS
LIVE_MANAGER_BROKER_UNCHANGED=PASS
T1_PRIVATE_ROLLBACK_PREP_DIR=CREATED_ROOT_PRIVATE_NOT_PUBLISHED
DATABASE_BACKUP=NOT_STARTED
MANAGER_FIRST_P4_REPLACEMENT=false
P3_BOARD_FIRST_BOOT=false
SETUP_SECRET_IMPORT=false
```

已保存当前 Manager 与 Broker 的原始 Docker inspect 以及旧 Manager 镜像 tar+SHA256 manifest，运行中的 Manager/Broker 未改变。备份位于操作者 T1 `/root/n3w-p4-manager-rollback-prep-*` 私有目录；**GitHub 不保留实际目录随机尾部、不发布文件本体、真实 Source 路径、镜像 ID、Env/密码/证书/身份详情**。

**结论边界：**旧镜像及容器配置归档并不等于 DB/秘钥可以恢复；旧镜像 tar 校验尚待现场独立验证，真实生产部署仍阻断于完整 RW 持久数据快照、非 Manager 其他写入者证据、SQLite 跨库一致窗口、旧五身份和重放高水位复核、隔离恢复演练。

### 15.1 下一门只读预检：验证归档与真实宿主机挂载源

只执行文件校验和 stat，绝不打印存档 JSON、宿主机 Source 路径或秘密值。以下程序仅当 T1 `/root` 下匹配 **唯一** 的上一阶段私有目录时继续；若有多个历史目录则先 STOP、不要猜用哪个。Mac Terminal：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'set -eu
set -- /root/n3w-p4-manager-rollback-prep-*
test "$#" -eq 1 || { echo ROLLBACK_PREP_DIR_NOT_UNIQUE_STOP=true; exit 20; }
DIR=$1
test -d "$DIR"
test "$(stat -c %a "$DIR")" = 700
for item in manager-inspect-private.json broker-inspect-private.json old-manager-image.tar old-manager-image.tar.sha256; do
  test -s "$DIR/$item"
  test "$(stat -c %a "$DIR/$item")" = 600
done
sha256sum -c --status "$DIR/old-manager-image.tar.sha256"
echo PRIVATE_OLD_IMAGE_ARCHIVE_HASH=PASS
echo PRIVATE_INSPECT_FILES_PROTECTED=PASS
test "$(docker inspect --type container --format "{{len .Mounts}}" greenhouse-manager)" = 6
docker inspect --type container --format "{{range .Mounts}}{{.Destination}}|{{.Source}}|{{.RW}}{{println}}{{end}}" greenhouse-manager |
{
  count=0
  while IFS="|" read -r dest src rw; do
    count=$((count+1))
    test ! -L "$src" || { echo SOURCE_SYMLINK_STOP=true; exit 31; }
    case "$dest:$rw" in
      /var/lib/greenhouse-manager-registration:true|/var/lib/greenhouse-manager/n3w:true|/var/lib/greenhouse-manager/n3w/relay-keys:true)
        test -d "$src" || { echo RW_SOURCE_NOT_DIRECTORY_STOP=true; exit 32; }
        ;;
      /run/secrets/provisioning_password:false|/run/secrets/broker-ca.pem:false|/run/secrets/gh_manager_mqtt_password:false)
        test -f "$src" || { echo RO_SECRET_SOURCE_NOT_FILE_STOP=true; exit 33; }
        ;;
      *)
        echo UNEXPECTED_MOUNT_LAYOUT_STOP=true
        exit 34
        ;;
    esac
    printf "MOUNT_DEST=%s RW=%s HOST_SOURCE_TYPE=PASS\n" "$dest" "$rw"
  done
  test "$count" -eq 6 || { echo MOUNT_COUNT_DRIFT_STOP=true; exit 35; }
}
echo PRIVATE_BACKUP_SOURCE_LAYOUT=PASS
docker inspect --type container --format "MANAGER_RUNNING={{.State.Running}} MANAGER_RESTARTS={{.RestartCount}}" greenhouse-manager
docker inspect --type container --format "BROKER_RUNNING={{.State.Running}} BROKER_RESTARTS={{.RestartCount}}" n3wfc4-broker-1
echo PRODUCTION_DATABASE_BACKUP=NOT_STARTED'
```

上述 4 个私有文件校验只是 Stage A 校验。任何一条 STOP 立即停止，保留目录，**不删除、不覆盖、不重建旧镜像，不停生产 Manager/Broker**。如果某个 Source 是有意的符号链接，先作为未解决的可恢复路径风险复核，而不是就地修复文件系统。输出只含 mount Destination/RW 与类型判定，不含 private Source 值。该命令不复制当前三个 SQLite DB，也不提供一致性数据备份。

### 15.2 后续执行包必须满足的单次停写与恢复合格条件

- 先有包含安全 STOP/失败恢复路径的经独立验证的部署执行包，复制目的地与所有权限在 T1 root-private space；配置秘密不进入 stdout 或 GitHub。
- 从 **保存的旧配置**与 fresh Docker metadata 一一核对三个 distinct RW host source，以及三个 RO secret host source；避免父级 n3w 和 nested relay-keys 混淆，使用 `tar --one-file-system` 时必须明确 nested bind 会被单独捕获。
- 单一受控停写窗口（Manager 止写、其他写入者确认不存在或已协调）后备份整个三个 RW 来源，包含 DB 主库、可能在那时重新出现的 `-wal/-shm`、relay keys、未列名持久状态、UID/GID/mode；冷备份的主库须用隔离连接读取 integrity（不能在 live source 上以 `PRAGMA integrity_check` 代替原子快照）。
- 必须先完成隔离恢复演练及原始镜像/原始 Docker 参数重建可能性验证，再允许用独立 `linux/arm64` 候选镜像启动**生产 Manager-only**；Broker 双网络与 TLS 不变。若任何不可恢复状态未知，停止升级并保留旧 Manager/old DB。
- 任何停机/回退必须有明确窗口和新旧状态对比；当前阶段**没有授权执行停机命令，亦没有执行部署**。

```text
PHASE_A_CONTAINER_SPEC_ARCHIVE=PASS
PHASE_A_OLD_IMAGE_TAR_CREATED=PASS
PHASE_A_TAR_SHA256_RECHECK=PENDING
HOST_BIND_SOURCES_FRESH_TYPE_CHECK=PENDING
CONSISTENT_DATA_SNAPSHOT=false
COLD_RESTORE_DRILL=false
MANAGER_RUNTIME_REPLACEMENT=false
BROKER_RESTART=false
FIRST_BOARD_NORMAL_BOOT=false
STOP_AT_ARCHIVE_HASH_AND_SOURCE_LAYOUT_PREFLIGHT=true
```

## 16. 挂载检查末尾空行误报修复（2026-10-09）

T1 操作者执行 §15.1 后取得以下真实结果：

```text
PRIVATE_OLD_IMAGE_ARCHIVE_HASH=PASS
PRIVATE_INSPECT_FILES_PROTECTED=PASS
SIX_EXPECTED_MOUNT_DESTINATIONS_HOST_SOURCE_TYPE=PASS_EACH
UNEXPECTED_MOUNT_LAYOUT_STOP=true
PRIVATE_BACKUP_SOURCE_LAYOUT=NOT_PRINTED
PRODUCTION_DATABASE_BACKUP=NOT_STARTED
```

六条有效挂载均已逐条输出 PASS，随后脚本报 `UNEXPECTED_MOUNT_LAYOUT_STOP=true`。高度怀疑是 Docker `docker inspect --format "{{range ...}}{{println}}{{end}}"` 输出中的**尾部空记录**，因为上一个解析循环对全空行也执行 `count++` 并进入 `case "$dest:$rw"`。这属于命令解析错误，不足以判定 T1 挂载异常；不需要修补或重启任何生产服务。**必须仍执行下面修正后的现场检查，不能只凭这一解释直接宣称安全门 PASS。**

### 16.1 只重跑挂载检查，不重复旧镜像校验

Mac Terminal：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'set -eu
test "$(docker inspect --type container --format "{{len .Mounts}}" greenhouse-manager)" = 6
docker inspect --type container --format "{{range .Mounts}}{{.Destination}}|{{.Source}}|{{.RW}}{{println}}{{end}}" greenhouse-manager |
{
  count=0
  seen="|"
  while IFS="|" read -r dest src rw; do
    if test -z "$dest" && test -z "$src" && test -z "$rw"; then
      continue
    fi
    case "$seen" in *"|$dest|"*) echo DUPLICATE_MOUNT_DEST_STOP=true; exit 36;; esac
    seen="$seen$dest|"
    test ! -L "$src" || { echo SOURCE_SYMLINK_STOP=true; exit 31; }
    case "$dest:$rw" in
      /var/lib/greenhouse-manager-registration:true|/var/lib/greenhouse-manager/n3w:true|/var/lib/greenhouse-manager/n3w/relay-keys:true)
        test -d "$src" || { echo RW_SOURCE_NOT_DIRECTORY_STOP=true; exit 32; }
        ;;
      /run/secrets/provisioning_password:false|/run/secrets/broker-ca.pem:false|/run/secrets/gh_manager_mqtt_password:false)
        test -f "$src" || { echo RO_SECRET_SOURCE_NOT_FILE_STOP=true; exit 33; }
        ;;
      *)
        echo UNEXPECTED_MOUNT_LAYOUT_STOP=true
        exit 34
        ;;
    esac
    count=$((count+1))
    printf "MOUNT_DEST=%s RW=%s HOST_SOURCE_TYPE=PASS\n" "$dest" "$rw"
  done
  test "$count" -eq 6 || { echo MOUNT_COUNT_DRIFT_STOP=true; exit 35; }
}
echo PRIVATE_BACKUP_SOURCE_LAYOUT=PASS
docker inspect --type container --format "MANAGER_RUNNING={{.State.Running}} MANAGER_RESTARTS={{.RestartCount}}" greenhouse-manager
docker inspect --type container --format "BROKER_RUNNING={{.State.Running}} BROKER_RESTARTS={{.RestartCount}}" n3wfc4-broker-1
echo DATABASE_BACKUP=NOT_STARTED'
```

**解释：**忽略的仅是 `dest/src/rw` 全为空的纯空行；任意非空异常行仍失败，仍验证六个唯一预期目的地、正确 RO/RW 以及真实宿主机源文件/目录类型，不输出宿主机 Source 或秘密。已通过的旧镜像 tar SHA256、私有权限检查无需重做。若任何安全门失败保持 STOP，不删除或更改原容器、备份归档或磁盘文件。

```text
OLD_IMAGE_PRIVATE_SHA256=PASS
PRIVATE_INSPECT_PERMISSIONS=PASS
ORIGINAL_MOUNT_CHECK=FALSE_POSITIVE_SUSPECTED
CORRECTED_SIX_MOUNT_CHECK=AWAITING_OPERATOR
THREE_DB_CONSISTENT_SNAPSHOT=false
ISOLATED_RESTORE_DRILL=false
MANAGER_DEPLOYMENT=false
BROKER_RESTART=false
FIRST_BOARD_NORMAL_BOOT=false
```

## 17. 六挂载类型来源复核已闭环；生产一致快照前检查其他运行容器写入（2026-10-09）

操作者 Mac Terminal 最新实际结果：

```text
MOUNT_DEST=/run/secrets/gh_manager_mqtt_password RW=false HOST_SOURCE_TYPE=PASS
MOUNT_DEST=/run/secrets/provisioning_password RW=false HOST_SOURCE_TYPE=PASS
MOUNT_DEST=/var/lib/greenhouse-manager-registration RW=true HOST_SOURCE_TYPE=PASS
MOUNT_DEST=/var/lib/greenhouse-manager/n3w RW=true HOST_SOURCE_TYPE=PASS
MOUNT_DEST=/var/lib/greenhouse-manager/n3w/relay-keys RW=true HOST_SOURCE_TYPE=PASS
MOUNT_DEST=/run/secrets/broker-ca.pem RW=false HOST_SOURCE_TYPE=PASS
PRIVATE_BACKUP_SOURCE_LAYOUT=PASS
MANAGER_RUNNING=true MANAGER_RESTARTS=0
BROKER_RUNNING=true BROKER_RESTARTS=0
DATABASE_BACKUP=NOT_STARTED
```

旧镜像私有归档 `sha256sum -c` 和文件权限此前已经 PASS；此处只读检查关闭了上一轮换行解析假阳性。候选本地 `linux/arm64` Manager 已编译并完成 P4 命令隔离验证。**不能因为预检通过而宣称数据备份/回退完成。**

### 17.1 下一步：排查其他容器是否共享可写数据源（只读）

下一条 Mac Terminal 命令检查当前 Manager 自身三个 RW bind 的确切 Host Source，判断是否有其他**正在运行的容器**以可写挂载指向相同或父子路径，同时检查 `tar`、`sha256sum` 与 `fuser` 能否用于后续冷备份。Host Source、Env、secret 不会输出；只输出数量、分类和 PASS/STOP。

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'set -eu
MGR=$(docker inspect --type container --format "{{.Id}}" greenhouse-manager)
REG=$(docker inspect --type container --format "{{range .Mounts}}{{if eq .Destination \"/var/lib/greenhouse-manager-registration\"}}{{.Source}}{{end}}{{end}}" greenhouse-manager)
N3W=$(docker inspect --type container --format "{{range .Mounts}}{{if eq .Destination \"/var/lib/greenhouse-manager/n3w\"}}{{.Source}}{{end}}{{end}}" greenhouse-manager)
KEYS=$(docker inspect --type container --format "{{range .Mounts}}{{if eq .Destination \"/var/lib/greenhouse-manager/n3w/relay-keys\"}}{{.Source}}{{end}}{{end}}" greenhouse-manager)
for p in "$REG" "$N3W" "$KEYS"; do
  test -n "$p" && test -d "$p" && test ! -L "$p" || { echo RW_HOST_SOURCE_INVALID_STOP=true; exit 30; }
done
test "$REG" != "$N3W" && test "$REG" != "$KEYS" && test "$N3W" != "$KEYS" || { echo RW_HOST_SOURCE_DUPLICATE_STOP=true; exit 31; }
echo THREE_RW_BIND_SOURCE_PATHS_PRESENT=PASS
case "$KEYS/" in "$N3W/"*) echo RELAY_KEYS_SOURCE_NESTED_IN_N3W_SOURCE=true;; *) echo RELAY_KEYS_SOURCE_NESTED_IN_N3W_SOURCE=false;; esac
IDS=$(docker ps -q --no-trunc) || { echo DOCKER_RUNNING_CONTAINER_LIST_ERROR_STOP=true; exit 34; }
test "$(docker inspect --type container --format "{{.State.Running}}" greenhouse-manager)" = "true"
COUNT=0
for cid in $IDS; do
  if test "$cid" = "$MGR"; then continue; fi
  mounts=$(docker inspect --type container --format "{{range .Mounts}}{{if .RW}}{{.Source}}{{println}}{{end}}{{end}}" "$cid") || { echo OTHER_CONTAINER_INSPECT_ERROR_STOP=true; exit 32; }
  oldifs=$IFS
  IFS="
"
  for other in $mounts; do
    test -n "$other" || continue
    for src in "$REG" "$N3W" "$KEYS"; do
      if test "$src" = "$other"; then COUNT=$((COUNT+1)); continue; fi
      case "$src/" in "$other/"*) COUNT=$((COUNT+1)); continue;; esac
      case "$other/" in "$src/"*) COUNT=$((COUNT+1)); continue;; esac
    done
  done
  IFS=$oldifs
done
printf "OTHER_RUNNING_CONTAINER_RW_PATH_OVERLAPS=%s\n" "$COUNT"
test "$COUNT" -eq 0 || { echo OTHER_CONTAINER_WRITER_RISK_STOP=true; exit 33; }
command -v tar >/dev/null && echo TAR_AVAILABLE=PASS
command -v sha256sum >/dev/null && echo SHA256_AVAILABLE=PASS
if command -v fuser >/dev/null 2>&1; then echo FUSER_AVAILABLE=true; else echo FUSER_AVAILABLE=false; fi
docker inspect --type container --format "MANAGER_RUNNING={{.State.Running}} MANAGER_RESTARTS={{.RestartCount}}" greenhouse-manager
docker inspect --type container --format "BROKER_RUNNING={{.State.Running}} BROKER_RESTARTS={{.RestartCount}}" n3wfc4-broker-1
echo CONSISTENT_DATA_BACKUP=NOT_STARTED'
```

检查的局限：输出 `OTHER_RUNNING_CONTAINER_RW_PATH_OVERLAPS=0` 只能排除当前 Docker 元数据可见的**运行中容器**共享可写来源，不能排除宿主机上的 systemd 服务、脚本、未来新进程或间接访问。因此后续**受控停写**还必须确认 Manager 已不再写库和实际文件描述符占用，不得把本预检当作跨三个数据库的原子备份证据。如果另一个容器的 RW source 是父目录（或共享源的子目录），此脚本会报重叠；若另有符号链接、bind 别名、不同 realpath，同样不能据此保证零重叠，应在受控执行包中进一步检查。

**没有授权** `docker stop`、`docker compose up`、清理/替换镜像、真实 SQLite copy、Broker 重启、实板首次正常启动、Setup Secret 导入。

```text
ARCHIVE_SHA256_AND_PRIVATE_MODE=PASS
SIX_MOUNT_TYPES=PASS
OTHER_WRITER_DOCKER_PRECHECK=PENDING
DB_CONSISTENT_COLD_SNAPSHOT=false
RESTORE_REHEARSAL=false
PRODUCTION_MANAGER_UPGRADE=false
STOP_AT_READONLY_WRITER_PREFLIGHT=true
```

## 18. T1 其他容器可写来源排查闭环与冷备份源码执行包（2026-10-09）

操作者最新的实际 T1 只读输出：

```text
THREE_RW_BIND_SOURCE_PATHS_PRESENT=PASS
RELAY_KEYS_SOURCE_NESTED_IN_N3W_SOURCE=false
OTHER_RUNNING_CONTAINER_RW_PATH_OVERLAPS=0
TAR_AVAILABLE=PASS
SHA256_AVAILABLE=PASS
FUSER_AVAILABLE=true
MANAGER_RUNNING=true
MANAGER_RESTARTS=0
BROKER_RUNNING=true
BROKER_RESTARTS=0
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

中继密钥的**容器内目的地**是 N3W 状态目录之下，但**宿主机真实 bind Source** 是另一个不嵌套的独立目录，三处 RW 数据根分别备份是必须的。当前其他运行容器 RW Source 重叠计数为 0，但不足以排除宿主机非容器进程、远程挂载别名、未来写者。不能直接进入在线主库 cp。

后续源代码安全门已建立独立 Draft #540：

- `tools/execution_packages/n3w/p4_manager_cold_backup/cold_snapshot.py`
- `tools/execution_packages/n3w/p4_manager_cold_backup/test_cold_snapshot.py`
- `tools/execution_packages/n3w/p4_manager_cold_backup/README.md`
- `.github/workflows/n3w-p4-manager-cold-backup-synthetic-ci.yml`

第一阶段 `preflight` 只检查已保存 Manager 配置/挂载与真实运行状态、Broker 运行及网络/端口不变、其它容器可写源，**不复制生产 DB**。第二阶段 `capture --permit-cold-copy` 要求原 Manager **已经由外部独立受控流程停止**，不允许脚本自己停止或重启任何容器；再进行对三处实际 RW Source 的全目录冷拷贝、SHA256/权限/UID/GID 私有清单校验，以及独立恢复副本的 SQLite 完整性测试。源码/合成 CI PASS 不能当成真实 T1 冷备份、旧五身份业务契约与数据恢复 PASS。

运行态替换前还必须：原 Manager 恢复运行的方法独立核实与模拟演练、Broker TLS/双网络不变、Manager 短暂停写预算、宿主机非容器进程写入排除、身份数量和重放高水位业务语义校验、异常回退流程。不得把只保留容器 JSON 和镜像 tar 当作可直接从零重建原有数据库的证明。

```text
THREE_INDEPENDENT_HOST_RW_SOURCES=PASS
RUNNING_CONTAINER_RW_SOURCE_OVERLAP=0
SOURCE_ONLY_DRAFT_PR540=CREATED
SYNTHETIC_BACKUP_RESTORE_CI=RUNNING_OR_PASS_DEPENDS_ON_FRESH_CI
COLD_BACKUP_REAL_T1=false
RESTORE_REHEARSAL_REAL_T1=false
MANAGER_LIVE_DEPLOYMENT=false
FIRST_NORMAL_BOARD_BOOT=false
SECRET_IMPORT=false
NEXT=PR540_SOURCE_REVIEW_THEN_READONLY_PREP
```

## 19. 宿主 Python/磁盘/守护服务检查 PASS，进入可恢复停写执行包只读预检（2026-10-09）

T1 操作者现场返回：

```text
HOST_PYTHON_VERSION=3.14.4
HOST_PYTHON_SQLITE=PASS
PRIVATE_BACKUP_FREE_KIB=5966748
MANAGER_RESTART_POLICY=unless-stopped
RELATED_SERVICE_UNIT=n3wfc4-broker-activation.service
RELATED_SERVICE_UNIT=n3wfc4-broker-certificate-lifecycle.service
RELATED_SERVICE_UNIT=n3wfc4-broker-ingress-guard.service
RELATED_SERVICE_UNIT_COUNT=3
MANAGER_RUNNING=true
MANAGER_RESTARTS=0
BROKER_RUNNING=true
BROKER_RESTARTS=0
MANAGER_STOP_NOT_EXECUTED=true
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

检查说明：Python 版本满足要求；`/root` 有约 5.97 GiB 的剩余空间，足以覆盖目前观察到约几 MiB 的三个持久目录及隔离恢复副本（正式冷备份仍以现场计算的源文件实际总大小和保守空间门槛为准）。Manager 的 `unless-stopped` 和当前运行状态与旧版配置相符。列出的三个 systemd units 是 Broker 专属单元，不能据此前置的名称过滤检索证明不存在其它管理/写入者。

PR #540 已新增独立 `controlled_window.py` 和模拟测试：
- 默认仅支持只读 `preflight`，`execute` 要求显式停写标志。
- 运行时以 root 私有 JSON 的旧 Manager 容器 id、image、host 配置、六个 binds 为锚点；只允许原 Manager 停止和原 Manager 启动，Broker 不执行 stop/restart。
- 在旧 Manager 已停止且所有前置关卡通过后，以同版本 `cold_snapshot.py` 在三个真实 RW 来源做整个目录冷拷贝和异地隔离恢复；全部文件校验及三个 SQLite 库验证合格；再启动**原旧 Manager**。
- 发生停止、复制、空间、哈希、WAL/SHM、恢复等异常时会在当前 Python 进程存活范围内进入 `finally` 尝试恢复原 Manager，严禁删除旧容器和替换生产数据；如果恢复失败，进入 STOP 保留现场。
- 不断开 SSH 的前提下已做源码/模拟测试，但 Python `finally` 不能防止掉电、SIGKILL 或宿主机故障。真实停写需独立的 systemd 监督启动/超时处理与失败时人工恢复 Runbook，以及写入者排除和历史身份/重放高水位证据；未具备这些条件时不执行 `execute`。

**本阶段只允许** T1 获取 exact PR #540 源码至其现有 Git 工作目录，在已经保护的 /root 私有归档目录下建立新的工具子目录，对 `controlled_window.py preflight` 及 `cold_snapshot.py preflight` 做无写操作的源版本绑定和验证；**不能**覆盖早期工具文件，也不允许直接执行 `capture`、`execute` 或 `docker stop/start`。

```text
BACKUP_HOST_ENVIRONMENT_PREFLIGHT=PASS
OLD_CONTAINER_AUTO_RESTART_POLICY=unless-stopped
BROKER_SYSTEMD_UNITS_OBSERVED=3
REVIEWED_CONTROLLED_WINDOW_SOURCE_CREATED=true
SYNTHETIC_WINDOW_RECOVERY_TESTS=CI_VALIDATED
NEW_EXACT_T1_EXECUTOR_BIND=PENDING
HOST_NONCONTAINER_WRITERS_STILL_NOT_EXHAUSTIVELY_EXCLUDED=true
COLD_SNAPSHOT_PRODUCTION=false
ISOLATED_RESTORE_PRODUCTION=false
OLD_MANAGER_STOP=false
NEW_MANAGER_DEPLOYMENT=false
BOARD_FIRST_BOOT=false
NEXT_ACTION=ONLY_EXACT_SOURCE_REBIND_AND_READONLY_CONTROLLED_WINDOW_PREFLIGHT
```

## 20. R3 现场预检 PASS；R4 独立 systemd 失败恢复准备（2026-10-09）

操作者在 T1 已经执行过 exact PR #540 R3 工具绑定和双只读预检，实际结果：

```text
REVIEWED_BACKUP_SOURCE_BINDING=PASS
ORIGINAL_MANAGER_STOP_RECOVERY_PREFLIGHT=PASS
BROKER_PERSISTENCE_PREFLIGHT=PASS
MANAGER_STOP_NOT_EXECUTED=true
CURRENT_MANAGER_IDENTITY_AND_MOUNTS=PASS
BROKER_RUNNING=PASS
OTHER_RUNNING_CONTAINER_WRITERS=NONE_DETECTED
COLD_BACKUP=NOT_STARTED
REVIEWED_BACKUP_PREFLIGHT=PASS
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

因此 R3 的源版本绑定、旧容器原状、Broker 与其它运行容器可写重叠安全门都已 PASS；但真实跨库快照与隔离恢复尚未发生。

源代码风险复核发现：原 `controlled_window.py` 的 `finally` 在当前 Python 进程被 SIGKILL / SSH 会话异常杀死时可能无法执行，必须独立于执行进程有保障恢复的系统组件。Draft #540 增加两份源文件：

- `emergency_resume.py`：独立进程以 root 私有原容器 inspect 和 live Docker ID/image/config 判定，仅在匹配时对**原 Manager 容器**执行条件性恢复，验证多次 stable-running 和 Broker 不变。
- `systemd_recovery_unit.py`：按照 root-only stage 和本机 Python 实际可执行文件在内存渲染 systemd **一次性 unit**；主入口调用受控停写-复制-恢复，`ExecStopPost` 调用独立恢复进程，unit `TimeoutStartSec=240` / `TimeoutStopSec=90`，不含任何 `[Install]` 项，避免开机自动执行误操作；当前不会写入/启用任何 systemd unit。

此机制在 SSH 链路中断或主进程被 systemd 超时结束时可尝试恢复原 Manager，但不承诺克服主机断电、Docker daemon 不可达或系统服务故障，须有明确手工恢复与业务指标验收步骤。当前不允许进入停机。

### 20.1 下一唯一现场动作：R4 完整版本只读绑定和 systemd 能力探测

最新 PR #540 HEAD 必须在运行前再检查，并从该确切 Git SHA 一次性绑定四份 R4 文件到现有私有备份根目录的新子目录，保留 R3 文件不覆盖。验证四个 git blob 完整哈希、0600/0700 权限、Python 无字节码模式下两种 preflight，检测宿主机 `docker.service`、`systemd-analyze` 以及 unit 的内存 render；绝对不安装、不 enable、不 start 单元，不写生产 DB、不停止 Manager。

预计输出：

```text
R4_RECOVERY_FILES_EXACT_BINDING=PASS
R4_ORIGINAL_MANAGER_RECOVERY_PREFLIGHT=PASS
R4_SYSTEMD_SERVICE_RECOVERY_TEMPLATE=PASS
R4_BROKER_UNCHANGED=PASS
MANAGER_STOP_NOT_EXECUTED=true
COLD_BACKUP=NOT_STARTED
```

**真实冷备份前仍阻断的事项**：确认其它宿主进程写者、业务上旧五身份与 credential/replay 高水位、基于实际 unit 的 `systemd-analyze verify` 与安装/超时触发失败注入模拟、人工失效恢复计划、单服务停写窗口时长。要求 Broker 双网络与旧 Manager 原始 Docker metadata、旧镜像归档全部仍然在 T1 私有 root 范围，证据仅安全状态写入 GitHub。

```text
PR540_R3_T1_READONLY_PREFLIGHT=PASS
PR540_R4_INDEPENDENT_RECOVERY_SOURCE=SOURCE_ONLY
SYSTEMD_RECOVERY_UNIT_INSTALLED=false
SYSTEMD_RECOVERY_UNIT_STARTED=false
OLD_MANAGER_STOP=false
CONSISTENT_COLD_COPY=false
ISOLATED_RESTORE_REAL_DATA=false
CANDIDATE_MANAGER_PRODUCTION_REPLACEMENT=false
FIRST_BOARD_NORMAL_BOOT=false
REAL_SETUP_SECRET_IMPORT=false
```

## 21. T1 R4 GitHub TLS 中断后单次恢复下载成功（2026-10-09）

第一次从 T1 执行 R4 GitHub fetch 时返回 `GnuTLS recv error (-110)`，因为 `set -e` 在 fetch 失败后直接退出，未创建 R4 私有 stage、未停 Manager、未备份数据库。随后操作者使用一次 `HTTP/1.1`、60 秒上限的 git fetch 重试，得到：

```text
R4_SOURCE_FETCH=PASS
R4_EXACT_HEAD=PASS
MANAGER_RUNNING=true MANAGER_RESTARTS=0
BROKER_RUNNING=true BROKER_RESTARTS=0
MANAGER_STOP_NOT_EXECUTED=true
DATABASE_BACKUP=NOT_STARTED
```

本次恢复成功的固定源码提交仍为 `cc33283fbc3b905a039270bbc62584e3756788b8`；T1 已在原工作树 FETCH_HEAD 获得相应版本。后续**不得再进行无必要的 fetch**。新 R4 操作只需在 root 私有既有备份目录下新建 `p4-reviewed-controlled-backup-r4`，对 `cold_snapshot.py`、`controlled_window.py`、`emergency_resume.py`、`systemd_recovery_unit.py` 四文件依次 `git show`、git blob hash 完整比对、权限固定为 0600，并运行三条仅只读 `preflight`，最后比较 Manager/Broker 的 image、StartedAt、RestartCount、Running 均不变。

```text
GIT_TRANSPORT_INCIDENT=CLOSED_RETRY_SUCCESS
PINNED_R4_FETCH_HEAD=PASS
R4_PRIVATE_STAGE=PENDING
R4_SYSTEMD_UNIT_INSTALL=false
R4_SYSTEMD_UNIT_START=false
REAL_COLD_SNAPSHOT=false
PRODUCTION_MANAGER_REPLACEMENT=false
BROKER_RESTART=false
BOARD_FIRST_BOOT=false
NEXT=ONLY_LOCAL_GIT_SHOW_R4_STAGE_AND_THREE_READONLY_PREFLIGHTS
```

## 22. R4 T1 完整只读预检 PASS 与 systemd 文件级验证 STOP（2026-10-09）

T1 操作者最新从 Mac SSH 上报：

```text
R4_RECOVERY_FILES_EXACT_BINDING=PASS
ORIGINAL_MANAGER_STOP_RECOVERY_PREFLIGHT=PASS
BROKER_PERSISTENCE_PREFLIGHT=PASS
MANAGER_STOP_NOT_EXECUTED=true
CURRENT_MANAGER_IDENTITY_AND_MOUNTS=PASS
BROKER_RUNNING=PASS
OTHER_RUNNING_CONTAINER_WRITERS=NONE_DETECTED
COLD_BACKUP=NOT_STARTED
T1_SYSTEMD_SERVICE_RECOVERY_TEMPLATE=PASS
UNIT_CONTENT_SHA256=be7f6dea3991a24fcca51a9c32bb6abffc5f82dd8f1728b189dbbbcbce7de5b6
T1_SYSTEMD_SERVICE_INSTALLED=false
R4_MANAGER_BROKER_UNCHANGED=PASS
SYSTEMD_RECOVERY_UNIT_INSTALLED=false
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

四份 R4 `cold_snapshot.py`、`controlled_window.py`、`emergency_resume.py`、`systemd_recovery_unit.py` 已从固定源码 `cc33283fbc3b905a039270bbc62584e3756788b8` 在 T1 root-only 新 staging 下经 Git blob 校验成功。该阶段 *仅* 生成内存 unit 模板，未进行真实 systemd parser 校验、未安装 unit，亦没有制造真实数据库快照。不能将 `T1_SYSTEMD_SERVICE_RECOVERY_TEMPLATE=PASS` 等同于系统服务已具备运行态故障恢复保障。

### 22.1 下一唯一动作：生成私有 unit 文件并调用 systemd-analyze verify

Mac Terminal 使用 `ssh -T ... 'bash -se' <<'REMOTE'` 只在 T1 已存在的 root 私有备份目录内创建单个 mode 0600 的 `n3w-p4-manager-cold-backup.service`，用已绑定 R4 同版本渲染函数生成实际文本，独立 SHA256 与上述已观察哈希比对，再 `timeout 20s systemd-analyze verify`。输出只含安全 PASS 状态；验证日志仅留在 root 私有目录，不打印 unit 文本、备份 JSON、secret 或真实 host bind Source。不将 unit 复制到 `/etc/systemd/system` 或 `/run/systemd/system`，不 `daemon-reload`、`enable`、`start`，也不执行任何 `docker stop` 或 `capture`。

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'bash -se' <<'REMOTE'
set -eu
umask 077
set -- /root/n3w-p4-manager-rollback-prep-*
test "$#" -eq 1 && test -d "$1" || { echo PRIVATE_DIRECTORY_AMBIGUOUS_STOP=true; exit 21; }
DIR=$1
STAGE="$DIR/p4-reviewed-controlled-backup-r4"
UNIT="$DIR/n3w-p4-manager-cold-backup.service"
LOG="$DIR/n3w-p4-manager-unit-verify-private.log"
test -d "$STAGE" && test "$(stat -c %a "$STAGE")" = 700
test ! -e "$UNIT" && test ! -L "$UNIT" || { echo PRIVATE_UNIT_ALREADY_EXISTS_STOP=true; exit 22; }
test ! -e "$LOG" && test ! -L "$LOG" || { echo PRIVATE_UNIT_LOG_ALREADY_EXISTS_STOP=true; exit 23; }
BEFORE_MANAGER=$(docker inspect --type container --format '{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}' greenhouse-manager)
BEFORE_BROKER=$(docker inspect --type container --format '{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}' n3wfc4-broker-1)
python3 -B - "$DIR" "$STAGE" "$UNIT" <<'PY'
import hashlib
import os
import sys
from pathlib import Path
private, stage, output = map(Path, sys.argv[1:])
sys.path.insert(0, str(stage))
import systemd_recovery_unit as unit
content = unit.render_unit(private, stage, Path(sys.executable).resolve())
require_hash = "be7f6dea3991a24fcca51a9c32bb6abffc5f82dd8f1728b189dbbbcbce7de5b6"
if hashlib.sha256(content.encode()).hexdigest() != require_hash:
    raise SystemExit("UNIT_CONTENT_DRIFT_STOP=true")
with output.open("x", encoding="utf-8") as handle:
    handle.write(content)
os.chmod(output, 0o600)
print("PRIVATE_SYSTEMD_UNIT_HASH=PASS")
PY
if timeout 20s systemd-analyze verify "$UNIT" >"$LOG" 2>&1; then
  echo SYSTEMD_UNIT_FILE_VERIFICATION=PASS
else
  echo SYSTEMD_UNIT_FILE_VERIFICATION_STOP=true
  exit 24
fi
test "$BEFORE_MANAGER" = "$(docker inspect --type container --format '{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}' greenhouse-manager)" || { echo MANAGER_DRIFT_STOP=true; exit 25; }
test "$BEFORE_BROKER" = "$(docker inspect --type container --format '{{.Image}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Running}}' n3wfc4-broker-1)" || { echo BROKER_DRIFT_STOP=true; exit 26; }
echo R4_MANAGER_BROKER_UNCHANGED=PASS
echo UNIT_INSTALLED_BY_THIS_STEP=false
echo UNIT_STARTED_BY_THIS_STEP=false
echo MANAGER_STOP_NOT_EXECUTED=true
echo CONSISTENT_DATA_BACKUP=NOT_STARTED
REMOTE
```

即使本节 `systemd-analyze verify` PASS，也只说明语法及引用路径在本机可被 systemd 静态识别，并非真实启动与 stop-timeout/ExecStopPost 故障注入。独立恢复的部署、真实 Manager 窗口与手工故障恢复契约仍须单独审查，尤其应验证系统服务管理单元的命令路径与安全边界，不得使用模板 PASS 授权生产停写。

```text
R4_EXACT_SOURCE_STAGED=PASS
R4_T1_PREFLIGHT=PASS
SYSTEMD_UNIT_IN_MEMORY_HASH=PASS
SYSTEMD_UNIT_FILE_VERIFY=AWAITING_OPERATOR
RECOVERY_UNIT_INSTALLED=false
RECOVERY_UNIT_STARTED=false
MANAGER_STOP=false
COLD_BACKUP=false
```

## 23. R4 systemd 文件静态校验 PASS；真实数据业务基线与写入者预检仍阻断（2026-10-09）

操作者提供 T1 执行结果：

```text
PRIVATE_SYSTEMD_UNIT_HASH=PASS
SYSTEMD_UNIT_FILE_VERIFICATION=PASS
R4_MANAGER_BROKER_UNCHANGED=PASS
UNIT_INSTALLED_BY_THIS_STEP=false
UNIT_STARTED_BY_THIS_STEP=false
MANAGER_STOP_NOT_EXECUTED=true
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

对应 root-private unit `n3w-p4-manager-cold-backup.service` 的 SHA256 为 `be7f6dea3991a24fcca51a9c32bb6abffc5f82dd8f1728b189dbbbcbce7de5b6`。已用 **T1 本机** `systemd-analyze verify` 完成解析检查；配置文件仅存在于 root 私有备份目录，没有复制到系统的 unit 目录，亦没有 `daemon-reload` / `enable` / `start`。不准把 systemd 静态 PASS 当作 runtime `ExecStopPost` 实际故障恢复的验收。

### 23.1 下一只读动作：确认三个生产 SQLite 主库和 WAL/SHM 的当前状态

在 Manager **仍正常运行**时，仅从 `docker inspect` 元数据查找 2 个真正的 SQLite RW Host Source（registration、n3w），使用 Python `Path.stat` 检查三个主 DB 和各自附属 `-wal` / `-shm` 文件是否存在、大小，以及 `fuser -s` 返回码；不会打开 SQLite、不会执行 SQL、不会修改数据库，不输出私有绝对 Host Source、任何身份记录或密码。重要：Manager 运行时数据库存在文件占用 `BUSY` 是正常现象，不应将其视为冷备份故障；此检查仅为受控停写前提供基线。不能靠当前 `fuser` 无占用就认定没有宿主机定时写入者。

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'python3 -B -' <<'PY'
import json
import subprocess
from pathlib import Path
raw = subprocess.run(
    ["docker", "inspect", "--type", "container", "greenhouse-manager"],
    check=True, capture_output=True, text=True,
).stdout
manager = json.loads(raw)[0]
binds = {m["Destination"]: Path(m["Source"]) for m in manager["Mounts"]}
database_specs = [
    ("registration", "/var/lib/greenhouse-manager-registration", "registration.sqlite3"),
    ("credential", "/var/lib/greenhouse-manager/n3w", "credential-lifecycle.sqlite3"),
    ("replay", "/var/lib/greenhouse-manager/n3w", "replay.sqlite3"),
]
for label, parent, filename in database_specs:
    main = binds[parent] / filename
    if not main.is_file() or main.is_symlink():
        raise SystemExit("DB_MAIN_MISSING_OR_UNEXPECTED_STOP=" + label)
    print(f"DB_{label.upper()}_MAIN=PASS")
    for kind, path in [
        ("MAIN", main), ("WAL", Path(str(main) + "-wal")),
        ("SHM", Path(str(main) + "-shm")),
    ]:
        if not path.exists():
            print(f"DB_{label.upper()}_{kind}_PRESENT=false")
            continue
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"DB_{label.upper()}_{kind}_TYPE_STOP=true")
        p = subprocess.run(["fuser", "-s", str(path)], capture_output=True)
        if p.returncode not in (0, 1):
            raise SystemExit(f"DB_{label.upper()}_{kind}_FUSER_UNCERTAIN_STOP=true")
        print(f"DB_{label.upper()}_{kind}_PRESENT=true")
        print(f"DB_{label.upper()}_{kind}_OPEN_BY_PROCESS={str(p.returncode == 0).lower()}")
        print(f"DB_{label.upper()}_{kind}_SIZE_KIB={(path.stat().st_size + 1023)//1024}")
print("THREE_PRODUCTION_DB_METADATA_PREFLIGHT=PASS")
print("BUSINESS_IDENTITY_COUNTS=NOT_READ")
print("CONSISTENT_DATA_BACKUP=NOT_STARTED")
PY
```

此命令刻意不直接连接任何 live SQLite，避免在线 `PRAGMA` 查询可能造成 WAL 读侧影响、也不把在线单独读到的状态错误地认作三库一致性基线。真正的历史身份、凭据版本、replay 高水位应先在后续停写的**同一冷快照和隔离恢复副本**上以明确表契约取证，再决定是否可进入旧 Manager 恢复与之后的升级阶段。

```text
SYSTEMD_UNIT_T1_STATIC_VERIFY=PASS
SYSTEMD_UNIT_INSTALLED=false
MANAGER_AND_BROKER_UNCHANGED=PASS
DB_METADATA_AND_SIDECAR_PREFLIGHT=PENDING_OPERATOR
HOST_NONCONTAINER_WRITER_ELIMINATION=INCOMPLETE
FIVE_HISTORIC_IDENTITIES_SNAPSHOT_PROOF=PENDING
CREDENTIAL_AND_REPLAY_BASELINE=PENDING
LIVE_COLD_SNAPSHOT=false
ISOLATED_RESTORE_REAL_DATA=false
MANAGER_UPGRADE=false
```

## 24. 生产三库元数据已核实；核对文件打开者是否属于原 Manager 进程树（2026-10-09）

T1 操作者现场返回：

```text
DB_REGISTRATION_MAIN=PASS
DB_REGISTRATION_MAIN_PRESENT=true
DB_REGISTRATION_MAIN_OPEN_BY_PROCESS=true
DB_REGISTRATION_MAIN_SIZE_KIB=660
DB_REGISTRATION_WAL_PRESENT=false
DB_REGISTRATION_SHM_PRESENT=false
DB_CREDENTIAL_MAIN=PASS
DB_CREDENTIAL_MAIN_PRESENT=true
DB_CREDENTIAL_MAIN_OPEN_BY_PROCESS=true
DB_CREDENTIAL_MAIN_SIZE_KIB=28
DB_CREDENTIAL_WAL_PRESENT=false
DB_CREDENTIAL_SHM_PRESENT=false
DB_REPLAY_MAIN=PASS
DB_REPLAY_MAIN_PRESENT=true
DB_REPLAY_MAIN_OPEN_BY_PROCESS=true
DB_REPLAY_MAIN_SIZE_KIB=7944
DB_REPLAY_WAL_PRESENT=false
DB_REPLAY_SHM_PRESENT=false
THREE_PRODUCTION_DB_METADATA_PREFLIGHT=PASS
BUSINESS_IDENTITY_COUNTS=NOT_READ
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

结论：三个主数据库都存在，被某些进程打开，全部 -wal/-shm 当前不存在。**不意味着数据库损坏或复制失败**；并不表示 manager 一定是唯一打开者、也不表示 SQLite 同一时间点快照已经存在。WAL/SHM 可能动态出现。暂时不能单凭 `OPEN_BY_PROCESS=true` 断定打开者身份。

### 24.1 下一步只读打开者归属检查（不输出 PID 和真实 Host Source）

从 Docker metadata 取 Manager 的**宿主机 PID**和三 DB 对应宿主机 Source，使用 `fuser` 返回的 PID，经 `/proc/<pid>/status` 的 PPid 链确定是否属于 Manager 进程树。当前仍不打开 SQLite 数据库（`fuser` 和 `stat` 仅检查进程与元数据）、不读取真实身份/凭据/高水位、不修改任何生产服务、不向 stdout 输出任何 PID、Host Source、环境秘密或数据库内容。若 PID 在观测窗口已消失或归属不明确，立即 STOP，不归类为产品故障。此检查只能确认**当前观察到的文件打开者**，不能排除未来定时启动的宿主写入者；正式受控停写窗口需再次确认零打开者并进行源稳定性前后对比。

Mac Terminal：

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'python3 -B -' <<'PY'
import json
import re
import subprocess
from pathlib import Path

def docker_state(name):
    p = subprocess.run(
        ["docker", "inspect", "--type", "container", name],
        capture_output=True, text=True, check=True, timeout=10,
    )
    x = json.loads(p.stdout)[0]
    return x, (x["Id"], x["Image"], x["State"]["StartedAt"], x["RestartCount"], x["State"]["Running"])

manager, old_manager = docker_state("greenhouse-manager")
broker, old_broker = docker_state("n3wfc4-broker-1")
if not old_manager[-1] or not old_broker[-1]:
    raise SystemExit("PRODUCTION_CONTAINER_NOT_RUNNING_STOP=true")

root_pid = int(manager["State"]["Pid"])
if root_pid <= 1:
    raise SystemExit("MANAGER_HOST_PID_INVALID_STOP=true")

mounts = {m["Destination"]: Path(m["Source"]) for m in manager["Mounts"]}
specs = (
    ("REGISTRATION", "/var/lib/greenhouse-manager-registration", "registration.sqlite3"),
    ("CREDENTIAL", "/var/lib/greenhouse-manager/n3w", "credential-lifecycle.sqlite3"),
    ("REPLAY", "/var/lib/greenhouse-manager/n3w", "replay.sqlite3"),
)

def belongs_to_manager(pid):
    visited = set()
    for _ in range(128):
        if pid == root_pid:
            return True
        if pid <= 1 or pid in visited:
            return False
        visited.add(pid)
        status = Path("/proc") / str(pid) / "status"
        try:
            data = status.read_text()
        except OSError:
            raise SystemExit("PROCESS_IDENTITY_RACE_STOP=true")
        match = re.search(r"^PPid:\s*(\d+)\s*$", data, flags=re.MULTILINE)
        if match is None:
            raise SystemExit("PROCESS_PARENT_UNREADABLE_STOP=true")
        pid = int(match.group(1))
    raise SystemExit("PROCESS_PARENT_DEPTH_STOP=true")

for label, dest, name in specs:
    db = mounts[dest] / name
    if not db.is_file() or db.is_symlink():
        raise SystemExit("DB_MAIN_LAYOUT_DRIFT_STOP=" + label)
    p = subprocess.run(["fuser", str(db)], capture_output=True, text=True, timeout=10)
    tokens = p.stdout.split()
    if p.returncode not in (0, 1) or (p.returncode == 0 and not tokens) or (p.returncode == 1 and tokens):
        raise SystemExit("FUSER_RESULT_UNCERTAIN_STOP=" + label)
    if any(not token.isdecimal() for token in tokens):
        raise SystemExit("FUSER_PID_FORMAT_UNEXPECTED_STOP=" + label)
    pids = {int(token) for token in tokens}
    owned = sum(belongs_to_manager(pid) for pid in pids)
    unknown = len(pids) - owned
    print(f"DB_{label}_OPENERS_COUNT={len(pids)}")
    print(f"DB_{label}_MANAGER_PROCESS_TREE_OPENERS={owned}")
    print(f"DB_{label}_OTHER_OR_UNCLASSIFIED_OPENERS={unknown}")
    if unknown:
        raise SystemExit("OTHER_OR_UNCLASSIFIED_DB_OPENER_STOP=" + label)

_, new_manager = docker_state("greenhouse-manager")
_, new_broker = docker_state("n3wfc4-broker-1")
if old_manager != new_manager or old_broker != new_broker:
    raise SystemExit("CONTAINER_STATE_DRIFT_STOP=true")
print("THREE_DB_CURRENT_OPENER_OWNERSHIP_PREFLIGHT=PASS")
print("MANAGER_BROKER_UNCHANGED=PASS")
print("CONSISTENT_DATA_BACKUP=NOT_STARTED")
PY
```

三份 DB 当前已经报告 `OPEN_BY_PROCESS=true`，预期每个 `OPENERS_COUNT` 大于 0，全部归属于当前 Manager 进程树，`OTHER_OR_UNCLASSIFIED_OPENERS=0`。如果观察进程在检查中自然退出而触发 `PROCESS_IDENTITY_RACE_STOP`，保留失败证据并复核命令条件；不自动修改 Docker 或数据库。即使所有打开者均属于 Manager，**也不代表系统中不会有未打开文件的定时写入程序**，更不授权停机。下一阶段需要与恢复窗口/业务库语义快照一起复核。

```text
THREE_LIVE_DB_MAIN_METADATA=PASS
LIVE_WAL_SHM_PRESENT=false
LIVE_THREE_DB_OPENERS=OBSERVED
OPENER_OWNERSHIP_CLASSIFICATION=PENDING
BUSINESS_IDENTITY_AND_REPLAY_HIGH_WATER=NOT_CHECKED
COLD_SNAPSHOT=false
ISOLATED_RESTORE=false
MANAGER_STOP=false
UNIT_INSTALLED=false
```

## 25. 使用者要求：终止逐项人工预检，收敛为单次可恢复冷备份执行包（2026-10-09）

用户明确反馈：前面一项一条 Mac Terminal 检查、反复提交结果的工作方式过于繁杂、浪费时间，要求尽可能一次验证完成。本节为**后续执行方式冻结要求**，优先于 §1–§24 中仍残留的多次人工 preflight 建议；旧章节保留为历史证据而非未来反复命令指令。

最新已完成 T1 只读证据：

```text
DB_REGISTRATION_OPENERS_COUNT=1
DB_REGISTRATION_MANAGER_PROCESS_TREE_OPENERS=1
DB_REGISTRATION_OTHER_OR_UNCLASSIFIED_OPENERS=0
DB_CREDENTIAL_OPENERS_COUNT=1
DB_CREDENTIAL_MANAGER_PROCESS_TREE_OPENERS=1
DB_CREDENTIAL_OTHER_OR_UNCLASSIFIED_OPENERS=0
DB_REPLAY_OPENERS_COUNT=1
DB_REPLAY_MANAGER_PROCESS_TREE_OPENERS=1
DB_REPLAY_OTHER_OR_UNCLASSIFIED_OPENERS=0
THREE_DB_CURRENT_OPENER_OWNERSHIP_PREFLIGHT=PASS
MANAGER_BROKER_UNCHANGED=PASS
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

这只证明**观测瞬间** 3 个 SQLite 主库各有一个打开者且都属于旧 Manager 进程树；不证明后续绝对不存在系统级周期写者。当前已通过的原始 Docker 保存、旧镜像 SHA256、私有权限、六 mounts、其他容器 RW 重叠、Host Python/磁盘、原 Manager restart policy、R4 四文件 exact bind、CI、R4 systemd 静态 verify **不再安排重复人工检查**；必要的即时重检自动纳入一次性脚本内部。

### 25.1 采用一个 NEXT_ONE_GATE，两个不可混淆的边界

```text
NEXT_ONE_GATE=N3W_P4_T1_MANAGER_ONE_SHOT_COLD_BACKUP_WITH_OLD_MANAGER_RESTORE_DESIGN_AND_EXECUTOR
PRIMARY_GOAL=ONE_OPERATOR_LAUNCH_ONE_FINAL_EVIDENCE_REPORT
SOURCE_PREPARATION=HOST_ONLY_GITHUB_ONLY
LIVE_T1_PRECHECKS=EMBEDDED_IN_SAME_EXECUTION
MANAGER_STOP_APPROVAL=REQUIRED_BEFORE_ANY_REAL_STOP
BROKER_MUTATION=false
CANDIDATE_MANAGER_DEPLOYMENT=false
FIRST_BOARD_NORMAL_BOOT=false
```

1. **执行包源码/模拟验收（无 T1 人工操作）**：在 Draft #540 扩充并整合原 `cold_snapshot.py`、`controlled_window.py`、`emergency_resume.py`、`systemd_recovery_unit.py`，消除中间人机往返；一次安装/部署路径必须仅作用于 P4 独立的临时 systemd 单次任务，不能自动 enable 也不能碰 Broker。合成环境覆盖成功、stop 失败、capture 失败、服务终止、时限超出、源目录变化、WAL/SHM、新增宿主写者、原容器恢复错误。不可把模拟成功当作 T1 故障注入验收。
2. **真实操作前唯一一次重大授权**：明确告知旧 Manager 将短暂停止、Broker 仍运行、观察预算与人工恢复方案；不默认为现有源码准备授权等于停写授权。
3. **用户仅执行一次经校验入口**：入口内部先做即时身份/配置、盘空间、文件、非容器进程写者可见性、监督 unit 状态；不满足直接 STOP（没有 service mutation）。通过后调用受监督旧 Manager stop → 检查数据库全部主/sidecar 无占用 → 三处 RW 冷拷贝 → 源副本与隔离恢复 hashes/permissions/3 SQLite integrity → 同一冷快照中检查历史已配对身份/凭据代际/replay 高水位 → 恢复**原 Manager** → Broker 未重启/Manager 稳定观察 → 单份摘要。
4. **失败恢复不可夸大**：systemd `ExecStopPost` + Python `finally` 为分层救援，不能应对停电、Docker 守护进程不可用和整机宕机。若旧 Manager 不能恢复，必须以 FAILED_STOP 保存现场，而不是输出 PASS 或继续候选升级。只有一个受控 STOP 点——原 Manager 必须确认已恢复并且业务验收成功，否则不得进入新镜像升级。

**尚未实现/必须在单次真实执行前补齐**：业务身份、credential generation、replay high-water 在一致冷备份与恢复副本中的只读断言；独立 systemd 单次执行任务的部署/回收方式及仅执行一次保护；受监督服务停止超时配置和人工恢复预案；对宿主定时/其他写入者的尽力排除；真实业务读取的隐私保护。不得跳过这些要求直接执行现有 `controlled_window.py execute`。

后续答复原则：无需继续索取重复的 `fuser`、`stat`、`git fetch`、`docker inspect` 手工结果；只有新的真实 blocker 才单独索取最低必要证据。以 GitHub 状态和单次任务证据为准，不依赖聊天记录完成验收。

## 26. 单次执行包 R5 开发集成与合成故障验证（2026-10-09）

按使用者明确同意的收敛方向，开发和测试统一放入 Draft #540，后续用户**不再需要重复输入 Mac Terminal 逐项检查命令**。前述六个挂载、三 SQLite 主库/WAL/SHM、唯一 Manager 进程打开者、Git 精确源码、systemd 静态校验、Broker 运行状态等现场只读检查，均已真实通过并留有前面的证据。本节不把这些静态证据冒充真实冷备份验收。

### 26.1 R5 版本化单次受监督执行包

- `one_shot_operator.py`：未来单次入口。自动校验旧 Manager docker image/config/mount，Broker 未重启、旧镜像 tar 私有 SHA、三个 SQLite DB 打开者属于当前原 Manager 的进程树、宿主存储余量、其它运行容器可写源、单次 systemd 名称无冲突及 unit 语法；若任何一项不通过，则在停止原 Manager 之前 STOP。
- `business_snapshot.py`：在同一停写窗口冷复制/隔离恢复所得的**两份副本**上，用只读 SQLite 查询验证注册与历史身份、凭据历史和代际、重放 state/seen 和高水位，逐表计数及有类型的内容哈希必须一致；要求可证明至少 5 个历史身份、至少 1 条 credential 历史、replay state 非空。结果只存 private 0600，不在终端打印身份值、密码、Host Source 等私密内容。
- `cold_snapshot.py`：三处互不嵌套宿主机 RW 源完整复制（registration、n3w、relay keys）、主 DB 和动态出现的 WAL/SHM 占用检查、前后真实源/冷副本与隔离恢复的 SHA256/UID/GID/mode，三数据库完整性测试，源变更立刻 fail closed。
- `controlled_window.py`：在 Manager **已经通过单次明确批准**前绝不执行停止；停止后运行 snapshot+business semantic 并在 Python finally 尝试启动原 Manager，超时或失败停止新阶段操作。
- `systemd_recovery_unit.py` 与 `emergency_resume.py`：使用 R5 staging `p4-reviewed-controlled-backup-r5`，一次性 systemd 服务 `ExecStart` 执行旧 Manager 控制窗口，`ExecStopPost` 独立救援，拒绝 service 名称被其它 systemd 单元占用；不 `enable` 开机自启，不 touch Broker；成功后自动清除本次 `/run/systemd/system` 临时 unit。失败时保留现场。
- **唯一终端结果**：安全前置检查 PASS 后提交 systemd 单次任务，等待**真实启动时间戳**和服务成功退出，再检查 3 数据库/业务数据私有证据、原 Manager ID 与正常运行、Broker 原 startedAt/restartCount，不从模拟结果臆造真实通过。若超时/意外中断，保留 unit 和日志并报告 STOP。

### 26.2 权限与状态

- 当前本节所有变动仍为 Draft #540 GitHub 源码和模拟 CI；**未在 T1 运行 R5 入口**，旧 R4 私有 stage 保留且不应再作为正式执行的版本。
- **本次用户对“单次验证方案”的同意，只构成继续整合源码/测试的授权，不等于允许现在停止生产 Manager**。在提供最终单次 Mac Terminal 执行命令之前，仍须独立明确确认 Manager 可短暂停止；Broker 必须维持运行，不能借此升级候选 P4 镜像或给实板导入任何配置。
- systemd + Python 双救援可覆盖常见执行进程退出/SSH 断开，但不能承诺在宿主机断电、Docker/systemd 整体失效、磁盘故障时自动恢复。STOP 后应保留私有目录、unit/job 信息，不得继续升级。未来实机执行后仍需记录运行时业务 MQTT 观察，不把容器已运行等同数据链路已经验收。
- 预期冷复制时间预算 `WINDOW_TIMEOUT_SECONDS=150`，`systemd TimeoutStartSec=240`，`TimeoutStopSec=90`，操作者等待上限约 390 秒；超时输出 STOP，不盲目循环。
- 独立的源码模拟测试覆盖：冷备份/隔离恢复、漏失历史身份、凭据/高水位克隆不一致、数据库表缺失、源目录中途变化、WAL/SHM 占用、service unit 名称冲突、作业并未真正启动却返回 inactive、systemd 失败、其它宿主进程占用 DB、原容器恢复与救援阻断。

```text
PR540_R5_SINGLE_ENTRY_SOURCE=READY
PR540_R5_SYNTHETIC_CI=REQUIRE_CURRENT_HEAD_ALL_GREEN
T1_R5_EXECUTION=NOT_STARTED
T1_REAL_MANAGER_STOP=false
T1_COLD_COPY=false
T1_BUSINESS_RESTORE_PROOF=false
T1_REAL_OLD_MANAGER_RECOVERY=false
PRODUCTION_MANAGER_UPGRADE=false
BROKER_RESTART=false
NEXT=SOURCE_REVIEW_AND_CURRENT_CI_THEN_ONE_EXPLICIT_LIVE_STOP_APPROVAL
```

## 27. R5 首次真实旧 Manager 一致性冷备份及原版恢复：现场 PASS（2026-10-09）

### 27.1 授权与源版本

用户在当前对话对唯一一次真实生产操作作出明确“批准”：允许在 Broker 保持运行的条件下，短暂停止 **现有旧版 greenhouse-manager**，一次完成三个独立 RW 宿主 Source（registration、n3w、relay keys）冷备份、隔离恢复、SQLite 与业务语义校验，最终恢复同一原容器。**并未批准**部署新版本 Manager、重启 Broker 或实板操作。

执行源码：`ca75d6bbc672d9e1e96500c88827ec529855f2b9`（PR #540 的 R5 精确头，提交时 12/12 CI PASS）；由 Mac Terminal `ssh -T` 向 T1 投递 **单条**脚本完成原 T1 Git fetch、六份 R5 源码 Git blob hash 校验、一次 `one_shot_operator.py execute --permit-manager-stop`。

### 27.2 一次完整真实执行证据

操作者真实返回的安全归档摘要如下（T1 连接目标按仓库公开安全规范脱敏，其余状态字段保留）：

```text
T1 SSH 目标：PRIVATE_T1_HOST_REDACTED
R5_EXACT_EXECUTION_PACKAGE=PASS
APPROVED_OLD_MANAGER_COLD_BACKUP=STARTING
SINGLE_ENTRY_PRECHECKS=PASS
SUPERVISED_COLD_BACKUP_JOB_SUBMITTED=true
ONE_SHOT_THREE_DATABASE_COLD_BACKUP=PASS
ONE_SHOT_ISOLATED_RESTORE_AND_BUSINESS_STATE=PASS
ORIGINAL_MANAGER_RESTARTED=PASS
BROKER_UNCHANGED=PASS
P4_CANDIDATE_MANAGER_DEPLOYED=false
ONE_SHOT_MANAGER_COLD_BACKUP_AND_OLD_RESTORE=PASS
FINAL_COLD_BACKUP_RESULT=PASS
```

### 27.3 确切结论和证据边界

- **PASS / CLOSED**：已从现场单次入口收到真实冷备份完成、三处独立持久来源目录复制、隔离恢复、源码要求的 3 SQLite 完整性/业务表指纹比对、历史身份数量下限、credential/replay 保存、原版 Manager 原容器恢复运行，以及 Broker 未重启的统一通过标志。源文件和私有 JSON/镜像 tar/完整 SHA256 文件明细**只保存在 T1 root 私有目录**，没有上传公开 GitHub。
- 这份 transcript 不包含原始 private manifest、具体文件哈希值、确切旧五身份明细、数据库内容或恢复后 MQTT 数据流样本；不应补造这些事实。源语义校验 `>=5` 历史已知硬件身份是最低安全约束，不等于公开证明恰好五个当前活跃配对节点。
- **尚未验收**：Manager 恢复后正常 MQTT 业务数据收发、与设备端真实通信连续性、新版 Manager 生产镜像部署及 P4 首次板级正常启动；这些应作为另一个受控阶段处理，不能由本次容器恢复 PASS 推定通过。
- **本阶段严格 STOP**：不重复冷备份、不手工修改私有 DB/密钥、不启动第二套 Manager、不移除原容器、不重启 Broker、不开始实板配对。不要求用户继续输入 `fuser`、`stat`、`docker inspect` 等零散命令。
- 单次 R5 执行包已在成功路径清理其由程序安装的临时 systemd service；但终端没有给出独立 `systemctl` unit 清理状态行，因此不能额外将“现场复查该 unit 已消失”宣称为独立实测证据。

```text
NEXT_ONE_GATE=N3W_P4_T1_OLD_MANAGER_POST_BACKUP_RUNTIME_ACCEPTANCE_AND_NEW_MANAGER_DEPLOYMENT_READINESS_DESIGN
P4_OLD_MANAGER_ONE_SHOT_COLD_BACKUP=CLOSED_PASS
P4_THREE_RW_SOURCE_SNAPSHOT_AND_ISOLATED_RESTORE=CLOSED_PASS
P4_BUSINESS_SEMANTIC_RESTORE=CLOSED_PASS
P4_OLD_MANAGER_RUNTIME_RESUMED=CLOSED_PASS
P4_BROKER_UNCHANGED=CLOSED_PASS
P4_POST_RESTART_MQTT_BUSINESS_ACCEPTANCE=NOT_YET_VALIDATED
P4_NEW_MANAGER_DEPLOYMENT=NOT_STARTED
P4_CLEAN_PRODUCT_BOARD_NORMAL_BOOT=NOT_STARTED
T1_PRIVATE_BACKUP_CONTENT_PUBLICATION=false
```

## 28. 旧 Manager 原版恢复后 MQTT 业务连续性：一次性只读观察设计（2026-10-09）

上阶段真实 T1 R5 冷备份 / 隔离恢复 / 原容器重启由操作者回传统一 `FINAL_COLD_BACKUP_RESULT=PASS`，证据已归档 §27。用户同意继续下一阶段，但**没有批准新的生产停机、候选镜像替换、Broker 重启、板卡移动或初次正常启动**。

### 28.1 当前唯一新门

```text
NEXT_ONE_GATE=N3W_P4_T1_OLD_MANAGER_POST_BACKUP_MQTT_BUSINESS_READONLY_ACCEPTANCE_20261009_01
SCOPE=ONE_OPERATOR_MAC_TERMINAL_SINGLE_90S_READONLY_PROBE
R5_COLD_BACKUP=ALREADY_CLOSED_PASS_DO_NOT_REPEAT
MANAGER_MUTATION=false
BROKER_MUTATION=false
BOARD_ACCESS=false
GITHUB_AUTHORITATIVE_RECORD=true
```

用 90 秒 single-shot 只读观察，检查：

1. `greenhouse-manager` 和 `n3wfc4-broker-1` Docker 当前仍在运行，窗口前后 exact 容器 ID、镜像 ID、`StartedAt`、`RestartCount` 都一致；不重复原先早已通过的多轮源目录/备份验证。
2. 当前 Manager 主进程在宿主机拥有到 Broker TLS TCP 8883 的 ESTABLISHED 连接。只打印 `CONNECTED=true/false`，不会打印 IP、PID、socket endpoint、MQTT credential、真实 NODE_ID。**TCP 建立本身不证明 MQTT 身份鉴权或应用数据已收到。**
3. 从**原 Manager 容器命名空间**只读打开 `/var/lib/greenhouse-manager/n3w/replay.sqlite3`，SQLite URI `mode=ro` + `PRAGMA query_only=ON`，窗口两端只取 `n3w_replay_seen` 总计数；输出增量而不是节点身份。**严格要求增量正值**才宣称观察到了新的持久化节点遥测处理记录。旧版本可能缺少容器 Python；此时只作为观测工具不可用，不能判定运行系统失败。
4. 观察期间 Manager/Broker 容器身份与启动时刻不变，TCP 连接存在且 replay 条目增加，则判定 `PASS_LIVE_CANONICAL_INGRESS`。TCP 建立而 replay 无增量时标记 `INCONCLUSIVE_NO_FRESH_TELEMETRY`，不得误归类为 Broker/Manager 产品故障（现场节点可能未上电/没有业务数据）。只有真实容器停机或容器重启等直接状态证据才属于 `FAIL_RUNTIME_CHANGED`。
5. 全过程不执行 `docker stop/start`、`systemctl start/stop`、任何数据库写入、任何网络发布或主动配对。不在 GitHub 提交真实数据库/密码/私有地址/身份。

### 28.2 数据与验收边界

已有 R5 验收仅证明冷备份和原容器恢复运行；当前 90 秒检查用于补足恢复后 Manager 能否实际继续接收及提交节点遥测的业务证明。如果没有实时节点，短窗口无法凭空制造数据，因此 `INCONCLUSIVE` 是有效证据，并不触发重复备份或重启设备。报告至少包含容器未重启、TCP 连接状态、replay delta，以及是否是真正新数据。最终新 P4 Manager 镜像替换和首次板级配对仍须另行授权与独立准入。

```text
P4_OLD_MANAGER_COLD_BACKUP=CLOSED_PASS
P4_POST_BACKUP_MQTT_RUNTIME_ACCEPTANCE=PENDING_SINGLE_LIVE_READONLY_OBSERVATION
P4_NEW_MANAGER_DEPLOYMENT=NOT_AUTHORIZED
P4_BOARD_FIRST_NORMAL_BOOT=NOT_AUTHORIZED
```

## 29. 旧 Manager 冷备份恢复后 90 秒只读 MQTT 观察：稳定、无新 replay，业务仍未闭环（2026-10-09）

### 29.1 现场真实观测

操作者按 §28 单条 Mac Terminal 命令，使用 90 秒的只读窗口，提供以下**去除私有 T1 地址**的输出：

```text
OBSERVATION_WINDOW=90_SECONDS
OBSERVATION_REMAINING_SECONDS=90
OBSERVATION_REMAINING_SECONDS=60
OBSERVATION_REMAINING_SECONDS=30
MANAGER_BROKER_RUNTIME_STABLE=true
MQTT_TCP_CONNECTED_BOTH_SAMPLES=true
REPLAY_TUPLES_BEFORE=475
REPLAY_TUPLES_AFTER=475
REPLAY_TUPLES_DELTA=0
POST_BACKUP_RUNTIME_ACCEPTANCE=INCONCLUSIVE_NO_FRESH_TELEMETRY
PRODUCTION_MUTATION=false
```

### 29.2 确切判定：不把无流量当成故障

- **PASS**：旧原版 Manager 与 Broker 在观察窗口内的容器 ID、image、StartedAt、RestartCount 和 Running 均保持不变；Manager 到 TLS Broker 的 TCP 会话两端均观察为 established。
- **INCONCLUSIVE，不是 FAIL**：持久化 `n3w_replay_seen` 表的行数从 475 保持到 475。只能证明窗口内没有观测到**新增的独立 replay tuple**；不能直接证明没有 MQTT 消息、不能证明配对节点正上报或旧 Manager 完整应用层收发失效。重复或被拒绝的数据也可能不会增加该表行数。
- **环境事实未知**：本轮证据没有提供任意已上电节点持续上报/业务发布的同期可靠观测，也没有采样到 Manager 对具体新数据的持久化接受证据。不能编造有在线节点或推断运行异常。
- **之前的 P4 R5 冷备份、隔离恢复及原容器恢复 CLOSED_PASS 不回退**。不再盲目重复 90s 静默观察、不重启/断电/重刷板、不重复冷备份、不执行 Broker 或 Manager 变更。

### 29.3 最小后续决策

下一步只需一次确认现场是否**本来就应有正在发数据的在线节点**。如果没有，停止当前 live-telemetry 接受检查，按受控 P4 首次产品板联机之后的实测业务数据闭环；这不阻碍先进行 host-only / source-only 的**候选 Manager 部署方案设计**，但不授权生产替换。如果现场确认存在持续发报节点，则应先设计**一个**新的有明确真实消息来源/权威接收证据、有限窗口、只读的端到端测试，不得再使用单独 `INFO` 行或 `replay delta=0` 宣称设备故障。

```text
P4_R5_REAL_COLD_BACKUP_AND_RESTORE=CLOSED_PASS
P4_OLD_MANAGER_RUNTIME_STABILITY_POST_RESTART=PASS
P4_MQTT_TCP_ESTABLISHED_TWO_SAMPLES=PASS
P4_REPLAY_TUPLES_BEFORE=475
P4_REPLAY_TUPLES_AFTER=475
P4_REPLAY_TUPLES_DELTA=0
P4_POST_RESTART_APP_MQTT_BUSINESS=INCONCLUSIVE_NO_FRESH_TELEMETRY
P4_LIVE_NODE_TRAFFIC_PRESENT=UNKNOWN
REPEAT_SILENT_PROBE=false
PRODUCT_DEFECT_PROVEN=false
MANAGER_STOP_OR_RESTART=false
BROKER_MUTATION=false
P4_NEW_MANAGER_DEPLOYMENT=NOT_AUTHORIZED
P4_BOARD_FIRST_NORMAL_BOOT=NOT_AUTHORIZED
```
