# N3-W T1 S20 real three-service secret handoff R2 failure and R3 TLS bind repair

Date: 2026-10-10

Status: R2_APPLY_FAIL / R2_ROLLBACK_CLOSED_PASS / SECOND_ROOT_CAUSE_CONFIRMED / R3_SOURCE_REPAIR_PREPARED

Repository: chrenguo-stack/HomeAssistant

PR: #541, OPEN DRAFT

LIVE_T1_MUTATION=false

BOARD_ACCESS=false

MERGE=false

## 1. R2 transaction result

```text
R2_AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R2_20261010_01
R2_AUTHORIZATION_CLAIMED=true
R2_AUTHORIZATION_CONSUMED=true
R2_AUTHORIZATION_REPLAY=false
S20_APPLY_R2=FAIL
R2_EXECUTOR_RESULT=transaction_failed_rolled_back:S20ServiceHandoffError
```

The R2 authorization is permanently consumed and must never be replayed.

## 2. R2 rollback closure

Fresh external read-only forensic evidence after R2 proved:

```text
DOCKER_CONTAINER_COUNT=0
TRANSACTION_CONTAINER_PRESENT=false
HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0

REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
REAL_DYNSEC_BASELINE_RESTORED=true
REAL_DYNSEC_OWNER_MODE=1883:1883:600

BROKER_CONFIG_UNCHANGED=true
S18_BACKUP_UNCHANGED=true

R1_SNAPSHOT_PRESENT=true
R1_SNAPSHOT_BASELINE_EXACT=true
R1_SNAPSHOT_OWNER_MODE=0:0:600

R2_SNAPSHOT_PRESENT=true
R2_SNAPSHOT_BASELINE_EXACT=true
R2_SNAPSHOT_OWNER_MODE=0:0:600

PRODUCTION_SECRET_DESTINATION_PRESENT=false
PRODUCTION_SECRET_PARENT_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false

DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_UNCHANGED=true
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

The R2 executor had already completed its internal rollback postcheck before emitting
`transaction_failed_rolled_back`. The independent external forensic confirms the same state.

Therefore:

```text
S20_APPLY_R2=FAIL
S20_APPLY_R2_ROLLBACK=CLOSED_PASS
MANUAL_RECOVERY_REQUIRED=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
```

Both R1 and R2 rollback snapshots remain immutable transaction evidence.

## 3. R2 failure stage

Docker lifecycle evidence:

```text
create
start
die exitCode=1
destroy
```

No `docker exec` event occurred.

Therefore R2 again failed during temporary Broker startup, before:

- Dynamic Security role/client creation;
- positive service authentication;
- wrong-client-ID checks;
- anonymous rejection check.

## 4. Why the R1 repair was necessary but insufficient

R1 source forced:

```text
--user 1883:1883
```

That was incorrect and R2 correctly removed it.

The exact Mosquitto 2.1.2 Alpine image has:

```text
IMAGE_USER=""
ENTRYPOINT=/docker-entrypoint.sh
```

The image entrypoint starts as root when no user override is supplied. It adjusts the data-directory ownership and then execs Mosquitto.

However Mosquitto itself, when started as root and no explicit `user` option is configured, defaults to dropping privileges to the `mosquitto` user.

Therefore removing Docker `--user 1883:1883` restored the image entrypoint flow but did not make the Broker remain root for its full configuration/TLS startup.

## 5. Second root cause

The frozen production Compose binds TLS files individually:

```text
/etc/n3wfc4/tls/ca.pem
  -> /mosquitto/tls/ca.pem

/etc/n3wfc4/tls/server.pem
  -> /mosquitto/tls/server.pem

/etc/n3wfc4/tls/server.key
  -> /mosquitto/tls/server.key
```

The failed S20 executor instead bound the entire host directory:

```text
/etc/n3wfc4/tls
  -> /mosquitto/tls
```

Fresh host forensic had already proved:

```text
/etc/n3wfc4/tls owner=0:0 mode=0700
ca.pem owner=0:0 mode=0644
server.pem owner=0:0 mode=0644
server.key owner=1883:1883 mode=0600
```

When the complete directory is bind-mounted, the container sees
`/mosquitto/tls` as root:root 0700. After Mosquitto drops privileges to UID/GID 1883, it cannot traverse that directory.

The individual production file mounts do not carry this root-only parent-directory traversal restriction into the container path. The files themselves have the intended readable ownership/modes.

Classification:

```text
R2_ROOT_CLASS=S20_EXECUTOR_TLS_BIND_CONTRACT_DRIFT
R2_ROOT_CAUSE=ROOT_ONLY_TLS_DIRECTORY_BIND_BLOCKS_MOSQUITTO_POST_DROP_TRAVERSAL
ROOT_CAUSE_STATUS=CONFIRMED
```

This also explains why R2 reproduced the exact same approximately one-second startup exit even after the R1 Docker-user repair.

## 6. R3 source repair

R3 aligns the temporary Broker mount contract with the frozen production Compose:

```text
TLS_DIRECTORY_BIND=false
TLS_CA_FILE_BIND=read-only
TLS_SERVER_CERT_FILE_BIND=read-only
TLS_SERVER_KEY_FILE_BIND=read-only
```

It additionally verifies before authorization claim:

```text
ca.pem owner=0:0 mode=0644
server.pem owner=0:0 mode=0644
server.key owner=1883:1883 mode=0600
```

The R1 and R2 snapshots are now both retained evidence:

```text
R1=/etc/n3wfc4/private/dynsec-s20-pre-three-service.json
R2=/etc/n3wfc4/private/dynsec-s20-r2-pre-three-service.json
```

R3 gets a distinct create-new-only rollback path:

```text
/etc/n3wfc4/private/dynsec-s20-r3-pre-three-service.json
```

No prior snapshot may be overwritten or used as R3's automatic restore source.

## 7. Proposed R3 authorization identity

The source defines the next proposed authorization identity as:

```text
N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R3_20261010_01
```

This is not yet user approval.

```text
R3_USER_APPROVAL=NOT_YET_GRANTED
R3_AUTHORIZATION_CLAIMED=false
R3_AUTHORIZATION_CONSUMED=false
LIVE_T1_MUTATION=false
```

Before any R3 approval request, the source must complete fresh CI and a fresh exact streamed T1 preclaim.

## 8. Source repair commits

```text
R3_TLS_FILE_BIND_SOURCE=4ce30523879b5ae66b46daf8c0a17b2452caf405
R3_SOURCE_FORMAT=ebce278ef6027441ec829f9a7be4f6436113a2fb
R3_TLS_REGRESSION_TESTS=fd53d3529d861464a3a303ac091279466edf8ac2
R3_TLS_TEST_HOST_INDEPENDENCE=b3be299556af43d941a0c8db03e298ceee6d186e
```

## 9. Gate state

```text
S20_R2_APPLY=FAIL
S20_R2_ROLLBACK=CLOSED_PASS
R2_AUTHORIZATION_CONSUMED=true
R2_AUTHORIZATION_REPLAY=false

R2_SECOND_ROOT_CAUSE=CONFIRMED
R3_SOURCE_REPAIR=PREPARED
R3_SOURCE_CI=PENDING

LIVE_T1_MUTATION=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
PR_MERGE=false

NEXT_ONE_GATE=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_R3_SOURCE_CI_AND_PRECLAIM_20261010_01
```
