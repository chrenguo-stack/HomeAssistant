# T1 S0 R2 — Mac Terminal 只读取证：Docker JSON 全容器、卷与 systemd 真实数据来源

> 原 S0 R1 2026-10-10 08:09 报告中六个容器的 `docker inspect --format` **全部失败**；不能用其填充任何宿主数据目录清理列表。此 R2 改用容器 JSON，在远端 Python 内存中仅提取白名单字段。**不读取、打印或提交** Config.Env、密钥、证书内容、数据库内容或日志正文。

```text
TASK=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY
CURRENT_ROUTE=SOFTWARE_REDEPLOY_PRESERVE_ARMBIAN
LIVE_RUNTIME_MUTATION=false
EVIDENCE_WRITE=MAC_LOCAL_LOG_ONLY
NO_DOCKER_STOP_RM_PRUNE=true
NO_SYSTEMD_START_STOP_DISABLE=true
NO_CERT_OR_SECRET_READ=true
NEXT_OUTPUT=N3W_T1_SOFTWARE_OWNERSHIP_R2_*.txt
```

## 直接复制到 Mac Terminal

```bash
set -o pipefail
printf '请输入 T1 SSH 目标（用户名@地址或 SSH 别名）：'
IFS= read -r T1_SSH
if [ -z "$T1_SSH" ]; then
  echo "STOP: 未提供 SSH 目标"
else
  LOG="$HOME/N3W_T1_SOFTWARE_OWNERSHIP_R2_$(date +%Y%m%d_%H%M%S).txt"
  ssh -o ConnectTimeout=12 "$T1_SSH" 'bash -s' <<'T1_READONLY' | tee "$LOG"
set -eu
python3 - <<'PY_REMOTE'
import json
import subprocess

def call(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if p.returncode:
        print("COMMAND_FAILED=" + " ".join(args[:3]) + " RC=" + str(p.returncode))
        raise SystemExit(2)
    return p.stdout

def output(key, value):
    print(key + "=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")))

print("=== S0 R2 JSON INSPECT BEGIN ===")
ids = [x.strip() for x in call("docker", "ps", "-aq", "--no-trunc").splitlines() if x.strip()]
print("CONTAINER_COUNT=" + str(len(ids)))
if not ids:
    raise SystemExit("CONTAINER_LIST_EMPTY_STOP")

volume_owners = {}
for cid in ids:
    obj = json.loads(call("docker", "inspect", "--type", "container", cid))
    if len(obj) != 1 or obj[0].get("Id") != cid:
        raise SystemExit("CONTAINER_ID_BINDING_FAILED_STOP")
    c = obj[0]
    labels = (c.get("Config") or {}).get("Labels") or {}
    host = c.get("HostConfig") or {}
    state = c.get("State") or {}
    networks = (c.get("NetworkSettings") or {}).get("Networks") or {}
    mounts = c.get("Mounts") or []
    name = str(c.get("Name", "")).lstrip("/")
    output("CONTAINER", {
        "name": name,
        "id": c.get("Id"),
        "image_id": c.get("Image"),
        "status": state.get("Status"),
        "running": state.get("Running"),
        "restart_policy": (host.get("RestartPolicy") or {}).get("Name"),
        "network_mode": host.get("NetworkMode"),
        "networks": sorted(networks.keys()),
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_service": labels.get("com.docker.compose.service"),
        "compose_files": labels.get("com.docker.compose.project.config_files"),
        "compose_workdir": labels.get("com.docker.compose.project.working_dir"),
        "mount_count": len(mounts),
    })
    for m in mounts:
        data = {
            "container": name,
            "container_id": cid,
            "type": m.get("Type"),
            "source": m.get("Source"),
            "destination": m.get("Destination"),
            "rw": m.get("RW"),
            "volume_name": m.get("Name"),
        }
        output("MOUNT", data)
        if m.get("Type") == "volume" and m.get("Name"):
            volume_owners.setdefault(m["Name"], []).append(name)

volume_names = [x.strip() for x in call("docker", "volume", "ls", "-q").splitlines() if x.strip()]
print("VOLUME_COUNT=" + str(len(volume_names)))
for volume in volume_names:
    objs = json.loads(call("docker", "volume", "inspect", volume))
    if len(objs) != 1 or objs[0].get("Name") != volume:
        raise SystemExit("VOLUME_ID_BINDING_FAILED_STOP")
    obj = objs[0]
    output("VOLUME", {
        "name": volume,
        "driver": obj.get("Driver"),
        "mountpoint": obj.get("Mountpoint"),
        "referenced_by_existing_containers": sorted(volume_owners.get(volume, [])),
    })

units = [
    "n3w-p4-fresh-manager-deploy.service",
    "n3w-p4-fresh-manager-r3-deploy.service",
    "n3wfc4-broker-activation.service",
    "n3wfc4-broker-ingress-guard.service",
    "n3wfc4-broker-certificate-lifecycle.service",
    "n3wfc4-broker-certificate-lifecycle.timer",
]
for unit in units:
    p = subprocess.run(
        ["systemctl", "show", unit, "--property=Id,LoadState,ActiveState,UnitFileState,FragmentPath,DropInPaths"],
        capture_output=True, text=True, timeout=15,
    )
    if p.returncode:
        output("UNIT_FAILED", {"name": unit, "rc": p.returncode})
        continue
    d = dict(row.split("=", 1) for row in p.stdout.splitlines() if "=" in row)
    output("UNIT", d)

print("=== S0 R2 COMPLETE ===")
print("T1_MUTATION=false")
print("CONTAINER_DELETE=false")
print("VOLUME_DELETE=false")
print("HOST_PATH_DELETE=false")
PY_REMOTE
T1_READONLY
  STATUS=$?
  echo "SSH_OR_REMOTE_EXIT_CODE=$STATUS"
  echo "LOCAL_REPORT=$LOG"
fi
```

## 验收和 STOP

- `S0_R2=PASS` 仅当每个当前 Docker container 都有一个包含真实完整 ID/name 的 `CONTAINER`，每个挂载有 `MOUNT`，每个卷有 `VOLUME`，且返回码 0；未在主机上进行 mutation。
- `VOLUME.referenced_by_existing_containers=[]` **不自动表示允许删除**；可能仍有关联外部流程/编排 authority，需下一阶段核查。
- `MOUNT.source` 精确路径可能属于生产私有目录。报告可以上传当前私有对话，但不得把原始输出、真实宿主路径或完整容器 ID 直接提交公共 GitHub。
- 任何 `COMMAND_FAILED`、Docker CLI 不可用、Python 不可用、无法取得 metadata、T1 身份变化、两 HA 共享 mount 等情况均保留证据并 STOP，不做猜测或尝试删除。
- 本次运行后由高阶模型将每个 `CONTAINER/ MOUNT/ VOLUME/ UNIT` 归为 `N3W_EXCLUSIVE`、`SHARED_OR_UNKNOWN` 或 `PRESERVE`，制定有 exact IDs 和 source paths 的**私有清理清单**，再提交仅脱敏的决策/状态文档。

```text
AFTER_PASS=CLASSIFY_EXACT_CLEAN_TARGETS
AUTO_DELETE_AFTER_PASS=false
S0_R2_PREEXECUTION_STATUS=AWAITING_USER_MAC_TERMINAL_OUTPUT
```
