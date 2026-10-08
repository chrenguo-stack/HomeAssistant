# N3-W Clean Product First-Pair — P2 Preboot Runtime Re-freeze Preexecution — 2026-10-08

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P2_PREBOOT_RUNTIME_REFREEZE_FOR_CURRENT_CLEAN_CANDIDATE_20261008_01
STATUS=AUTHORIZED_NOT_EXECUTED
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_MUTATION=false
BOARD_ACCESS=false
BOARD_WRITE=false
MERGE=false
```

## 1. Entry authority

```text
CURRENT_P1_SUCCESSOR=CLOSED_PASS
CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
PRODUCT_HARDWARE_ID_SHA256=DEFERRED
PRODUCT_NORMAL_BOOT=false

SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
ARTIFACT_ID=11469977052
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c

P3_AUTHORIZATION_GRANTED=true
P3_AUTHORIZATION_CLAIMED=false
P3_AUTHORIZATION_CONSUMED=false
```

The previous P2 R5 closure remains valid historical evidence, but it predates
the current P1 successor closure. Before P3 mutation, freeze a fresh current
Manager/Broker/TLS/identity snapshot authority.

## 2. Allowed scope

```text
ALLOWED=one bounded explicit-root T1 SSH read-only collection
ALLOWED=Manager exact container greenhouse-manager
ALLOWED=Broker unique Compose project n3wfc4 + service broker
ALLOWED=runtime/image/network/TLS/config/mount metadata
ALLOWED=SQLite mode=ro + PRAGMA query_only=ON
ALLOWED=stable preboot identity snapshot
ALLOWED_AFTER_REMOTE_PASS=one Mac-origin UDP/47111 discovery query

BOARD_ACCESS=false
BOARD_WRITE=false
T1_CONFIGURATION_MUTATION=false
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_P3=false
AUTO_RETRY=false
```

The operator's "continue" instruction authorizes this read-only successor gate.
Any failure stops the gate; no automatic retry.

## 3. Required PASS predicates

```text
PAIRING_ADVERTISED_HOST_MODE_AUTO=true
REAL_T1_ADDRESS_MATCH=true
NODE_CREDENTIAL_BROKER_HOST_MATCH=true
BROKER_TCP_TLS_A_8883=true

MANAGER_CONTAINER_RUNNING=true
BROKER_CONTAINER_RUNNING=true
BROKER_RUNTIME_BINDING_UNIQUE=true
MANAGER_HOST_NETWORK=true
MANAGER_PORTS_EMPTY=true

UDP_47111_LISTENING=true
TCP_47112_LISTENING=true
TCP_8883_LISTENING=true

DB_MOUNT_RESOLUTION_PASS=true
IDENTITY_SNAPSHOT_STABLE=true
MANAGER_PREBOOT_SNAPSHOT_CREATED=true
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1

EXTERNAL_DISCOVERY_PASS=true
MANAGER_DISCOVERY_AUTO_SOURCE_A=true
```

## 4. Closure boundary

On PASS, freeze the fresh Manager/Broker IDs, started-at values, restart
counts, TLS binding hash, and Manager preboot identity snapshot SHA256.

```text
P2_REFREEZE_STATUS=CLOSED_PASS
READY_FOR_P3=true
P3_AUTHORIZATION_REMAINS_GRANTED=true
P3_AUTHORIZATION_CLAIMED=false
P3_AUTHORIZATION_CONSUMED=false
AUTO_P3=false
STOP=true
```

No board command is part of this P2 gate.


## 5. Versioned executor binding

```text
EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p2_preboot_runtime_refreeze/executor.py
EXECUTOR_COMMIT=88ebc85693fb15f334b4d505ce5c08bfc45095e5
EXECUTOR_BLOB_SHA=4b27e6174be45a5fc250d81b4f292ede5009e7d3
REPOSITORY_VERSIONED_EXECUTOR=true
```

The Mac bootstrap must fetch this exact GitHub blob, require the exact blob SHA,
compile it locally, and only then execute it. No board command is present in
this executor.
