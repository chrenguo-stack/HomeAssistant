# N3-W Current State

Updated: 2026-09-15
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

KF-089 code/package integration baseline after the clean PR #406 → #407 → #408 sequence:

```text
REPOSITORY=chrenguo-stack/HomeAssistant
KF089_CODE_PACKAGE_INTEGRATION_BASE_MAIN=1bbd4f3f1cfbccaa383d326a28bc972ed4ee202b
KF089_CODE_PACKAGE_INTEGRATION_BASE_TREE=5b9bdc77585f3c1990b4123fccfb84f4d16d281d
```

The accepted KF-089 repair/validation code and execution-package stack is integrated into `main` through the clean integration path:

```text
PR406=MERGED
PR406_HEAD=159e8deabdbbf0f1990c4ecd7e425116a97b1879
PR406_MERGE_COMMIT=d7d9cd9d49f795c71a96c5f28f90cbdd9930c5e2
PR406_POSTMERGE_CI=PASS

PR407=MERGED
PR407_HEAD=55af8ba3a7bb55325f9b430e67a3e08efff1b6f5
PR407_MERGE_COMMIT=9237e1ad1b4cf1850af40599ce173f07b00ad5cd
PR407_POSTMERGE_CI=PASS

PR408=MERGED
PR408_HEAD=c8f4efbdbd0f14fbc0c6c50ac915af06ce34b755
PR408_MERGE_COMMIT=1bbd4f3f1cfbccaa383d326a28bc972ed4ee202b
PR408_POSTMERGE_CI=PASS

ID23_ID24_ID25_ID26_REPOSITORY_INTEGRATION=PASS
MANAGER_RELAY_SOURCE_CONTRACT_INTEGRATION=PASS
```

Historical PR #400 / #403 / #404 remain provenance for the original accepted live packages. The clean integration path above is the authority for what entered `main`; consumed historical live authorizations remain non-replayable.

Repository `main` must always be queried fresh. The fixed SHA above is the KF-089 code/package integration baseline, not a permanent claim about the repository tip after documentation-only descendants. Live acceptance and repository integration remain separate authorities: the live T1 repair and physical Relay acceptance were proven before integration, and the corresponding source/guard package stack is now also present in `main`.

Active architecture authority remains:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current product direction remains:

- provisioned runtime startup does not require an existing Wi-Fi association;
- Direct remains preferred;
- when Direct is unavailable, node-local bounded autonomous Relay discovery is allowed;
- full custom radio-ownership architecture remains deferred unless later evidence requires it.

## Deployed product authorities

Board Schema-v5 authority used by the accepted two-board Relay chain:

```text
BOARD_FIRMWARE_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
BOARD_FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
DIAGNOSTIC_SCHEMA_VERSION=5
```

The deployed Manager runtime authority remains distinct from repository-main source integration:

```text
DEPLOYED_MANAGER_SOURCE=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
LIVE_MANAGER_DYNSEC_REPAIR=PASS
MANAGER_RELAY_SOURCE_CONTRACT_INTEGRATION=PASS
```

ID24 repaired the active live Dynamic Security role in place. ID25 then performed exactly one Manager restart to establish a fresh MQTT subscription cycle. ID26 proved fresh Relay telemetry delivery without further Manager/Broker/DynSec mutation. Integrating the source contract into `main` does not retroactively change the deployed Manager image revision; it makes the corrected contract durable for repository-controlled future materialization.

## KF-089 final Relay acceptance

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
BOARD_SIDE_RELAY_CHAIN=PROVEN
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
```

The final ID26 fresh window was isolated by a Board-B-off baseline:

```text
PREWINDOW_ACCEPTED_RELAY_COUNT=0
PREWINDOW_QUIESCENCE_SECONDS_OBSERVED=10.003290081047453
RELAY_WINDOW_SECONDS_OBSERVED=384.16830721497536
WINDOW_ACCEPTED_RELAY_COUNT=38
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_ACCEPTED_RELAY_ROUTE_COUNT=1
```

This proves the product chain through Manager acceptance:

```text
BOARD_B
-> ESP_NOW
-> BOARD_A_GATEWAY_FORWARD
-> MQTT_BROKER
-> MANAGER_RELAY_INGRESS
-> MANAGER_ACCEPTED_TELEMETRY
```

Detailed public-safe closeout authority:

`docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`

## Dynamic Security / subscription repair boundary

The downstream Relay failure was localized to the active Manager Dynamic Security role. Default subscribe and client-receive behavior remained deny, while the Manager role lacked the exact Relay ingress receive contract.

Accepted least-privilege topic:

```text
gh/v1/<sid>/ingress/gateway/+/+/frame
```

Accepted ACL trio:

```text
subscribePattern
publishClientReceive
unsubscribePattern
```

Final repair/runtime state:

```text
ID24_REPAIR_RESULT=PASS
POSTSTATE_EXACT_RELAY_ACL_COUNT=3
POSTSTATE_EXACT_CONTRACT_PROVEN=true

ID25_REACTIVATION_RESULT=PASS
POSTRESTART_RELAY_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_DIRECT_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_FAILURE_LOG_ABSENT=true

ID26_REVALIDATION_RESULT=PASS
LIVE_REPAIRED_DYNSEC_POSTSTATE_PROVEN=true
DYNSEC_STATE_UNCHANGED=true
MANAGER_RUNTIME_STABLE=true
BROKER_RUNTIME_STABLE=true
```

No broad `ingress/gateway/#` grant is part of the accepted repair.

## Last-proven physical boundary

```text
BOARD_A_LAST_PROVEN_STATE=POWERED_DIRECT_DURING_ID26_UNTOUCHED
BOARD_A_USB_ACCESS_DURING_ID26=false
BOARD_A_PHYSICAL_MUTATION_DURING_ID26=false

BOARD_B_ID26_INITIAL_STATE=POWERED_OFF_AT_QUALIFIED_RELAY_ONLY_LOCATION
BOARD_B_ID26_POWER_WINDOW_COMPLETED=true
BOARD_B_ID26_FINAL_STATE=POWERED_OFF
BOARD_B_USB_ACCESS_DURING_ID26=false

CONTROLLED_RF_EXPERIMENT=PASS
```

These are last-proven experiment boundary facts, not a claim about the boards' real-time state after the operator later leaves the experiment.

## T1 runtime boundary

The previously accepted T1 runtime-convergence closure remains in force. ID24-ID26 additionally prove the current Relay receive path without reopening the infrastructure detour.

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
AUTHORITATIVE_MANAGER_COUNT=1
AUTHORITATIVE_BROKER_COUNT=1
BROKER_HOST_PUBLICATION_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS

ID26_MANAGER_RUNTIME_STABLE=true
ID26_BROKER_RUNTIME_STABLE=true
ID26_DYNSEC_STATE_UNCHANGED=true
```

Detailed historical T1 convergence archive:

`docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`

## Acceptance boundaries not claimed by KF-089 closeout

```text
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

The accepted fresh/cold Relay path must not be re-labelled as proof of a same-session Direct→Relay transition or Relay→Direct recovery.

## 2026-09-15 broader multi-node Relay / Home Assistant continuation

The broader acceptance route continued beyond the KF-089 cold/fresh Relay closeout under:

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Fresh physical execution proved Board B and Board C can simultaneously use Board A as their only Relay gateway while Board A remains Direct:

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
BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PROVEN
```

Manager, Broker and accepted DynSec state remained stable. No board/T1 mutation or MQTT test publish was used for this proof.

Therefore:

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
```

The next downstream Home Assistant validation exposed an independent infrastructure blocker rather than a Relay regression. Fresh authority classification proved the current N3-W Home Assistant is the exact FC4 `fc4-homeassistant` runtime in Compose project `n3wfc4`; the independent `homeassistant` project has no A/B/C N3-W entities and is not the current authority.

The FC4 Home Assistant MQTT identity matches the current dedicated DynSec Home Assistant identity and uses the correct TLS listener port. Broker certificate forensic proved the served certificate is valid now, remains valid for the next 30 days, has a valid chain from the FC4 Home Assistant namespace, and has exactly one DNS SAN. The current Home Assistant target and current Manager target both equal that certificate-authoritative DNS identity by public-safe fingerprint:

```text
TLS_DNS_SAN_SHA256_16=8203b89b390ddffc
CURRENT_HA_TARGET_SHA256_16=8203b89b390ddffc
MANAGER_RUNTIME_TARGET_SHA256_16=8203b89b390ddffc
```

However that certificate-authoritative name is not resolvable inside the FC4 Home Assistant private Docker network. Other Docker-internal Broker names are DNS-resolvable and TCP-connectable on 8883, and their certificate chain validates, but full TLS verification fails with `HOSTNAME_MISMATCH` because those names are not covered by the Broker certificate SAN.

Current root cause:

```text
ROOT_DOMAIN=INFRASTRUCTURE
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
RELAY_SPECIFIC_FAILURE=false
HOME_ASSISTANT_MQTT_TARGET_VALUE_CORRECT=true
HOME_ASSISTANT_MQTT_IDENTITY_CORRECT=true
BROKER_TLS_CERTIFICATE_VALID=true
BROKER_CA_CHAIN_VALID=true
BROKER_TCP_REACHABILITY_FROM_FC4_HA=true
```

Minimum repair direction:

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

No live Broker/network mutation is authorized yet. The current repair path must first exact-bind the Compose/network authority, prove the SAN is absent as a Broker alias, prove alias-only intended delta, preserve Broker data/TLS/DynSec, preserve Manager/HA as non-target services, and maintain/verify the accepted 8883 publication after any recreate or endpoint reattach.

Detailed current alignment:

`docs/development/N3W_MULTI_NODE_RELAY_HOME_ASSISTANT_MQTT_PATH_PROGRESS_ALIGNMENT_20260915.md`

Current broader acceptance boundary:

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=BLOCKED_BY_HA_BROKER_TLS_DNS_BINDING
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=PENDING
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

## Required guards

- USB port is a locator only and is not board identity authority.
- Board-targeted mutation requires explicit operator target/connection confirmation before board access and fresh ROM silicon identity before write.
- Application serial open is not a passive runtime oracle.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Discovery RX means decoded handler RX, not accepted advertisement.
- Historical discovery counts are boot-session cumulative, not exact final RF-window counts.
- Schema-v4 `esp_now_send(...) == ESP_OK` is submit acceptance, not asynchronous delivery completion; Schema-v5 completion counters are the correct device-side completion oracle.
- Manager/Broker authority must not be selected by container name alone.
- Home Assistant authority must not be selected by host-global service-name cardinality; bind the exact current Compose lineage/name/runtime authority.
- Strict read-only gates must not create temporary files on the target.
- Current DynSec authority must be derived from the running Broker effective configuration; broad Relay grants remain forbidden.
- The Manager Relay role must retain exactly the required least-privilege receive contract while default deny remains active.
- A live in-place ACL repair does not reactivate an existing MQTT subscription by itself; reactivation evidence must be established separately.
- End-to-end Relay proof requires a bounded fresh traffic window with a clean pre-window baseline or another equally strong attribution oracle.
- Consumed one-shot authorizations are never replayable.
- MQTT/Broker target reachability must be validated inside the consuming runtime's own network namespace.
- TCP reachability is not TLS target validity; full certificate hostname verification remains mandatory.
- Never disable TLS hostname verification to compensate for Docker DNS/SAN mismatch.
- Bridge-network Broker naming must preserve a usable intersection between Docker DNS authority and certificate SAN authority.
- SSH used inside shell read loops must have explicit stdin ownership; read-only SSH that does not require stdin should use a non-consuming stdin contract.
- Minimal production images must not be assumed to contain diagnostic tools such as `openssl`; helper dependencies must be preflighted.
- Recorder cursor movement alone is not a generic MQTT delivery oracle for static/diagnostic Home Assistant entities.

## KF-089 closeout gate (historical scope)

KF-089 no longer requires another physical/T1 gate for its Relay end-to-end acceptance. The code/package integration route is complete, and the final closeout/current-authority documentation was integrated after PR #406→#408.

```text
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
PR406_PR407_PR408_INTEGRATION=PASS
PHYSICAL_AUTHORIZATION_REQUIRED=false
T1_AUTHORIZATION_REQUIRED=false
POST_KF089_CLOSEOUT_NEXT_ONE_GATE=NONE_WITHIN_KF089_RELAY_CLOSEOUT
```

## Current broader ONE gate

```text
CURRENT_ONE_GATE=FC4_HOME_ASSISTANT_BROKER_TLS_SAN_NETWORK_ALIAS_REPAIR_PRECLAIM
MUTATION_AUTHORIZATION_GRANTED=false
```

The current gate is read-only planning/preclaim work. It does not authorize Broker recreate, endpoint reattach, Docker network mutation, Home Assistant reconfigure, certificate rotation, credential rotation or DynSec mutation.

## Frozen broader acceptance

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
N3W_MULTI_NODE_RELAY_ITEM_1=PASS
```

Public GitHub stores source, tests, hashes, sanitized closures, architecture decisions, and sanitized runtime alignment. Raw NVS, credentials, private board identities, remote-host details, private paths/addresses, raw Manager logs, raw Home Assistant storage contents and raw Dynamic Security snapshots remain private/local.
