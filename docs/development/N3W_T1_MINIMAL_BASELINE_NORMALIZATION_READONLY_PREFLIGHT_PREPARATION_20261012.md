# N3-W T1 minimal-baseline normalization read-only preflight preparation（2026-10-12）

## 0. 当前结论

R1-R6 source/CI 已完成，R6 exact ARM64 三镜像证据已 CLOSED_PASS。

下一步不直接删除 T1 上的任何旧产品状态。先做一次新的 **只读现场清单**，再根据真实清单生成 exact normalization manifest。

```text
TARGET_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
GATE=N3W_T1_MINIMAL_BASELINE_NORMALIZATION_READONLY_PREFLIGHT_20261012_01
GATE_STATE=PREPARED_NOT_AUTHORIZED
T1_ACCESS=false
LIVE_MUTATION=false
DESTRUCTIVE_NORMALIZATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## 1. 为什么不能现在直接删

已知 T1 历史上仍保留过 45 个 Docker volumes，以及旧 identity、secret、Broker/Manager/HA 状态、systemd/dispatcher/guard 等产品对象。

但“45 个 volume”只是历史数量证据，不能自动等价为“这 45 个现在都可以删除”。

正式 normalization 必须依据一次 fresh read-only inventory，逐项确认：

- 当前容器、镜像、volume、network；
- product paths；
- systemd service/timer；
- NetworkManager dispatcher；
- product firewall/guard；
- MQTT / HA / pairing listeners；
- Docker root 与磁盘余量；
- SSH / NetworkManager / Docker / time sync 等宿主基础仍健康。

## 2. 只读阶段要输出什么

read-only preflight 只允许收集和分类，不允许 rm / docker volume rm / systemctl disable / iptables delete / chmod / chown。

输出必须至少分为三类：

1. **PRESERVE_HOST_BASELINE**：Armbian、SSH、NetworkManager、当前网络配置、默认路由、DNS、时间同步、Docker Engine、Compose；
2. **DELETE_PRODUCT_STATE_CANDIDATE**：确认属于温室产品、且目标 minimal baseline 不再保留的对象；
3. **UNKNOWN_STOP**：所有无法证明归属的对象。只要存在 UNKNOWN，就不得生成 destructive authorization。

## 3. normalization manifest 的安全合同

后续 exact manifest 必须绑定：

- fresh inventory SHA；
- 每个待删对象的 exact type + exact name/path；
- 删除前 expected state；
- 删除后 absence oracle；
- preserve-list；
- no-wildcard/no-glob deletion；
- Docker volume 必须逐个 exact name；
- systemd unit 必须逐个 exact name；
- filesystem path 必须逐个 absolute exact path；
- firewall/dispatcher 同样逐项绑定；
- 任何现场漂移都 STOP，不做“顺手清理”。

manifest 本身只是计划，不构成 live mutation authorization。

## 4. 下一 STOP 点

下一步需要用户单独批准 **T1 read-only inventory**。

该授权只允许读取，不允许任何删除或修改。

read-only inventory PASS 后，才生成 exact clean-baseline normalization manifest；manifest 完成后，再请求一次独立的 destructive live authorization。

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_BASELINE_NORMALIZATION_READONLY_PREFLIGHT_20261012_01

NEXT_GATE_REQUIRES_EXPLICIT_T1_READONLY_AUTHORIZATION=true
DESTRUCTIVE_AUTHORIZATION_NOT_REQUESTED_YET=true
```
