# N3-W P4 Manager 一致性冷备份与隔离恢复演练

## 状态与用途

- 这是 **Draft PR #540 源码包**，不能因 CI PASS 直接视为 T1 生产备份完成。
- 在 P4 Manager 正式替换之前，保护三个独立可写 bind 源（registration、n3w、relay keys），以及保留已经私有归档的原 Manager 运行配置与旧镜像。
- 本工具 **不会** 停止、启动、重启、删除或创建 Manager/Broker 容器，不会修改 Broker 或板卡，不会把秘密/真实 Source 路径打印到终端。
- `preflight`：只读检查生产 Manager 身份/配置/挂载与旧备份的精确一致、Broker 运行与双网络/端口映射、其他运行容器对三个 RW 来源无重叠可写挂载。
- `capture --permit-cold-copy`：仅在 *相同原 Manager 容器已停止*、Broker 仍在运行、未发现其他容器共享可写来源、全部三个 SQLite 主库经 `fuser` 未发现打开者后，在 root 私有目录新建独立 cold-snapshot。复制整个可写目录，包括将来可能存在的 -wal/-shm 和所有 relay key 文件。
- 生成所有复制文件的 SHA256、mode、UID/GID 私有清单。将 cold-snapshot 复制到第二个 *隔离恢复* 目录，校验二者的完整清单一致，并在隔离恢复目录中对三个 SQLite 库运行 `PRAGMA integrity_check`。任何检查失败即 STOP，不会恢复覆盖生产源。

## 操作前已确认（实际 T1 证据）

- PR #538 exact head = `3d86d6bfaf361dc3a3d7295d046f541a544d552d`，本地 T1 新镜像 linux/arm64 构建与隔离功能测试 PASS，生产 Manager 尚未升级。
- 当前 Manager 为旧镜像，运行在 `host` 网络，零 Docker port publications；Broker 的两个网络与单一 8883 映射必须不变。
- 已有 root-only 原 Docker inspect 与旧 Manager image `docker save` tar + SHA256，且 SHA256 和私有权限均 PASS。
- 三个独立宿主机 RW 来源、三个 RO secret 来源均存在，另一个运行中容器共享可写来源计数 = 0。
- relay-keys 的 *容器内路径* 嵌套，但宿主机来源 **不在 n3w 原来源目录内**。因此需要单独复制第三处可写源，不允许通过复制 n3w 父目录代替。
- 上述通过不证明宿主机 systemd、cron 或其他进程不会写 DB；`fuser -s` 只能检测检查时仍打开文件的进程。

## 开发与测试

```bash
python3 -m compileall -q tools/execution_packages/n3w/p4_manager_cold_backup
python3 -m unittest discover -s tools/execution_packages/n3w/p4_manager_cold_backup -p 'test_*.py' -v
```

CI 只用合成数据库/密钥，无 T1 SSH、实板、真实凭据、Broker 连接或真实数据库复制。

## 正式 T1 使用限制

必须先在 GitHub CI 全部通过、完成独立源码复核并完成受控停写预执行审批。不得自行套用下面的命令立即停止现有 Manager。

`preflight` 命令可以在服务正常运行时执行：

```bash
python3 cold_snapshot.py preflight --private-root /root/n3w-p4-manager-rollback-prep-<private-suffix>
```

真正的 `capture` 只在**额外的、明确授权的停写执行窗口**内，外部执行计划已经确认如何安全恢复旧 Manager、如何排除宿主机其他写入者、如何控制传输期间的服务空档、如何验证身份数和 replay 高水位后才执行：

```bash
python3 cold_snapshot.py capture --private-root /root/n3w-p4-manager-rollback-prep-<private-suffix> --permit-cold-copy
```

注意：工具只验证旧镜像、绑定来源和冷拷贝/隔离恢复的底层完整性，不代替业务语义上的旧五身份、配对服务稳定性、Broker 运行态 TLS、节点通信连续性验收。`--permit-cold-copy` 也不是允许停止生产服务的授权。

## 本阶段禁止

- `docker stop`、`docker rm`、`docker compose up -d`、Broker 重启、实板首次正常启动。
- 在 Manager 仍运行时直接 `cp` 三个 SQLite 主库；不能用三个分别执行的 online sqlite3.backup 认定多库同一个恢复节点。
- 使用旧版 `t1_backup.py` 代替此 P4 独立注册库 + relay-keys 的冷备份。
- 把 `manager-inspect-private.json`、宿主机真实 Source、密钥、证书、数据库内容或备份本体上传公开 GitHub/聊天。
- 在备份或隔离恢复证据不足时替换生产 Manager。

## 生产执行前还需独立核对

1. T1 宿主机 Python 3.11+、权限/工具及根目录剩余空间；秘密备份目录是否仅 root 0700、文件 0600。
2. 从 `docker inspect` 原启动配置生成可恢复的旧版 Manager 单服务重建命令并在无业务数据的环境演练；不能把 Docker inspect 的 JSON 文件本身当作可直接 `docker run` 的配置。
3. 管理器停写期间 Broker 保持可用；若 Manager 与 MQTT 连接中断影响监测数据必须设定允许窗口和恢复观察预算。
4. 备份之后，必须核对业务层真实历史五身份与凭据/replay 高水位；仅 SQLite `integrity_check` 不证明业务语义正确。
5. 停写冷备份完成后，应明确何时恢复旧 Manager，以及在何时切换为候选新镜像，避免无意延长停机窗口。

STOP 点：本 PR 只做到 **源码/模拟测试、可见 preflight**，正式生产数据冷拷贝和运行态部署均需后续独立明确控制。

## 2026-10-09 冷备份源码 R2 与 T1 环境状态

T1 操作者已经在旧 `6f0cc209...` 工具版本上执行 `preflight` 并输出：

```text
BACKUP_EXECUTOR_EXACT_SOURCE=PASS
BACKUP_EXECUTOR_SYNTAX=PASS
CURRENT_MANAGER_IDENTITY_AND_MOUNTS=PASS
BROKER_RUNNING=PASS
OTHER_RUNNING_CONTAINER_WRITERS=NONE_DETECTED
COLD_BACKUP=NOT_STARTED
```

**该 PASS 只对上一次所执行的文件及当时 T1 状态有效。** 后续源码审查新增保护，使版本已改变，T1 原 `p4_cold_snapshot.py` 需要在真正采集之前重新校验 exact Git Blob 并更新；不得把旧版 `preflight` 冒充新版本的 `capture` 授权。

新保护点：

- 在复制前/后以及隔离恢复完成后，各自重新读取三个**真实源目录**的完整文件清单和 SHA256/UID/GID/mode，阻止备份窗口内数据发生变化却宣称 PASS。
- 对三个 SQLite 主库及存在的 `-wal`、`-shm` sidecars 分别检查文件占用状态，任何 `fuser` 模糊退出或文件占用均 STOP。
- 在复制前按源文件总字节数做保守空间判断（至少约三份数据再加 64MiB 余量）。
- 在隔离恢复 SQLite `integrity_check` 后，再次比较恢复目录文件清单，确保检验本身没有偷偷修改恢复内容。
- 保持旧镜像、旧容器不可删除不可重建；保留 Broker 双网络、8883 publication 与 T1 Manager 生产容器配置校验。

**三段式生产工作流（必须按顺序）：**

A. 只读部署前证据：host Python 版本及 SQLite 版本、`docker inspect` 精确旧容器 restart policy、host systemd 独立守护任务、根目录剩余空间、Docker CLI / `cp` / `fuser`，并再次比对新候选镜像和旧镜像的来源与私有归档；不得打印 secret 或 RW Source 路径。

B. 单次旧 Manager 冷备份窗口（尚未授权）：先固定一次真实业务指标（旧五身份、凭据、replay 高水位），然后 **仅停止旧 Manager**、保持 broker 与双网络不变。证明确认所有写入者已停后，运行已固定、源码 CI PASS 的 `capture`，对私有冷副本及隔离恢复副本完成 SHA256 和三个库 `integrity_check`。**无论 capture 成功还是失败，都以不删除原 Manager 容器、使用原容器启动为首选恢复路径；只有旧 Manager 经运行态验证恢复之后才结束这一窗口。** 如果出现失败且启动不能成功，保留 T1 现场用于受控回退，不自动清库或重建 Broker。

C. 独立的新 Manager 升级窗口（尚未授权）：先有可逆的 exact original container create spec 重建方案与演练、候选 P4 镜像的同一绑定、业务层历史身份/replay 高水位回归检测、Broker 连接与健康观察预算，才能替换生产 Manager。**绝不将 B 阶段成功视为 C 阶段已经授权或完成。**

阶段 A 仍可继续只读执行；阶段 B/C 需要额外的外部脚本与批准，任何原 Manager 的 `docker stop`、`docker rm`、`docker rename`、`docker start` 都由受控执行包负责，不应依赖手动拼接命令。

## 2026-10-09：T1 主机预检通过与受控停写窗口源码

最新 T1 操作者真实结果：

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

**含义**：T1 宿主 Python 版本满足 3.11+；根分区空间足以继续本轮候选小数据集检查；Manager 原容器带 `unless-stopped`，明确人为 `docker stop` 后可从 `docker start` 恢复原容器；通过此前数据检查确认其他正在运行的容器无 RW Source 重叠。列出的 3 个 systemd 单元属于 Broker，不能由此证明“没有任何其它宿主机进程写库”，也不能据此自行停止 Manager。

此次额外加入了 `controlled_window.py`：源码层两阶段 `preflight` 和需要显式标志的 `execute`。它只控制**原来的** Manager 容器：先精确比对 T1 私有 Docker inspect 与 Manager 镜像、挂载、Manager 原 restart policy、Broker 双网络端口；停止原 Manager 后运行新版 `cold_snapshot.py`，发生复制异常或 Docker stop 部分失败时会尝试在 `finally` 恢复**原容器**，核对原 Manager 连续运行及 Broker StartedAt/重启计数未变化。绝不 `docker rm` 原容器，不操作 Broker。还会在复制结束后检查 Manager 仍处于停止状态，防止异常监督程序抢先重启。

注意：`finally` 对进程存活期间抛出的异常有用，但**无法对断电、内核崩溃、SIGKILL、Docker 守护进程停摆等事件承诺自动恢复**。因此正式停写执行前还须配置能独立于 SSH 存活的系统任务和失败监测，以及手工恢复的独立只读核查/操作计划；不能把 Python `finally` 当作全部事故应急机制。

**当前状态：脚本只存于 GitHub Draft PR #540；尚未在 T1 执行更新后的停写 wrapper；生产当前运行状态未改变。** 下一动作仅限下载并绑定 exact 工具源到原私有目录的新子目录，执行 `controlled_window.py preflight` 只读检查。不得运行 `execute`、`--permit-manager-stop`、任何 `docker stop/start/rm` 或真实数据冷复制。

正式受控窗口在 PR #540 源码独立复核通过、全部 CI 通过、旧容器原状恢复计划经过测试且有现场明确执行窗口后方可授权。

## 2026-10-09：R4 独立 systemd 失败恢复保护（源码及模拟测试）

T1 操作者已在此前 R3 两个脚本上完成真实只读预检：

```text
REVIEWED_BACKUP_SOURCE_BINDING=PASS
ORIGINAL_MANAGER_STOP_RECOVERY_PREFLIGHT=PASS
BROKER_PERSISTENCE_PREFLIGHT=PASS
CURRENT_MANAGER_IDENTITY_AND_MOUNTS=PASS
BROKER_RUNNING=PASS
OTHER_RUNNING_CONTAINER_WRITERS=NONE_DETECTED
REVIEWED_BACKUP_PREFLIGHT=PASS
MANAGER_STOP_NOT_EXECUTED=true
CONSISTENT_DATA_BACKUP=NOT_STARTED
```

R3 结果对当时版本有效，但**不等于已安装独立恢复保障**。补充：
- `emergency_resume.py`：另一个独立 Python 进程，使用 root 私有原 Docker inspect 严格比对当前容器 ID、原镜像、原配置，才允许检查或尝试 `docker start` **原来的 Manager**。运行后必须连续观察多次原容器运行，并复核 Broker 没有重启。禁止创建/删除/重命名容器、禁止更改 Broker。
- `systemd_recovery_unit.py`：仅在内存生成可复核的 systemd 单次执行 unit 文字，`preflight` 只显示状态和 SHA256，**不会在 /etc 写文件，也不会注册/启动服务**。
- Unit `ExecStart` 调用受控旧 Manager 停写窗口，`ExecStopPost` 独立调用恢复脚本；`TimeoutStartSec=240`，`TimeoutStopSec=90`，`Restart=no`，无 `[Install]` 区段以防误设开机自动执行。只在外部批准的操作窗口以手动一次性启动方式运行；**不得** `systemctl enable`。
- 此组合可在 SSH 断开或主脚本被 systemd 超时结束后尝试恢复原容器；仍不能承诺处理掉电、Docker 守护进程不可用、systemd PID 1 异常、磁盘损坏，也不能取代明确的人工恢复指引与必要时现场检查。

下阶段仅允许：从 PR #540 的**新固定 HEAD** 把 `cold_snapshot.py`、`controlled_window.py`、`emergency_resume.py`、`systemd_recovery_unit.py` 精确绑定到同一个 **r4 root 私有新目录**，通过 `python3 -B ... systemd_recovery_unit.py preflight`、`controlled_window.py preflight`、`cold_snapshot.py preflight`，再从 systemctl 只读确认 `docker.service`/systemd 可用。禁止在这一步安装、启动单元或停止 Manager。

若后续真要执行旧 Manager 备份窗口，必须**先**独立复核 unit 的时序、写入者排除、业务身份/replay 高水位基线，明确短暂 Manager 服务中断预算和失败恢复时的人工操作路径。任何 `docker stop`、`systemctl start ...cold-backup.service`、`cold_snapshot.py capture` 仍是下一道独立现场控制门，不受这里的只读预检授权。
