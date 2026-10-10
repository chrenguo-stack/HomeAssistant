# N3-W T1 软件环境全新部署：S0 实际服务归属及数据清理清单前置核查

## 一、权威和当前停止点

```text
ROUTE=T1_SOFTWARE_STACK_CLEAN_REDEPLOY_PRESERVE_ARMBIAN
AUTHORITY=docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md
S0_GATE=N3W_T1_SOFTWARE_OWNERSHIP_READONLY_EVIDENCE_AND_CLEAN_TARGET_DRY_RUN
S0_RESULT=AWAITING_USER_REAL_T1_RUNTIME_INVENTORY
HOST_OS_REINSTALL=false
HOST_SYSTEM_DISK_ERASE=false
PRESERVE=ARMBIAN_NETWORKMANAGER_SSH_DOCKER_ENGINE
REMOVE_UNKNOWN_CONTAINERS=false
REMOVE_DOCKER_VOLUMES_BY_GLOB=false
REMOVE_SHARED_HOME_ASSISTANT=false
REMOVE_RECIPES_BROKER=false
R4_B1I1_ROLLBACK_DEVELOPMENT=false
S0_T1_MUTATION=false
S0_GITHUB_PRIVATE_SECRETS=false
```

先前真实 SSH 观察仅确认容器名称和状态（`greenhouse-manager`, `greenhouse-manager-p4-shadow`, `n3wfc4-broker-1`, `recipes-broker-1`, `fc4-homeassistant`, `homeassistant`）。**未确认**哪一套 HA 属于温室、其他服务数据是否共用 Broker、Docker 命名卷的实际归属；不能推断当前现场与那份观察完全相同。

## 二、S0 只读采集要求

由用户在 Mac Terminal 运行，SSH 目标须为实际 T1；只读取 Docker 容器标识/标签/六挂载来源、网络和端口、Docker 卷名、具有温室关键字的 systemd unit，以及端口监听。禁止读取 `docker inspect` 的 `Config.Env`、密钥、证书内容、账号密码、业务数据库内容、完整日志。

```sh
set -o pipefail
printf '请输入 T1 SSH 目标（用户名@T1地址或已配置SSH别名）：'
IFS= read -r T1_SSH
if [ -z "$T1_SSH" ]; then
  echo "STOP: T1 SSH 目标为空"
else
  LOG="$HOME/N3W_T1_SOFTWARE_OWNERSHIP_$(date +%Y%m%d_%H%M%S).txt"
  ssh -o ConnectTimeout=12 "$T1_SSH" 'bash -s' <<'T1_READONLY' | tee "$LOG"
set -u
echo "=== S0 BEGIN ==="
date -Is
hostname
echo "=== DOCKER ROOT ==="
docker info --format '{{.DockerRootDir}}' 2>/dev/null || true
echo "=== CONTAINERS AND EXACT OWNERSHIP ==="
docker ps -a --format '{{.Names}} | {{.Image}} | {{.Status}}'
for id in $(docker ps -aq --no-trunc); do
  docker inspect --type container --format 'CONTAINER={{.Name}} ID={{.Id}} IMAGE={{.Image}} STATE={{.State.Status}} RESTART={{.HostConfig.RestartPolicy.Name}} NETMODE={{.HostConfig.NetworkMode}} PROJECT={{index .Config.Labels "com.docker.compose.project"}} SERVICE={{index .Config.Labels "com.docker.compose.service"}} CONFIG={{index .Config.Labels "com.docker.compose.project.config_files"}} WORKDIR={{index .Config.Labels "com.docker.compose.project.working_dir"}} NETWORKS={{range $name, $network := .NetworkSettings.Networks}}{{$name}},{{end}} PORTS={{json .NetworkSettings.Ports}} MOUNTS={{range .Mounts}}[{{.Type}}|{{.Source}}|{{.Destination}}|RW={{.RW}}|{{.Name}}]{{end}}' "$id" || echo "INSPECT_FAILED=$id"
done
echo "=== DOCKER VOLUMES ==="
docker volume ls --format '{{.Name}}'
echo "=== DOCKER NETWORKS ==="
docker network ls --format '{{.ID}} | {{.Name}} | {{.Driver}}'
for id in $(docker network ls -q); do
  docker network inspect --format 'NETWORK={{.Name}} PROJECT={{index .Labels "com.docker.compose.project"}} CONTAINERS={{range .Containers}}{{.Name}},{{end}}' "$id" || true
done
echo "=== RELATED SYSTEMD UNITS ==="
systemctl list-unit-files --type=service --no-pager --no-legend 2>/dev/null | grep -Ei 'n3w|fc4|greenhouse|mosquitto|broker|homeassistant|recipe|certificate' || true
systemctl list-unit-files --type=timer --no-pager --no-legend 2>/dev/null | grep -Ei 'n3w|fc4|broker|certificate' || true
echo "=== RELATED RUNNING SERVICES ==="
systemctl list-units --type=service --all --no-pager --plain 2>/dev/null | grep -Ei 'n3w|fc4|greenhouse|mosquitto|broker|homeassistant|recipe|certificate' || true
echo "=== RELEVANT LISTENING PORTS ==="
ss -H -lntu 2>/dev/null | grep -E ':(8883|47111|47112|8123|1883)[[:space:]]' || true
echo "=== STORAGE SPACE ==="
df -h / /var/lib/docker 2>/dev/null || true
echo "=== S0 COMPLETE ==="
echo "T1_MUTATION=false"
echo "CONTAINER_REMOVAL=false"
echo "DATA_DELETION=false"
T1_READONLY
  CODE=$?
  echo "SSH_EXIT_CODE=$CODE"
  echo "REPORT=$LOG"
fi
```

本工具只在 Mac 本地写入 `$LOG`。远端只读，无新建、停止、删除或重启。SSH 与 Docker 操作若发生命令错误，应如实留在报告中，不因日志缺失推断业务故障。

## 三、S1/S2 下一输出（不可先行销毁）

根据 S0 的容器完整 ID + Compose 标签 + 挂载宿主来源，逐项制作 `EXACT_DELETE_CANDIDATES` / `PRESERVE` / `SHARED_OR_UNKNOWN` 三类清单：

1. Manager、Manager shadow、Broker exact 容器与业务数据：证明完全属于温室后列为可清理候选，不能凭名称自动删除。
2. `fc4-homeassistant` 与 `homeassistant`：以 project/service/config_files/mount host source 决定哪一份为温室专用；没有确定前两者全部放入 `SHARED_OR_UNKNOWN`。
3. `recipes-broker-1`：默认保留；即使已经停止也不可按旧容器垃圾处理。
4. Docker network 和 volume：必须证明无其他服务共享才可删除。绝不能使用 `docker system prune`、`docker compose down -v`、`--remove-orphans`。
5. systemd：只对属于新温室栈的专用 unit 作后续版本化替换；保留 Docker.service、SSH、NetworkManager 及主机全局防火墙体系。8883 ingress guard 在新 Broker 正式建立前要保持 fail-closed。
6. 建立新 TLS/CA/DynSec/Manager 业务状态时默认不迁移旧私钥、凭据和数据库；但要先确定旧 Broker 是否也服务其他项目，以及旧 HA/节点的重配影响。

完成 `S2=EXACT_TARGET_DRY_RUN` 后向用户一次性呈现具体删除对象、路径、数据丢失范围，再执行清理及全新安装；不再反复讨论旧 R4/B1I1 回退。

```text
NEXT_INPUT=N3W_T1_SOFTWARE_OWNERSHIP_*.txt
NEXT_GATE=N3W_T1_SOFTWARE_OWNERSHIP_EVIDENCE_CLASSIFICATION_AND_EXACT_CLEAN_MANIFEST
LIVE_DATA_DELETE=false
```
