# N3-W T1 Core Stack Clean Reference — R3 R2 common-reference baseline closure

Date: 2026-11-01

## 0. Result

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_R2_COMMON_REFERENCE_BASELINE_20261101
RESULT=CLOSED_PASS

PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R2A_CONTROL_HEAD=abeb6c31147bcf249361dcec7e9536eaed6106a6
R2B_CONTROL_HEAD=e15c64ac8f0f5f482a6c8538072031734002a559
R3_OBSERVER_CONTROL_HEAD=da9124fe18774cdb5822f9eb3afee40120cfb04f

REFERENCE_LABEL=R2
REFERENCE_SHA256=89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747

R2_REFERENCE_FINAL=PASS
R3_WORKLOAD_EXECUTED=false
BOARD_ACCESS=false
```

## 1. Exact observer authority

```text
WORKFLOW_RUN=41317600634
WORKFLOW_RESULT=SUCCESS
SOURCE_TEST_COUNT=8
R2A_BYTE_CONTINUITY=PASS
R2B_BYTE_CONTINUITY=PASS

ARTIFACT_ID=13087179158
ARTIFACT_NAME=n3w-t1-clean-reference-r3-observer-da9124fe18774cdb5822f9eb3afee40120cfb04f
ARTIFACT_DIGEST=sha256:473499d10e0487a591e8828312a76036fe438463d3455a8ed74d8eea5f96821b
PACKAGE_MANIFEST_SHA256=fdd9a634435ffa497569dce55c70c19edca365322a8b4214f586a68d68574b0e
```

The exact artifact contained only:

- `tools/n3w_t1_clean_reference_observer.py`
- `tools/n3w_t1_clean_reference_compare.py`

The observer contract is read-only and privacy-safe.

## 2. Collection integrity

Before and after the reference collection:

```text
BOOT_UNCHANGED_DURING_COLLECTION=true
CONTAINERS_UNCHANGED_DURING_COLLECTION=true
PRODUCT_MUTATION_OBSERVED=false
TRANSPORT_RESIDUAL_COUNT=0
BOARD_ACCESS=false
```

The exact reference was captured locally under the operator's R3 evidence directory.
The public repository records only the safe summary and reference SHA-256, not private raw
runtime data.

## 3. Health reference

```text
SYSTEM_STATE=running
FAILED_UNIT_COUNT=0

RUNTIME_SERVICES=broker,homeassistant,manager

MANAGER_CURRENT_AUTHENTICATED=true
HOMEASSISTANT_CURRENT_AUTHENTICATED=true

MANAGER_MQTT_SOCKET_COUNT=1
HOMEASSISTANT_MQTT_SOCKET_COUNT=1

HOMEASSISTANT_HTTP_STATUS=401

HEALTH_OVERALL_PASS=true
```

Systemd accepted state:

```text
n3wfc4-broker-activation.service=enabled+active
n3wfc4-services-activation.service=enabled+active
n3wfc4-broker-ingress-guard.service=enabled+active
n3wfc4-registration-ingress-guard.service=enabled+active
n3wfc4-provision-resume.service=enabled+active
n3wfc4-broker-certificate-lifecycle.timer=enabled+active
n3wfc4-broker-certificate-lifecycle.service=static+inactive
```

## 4. Stable-contract reference

Exact image tags:

```text
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
MANAGER_IMAGE=local/greenhouse-manager:fresh-24382caae4a1
PLATFORM=linux/arm64
```

Stable runtime contract hashes:

```text
BROKER_RUNTIME_CONTRACT_SHA256=7e49a2f83176e2c47ff2cdaa5146810385c817561c60b2d8f82df457ee9bb1e7
HOMEASSISTANT_RUNTIME_CONTRACT_SHA256=9622e596f6429852a3525c5c0e62204a04301a53f2243386340cb6d7aadff76a
MANAGER_RUNTIME_CONTRACT_SHA256=6a6528b6c4ac48500119eb85f1b374d44d8c76a28771997a72c93d31e9360019
```

Fixed config hashes:

```text
COMPOSE_SHA256=9ea58161d5f8e24233bacbfe1f31edd5f6f6c62c272271823788c0c5b59e8357
MOSQUITTO_CONFIG_SHA256=6c8d0f134c26987826cbfd3149cf393249586d74642857c8159862d0005ce59a
HOMEASSISTANT_CONFIGURATION_SHA256=ca966d080c2ca2b5ea9cf509cc95a8e6a78987d33b0b062d00acb39ca7bd8b24
CUSTOM_COMPONENT_TREE_SHA256=451a470c795b3d1ed65058174a474b59bf9baccf684e29b88060982c791e704e
DYNSEC_TOP_LEVEL_KEYS_SHA256=59af50181cddcd17f3eddc38d4cedf360e12d86536c5841633caf350f66b04d8
```

Public certificate hashes:

```text
BROKER_CA_SHA256=0548b02c964afff1b01f58817ec126225ec7f3044eec156732f1b126eb4e3898
BROKER_SERVER_CERT_SHA256=3329adaeca4503f81e9eb13c00c803d928b0cec8af4f52d97281f072a5bc803c
SYSTEM_CA_SHA256=39de7a7fa5f3f6406dddae1523b1b0f0f69ecd8a3023ae22c8883813940ab741
```

SQLite schema reference:

```text
MANAGER_TABLE_COUNT=8
MANAGER_SCHEMA_SHA256=40f10b68870a40f861dee0ceaebf3fd09984135d67c81f51996a7c5ff2de4dd2

RELAY_AUTH_TABLE_COUNT=4
RELAY_AUTH_SCHEMA_SHA256=0b91a4edf4cb5a99c13e0c4b443428063d8a8de6c80d3fd31a4a7b3535b8e21f

REPLAY_TABLE_COUNT=5
REPLAY_SCHEMA_SHA256=46878ae3dee61f3cb2d19a5d69bfa5e49772f250753f3ba6c601bc0b74c000cc
```

## 5. Runtime-variable baseline

Before R3 workload, Manager business tables are empty:

```text
credential_assignments=0
first_registration_attempts=0
node_id_leases=0
pairing_sessions=0
registration_events=0
registration_node_history=0
registrations=0
retirement_outbox=0
```

N3-W runtime stores:

```text
relay_authorization_active_nodes=0
replay_seen=0
replay_state=0
canonical_cursors=0
```

Dynamic Security counts:

```text
clients=4
groups=1
roles=10
```

Home Assistant registry counts:

```text
config_entries=6
devices=3
entities=14
```

These are runtime observations only. They are intentionally not classified as hard invariants
by this closure.

## 6. Important reference gap

The original R1/R2 execution route predated the common observer schema, so a full R1 common
reference does not exist.

```text
R1_FULL_COMMON_REFERENCE_GAP=true
R1_REFERENCE_RECREATION_BY_REDEPLOY=false
R2_COMMON_REFERENCE_AVAILABLE=true
```

The project must not wipe/redeploy T1_B solely to manufacture a historical R1 observation.

## 7. R3 pairing-entry blocker discovered after baseline

Frozen product source contains the standard first-pairing onboarding tool, but that tool requires:

`/var/lib/n3w-t1-provisioning/FACTORY_ACCEPTED.json`

The Clean Reference R1/R2 route did not create that marker.

Old F4 cannot be replayed to create it after R2. Its factory audit requires production activation
units to be stopped and disabled and `production_service_start=false`, whereas the accepted R2
state is intentionally enabled, active and post-reboot.

Therefore:

```text
STANDARD_FIRST_PAIRING_TOOL_PRESENT=true
FACTORY_ACCEPTED_MARKER_CREATED_BY_CLEAN_REFERENCE_ROUTE=false
OLD_F4_REPLAY_SAFE=false
DIRECT_BOARD_PAIRING_READY=false
R3_PAIRING_ENTRY_BLOCKER=FACTORY_ACCEPTED_AUTHORITY_GAP
```

This is a host control-authority gap, not a Board failure.

## 8. Current boundary

```text
R2_COMMON_REFERENCE=CLOSED_PASS
R3=IN_PROGRESS
R3_WORKLOAD_EXECUTED=false
R3_BOARD_WORK_REQUIRES_SEPARATE_GATE=true
R3_PAIRING_ENTRY_BLOCKER=OPEN
A1=NOT_EXECUTED
MERGE=false
```
