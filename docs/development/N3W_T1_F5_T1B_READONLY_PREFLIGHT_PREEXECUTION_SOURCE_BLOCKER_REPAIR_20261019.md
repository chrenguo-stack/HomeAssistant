# N3W T1 F5-8 T1-B Read-only Preflight — Preexecution Source Blocker Repair

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_T1B_READONLY_PREFLIGHT
USER_T1B_READONLY_AUTHORIZATION=GRANTED
T1_ACCESS_PERFORMED=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

F5-7 durable release archive is CLOSED_PASS. Before opening an SSH session to T1-B, the packaged
F5-8 call path was re-read from the accepted production source and exact release.

## Deterministic blocker found before T1 access

The packaged F2 read-only executor requires the exact confirmation:

~~~text
READONLY FRESH T1 PREFLIGHT: YES
~~~

but the production runtime passed:

~~~text
READONLY N3W T1 FRESH PREFLIGHT: YES
~~~

The executor compares the string exactly and would return
`readonly_confirmation_invalid`. Therefore the final F5 release cannot complete its production
read-only preflight even though the underlying checks are available.

This is a source defect in the Mac production orchestration path. It was found before any T1-B
connection was attempted.

## Minimal repair

The repair is deliberately narrow:

1. define `F2_READONLY_CONFIRMATION` in `tools/n3w_t1_production_runtime.py`;
2. bind it to the executor's already-frozen confirmation text;
3. use that constant in the production preflight invocation;
4. add a regression proving the runtime value equals the packaged executor contract.

No preflight check, SSH policy, capacity rule, release environment policy, production authorization,
F3/F4 behavior or T1 state is changed.

## Release consequence

Because `tools/n3w_t1_production_runtime.py` is part of the approved Mac-orchestrator file set, this
repair changes production release bytes. The currently archived release remains valid historical
evidence for F5-7 attempt history but is superseded for F5-8/F5-9 onward.

After source CI passes, F5-7 release construction must be repeated against the repaired source head,
including fresh source-bound F3/F4/reboot artifacts, exact release build/binding, and durable Mac
archive acceptance. T1-B read-only access remains paused until the repaired release is closed.

## Stop

~~~text
CURRENT_STOP_POINT=WAIT_F5_8_PREFLIGHT_CONFIRMATION_SOURCE_REPAIR_CI
T1B_READONLY_AUTHORIZATION=GRANTED_NOT_CONSUMED
T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~
