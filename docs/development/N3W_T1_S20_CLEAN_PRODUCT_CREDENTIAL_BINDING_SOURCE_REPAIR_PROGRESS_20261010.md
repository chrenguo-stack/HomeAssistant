# N3-W T1 S20 clean-product 三服务凭据绑定 source repair progress（2026-10-10）

## 1. 当前结论

S19 隔离身份/ACL 验收继续保持 `CLOSED_PASS`。S20 原 read-only preflight 的 `FAIL_CLOSED / SOURCE` 已进入 source repair，尚未转为 production authorization。

```text
S19_ISOLATED_IDENTITY_AND_ACL_ACCEPTANCE=CLOSED_PASS
S20_ORIGINAL_PREFLIGHT_RESULT=FAIL_CLOSED
S20_ORIGINAL_FAILURE_CLASS=SOURCE
SOURCE_REPAIR_HEAD=af5cd031979bce091965468d587a361ee86ccf5f
LIVE_RUNTIME_MUTATION=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
```

## 2. 已实现的 source candidate

### 2.1 三服务凭据 bundle

新增 `t1_clean_service_credential_bundle.py`：

- 只生成 manager / provisioning / homeassistant 三个服务身份；
- 三个随机密码独立；
- service 目录 0700、secret 文件 0600；
- node credential 数量固定为 0；
- Manager 与 Provisioning 使用两个不同 password-file target；
- Home Assistant 密码与 bootstrap metadata 分开只读挂载；
- manifest/report 不包含密码正文；
- symlink、权限漂移、文件 hash/inventory 漂移 fail closed。

Provisioning 的实际消费者仍为同一个 greenhouse-manager product runtime，不新增第四个容器。

### 2.2 Home Assistant fresh-first-boot 自动 bootstrap

新增 T1 专用 custom integration `n3w_mqtt_bootstrap`。

冻结语义：

```text
MQTT_ENTRY_COUNT=0
-> call Home Assistant MQTT official config flow
-> broker=127.0.0.1
-> port=1883
-> protocol=5
-> username/password/client_id from private handoff
-> create exactly one entry

MQTT_ENTRY_COUNT=1 + exact match
-> no-op PASS

MQTT_ENTRY_COUNT>1 or any mismatch
-> FAIL_CLOSED
-> no automatic reconfigure
```

该路径不直接编辑 `.storage`。历史已有 HA 的迁移/轮换协议仍禁止脚本自动 reconfigure；fresh-first-boot 是单独、仅零 entry 状态允许的产品初始化路径。

### 2.3 Home Assistant source authority

2026-10-10 官方 stable 版本为 `2026.10.0`。本轮绑定：

```text
HOMEASSISTANT_CANDIDATE_IMAGE_REF=ghcr.io/home-assistant/home-assistant:2026.10.0
HOMEASSISTANT_UPSTREAM_SOURCE_TAG=2026.10.0
MQTT_CONFIG_FLOW_BLOB=9181013edc6686b6ac482b4061b3f5e48ba4ff77
HOMEASSISTANT_OCI_DIGEST=UNBOUND
```

exact 2026.10.0 MQTT config-flow source确认 user flow 进入 broker step，broker step 会验证真实连接并由 Home Assistant 自身创建 config entry；没有 `async_step_import`。因此没有通过伪造 import 或直接 storage patch 绕过官方配置逻辑。

### 2.4 Home Assistant loopback MQTT

fresh Broker source 增加 container listener 1883，同时保留 TLS/8883：

```text
container 1883=authenticated, no TLS
host publication required=127.0.0.1:1883 only

container 8883=TLS
host publication required=0.0.0.0:8883

allow_anonymous=false
global Dynamic Security plugin=one
per_listener_settings=absent
```

Manager 与真实节点继续走现有 TLS/8883；新增 1883 仅供同一 T1 的 host-network Home Assistant 使用。

源码 Compose gate 已要求 fresh clean product 只有 manager / broker / homeassistant 三个服务、只有 `n3wfc4-private` / `n3wfc4-services` 两个项目网络。由于 Broker container 内部 1883 监听其容器接口，后续 live acceptance 还必须证明两个项目网络的实际 membership 没有额外容器；Host 侧同时必须证明 1883 只有 IPv4 loopback listener/publication，没有 wildcard/LAN/IPv6 publication。

## 3. Source gates / tests

新增或扩展：

```text
tools/n3w_t1_clean_product_deployment_gate.py
tests/tools/test_n3w_t1_clean_product_deployment_gate.py
tests/tools/test_n3w_t1_fresh_mosquitto_config_contract.py
tests/tools/test_n3w_ha_mqtt_bootstrap_component.py
host/greenhouse-manager/tests/ops/test_t1_clean_service_credential_bundle.py
.github/workflows/n3w-t1-deployment-gate-ci.yml
```

focused source CI 已在 code-equivalent head `6dd2476e7be0b3f31253309c091a1576cf017303` 通过：

```text
N3W_T1_DEPLOYMENT_GATE_CI_RUN=38028806480
N3W_T1_DEPLOYMENT_GATE_CI=PASS
N3W_BROKER_INGRESS_GUARD_CI_RUN=38028806459
N3W_BROKER_INGRESS_GUARD_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI_RUN=38028806482
PUBLIC_REPOSITORY_SAFETY_CI=PASS
```

后续只增加 exact Home Assistant isolated runtime test/workflow，没有修改上述产品 source candidate。

## 4. Exact Home Assistant isolated runtime acceptance

新增：

```text
tests/tools/test_n3w_ha_mqtt_bootstrap_isolated_runtime.py
.github/workflows/n3w-t1-ha-bootstrap-isolated-ci.yml
```

目标：在 GitHub runner 上拉取 exact `home-assistant:2026.10.0` 与 Mosquitto 2.1.2，真实启动隔离 Broker + Home Assistant，验证首次 config-flow 创建 MQTT entry，并重建 HA 容器验证 entry 持久且 bootstrap 二次执行不制造第二 entry。

当前 run：

```text
HA_ISOLATED_CI_RUN=38028945518
HA_ISOLATED_CI_SOURCE_HEAD=af5cd031979bce091965468d587a361ee86ccf5f
HA_ISOLATED_CI_STATUS=IN_PROGRESS_AFTER_THREE_ASSISTANT_POLLS
FURTHER_ASSISTANT_POLLING=STOPPED_BY_PROJECT_RULE
```

本文件不把 pending CI 写成 PASS。

## 5. 仍未关闭

```text
HOMEASSISTANT_EXACT_OCI_DIGEST=UNBOUND
HOMEASSISTANT_ARM64_IMAGE_BINDING=UNPROVEN
HOMEASSISTANT_ISOLATED_CONFIG_FLOW_RUNTIME=CI_PENDING
MANAGER_PRODUCTION_IMAGE=UNBOUND
MANAGER_RUNTIME_UID_GID=UNBOUND
T1_FRESH_READONLY_REBIND=NOT_EXECUTED_AFTER_SOURCE_REPAIR
PRODUCTION_THREE_SERVICE_DYNSEC_TRANSACTION=NOT_AUTHORIZED
PRODUCTION_BROKER_START=NOT_AUTHORIZED
HOST_1883_PUBLICATION=NOT_APPLIED
HOST_8883_PUBLICATION=NOT_APPLIED
BOARD_ACCESS=false
```

因此：

```text
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
S20_SOURCE_REPAIR_FINAL_CLOSURE=PENDING_HA_ISOLATED_CI
```

## 6. 下一停止点

先等待 exact HA isolated CI 自行结束。按项目规则不继续轮询。取得结果后：

- PASS：做 source review + exact image/arm64 binding preflight，然后才进入 T1 fresh read-only rebind；
- FAIL：只分析本次 isolated CI 的第一条真实失败证据，不碰 T1，不自动绕过 config-flow；
- 任一情况都不自动创建三生产账号、不启动 Broker、不访问板卡。
