# N3-W T1 S20 real three-service secret handoff R1 failure forensic

Date: 2026-10-10

Status: R1_APPLY_FAIL / ROLLBACK_CLOSED_PASS / ROOT_CAUSE_CONFIRMED

PR: #541 (OPEN DRAFT)

## 1. R1 transaction result

```text
AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY=false
S20_APPLY_R1=FAIL
S20_APPLY_R1_ROLLBACK=CLOSED_PASS
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
```

The executor emitted `AUTHORIZATION_CLAIMED=true`, then returned
`transaction_failed_rolled_back:S20ServiceHandoffError`.

The authorization is consumed and must never be replayed.

## 2. Rollback evidence

Fresh read-only forensic evidence after the failed transaction proved:

```text
DOCKER_CONTAINER_COUNT=0
TRANSACTION_CONTAINER_PRESENT=false
HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0
REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
REAL_DYNSEC_BASELINE_RESTORED=true
BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
BROKER_CONFIG_UNCHANGED=true
S18_BACKUP_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
S18_BACKUP_UNCHANGED=true
S20_ROLLBACK_SNAPSHOT_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
S20_ROLLBACK_SNAPSHOT_BASELINE_EXACT=true
PRODUCTION_SECRET_DESTINATION_PRESENT=false
PRODUCTION_SECRET_PARENT_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
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
DYNSEC_DEFAULT_ACL_BASELINE=true
```

The R1 rollback snapshot is retained as transaction evidence and must not be deleted by the source-repair gate.

## 3. Failure stage

Docker lifecycle evidence for the transaction container:

```text
create
start
die exitCode=1
destroy
```

The container used the exact frozen Mosquitto image binding and died about one second after start.

Therefore the failure occurred during temporary Broker startup/readiness, before successful Dynamic Security service-account application was proven.

## 4. Root cause

Fresh read-only runtime evidence proved:

```text
IMAGE_USER=""
ENTRYPOINT=["/docker-entrypoint.sh"]
CMD=["/usr/sbin/mosquitto","-c","/mosquitto/config/mosquitto.conf"]

/etc/n3wfc4/tls owner=0:0 mode=0700
/etc/n3wfc4/tls/server.key owner=1883:1883 mode=0600
/var/lib/n3wfc4-broker owner=1883:1883 mode=0700

UID1883_READ_ca.pem=false
UID1883_READ_server.pem=false
UID1883_READ_server.key=false
UID1883_READ_dynamic-security.json=true
UID1883_DATA_DIR_WRITE=true
```

The R1 executor incorrectly forced the temporary Broker container to start with
`--user 1883:1883`.

That bypassed the image's default root entrypoint privilege flow. The production TLS directory is intentionally root-owned mode 0700, so a container process forced directly to UID/GID 1883 cannot traverse the TLS bind and cannot read the required TLS files. This is consistent with the observed immediate exit code 1.

The production Compose does not set a Broker `user:` override, and the repository's previously accepted isolated/shadow Broker runners also preserve the image's default entrypoint user flow.

Classification:

```text
R1_ROOT_CLASS=S20_EXECUTOR_TEMP_BROKER_PRIVILEGE_OVERRIDE
R1_ROOT_CAUSE=FORCED_UID1883_BYPASSED_IMAGE_ENTRYPOINT_PRIVILEGE_FLOW
ROOT_CAUSE_STATUS=CONFIRMED
```

## 5. Source repair

The source repair removes `--user 1883:1883` from the temporary Broker `docker run` command.

The Broker image entrypoint is therefore allowed to perform its normal root-start privilege setup. Secret-reading one-shot client commands remain explicitly isolated as:

```text
docker exec --user 0:0 ...
```

for root-only transaction client-config access.

The repair also adds an explicit early-exit check so a future Broker startup failure reports
`transaction_broker_exited_before_ready:<exit-code>` rather than waiting for the generic readiness timeout.

Source repair:

```text
SOURCE_FIX=67ad72411d8e90b2ac0e7d157528b9d4b2ff2beb
REGRESSION_TESTS=cf9d4ca985bb7f150618651480ac9b738c636338
```

## 6. R2 authorization boundary

R1 authorization is permanently consumed.

No R2 live apply may reuse:

```text
N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01
```

R2 requires all of the following before any new live mutation:

- source repair CI PASS;
- fresh source/executor binding;
- fresh T1 read-only preclaim;
- explicit handling of the retained R1 rollback snapshot;
- a new authorization ID;
- new explicit user approval.

Until then:

```text
LIVE_T1_MUTATION=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
PR_MERGE=false
```
