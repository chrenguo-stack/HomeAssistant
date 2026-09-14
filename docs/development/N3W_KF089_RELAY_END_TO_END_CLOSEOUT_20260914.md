# N3-W KF-089 Relay End-to-End Closeout

Status: `PUBLIC_SAFE_CLOSEOUT`
Date: `2026-09-14`
Scope: KF-089 Relay end-to-end acceptance from the provisioned ESP32-C6 node through ESP-NOW, gateway MQTT ingress, Broker, and Manager acceptance. Home Assistant entity/display propagation is explicitly outside this closeout.

## 1. Final result

```text
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE

KF089_RELAY_END_TO_END_CLOSEOUT=PASS
```

The final live revalidation used one fresh Board-B Relay-only power window while Board A remained powered and Direct. A 10-second pre-window proved zero accepted Relay records. During the fresh Relay window the Manager accepted 38 Relay telemetry records, rejected 0, classified 0 as duplicates, and observed exactly one accepted node/gateway route.

```text
PREWINDOW_ACCEPTED_RELAY_COUNT=0
PREWINDOW_QUIESCENCE_ELAPSED_SECONDS=10.003290081047453
RELAY_WINDOW_ELAPSED_SECONDS=384.16830721497536
WINDOW_ACCEPTED_RELAY_COUNT=38
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_ACCEPTED_RELAY_ROUTE_COUNT=1
```

## 2. Repository and review authority

Fresh repository main observed before this closeout:

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
```

The accepted live package stack remains review-only and unmerged at the time of this archive:

```text
PR400_STATE=OPEN_DRAFT_UNMERGED
PR400_HEAD=b973934b760db975ada601819191c62fe0513a9e
PR400_PURPOSE=MANAGER_RELAY_DYNSEC_ACL_SOURCE_REPAIR_AND_ID24_PACKAGE

PR403_STATE=OPEN_DRAFT_UNMERGED
PR403_HEAD=1f4cb36a2d1180753556eb08d2b46fa180d423e0
PR403_PURPOSE=ID25_MANAGER_RELAY_SUBSCRIPTION_REACTIVATION

PR404_STATE=OPEN_DRAFT_UNMERGED
PR404_HEAD=83006bc87904843d6ca784355556032852c3813d
PR404_PURPOSE=ID26_MINIMAL_END_TO_END_RELAY_REVALIDATION
```

The physical/runtime acceptance is therefore proven independently of repository-main integration. The corresponding source/guard stack must still be integrated through the normal PR path before current main can be described as containing the complete KF-089 Relay receive repair.

## 3. Root-cause chain

KF-089 began with a provisioned cold-boot failure: when Wi-Fi was unavailable, the product startup gate required `wifi_connected()` before the Relay-capable N3-W runtime could initialize. That startup defect was repaired earlier and durable evidence subsequently proved Direct-to-DISCOVERY transition, autonomous channel scanning, A/B ESP-NOW reachability, Relay advertisement acceptance, and authenticated Relay acquisition.

Schema-v5 two-board validation then proved the board-side telemetry chain through Board A forward submission. The remaining T1 acceptance failure was localized separately:

```text
BOARD_SIDE_RELAY_CHAIN=PROVEN
MANAGER_RELAY_INGRESS=NOT_PROVEN_BEFORE_ID24
```

The downstream root cause was the active Manager Dynamic Security role: default subscribe and client-receive behavior was deny, while the Manager role had no exact Relay ingress receive grants. The required least-privilege topic is:

```text
gh/v1/<sid>/ingress/gateway/+/+/frame
```

and the required receive ACL trio is:

```text
subscribePattern
publishClientReceive
unsubscribePattern
```

No broad `ingress/gateway/#` grant is part of the repair.

## 4. ID24 — Dynamic Security ACL repair

Authorization and execution were one-shot and are permanently consumed.

```text
ID24_EXECUTION_PACKAGE_COMMIT=b973934b760db975ada601819191c62fe0513a9e
ID24_REPAIR_RESULT=PASS
SOURCE_CONTRACT_REPAIRED=true
LIVE_PRESTATE_DEFECT_PROVEN=true
PRECHANGE_DYNSEC_SNAPSHOT_SHA256_RECORDED=true
TARGET_ACL_ADD_SUCCESS_COUNT=3
POSTSTATE_EXACT_RELAY_ACL_COUNT=3
POSTSTATE_EXACT_CONTRACT_PROVEN=true
MANAGER_RUNTIME_STABLE=true
BROKER_RUNTIME_STABLE=true
ROLLBACK_ATTEMPTED=false
DYNSEC_MUTATION=true
```

ID24 modified only the exact live Dynamic Security ACL contract. It did not restart the Manager or Broker and did not run an application MQTT probe, board access, or RF experiment.

## 5. ID25 — Manager subscription reactivation

Because ID24 repaired the Broker authorization in place, the already-running Manager MQTT session had not yet been forced through a fresh `_on_connect()` subscription cycle. ID25 therefore performed exactly one controlled Manager restart.

```text
ID25_EXECUTION_PACKAGE_COMMIT=1f4cb36a2d1180753556eb08d2b46fa180d423e0
ID25_REACTIVATION_RESULT=PASS
SOURCE_SUBSCRIPTION_CONTRACT_PROVEN=true
LIVE_REPAIRED_DYNSEC_PRESTATE_PROVEN=true
MANAGER_RESTART_COMMAND_COUNT=1
MANAGER_RESTART_COMPLETED=true
MANAGER_CONTAINER_ID_PRESERVED=true
MANAGER_IMAGE_PRESERVED=true
MANAGER_STARTED_AT_CHANGED=true
MANAGER_RUNNING=true
BROKER_RESTART=false
BROKER_RUNTIME_STABLE=true
POSTRESTART_RELAY_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_DIRECT_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_FAILURE_LOG_ABSENT=true
LIVE_REPAIRED_DYNSEC_POSTSTATE_PROVEN=true
DYNSEC_STATE_UNCHANGED=true
DYNSEC_MUTATION=false
```

ID25 proved the expected subscription path was reactivated after the ACL repair. It deliberately did not claim end-to-end Relay delivery.

## 6. ID26 — minimal fresh end-to-end Relay revalidation

ID26 was intentionally narrower than the historical two-board diagnostic capture. No USB, serial, firmware write, NVS write, Manager/Broker restart, DynSec mutation, MQTT test publish, or extra MQTT subscriber was used.

Execution conditions:

```text
BOARD_A=POWERED_DIRECT_UNTOUCHED
BOARD_B_INITIAL=POWERED_OFF_AT_QUALIFIED_RELAY_ONLY_LOCATION
OTHER_RELAY_TEST_SENDERS=POWERED_OFF
BOARD_A_USB_ACCESS=false
BOARD_B_USB_ACCESS=false
SERIAL_OPEN=false
```

The executor first exact-bound the Manager/Broker and the repaired DynSec contract, then required the Board-B-off quiescence window to contain no accepted Relay telemetry. Only after this zero baseline did the single Board B power window begin.

Final ID26 closure:

```text
ID26_EXECUTION_PACKAGE_COMMIT=83006bc87904843d6ca784355556032852c3813d
SOURCE_END_TO_END_ORACLE_CONTRACT_PROVEN=true
T1_ACCESS_OCCURRED=true
LIVE_REPAIRED_DYNSEC_PRESTATE_PROVEN=true
PRE_WINDOW_DYNSEC_SNAPSHOT_SHA256_RECORDED=true
PREWINDOW_ACCEPTED_RELAY_COUNT=0
PREWINDOW_QUIESCENCE_ELAPSED_SECONDS=10.003290081047453
RELAY_WINDOW_ELAPSED_SECONDS=384.16830721497536
BOARD_B_FRESH_RELAY_POWER_WINDOW_COMPLETED=true
CONTROLLED_RF_EXPERIMENT=true
WINDOW_ACCEPTED_RELAY_COUNT=38
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_ACCEPTED_RELAY_ROUTE_COUNT=1
MANAGER_RUNTIME_STABLE=true
BROKER_RUNTIME_STABLE=true
LIVE_REPAIRED_DYNSEC_POSTSTATE_PROVEN=true
DYNSEC_STATE_UNCHANGED=true
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
REVALIDATION_RESULT=PASS
NEXT_ROUTE=KF089_RELAY_END_TO_END_CLOSEOUT
```

The clean zero baseline plus one fresh power window and exactly one accepted Relay route makes the positive Manager evidence attributable to the intended fresh Board B → Board A Relay path rather than historical log residue or another Relay sender.

## 7. Safety invariants preserved

Across ID26:

```text
BOARD_A_PHYSICAL_MUTATION=false
BOARD_A_USB_ACCESS=false
BOARD_B_USB_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
HOST_NVS_WRITE=false
T1_FILE_WRITE=false
T1_DOCKER_MUTATION=false
MANAGER_RESTART=false
BROKER_RESTART=false
DYNSEC_MUTATION=false
MQTT_TEST_PUBLISH=false
MQTT_EXTRA_SUBSCRIBER=false
AUTOMATIC_RETRY=false
AUTOMATIC_ROLLBACK=false
```

ID24/ID25/ID26 authorizations were one-shot, consumed, and non-replayable.

## 8. Product acceptance boundary after closeout

The following KF-089 stages are now accepted:

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

Still not claimed by this closeout:

```text
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

The successful cold/fresh Relay path does not by itself prove a live Direct→Relay transition or later Relay→Direct recovery in the same application session.

## 9. KF-089 regression disposition

KF-089 remains classified as `PRODUCT` and is `GUARDED` on this accepted stack. The regression boundary now includes both parts of the discovered product path:

1. provisioned Relay-capable runtime startup must not be gated on an existing Wi-Fi association;
2. the Manager service identity plan must grant only the exact Relay ingress receive ACL trio while default deny remains in force.

The accepted runtime additionally requires a fresh Manager MQTT connection/subscription cycle after an in-place live ACL repair. Normal deployments that materialize the corrected source contract from startup should obtain the exact role contract directly; the one-time ID24/ID25 recovery sequence is historical repair evidence, not a normal product startup procedure.

## 10. PR stack closeout and merge route

No merge is authorized by this archive. The safe integration order is:

```text
1. PR #400
   retarget/review against current main
   -> integrate ID23 predecessor material plus the exact Manager Relay DynSec source repair and ID24 package

2. PR #403
   after #400 integration, retarget/review against refreshed main
   -> integrate ID25 subscription-reactivation package and guards

3. PR #404
   after #403 integration, retarget/review against refreshed main
   -> integrate ID26 minimal end-to-end revalidation package and guards

4. KF-089 closeout documentation PR
   after the code/package stack is integrated, retarget/review against refreshed main
   -> integrate current-state, known-failure, and closeout records
```

Because PR #400 is based on the ID23 branch, retargeting it to main must be preceded by a fresh changed-file/diff review so that the intended ID23 predecessor artifacts are consciously included. PR #399 can be closed as superseded only after the integrated PR path is proven to contain the required ID23 authority. PR #402 is a historical read-only recovery package and is not a required ancestor of the PR #400 → #403 → #404 integration chain.

Do not merge a stacked child into its feature-branch base and mistake that for integration into `main`. Each step must be re-read after retarget/merge, and post-merge checks must be evaluated on the resulting main commit using the repository's GitHub-authority guard rules.

## 11. Public/private evidence boundary

Public GitHub contains only the sanitized closures, counts, hashes, source/tests/executors, PR heads, and this closeout. Raw Manager logs, raw Dynamic Security JSON, full route identities, SSH target, local private paths, and any credentials remain private.

```text
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_PATH_PUBLISHED=false
PRIVATE_EVIDENCE_SECRET_VALUES_PUBLISHED=false
```

The user-supplied sanitized ID24/ID25/ID26 closures are the public-safe live acceptance authority used by this archive. No raw private evidence was copied into GitHub during closeout.

## 12. Closeout status

```text
GITHUB_CLOSEOUT_ARCHIVE_CREATED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURE_DISPOSITION_DEFINED=true
CURRENT_STATE_UPDATE_REQUIRED=true
CURRENT_STATE_INDEX_UPDATE_REQUIRED=true
PR_STACK_MERGE_ROUTE_DEFINED=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
UNARCHIVED_CRITICAL_KNOWLEDGE_FROM_CHAT=0

NEXT_SAFE_ENTRY_POINT=KF089_PR_STACK_INTEGRATION_REVIEW
PHYSICAL_OR_T1_ACTION_REQUIRED=false
```
