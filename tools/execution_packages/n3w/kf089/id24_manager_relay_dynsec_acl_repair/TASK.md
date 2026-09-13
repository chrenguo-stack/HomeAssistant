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

The Manager service identity contract grants the exact existing runtime Relay subscription:

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
6. no exact or broader Relay receive/unsubscribe allow currently covers the target;
7. the Manager container has a complete dedicated N3-W provisioning identity and Broker endpoint;
8. the repaired source contract is bound to the exact repository blob;
9. a fresh private copy of the live Dynamic Security JSON is recorded with SHA256 before the first mutation command.

Any drift stops before mutation.

## Mutation

Using only the already-configured dedicated provisioning identity, add exactly three ACL entries to the active Manager role:

```text
allow subscribePattern       gh/v1/<sid>/ingress/gateway/+/+/frame priority=100
allow publishClientReceive   gh/v1/<sid>/ingress/gateway/+/+/frame priority=100
allow unsubscribePattern     gh/v1/<sid>/ingress/gateway/+/+/frame priority=100
```

The control operation is executed in the existing Manager container through stdin-fed Python. No script, credential, or temporary file is written on T1. The provisioning password is read only inside the container and is never emitted.

## Exact poststate contract

PASS requires independent live Dynamic Security readback to prove all of the following simultaneously:

```text
EXACT_TARGET_ACL_ENTRY_COUNT=3
EACH_TARGET_ACL_TYPE_COUNT=1
DEFAULT_SUBSCRIBE_DENY=true
DEFAULT_PUBLISH_CLIENT_RECEIVE_DENY=true
DIRECT_INGRESS_ACL_CONTRACT_INTACT=true
RELAY_SUBSCRIBE_BROAD_ALLOW_COUNT=1
RELAY_RECEIVE_BROAD_ALLOW_COUNT=1
RELAY_UNSUBSCRIBE_BROAD_ALLOW_COUNT=1
```

The `=1` broad counts above mean the exact target topic itself is the only matching allow. Any broader `gateway/#`, `ingress/#`, `gh/#`, `#`, duplicate exact ACL, or default-access weakening is a transaction failure.

## Transaction and rollback

The proven prestate has all three target ACLs absent. After the first mutation attempt, **any** later failure before full PASS enters rollback, including:

- an addRoleACL rejection or uncertain response;
- failure to read/parse the post-mutation DynSec state;
- exact-poststate mismatch;
- broader/default ACL drift;
- Manager/Broker runtime-stability postcheck failure;
- unexpected exception after mutation began.

Rollback issues `removeRoleACL` only for the same three exact target ACL type/topic pairs, then independently re-reads the authoritative live DynSec state.

The live readback is the rollback authority. A remove command may return non-PASS when an uncertain add never committed; this is benign only if the final authoritative state exactly matches the proven prestate defect contract.

```text
ROLLBACK_PASS=
  target exact/broad Relay ACL coverage restored to zero
  AND default subscribe remains deny
  AND default publishClientReceive remains deny
  AND Direct ingress ACL contract remains intact
```

If rollback cannot be proven:

```text
ROLLBACK_RESULT=FAIL
FIRST_FAILED_OPERATION=T1_DYNSEC_ROLLBACK
AUTO_RETRY=false
MANUAL_RECOVERY_REQUIRED_BY_HIGH_LEVEL_MODEL=true
```

Rollback is a safety action inside the same authorization, not a replay.

## PASS

```text
SOURCE_CONTRACT_REPAIRED=true
LIVE_PRESTATE_DEFECT_PROVEN=true
PRECHANGE_DYNSEC_SNAPSHOT_SHA256_RECORDED=true
TARGET_ACL_ADD_SUCCESS_COUNT=3
POSTSTATE_EXACT_RELAY_ACL_COUNT=3
POSTSTATE_EXACT_CONTRACT_PROVEN=true
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

The only live mutation later authorized by ID24 is the exact three-entry Dynamic Security role ACL change plus bounded rollback of those same exact entries if needed.

## Private/public boundary

Private evidence may contain the SSH target, raw Docker inspect output, raw DynSec JSON, active client/role names, system ID, private paths, provisioning configuration metadata, and the private prechange snapshot/hash authority. None may be posted to public GitHub.

Public-safe evidence is limited to exact source/package commits, booleans, sanitized counts, PASS/STOP classification, rollback status, and next-route classification.
