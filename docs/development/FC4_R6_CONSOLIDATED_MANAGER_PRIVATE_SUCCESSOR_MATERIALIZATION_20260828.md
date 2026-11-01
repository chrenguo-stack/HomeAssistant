# FC4 R6 Consolidated Manager Private Successor Materialization — 2026-08-28

> Public-safe engineering archive. No raw hostnames, private addresses, private host paths, credential bodies, CA paths, Setup Secret, pairing identifiers or private artifact paths are included.

## Route Lock

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=ARCHIVE_AND_PRIVATE_SUCCESSOR_MATERIALIZATION
ACTIVE_DETOUR=T1_RUNTIME_BASELINE_RECOVERY
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION
NEW_BRANCH_ALLOWED=false
```

## Result

The private successor materialization passed. The exact current Manager runtime, Compose source authority, current image binding, future TLS authority, source Compose mount authority, R2 plan hash, successor delta allowlist and prepared DynSec continuation were all rebound successfully before any production mutation.

The successor was materialized only into a private root-owned artifact directory with directory mode `0700` and files mode `0600`. No private path was emitted.

Frozen public-safe hashes:

```text
CONSOLIDATED_MANAGER_SUCCESSOR_PLAN_SHA256=0bc33fc672c23f9f380b3be2a3109efa93eff74c2f24f943acc4de3573fffc9a
SOURCE_COMPOSE_NORMALIZED_SHA256=4b395c0e572ba1f140bcaaa1d07592338ed04631ab6e1843d04f0b9460bf8893
SUCCESSOR_COMPOSE_SHA256=821d0004a2d3289539879a34b12685b87b5c767232238b6a69401d0c8acce138
SUCCESSOR_MANAGER_SERVICE_SHA256=933cf9de359f08e17c716440bcf2ee3bd109d54a205950eb15659670385536a6
```

## Frozen successor delta

The successor changes only the current Manager service and preserves product source/image/revision/network identity.

Manager MQTT transport:

```text
GH_MQTT_HOST     -> frozen TLS server-name authority
GH_MQTT_PORT     -> 8883
GH_MQTT_TLS      -> true
GH_MQTT_CA_FILE  -> existing N3-W Broker CA authority
```

SQLite topology:

```text
4 RW single-file binds
  -> remove 4 exact DB file binds
  -> add 1 RW common-parent directory bind
```

The four SQLite state objects themselves are preserved. Registration remains on its already-correct directory bind. Relay-key remains on its existing exact nested bind and is not relocated. Manager username/client-id/password authority and Provisioning username/client-id/password authority remain unchanged.

Frozen counts:

```text
FUTURE_MANAGER_ENV_CHANGE_COUNT=4
FUTURE_MANAGER_MOUNT_REMOVE_COUNT=4
FUTURE_MANAGER_MOUNT_ADD_COUNT=1
MANAGER_RECREATE_COUNT_TARGET=1
```

No Broker or Home Assistant configuration change is part of this successor. DynSec mutation remains a separate already-preclaimed transaction after the Manager successor is installed.

## Mutation boundary

At materialization closure:

```text
PRIVATE_SUCCESSOR_MATERIALIZATION=PASS
R6D2_AUTHORIZATION_STILL_UNCLAIMED=true
PRODUCTION_FILE_WRITE=false
COMPOSE_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
DYNSEC_MUTATION=false
SQLITE_MUTATION=false
BOARD_C_ACCESS=false
```

The next route node is the single consolidated Manager mutation authorization. That authorization, if granted, must permit exactly one Manager recreate using the frozen private successor and must not include Broker, Home Assistant, DynSec, Board C, flash/NVS or unrelated state mutation.

After the Manager recreate is proven, execution must return directly to the already-preclaimed `R6D2_DYNSEC_AUTHORITY_REPAIR`, then to Board C first registration and FC4 final physical acceptance. No sibling diagnostic branch is authorized by this archive.
