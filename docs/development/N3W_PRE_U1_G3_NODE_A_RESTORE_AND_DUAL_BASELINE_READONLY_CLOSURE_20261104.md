# N3-W Pre-U1 G3 Node A restore and dual baseline read-only closure

Date: 2026-11-04

## 1. Result

```text
GATE=N3W_PRE_U1_G3_NODE_A_RESTORE_AND_DUAL_BASELINE_READONLY_20261104_01
RESULT=CLOSED_PASS

PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
PRE_U1_G3_RESULT=IN_PROGRESS

NODE_A_RESTORED_ONLINE=true
NODE_A_G2_ACCEPTANCE_RETAINED=true
NODE_A_IDENTITY_CONTINUITY=PASS
NODE_A_DIRECT_TELEMETRY_CONTINUITY=PASS

NODE_B_WIFI_CONNECTED=true
NODE_B_IDLE_UNREGISTERED_QR_VISIBLE=true
NODE_B_FIRST_REGISTRATION_STARTED=false

T1_RUNTIME_MUTATION=false
DATABASE_MUTATION=false
CREDENTIAL_MUTATION=false
PAIRING_MUTATION=false
SERVICE_RESTART=false
PR774_MERGE=false
```

Node A was physically restored to power after the Node B Wi-Fi setup sub-gate. The verification package was read-only and used product service state, listener state, container metadata, and SQLite `mode=ro` + `PRAGMA query_only=ON` durable-state reads.

## 2. Product service continuity

Fresh T1_B evidence:

```text
SYSTEM_STATE=running
DOCKER_SERVICE=active
BROKER_ACTIVATION_SERVICE=active
SERVICES_ACTIVATION_SERVICE=active
REGISTRATION_INGRESS_GUARD=active
CERTIFICATE_LIFECYCLE_TIMER=active
CERTIFICATE_LIFECYCLE_SERVICE=inactive_EXPECTED_ONESHOT_IDLE

MANAGER_CONTAINER=n3wfc4-manager-1
MANAGER_STATE=running
MANAGER_RESTART_COUNT=0
MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909

HOMEASSISTANT_CONTAINER=n3wfc4-homeassistant-1
HOMEASSISTANT_STATE=running
HOMEASSISTANT_RESTART_COUNT=0
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

BROKER_CONTAINER=n3wfc4-broker-1
BROKER_STATE=running
BROKER_RESTART_COUNT=0
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
```

The product listener baseline remained normal:

```text
TCP_1883=LISTEN_LOOPBACK
TCP_8883=LISTEN_WILDCARD
TCP_8123=LISTEN
TCP_47110=LISTEN
UDP_47111=LISTEN
TCP_47112=CLOSED
```

No product-service restart was used to recover Node A or to prepare Node B registration.

## 3. Existing registered Node A continuity

The already frozen G2 public-safe Node A identity remained exact:

```text
EXPECTED_NODE_A_NODE_ID_SHA256=7c5197ca0643ea0669c2ee43d5d89a994b09b0394fdd7e9872fea5aa4d97e090
OBSERVED_REGISTERED_NODE_ID_SHA256=7c5197ca0643ea0669c2ee43d5d89a994b09b0394fdd7e9872fea5aa4d97e090
NODE_A_IDENTITY_CONTINUITY=PASS
```

After the physical power restore, a new boot session is expected. Two read-only canonical-cursor snapshots showed:

```text
BOOT_SESSION_SHA256=ab11cb5a8ade4616fcdd1ca5accbc136a458d2d67193458bd187f4900e02e081
BASELINE_1_SEQ=12
BASELINE_1_SOURCE=direct
BASELINE_1_UPDATED_AT=2026-11-04T06:50:54.150Z

BASELINE_2_SEQ=14
BASELINE_2_SOURCE=direct
BASELINE_2_UPDATED_AT=2026-11-04T06:52:54.195Z

SAME_BOOT_BETWEEN_SNAPSHOTS=true
SEQ_ADVANCED=true
SEQ_DELTA=2
SOURCE_REMAINED_DIRECT=true
NODE_A_DIRECT_TELEMETRY_CONTINUITY=PASS
```

The boot-session hash is intentionally not compared to the G2 boot-session hash because Node A was power-cycled between the gates.

## 4. Node B still unregistered / no hidden registration start

Both read-only snapshots returned the same business-state counts:

```text
REGISTERED_NODE_COUNT=1
ACTIVE_NODE_ID_LEASE_COUNT=1
ACTIVE_CREDENTIAL_ASSIGNMENT_COUNT=1
ACTIVE_CREDENTIAL_GENERATION=1
PAIRING_SESSION_COUNT=1
UNRESOLVED_FIRST_REGISTRATION_COUNT=0
TCP_47112=CLOSED
```

The single registered node, active lease and active credential all bind to the frozen Node A public-safe identity hash.

Therefore:

```text
NODE_B_EXISTING_REGISTRATION=false
NODE_B_EXISTING_ACTIVE_LEASE=false
NODE_B_EXISTING_ACTIVE_CREDENTIAL=false
ACTIVE_FIRST_REGISTRATION_TRANSACTION=false
PAIRING_WINDOW_STATE=CLOSED
NODE_B_IDLE_UNREGISTERED_PRECONDITION=PASS
```

The existing pairing-session count of one is historical Node A state and did not increase during this gate.

## 5. Initial observer mistake disposition

The first command package was accidentally run in the Mac shell rather than T1_B. It returned `x86_64`, missing `systemctl`/`ss`, and no local Docker socket. That attempt did not touch T1_B and is not product evidence.

A second read-only attempt on T1_B initially used guessed container names (`greenhouse-manager`, `homeassistant`, `mosquitto`) and received container-not-found errors. Product listeners already proved the services were live. The bounded correction resolved exact running containers by their frozen image identities and completed the read-only proof. These observer mistakes are not product failures.

## 6. Gate classification

```text
NODE_A_RESTORED_ONLINE=PASS
NODE_A_IDENTITY_CONTINUITY=PASS
NODE_A_DIRECT_TELEMETRY_CONTINUITY=PASS
PRODUCT_SERVICES_HEALTHY=PASS
PRODUCT_SERVICE_RESTART_COUNTS_ZERO=PASS
NODE_B_STILL_UNREGISTERED=PASS
NO_ACTIVE_FIRST_REGISTRATION_TRANSACTION=PASS
PAIRING_WINDOW_CLOSED=PASS

DUAL_BASELINE_READONLY=PASS
RESULT=CLOSED_PASS
NEW_KF_REQUIRED=false
```

## 7. Next boundary

```text
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G3_NODE_B_FIRST_REGISTRATION_20261104_01
AUTO_EXECUTE_NEXT_GATE=false

NEW_AUTHORIZATION_REQUIRED=NODE_B_NORMAL_FIRST_REGISTRATION
G3_T1_BUSINESS_MUTATION=true
G3_BOARD_ACCESS=true

NODE_B_REGISTRATION_QR_SCAN_ALLOWED=false
HOST_DISCOVERY_ALLOWED=false
START_REGISTRATION_ALLOWED=false

T1_RUNTIME_MUTATION_ALLOWED=false
PR774_MERGE=false
STOP=true
```

The next gate is the actual normal-product Node B first registration. This closure does not authorize scanning the registration QR, host discovery/selection, clicking “开始注册”, opening the 47112 pairing window, or any registration/credential mutation.
