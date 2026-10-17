# N3W T1 F5 V1 架构合同 post-merge 状态对齐 — 2026-10-17

## 1. Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_ARCHITECTURE_CONTRACT_POSTMERGE_STATE_ALIGNMENT_20261017_01
STATUS=DOCS_ONLY_ALIGNMENT_PAYLOAD_READY

SOURCE_MAIN=77e403b99fe8bb8dbe75ba04afab470ff9b4c853
PR610_STATE=CLOSED_MERGED
PR610_HEAD=3180a547ad4077a026d65e9766ee15c6111f2432
PR610_MERGE_COMMIT=77e403b99fe8bb8dbe75ba04afab470ff9b4c853
PR610_HEAD_TO_MAIN_CONTENT_DELTA=NONE

F5_ARCHITECTURE_CONTRACT_IN_MAIN=true
F5_ARCHITECTURE_CONTRACT_SOURCE_IMPLEMENTATION_STARTED=false

ALIGNMENT_SCOPE=DOCS_ONLY
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

TERMINATING_CLOSURE_RULE=THIS_ALIGNMENT_PAYLOAD_REACHABLE_FROM_MAIN
F5_ARCHITECTURE_CONTRACT_REPOSITORY_ALIGNMENT_FINAL=false
AUTO_MERGE=false
~~~

## 2. Purpose

PR #610 has merged the reviewed F5 V1 architecture contract into main.

The two current-state ledgers inside that PR were intentionally written before the merge and therefore still describe
PR #610 as an open Draft candidate. This alignment payload updates only that durable repository bookkeeping.

No product source, workflow, tests, T1 runtime state, board state, service state or credential state is changed.

## 3. Exact merged facts

~~~text
OLD_MAIN=cdd597e43149e872e26f81c63bc72f4320e61bcc
PR610_HEAD=3180a547ad4077a026d65e9766ee15c6111f2432
PR610_MERGE_COMMIT=77e403b99fe8bb8dbe75ba04afab470ff9b4c853
NEW_MAIN=77e403b99fe8bb8dbe75ba04afab470ff9b4c853

PREMERGE_OBSERVED_WORKFLOWS=PASS:11/11
READY_TRANSITION_COMPLETED=true
MERGE_METHOD=merge
EXPECTED_HEAD_ENFORCED=true
PR_HEAD_TO_NEW_MAIN_CONTENT_DELTA=NONE
MERGE_ONLY_CONTENT_DRIFT=NONE
~~~

The accepted F5 V1 architecture remains:

- Mac thin production orchestrator;
- minimal durable T1 production run/phase authority;
- reuse of existing F3, explicit provisioning and F4 primitives;
- one production approval for the full normal plan;
- one SSH password per connection epoch, therefore two prompts for one planned reboot;
- no password persistence or new permanent SSH management key in V1;
- initial production override allowlist empty;
- existing 5 GiB F3 reserve remains strict;
- Plan B: preserve T1-A and use fresh T1-B for final physical F5 repeatability acceptance;
- release binding includes supported OS and Docker/Compose versions;
- normal production path does not expose engineering repair commands;
- no ESP32/board work is required by default for F5 process closure.

## 4. F3/F4 and known-failure boundary

~~~text
F3_R4_CLOSED_PASS=true
EXPLICIT_PROVISIONING_CLOSED_PASS=true
F4_RUNTIME_CLOSURE=PASS
F4_DURABLE_REBOOT_LEDGER=REBOOT_ACCEPTED
KF_121_DURABLE_LEDGER_BLOCKER=CLOSED_PASS
F4_REPOSITORY_CLOSURE_FINAL=true
NEW_KF_OPENED_BY_F5_ARCHITECTURE_FREEZE=false
~~~

The planned F5 source work is not itself a product regression and does not reopen F3, F4, KF-121, PR #608 or PR #609.

## 5. Source-implementation boundary

F5 source implementation has not started.

The next source work package remains bounded to the already frozen architecture:

~~~text
F5_SOURCE_BLOCKERS=
PRODUCTION_AUTHORITY;
ORCHESTRATION;
RELEASE_ENVIRONMENT_BINDING;
RESULT_EVIDENCE_CONTRACT

F5_SOURCE_IMPLEMENTATION_STARTED=false
T1_B_ACCESS_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
~~~

F5-1 through F5-6 are intended to be implemented as one coherent source work package, followed by exact release
binding and only then T1-B read-only/live gates.

## 6. Terminating closure rule

This alignment uses the same terminating rule already used for F4:

~~~text
F5 architecture-contract repository alignment is final when this exact alignment payload is reachable from main.
~~~

Once this payload is merged and fresh main verification proves that condition, no second “alignment of the alignment”
commit is required merely to record the same merge.

The alignment PR merge remains a separate explicit authorization decision.

## 7. Next boundary

~~~text
CURRENT_STAGE=F5_0_POSTMERGE_STATE_ALIGNMENT
CURRENT_STOP_POINT=ALIGNMENT_PAYLOAD_READY_FOR_PR_CI_AND_SEPARATE_MERGE_DECISION

NEXT_AFTER_ALIGNMENT_MERGE=
N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_WORK_PACKAGE_PREPARATION

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
