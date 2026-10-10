# N3-W T1 S20 real three-service secret handoff R2 source review and authorization design

Date: 2026-10-10

Status: SOURCE_REVIEW_COMPLETE / R2_DESIGN_FROZEN / EXPLICIT_AUTHORIZATION_PENDING

Repository: chrenguo-stack/HomeAssistant

PR: #541, OPEN DRAFT

SOURCE_REVIEW_BASE=7681813241b00d091d849dbc0bfeb137f97e6788

MAIN_EXACT=d423211b6196c2f2f0f01dff072c4f877fbe58ee

LIVE_T1_MUTATION=false

BOARD_ACCESS=false

MERGE=false

## 1. Purpose

R1 consumed its one-time authorization and failed after claim when the temporary Mosquitto container was forced to run as UID/GID 1883. The transaction rolled back successfully and the retained R1 snapshot remains exact evidence.

R2 must not reuse the consumed R1 authorization and must not overwrite or delete the retained R1 snapshot.

This gate reviews the repaired executor, freezes the retained-snapshot policy, introduces an attempt-scoped R2 rollback snapshot, and defines a new one-time authorization ID. It performs source/docs/tests changes only. No T1 mutation is authorized by this document.

## 2. Frozen R1 result

```text
S20_APPLY_R1=FAIL
S20_APPLY_R1_ROLLBACK=CLOSED_PASS
R1_ROOT_CAUSE_STATUS=CONFIRMED
R1_AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01
R1_AUTHORIZATION_CLAIMED=true
R1_AUTHORIZATION_CONSUMED=true
R1_AUTHORIZATION_REPLAY=false

REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
R1_SNAPSHOT_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
R1_SNAPSHOT_OWNER_MODE=0:0:600
PRODUCTION_SECRET_DESTINATION_PRESENT=false
DOCKER_CONTAINER_COUNT=0
HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0
```

R1 evidence authority:
`docs/development/N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_R1_FAILURE_FORENSIC_20261010.md`.

## 3. R2 source review findings

### A1. Retained R1 snapshot is evidence, not an R2 work file

The retained path is:

```text
/etc/n3wfc4/private/dynsec-s20-pre-three-service.json
```

It records the exact R1 pre-transaction baseline and must remain immutable during R2.

R2 preclaim must require:

```text
R1_SNAPSHOT_PRESENT=true
R1_SNAPSHOT_SYMLINK=false
R1_SNAPSHOT_OWNER_MODE=0:0:600
R1_SNAPSHOT_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
R1_SNAPSHOT_MUTATION_BY_R2=false
```

Missing, unsafe, metadata-drifted, or hash-drifted R1 evidence causes STOP before authorization claim.

### A2. R1 snapshot must not be reused as the R2 rollback target

Reusing the retained R1 file would blur transaction provenance and would violate the create-new-only rollback snapshot rule for the new attempt.

R2 therefore receives a distinct attempt-scoped rollback path:

```text
/etc/n3wfc4/private/dynsec-s20-r2-pre-three-service.json
```

Preclaim requires this R2 path to be absent.

### A3. R2 first mutation remains a fresh rollback snapshot

After a fresh R2 preclaim passes and only after the new authorization is claimed:

```text
AUTHORIZATION_CLAIMED=true
```

the first filesystem write is creation of the R2 snapshot.

R2 snapshot contract:

```text
create-new-only
owner=root:root
mode=0600
source=/var/lib/n3wfc4-broker/dynamic-security.json
source_sha256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
```

R1 snapshot remains untouched.

### A4. R2 rollback may use only the R2 snapshot

If any post-claim R2 step fails:

1. stop/remove the temporary transaction Broker;
2. restore Dynamic Security from the R2 snapshot if the R2 snapshot was successfully created;
3. if snapshot creation itself failed before a valid R2 snapshot existed, accept rollback only when the live Dynamic Security file is still the exact frozen baseline with exact owner/mode;
4. remove only R2-created service-secret material;
5. verify cleanup;
6. run a full read-only rollback postcheck.

R1 snapshot is never the automatic R2 restore source.

### A5. Cleanup must be proven, not assumed

R1 showed that cleanup worked in practice, but the old source used best-effort recursive deletion without proving that transaction directories were actually gone.

R2 source now treats cleanup failure as rollback failure. It verifies:

```text
SECRET_DESTINATION_ABSENT=true
TRANSACTION_DIRECTORY_ABSENT=true
SECRET_PARENT_ABSENT_IF_R2_CREATED_IT=true
```

If exact cleanup cannot be proved:

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
AUTO_RETRY=false
STOP=true
```

### A6. Rollback postcheck is now part of the executor contract

A successful R2 rollback must prove all of the following before reporting rolled back:

```text
DOCKER_CONTAINER_COUNT=0
DOCKER_VOLUME_SET_UNCHANGED=true
TWO_PROJECT_NETWORKS_EMPTY=true
GUARD_UNCHANGED=true
HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0
BROKER_CONFIG_SHA_UNCHANGED=true
REAL_DYNSEC_SHA_BASELINE_RESTORED=true
REAL_DYNSEC_OWNER_MODE=1883:1883:600
S18_BACKUP_SHA_UNCHANGED=true
TARGET_SERVICE_CLIENTS_ABSENT=true
TARGET_SERVICE_ROLES_ABSENT=true
NODE_CLIENTS_ABSENT=true
SECRET_DESTINATION_ABSENT=true
TRANSACTION_DIRECTORY_ABSENT=true
R1_RETAINED_SNAPSHOT_VERIFIED=true
```

If an R2 snapshot exists, it must also be exact root:root 0600 with the frozen baseline SHA.

### A7. R1 Broker-start root-cause repair remains in force

The temporary Broker no longer uses:

```text
--user 1883:1883
```

The exact Mosquitto image is allowed to execute its normal `/docker-entrypoint.sh` privilege flow.

Root-only transaction client configuration is still consumed only by one-shot client commands using:

```text
docker exec --user 0:0 ...
```

The Broker remains network-none and publishes no host port.

### A8. R2 source review result

```text
A1_RETAIN_R1_EVIDENCE=CLOSED
A2_ATTEMPT_SCOPED_R2_SNAPSHOT=CLOSED
A3_FIRST_MUTATION_FRESH_R2_SNAPSHOT=CLOSED
A4_R2_ONLY_ROLLBACK_SOURCE=CLOSED
A5_VERIFIED_CLEANUP=CLOSED
A6_ROLLBACK_POSTCHECK=CLOSED
A7_BROKER_PRIVILEGE_REPAIR_PRESERVED=CLOSED
A8_R2_AUTHORIZATION_BOUNDARY=CLOSED
SOURCE_REVIEW_RESULT=PASS_PENDING_CI
```

## 4. R2 source implementation

R2 source implementation commits:

```text
R2_SNAPSHOT_AND_ROLLBACK_HARDENING=ec7fddde9c7d10b7815f296b1214401910df8d5a
R2_SOURCE_FORMAT=2006de388035a24a1e3c33ce43c182dd5de5b523
R2_REGRESSION_TESTS=7681813241b00d091d849dbc0bfeb137f97e6788
```

The exact final executor SHA and CI run IDs are not frozen until the source/docs gate reaches a stable HEAD and fresh CI completes.

## 5. New R2 authorization ID

The proposed R2 authorization ID is:

```text
AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R2_20261010_01
```

This is a new authorization identity. It does not revive or replace R1 authorization.

Current status:

```text
R2_USER_APPROVAL=NOT_YET_GRANTED
R2_AUTHORIZATION_CLAIMED=false
R2_AUTHORIZATION_CONSUMED=false
R2_LIVE_T1_MUTATION=false
```

## 6. Proposed R2 authorized mutation scope

Only after fresh CI, fresh exact source binding, fresh T1 read-only preclaim, and a new explicit user approval, the R2 authorization may cover exactly:

```text
- create /etc/n3wfc4/private/dynsec-s20-r2-pre-three-service.json create-new-only;
- preserve /etc/n3wfc4/private/dynsec-s20-pre-three-service.json unchanged;
- create /opt/greenhouse-secrets parent if absent;
- generate exactly three service credential bundles and zero node credentials;
- chown Manager and Provisioning password files to numeric 999:999;
- run one exact-image temporary --network none/no-host-port Broker transaction;
- add exactly three service roles and exactly three service clients;
- perform isolated positive/wrong-client-id/anonymous authentication checks;
- stop/remove the temporary Broker;
- on failure, restore exact baseline from the R2 snapshot when available;
- remove only R2-created secret material;
- run full rollback postcheck.
```

Not authorized:

```text
- deletion or modification of the retained R1 snapshot;
- reuse of the R1 authorization;
- production Broker activation;
- host 1883 or 8883 publication;
- Manager start;
- Home Assistant start;
- node credential creation;
- Gate F pairing;
- TLS certificate/key replacement;
- firewall mutation;
- Docker volume deletion;
- Armbian/network modification;
- board/USB/serial/flash/NVS/RF access;
- PR merge.
```

## 7. Authorization claim boundary

R2 authorization is not claimable until all of these are freshly true:

```text
R2_SOURCE_CI=PASS
EXACT_EXECUTOR_BINDING=PASS
STREAMED_DEPENDENCY_BINDING=PASS
T1_FRESH_PRECLAIM=PASS
R1_RETAINED_SNAPSHOT_VERIFIED=true
R2_ROLLBACK_SNAPSHOT_ABSENT=true
REAL_DYNSEC_SHA_BASELINE=true
TARGET_SERVICE_IDENTITIES_ABSENT=true
SECRET_DESTINATION_ABSENT=true
DOCKER_CONTAINER_COUNT=0
PROJECT_NETWORKS_EMPTY=true
HOST_MQTT_LISTENERS=0
```

Then and only then, after explicit user approval:

```text
AUTHORIZATION_CLAIMED=true
```

must be emitted immediately before the first R2 snapshot write.

## 8. Gate state

```text
EXECUTION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_R2_SOURCE_REVIEW_AND_AUTHORIZATION_DESIGN_20261010_01
R2_SOURCE_REVIEW=PASS_PENDING_CI
R2_RETAINED_R1_SNAPSHOT_POLICY=FROZEN
R2_NEW_AUTHORIZATION_ID=DEFINED
R2_EXPLICIT_AUTHORIZATION_STATUS=PENDING_USER_APPROVAL
LIVE_T1_MUTATION=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
PR_MERGE=false
NEXT_ONE_GATE=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_R2_SOURCE_CI_AND_PRECLAIM_20261010_01
```
