# N3-W T1 F4 Stopped Runtime Acceptance Recovery Source Repair Progress — 2026-10-15

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_SOURCE_REPAIR_20261015_01
STATUS=IMPLEMENTED_PENDING_CI_AND_INDEPENDENT_REVIEW

DESIGN_PR=570
DESIGN_HEAD=5e7bdeb384c1684536d40af23454d987603a2ce8

SOCKET_PROBE_REPAIR_PR=569
SOCKET_PROBE_REPAIR_BASE=ffcbb1a890e42ac776c6d90000bf3f25195da01d
SOCKET_PROBE_REPAIR_HEAD=e7f31b4703526442cf14429c4e5ab60924b24eb4

FAILED_LIVE_STAGE=STOPPED_RUNTIME_ACCEPTANCE
FAILED_ACCEPTANCE_AUTHORIZATION=CONSUMED_NO_REPLAY
FAILED_ERROR_CODE=manager_mqtt_socket_count_invalid
FAILED_ROLLBACK_PROVEN=true

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~

## Implementation

The F4 host control now adds one stopped-state recovery command:

~~~text
repair-stopped-runtime-acceptance
~~~

The command:

- accepts only the exact `STOPPED_RUNTIME_ACCEPTANCE` incident prestate;
- binds the failed source, manifest and installed launcher;
- validates the successor exact package with the existing package contract;
- requires the command itself to execute from the validated package launcher;
- permits only the installed F4 launcher to differ from the current package;
- requires the runtime/listeners to remain stopped and persistence/certificate enablement to remain off;
- consumes a distinct one-shot recovery authorization before launcher replacement;
- preserves the failed acceptance facts under explicit `runtime_acceptance_last_failure_*` fields;
- atomically replaces only the F4 launcher;
- returns to `PREPARED` with both activation and runtime-acceptance retry eligibility enabled;
- keeps the failed runtime-acceptance authorization claimed/consumed/no-replay.

No Broker, Manager or Home Assistant service is started by recovery.

## Runtime acceptance successor authority

The generic successor-authorization helper remains strict for persistence/certificate and other stages.

`accept-runtime` now has a bounded retry path only when the transaction explicitly carries:

~~~text
runtime_acceptance_retry_eligible=true
~~~

When a prior acceptance was already claimed, the prior authorization is appended to:

~~~text
runtime_acceptance_authorization_history
~~~

before the new acceptance authorization replaces the current field.

Both activation history and runtime-acceptance history, plus the recovery authorization itself, are included in the
global prior-F4-authorization set. Any prior ID therefore remains permanently unusable.

## Failure behavior

If recovery fails after the recovery authorization is consumed, the existing downstream fail-closed path is reused
under the stage prefix:

~~~text
RUNTIME_ACCEPTANCE_RECOVERY
~~~

A proven rollback records:

~~~text
STOPPED_RUNTIME_ACCEPTANCE_RECOVERY
~~~

and an unproven rollback remains explicitly suffixed `_ROLLBACK_UNPROVEN`.

The recovery authorization is never made reusable.

## Tests added

Source tests now cover:

- the recovery command/confirmation surface;
- exact package-launcher execution authority;
- launcher-only replacement and PREPARED transition;
- preservation of the failed acceptance authorization;
- rejection of a non-launcher package delta;
- fail-closed behavior after a claimed recovery authorization;
- one distinct runtime-acceptance successor after explicit recovery retry eligibility;
- rejection of claimed runtime acceptance without retry eligibility;
- inclusion of recovery IDs and acceptance history in the global prior-authorization set.

Existing activation successor tests remain in force and continue to cover PREPARED -> RUNTIME_STARTED using a new
distinct activation authorization.

## Current boundary

~~~text
SOURCE_IMPLEMENTATION_COMPLETE=true
LIVE_RECOVERY_AUTHORIZATION_GRANTED=false
LIVE_SUCCESSOR_ACTIVATION_AUTHORIZATION_GRANTED=false
LIVE_SUCCESSOR_ACCEPTANCE_AUTHORIZATION_GRANTED=false

CURRENT_REAL_T1_STAGE=STOPPED_RUNTIME_ACCEPTANCE
CURRENT_REAL_T1_RUNTIME_STARTED=false
~~~

No live T1 command is authorized by this source-repair gate.

## Next review condition

The gate cannot close until:

1. exact-head source CI is green;
2. exact-control-package CI is green;
3. independent diff review confirms no authorization or runtime-start bypass;
4. package execution-entrypoint binding and launcher-only delta are confirmed;
5. failure paths remain fail-closed.

Only after those pass may an exact recovery artifact and live preexecution plan be designed.
