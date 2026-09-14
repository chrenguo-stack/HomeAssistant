# KF-089 ID24R1 — T1 DynSec State Read-Only Recovery

Status: `HOST_ONLY_PACKAGE_PREPARATION`

This gate exists because the later chat history contains an unverified purported ID24 live closure, while no raw ID24 executor evidence has been recovered. It does not try to reconstruct that historical execution. Its sole purpose is to establish the current T1 Manager/Broker/Dynamic Security state without changing it.

The durable predecessor remains the proven ID23 adjudication:

```text
BOARD_SIDE_RELAY_CHAIN=PROVEN
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

The accepted ID24 repair package remains at:

```text
b973934b760db975ada601819191c62fe0513a9e
```

## Goal

After a separate explicit T1 read-only authorization, classify the current active Manager Relay ACL state as exactly one of:

```text
PRE_REPAIR_DEFECT
EXACT_REPAIRED
PARTIAL_OR_DRIFT
```

The classification is based on the same exact runtime/DynSec binding logic used by the accepted ID24 repair executor.

`PRE_REPAIR_DEFECT` requires default subscribe and publishClientReceive deny, Direct ingress intact, and zero exact/broader Relay coverage for all three target ACL types.

`EXACT_REPAIRED` requires default deny preserved, Direct ingress intact, exactly one exact target ACL for each of `subscribePattern`, `publishClientReceive`, and `unsubscribePattern`, and no broader Relay grant.

Anything else is `PARTIAL_OR_DRIFT` and returns to the high-level model without repair.

## Read-only execution shape

1. Bind exact package HEAD and a clean tracked worktree.
2. Claim the fresh read-only authorization.
3. Read the current T1 Docker container inventory.
4. Exact-bind one authoritative deployed Manager and one `n3wfc4` Broker.
5. Derive the active Dynamic Security file path from live Broker `mosquitto.conf`.
6. Read the live Dynamic Security JSON privately.
7. Exact-bind the active Manager DynSec client by the running Manager's MQTT username + client ID and expected service role.
8. Save the live Dynamic Security state and SHA256 only in the private host evidence root.
9. Classify the current Relay ACL state.
10. Re-read Docker runtime state and prove Manager/Broker identity/restart stability.
11. Emit a sanitized closure and stop.

## Route

If `PRE_REPAIR_DEFECT`:

```text
NEXT_ROUTE=REQUEST_NEW_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION
```

A new authorization and new execution ID are required. The unresolved historical ID24 authorization/execution ID must never be reused.

If `EXACT_REPAIRED`:

```text
NEXT_ROUTE=PREPARE_KF089_MANAGER_RELAY_SUBSCRIPTION_REACTIVATION_PACKAGE
```

This does not prove how or when the ACLs were installed and does not prove end-to-end Relay telemetry.

If `PARTIAL_OR_DRIFT`:

```text
NEXT_ROUTE=STOP_RETURN_TO_HIGH_LEVEL_MODEL
```

No automatic repair is allowed.

## Forbidden

```text
DYNSEC_MUTATION=false
MQTT_CONTROL_REQUEST=false
MQTT_TEST_PUBLISH=false
APPLICATION_TOPIC_SUBSCRIBER=false
MANAGER_RESTART=false
BROKER_RESTART=false
DOCKER_MUTATION=false
BROKER_CONFIG_MUTATION=false
CREDENTIAL_CHANGE=false
T1_FILE_WRITE=false
BOARD_A_ACCESS=false
BOARD_B_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_MUTATION=false
RF_EXECUTION=false
AUTO_RETRY=false
PR_MERGE=false
```

Read-only `docker exec ... cat` is allowed solely to read already-running Broker configuration/state. Private evidence may contain the SSH target, raw Docker inspect, raw DynSec JSON, service identities and private paths; none of those may be published to public GitHub.
