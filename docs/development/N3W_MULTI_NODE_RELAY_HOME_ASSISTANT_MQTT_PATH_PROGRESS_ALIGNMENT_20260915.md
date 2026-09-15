# N3-W Multi-Node Relay + Home Assistant MQTT Path Progress Alignment — 2026-09-15

Status: `CURRENT_PROGRESS_ALIGNMENT`

> Public-safe alignment only. Raw node IDs, host addresses, credentials, private paths, raw MQTT payloads and private runtime evidence are intentionally omitted. Hashes below are public-safe bindings already used by the project.

## 1. Scope

This document aligns the broader N3-W acceptance work that continued after the accepted KF-089 cold/fresh Relay closeout.

The broader North Star is:

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Acceptance sequence:

```text
1. Board B + Board C simultaneously Relay through Board A while B/C have no Wi-Fi
2. Home Assistant entities update from Relay-fed canonical telemetry
3. Live Direct -> Relay automatic failover
4. Relay -> Direct automatic recovery
```

The accepted KF-089 cold/fresh Relay closeout remains frozen PASS and is not reopened by this continuation.

## 2. Repository / execution baseline

This alignment branch was created from exact `main`:

```text
BASE_MAIN=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
```

The deployed Manager source authority remains distinct from repository `main` and is unchanged by this documentation-only alignment.

No board, Home Assistant, Broker, Manager, Dynamic Security or MQTT mutation is performed by this document sync.

## 3. Multi-node simultaneous Relay via Board A — PASS

A fresh preclaim first proved:

```text
AUTHORITATIVE_MANAGER_COUNT=1
AUTHORITATIVE_BROKER_COUNT=1
MANAGER_RUNTIME_CONTINUITY=PASS
BROKER_RUNTIME_CONTINUITY=PASS
DYNSEC_ACCEPTED_STATE_CONTINUITY=PASS
BOARD_C_FRESH_DIRECT_MANAGER_ACCEPTANCE=PASS
BOARD_A_ISOLATED_DIRECT_MANAGER_INGRESS=PASS
PRECLAIM_RELAY_ACCEPTED_COUNT=0
PRECLAIM_RELAY_REJECTED_COUNT=0
PRECLAIM_RELAY_DUPLICATE_COUNT=0
```

The separately authorized physical window then proved simultaneous B+C Relay through A:

```text
WINDOW_ACCEPTED_RELAY_COUNT=82
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_RELAY_ROUTE_COUNT=2
WINDOW_UNIQUE_RELAY_NODE_COUNT=2
WINDOW_UNIQUE_RELAY_GATEWAY_COUNT=1

BOARD_B_ACCEPTED_RELAY_COUNT=40
BOARD_C_ACCEPTED_RELAY_COUNT=42
BOARD_A_DIRECT_DURING_RELAY_COUNT=98
BOARD_B_DIRECT_DURING_RELAY_COUNT=0
BOARD_C_DIRECT_DURING_RELAY_COUNT=0

RELAY_GATEWAY_EQUALS_BOARD_A=true
BOARD_B_RELAY_VIA_A=PROVEN
BOARD_C_RELAY_VIA_A=PROVEN
BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PROVEN
```

Identity continuity was bound by existing public-safe hashes:

```text
BOARD_A_NODE_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
BOARD_B_NODE_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
BOARD_C_NODE_SHA256=73cd4e91562d425ec90acd114b622ee448680b5e011742744eb15fe54e9dd497
RELAY_GATEWAY_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
```

Runtime/security continuity also remained stable:

```text
MANAGER_RUNTIME_CONTINUITY=PASS
BROKER_RUNTIME_CONTINUITY=PASS
DYNSEC_STATE_CONTINUITY=PASS
DYNSEC_SHA256=af6ab6e7c43c9eeb4300d529a4f9acdd097c83f2f2e8c3b780af03926252aeff
```

No board/T1 mutation, MQTT test publish or extra subscriber occurred in this validation.

Therefore:

```text
MAINLINE_ACCEPTANCE_ITEM_1=PASS
```

## 4. Home Assistant Relay entity validation — first oracle failure was harness-only

The first Home Assistant validator assumed exactly one running Home Assistant container on the host and stopped at:

```text
HOME_ASSISTANT_RUNNING_COUNT_2
```

Fresh authority recovery confirmed the already-known dual-HA topology:

1. authoritative FC4 candidate: `fc4-homeassistant`, Compose project `n3wfc4`, service `homeassistant`, private Docker network;
2. independent/legacy runtime: `homeassistant`, separate Compose project `homeassistant`, host network.

The authoritative FC4 selector remains the unique running container satisfying the exact FC4 project/service/name contract. The host-global selector failure is a recurrence of the existing current-runtime authority-discriminator class already covered by KF-071.

A later classifier also exposed a second harness defect: a shell `while ... read` loop allowed `ssh` to inherit loop stdin, so the first SSH call consumed the remaining candidate row and skipped the second Home Assistant runtime. This is an executor stdin-ownership issue consistent with the existing KF-078 guard family. It is not product evidence.

## 5. FC4 Home Assistant state evidence

After exact FC4 Home Assistant rebinding:

```text
FC4_HOME_ASSISTANT_AUTHORITY_COUNT=1
FC4_HOME_ASSISTANT_AUTHORITY_REBIND=PASS
FC4_HOME_ASSISTANT_CONTAINER_NAME=fc4-homeassistant
FC4_HOME_ASSISTANT_PROJECT=n3wfc4
FC4_HOME_ASSISTANT_SERVICE=homeassistant
FC4_HOME_ASSISTANT_RESTART_COUNT=0
```

Board B and Board C each had five registered Home Assistant entities, but their recorder state cursors did not advance during a fresh 90-second window even while Manager accepted 19 Relay frames from each node:

```text
BOARD_B_HA_ENTITY_COUNT=5
BOARD_C_HA_ENTITY_COUNT=5
BOARD_B_WINDOW_RELAY_ACCEPTED_COUNT=19
BOARD_C_WINDOW_RELAY_ACCEPTED_COUNT=19
BOARD_B_HA_STATE_CURSOR_ADVANCED=false
BOARD_C_HA_STATE_CURSOR_ADVANCED=false
```

This recorder-cursor result was not sufficient by itself to prove a Relay-to-HA product failure because the generated discovery set can contain static/diagnostic entities whose state rows need not advance on every canonical payload. The recorder oracle therefore remains a diagnostic input, not an independent MQTT-delivery proof.

## 6. Current Home Assistant authority and MQTT consumption classification

Fresh read-only comparison of both running Home Assistant runtimes showed:

### 6.1 FC4 Home Assistant

The FC4 instance contains A/B/C entity registrations, but all three connectivity entities are stale and `unavailable`; their last recorded updates cluster around the FC4 Home Assistant startup epoch rather than current Manager traffic.

```text
A_ENTITY_REGISTRY_COUNT=5
B_ENTITY_REGISTRY_COUNT=5
C_ENTITY_REGISTRY_COUNT=5
A_CONNECTIVITY=unavailable
B_CONNECTIVITY=unavailable
C_CONNECTIVITY=unavailable
```

During the same period Manager continued accepting current Board A Direct plus Board B/C Relay telemetry.

### 6.2 Independent/legacy Home Assistant

The separate `homeassistant` project has no A/B/C N3-W entities:

```text
A_ENTITY_REGISTRY_COUNT=0
B_ENTITY_REGISTRY_COUNT=0
C_ENTITY_REGISTRY_COUNT=0
```

Its enabled MQTT entry targets port 1883 without username/password and the target is not TCP-connectable from that runtime. It is therefore not the current N3-W Home Assistant authority.

Conclusion:

```text
CURRENT_N3W_HOME_ASSISTANT_AUTHORITY=fc4-homeassistant
SECOND_HOME_ASSISTANT_N3W_AUTHORITY=false
```

## 7. FC4 Home Assistant MQTT target/identity localization

Fresh static contract inspection showed the FC4 Home Assistant MQTT identity itself is correct:

```text
FC4_HA_ENABLED_MQTT_ENTRY_COUNT=1
FC4_HA_MQTT_PORT=8883
FC4_HA_MQTT_USERNAME_PRESENT=true
FC4_HA_MQTT_PASSWORD_PRESENT=true
FC4_HA_MQTT_CLIENT_ID_PRESENT=true
FC4_HA_PORT_MATCHES_BROKER_LISTENER=true
DYNSEC_HOMEASSISTANT_IDENTITY_COUNT=1
DYNSEC_HOMEASSISTANT_IDENTITY_ENABLED=true
FC4_HA_USERNAME_MATCHES_DYNSEC=true
FC4_HA_CLIENT_ID_MATCHES_DYNSEC=true
FC4_HA_MQTT_IDENTITY_CONTRACT_OK=true
```

However the configured Broker target is not resolvable/reachable from the FC4 Home Assistant network namespace:

```text
FC4_HA_CONFIGURED_TARGET_TCP_CONNECTABLE=false
FC4_HA_MQTT_TARGET_CONTRACT_OK=false
```

Meanwhile multiple Docker-internal Broker targets are DNS-resolvable and TCP-connectable from FC4 Home Assistant at 8883, so generic network reachability is not the root cause.

## 8. Broker TLS identity forensic — root cause localized

The first TLS forensic helper incorrectly assumed the Mosquitto image contained `openssl`; it stopped before any mutation with an OCI `openssl not found` error. That stop is a harness dependency defect only and is not TLS/product evidence.

The replacement forensic used the served certificate directly from the FC4 Home Assistant namespace and proved:

```text
BROKER_SERVED_CERT_SHA256=8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb
BROKER_CERT_VALID_NOW=true
BROKER_CERT_VALID_FOR_NEXT_30D=true
BROKER_CERT_DNS_SAN_COUNT=1
BROKER_CERT_IP_SAN_COUNT=0
BROKER_CHAIN_VALID_FROM_HA_WITHOUT_HOSTNAME=true
```

The sole DNS SAN has the same public-safe fingerprint as both the current FC4 Home Assistant target and the current Manager target:

```text
TLS_DNS_SAN_SHA256_16=8203b89b390ddffc
CURRENT_HA_TARGET_SHA256_16=8203b89b390ddffc
MANAGER_RUNTIME_TARGET_SHA256_16=8203b89b390ddffc
```

Therefore the Home Assistant MQTT target value itself is not wrong, and the Broker certificate identity is not wrong.

The exact failure is namespace-dependent name reachability:

```text
TLS_SAN_NAME_FROM_FC4_HA:
  DNS_RESOLVED=false
  TCP_CONNECTABLE=false

BROKER_DOCKER_INTERNAL_NAMES_FROM_FC4_HA:
  DNS_RESOLVED=true
  TCP_CONNECTABLE=true
  TLS_CHAIN_VALID=true
  TLS_VERIFIED=false
  VERIFY_CLASS=HOSTNAME_MISMATCH

BROKER_ENDPOINT_IP_FROM_FC4_HA:
  TCP_CONNECTABLE=true
  TLS_CHAIN_VALID=true
  TLS_VERIFIED=false
  VERIFY_CLASS=HOSTNAME_MISMATCH
```

This closes the root cause as:

```text
ROOT_DOMAIN=INFRASTRUCTURE
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
```

This is not a Relay defect, not a credential defect, not a Dynamic Security defect, not an expired/invalid certificate, and not a generic TCP path failure.

## 9. Minimum repair direction

The minimum structurally correct repair is:

```text
REPAIR_DESIGN=ADD_EXISTING_TLS_DNS_SAN_AS_BROKER_SHARED_NETWORK_ALIAS
```

The repair should make the Broker endpoint on the shared FC4 private Docker network answer to the already-existing TLS DNS SAN while preserving the existing certificate and Home Assistant MQTT entry.

Expected no-change surfaces:

```text
HOME_ASSISTANT_MQTT_ENTRY_CHANGE_REQUIRED=false
BROKER_CERT_ROTATION_REQUIRED=false
BROKER_CA_ROTATION_REQUIRED=false
HOME_ASSISTANT_CREDENTIAL_CHANGE_REQUIRED=false
DYNSEC_MUTATION_REQUIRED=false
MANAGER_CONFIGURATION_CHANGE_REQUIRED=false
```

Expected mutation surface:

```text
BROKER_NETWORK_ENDPOINT_MUTATION_REQUIRED=true
DURABLE_COMPOSE_REPAIR_REQUIRED=true
BROKER_RECREATE_OR_ENDPOINT_REATTACH_REQUIRED=true
```

No mutation authorization has been granted for this repair yet.

Before any live change, a fresh repair preclaim must prove:

- exact raw equality of the TLS SAN, FC4 Home Assistant configured target and Manager runtime target;
- SAN is not already an alias/DNS name on the Broker shared-network endpoint;
- SAN is Docker-DNS alias-safe;
- exact Compose source authority and alias-only intended delta;
- current 8883 host publication/runtime mapping remains part of the required post-mutation acceptance;
- Broker data, TLS material and Dynamic Security state are preserved;
- Manager and Home Assistant are non-target services;
- exact rollback to the current Broker/network state is available.

## 10. Mainline status after this alignment

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=BLOCKED_BY_HA_BROKER_TLS_DNS_BINDING
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=PENDING
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

The accepted simultaneous Relay proof must not be reopened or relabelled as failed merely because the downstream Home Assistant MQTT consumer cannot currently resolve the certificate-authoritative Broker name.

## 11. Regression guards added by this investigation

- Home Assistant authority must be selected by exact current runtime lineage, not host-global service-name cardinality.
- SSH invoked inside a shell read-loop must not inherit the loop input unless it is the explicit stdin owner; use explicit stdin ownership or `ssh -n` for read-only commands.
- Recorder cursor movement is not a sufficient generic oracle for MQTT delivery when the discovery entity set contains static/diagnostic values.
- MQTT target validation must occur inside the consuming runtime's own network namespace.
- TCP reachability and TLS identity verification are separate gates; successful TCP must not be promoted to a TLS-valid target.
- Never disable TLS hostname verification to make an internal Docker name work.
- A durable Broker target used by a bridge-network Home Assistant must have a usable intersection between Docker DNS authority and Broker certificate SAN authority.
- If the already-configured target equals the existing valid certificate SAN but that name is not resolvable in the Home Assistant namespace, prefer restoring network-name binding over rotating credentials or weakening TLS.
- Broker network attachment/alias changes are runtime-authority changes and require exact Compose binding, preservation/rollback, and post-recreate 8883 publication checks.
- Diagnostic executors must not assume optional tools such as `openssl` exist inside minimal production images; required parser/probe dependencies must be preflighted or supplied from a separately verified runtime.

## 12. Current ONE gate

```text
CURRENT_ONE_GATE=FC4_HOME_ASSISTANT_BROKER_TLS_SAN_NETWORK_ALIAS_REPAIR_PRECLAIM
MUTATION_AUTHORIZATION_GRANTED=false
```

No live Broker/network mutation, Home Assistant reconfigure, certificate rotation, credential rotation or DynSec change is authorized by this alignment document.
