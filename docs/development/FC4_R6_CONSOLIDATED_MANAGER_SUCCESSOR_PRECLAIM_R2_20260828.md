# FC4 R6 Consolidated Manager Successor Preclaim R2 — 2026-08-28

> Public-safe engineering archive. No raw hostnames, private addresses, credential bodies, Setup Secret, private evidence paths, pairing identifiers or private keys are included.

## Route Lock

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=R6_CONSOLIDATED_MANAGER_SUCCESSOR_PRECLAIM
ACTIVE_DETOUR=T1_RUNTIME_BASELINE_RECOVERY
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION
NEW_BRANCH_ALLOWED=false
```

This archive records the successful read-only R2 preclaim after the FC4 Acceptance Route Lock V1.0 two-failure fuse forced an executor-contract audit. No production mutation occurred.

## Executor-contract correction

The earlier consolidated preclaim incorrectly assumed that four SQLite single-file binds must become four distinct directory binds. Read-only audit proved all four current database files share one container parent and one host parent filesystem object. The correct repair model is therefore:

```text
4 RW single-file binds
  -> remove all 4
  -> add 1 RW common-parent directory bind
```

The existing relay-key nested bind remains unchanged and resolves to the same object already present beneath the common host parent. The registration database remains on its separate already-correct directory bind.

This failure is classified as an executor/harness contract defect, not a product defect and not a new product-development branch.

## R2 preclaim result

The final corrected read-only preclaim passed all required bindings:

- exact current Manager, Broker and FC4 Home Assistant authority rebound successfully;
- future Manager MQTT transport is expressible without source modification;
- future MQTT host strategy is `USE_TLS_SERVER_NAME_AS_MQTT_HOST`;
- future MQTT port is `8883` with TLS enabled;
- TLS-only handshake passed against the current FC4 Broker;
- future TLS target was bound to the current FC4 Broker publication;
- exact MQTT environment delta contains only `GH_MQTT_CA_FILE`, `GH_MQTT_HOST`, `GH_MQTT_PORT`, and `GH_MQTT_TLS`;
- all four current SQLite file binds resolve to the same objects that will be visible through the future common-parent directory bind;
- current common-parent bind count is zero;
- current database single-file bind count is four;
- current relay-key nested bind count is one;
- unknown nested bind count is zero;
- registration directory bind is preserved unchanged;
- relay-key nested bind is preserved unchanged;
- Manager image, frozen revision, network mode, Manager identity/password authority, and Provisioning identity/password authority remain unchanged;
- prepared DynSec candidate remains present and the DynSec repair authorization remains unclaimed/unconsumed.

Frozen corrected plan:

```text
CORRECTED_MOUNT_MODEL=FOUR_FILE_BINDS_TO_ONE_COMMON_PARENT_BIND
FUTURE_MANAGER_MOUNT_REMOVE_COUNT=4
FUTURE_MANAGER_MOUNT_ADD_COUNT=1
MANAGER_RECREATE_COUNT_TARGET=1
MQTT_TRANSPORT_REPAIR_INCLUDED=true
SQLITE_COMMON_PARENT_DIRECTORY_BIND_REPAIR_INCLUDED=true
FOUR_SQLITE_STATE_OBJECTS_PRESERVED=true
BROKER_CHANGE=false
HOMEASSISTANT_CHANGE=false
DYNSEC_MUTATION=false
BOARD_C_ACCESS=false
```

The public-safe consolidated plan hash is:

```text
CONSOLIDATED_MANAGER_SUCCESSOR_PLAN_SHA256=0bc33fc672c23f9f380b3be2a3109efa93eff74c2f24f943acc4de3573fffc9a
```

## Mutation ordering frozen by this preclaim

The intended route is now:

```text
private consolidated successor materialization
  -> explicit consolidated Manager mutation authorization
  -> exactly one Manager recreate
  -> verify TLS transport + five writable-state topologies
  -> return to already-preclaimed R6D2 DynSec authority repair
  -> prove Manager + Provisioning MQTT authentication
  -> Board C first registration
  -> FC4 Final Physical Acceptance closure
```

The Manager recreate may temporarily leave Manager MQTT authentication rejected because the active DynSec authority is still stale. That expected intermediate state is not itself a rollback trigger; DynSec repair is the immediately following bounded Broker transaction.

## Safety boundary

At R2 closure:

```text
R6_CONSOLIDATED_MANAGER_SUCCESSOR_PRECLAIM=PASS
PRODUCTION_FILE_WRITE=false
COMPOSE_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
DYNSEC_MUTATION=false
SQLITE_MUTATION=false
BOARD_C_ACCESS=false
NEW_BRANCH_ALLOWED=false
```

No sibling S1C/S1D/R6D3-style route is authorized. Any new blocker must remain attached to the same Route Lock node unless it independently proves that the north-star route itself is invalid.
