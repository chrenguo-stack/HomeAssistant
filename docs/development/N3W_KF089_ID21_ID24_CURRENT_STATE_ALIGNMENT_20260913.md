# N3-W KF-089 ID21–ID24 Current-State Alignment — 2026-09-13

Status: `PUBLIC_SAFE_PROGRESS_ALIGNMENT`

This document aligns the durable public-safe KF-089 route after the Schema-v5 two-board Relay validation, bounded T1 ingress confirmation, live Dynamic Security forensic, and Host-only ID24 repair-package acceptance.

## Frozen evidence chain

```text
ID21_RESULT=PASS
BOARD_SIDE_RELAY_CHAIN=PROVEN

ID22R2_RESULT=STOP
FIRST_FAILED_OPERATION=T1_MANAGER_RELAY_ACCEPTANCE
MANAGER_RELAY_INGRESS=NOT_PROVEN

ID23_EXECUTOR_RESULT=STOP
ID23_POSTEXEC_OFFLINE_ADJUDICATION=PASS
MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
LIVE_T1_NODE_SELF_GATEWAY_PUBLISH_ACL=PROVEN_FOR_ALL_3_NODE_CLIENTS
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING

PR400=OPEN_DRAFT_UNMERGED
ID24_EXACT_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
ID24_DEDICATED_CI_RUN=34764719402
ID24_DEDICATED_CI=PASS
ID24_PUBLIC_REPOSITORY_SAFETY_RUN=34764719347
ID24_PUBLIC_REPOSITORY_SAFETY=PASS
ID24_HOST_ONLY_PREPARE_ACCEPTANCE=PASS
```

## Current product boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PROVEN
B_UNICAST_TX_COMPLETION=PROVEN
A_COMPACT_RX=PROVEN
A_COMPACT_DECODE=PROVEN
A_COMPACT_FORWARD_SUBMIT=PROVEN
BOARD_SIDE_RELAY_CHAIN=PROVEN

MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

The old boundary `FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX` is retired. The first unresolved end-to-end layer is now the repaired Broker/Manager Relay ingress path after the proven live Manager DynSec ACL blocker is removed.

## Current ONE gate

```text
NEXT_ONE_GATE=PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE
GATE_STATE=HOST_ACCEPTED_AWAITING_SEPARATE_LIVE_T1_MUTATION_AUTHORIZATION
```

No T1 mutation, Board A/B access, RF execution, credential rotation, Broker replacement, or PR merge is authorized by this alignment.

## Repair-package contract

The Host-accepted ID24 package is bound to PR #400 exact head `b973934b760db975ada601819191c62fe0513a9e` and requires, before any future separately authorized live mutation:

- exact live Manager/Broker binding;
- exact active Manager DynSec identity/role binding;
- proof that the live missing-Relay-ACL defect still exists;
- fresh private prechange Dynamic Security snapshot plus SHA256 authority;
- mutation limited to the exact Relay frame topic `gh/v1/<system_id>/ingress/gateway/+/+/frame` and the three receive ACL types `subscribePattern`, `publishClientReceive`, `unsubscribePattern`;
- exact least-privilege postcheck with default deny preserved and no broader Relay grant;
- bounded rollback after any started mutation that does not reach the exact repaired poststate;
- stable Manager/Broker runtime identity and restart state.

A successful ACL repair does not itself prove KF-089 end-to-end Relay telemetry. A later bounded reactivation / end-to-end verification remains required.

## Privacy boundary

Raw DynSec JSON, credential material, private client/role/node identities, T1 target details, raw Docker inspect, raw Broker logs, raw NVS, complete board identities, and private paths remain private evidence only.
