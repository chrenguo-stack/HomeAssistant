# N3-W Pre-U1 G3 Node B normal first registration closure

Date: 2026-11-04

## 1. Result

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G3_NODE_B_FIRST_REGISTRATION_20261104_01
RESULT=CLOSED_PASS

PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
PRE_U1_G3_RESULT=CLOSED_PASS

NODE_B_NORMAL_FIRST_REGISTRATION=PASS
NODE_B_FIRST_REGISTRATION_AUTHORIZATION=CLAIMED_CONSUMED
MANUAL_REGISTRATION_RETRY_ALLOWED=false
```

Node B completed first registration through the normal product UX only: LCD registration QR -> phone-local registration page -> intended T1 selection/confirmation -> normal registration/pairing protocol -> durable Manager commit -> product runtime. No direct SQLite write, manual NODE_ID assignment, manual MQTT credential insertion, manual DynSec client creation, service restart or registration retry was used.

The phone reported registration success and Node B LCD page 5 changed to the normal registered state.

## 2. Durable registration and identity proof

Fresh read-only T1 evidence after the product UI reported success:

```text
REGISTERED_NODE_COUNT=2
ACTIVE_NODE_ID_LEASE_COUNT=2
ACTIVE_CREDENTIAL_ASSIGNMENT_COUNT=2
UNRESOLVED_FIRST_REGISTRATION_COUNT=0

NODE_A_NODE_ID_SHA256=7c5197ca0643ea0669c2ee43d5d89a994b09b0394fdd7e9872fea5aa4d97e090
NODE_B_NODE_ID_SHA256=589486b4e4e7fb05fc0a7e8994d977b67c60ce72770b80af6ee74eef0bd1d724
NODE_B_DISTINCT_FROM_NODE_A=true
```

The latest first-registration attempt is:

```text
STATE=COMMITTED
PHASE=TERMINAL
CLEANUP_STATE=COMPLETE
TERMINAL_REASON=null
APPLICATION_KEY_EPOCH=1
DYNSEC_PRESTATE_ABSENT=1
APPLICATION_KEY_PRESTATE_ABSENT=1
```

The exact Node B registration binding is:

```text
PAIRING_STATE=approved
NODE_ID_LEASE_STATE=active
```

Therefore the supported first-registration transaction reached its durable terminal commit with no unresolved cleanup.

## 3. Credential and application-key commit oracle

Fresh secret-free lifecycle evidence:

```text
NODE_B_CREDENTIAL_STATE=active
NODE_B_ACTIVE_GENERATION=1
NODE_B_PENDING_GENERATION=null
NODE_B_REVOKED=false

NODE_B_APPLICATION_KEY_ACTIVE_NODE_COUNT=1
NODE_B_APPLICATION_KEY_ACTIVE_OR_GRACE_EPOCH_COUNT=1
NODE_B_APPLICATION_KEY_EPOCH=1
NODE_B_APPLICATION_KEY_STATE=ACTIVE
NODE_B_APPLICATION_KEY_MATERIAL_BINDING_VALID=true
```

This proves generation-1 credential lifecycle and application-key state agree with the committed registration.

## 4. DynSec exact plan proof

The live Broker Dynamic Security state was compared read-only against the deterministic generation-1 plan rebuilt from the current product source for Node B.

```text
DYNSEC_CLIENT_PRESENT=true
DYNSEC_ROLE_PRESENT=true
DYNSEC_CLIENT_ROLE_BINDING_EXACT=true
DYNSEC_ROLE_ACL_EXACT=true
```

No manual DynSec object was created or edited for this acceptance.

## 5. Pairing window and product-service continuity

Final listener state:

```text
TCP_47110_LISTENER_COUNT=1
UDP_47111_LISTENER_COUNT=1
TCP_47112_LISTENER_COUNT=0
PAIRING_WINDOW_STATE=CLOSED
```

All three product containers remained on the frozen images and did not restart:

```text
MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
MANAGER_STATE=running
MANAGER_RESTART_COUNT=0

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_STATE=running
HOMEASSISTANT_RESTART_COUNT=0

BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_STATE=running
BROKER_RESTART_COUNT=0
```

## 6. Two-node runtime continuity observed inside G3

Two read-only canonical-cursor snapshots were taken after Node B registration.

Node B:

```text
NODE_ID_SHA256=589486b4e4e7fb05fc0a7e8994d977b67c60ce72770b80af6ee74eef0bd1d724
BOOT_SESSION_SHA256=665e994827f6b03167e80c1513eb356e0d4f013f2e03a3b345e1e5e3c24dfca6
SOURCE=direct
SEQ_1=4
SEQ_2=6
SEQ_ADVANCED=true
```

Node A:

```text
NODE_ID_SHA256=7c5197ca0643ea0669c2ee43d5d89a994b09b0394fdd7e9872fea5aa4d97e090
BOOT_SESSION_SHA256=ab11cb5a8ade4616fcdd1ca5accbc136a458d2d67193458bd187f4900e02e081
SOURCE=direct
SEQ_1=24
SEQ_2=26
SEQ_ADVANCED=true
```

Both registered nodes therefore continued independent Direct canonical telemetry after the registration transaction. This evidence supports G3 continuity but does not replace the separate G4 minimum 10-minute two-node runtime observation.

## 7. Home Assistant automatic discovery

Read-only Home Assistant registry inspection:

```text
NODE_A_HA_DEVICE_MATCH_COUNT=1
NODE_A_HA_ENTITY_COUNT=17
NODE_B_HA_DEVICE_MATCH_COUNT=1
NODE_B_HA_ENTITY_COUNT=6
```

Operator normal-UI confirmation:

```text
HA_UI_NODE_A_VISIBLE=true
HA_UI_NODE_B_VISIBLE=true
HA_UI_TWO_SEPARATE_DEVICES=true
HA_UI_NODE_A_OVERWRITTEN=false
HA_UI_NODE_A_DUPLICATED=false
```

Node B is allowed to be sensorless in G3, so its smaller entity count is not a failure.

No manual MQTT integration change was used.

## 8. Observer-only issue classification

After the core commit proof had already succeeded, the first auxiliary DynSec/Home Assistant read-only command package failed with two `JSONDecodeError` exceptions because the command composition omitted stdin forwarding for nested `docker exec` Python reads.

The corrected read-only package completed successfully and produced the exact DynSec and Home Assistant results above.

```text
OBSERVER_COMMAND_DEFECT=true
PRODUCT_FAILURE=false
T1_MUTATION_FROM_OBSERVER=false
REGISTRATION_RETRY=false
```

## 9. Final G3 classification

```text
NODE_B_NORMAL_FIRST_REGISTRATION=PASS
FIRST_REGISTRATION_DURABLE_COMMIT=PASS
NODE_B_IDENTITY_UNIQUE=PASS
NODE_B_REGISTRATION_APPROVED=PASS
NODE_B_ACTIVE_NODE_ID_LEASE=PASS
NODE_B_CREDENTIAL_GENERATION_1_ACTIVE=PASS
NODE_B_APPLICATION_KEY=PASS
NODE_B_DYNSEC_EXACT_PLAN=PASS
PAIRING_WINDOW_CLOSED=PASS
NO_UNRESOLVED_FIRST_REGISTRATION=PASS

NODE_A_IDENTITY_CONTINUITY=PASS
NODE_A_TELEMETRY_CONTINUITY=PASS
NODE_B_TELEMETRY_RUNTIME_ENTRY=PASS
PRODUCT_SERVICE_RESTART_COUNT_ZERO=PASS

HA_NODE_B_AUTO_DISCOVERY=PASS
HA_TWO_SEPARATE_NODE_DEVICES=PASS
HA_NODE_A_NOT_DUPLICATED_OR_OVERWRITTEN=PASS

RESULT=CLOSED_PASS
NEW_KF_REQUIRED=false
```

## 10. Next boundary

```text
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G4_TWO_NODE_RUNTIME_20261104_01
TARGET_OBSERVATION_MINUTES=10
DIRECT_RELAY_FAILOVER_TEST=false
AUTO_EXECUTE_NEXT_GATE=false

NEW_AUTHORIZATION_REQUIRED=G4_TWO_NODE_NORMAL_RUNTIME_OBSERVATION
T1_BUSINESS_MUTATION=false
REGISTRATION_MUTATION=false
SERVICE_RESTART_AS_TEST_REPAIR=false
PR774_MERGE=false
STOP=true
```

G4 is a separate minimum-10-minute ordinary Direct-mode two-node runtime acceptance. G3 closure does not authorize entering that next gate.
