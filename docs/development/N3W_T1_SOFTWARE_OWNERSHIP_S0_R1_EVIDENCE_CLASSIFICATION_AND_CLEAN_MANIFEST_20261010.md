# N3-W T1 保留 Armbian 的软件清洁重装 — S0 R1 证据分类与精确清理候选清单（2026-10-10）

## 决策摘要

上传的 T1 只读输出 `N3W_T1_SOFTWARE_OWNERSHIP_20261010_080909.txt` 于 2026-10-10 08:09:13 +08:00 采集。本地原件 SHA256: `74127af80fec997a51717cf08c72879813e7885b6a9ff99a76c999783121132f`。**原件没有提交到 GitHub**；GitHub 只存去敏感信息的分析结论。

```text
CURRENT_ROUTE=SOFTWARE_STACK_CLEAN_REINSTALL_ON_EXISTING_ARMBIAN
OS_REINSTALL=false
DISK_ERASE=false
T1_MUTATION=false
CONTAINER_REMOVAL=false
DATA_DELETION=false
S0_R1_CONTAINER_LIST=PASS_6
S0_R1_CONTAINER_DETAIL_INSPECT=FAIL_6_OF_6
S0_R1_VOLUME_LIST=PASS_46_ANONYMOUS
S0_R1_EXACT_VOLUME_OWNER=UNVERIFIED
S0_R1_EXACT_HOST_BIND_SOURCES=UNVERIFIED
S0_R1_COMPOSE_LABELS=UNVERIFIED
S0_R1_NETWORK_MEMBERSHIP=PASS_FOR_REPORTED_RUNTIME
S0_R1_RELATED_SYSTEMD_UNIT_NAMES=PASS
S0_R1_EXACT_DELETE_MANIFEST=BLOCKED_MISSING_MOUNT_AND_OWNER_BINDING
LIVE_DELETE_READY=false
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY
```

这不是“已证实 6 个容器坏了”，而是 **6 次 Docker inspect 模板读取失败**。上传的管道没有捕获详细 stderr，根因目前为 TBD；不能将诊断脚本失败升级为产品故障，更不能把 Docker 卷或宿主目录猜成可删项。下一轮直接读取 `docker inspect` JSON、用已安装 Python 只解析白名单字段，同时输出准确退出状态。

## 1. 已证明的容器名和运行状态；仅作为清理候选

| EXACT 容器名 | 实测镜像标识 | 实测状态 | 分类与动作 | FULL ID / Compose / HOST RW PATH |
|---|---|---|---|---|
| `greenhouse-manager` | `b806e7c8b97c`（ps 显示短镜像标识，非 digest） | Up 13 hours | **N3W 候选**：目标新装 Manager，待 exact ID/挂载校验 | 未证明 |
| `greenhouse-manager-p4-shadow` | `3967b369836f`（短标识） | Created | **旧 P4 影子候选**：待 exact ID/卷排他性校验 | 未证明 |
| `n3wfc4-broker-1` | `local/mosquitto:pr260-source-exact` | Up 3 days | **N3W Broker 候选**：要建立新 CA/TLS/DynSec；旧 Broker 是否被 HA/其他业务共享须验明 | 未证明 |
| `fc4-homeassistant` | `local/homeassistant:pr260-exact-c1e5f0147f4c` | Up 3 days | **归属待决**：在 N3W 网络，不能据此断言是独占温室 HA | 未证明 |
| `homeassistant` | 同一镜像 tag | Up 3 days | **默认保留**：在 host 网络，可能另有生产 HA 数据 | 未证明 |
| `recipes-broker-1` | `local/mosquitto:pr260-source-exact` | Exited (0) 13 days ago | **默认保留**：疑似非 N3W 服务，非清理目标 | 未证明 |

**FULL-ID 映射不可从日志证明**：虽然另有六条 `INSPECT_FAILED=<full id>`，其格式化输出完全失败，没有与 name 绑定的成功 inspect 记录；不允许按列表位置把 full ID 推断到容器名上。

### 2. Docker network 只读证明

| 网络 | 项目标签 | 实测加入的容器 | 清理决策 |
|---|---|---|---|
| `host` | 系统共享网络 | `greenhouse-manager`, `homeassistant` | 永远不是可删网络 |
| `n3wfc4-private` | `n3wfc4` | `n3wfc4-broker-1`, `fc4-homeassistant` | N3W 有效双网络之一；旧新切换范围核实前不得移除 |
| `n3wfc4-services` | `n3wfc4` | `n3wfc4-broker-1` | N3W 有效双网络之一；不得提前删除 |
| `corrected-successor-mqtt-runtime-20260827-01_default` | 同名项目 | 无连接 | 历史孤立网络候选，但真实网络使用权、宿主路径不明，保留 |
| `greenhouse-pr260-hostloopback-v13r4r2-20260806t015504z-f147d422` | 未显示项目标签 | 无连接 | 历史网络候选，仅归档、不删除 |
| `greenhouse-pr260-private` | 未显示项目标签 | 无连接 | 历史网络候选，仅归档、不删除 |
| `bridge` / `none` | 系统基础网络 | 无连接 | 永不批量删除 |

上传记录没有证明 `homeassistant` 与 `fc4-homeassistant` 的挂载目录是否重叠，也没有证明两者谁使用 Broker；上表的 network membership 只证明网络连接。

### 3. systemd 服务精确名称

| Unit | 实测 enable 状态 | 清理分类 |
|---|---|---|
| `n3w-p4-fresh-manager-deploy.service` | static | 旧 P4 部署 unit，未来清理候选，先确认 FragmentPath 与 owner |
| `n3w-p4-fresh-manager-r3-deploy.service` | static | 同上 |
| `n3wfc4-broker-activation.service` | enabled | N3W Broker 新装必须重新收敛的 unit，不能不先核对而删除 |
| `n3wfc4-broker-ingress-guard.service` | enabled | 8883 安全入口 guard，未验证新 Guard 前保持现行安全边界 |
| `n3wfc4-broker-certificate-lifecycle.service` | static | 新证书生命周期候选替换，先核对 FragmentPath |
| `n3wfc4-broker-certificate-lifecycle.timer` | enabled | 新证书生命周期 timer 候选替换，先核对 enabled/status/路径 |

`ssh.service`、`NetworkManager.service`、`docker.service` 和 Armbian OS 不属于清理目标。

### 4. 数据目录、匿名卷和监听端口

- `docker volume ls` 实际列出 **46 个 64 位匿名卷名称**，但没有一条成功的容器 Mount 或 Docker 卷 owner 对应关系；因此 `DELETE_VOLUME_SET=EMPTY`（未核准），不是“46 个待删卷”。
- 真实的 `/var/lib/...`、`/opt/...`、`/etc/...` 具体宿主目录尚无成功映射，`DELETE_HOST_PATH_SET=EMPTY`（未核准）。产品文档里的 Manager 容器内 3 RW/3 RO 目标路径不能替代宿主运行时 Source 证据。
- TCP 8883、TCP 47112、UDP 47111、TCP 8123（IPv4 和 IPv6）在报告中 LISTEN；`ss` 未显示 PID/进程，**端口监听与具体容器 owner 尚未绑定**。不据此删除端口/防火墙规则。
- 根分区 14G、已用 7.8G、可用 5.7G；这是当时容量事实，不代表清理安全。

## 5. 精确的待核实删除候选清单，不是删除指令

```text
CONTAINER_DELETE_CANDIDATES_NOT_APPROVED=
  greenhouse-manager
  greenhouse-manager-p4-shadow
  n3wfc4-broker-1

CONTAINER_HOLD_UNTIL_EXACT_OWNER_PROVEN=
  fc4-homeassistant

CONTAINER_PRESERVE_BY_DEFAULT=
  homeassistant
  recipes-broker-1

SERVICE_REPLACE_CANDIDATES_NOT_APPROVED=
  n3w-p4-fresh-manager-deploy.service
  n3w-p4-fresh-manager-r3-deploy.service
  n3wfc4-broker-activation.service
  n3wfc4-broker-ingress-guard.service
  n3wfc4-broker-certificate-lifecycle.service
  n3wfc4-broker-certificate-lifecycle.timer

DELETE_DOCKER_VOLUME_SET=UNDETERMINED
DELETE_HOST_DIRECTORY_SET=UNDETERMINED
DELETE_NETWORK_SET=UNDETERMINED
CLEAN_MANIFEST_CERTIFIED=false
```

“准确到容器、数据目录和服务”的**可执行**清理清单未形成，原因是输入的 `docker inspect` 六次全部失败，并非用户授权不足或应另建回退方案。下一门只读补充：容器完整 ID → Compose project/service/config_files → Mount Type/Source/Destination/RW/Name → Docker volumes 的引用容器 → Systemd FragmentPath 与 service status；所有文件路径只留在私有现场日志，公共 GitHub 只写去敏感分类。

## 6. 下一 ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY
INPUT=FRESH_T1_READONLY_JSON_INSPECT_REPORT
METHOD=DOCKER_JSON_TO_PYTHON_SELECTIVE_WHITELIST_NOT_GO_TEMPLATE
NO_RUNTIME_MUTATION=true
REPORT_SUCCESS=ALL_6_INSPECT_SUCCEEDED_AND_EACH_MOUNT_CLASSIFIED
STOP_IF=ANY_INSPECT_FAILURE_OR_IDENTITY_AMBIGUITY
AFTER_PASS=EXACT_CLEAN_MANIFEST_AND_ONE_TIME_SCOPE_CONFIRMATION_DESIGN
AUTO_DELETE=false
```

新会话应运行版本化 S0 R2 只读采集，修复证据缺口，随后可独立核准具体清理对象。**禁止从本 S0 R1 文档直接执行容器/卷/目录删除**。
