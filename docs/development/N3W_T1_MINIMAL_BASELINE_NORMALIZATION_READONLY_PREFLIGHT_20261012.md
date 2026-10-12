# N3-W T1 minimal-baseline normalization read-only preflight（2026-10-12）

用户已批准：

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_BASELINE_NORMALIZATION_READONLY_PREFLIGHT_20261012_01
```

本 gate 只允许读取真实 T1 状态，不允许删除、修改、停服务、启动服务或重启。

为避免把临时 shell 当作执行合同，本轮新增 repository-versioned host executor：

```text
tools/n3w_t1_minimal_baseline_readonly_inventory.py
```

它通过 `ssh -n` 直接执行内存中的只读 Python inventory，不在 T1 创建临时文件。采集范围包括：

- Armbian / SSH / NetworkManager / Docker / Compose / 默认路由 / DNS / 时间同步 / 根分区余量；
- Docker containers / images / volumes / networks；
- 相关 systemd service/timer；
- 已知产品路径及一层 metadata；
- 1883/8883/18883/8123/47110/47111/47112 listener；
- 只读 firewall rule listing。

输出分为：

- `PRESERVE_HOST_BASELINE`
- `DELETE_PRODUCT_STATE_CANDIDATE`
- `UNKNOWN_STOP`

任何 ownership 无法证明的 Docker 对象或 firewall read failure 都进入 `UNKNOWN_STOP`，不得自动清理。

```text
READONLY_AUTHORIZATION=GRANTED
SOURCE_EXECUTOR_COMMITTED=true
CI=PENDING
T1_ACCESS_NOT_YET_EXECUTED=true
LIVE_MUTATION=false
DESTRUCTIVE_NORMALIZATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```


## Fresh live inventory result

真实 T1 read-only inventory 已执行。executor 未执行任何 mutation，未启动生产服务，board 未访问。

```text
INVENTORY_RC=2
INVENTORY_STATUS=STOP
INVENTORY_SHA256=0ad246ee33dcddf70555fcf23551c7b106f8b0edad8eb0523a24421d674f4814
MUTATION_PERFORMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

STOP 的直接原因不是宿主异常，而是首版 classifier 故意保守：

- 45 个 anonymous volume 被标记为 ownership unknown；
- Docker 默认 `bridge/host/none` 也被错误放入 unknown；
- 历史 `corrected-successor-mqtt-runtime-20260827-01_default` 网络没有进入 product candidate；
- firewall 过滤把 Docker 自身 `DOCKER-USER` framework 也混入 product candidate。

进一步对照 current repository authority 后：

1. 当前 45 个 volume 的排序名称集合 SHA256 精确等于旧 staging executor 冻结的
   `20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b`；
2. minimal-host baseline 决策已明确把这套 45-volume frozen set 列为被新架构 supersede 的旧 staging 前提，并要求后续 exact normalization；
3. `bridge/host/none` 是 Docker Engine 默认网络，属于 host baseline，必须保留；
4. `corrected-successor-mqtt-runtime-20260827-01_default` 带历史 Compose project identity，应归为历史产品网络；
5. `DOCKER-USER` chain 与 `FORWARD -> DOCKER-USER` 属 Docker framework，必须保留；只允许删除 N3WFC4 专用 ingress chain/anchors。

classifier 已按这些事实修补，新增 regression；等待 CI。无需读取 anonymous volume 内容，也不需要暴露其中可能存在的历史敏感数据。

```text
READONLY_LIVE_INVENTORY=EXECUTED
HOST_BASELINE=HEALTHY
CONTAINERS=0
IMAGES=0
VOLUMES=45_EXACT_HISTORICAL_SET
PRODUCT_NETWORKS=5
DEFAULT_DOCKER_NETWORKS=3_PRESERVE
PRODUCTION_LISTENERS=0
CLASSIFIER_REPAIR=COMMITTED
CLASSIFIER_REPAIR_CI=PENDING
DESTRUCTIVE_NORMALIZATION=false
```
