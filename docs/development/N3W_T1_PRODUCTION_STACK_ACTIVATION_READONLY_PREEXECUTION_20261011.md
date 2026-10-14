# N3-W T1 production stack activation read-only preexecution

Date: 2026-10-11

Status: PREEXECUTION_READY / LIVE_ACTIVATION_NOT_AUTHORIZED

PR: #541 OPEN DRAFT

## 1. Entry authority

S20 three-service production secret handoff is CLOSED_PASS.

```text
S20_THREE_SERVICE_SECRET_HANDOFF=CLOSED_PASS
R5_TRANSACTION_APPLY=PASS
R5_EXECUTOR_POSTCHECK=PASS
R5_INDEPENDENT_POSTAPPLY_AUDIT=PASS
R5_AUTHORIZATION_CONSUMED=true
R5_REPLAY=false
```

Closure authority:
`docs/development/N3W_T1_S20_R5_POSTAPPLY_INDEPENDENT_READONLY_CLOSURE_20261011.md`.

The next stage must not replay the R5 transaction. It consumes the already-created service identities and secret bundle only.

## 2. Exact source authority

The current tested source/workflow authority remains:

```text
SOURCE_HEAD=1ecc12ded60c7ea53e0af94722a05f3b4f0e4654
```

At preparation time PR #541 head was:

```text
112645310550df500a4d3e9ea9a1291b5471e2cd
```

Exact compare from SOURCE_HEAD to current PR head was ahead-only and documentation-only; no source/workflow drift existed.

Production activation source:

```text
infra/n3w-t1/production/docker-compose.yml
infra/n3w-t1/production/image-lock.json
infra/n3w-t1/production/homeassistant-configuration.yaml
infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/
infra/n3w-t1/broker/mosquitto.conf
infra/n3w-t1/systemd/n3wfc4-broker-activation.service
infra/n3w-t1/systemd/n3wfc4-services-activation.service
infra/n3w-t1/systemd/n3wfc4-broker-ingress-guard.service
infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
infra/n3w-t1/install-systemd-persistence.sh
infra/n3w-t1/broker-activation.env.example
tools/n3w_t1_broker_authenticated_readiness.py
tools/n3w_t1_clean_product_deployment_gate.py
```

## 3. Frozen production image authority

```text
MANAGER_IMAGE=local/greenhouse-manager:s20-511db028
MANAGER_IMAGE_ID=sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1
MANAGER_RUNTIME_UID_GID=999:999

HOMEASSISTANT_IMAGE=ghcr.io/home-assistant/home-assistant:2026.10.0@sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
HOMEASSISTANT_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879

BROKER_IMAGE=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine@sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
BROKER_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
```

The R5 temporary-Broker source-tag image binding is not a substitute for these production image-lock IDs. This gate must read the exact digest/tag references on T1 and report present/missing/mismatch separately.

## 4. Frozen post-S20 live baseline

```text
DOCKER_CONTAINER_COUNT=0
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

PROJECT_NETWORKS_EMPTY=true
HOST_MQTT_LISTENERS=0
INGRESS_GUARD_EXACT=true

POSTAPPLY_DYNSEC_SHA256=95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a
PRODUCTION_SERVICE_CLIENTS=3
PRODUCTION_SERVICE_ROLES=3
PRODUCTION_NODE_CLIENTS=0
PRODUCTION_SECRET_BUNDLE=VERIFIED

PRODUCTION_BROKER_STARTED=false
PRODUCTION_MANAGER_STARTED=false
PRODUCTION_HOMEASSISTANT_STARTED=false
```

## 5. Read-only preexecution questions

The T1 read-only preexecution must classify:

1. whether the exact three production images are already local with the frozen image IDs;
2. whether production source/install targets already exist, are absent, or contain unexpected prior content;
3. whether Broker/Services activation units, readiness helper, dispatcher, persistence installer and activation env currently exist and their state;
4. whether Manager and Home Assistant state directories exist and, if present, whether they are empty/non-empty and have safe owner/mode;
5. whether current guard remains active/enabled and host service ports remain unused;
6. whether the S20 secret/DynSec baseline remains exact;
7. available filesystem capacity before any image/source staging.

Missing expected-to-be-staged production files or images are not automatically product failures. They are classified as `STAGING_REQUIRED`. Unexpected running containers, listeners, secret/DynSec drift, unsafe target collisions, or unrelated target content are fail-closed blockers.

## 6. Activation boundary after a PASS

A future live activation authorization may cover one bounded installation/activation transaction, but only after this read-only gate is reviewed.

Expected order:

```text
fresh read-only recheck
-> stage exact source/install files
-> make exact production images available
-> create empty Manager/HA state roots with exact ownership/mode
-> install/validate Compose + env + readiness + systemd material
-> run rendered Compose deployment gate
-> prove ingress guard exact before publication
-> enable persistence without --now
-> start Broker activation
-> authenticated Broker readiness
-> start Manager + Home Assistant activation
-> verify HA MQTT bootstrap / Manager runtime / listeners / container/image bindings
-> reboot-persistence acceptance in a later explicit gate
```

No board access is part of production host activation.

## 7. Current gate

```text
GATE=N3W_T1_PRODUCTION_STACK_ACTIVATION_READONLY_PREEXECUTION_20261011_01
MODE=SOURCE_AND_T1_READ_ONLY
AUTHORIZATION=NOT_REQUIRED_READONLY
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

A PASS from this gate does not authorize activation.
