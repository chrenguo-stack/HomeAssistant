# N3-W T1 Core Updater U1 R4 Manager A -> B live reapply authorization

Date: 2026-11-05

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R4_MANAGER_A_TO_B_LIVE_REAPPLY_AUTHORIZATION_20261105_01

PR=777
BRANCH=test/n3w-u1-manager-a-to-b-red-regression-20261104
FRESH_REBIND_HEAD=acc3703c84be3dcfa68104becfb23d64bf055b76

EXACT_UPDATER_SOURCE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
EXACT_PACKAGE_ARTIFACT_ID=13336359358
EXACT_PACKAGE_ARTIFACT_DIGEST_SHA256=e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
EXACT_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
ARTIFACT_EXPIRED=false
CI_RUN_ID=41854863798
CI_RESULT=SUCCESS

CURRENT_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
CURRENT_HEALTH_STATE=HEALTHY
CURRENT_TRANSACTION_STATUS=ROLLED_BACK
CURRENT_RECOVERY_REQUIRED=false

TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
TARGET_MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc

PROPOSED_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_REAPPLY_U1_R4_20261105_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
APPLY=false
ROLLBACK=false
BOARD_ACCESS=false
MERGE=false
```

## Fresh rebind result

The exact repaired package remains bound to source
`fc1e1bee1f158cc199413ead26564938fca5b1a9`. The package is unexpired and its
CI run remains successful.

Fresh comparison from that exact source head to current PR #777 head shows
documentation/state-record changes only. No Manager or updater source drift
requires a rebuild.

## Exact V2 apply contract

The exact updater CLI requires:

```text
apply
--target-manifest <manager-target-v2.json>
--baseline-manifest <upgrade-baseline-a.json>
--image-tar <greenhouse-manager-arm64.tar>
--authorization-id <fresh one-shot authorization>
--confirmation T1_CORE_UPDATER_APPLY
```

The V2 confirmation token is exactly:

```text
T1_CORE_UPDATER_APPLY
```

## Required pre-mutation guard

A later explicitly authorized R4 execution must stop before apply unless fresh
read-only evidence proves all of the following:

```text
UPDATER_STATUS=PASS
RECOVERY_REQUIRED=false
TRANSACTION_STATUS=ROLLED_BACK

RUNTIME_STATE=PASS
RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
HEALTH_STATE=HEALTHY
MANAGER=local/greenhouse-manager:fresh-b863ddd95909

INSPECT_MANAGER=PASS
PLAN=PASS
PLAN_MUTATION=false
PLAN_CURRENT_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
PLAN_TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
TARGET_ARCHIVE_VERIFIED=true
ROLLBACK_AVAILABLE=true
```

Any drift stops before authorization claim/consumption.

## Authorized scope after explicit grant

Exactly one R4 apply may be invoked if every precondition passes.

Allowed:
- exact package hash verification;
- fresh read-only status/runtime-state/inspect/plan;
- one updater-owned V2 Manager A -> B apply;
- updater-owned service lifecycle required by that apply;
- Manager image binding A -> B only;
- post-apply status/runtime-state/inspect verification;
- evidence archival.

Forbidden:
- replay R3 or reconciliation authorizations;
- second apply after any failure;
- blind explicit rollback after failure;
- manual transaction edit/delete;
- Home Assistant image mutation;
- Broker image mutation;
- credentials/DynSec/pairing/registration mutation;
- board access;
- PR merge.

## PASS target

```text
APPLY_STATUS=PASS
APPLY_TRANSACTION_STATUS=COMMITTED
APPLY_T1_MUTATION=true

POST_RECOVERY_REQUIRED=false
POST_TRANSACTION_STATUS=COMMITTED
POST_RUNTIME_CLASS=TARGET_BOUND_RUNNING
POST_HEALTH_STATE=HEALTHY
POST_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
POST_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
POST_BROKER=local/n3w-mosquitto:2.1.2-3184566d
```

## Failure boundary

If the preflight fails, authorization must remain unclaimed/unconsumed.

Once apply is invoked, the one-shot authorization is consumed regardless of
PASS or FAIL.

On apply failure:
- do not invoke a second apply;
- do not blindly invoke explicit rollback;
- capture read-only status/runtime-state/inspect;
- stop at a separate recovery decision boundary.

## Authorization boundary

The user explicitly granted the fresh one-shot R4 live apply authorization.

```text
AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_REAPPLY_U1_R4_20261105_01
AUTHORIZATION_GRANTED=true
AUTO_EXECUTE=true
STOP_BEFORE_APPLY_ON_PREFLIGHT_DRIFT=true
```


## Explicit authorization grant

```text
AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_REAPPLY_U1_R4_20261105_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

PERMITTED_APPLY_INVOCATIONS=1
SECOND_APPLY_ALLOWED=false
BLIND_ROLLBACK_ALLOWED=false
MERGE_ALLOWED=false

EXECUTION_GATE=N3W_T1_CORE_UPDATER_U1_R4_MANAGER_A_TO_B_LIVE_REAPPLY_EXECUTION_20261105_01
```

The authorization remains unclaimed and unconsumed until all fresh pre-mutation
guards pass and the single updater-owned apply invocation is about to occur.


## Execution attempt 01 — local transport preflight stop

```text
EXECUTION_ATTEMPT=01
RESULT=STOP_BEFORE_T1_COMMANDS
LOCAL_EXACT_PACKAGE=PASS
SSH_AUTH_PROMPT_REACHED=true
SSH_CONTROLMASTER_CREATED=false
FAILURE_REASON=LOCAL_UNIX_CONTROL_SOCKET_PATH_TOO_LONG

R4_PREFLIGHT_STARTED=false
APPLY_INVOKED=false
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
T1_MUTATION=false
```

The first execution script stopped on the Mac while creating the SSH
ControlMaster socket. The ControlPath inherited the long evidence-directory
path and exceeded the Unix-domain-socket path limit. No remote staging command,
updater preflight, apply invocation, transaction write, or service mutation was
reached.

The one-shot authorization therefore remains valid, granted, unclaimed and
unconsumed. The executor may be retried with a short temporary ControlPath.


## Execution closure

```text
EXECUTION_RESULT=CLOSED_PASS
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

APPLY_INVOCATION_COUNT=1
APPLY_STATUS=PASS
APPLY_TRANSACTION_STATUS=COMMITTED
APPLY_T1_MUTATION=true

POST_RECOVERY_REQUIRED=false
POST_RUNTIME_CLASS=TARGET_BOUND_RUNNING
POST_HEALTH_STATE=HEALTHY
POST_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210

SECOND_APPLY_ALLOWED=false
BLIND_ROLLBACK_ALLOWED=false
STOP=true
```

Closure authority:
`docs/development/N3W_T1_CORE_UPDATER_U1_R4_MANAGER_A_TO_B_LIVE_REAPPLY_CLOSURE_20261105.md`.
