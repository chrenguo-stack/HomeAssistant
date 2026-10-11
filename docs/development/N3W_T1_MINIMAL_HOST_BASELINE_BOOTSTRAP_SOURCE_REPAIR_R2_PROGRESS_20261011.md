# N3-W T1 minimal-host fresh bootstrap R2 source repair progress（2026-10-11）

## Scope

```text
GATE=N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R2_20261011_01
R2_SCOPE=BROKER_TLS_AND_DYNSEC_FRESH_BOOTSTRAP
TARGET_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
T1_MUTATION=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## 本轮实现

新增：

```text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_broker.py
host/greenhouse-manager/tests/bootstrap/test_fresh_broker.py
```

fresh Broker source constructor 从空 candidate root 创建：

- 独立 Broker private CA；
- Broker server key/certificate；
- SAN：`mqtt.greenhouse.local`、兼容 DNS `armbian`、IPv4 loopback `127.0.0.1`；
- root-only Dynamic Security bootstrap admin secret；
- Manager / Provisioning / Home Assistant 三套独立 MQTT credential bundle；
- node credential count 固定为 0；
- private 0700/0600 inventory；
- marker/report 不输出 secret value。

Broker transport CA 与 H0/H1 System CA 保持独立，不合并 trust authority。

新增 fresh Dynamic Security source orchestration：

```text
verify credential bundle
→ apply exact default ACL
→ create provisioning role/client
→ create manager role/client
→ create homeassistant role/client
→ node credential count remains 0
```

复用已有 `service_identity_plan.py` 与 `DynsecProvisioner`，不复制 ACL 真值，不手写 Mosquitto password hash。

新增 Dynamic Security JSON audit source contract：

```text
publishClientSend=false
publishClientReceive=false
subscribe=false
unsubscribe=true

required service clients=3
required service roles=3
precreated node clients=0
precreated node roles=0
runtime admin not used by applications
```

## CI

`M2 Dynamic Security CI` 新增独立 `fresh-bootstrap-contract` job，执行 fresh TLS/DynSec source tests + Ruff。

现有真实 Broker Dynamic Security integration job保持不变，用于继续覆盖底层 DynSec API、client-id binding、rollback 等既有能力。精确 production Broker ARM64 image 上的 fresh candidate runtime matrix仍按 source design 留给 R6；R2 不提前宣称 exact-image runtime PASS。

```text
R2_SOURCE_COMMITTED=true
R2_CI=PENDING
EXACT_IMAGE_FRESH_DYNSEC_RUNTIME=NOT_YET_R6
T1_ACCESS=false
LIVE_MUTATION=false
AUTHORIZATION_03=NOT_GRANTED_SUPERSEDED
```

R2 CI PASS 后下一门：

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R3_20261011_01

R3_SCOPE=MINIMAL_BASELINE_FRESH_INSTALLER_ORCHESTRATION
```
