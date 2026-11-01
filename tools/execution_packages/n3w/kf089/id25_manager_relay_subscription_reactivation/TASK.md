# KF-089 ID25 — Manager Relay Subscription Reactivation

Status: `HOST_ONLY_PACKAGE_PREPARATION`

ID24 repaired the active Manager Dynamic Security role in place and proved the exact least-privilege Relay ACL trio is now present. ID24 deliberately did not restart the Manager, so the already-running MQTT session has not yet been forced through a fresh `_on_connect()` cycle after the ACL repair.

The deployed N3-W Manager source subscribes to:

```text
gh/v1/<sid>/ingress/gateway/+/+/frame
```

inside `N3wSimplifiedIsolatedMqttService._on_connect()`. A fresh Manager MQTT session is therefore required before the end-to-end Relay path can be revalidated.

ID25 is intentionally narrower than the later end-to-end test. It reactivates the existing Manager Relay subscription by performing exactly one controlled Manager container restart, while proving the repaired DynSec state remains exact and the Broker runtime is untouched.

## Proven predecessor

```text
ID24_REPAIR_RESULT=PASS
LIVE_PRESTATE_DEFECT_PROVEN=true
TARGET_ACL_ADD_SUCCESS_COUNT=3
POSTSTATE_EXACT_RELAY_ACL_COUNT=3
POSTSTATE_EXACT_CONTRACT_PROVEN=true
MANAGER_RUNTIME_STABLE=true
BROKER_RUNTIME_STABLE=true
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

## Source authority

The package binds all of the following before any T1 access:

```text
ID24_EXECUTOR_BLOB=0ee29a4b8378813498ad2c41d7f44fd8b5801245
N3W_SUBSCRIPTION_SOURCE_BLOB=2a478300e66bed341f55b44e629c24847128f413
N3W_RUNTIME_WIRING_BLOB=90cd70249200a810711b0388a38bcd6c8e64ef16
DEPLOYED_MANAGER_SOURCE=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
```

The subscription source must still contain the exact Relay subscription property and the `_on_connect()` call that subscribes to it at QoS 1. The runtime wiring must still select the simplified N3-W Manager service when N3-W runtime is enabled.

## Live execution shape after later authorization

1. Bind exact package HEAD and a clean tracked worktree.
2. Claim the fresh one-shot authorization.
3. Read current T1 container inventory and exact-bind the authoritative deployed Manager and `n3wfc4` Broker.
4. Read current Broker configuration and Dynamic Security state.
5. Prove the live DynSec state still matches the exact repaired ID24 contract.
6. Save a fresh private pre-restart DynSec snapshot and SHA256.
7. Read a T1 epoch marker for a bounded post-restart log window.
8. Execute exactly one `docker restart --time 10 <manager>` operation.
9. Wait a fixed short observation interval; do not retry the restart.
10. Re-read Docker runtime state and prove:
    - same Manager container ID;
    - same Manager image/source revision;
    - Manager `StartedAt` changed;
    - Manager is running;
    - Broker container/image/restart count/StartedAt remain unchanged.
11. Read only the Manager logs from the bounded post-restart window and require:
    - Direct ingress subscription request observed;
    - exact Relay subscription request observed;
    - no MQTT connection rejection;
    - no local Relay subscribe failure.
12. Re-read Dynamic Security state and require the exact repaired contract and byte-for-byte SHA256 equality with the pre-restart snapshot.
13. Emit a sanitized closure and stop.

The Manager log evidence proves that the restarted Manager executed the expected subscription path after the ACL repair. It does **not** by itself prove Broker-to-Manager Relay delivery; that remains for the later minimal end-to-end Relay revalidation gate.

## PASS boundary

```text
SOURCE_SUBSCRIPTION_CONTRACT_PROVEN=true
LIVE_REPAIRED_DYNSEC_PRESTATE_PROVEN=true
PRE_RESTART_DYNSEC_SNAPSHOT_SHA256_RECORDED=true
MANAGER_RESTART_COMMAND_COUNT=1
MANAGER_RESTART_COMPLETED=true
MANAGER_CONTAINER_ID_PRESERVED=true
MANAGER_IMAGE_PRESERVED=true
MANAGER_STARTED_AT_CHANGED=true
MANAGER_RUNNING=true
BROKER_RUNTIME_STABLE=true
POSTRESTART_RELAY_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_DIRECT_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_FAILURE_LOG_ABSENT=true
LIVE_REPAIRED_DYNSEC_POSTSTATE_PROVEN=true
DYNSEC_STATE_UNCHANGED=true
REACTIVATION_RESULT=PASS
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
NEXT_ROUTE=PREPARE_KF089_MINIMAL_END_TO_END_RELAY_REVALIDATION_PACKAGE
```

## Failure behavior

There is no automatic retry and no automatic rollback. A Manager restart cannot be meaningfully rolled back to the previous process instance. Any failure after authorization claim stops and returns to the high-level model. A failed or incomplete restart must not be repeated under the same authorization.

## Forbidden

```text
DYNSEC_MUTATION=false
BROKER_RESTART=false
BROKER_CONFIG_MUTATION=false
T1_FILE_WRITE=false
CREDENTIAL_CHANGE=false
MQTT_TEST_PUBLISH=false
APPLICATION_TOPIC_SUBSCRIBER=false
BOARD_A_ACCESS=false
BOARD_B_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_MUTATION=false
CONTROLLED_RF_EXPERIMENT=false
AUTO_RETRY=false
AUTO_ROLLBACK=false
PR_MERGE=false
```

Raw Docker inspect, raw Manager logs, raw DynSec JSON, SSH target, service identities and private paths remain private evidence only.
