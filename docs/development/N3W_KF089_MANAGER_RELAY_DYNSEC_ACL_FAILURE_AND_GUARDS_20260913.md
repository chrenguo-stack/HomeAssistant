# KF-089 Manager Relay DynSec ACL Failure and Regression Guards — 2026-09-13

Status: `PUBLIC_SAFE_KNOWN_FAILURE_ADDENDUM`

This is a public-safe KF-089 addendum. It supplements the original KF-089 startup-gate record without rewriting that historical root cause.

## Observed progression

```text
ID21_RESULT=PASS
BOARD_SIDE_RELAY_CHAIN=PROVEN
B_UNICAST_TX_COMPLETION=PROVEN
A_COMPACT_RX=PROVEN
A_COMPACT_DECODE=PROVEN
A_COMPACT_FORWARD_SUBMIT=PROVEN

ID22R2_RESULT=STOP
FIRST_FAILED_OPERATION=T1_MANAGER_RELAY_ACCEPTANCE
MANAGER_ACCEPTED_RELAY_COUNT=0
MANAGER_REJECTED_RELAY_COUNT=0

ID23_EXECUTOR_RESULT=STOP
ID23_POSTEXEC_OFFLINE_ADJUDICATION=PASS
ACTIVE_MANAGER_EXACT_MATCH_COUNT=1
NODE_CLIENT_COUNT=3
NODE_SELF_GATEWAY_PUBLISH_ALLOW_COUNT=3
```

## Proven root cause

The deployed Manager application subscribes to the Relay ingress pattern, while the deployed service-identity DynSec plan omitted the corresponding Manager receive ACL. The live active Manager role matched that source defect.

```text
MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
LIVE_T1_NODE_SELF_GATEWAY_PUBLISH_ACL=PROVEN_FOR_ALL_3_NODE_CLIENTS

DYNSEC_DEFAULT_SUBSCRIBE_DENY=true
DYNSEC_DEFAULT_PUBLISH_CLIENT_RECEIVE_DENY=true
ACTIVE_MANAGER_RELAY_SUBSCRIBE_ALLOW_COUNT=0
ACTIVE_MANAGER_RELAY_RECEIVE_ALLOW_COUNT=0

ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
```

The exact Relay frame pattern is:

```text
gh/v1/<system_id>/ingress/gateway/+/+/frame
```

The missing Manager least-privilege receive contract is:

```text
subscribePattern allow
publishClientReceive allow
unsubscribePattern allow
```

This is a proven blocking defect, not proof that no additional downstream defect exists after repair.

## Source / repair guard

PR #400 carries the source contract repair and ID24 bounded live-repair package.

```text
ID24_EXACT_REPAIR_HEAD=b973934b760db975ada601819191c62fe0513a9e
ID24_DEDICATED_CI_RUN=34764719402
ID24_DEDICATED_CI=PASS
ID24_PUBLIC_REPOSITORY_SAFETY_RUN=34764719347
ID24_PUBLIC_REPOSITORY_SAFETY=PASS
ID24_HOST_ONLY_PREPARE_ACCEPTANCE=PASS
LIVE_T1_MUTATION_AUTHORIZATION_GRANTED=false
```

Regression requirements:

1. Manager application subscription and Manager service-identity ACL generation must remain contract-consistent for the exact Relay frame pattern.
2. The repair may add only `subscribePattern`, `publishClientReceive`, and `unsubscribePattern` for the exact Relay pattern; broader `gateway/#`, `ingress/#`, `gh/#`, or `#` grants are forbidden.
3. DynSec default `subscribe` and `publishClientReceive` deny semantics must remain deny.
4. The active Manager must be exact-bound from the running runtime identity to one DynSec client and expected service role before mutation.
5. A fresh private prechange DynSec snapshot plus SHA256 authority is required before mutation.
6. Once any target ACL mutation starts, any failed or uncertain downstream path must enter bounded rollback; rollback is accepted only after independent live readback proves restoration of the exact prestate.
7. Manager and Broker runtime identity/restart state must remain stable through the bounded repair.
8. A successful ACL repair does not itself prove KF-089 end-to-end Relay telemetry. A later bounded Relay-ingress/end-to-end verification is still required.
9. Consumed ID22/ID23 authorizations remain non-replayable; board/RF replay is not justified merely to repair this Manager ACL blocker.

## Current disposition

```text
KF089_STARTUP_GATE_REPAIR=PASS
BOARD_SIDE_RELAY_CHAIN=PROVEN
MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING=PROVEN
PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE=PASS
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
STATUS=OPEN_UNTIL_LIVE_REPAIR_AND_END_TO_END_RETEST
NEXT_ONE_GATE=REQUEST_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_T1_MUTATION_AUTHORIZATION
```

Raw DynSec state, credentials, private client/role/node identities, raw Docker/Broker evidence, T1 target details, complete board identities, raw NVS, and private paths remain private evidence only.
