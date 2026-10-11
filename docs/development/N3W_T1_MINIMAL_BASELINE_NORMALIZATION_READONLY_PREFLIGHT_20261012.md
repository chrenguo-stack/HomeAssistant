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
