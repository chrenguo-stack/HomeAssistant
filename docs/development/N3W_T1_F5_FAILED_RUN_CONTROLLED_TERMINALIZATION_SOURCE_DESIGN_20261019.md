# N3-W T1 F5 failed production run controlled terminalization — source design

Date: 2026-10-19

## Scope

~~~text
TASK=N3W_T1_F5_FAILED_RUN_CONTROLLED_TERMINALIZATION_SOURCE_DESIGN_20261019_01
SOURCE_ONLY=true
T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

The historical F5-9 run is consumed and non-replayable. It is durably stuck at
`HOST_BASELINE=APPLYING` because the old authority CLI returned exit code 2 for a valid phase context.
Read-only evidence proved the host-baseline business execution ledger is absent.

This recovery does not resume or replay that run. It only changes the F5 production authority ledger from
an active failed pre-business state to a terminal failed state.

## Frozen incident binding

~~~text
RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
PHASE=HOST_BASELINE
FAILING_SOURCE_HEAD=6e228a4b2c7c4ff78918571abb7b583e416615ee
FAILING_RELEASE_ID=b89c9e227e53fcac2ef2717d7b11cd6b64536ce27c9b6b16c2429980049c8a69
FAILING_RELEASE_SHA256=5291042f87686aecbd6b7e52641c10f69cdae0d56abbf675b8eab8c9bfeb8804
TARGET_BINDING_SHA256=280c06d1753dc676ca7c11b1967ae603a432bb3c996abb305a449c85cf5ca3b3
SSH_HOST_KEY_SHA256=2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901
~~~

## Executor contract

The dedicated terminalizer has two commands.

`inspect` is read-only and succeeds only when all frozen incident facts still match:

- target identity is exact;
- run is `IN_PROGRESS`, consumed, non-replayable and non-terminal;
- last claimed phase is exactly `HOST_BASELINE`;
- no phase has completed;
- `HOST_BASELINE` is exactly `APPLYING`;
- phase result/failure fields are still empty;
- run/phase source, release and target bindings are exact;
- the exact host-baseline business-execution claim and completion records derived from the current phase-claim SHA-256 are both absent.

`terminalize` first repeats the full inspection, requires the exact previously observed phase-claim SHA-256 and
the literal confirmation `TERMINALIZE FAILED F5 RUN: YES`, then calls the repository-owned production authority
`fail_phase(... state="FAILED")`.

Accepted poststate is exact:

~~~text
RUN_STATE=TERMINAL
RUN_TERMINAL_STATE=FAIL
RUN_FAILURE_CLASS=FAILED
PHASE_STATE=FAILED
PHASE_FAILURE_CODE=KF122_PHASE_CONTEXT_CLI_STATUS_MISSING
LAST_COMPLETED_PHASE=null
REPLAY_ALLOWED=false
HOST_BASELINE_BUSINESS_EXECUTION_LEDGER=ABSENT
~~~

The tool then rechecks the absence of the business-execution claim/completion records.

## Mutation boundary

The only intended target mutation is the existing F5 production authority's atomic replacement of:

- the historical `phase-HOST_BASELINE.json`;
- the historical `run.json`.

It does not run host-baseline installation, F3, provisioning, F4, service activation, reboot, certificate mutation,
board access, or a replacement production run.

Any prestate drift is a hard stop.

## Authorization

Source/CI/artifact preparation is not a live authorization.

A future target execution requires one fresh explicit authorization limited to:

~~~text
ONE_EXACT_FAILED_RUN_TERMINALIZATION=true
RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
MUTATION_SCOPE=f5_production_authority_ledger_only
PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
REPLAY=false
~~~

After terminalization PASS, a separate fresh F5-9 authorization is still required before the replacement release
can start a new production run.


## Independent source review repair

The first implementation passed its focused tests, but independent review found two blockers before any live use:

1. the underlying two-record fail transition could be interrupted after the phase record became `FAILED` but before the run record became `TERMINAL/FAIL`; the first terminalizer had no legitimate continuation from that partial state;
2. an exception after a target write could be reported as `mutation_performed=false`, which would understate an ambiguous target mutation.

The repaired design adds a dedicated root-owned recovery ledger:

~~~text
RECOVERY_ROOT=/var/lib/n3w-t1-f5-failed-run-terminalizations
RECOVERY_STATE=CLAIMED -> APPLYING -> TERMINALIZED
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
~~~

A future live call must provide a fresh exact recovery authorization ID. The tool durably claims that ID, persists and reads back `APPLYING` before touching the historical production run, and allows continuation only under the same recovery authorization and original phase-claim SHA-256.

If interruption occurs after `phase-HOST_BASELINE.json` becomes the exact incident-specific `FAILED` record but before `run.json` reaches `TERMINAL/FAIL`, the same consumed recovery authorization may resume only the unfinished ledger finalization. It may not rerun the original F5 production phase or create a second authorization.

The CLI now reports a conservative `mutation_state`. Errors after an authorization/recovery write are never represented as a proven no-mutation outcome.

Additional regression coverage includes:
- exact read-only eligible prestate;
- rejection when any host-baseline business-execution record exists;
- wrong phase-claim hash rejection before recovery claim;
- exact confirmation requirement;
- durable recovery authorization binding;
- resume from the bounded phase-failed/run-active split state;
- rejection of a different recovery authorization;
- terminalized production run remains non-replayable.
