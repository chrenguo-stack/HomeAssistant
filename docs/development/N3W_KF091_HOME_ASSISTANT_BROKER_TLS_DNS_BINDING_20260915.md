# KF-091 — FC4 Home Assistant / Broker TLS DNS Binding

Date: 2026-09-15  
Status: `CLOSED_PASS`  
Primary domain: `INFRASTRUCTURE`

## Problem

The FC4 Home Assistant MQTT target, current Manager Broker target, and Broker certificate's sole DNS SAN were the same authority. The certificate and CA chain were valid, but that certificate-authoritative name was not resolvable from the FC4 Home Assistant Docker namespace. Alternate Docker-internal names were reachable but failed full hostname verification.

## Proven root cause

```text
ROOT_DOMAIN=INFRASTRUCTURE
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
```

The durable Broker endpoint on the shared FC4 private network lacked a Docker DNS alias equal to the already-correct TLS DNS SAN.

## Proven non-causes

```text
RELAY_SPECIFIC_FAILURE=false
HOME_ASSISTANT_MQTT_TARGET_VALUE_CORRECT=true
HOME_ASSISTANT_MQTT_IDENTITY_CORRECT=true
BROKER_TLS_CERTIFICATE_VALID=true
BROKER_CA_CHAIN_VALID=true
CREDENTIAL_ROTATION_REQUIRED=false
DYNSEC_MUTATION_REQUIRED=false
MANAGER_CONFIGURATION_CHANGE_REQUIRED=false
```

## Accepted repair

```text
AUTHORIZATION=FC4_HOME_ASSISTANT_BROKER_TLS_SAN_ALIAS_REPAIR_MUTATION_20260915_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
RESULT=PASS
```

Repair design:

```text
REPAIR_DESIGN=ADD_EXISTING_TLS_DNS_SAN_AS_BROKER_SHARED_NETWORK_ALIAS
```

The repair changed only the durable Broker network alias and recreated the Broker exactly once.

```text
COMPOSE_SOURCE_PRE_SHA256=56f004d4b1741ea7e868de7aa5491faa213b56c87864cc19deeadd5f465429db
COMPOSE_SOURCE_POST_SHA256=d3a2bb681db523d4414e64fd26d49074d76c90ac5265493f18ec760494472f60
BROKER_RECREATE_COUNT_EXACT=1
BROKER_IMAGE_UNCHANGED=true
BROKER_NETWORK_ATTACHMENT_SET_UNCHANGED=true
BROKER_8883_PUBLICATION_UNCHANGED=true
BROKER_CA_UNCHANGED=true
BROKER_CERT_UNCHANGED=true
DYNSEC_SHA256_UNCHANGED=true
MANAGER_CONTAINER_ID_UNCHANGED=true
MANAGER_RESTART_COUNT_UNCHANGED=true
HOME_ASSISTANT_CONTAINER_ID_UNCHANGED=true
HOME_ASSISTANT_RESTART_COUNT_UNCHANGED=true
HOME_ASSISTANT_MQTT_ENTRY_CHANGE=false
HOME_ASSISTANT_CONFIG_MUTATION=false
HOME_ASSISTANT_CREDENTIAL_CHANGE=false
MANAGER_CONFIGURATION_MUTATION=false
BOARD_MUTATION=false
```

Post-repair proof from the exact FC4 Home Assistant namespace:

```text
FC4_HA_TLS_SAN_DNS_RESOLVED=true
FC4_HA_TCP_8883_CONNECTABLE=true
FC4_HA_TLS_CHAIN_VERIFIED=true
FC4_HA_TLS_HOSTNAME_VERIFIED=true
HA_MQTT_8883_SESSION_OBSERVED=true
MANAGER_8883_SESSION_RECOVERED=true
```

Therefore the Docker-DNS/TLS-identity blocker is closed.

## Regression guard

For Broker TLS consumers in container namespaces:

1. validate target DNS/TCP from the exact consumer namespace;
2. validate CA-chain and hostname verification separately;
3. require full hostname verification for the chosen target;
4. require an intersection between Docker DNS authority and certificate SAN authority;
5. never disable hostname verification to compensate for internal-name/SAN mismatch;
6. do not rotate credentials, DynSec identity, or certificates when the defect is only network-name binding;
7. Broker alias/network changes require exact Compose binding, rollback, non-target continuity, and post-recreate publication checks;
8. distinguish raw-file SHA from any aggregate/meta hash oracle before mutation.

## Closure boundary

KF-091 closure proves Home Assistant/Broker TLS transport recovery. It does not itself prove the broader Relay-only entity-update acceptance item. Subsequent field evidence moved the active blocker to KF-092 firmware Relay delivery feedback.

Current authority:

- `docs/development/N3W_CURRENT_STATE.md`
- `docs/development/N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_DEFECT_20260915.md`
