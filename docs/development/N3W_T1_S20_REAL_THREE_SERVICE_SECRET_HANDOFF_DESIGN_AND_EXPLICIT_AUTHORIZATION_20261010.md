# N3-W T1 S20 real three-service secret handoff design and explicit authorization

Date: 2026-10-10
Status: DESIGN_CLOSED / EXPLICIT_AUTHORIZATION_PENDING
Repository: chrenguo-stack/HomeAssistant
PR: #541, OPEN DRAFT
DESIGN_SOURCE_HEAD=f75b8ae142c3fee3a1a0bfde56d72956b77ed984
MAIN_EXACT=d423211b6196c2f2f0f01dff072c4f877fbe58ee
LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false

## 1. Purpose

This gate converts the CLOSED_PASS S20 source/T1 read-only preflight into one exact, bounded production transaction design.

The transaction will create exactly three production Broker service identities and the three matching persistent private password consumers:

- Provisioning
- Manager
- Home Assistant

It will not create any node identity. It will not start the production Broker, Manager, or Home Assistant. It will not publish host TCP/1883 or TCP/8883. It will not access any ESP32-C6 board.

No mutation is performed by this design gate. A new explicit authorization is required before the first T1 write.

## 2. Frozen preconditions

The immediately preceding preflight is authoritative:

```text
S20_PREFLIGHT_R2=CLOSED_PASS
SOURCE_HEAD_AT_PREFLIGHT=a6eeddb51d0ace3310ec069832cc0abdf01a7cc3
MAIN_EXACT=d423211b6196c2f2f0f01dff072c4f877fbe58ee

T1_ARCH=aarch64
T1_KERNEL=6.18.26-ophub
T1_ARMBIAN_VERSION=26.05.0
T1_DOCKER_VERSION=29.7.1

DOCKER_CONTAINER_COUNT=0
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SORTED_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
NETWORK_n3wfc4-private_CONTAINER_COUNT=0
NETWORK_n3wfc4-services_CONTAINER_COUNT=0

GUARD_ACTIVE=active
GUARD_ENABLED=enabled
INPUT_FIRST_JUMP=true
DOCKER_USER_FIRST_JUMP=true
INPUT_ANCHOR_COUNT=1
DOCKER_USER_ANCHOR_COUNT=1
GUARD_LAST_DROP=true

HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0

BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
S18_BACKUP_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
```

Every item above must be freshly rechecked immediately before authorization claim. Historical PASS cannot substitute for the preclaim.

## 3. Exact service identity contract

Source authority remains `service_identity_plan.py` generation 1.

```text
SYSTEM_ID=greenhouse
GENERATION=1

SERVICE=provisioning
USERNAME=ghs_greenhouse_provisioning
CLIENT_ID=gh-provisioning-greenhouse
ROLE=gh-service-greenhouse-provisioning
ACL_COUNT=10

SERVICE=manager
USERNAME=ghs_greenhouse_manager
CLIENT_ID=gh-manager-greenhouse
ROLE=gh-service-greenhouse-manager
ACL_COUNT=17

SERVICE=homeassistant
USERNAME=ghs_greenhouse_homeassistant
CLIENT_ID=gh-homeassistant-greenhouse
ROLE=gh-service-greenhouse-homeassistant
ACL_COUNT=9

NODE_CREDENTIAL_COUNT=0
```

The four Dynamic Security defaults remain unchanged:

```text
publishClientSend=false
publishClientReceive=false
subscribe=false
unsubscribe=true
```

No anonymous role/group is created.

## 4. Secret generation and persistent handoff

The source authority is the existing clean credential bundle implementation.

Production destination:

```text
/opt/greenhouse-secrets/mqtt
```

Parent contract:

```text
/opt/greenhouse-secrets
owner=root:root
mode=0700
```

The destination must not exist before the transaction. An existing destination is ambiguity and causes STOP; it is never overwritten.

The bundle generates exactly three independent random passwords and no node password.

Required runtime ownership after generation:

```text
manager/password
owner=999:999
mode=0600
target=/run/secrets/gh_manager_mqtt_password
read_only=true

provisioning/password
owner=999:999
mode=0600
target=/run/secrets/gh_n3w_provisioning_mqtt_password
read_only=true

homeassistant/password
owner=0:0
mode=0600
target=/run/secrets/gh_homeassistant_mqtt_password
read_only=true

homeassistant/mqtt-bootstrap.json
owner=0:0
mode=0600
target=/run/n3w/ha-mqtt-bootstrap.json
read_only=true
```

Manager/Provisioning files use numeric owner `999:999`; no host NSS username lookup is allowed.

No password value may appear in argv, environment output, stdout/stderr, GitHub, shell history, evidence JSON, or documentation.

## 5. Dynamic Security transaction method

The real production Broker remains stopped.

The transaction uses one temporary exact-image Broker only as a local Dynamic Security control engine:

```text
IMAGE=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine@sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
NETWORK=none
HOST_PORT_PUBLICATION=none
AUTO_REMOVE=true
REAL_DYNSEC_DATA_BIND=read-write
BROKER_CONFIG_BIND=read-only
TLS_FILES_BIND=read-only
```

This temporary Broker may listen only inside its isolated container namespace. It does not constitute production Broker activation.

The existing root-only admin password is consumed from:

```text
/etc/n3wfc4/private/dynsec-admin-password
```

The executor may read that secret internally only to construct a mode-0600 temporary Mosquitto client config. It must never print the value or put it into process arguments visible outside that private config.

## 6. Authorization claim point

Before claim, the executor must prove all of the following:

- exact source/executor binding;
- root execution;
- all frozen T1 read-only host guards still match;
- no Docker container exists;
- both project networks remain empty;
- current 45-volume set hash still matches the new S20 baseline;
- host 8883/18883 remain unbound;
- production Broker/DynSec/S18 backup SHA values remain exact;
- admin password file exists with root-only safe permissions;
- production secret destination does not exist;
- target service usernames and roles are absent from current Dynamic Security inventory;
- current Dynamic Security inventory still contains only the existing administrator in the service-client domain;
- no target node credential is created or staged.

Only then:

```text
AUTHORIZATION_CLAIMED=true
```

The claim is immediately before the first filesystem write. Any failure before claim is non-consuming and may be repaired/re-run after source correction. Any failure after claim consumes the authorization.

## 7. First mutation and rollback snapshot

The first mutation is a fresh exact rollback snapshot of current production Dynamic Security state.

Target:

```text
/etc/n3wfc4/private/dynsec-s20-pre-three-service.json
```

Contract:

```text
create-new-only
owner=root:root
mode=0600
source_sha256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
```

If this path already exists, STOP before claim; never overwrite an old transaction snapshot.

The older S18 backup is preserved unchanged and is not used as the automatic rollback target for S20.

## 8. Apply order

After the fresh rollback snapshot:

1. create/verify the private three-service credential bundle;
2. apply numeric ownership `999:999` only to Manager and Provisioning runtime password files;
3. start the temporary network-none Broker with no host publication;
4. authenticate as the existing DynSec administrator using a private temporary config;
5. re-read exact target absence;
6. create Provisioning role then client;
7. create Manager role then client;
8. create Home Assistant role then client;
9. read back only non-secret inventory/ACL metadata;
10. authenticate each new service with its exact username/password/client ID through the isolated Broker;
11. verify wrong client ID is rejected for each service;
12. verify anonymous connection remains rejected;
13. verify no node client exists;
14. stop/remove the temporary Broker;
15. verify real Dynamic Security owner/mode, new SHA, three secret ownerships/modes and unchanged host safety guards.

No application service is started in this gate.

## 9. Success oracle

The transaction is PASS only if all are simultaneously true:

```text
EXACT_SERVICE_CLIENT_COUNT_CREATED=3
EXACT_SERVICE_ROLE_COUNT_CREATED=3
NODE_CLIENT_CREATED=false

PROVISIONING_USERNAME_CLIENT_ID_ROLE=PASS
MANAGER_USERNAME_CLIENT_ID_ROLE=PASS
HOMEASSISTANT_USERNAME_CLIENT_ID_ROLE=PASS

ACL_COUNTS=10,17,9
DEFAULT_ACL_BASELINE_UNCHANGED=true

ALL_THREE_EXACT_CREDENTIAL_AUTH=PASS
ALL_THREE_WRONG_CLIENT_ID_REJECTED=true
ANONYMOUS_REJECTED=true

MANAGER_PASSWORD_OWNER_MODE=999:999:600
PROVISIONING_PASSWORD_OWNER_MODE=999:999:600
HOMEASSISTANT_PASSWORD_OWNER_MODE=0:0:600
HA_BOOTSTRAP_OWNER_MODE=0:0:600

PRODUCTION_BROKER_STARTED=false
HOST_1883_PUBLISHED=false
HOST_8883_PUBLISHED=false
DOCKER_CONTAINER_COUNT_AFTER=0
DOCKER_VOLUME_SET_UNCHANGED=true
TWO_PROJECT_NETWORKS_EMPTY=true
GUARD_UNCHANGED=true
BOARD_ACCESS=false
```

The post-transaction Dynamic Security SHA is expected to change and becomes the new production authority only after all checks PASS.

## 10. Rollback

Any failure after claim triggers one rollback route only:

1. stop/remove the isolated transaction Broker if present;
2. atomically restore the exact S20 pre-transaction Dynamic Security snapshot;
3. restore owner `1883:1883` and mode `0600`;
4. remove only the credential bundle proven to have been created by this transaction;
5. remove `/opt/greenhouse-secrets` only if this transaction created it and it is empty;
6. verify original Dynamic Security SHA restored;
7. verify all three target clients/roles absent;
8. verify no node identity exists;
9. verify no containers/listeners and all host/network/guard baselines remain intact.

The fresh rollback snapshot is retained root-only as transaction evidence unless a later explicit cleanup gate authorizes removal.

If exact rollback cannot be proven:

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
AUTO_RETRY=false
PRODUCTION_BROKER_START_FORBIDDEN=true
STOP=true
```

No second apply attempt is permitted under the consumed authorization.

## 11. Source/executor preparation rule

Because this transaction handles production passwords and production Dynamic Security, it requires a versioned executor and source tests before live apply.

The next authorized gate must first:

- add the exact executor to PR #541;
- add host-only unit tests for preclaim, claim boundary, rollback, ownership and secret-redaction behavior;
- run focused CI;
- fresh rebind T1 read-only state again;
- present the exact executor commit/blob and CI results before executing the claimed mutation.

Source preparation itself is not a T1 mutation and does not consume the live authorization.

If executor source expands the mutation scope described in this document, authorization is invalid and must be requested again.

## 12. Explicit authorization contract

Proposed one-time authorization:

```text
AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01

AUTHORIZED=true only after explicit user approval

AUTHORIZED_MUTATIONS:
- create fresh S20 DynSec rollback snapshot;
- create /opt/greenhouse-secrets parent if absent;
- generate exactly three service credential bundles, zero node credentials;
- chown Manager and Provisioning password files to numeric 999:999;
- run one temporary --network none/no-port exact Broker transaction container;
- add exactly three service roles and three service clients to production Dynamic Security;
- perform isolated positive/negative credential verification;
- on failure, restore exact pre-transaction DynSec and remove only transaction-created credential material.

NOT_AUTHORIZED:
- production Broker activation;
- host 1883 or 8883 publication;
- Manager start;
- Home Assistant start;
- node credential creation;
- Gate F pairing;
- TLS key/certificate replacement;
- firewall mutation;
- Docker volume deletion;
- Armbian/network modification;
- board/USB/serial/flash/NVS/RF access;
- PR merge.

AUTHORIZATION_REPLAY=false
AUTO_RETRY=false
```

## 12A. Explicit authorization received

```text
AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01
USER_APPROVAL=GRANTED
APPROVAL_RECORDED_AT=2026-10-10
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_T1_MUTATION=false
SOURCE_EXECUTOR_COMMIT=3cd66a337cfbb9d5bf3c7f7b335f38a1ca32cc1f
SOURCE_EXECUTOR_BLOB_SHA1=50e3e7bf71c17b206575f47ad4acd91d471ff290
SOURCE_EXECUTOR_SHA256=5258f7d900be50247430365bba178e26e8e9ad7f2b53ebe583ded2bef142ee15
S20_HANDOFF_CI=PASS:38049008257
GREENHOUSE_MANAGER_CI=PASS:38049008261
PUBLIC_REPOSITORY_SAFETY_CI=PASS:38049008219
NEXT_STEP=FRESH_T1_READONLY_PRECLAIM
```

Approval authorizes the bounded live transaction described above, but does not itself claim or consume it. Fresh T1 preclaim remains mandatory before the first write.

## 13. Gate closure

```text
EXECUTION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_DESIGN_AND_EXPLICIT_AUTHORIZATION_20261010_01
DESIGN_RESULT=PASS
SOURCE_PREPARATION_REQUIRED=true
LIVE_MUTATION=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
HOST_1883_PUBLICATION=false
HOST_8883_PUBLICATION=false
BOARD_ACCESS=false
EXPLICIT_AUTHORIZATION_STATUS=PENDING_USER_APPROVAL
READY_TO_REQUEST_EXPLICIT_AUTHORIZATION=true
STOP=true
```

After explicit approval:

```text
NEXT_ONE_GATE=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_SOURCE_PREPARATION_AND_APPLY_20261010_01
```

That successor must complete source/CI/preclaim before claiming and applying the live authorization.
