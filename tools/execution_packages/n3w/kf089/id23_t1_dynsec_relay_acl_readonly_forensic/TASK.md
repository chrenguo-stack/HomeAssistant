# KF-089 ID23 — T1 DynSec Relay ACL Read-Only Forensic

Status: `HOST_ONLY_PACKAGE_PREPARATION`

This package is the next gate after ID22R2 STOP. It does not authorize T1 access by itself. No Board A/Board B access, application boot, RF execution, MQTT test publish, extra subscriber, Broker/DynSec mutation, Docker mutation, file write, network mutation, or PR merge is authorized by package preparation.

A fresh explicit T1 read-only authorization bound to the final exact package commit is required before execution.

## Goal

Determine whether the live T1 Dynamic Security state reproduces the source-level Relay ingress ACL defect already identified at the frozen deployed Manager source revision.

Frozen ID22R2 evidence:

```text
ID22R2_RESULT=STOP
ID22R2_EXECUTION_PACKAGE_COMMIT=23b3dc63dc112979a8e94928185daf8af2da6640
FIRST_FAILED_OPERATION=T1_MANAGER_RELAY_ACCEPTANCE
BOARD_SIDE_RELAY_CHAIN_PROVEN_IN_ID22_SESSION=true
A_COMPACT_FORWARD_SUBMIT_SUCCESS>=1
MANAGER_ACCEPTED_RELAY_COUNT=0
MANAGER_REJECTED_RELAY_COUNT=0
```

ID22R2 is consumed and non-replayable. ID23 does not repeat any RF experiment.

## Frozen source-contract evidence

The deployed Manager source revision is:

```text
8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
```

At that exact source:

1. `N3wSimplifiedIsolatedMqttService` subscribes to:
   `gh/v1/<system_id>/ingress/gateway/+/+/frame`.
2. `service_identity_plan.py` grants the Manager Direct ingress receive ACL but no `ingress/gateway/...` Relay receive ACL.
3. `dynsec_plan.py` grants each node `publishClientSend gh/v1/<system_id>/ingress/gateway/<node_id>/#`.

Therefore:

```text
MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_DEFECT=NOT_YET_PROVEN
```

ID23 exists only to resolve the live-state question.

## Execution shape after later authorization

ID23 is T1-only and read-only.

1. Bind the local ID22R2 private evidence root and recover its exact T1 UTC start/end window.
2. Rebind the current authoritative T1 Manager and Broker using the already-observed runtime authority:
   - Manager: container name `greenhouse-manager`, image prefix `greenhouse-manager:`,
     source revision `8fbedc7e...`, host network, running.
   - Broker: Compose service `broker`, Compose project `n3wfc4`, running.
3. Read `/mosquitto/config/mosquitto.conf` inside the authoritative Broker and derive the active `plugin_opt_config_file` path.
4. Read that exact live Dynamic Security JSON into the private evidence root.
5. Parse the live Manager client/role/default ACL state.
6. Parse all live node clients and determine whether their own gateway publish ACL is present.
7. Read Broker logs bounded by the exact ID22R2 T1 start/end timestamps and classify any gateway-topic or ACL/authorization evidence.
8. Produce a sanitized closure.

Read-only `docker exec ... cat` is permitted solely to read the already-running Broker configuration/state. It is not Docker mutation.

## Required live-state adjudication

The decisive live defect condition is:

```text
defaultACLAccess.subscribe=false
AND defaultACLAccess.publishClientReceive=false
AND Manager has no allow subscribePattern covering
    gh/v1/<sid>/ingress/gateway/+/+/frame
AND Manager has no allow publishClientReceive covering
    gh/v1/<sid>/ingress/gateway/+/+/frame
```

If all are true:

```text
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
NEXT_ROUTE=PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE
```

The node-side live state is separately summarized as the count of node identities whose role contains an allowed self-gateway publish topic. Complete node IDs remain private.

Broker logs are supporting evidence only. Absence of a Broker log line is not interpreted as proof that a publish or denial did not occur.

## PASS meaning

`ID23 forensic_result=PASS` means the requested live read-only evidence was successfully collected and adjudicated. It does **not** mean KF-089 end-to-end Relay telemetry is proven.

If the live Manager role reproduces the defect:

```text
MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

If it does not reproduce the defect, the next route is deeper Broker Relay ingress forensic; no RF replay occurs automatically.

## Forbidden

```text
BOARD_A_ACCESS=false
BOARD_B_ACCESS=false
APPLICATION_BOOT=false
CONTROLLED_RF_EXPERIMENT=false
FLASH_WRITE=false
HOST_NVS_WRITE=false
OTADATA_WRITE=false
SERIAL_OPEN=false

T1_FILE_WRITE=false
T1_DOCKER_MUTATION=false
T1_NETWORK_MUTATION=false
DYNSEC_MUTATION=false
BROKER_CONFIG_MUTATION=false

MQTT_TEST_PUBLISH=false
MQTT_EXTRA_SUBSCRIBER=false
MQTT_CONTROL_REQUEST=false

AUTO_RETRY=false
AUTO_REPAIR=false
PR_MERGE=false
```

## Private/public evidence boundary

Private evidence may contain:

- T1 SSH target;
- raw Docker inspect data;
- raw `mosquitto.conf`;
- raw Dynamic Security JSON including credential hashes/salts;
- complete client IDs, role names and node IDs;
- raw bounded Broker logs;
- local absolute paths.

None of those raw materials may be posted to public GitHub.

Public-safe evidence may contain only:

- package/source commit hashes;
- boolean ACL findings;
- sanitized counts;
- PASS/STOP classification;
- root-cause class;
- next route.
