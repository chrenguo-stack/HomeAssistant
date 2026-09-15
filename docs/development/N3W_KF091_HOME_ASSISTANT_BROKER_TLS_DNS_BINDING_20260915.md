# KF-091 — FC4 Home Assistant / Broker TLS DNS Binding

Date: 2026-09-15  
Status: `OPEN`  
Primary domain: `INFRASTRUCTURE`

## Problem

The current FC4 Home Assistant runtime has the correct dedicated MQTT username/client ID, the correct TLS listener port, and a Broker target whose public-safe fingerprint exactly matches the Broker certificate's sole DNS SAN and the current Manager target.

However, that certificate-authoritative DNS name is not resolvable from the FC4 Home Assistant private Docker network namespace.

Other Docker-internal Broker names are resolvable and TCP-connectable on 8883, and the Broker certificate chain validates, but full TLS verification fails with `HOSTNAME_MISMATCH` because those internal names are not covered by the certificate SAN.

## Proven non-causes

```text
RELAY_SPECIFIC_FAILURE=false
HOME_ASSISTANT_MQTT_TARGET_VALUE_CORRECT=true
HOME_ASSISTANT_MQTT_IDENTITY_CORRECT=true
BROKER_TLS_CERTIFICATE_VALID=true
BROKER_CERT_VALID_FOR_NEXT_30D=true
BROKER_CA_CHAIN_VALID=true
BROKER_TCP_REACHABILITY_FROM_FC4_HA=true
CREDENTIAL_ROTATION_REQUIRED=false
DYNSEC_MUTATION_REQUIRED=false
```

## Root cause

```text
ROOT_DOMAIN=INFRASTRUCTURE
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
```

The durable Broker endpoint on the shared FC4 private network does not currently expose a Docker DNS alias equal to the existing TLS certificate DNS SAN.

## Minimum repair direction

```text
REPAIR_DESIGN=ADD_EXISTING_TLS_DNS_SAN_AS_BROKER_SHARED_NETWORK_ALIAS
HOME_ASSISTANT_MQTT_ENTRY_CHANGE_REQUIRED=false
BROKER_CERT_ROTATION_REQUIRED=false
BROKER_CA_ROTATION_REQUIRED=false
HOME_ASSISTANT_CREDENTIAL_CHANGE_REQUIRED=false
DYNSEC_MUTATION_REQUIRED=false
MANAGER_CONFIGURATION_CHANGE_REQUIRED=false
BROKER_NETWORK_ENDPOINT_MUTATION_REQUIRED=true
DURABLE_COMPOSE_REPAIR_REQUIRED=true
```

Before live repair, exact preclaim must prove:

- raw equality of TLS SAN, current FC4 Home Assistant target and current Manager target;
- SAN is absent from the Broker shared-network alias/DNS authority;
- SAN is syntactically safe for Docker DNS alias use;
- exact current Compose source and network attachment authority;
- alias-only intended delta;
- Broker data/TLS/DynSec preservation;
- Manager and Home Assistant remain non-target services;
- accepted 8883 host publication/runtime mapping remains present after any recreate or endpoint reattach;
- exact rollback to the current Broker/network state.

No live mutation is authorized by this issue record.

## Regression guard

For any service consuming Broker TLS from a container network namespace:

1. validate Broker target DNS/TCP from the consumer's exact network namespace;
2. validate the TLS certificate chain independently from hostname verification;
3. require full TLS hostname verification for the chosen target;
4. require a non-empty intersection between Docker DNS authority and certificate SAN authority;
5. never disable hostname verification to compensate for an internal-name/SAN mismatch;
6. do not rotate credentials, DynSec identity or certificates when the proven defect is only network-name binding;
7. Broker alias/network changes require exact Compose binding, rollback, non-target continuity and post-recreate publication checks.

## Related existing guards

The investigation also reproduced existing harness classes and does not allocate new IDs for them:

- KF-071: host-global Home Assistant selector falsely assumed only one running Home Assistant runtime;
- KF-078: SSH inherited a shell loop's stdin and consumed the remaining candidate row;
- executor dependency preflight: an early TLS forensic incorrectly assumed the minimal Mosquitto image contained `openssl`;
- oracle separation: Home Assistant recorder cursor non-advancement alone was insufficient to classify MQTT delivery for static/diagnostic discovery entities.

Detailed current evidence and broader route alignment:

`docs/development/N3W_MULTI_NODE_RELAY_HOME_ASSISTANT_MQTT_PATH_PROGRESS_ALIGNMENT_20260915.md`
