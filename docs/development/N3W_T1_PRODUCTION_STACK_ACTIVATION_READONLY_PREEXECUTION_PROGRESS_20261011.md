# N3-W T1 production stack activation read-only preexecution progress

Date: 2026-10-11

Status: PARTIAL_PASS / STAGING_REQUIRED / MANAGER_STATE_CLASSIFICATION_REQUIRED

PR: #541 OPEN DRAFT

## 1. Fresh T1 baseline

The operator completed the first read-only production-activation preexecution probe.

```text
REMOTE_HOST=armbian
REMOTE_ARCH=aarch64
REMOTE_KERNEL=6.18.26-ophub
REMOTE_DOCKER=29.7.1
REMOTE_COMPOSE=5.4.0

CONTAINER_COUNT=0
VOLUME_COUNT=45
VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

NETWORK_PRIVATE_CONTAINERS=0
NETWORK_SERVICES_CONTAINERS=0

TCP1883=0
TCP8883=0
TCP18883=0
TCP8123=0
TCP47112=0
UDP47111=0

GUARD_ACTIVE=active
GUARD_ENABLED=enabled

DYNSEC_SHA256=95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a
R5_SNAPSHOT_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
SECRET_ROOT_STAT=0:0:700
SECRET_FILE_COUNT=11
TRANSACTION_DIR_PRESENT=false
```

This matches the S20 post-apply closure baseline.

## 2. Production image staging

All three exact production image references are currently absent from T1:

```text
MANAGER_IMAGE_STATE=ABSENT
HOMEASSISTANT_IMAGE_STATE=ABSENT
BROKER_IMAGE_STATE=ABSENT
```

This is classified as:

```text
PRODUCTION_IMAGE_STATE=STAGING_REQUIRED
PRODUCT_FAILURE=false
```

No image pull/load is authorized by this read-only gate.

## 3. Production deployment material staging

The following production targets are currently absent:

```text
/opt/HomeAssistant
/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml
/opt/HomeAssistant/infra/n3w-t1/production/image-lock.json
/opt/HomeAssistant/infra/n3w-t1/production/homeassistant-configuration.yaml
/opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf
/etc/n3wfc4/docker-compose.yml
/etc/n3wfc4/docker-compose.env
/etc/n3wfc4/broker-activation.env
/usr/local/sbin/n3w-t1-broker-authenticated-readiness
/usr/local/sbin/n3w-broker-systemd-persistence-install
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
```

Activation-related units are also not installed:

```text
n3wfc4-broker-activation.service=not-found
n3wfc4-services-activation.service=not-found
n3wfc4-broker-certificate-lifecycle.timer=not-found
```

The existing ingress guard remains active/enabled and is the only retained systemd safety authority.

Classification:

```text
PRODUCTION_SOURCE_INSTALL_STATE=STAGING_REQUIRED
INGRESS_GUARD_PRESERVED=true
PRODUCT_FAILURE=false
```

## 4. Manager state root needs independent classification

Unexpected relative to the earlier S5 empty-host statement:

```text
/var/lib/greenhouse-manager
STATE=DIRECTORY
STAT=0:0:711
TOPLEVEL_COUNT=8
```

The production Compose binds this path read-write into a Manager process running as UID/GID 999:999.

The current evidence does not establish whether these eight entries are the intended fresh system/manager identity state created by later clean-product stages, or an unsafe collision/residual. The directory must not be deleted, chowned, or treated as empty by inference.

```text
MANAGER_STATE_CLASSIFICATION=REQUIRED
MANAGER_STATE_MUTATION=false
ACTIVATION_READY=false
```

The next operation is a bounded read-only inventory of this root: relative names, file types, owner/mode, sizes, hashes for regular files, symlink detection, and SQLite metadata/integrity where applicable. No file content or secret value may be printed.

## 5. Home Assistant state

```text
/var/lib/n3wfc4-homeassistant=ABSENT
```

This is expected for fresh activation and is classified `STAGING_REQUIRED`, not failure.

## 6. Capacity

```text
ROOT_AVAILABLE_KIB=6270568
ROOT_USED_PERCENT=56
```

Capacity is not yet declared sufficient because the exact production image transfer/load footprint must be checked against the frozen artifacts before mutation.

## 7. Current gate

```text
GATE=N3W_T1_PRODUCTION_STACK_ACTIVATION_READONLY_PREEXECUTION_20261011_01
BASELINE_GUARDS=PASS
S20_STATE=PASS
PRODUCTION_IMAGES=STAGING_REQUIRED
PRODUCTION_INSTALL_FILES=STAGING_REQUIRED
HOMEASSISTANT_STATE_ROOT=STAGING_REQUIRED
MANAGER_STATE_CLASSIFICATION=REQUIRED
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

Next bounded read-only subgate:

```text
NEXT_ONE_GATE=N3W_T1_PRODUCTION_STACK_MANAGER_STATE_READONLY_CLASSIFICATION_20261011_01
```
