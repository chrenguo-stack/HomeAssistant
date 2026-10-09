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
