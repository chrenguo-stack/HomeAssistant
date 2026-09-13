# KF-089 ID24 — Manager Relay DynSec ACL Repair

Status: `HOST_ONLY_PACKAGE_PREPARATION`

ID24 is the first mutation gate after the ID23 post-execution offline adjudication proved the live root cause:

```text
MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

Package preparation does not authorize T1 access or mutation. A fresh explicit authorization bound to the final exact package commit is required.

## Source repair

The Manager service identity contract now grants the exact existing runtime Relay subscription:

```text
gh/v1/<system_id>/ingress/gateway/+/+/frame
```

using the same least-privilege receive trio already used by Direct ingress:

```text
subscribePattern
publishClientReceive
unsubscribePattern
```

No broader `ingress/gateway/#` permission is added.

## Live repair purpose

The deployed Manager runtime already subscribes to the Relay topic, but its current live DynSec role lacks receive authority. ID24 aligns only that existing active Manager role with the repaired source contract.

The mutation is deliberately narrower than a service restart or end-to-end retest. ID24 does **not** restart Manager or Broker and does not send application MQTT traffic. A later separately-authorized gate reactivates the Manager Relay subscription after the ACL has been repaired.

## Required prestate

Before mutation the executor must prove:

1. exactly one authoritative standalone Manager and one authoritative `n3wfc4` Broker are running;
2. the active Manager DynSec client is uniquely bound by runtime `GH_MQTT_USERNAME` + `GH_MQTT_CLIENT_ID`;
3. the expected Manager service role is bound to that active client;
4. default `subscribe` and `publishClientReceive` are deny;
5. the Direct ingress receive ACL contract remains intact;
6. no exact or broader Relay receive allow currently covers the target;
7. the Manager container has a complete dedicated N3-W provisioning identity and Broker endpoint;
8. the repaired source contract is bound to the exact repository blob.

Any drift stops before mutation.

## Mutation

Using only the already-configured dedicated provisioning identity, add exactly three ACL entries to the active Manager role:

```text
allow subscribePattern       gh/v1/<sid>/ingress/gateway/+/+/frame priority=100
allow publishClientReceive   gh/v1/<sid>/ingress/gateway/+/+/frame priority=100
allow unsubscribePattern     gh/v1/<sid>/ingress/gateway/+/+/frame priority=100
```

The control operation is executed in the existing Manager container through stdin-fed Python. No script, credential, or temporary file is written on T1. The provisioning password is read only inside the container and is never emitted.

## Transaction and rollback

The prestate has all three target ACLs absent. After the bounded `addRoleACL` operations, live Dynamic Security state is independently read from the authoritative Broker.

If the mutation is partial, rejected, or the exact poststate is not proven, ID24 removes only target ACLs observed present and then re-reads live state. PASS rollback means the prestate absence is restored. A rollback that cannot be proven is a hard STOP requiring high-level recovery; no automatic repair retry is allowed.

Rollback is a safety action inside the same authorization, not a replay.

## PASS

```text
SOURCE_CONTRACT_REPAIRED=true
LIVE_PRESTATE_DEFECT_PROVEN=true
TARGET_ACL_ADD_SUCCESS_COUNT=3
POSTSTATE_EXACT_RELAY_ACL_COUNT=3
MANAGER_RUNTIME_STABLE=true
BROKER_RUNTIME_STABLE=true
REPAIR_RESULT=PASS

KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN

NEXT_ROUTE=PREPARE_KF089_MANAGER_RELAY_SUBSCRIPTION_REACTIVATION_PACKAGE
```

ID24 PASS does not claim that the already-connected Manager has an active Relay subscription. The original SUBSCRIBE may have been denied before the ACL repair. Reactivation is intentionally a later gate.

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
MANAGER_RESTART=false
BROKER_RESTART=false
BROKER_CONFIG_MUTATION=false
CREDENTIAL_CHANGE=false

MQTT_TEST_PUBLISH=false
APPLICATION_TOPIC_SUBSCRIBER=false
AUTO_RETRY=false
PR_MERGE=false
```

The only live mutation later authorized by ID24 is the exact three-entry Dynamic Security role ACL change plus a bounded rollback if needed.

## Private/public boundary

Private evidence may contain the SSH target, raw Docker inspect output, raw DynSec JSON, active client/role names, system ID, private paths, and provisioning configuration metadata. None may be posted to public GitHub.

Public-safe evidence is limited to exact source/package commits, booleans, sanitized counts, PASS/STOP classification, rollback status, and next-route classification.
