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
