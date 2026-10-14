# N3-W T1 S20 real three-service secret handoff R3 failure and R4 TLS path contract repair

Date: 2026-10-10

Status: R3_APPLY_FAIL / R3_ROLLBACK_CLOSED_PASS / PERSISTENT_STARTUP_ROOT_CAUSE_CONFIRMED / R4_SOURCE_REPAIR_PREPARED

Repository: chrenguo-stack/HomeAssistant

PR: #541, OPEN DRAFT

LIVE_T1_MUTATION=false

BOARD_ACCESS=false

MERGE=false

## 1. R3 transaction result

```text
R3_AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R3_20261010_01
R3_AUTHORIZATION_CLAIMED=true
R3_AUTHORIZATION_CONSUMED=true
R3_AUTHORIZATION_REPLAY=false
S20_APPLY_R3=FAIL
R3_EXECUTOR_RESULT=transaction_failed_rolled_back:S20ServiceHandoffError
```

The R3 authorization is permanently consumed and must never be replayed.

## 2. R3 rollback closure

Fresh independent read-only forensic after R3 proved:

```text
DOCKER_CONTAINER_COUNT=0
TRANSACTION_CONTAINER_PRESENT=false
HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0

REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
REAL_DYNSEC_BASELINE_RESTORED=true
REAL_DYNSEC_OWNER_MODE=1883:1883:600

R1_SNAPSHOT_BASELINE_EXACT=true
R2_SNAPSHOT_BASELINE_EXACT=true
R3_SNAPSHOT_BASELINE_EXACT=true
R1_R2_R3_SNAPSHOT_OWNER_MODE=0:0:600

PRODUCTION_SECRET_DESTINATION_PRESENT=false
PRODUCTION_SECRET_PARENT_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false

DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
NETWORK_n3wfc4-private_CONTAINER_COUNT=0
NETWORK_n3wfc4-services_CONTAINER_COUNT=0

GUARD_ACTIVE=active
GUARD_ENABLED=enabled

DYNSEC_CLIENT_COUNT=1
DYNSEC_ADMIN_ONLY=true
TARGET_SERVICE_CLIENTS_ABSENT=true
TARGET_SERVICE_ROLES_ABSENT=true
NODE_CLIENTS_ABSENT=true
```

Therefore:

```text
S20_APPLY_R3=FAIL
S20_APPLY_R3_ROLLBACK=CLOSED_PASS
MANUAL_RECOVERY_REQUIRED=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
```

## 3. R3 failed before any DynSec mutation

The R3 event stream again showed only:

```text
create
start
die exitCode=1
destroy
```

No transaction-container `docker exec` event occurred.

Therefore R3 failed during Broker configuration/startup, before Dynamic Security service-role/client creation or authentication tests.

## 4. Exact live Broker config authority

The S20 executor intentionally freezes and validates:

```text
BROKER_CONFIG=/etc/n3wfc4/mosquitto.conf
SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
```

Fresh live read-only forensic proved its TLS directives are:

```text
cafile /mosquitto/config/n3w-ca.pem
certfile /mosquitto/config/n3w-server.pem
keyfile /mosquitto/config/n3w-server.key
```

The repository production Compose currently describes a different later product-source layout under
`/opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf`, but that file is absent on this clean T1 state:

```text
PROD_CONFIG_PRESENT=false
```

Therefore the next isolated transaction must not assume that repository path exists on T1.
The exact installed `/etc/n3wfc4/mosquitto.conf` remains the transaction's live config authority.

## 5. Persistent startup root cause

R3 changed TLS host sources from a whole-directory bind to three individual file binds, but mounted them to:

```text
/mosquitto/tls/ca.pem
/mosquitto/tls/server.pem
/mosquitto/tls/server.key
```

Those are not the paths referenced by the exact live Broker config.

The exact config requires:

```text
/mosquitto/config/n3w-ca.pem
/mosquitto/config/n3w-server.pem
/mosquitto/config/n3w-server.key
```

Thus R3 necessarily starts Mosquitto with three TLS paths that do not exist in the container namespace. This explains the immediate startup exit and is independent of Dynamic Security state.

Classification:

```text
R3_ROOT_CLASS=S20_EXECUTOR_BROKER_CONFIG_TO_TLS_MOUNT_PATH_DRIFT
R3_ROOT_CAUSE=EXACT_BROKER_CONFIG_REFERENCES_MOSQUITTO_CONFIG_N3W_TLS_PATHS_BUT_EXECUTOR_MOUNTS_MOSQUITTO_TLS_PATHS
R3_ROOT_CAUSE_STATUS=CONFIRMED
```

## 6. Correction of earlier causal attribution

The earlier R1 forced `--user 1883:1883` was a real executor defect and remains correctly removed.

The R2 whole-directory TLS bind also introduced a root-only parent traversal problem.

However the R3 forensic proves that the persistent startup failure across the attempts had an even earlier deterministic blocker: the mounted TLS target paths did not satisfy the exact live Broker config.

Therefore earlier statements that attributed the observed startup exit solely to Docker UID or TLS-parent traversal were too strong.

Current corrected status:

```text
R1_FORCED_UID_DEFECT=CONFIRMED
R1_FORCED_UID_CAUSALITY_FOR_OBSERVED_EXIT=NOT_ISOLATED

R2_ROOT_ONLY_TLS_DIRECTORY_DEFECT=CONFIRMED
R2_DIRECTORY_PERMISSION_CAUSALITY_FOR_OBSERVED_EXIT=NOT_ISOLATED

PERSISTENT_R1_R2_R3_STARTUP_BLOCKER=
BROKER_CONFIG_TO_TLS_MOUNT_PATH_DRIFT

PERSISTENT_STARTUP_BLOCKER_STATUS=CONFIRMED
```

## 7. R4 source repair

R4 keeps the exact installed Broker config authority and mounts the existing host TLS files to the exact target names it references:

```text
/etc/n3wfc4/tls/ca.pem
  -> /mosquitto/config/n3w-ca.pem:ro

/etc/n3wfc4/tls/server.pem
  -> /mosquitto/config/n3w-server.pem:ro

/etc/n3wfc4/tls/server.key
  -> /mosquitto/config/n3w-server.key:ro
```

The executor now defines the mount target paths once and uses them both for:

- Broker config TLS path contract validation during preclaim;
- temporary Broker Docker bind targets.

This prevents source/config path drift from silently reaching a claimed transaction.

## 8. R4 rollback hardening

Before any further live attempt, R4 also closes two latent rollback weaknesses found during source review:

1. Snapshot creation now removes the create-new R4 snapshot on any copy, ownership, mode, or hash-validation failure.
2. Snapshot restore validates the R4 snapshot metadata/hash before replacing the live DynSec file.
3. The runtime retains whether `/opt/greenhouse-secrets` was absent at preclaim, so a later postcheck failure can still remove a transaction-created empty parent even after the transaction marker directory has already been cleaned.

These changes do not alter current T1 state.

## 9. Snapshot attempt isolation

R1/R2/R3 remain immutable evidence:

```text
R1=/etc/n3wfc4/private/dynsec-s20-pre-three-service.json
R2=/etc/n3wfc4/private/dynsec-s20-r2-pre-three-service.json
R3=/etc/n3wfc4/private/dynsec-s20-r3-pre-three-service.json
```

R4 uses a new create-new-only rollback snapshot:

```text
R4=/etc/n3wfc4/private/dynsec-s20-r4-pre-three-service.json
```

No older snapshot is an automatic R4 restore source.

## 10. Proposed R4 authorization identity

The source defines:

```text
N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R4_20261010_01
```

This is not live approval.

```text
R4_USER_APPROVAL=NOT_YET_GRANTED
R4_AUTHORIZATION_CLAIMED=false
R4_AUTHORIZATION_CONSUMED=false
LIVE_T1_MUTATION=false
```

Fresh source CI and a new exact streamed read-only T1 preclaim are mandatory before any approval request.

## 11. R4 source commits

```text
R4_TLS_PATH_AND_ROLLBACK_SAFETY=ec9036a8a0f94afb095176139966d272c9faa76b
R4_REGRESSION_TESTS=25e7c61da9e4d00977b30edfad5cd2bdee6fe4e5
R4_CONFIG_MOUNT_SINGLE_SOURCE_CONTRACT=961772f0a203177cf01f703a2b9a6bef37a28fb8
R4_CONFIG_CONTRACT_TESTS=4783a82c4e2c2f8a5df4d53f63c24cfe290d3327
```

## 12. Gate state

```text
S20_R3_APPLY=FAIL
S20_R3_ROLLBACK=CLOSED_PASS
R3_AUTHORIZATION_CONSUMED=true
R3_AUTHORIZATION_REPLAY=false

R3_ROOT_CAUSE_STATUS=CONFIRMED
R4_SOURCE_REPAIR=PREPARED
R4_SOURCE_CI=PENDING

R4_USER_APPROVAL=NOT_YET_GRANTED
R4_AUTHORIZATION_CLAIMED=false
R4_AUTHORIZATION_CONSUMED=false

LIVE_T1_MUTATION=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
PR_MERGE=false

NEXT_ONE_GATE=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_R4_SOURCE_CI_AND_PRECLAIM_20261010_01
```
