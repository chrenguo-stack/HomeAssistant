# N3-W T1 production stack staging live authorization preexecution

Date: 2026-10-11

Status: SUCCESSOR_PREEXECUTION_PREPARED / AUTHORIZATION_NOT_GRANTED

PR: #541 OPEN DRAFT

## 1. Purpose

This gate stages the production T1 software without starting any production service.

It consumes the closed KF-104 source contract and prepares the host for a later, separately authorized Broker/Manager/Home Assistant activation.

```text
PREDECESSOR_AUTHORIZATION_ID=
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
PREDECESSOR_AUTHORIZATION_STATE=CONSUMED_FAILED_ROLLBACK_PASS
PREDECESSOR_REPLAY_FORBIDDEN=true

AUTHORIZATION_ID=
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02

AUTHORIZATION_STATE=NOT_GRANTED
ONE_SHOT=true
REPLAY_FORBIDDEN=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

## 2. Required fresh preflight

Immediately before any mutation, the execution must re-prove:

```text
containers=0
docker_volume_count=45
docker_volume_set_sha256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
project_network_container_counts=0/0
tcp_1883=0
tcp_8883=0
tcp_18883=0
tcp_8123=0
tcp_47112=0
udp_47111=0
guard=active+enabled
dynsec_sha256=95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a
secret_file_count=11
transaction_dir_absent=true
preserved_system_identity_claim_count=1
manager_database_quick_check=ok
manager_business_rows=0
manager_provenance_rows=1
manager/registration.sqlite3=empty root:root:0755 directory
n3w_state_root=absent
production_images=absent
production_services=stopped
```

Any drift is STOP.

## 3. Authorized mutations

Only after explicit authorization, one transaction may:

1. remove exactly the empty directory
   `/var/lib/greenhouse-manager/manager/registration.sqlite3`
   after rechecking type, owner, mode and child count;
2. create `/var/lib/greenhouse-manager/n3w` as `999:999:0700`;
3. load the exact frozen Manager image artifact:
   - artifact run `38040433177`;
   - artifact ID `11665219740`;
   - tar SHA256 `2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081`;
   - classic-store config digest `sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1`;
   - containerd/OCI target digest `sha256:abd9560c978b69429eea734df216664ea643ed762a77777dcb816f5d537afad6`;
4. run `tools/n3w_t1_production_manager_state_prepare.py` in the exact Manager image with `--network none`;
5. pull only the exact locked ARM64 Home Assistant and Broker image references from `infra/n3w-t1/production/image-lock.json`;
6. stage the exact production source/configuration material under `/opt/HomeAssistant`;
7. stage `/etc/n3wfc4/docker-compose.yml`, an empty private `docker-compose.env`, and private `broker-activation.env`;
8. stage the authenticated Broker readiness helper and Broker/Services activation systemd unit files;
9. create the empty Home Assistant state root needed for first activation;
10. run `systemctl daemon-reload`;
11. render and validate the production Compose and image lock;
12. perform a final stopped-state audit.

## 4. Explicitly forbidden in this authorization

This staging authorization does not permit:

```text
systemctl start n3wfc4-broker-activation.service
systemctl start n3wfc4-services-activation.service
docker compose up
Broker/Manager/Home Assistant production start
systemctl enable activation units
systemctl enable certificate timer
install or activate NetworkManager dispatcher
reboot
board access
PR merge
R5 replay
DynSec mutation
secret regeneration
TLS key/certificate replacement
guard replacement
```

The NetworkManager dispatcher is intentionally excluded because its current source can call `systemctl start n3wfc4-broker-activation.service` on eth0 events. Installing it during a "staging only" transaction would violate the no-service-start boundary.

Persistence enablement and dispatcher installation are deferred until production activation has independently passed.

## 5. Post-staging acceptance

A successful transaction must prove:

```text
containers=0
production listeners remain absent
guard remains active+enabled
DynSec SHA unchanged
secret bundle unchanged
manager database SHA unchanged
manager business rows remain 0
legacy empty registration directory absent
n3w state root=999:999:0700
replay state=empty
relay authorization state=empty
relay key directory=empty
exact Manager image present
exact HA image present
exact Broker image present
production source/config hashes exact
Broker activation unit=inactive+disabled
Services activation unit=inactive+disabled
dispatcher=absent
production_service_start=false
board_access=false
```

## 6. Rollback

If any authorized staging step fails, rollback must occur before leaving the transaction:

- remove only staging-created production files/units;
- remove staging-created Home Assistant state root only if still empty;
- remove the staging-created `n3w/` state only after proving it contains no product node state;
- restore the exact empty `manager/registration.sqlite3` directory as `root:root:0755` if it was removed;
- remove only images proven absent in the fresh preflight and introduced by this transaction;
- run `systemctl daemon-reload`;
- re-prove 0 containers and no production listeners;
- never touch S20 DynSec, secrets, TLS or retained restore identity state.

The Manager database must never be rolled back from an inferred copy. Its SHA must remain unchanged throughout the staging transaction.

## 7. Current boundary

```text
SOURCE_REPAIR_CI=PASS
LIVE_STAGING_AUTHORIZATION_REQUIRED=true
PREDECESSOR_AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
PREDECESSOR_AUTHORIZATION_STATE=CONSUMED_FAILED_ROLLBACK_PASS
PREDECESSOR_REPLAY_FORBIDDEN=true
AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
AUTHORIZATION_STATE=NOT_GRANTED
```


## 8. Successor authorization boundary

The predecessor one-shot authorization was consumed by the first staging apply
attempt. That attempt failed closed at the Manager image identity oracle and
completed rollback with zero reported rollback errors.

The successor authorization is intentionally a new identity:

```text
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
```

It is not granted by creation of this document, by CI PASS, by a fresh
preflight, or by the user's prior approval of `..._01`.

Before `..._02` can be claimed:

1. the rotated exact-source payload CI must PASS;
2. the content-addressed payload and repository-owned host wrapper must be
   rebound by artifact ID and SHA256;
3. a fresh T1 read-only preflight with that replacement payload must PASS;
4. the user must explicitly approve `..._02`.

The successor scope remains staging-only. It still does not permit production
service start, unit enablement, dispatcher installation, reboot, board access,
or PR merge.
