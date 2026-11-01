# N3-W T1 minimal-host fresh bootstrap R1 source repair progress（2026-10-11）

## Scope

```text
GATE=N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R1_20261011_01
TARGET_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
R1_SCOPE=FRESH_MANAGER_AND_N3W_STATE_CONSTRUCTORS
T1_MUTATION=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## Source change

新增：

```text
tools/n3w_t1_fresh_product_state_prepare.py
tests/tools/test_n3w_t1_fresh_product_state_prepare.py
```

并为 `CredentialLifecycleStore` 补齐显式 `close()` / context-manager 生命周期，使 fresh constructor 不依赖私有 connection 属性。

fresh state creator 只调用产品 runtime schema owners：

```text
RegistrationRegistry
CredentialLifecycleStore
ReplayRegistry
SqliteNodeApplicationKeyAdmin
```

不再用手写 SQL 伪造 fresh Manager schema，也不创建
`h0h1_legacy_adoption_provenance`。

创建结果要求：

```text
MANAGER_TABLE_COUNT=7
MANAGER_BUSINESS_ROWS=0
LEGACY_PROVENANCE_PRESENT=false
REPLAY_NODE_COUNT=0
REPLAY_TUPLE_COUNT=0
RELAY_ACTIVE_NODE_COUNT=0
RELAY_KEY_FILE_COUNT=0
NODE_CREDENTIAL_COUNT=0
PRODUCTION_SERVICE_START=false
NETWORK_OPERATION=false
```

create 要求 manager/n3w 两个 0700 root 已存在且为空；任何残留都 fail closed。audit 只接受 exact current fresh schema 与空业务状态。

## CI

`N3W T1 production Manager state binding CI` 已加入新 tool/test path，并把 R1 focused tests 纳入同一 source gate。

本 R1 不改变现有 production Compose、Broker、Home Assistant、old staging executor 或 T1 runtime；它只建立后续 fresh installer 所需的正式 state constructor。

```text
R1_SOURCE_COMMITTED=true
R1_CI=PENDING
T1_ACCESS=false
LIVE_MUTATION=false
AUTHORIZATION_03=NOT_GRANTED_SUPERSEDED
```

R1 CI PASS 后的下一门：

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R2_20261011_01

R2_SCOPE=BROKER_TLS_AND_DYNSEC_FRESH_BOOTSTRAP
```
