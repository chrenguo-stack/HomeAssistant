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

### 10.1 下一步：仅将 #538 精确源码冻结到 T1 独立工作目录

使用当前 T1 SSH 登录；来源固定公开 GitHub 分支 `fix/n3w-pr537-terminal-claim-write-ssh-target-minimal-20261009`，要求 checkout HEAD **精确匹配** `3d86d6bfaf361dc3a3d7295d046f541a544d552d`。这只创建 Git 工作目录，**不**启动、停止、重建 Docker 容器，不触碰现有 DB/secret/board。此时并不构建镜像。

```bash
printf 'T1 SSH 目标：'
IFS= read -r T1_SSH
ssh -T "$T1_SSH" 'set -eu
SHA=3d86d6bfaf361dc3a3d7295d046f541a544d552d
BRANCH=fix/n3w-pr537-terminal-claim-write-ssh-target-minimal-20261009
DIR=/var/tmp/n3w-p4-manager-source-${SHA}
umask 077
if test -e "$DIR"; then echo SOURCE_WORKDIR_ALREADY_EXISTS_STOP=true; exit 11; fi
mkdir -m 700 "$DIR"
git -C "$DIR" init -q
git -C "$DIR" remote add origin https://github.com/chrenguo-stack/HomeAssistant.git
git -C "$DIR" fetch -q --depth 1 origin "$BRANCH"
git -C "$DIR" checkout -q --detach FETCH_HEAD
ACTUAL=$(git -C "$DIR" rev-parse HEAD)
if test "$ACTUAL" != "$SHA"; then echo SOURCE_EXACT_HEAD_MISMATCH_STOP=true; exit 12; fi
test -f "$DIR/host/greenhouse-manager/Dockerfile"
test -f "$DIR/host/greenhouse-manager/pyproject.toml"
echo SOURCE_EXACT_HEAD=PASS
echo SOURCE_CONTAINER_BUILD_CONTEXT=READY
echo EXISTING_MANAGER_NOT_TOUCHED=true'
```

失败即 STOP：不删除旧镜像、不清理 Git 目录、不自动降级到 main 或漂移的 branch HEAD。需要按确切失败原因诊断，不能进入镜像构建。

### 10.2 后续镜像构建与合成无网验证的边界

收到 `SOURCE_EXACT_HEAD=PASS` 后，下一阶段可使用该**独立目录**运行 `docker buildx build --load`，以从源码 sha 派生的**新标签**和 OCI `org.opencontainers.image.revision` 标签绑定新镜像；**禁止复用当前 Manager 镜像 ID 或覆盖旧镜像标签**。Dockerfile 的 `python:3.11-slim` 与 pip 依赖范围尚未锁定，构建结果并非天然逐位可重现：仍需记录最终镜像 ID、基础层与实际包版本并隔离检验 `p4-pending-readonly`、`import-payload` 和 #534 管理器锁内期限检查。独立镜像构建可能占用 T1 资源或拉取依赖；不应将此描述为“完全无风险的只读操作”。后续在明确磁盘容量门槛下单独执行，不自动触发运行中的 Manager 部署。

正式生产部署仍要求重新核对全部秘密配置/绑定、带停止写入边界的多数据库一致备份、隔离恢复演练，以及 Broker 原双网络与 TLS 连续性。缺失任何条件均不允许替换运行中的 Manager，也不得启动已 P3 写入的干净板。

```text
WAL_SHM_CHECK=CURRENT_ALL_ABSENT
GIT_AVAILABLE=true
BUILDX_AVAILABLE=true
SOURCE_ONLY_FETCH_READY=true
CANDIDATE_IMAGE_BUILT=false
MANAGER_IMAGE_DEPLOYED=false
THREE_DB_SNAPSHOT_VALIDATED=false
BOARD_FIRST_NORMAL_BOOT=false
NEXT_ACTION=GIT_EXACT_HEAD_STAGING_ONLY
STOP_AFTER_SOURCE_BINDING=true
```

### 10.3 新镜像构建与隔离检查的现场命令

**仅在 §10.1 精确源码绑定成功后执行。** 本步骤会写入 **新的、独立的 Docker 镜像及构建缓存**，可能占用 CPU、网络和磁盘，不是只读；但是不启动或替换生产 Manager/Broker，不装载真实数据库或秘密文件。要求 Docker 根目录执行前仍至少有 4 GiB 空闲（工程保护阈值，不是保证不会耗尽）。拒绝覆盖已有新标签，拒绝 source drift，绝不使用 `docker system prune`。

```bash
ssh -T "$T1_SSH" 'set -eu
SHA=3d86d6bfaf361dc3a3d7295d046f541a544d552d
DIR=/var/tmp/n3w-p4-manager-source-${SHA}
TAG=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
test -d "$DIR/.git"
test "$(git -C "$DIR" rev-parse HEAD)" = "$SHA"
if docker image inspect "$TAG" >/dev/null 2>&1; then echo CANDIDATE_TAG_ALREADY_EXISTS_STOP=true; exit 21; fi
ROOT=$(docker info --format "{{.DockerRootDir}}")
FREE=$(df -Pk "$ROOT" | awk "NR==2 {print \$4}")
if test "$FREE" -lt 4194304; then echo INSUFFICIENT_DOCKER_DISK_STOP=true; exit 22; fi
echo SOURCE_BINDING=PASS
echo BUILD_FREE_DISK_KIB="$FREE"
docker buildx build --load --label org.opencontainers.image.revision="$SHA" --tag "$TAG" --file "$DIR/host/greenhouse-manager/Dockerfile" "$DIR/host/greenhouse-manager"
test "$(docker image inspect --format "{{index .Config.Labels \"org.opencontainers.image.revision\"}}" "$TAG")" = "$SHA"
docker image inspect --format "CANDIDATE_IMAGE_ID={{.Id}} CANDIDATE_IMAGE_BYTES={{.Size}}" "$TAG"
echo CANDIDATE_IMAGE_BUILT=true
echo PRODUCTION_MANAGER_UNCHANGED=true'
```

这段构建命令的退出码非 0 就 **STOP**，保留现场输出，不删除正在运行的服务或旧镜像、不盲目重试。构建产物尚未授予生产部署资格。

下面是隔离、无网络、无持久卷的功能检查。不发送任何 QR/秘密：

```bash
ssh -T "$T1_SSH" 'set -eu
TAG=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
docker run --rm --network none --read-only --entrypoint greenhouse-manager-registration "$TAG" p4-pending-readonly --help >/dev/null
echo P4_READONLY_CLI_IN_IMAGE=PASS
docker run --rm --network none --read-only --entrypoint greenhouse-manager-pairing "$TAG" import-payload --help >/dev/null
echo QR_PAYLOAD_IMPORT_CLI_IN_IMAGE=PASS
docker run --rm --network none --read-only --entrypoint python "$TAG" -c '"'"'import inspect; from greenhouse_manager.runtime.registration import RegistrationRegistry; from greenhouse_manager.runtime.n3w_simplified_pairing import SimplifiedPairingCoordinator; assert callable(getattr(RegistrationRegistry,"pending_import_guard",None)); assert "pending_import_guard" in inspect.getsource(SimplifiedPairingCoordinator.import_setup_secret); print("PENDING_EXPIRY_AT_USE_SOURCE_IN_IMAGE=PASS")'"'"'
echo NO_LIVE_MANAGER_MUTATION=true'
```

该检查只证明候选镜像中存在相应 CLI 和源码保护入口，**不能替代**运行真实 pending/SQLite/IPC 的隔离集成测试，也不证明 T1 正在运行候选镜像。Dockerfile 的底层镜像 tag、依赖范围仍可漂移；必须保留本次构建产物的完整 image ID 与受控镜像快照，并补做备份恢复演练才能申请 Manager service-only 部署。

```text
BUILD_SCOPE=NEW_IMAGE_ONLY
DEPLOY_SCOPE=NONE
REAL_DATABASE_MOUNTS=NONE
REAL_SECRET_MOUNTS=NONE
REAL_BROKER_RECREATE=false
P4_REAL_BOARD_FIRST_BOOT=false
STOP_AFTER_SYNTHETIC_IMAGE_PROBE=true
```
