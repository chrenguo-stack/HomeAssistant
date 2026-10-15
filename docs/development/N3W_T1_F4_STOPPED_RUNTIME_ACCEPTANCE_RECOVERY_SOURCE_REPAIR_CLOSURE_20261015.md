# N3-W T1 F4 Stopped Runtime Acceptance Recovery Source Repair Closure — 2026-10-15

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_SOURCE_REPAIR_20261015_01
RESULT=CLOSED_PASS

DESIGN_PR=570
DESIGN_HEAD=5e7bdeb384c1684536d40af23454d987603a2ce8

SOURCE_REPAIR_PR=571
SOURCE_REPAIR_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
SOURCE_REPAIR_BASE=5e7bdeb384c1684536d40af23454d987603a2ce8

EXACT_CONTROL_PACKAGE_RUN=38767114055
EXACT_CONTROL_PACKAGE_ARTIFACT_ID=11990381805
EXACT_CONTROL_PACKAGE_ARTIFACT_NAME=n3w-t1-f4-control-package-f0bcc2ac50326b9a988405af8a2aad4c51694810
EXACT_CONTROL_PACKAGE_ARTIFACT_EXPIRED=false

CURRENT_REAL_T1_STAGE=STOPPED_RUNTIME_ACCEPTANCE
CURRENT_REAL_T1_PRODUCTION_SERVICE_START=false
CURRENT_REAL_T1_PERSISTENCE_ENABLED=false
CURRENT_REAL_T1_CERTIFICATE_TIMER_ENABLED=false
FAILED_RUNTIME_ACCEPTANCE_AUTHORIZATION=CONSUMED_NO_REPLAY

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~

## Closure summary

The stopped-runtime-acceptance recovery source repair is complete at exact source
`f0bcc2ac50326b9a988405af8a2aad4c51694810`.

The implementation remains incident-bounded. It does not reset the F4 transaction, does not revive the consumed
runtime-acceptance authorization, and does not start the product runtime during control recovery.

The real T1 has not been touched by this gate and remains safely stopped.

## Source review

### A1 — exact failed prestate binding: CLOSED

Recovery accepts only the real incident class:

~~~text
stage=STOPPED_RUNTIME_ACCEPTANCE
error_code=manager_mqtt_socket_count_invalid
rollback_proven=true
rollback_error_count=0
product_listener_ports=[]
production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false
runtime_acceptance_authorization_claimed=true
runtime_acceptance_authorization_consumed=true
runtime_acceptance_authorization_replay_allowed=false
~~~

It also binds the exact failed source, manifest and installed launcher.

### A2 — live stopped-state proof: CLOSED

The recovery refuses to proceed unless fresh runtime inspection proves:

- Compose runtime probe is PASS;
- running product services are exactly empty;
- Broker and Services unit active states are known non-running states;
- product listener set is empty;
- Broker, Services and certificate timer are exactly disabled;
- certificate timer and certificate lifecycle service are exactly inactive;
- no runtime-acceptance report exists.

Unknown runtime/service state is rejected instead of being treated as stopped.

### A3 — successor package authority: CLOSED

The recovery command must execute from the launcher located inside the already validated successor package.

The executing path, file size and SHA256 must match that package launcher record. A different file path is rejected
even when file contents match.

The successor package must be distinct from the failed source/manifest/launcher.

### A4 — launcher-only installed delta: CLOSED

Every package record other than `tools/n3w_t1_f4_activation_host.py` must match the existing installed binding by
SHA256 and size.

Only:

~~~text
/usr/local/sbin/n3w-t1-f4-activation
~~~

may change during this recovery.

No systemd unit, ingress guard, broker readiness helper or certificate tool is modified.

### A5 — recovery authorization: CLOSED

Recovery uses one new distinct authorization:

~~~text
runtime_acceptance_recovery_authorization_id
~~~

It is claimed/consumed/no-replay before launcher replacement and is included in the global prior-F4-authorization
set.

The failed runtime-acceptance authorization remains consumed and cannot be reused.

### A6 — failed acceptance evidence preservation: CLOSED

Before leaving the STOPPED incident stage, the exact failed acceptance facts are copied into durable
`runtime_acceptance_last_failure_*` fields.

The failed acceptance ID is not silently overwritten.

### A7 — partial launcher replacement durability: CLOSED

After a successful atomic launcher replacement, the new installed-file binding and successor source/manifest are
persisted while the transaction is still in the stopped recovery stage, before PREPARED is declared.

If recovery subsequently fails, the source re-reads the installed launcher and reconciles whether it is exactly:

- the old bound launcher; or
- the new bound launcher.

Any third/unreadable launcher state makes the recovery rollback explicitly unproven.

### A8 — recovery success boundary: CLOSED

Successful control recovery stops at:

~~~text
PREPARED
activation_retry_eligible=true
runtime_acceptance_retry_eligible=true
production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false
~~~

No Broker, Manager or Home Assistant service is started by the recovery command.

### A9 — successor activation: CLOSED

The implementation reuses the existing bounded `activate` path.

A new activation authorization must be distinct from all prior F4 authorizations. The previous activation ID is
preserved in activation history before replacement.

No second runtime-start implementation was added.

### A10 — successor runtime acceptance: CLOSED

A previously claimed runtime acceptance can be retried only when all recovery proof is present:

~~~text
runtime_acceptance_retry_eligible=true
runtime_acceptance_recovery_passed=true
runtime_acceptance_recovery_authorization_claimed=true
runtime_acceptance_recovery_authorization_consumed=true
runtime_acceptance_recovery_authorization_replay_allowed=false
~~~

The current failed acceptance ID must also equal the durable
`runtime_acceptance_last_failure_authorization_id`.

Before the new acceptance ID replaces it, the failed ID is appended to
`runtime_acceptance_authorization_history`.

The recovery authorization and all activation/acceptance history IDs are included in the global prior-authorization
set and can never be reused.

### A11 — fail-closed recovery behavior: CLOSED

A post-claim failure uses the downstream fail-closed path under
`RUNTIME_ACCEPTANCE_RECOVERY`.

A failure is not declared fully proven unless both runtime rollback and launcher-state reconciliation are proven.

Unknown launcher state produces:

~~~text
STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_ROLLBACK_UNPROVEN
~~~

with `rollback_proven=false`.

### A12 — scope: CLOSED

No source delta was made to:

- production Compose;
- Broker configuration;
- Manager application runtime;
- Home Assistant;
- firmware;
- radio state machine;
- board/NVS;
- persistence policy;
- certificate policy.

PR #571 changes only:

~~~text
tools/n3w_t1_f4_activation_host.py
tests/tools/test_n3w_t1_f4_activation_host.py
docs/development/N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_SOURCE_REPAIR_PROGRESS_20261015.md
~~~

## Test closure

The focused source tests cover the recovery command, exact package entrypoint, exact stopped state, launcher-only
delta, pre-replacement authorization claim, failure rollback, runtime-acceptance retry binding, old-ID rejection and
an end-to-end source simulation:

~~~text
STOPPED_RUNTIME_ACCEPTANCE
-> STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_CLAIMED
-> PREPARED
-> ACTIVATION_CLAIMED
-> BROKER_STARTING
-> BROKER_READY
-> SERVICES_STARTING
-> RUNTIME_STARTED
-> RUNTIME_ACCEPTED
~~~

The simulation keeps persistence and certificate timer disabled throughout.

## CI closure

Exact source head `f0bcc2ac50326b9a988405af8a2aad4c51694810`:

~~~text
M0_VERTICAL_SLICE_CI=PASS
C07_NODE_RETIREMENT_CI=PASS
M2_MANAGER_RUNTIME_SECRET_OWNERSHIP_CI=PASS
M2_NODE_AUTH_NATIVE_BOARD_LAB_CI=PASS
M2_NODE_AUTH_BOARD_LAB_CI=PASS
M2_NODE_AUTH_ISOLATED_LAB_CI=PASS
M2_PRIVATE_MOSQUITTO_CI=PASS
M2_DYNAMIC_SECURITY_CI=PASS
H3_N2_STAGE2B3_PAIRING_RUNTIME_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
N3W_T1_F4_EXACT_CONTROL_PACKAGE_CI=PASS
N3W_T1_F4_ACTIVATION_SOURCE_CI=PASS
~~~

The activation-source CI initially found only test-placement/Ruff issues during development. Those were repaired
before the exact closure head. No runtime-policy blocker remained.

## Exact artifact availability

The exact-control-package workflow already produced an unexpired artifact bound to the source closure head:

~~~text
RUN_ID=38767114055
ARTIFACT_ID=11990381805
ARTIFACT_NAME=n3w-t1-f4-control-package-f0bcc2ac50326b9a988405af8a2aad4c51694810
~~~

This closure records artifact availability only. It does not download, hash-bind, transfer or execute that artifact.

Those actions belong to the next gate.

## Remaining live truth

~~~text
KF-121_SOURCE_DEFECT=REPAIRED
KF-121_LIVE_REVALIDATION=PENDING

CURRENT_REAL_T1_STAGE=STOPPED_RUNTIME_ACCEPTANCE
CURRENT_REAL_T1_RUNTIME_STARTED=false

LIVE_RECOVERY_AUTHORIZATION_GRANTED=false
LIVE_SUCCESSOR_ACTIVATION_AUTHORIZATION_GRANTED=false
LIVE_SUCCESSOR_RUNTIME_ACCEPTANCE_AUTHORIZATION_GRANTED=false
~~~

No persistence, certificate, reboot or board step is eligible yet.

## Next ONE Gate

~~~text
NEXT_ONE_GATE=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_EXACT_ARTIFACT_BINDING_AND_LIVE_PREEXECUTION_PREPARATION_20261015_01

CROSS_GATE_AUTO_EXECUTE=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~
