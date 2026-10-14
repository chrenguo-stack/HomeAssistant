# N3-W T1 S20 production three-service credential handoff and deployment preflight R2 closure

Date: 2026-10-10
Status: CLOSED_PASS
Repository: chrenguo-stack/HomeAssistant
PR: #541, OPEN DRAFT
SOURCE_HEAD=a6eeddb51d0ace3310ec069832cc0abdf01a7cc3
MAIN_EXACT=d423211b6196c2f2f0f01dff072c4f877fbe58ee
AUTHORIZATION=READ_ONLY
T1_MUTATION=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
MERGE=false

## Closure summary

S20 production three-service credential handoff and deployment preflight R2 is CLOSED_PASS.

This closure combines two independent evidence domains:

1. exact source/deployment binding at PR #541 head;
2. fresh T1 host read-only rebind performed by the operator.

No production credential was created, no Broker/container/service was started, no host MQTT port was opened, no secret value was read, and no board was accessed.

## Exact source authority

```text
MAIN_EXACT=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541_STATE=OPEN_DRAFT
PR541_HEAD=a6eeddb51d0ace3310ec069832cc0abdf01a7cc3

N3W_BROKER_INGRESS_GUARD_CI=PASS:38044419886
N3W_T1_DEPLOYMENT_GATE_CI=PASS:38044419722
N3W_T1_S20_PRODUCTION_IMAGE_BINDING_CI=PASS:38044419646
N3W_T1_HA_BOOTSTRAP_ISOLATED_CI=PASS:38044419750
PUBLIC_REPOSITORY_SAFETY_CI=PASS:38044419654
GREENHOUSE_MANAGER_CI=PASS:38044419672
```

The repository now contains and validates the real clean-product production deployment authority:

- `infra/n3w-t1/production/docker-compose.yml`
- `infra/n3w-t1/production/image-lock.json`
- `infra/n3w-t1/production/homeassistant-configuration.yaml`
- `infra/n3w-t1/systemd/n3wfc4-services-activation.service`
- `tools/n3w_t1_broker_authenticated_readiness.py`

The deployment gate renders the repository production Compose and validates it directly rather than relying only on a synthetic fixture.

## Three-service consumer binding

### Manager

```text
ROLE_AND_CLIENT_ID_SOURCE=BOUND
USERNAME=ghs_greenhouse_manager
CLIENT_ID=gh-manager-greenhouse
PASSWORD_FILE_TARGET=/run/secrets/gh_manager_mqtt_password
PRODUCTION_IMAGE=local/greenhouse-manager:s20-511db028
IMAGE_SOURCE_SHA=511db028780988a7c07cb9342c8be507380bae0f
IMAGE_ID=sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1
TARGET_PLATFORM=linux/arm64
RUNTIME_UID_GID=999:999
SECRET_MOUNT_READ_ONLY=true
INLINE_PASSWORD_FORBIDDEN=true
```

### Provisioning

Provisioning is a distinct Broker identity consumed by the Manager product runtime, not a fourth service container.

```text
ROLE_AND_CLIENT_ID_SOURCE=BOUND
USERNAME=ghs_greenhouse_provisioning
CLIENT_ID=gh-provisioning-greenhouse
PASSWORD_FILE_TARGET=/run/secrets/gh_n3w_provisioning_mqtt_password
CONSUMER=greenhouse-manager
SECRET_MOUNT_READ_ONLY=true
SECRET_DISTINCT_FROM_MANAGER=true
```

### Home Assistant

```text
ROLE_AND_CLIENT_ID_SOURCE=BOUND
USERNAME=ghs_greenhouse_homeassistant
CLIENT_ID=gh-homeassistant-greenhouse
PASSWORD_FILE_TARGET=/run/secrets/gh_homeassistant_mqtt_password
BOOTSTRAP_METADATA_TARGET=/run/n3w/ha-mqtt-bootstrap.json
PRODUCTION_IMAGE=ghcr.io/home-assistant/home-assistant:2026.10.0@sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
TARGET_PLATFORM=linux/arm64
SECRET_MOUNT_READ_ONLY=true
OFFICIAL_CONFIG_FLOW_ONLY=true
DIRECT_STORAGE_EDIT=false
ISOLATED_FIRST_BOOT_AND_RECREATE_ACCEPTANCE=PASS
```

Production Compose keeps Manager and Home Assistant in host network mode, while Broker owns the two project networks and publishes local HA MQTT only on `127.0.0.1:1883` plus guarded TLS on `0.0.0.0:8883`.

The application activation unit requires the Broker activation owner and runs an authenticated MQTT v5 readiness probe before starting Manager/Home Assistant.

## Fresh T1 read-only rebind

Operator fresh read-only evidence:

```text
REMOTE_UID=0
ARCH=aarch64
KERNEL=6.18.26-ophub
ARMBIAN_BOARD=S912-Phicomm-T1
ARMBIAN_VERSION=26.05.0
ARMBIAN_BRANCH=current
DOCKER_SERVER_VERSION=29.7.1

DOCKER_CONTAINER_COUNT=0
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_CURRENT_SORTED_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

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

REAL_DYNSEC_STAT=1883:1883:600
S18_BACKUP_STAT=0:0:600
BROKER_CONFIG_STAT=0:0:644

SECRETS_READ=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
S20_T1_READONLY_RESULT=PASS
```

The current sorted Docker volume-set SHA256 is a new baseline authority created in this gate. S19 proved the count and preservation of the 45-volume set but did not archive a comparable prior set hash, so this closure does not retroactively claim a byte-for-byte name-set comparison with S19.

## Scope interpretation

This PASS proves that the source-side production consumers, exact ARM64 images, secret-file targets, Compose binding, activation/readiness ordering, and current T1 host safety guards are sufficiently bound to request the next explicit mutation authorization.

It does not prove live production Manager/Home Assistant secret mounts because those production services are intentionally not running yet. That runtime proof belongs to the future authorized deployment/post-start acceptance and must not be inferred from this preflight.

## Structured closure

```text
=== N3W T1 S20 SERVICE CREDENTIAL HANDOFF READONLY CLOSURE ===
EXECUTION_ID=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT_R2_20261010_01
AUTHORIZATION=READ_ONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
MAIN_EXACT_REBIND=PASS:d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541_STATE_AND_EXACT_HEAD=PASS:OPEN_DRAFT@a6eeddb51d0ace3310ec069832cc0abdf01a7cc3
SOURCE_PLAN_BOUND=PASS
FINAL_PRODUCTION_COMPOSE_SOURCE=PASS
REAL_REPOSITORY_COMPOSE_GATE=PASS
ARM64_IMAGE_BINDING=PASS
AUTHENTICATED_BROKER_READINESS_SOURCE=PASS
T1_HOST_FRESH_READONLY_REBIND=PASS
ARMBIAN_SSH_DOCKER_GUARDS_PRESERVED=PASS
DOCKER_VOLUMES_45_PRESERVED=PASS_COUNT_AND_CURRENT_BASELINE_HASH
DOCKER_VOLUME_CURRENT_SORTED_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
TWO_PROJECT_NETWORKS_EMPTY=PASS
GUARD_FIRST_JUMPS_LAST_DROP=PASS
REAL_DYNSEC_SHA_MATCH=PASS
S18_BACKUP_SHA_MATCH=PASS
BROKER_CONFIG_SHA_MATCH=PASS
BROKER_STOPPED=PASS
HOST_8883_NOT_PUBLISHED=PASS
MANAGER_ROLE_AND_CLIENT_ID_BOUND=PASS_SOURCE
MANAGER_RUNTIME_UID_SECRET_FILE_MOUNT_CONSUMER=PASS_SOURCE_DEPLOYMENT_BINDING
PROVISIONING_ROLE_AND_CLIENT_ID_BOUND=PASS_SOURCE
PROVISIONING_SEPARATE_SECRET_FILE_CONSUMER=PASS_SOURCE_DEPLOYMENT_BINDING
HA_ROLE_AND_CLIENT_ID_BOUND=PASS_SOURCE
HA_FRESH_MQTT_SECRET_FILE_AND_INTEGRATION_CONSUMER=PASS_SOURCE_PLUS_ISOLATED_RUNTIME
LIVE_PRODUCTION_SECRET_MOUNTS=NOT_YET_APPLICABLE_SERVICES_NOT_DEPLOYED
SECRETS_READ=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
S20_PREFLIGHT_RESULT=PASS
S20_FAILURE_CLASS=NONE
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=true
NEXT_ROUTE=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_DESIGN_AND_EXPLICIT_AUTHORIZATION_20261010_01
STOP=true
=== END ===
```

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_DESIGN_AND_EXPLICIT_AUTHORIZATION_20261010_01
GATE_MODE=DESIGN_PREEXECUTION
LIVE_MUTATION=false
NEW_EXPLICIT_AUTHORIZATION_REQUIRED=true
```

The next gate may prepare the exact atomic transaction, rollback/reconciliation rules, secret ownership/install order, and post-write evidence plan. It must STOP before creating production clients, generating/placing production passwords, starting Broker, publishing 1883/8883, starting Manager/Home Assistant, or changing T1 until a new explicit authorization is granted.
