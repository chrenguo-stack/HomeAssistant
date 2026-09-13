# N3-W Current State

Updated: 2026-09-13  
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W / KF-089 state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
REPOSITORY_MAIN_TREE=91d2e4767887dad86525cf521e476d4a1234551a

PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5

ID21_EXECUTION_PACKAGE_COMMIT=9ebe5968e2f06f23a657abbeeb68c4094b445a66
ID22_EXECUTION_PACKAGE_COMMIT=23b3dc63dc112979a8e94928185daf8af2da6640
ID23_EXECUTION_PACKAGE_COMMIT=17709dca4dec4dc5d4f8fceb4c6dbfc135becfa4

ID24_REPAIR_PR=400
ID24_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
ID24_REPAIR_PR_STATE=OPEN_DRAFT_UNMERGED
```

Repository `main` must always be queried fresh. Open stacked PRs and documentation branches do not redefine `main` until merged. Product-behavior and diagnostic authorities remain separately frozen from repository-main advancement.

Active architecture authority remains:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current product direction:

- provisioned N3-W communication runtime does not require an existing Wi-Fi association to start;
- Direct remains preferred;
- when Direct is unavailable, node-local bounded autonomous Relay discovery is allowed;
- full custom radio-ownership architecture remains deferred unless new evidence requires it.

## KF-089 evidence chain

### ID21 — board-side Relay chain

```text
ID21_RESULT=PASS
B_RELAY_ACTIVE=PROVEN
B_AUTHENTICATED_RELAY_ACQUISITION=PROVEN
B_RELAY_TELEMETRY_SUBMISSION=PROVEN
B_UNICAST_TX_COMPLETION=PROVEN
A_COMPACT_RX=PROVEN
A_COMPACT_DECODE=PROVEN
A_COMPACT_FORWARD_ATTEMPT=PROVEN
A_COMPACT_FORWARD_SUBMIT=PROVEN
BOARD_SIDE_RELAY_CHAIN=PROVEN
```

The old boundary `FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX` is retired.

### ID22R2 — bounded T1/Manager Relay ingress confirmation

```text
ID22R2_RESULT=STOP
FIRST_FAILED_OPERATION=T1_MANAGER_RELAY_ACCEPTANCE
BOARD_SIDE_RELAY_CHAIN_PROVEN_IN_ID22_SESSION=true
MANAGER_ACCEPTED_RELAY_COUNT=0
MANAGER_REJECTED_RELAY_COUNT=0
MANAGER_RELAY_INGRESS=NOT_PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

ID22R2 proved selective RF behavior and the board-side Relay chain in the same session while the current Manager remained alive and continued accepting Direct telemetry. Absence of Relay acceptance/rejection logs did not by itself prove where the Broker/Manager path stopped.

### ID23 — live Dynamic Security forensic and offline exact authority resolution

The original one-shot ID23 executor correctly stopped fail-closed when two Manager-like DynSec clients were present:

```text
ID23_EXECUTOR_RESULT=STOP
FIRST_FAILED_OPERATION=T1_DYNSEC_STATE
STOP_REASON=Manager DynSec client count=2
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

Using only the already-captured private ID23 Docker inspect and Dynamic Security evidence, a later offline exact runtime-to-DynSec match resolved the active Manager uniquely:

```text
ID23_POSTEXEC_OFFLINE_ADJUDICATION=PASS
RUNTIME_MANAGER_COUNT=1
MANAGER_DYNSEC_CANDIDATE_COUNT=2
ACTIVE_MANAGER_EXACT_MATCH_COUNT=1

DYNSEC_DEFAULT_SUBSCRIBE_DENY=true
DYNSEC_DEFAULT_PUBLISH_CLIENT_RECEIVE_DENY=true
ACTIVE_MANAGER_RELAY_SUBSCRIBE_ALLOW_COUNT=0
ACTIVE_MANAGER_RELAY_RECEIVE_ALLOW_COUNT=0
ACTIVE_MANAGER_MATCHES_RELAY_ACL_DEFECT=true

NODE_CLIENT_COUNT=3
NODE_SELF_GATEWAY_PUBLISH_ALLOW_COUNT=3
```

Therefore the current proven blocker is:

```text
MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
LIVE_T1_NODE_SELF_GATEWAY_PUBLISH_ACL=PROVEN_FOR_ALL_3_NODE_CLIENTS
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
```

This proves a real blocking defect. It does not prove that no additional downstream defect exists after that blocker is repaired.

## ID24 repair-package authority

PR #400 carries the source repair and repository-versioned live repair package.

```text
ID24_EXACT_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
ID24_DEDICATED_CI_RUN=34764719402
ID24_DEDICATED_CI=PASS
ID24_PUBLIC_REPOSITORY_SAFETY_RUN=34764719347
ID24_PUBLIC_REPOSITORY_SAFETY=PASS
ID24_HOST_ONLY_PREPARE_ACCEPTANCE=PASS
```

The repaired Manager service identity contract grants only the exact Relay frame topic:

```text
gh/v1/<system_id>/ingress/gateway/+/+/frame
```

with the least-privilege receive trio:

```text
subscribePattern
publishClientReceive
unsubscribePattern
```

The Host-accepted ID24 executor requires before any separately authorized live mutation:

- exact live Manager/Broker binding;
- exact active Manager DynSec identity and role binding;
- proof that the missing-Relay-ACL defect still exists;
- fresh private prechange Dynamic Security snapshot plus SHA256 authority;
- mutation limited to the exact three ACL type/topic pairs above;
- exact poststate with one target ACL per type, default deny preserved, Direct ingress intact, and no broader Relay grant;
- bounded rollback after any started mutation that does not reach the exact repaired poststate;
- Manager/Broker runtime identity and restart stability.

No live ID24 mutation has been authorized or executed.

## Current KF-089 product boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PROVEN
B_UNICAST_TX_COMPLETION=PROVEN
A_COMPACT_RX=PROVEN
A_COMPACT_DECODE=PROVEN
A_COMPACT_FORWARD_SUBMIT=PROVEN
BOARD_SIDE_RELAY_CHAIN=PROVEN

MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNRESOLVED_LAYER=POST_REPAIR_BROKER_TO_MANAGER_RELAY_INGRESS_AND_END_TO_END_CONFIRMATION
```

## T1 runtime authority

The predecessor T1 runtime-convergence detour remains closed PASS:

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
ACTIVE_DETOUR=NONE
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
N3W_ACTIVE_COMPOSE_LINEAGE_COUNT=1
BROKER_NETWORK_COUNT_FINAL=2
BROKER_RUNTIME_MAPPING_COUNT=3
BROKER_HOST_PUBLICATION_RUNTIME=PASS
BROKER_TLS_DYNSEC_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS
HA_TO_BROKER_RUNTIME_CONTINUITY=PASS
T1_RUNTIME_RESIDUE_POSTCHECK=PASS
T1_CONTROLLED_REBOOT_BOOT_RECOVERY=PASS
```

Last ID23 read-only observation also found the authoritative Manager and Broker running with stable container identity/restart state. Those observations are historical runtime evidence, not permission to assume the live state is unchanged. A future ID24 mutation must perform a fresh read-only runtime and DynSec preclaim before authorization is consumed and before any ACL mutation.

Detailed T1 convergence archive:

`docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`

Current ID21–ID24 public-safe alignment:

`docs/development/N3W_KF089_ID21_ID24_CURRENT_STATE_ALIGNMENT_20260913.md`

## Physical boundary

```text
BOARD_A_CURRENT_POWER_STATE=UNKNOWN
BOARD_B_CURRENT_POWER_STATE=UNKNOWN
BOARD_A_ACCESS_DURING_ID23=false
BOARD_B_ACCESS_DURING_ID23=false
CONTROLLED_RF_EXPERIMENT_DURING_ID23=false
```

ID21/ID22 already supplied the required board-side proof. No new board/RF replay is justified merely to repair the proven Manager DynSec blocker. Board access remains outside the current repair gate.

## Required guards

- USB port is a locator only and is not board identity authority.
- Any board-targeted mutation requires explicit operator target/connection confirmation and fresh silicon identity before write.
- Consumed one-shot authorizations are never replayed.
- Absence of Broker/Manager per-frame logs is not proof of no publish/no receive unless an independent negative oracle exists.
- Manager/Broker authority must not be selected by container name alone.
- DynSec mutation must exact-bind the active Manager identity and role to the current runtime.
- DynSec default deny must remain deny after the repair.
- The repair may add only the exact Relay topic receive trio; broader `gateway/#`, `ingress/#`, `gh/#`, or `#` grants are forbidden.
- A fresh private prechange DynSec snapshot plus SHA256 authority is required before mutation.
- Once any ACL mutation starts, any uncertain/failing path must enter the bounded transaction rollback and independently re-read the live DynSec state.
- Rollback authority is restoration of the proven prestate, not individual remove-command return codes.
- A successful ACL repair does not itself prove KF-089 end-to-end Relay telemetry; a later bounded end-to-end verification remains required.

## Current ONE gate

The Host/GitHub-only preparation gate is now accepted at exact head `b973934b760db975ada601819191c62fe0513a9e`.

```text
PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE=PASS
NEXT_ONE_GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION
LIVE_T1_MUTATION_AUTHORIZATION_GRANTED=false
```

The next action is authorization discussion only. No T1 mutation may occur until a fresh explicit one-shot authorization is bound to the exact accepted ID24 head and execution package.

## Route after a successful ACL repair

```text
MANAGER_RELAY_DYNSEC_ACL_REPAIR
-> MANAGER_RELAY_SUBSCRIPTION_REACTIVATION / BOUNDED_RUNTIME_CONFIRMATION
-> MINIMAL_END_TO_END_RELAY_TELEMETRY_VERIFICATION
-> KF089_END_TO_END_RELAY_TELEMETRY_ADJUDICATION
```

Public GitHub stores source, tests, hashes, sanitized closures, architecture decisions, and sanitized runtime alignment. Raw Dynamic Security state, credentials, private node/service identities, raw Docker evidence, raw Broker logs, raw NVS, complete board identities, private host details, private paths/addresses, and other sensitive evidence remain private/local.
