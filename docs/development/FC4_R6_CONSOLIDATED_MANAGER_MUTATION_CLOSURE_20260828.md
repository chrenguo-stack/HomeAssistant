# FC4 R6 Consolidated Manager Mutation Closure — 2026-08-28

## Route Lock

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=CONSOLIDATED_MANAGER_MUTATION_EXECUTION
ACTIVE_DETOUR=T1_RUNTIME_BASELINE_RECOVERY
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION
NEW_BRANCH_ALLOWED=false
```

## Authorization

```text
AUTHORIZATION=R6-CONSOLIDATED-MANAGER-SUCCESSOR-MUTATION-20260828-01
EXECUTOR_REVISION=SCOPE_CORRECTED_R1
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

The first executor attempt stopped pre-CLAIM on `CLAIM_BOUNDARY_PAIRING_REBIND_TIMEOUT` with no production mutation. Route Lock classified the Board C fresh-PENDING dependency as an executor scope overconstraint for this Manager-only transaction. The corrected executor removed Board C/pairing as a claim dependency and deferred the mandatory fresh pairing rebind to the later `BOARD_C_FIRST_REGISTRATION` transaction.

## Forward mutation closure

```text
FORWARD_MANAGER_RECREATE=PASS
MANAGER_CONTAINER_ID_CHANGED=true
MANAGER_RECREATE_COUNT=1
MANAGER_IMAGE_PRESERVED=true
MANAGER_REVISION_PRESERVED=true
MANAGER_NETWORK_MODE_PRESERVED=true
MANAGER_ROOTFS_READONLY=true
```

MQTT transport was corrected in the same Manager recreate:

```text
MANAGER_MQTT_PORT=8883
MANAGER_MQTT_TLS=true
MANAGER_TLS_HANDSHAKE=PASS
MANAGER_IDENTITY_PRESERVED=true
PROVISIONING_IDENTITY_PRESERVED=true
```

The four unsafe SQLite single-file binds were consolidated to one write-capable common-parent directory bind while preserving existing state objects:

```text
WRITE_CAPABLE_SQLITE_SINGLE_FILE_BIND_COUNT_AFTER_REPAIR=0
SQLITE_COMMON_PARENT_DIRECTORY_BIND_COUNT=1
SQLITE_COMMON_PARENT_WRITE_EXECUTE_CAPABLE=true
FOUR_SQLITE_STATE_OBJECTS_PRESENT=true
REGISTRATION_DIRECTORY_BIND_PRESERVED=true
RELAY_KEY_NESTED_BIND_PRESERVED=true
```

## Non-target preservation

```text
PAIRING_SOCKET_READY=true
BROKER_MUTATION=false
BROKER_RESTART=false
HOMEASSISTANT_MUTATION=false
DYNSEC_MUTATION=false
BOARD_C_ACCESS=false
BOARD_C_RESET=false
FLASH_WRITE=false
NVS_ERASE=false
SETUP_SECRET_IMPORT=false
SETUP_SECRET_VALUE_CHANGED=false
SETUP_SECRET_REIMPORT_REQUIRED=true
```

The intermediate Manager MQTT authorization state is allowed to remain `Not authorized` until the already-preclaimed R6D2 DynSec authority repair is executed. This is not a rollback condition for the Manager mutation.

## Next route node

```text
NEXT_GATE=R6D2_DYNSEC_AUTHORITY_REPAIR
CLAIM_BOUNDARY_PAIRING_REBIND_NEXT_REQUIRED_AT=BOARD_C_FIRST_REGISTRATION
NEW_BRANCH_ALLOWED=false
```

The next mutation must not replay this Manager authorization. The Manager transaction is permanently consumed. The separate DynSec authorization remains unclaimed until its own claim boundary.
