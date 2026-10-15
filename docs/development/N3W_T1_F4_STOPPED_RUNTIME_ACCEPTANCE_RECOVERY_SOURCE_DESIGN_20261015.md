# N3-W T1 F4 Stopped Runtime Acceptance Recovery Source Design — 2026-10-15

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_SOURCE_DESIGN_20261015_01
STATUS=DESIGN_COMPLETE_PENDING_SOURCE_REPAIR

REPOSITORY_MAIN=b12c69be5c1d1d61887e9be4a776f575141d44c6

LIVE_EVIDENCE_PR=568
LIVE_EVIDENCE_HEAD=9af22d12b6fa229722cb4d311a0ad0d00e5907c6

SOCKET_PROBE_SOURCE_REPAIR_PR=569
SOCKET_PROBE_SOURCE_REPAIR_HEAD=e7f31b4703526442cf14429c4e5ab60924b24eb4
SOCKET_PROBE_SOURCE_REPAIR_BASE=ffcbb1a890e42ac776c6d90000bf3f25195da01d

CURRENT_T1_STAGE=STOPPED_RUNTIME_ACCEPTANCE
CURRENT_PRODUCTION_SERVICE_START=false
CURRENT_PERSISTENCE_ENABLED=false
CURRENT_CERTIFICATE_TIMER_ENABLED=false
CURRENT_PRODUCT_LISTENER_PORTS=[]
CURRENT_ROLLBACK_PROVEN=true

FAILED_RUNTIME_ACCEPTANCE_AUTHORIZATION=CONSUMED_NO_REPLAY
FAILED_RUNTIME_ACCEPTANCE_REPORT_PRESENT=false

LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~

## 1. Design goal

Provide one bounded recovery route from the real T1's current
`STOPPED_RUNTIME_ACCEPTANCE` state after KF-121.

The route must:

1. preserve the failed runtime-acceptance authorization as permanently consumed;
2. preserve the failure/rollback evidence;
3. install only the repaired F4 control launcher from a new exact package;
4. keep Broker, Manager and Home Assistant stopped during the repair;
5. return the transaction to a controlled `PREPARED` state;
6. permit one new, distinct activation authorization to start the runtime;
7. permit one new, distinct runtime-acceptance authorization only after that activation reaches `RUNTIME_STARTED`;
8. keep persistence, certificate lifecycle, reboot and board access outside this recovery route.

This is not a reset, transaction erase, or re-use of the failed authorization.

## 2. Frozen live prestate

The recovery source MUST reject any state that does not match the bounded incident prestate.

Required durable transaction facts:

~~~text
stage=STOPPED_RUNTIME_ACCEPTANCE
error_code=manager_mqtt_socket_count_invalid
rollback_proven=true
rollback_error_count=0
production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false

runtime_acceptance_authorization_claimed=true
runtime_acceptance_authorization_consumed=true
runtime_acceptance_authorization_replay_allowed=false
runtime_acceptance_passed is not true
~~~

Required current runtime facts:

~~~text
running_services=[]
product_listener_ports=[]
Broker enabled != enabled
Services enabled != enabled
Certificate timer enabled != enabled
Certificate timer active not in active/activating/reloading
Certificate lifecycle service active not in active/activating/reloading
RUNTIME_ACCEPTANCE.json absent
~~~

Required failed-source binding:

~~~text
FROM_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
FROM_PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
FROM_INSTALLED_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
~~~

The source-repair implementation must bind these as exact recovery-from constants.
The successor target source/manifest are intentionally not frozen in this design document; they are bound by the
later exact SOURCE_REPAIR head and its exact-package artifact.

## 3. Why the existing installed launcher cannot be the recovery entrypoint

The currently installed launcher is the failed-source launcher. It does not contain the new
`STOPPED_RUNTIME_ACCEPTANCE` recovery command.

Therefore the live recovery MUST NOT depend on first mutating the installed launcher with an ad-hoc copy.

The recovery entrypoint is the successor launcher's file inside the extracted exact F4 control package:

~~~text
<exact-package-root>/tools/n3w_t1_f4_activation_host.py
~~~

The later live preexecution must independently bind:

- workflow run / exact SOURCE_HEAD;
- transport tar SHA256;
- package manifest SHA256;
- successor launcher SHA256.

The successor launcher then validates the complete package through the existing `_validate_package()` contract before
performing any mutation.

The recovery command must additionally prove that the executing file itself is exactly the launcher record inside the
validated package. A copied or unrelated Python file must not be accepted as the recovery authority.

## 4. New source command

Add one command:

~~~text
repair-stopped-runtime-acceptance
~~~

Required arguments:

~~~text
--confirm
--authorization-id
--package-root
--package-manifest-sha256
--package-source-head
~~~

Confirmation contract:

~~~text
RECOVER F4 STOPPED RUNTIME ACCEPTANCE: YES
~~~

Suggested internal function:

~~~text
_repair_stopped_runtime_acceptance(...)
~~~

This command is control-material repair only. It MUST NOT start Broker, Manager, Home Assistant, the certificate
service, or the certificate timer.

## 5. New authorization namespace

Add one new one-shot transaction authorization:

~~~text
runtime_acceptance_recovery_authorization_id
runtime_acceptance_recovery_authorization_claimed
runtime_acceptance_recovery_authorization_consumed
runtime_acceptance_recovery_authorization_replay_allowed
~~~

Rules:

- authorization ID must satisfy the existing F4 ID syntax;
- it must be distinct from every prior F4 authorization;
- it is durably claimed and consumed before launcher replacement;
- replay is always false;
- failure after claim does not make the same authorization reusable.

Add the new authorization ID to `_all_prior_authorization_ids()`.

## 6. Runtime-acceptance authorization history and successor retry

The failed runtime-acceptance authorization must not be overwritten without durable history.

Add:

~~~text
runtime_acceptance_authorization_history=[]
runtime_acceptance_retry_eligible=false
~~~

`_all_prior_authorization_ids()` must validate and include every string in
`runtime_acceptance_authorization_history`.

### Modified accept-runtime rule

Current source rejects any new runtime acceptance when
`runtime_acceptance_authorization_claimed=true`.

The successor source must mirror the existing bounded activation-retry pattern:

~~~text
prior_claimed = runtime_acceptance_authorization_claimed is true
retry_eligible = runtime_acceptance_retry_eligible is true

if prior_claimed and not retry_eligible:
    reject

new authorization must satisfy the normal F4 ID syntax
new authorization must be distinct from every prior F4 authorization

if prior_claimed:
    append previous runtime_acceptance_authorization_id to
    runtime_acceptance_authorization_history

claim new runtime acceptance authorization
set runtime_acceptance_retry_eligible=false
continue normal runtime acceptance
~~~

Important implementation constraint: the current
`_validate_successor_authorization(..., claimed_field="runtime_acceptance_authorization_claimed")`
cannot be called unchanged for this successor path, because that helper rejects every already-claimed field before it
can consider retry eligibility.

SOURCE_REPAIR must therefore either:

1. extend the helper with an explicit retry-eligibility contract; or
2. keep the helper unchanged for other stages and implement the runtime-acceptance retry check locally using the same
   syntax/all-prior-ID rules.

Do not weaken persistence or certificate authorization checks as a side effect.

The old failed authorization therefore remains permanently present in history and remains rejected forever.

## 7. Re-use the existing activation successor mechanism

Do not invent a second runtime-start implementation.

After successful control repair, the transaction will deliberately return to:

~~~text
stage=PREPARED
activation_retry_eligible=true
runtime_acceptance_retry_eligible=true
production_service_start=false
persistence_enabled=false
~~~

The existing `activate` implementation already has the required bounded-successor rule:

- if an earlier activation was claimed, `activation_retry_eligible=true` is required;
- the new activation authorization must be distinct;
- the previous activation authorization is preserved in `activation_authorization_history`;
- the new activation authorization is claimed/consumed/no-replay before services start;
- successful start advances to `RUNTIME_STARTED`.

This existing mechanism should be reused instead of adding a second service-start path.

## 8. Recovery transaction sequence

### 8.1 Recovery claim

After all prestate, package, installed-material and authorization checks pass:

~~~text
stage=STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_CLAIMED

runtime_acceptance_recovery_authorization_id=<new>
runtime_acceptance_recovery_authorization_claimed=true
runtime_acceptance_recovery_authorization_consumed=true
runtime_acceptance_recovery_authorization_replay_allowed=false

runtime_acceptance_recovery_from_source_head=<failed exact source>
runtime_acceptance_recovery_from_manifest_sha256=<failed exact manifest>
runtime_acceptance_recovery_target_source_head=<successor exact source>
runtime_acceptance_recovery_target_manifest_sha256=<successor exact manifest>

production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false
~~~

The stage intentionally remains STOPPED-prefixed so the durable record cannot imply a running product runtime.

### 8.2 Allowed package delta

Recovery may replace only:

~~~text
/usr/local/sbin/n3w-t1-f4-activation
~~~

The successor package's records for every other `INSTALL_MAP` path must match the existing installed bindings by
both SHA256 and size.

This prevents a stopped-runtime recovery from silently changing systemd units, guard scripts, certificate tools or
broker readiness tooling.

### 8.3 Atomic launcher replacement

Use the existing bound atomic replacement primitive:

~~~text
_atomic_replace_bound_file(...)
~~~

It must require:

- current installed launcher binding exactly equals the frozen failed launcher binding;
- successor launcher binding exactly equals the validated package record;
- successor launcher begins with the expected Python shebang;
- target remains root:root and mode 0755.

### 8.4 Post-repair stopped-state proof

After replacement and before declaring success, prove again:

~~~text
production_service_start=false
running_services=[]
product_listener_ports=[]
Broker/Services remain disabled
Certificate timer remains disabled and inactive
Certificate lifecycle service remains inactive
RUNTIME_ACCEPTANCE.json remains absent
~~~

No container start is permitted as part of this function.

### 8.5 Preserve the failed acceptance evidence before leaving STOPPED

Before changing the durable stage to PREPARED, copy the incident facts into explicit durable fields:

~~~text
runtime_acceptance_last_failure_stage=STOPPED_RUNTIME_ACCEPTANCE
runtime_acceptance_last_failure_error_code=manager_mqtt_socket_count_invalid
runtime_acceptance_last_failure_authorization_id=<consumed failed auth>
runtime_acceptance_last_failure_source_head=ffcbb1a890e42ac776c6d90000bf3f25195da01d
runtime_acceptance_last_failure_manifest_sha256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
runtime_acceptance_last_failure_rollback_proven=true
runtime_acceptance_last_failure_rollback_error_count=0
~~~

This prevents a later PREPARED/RUNTIME_STARTED record from carrying ambiguous stale top-level STOP fields while still
preserving the exact failed incident.

### 8.6 Recovery success state

On success write:

~~~text
stage=PREPARED

installed_files=<updated launcher binding only>
package_source_head=<successor source head>
package_manifest_sha256=<successor manifest sha>

runtime_acceptance_recovery_passed=true
activation_retry_eligible=true
runtime_acceptance_retry_eligible=true

broker_ready=false
runtime_started=false
runtime_acceptance_required=true
runtime_acceptance_passed=false
runtime_acceptance_report_sha256=null
homeassistant_mqtt_entry_id_sha256=null

error_code=null
rollback_proven=null
rollback_error_count=null
product_listener_ports=[]

production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false
~~~

Do not delete:

- original activation authorization history;
- failed runtime-acceptance authorization/history;
- the explicit `runtime_acceptance_last_failure_*` evidence;
- recovery authorization evidence.

## 9. Recovery failure behavior

Any failure after the recovery authorization has been claimed must remain stopped.

Preferred failure stage:

~~~text
STOPPED_RUNTIME_ACCEPTANCE_RECOVERY
~~~

Required fields:

~~~text
runtime_acceptance_recovery_passed=false
runtime_acceptance_recovery_error_code=<bounded error>
production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false
~~~

The source must attempt to prove:

- no product runtime;
- no product listeners;
- Broker/Services disabled;
- certificate timer disabled/inactive;
- certificate lifecycle inactive.

If that proof fails, use:

~~~text
STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_ROLLBACK_UNPROVEN
~~~

The consumed recovery authorization is still not replayable.

## 10. Successor activation gate

After recovery success, a later live gate supplies a NEW distinct activation authorization.

Expected transition:

~~~text
PREPARED
  -> ACTIVATION_CLAIMED
  -> BROKER_STARTING
  -> BROKER_READY
  -> SERVICES_STARTING
  -> RUNTIME_STARTED
~~~

At `RUNTIME_STARTED`:

~~~text
production_service_start=true
persistence_enabled=false
runtime_acceptance_required=true
runtime_acceptance_retry_eligible=true
~~~

STOP there.

Do not combine activation and runtime acceptance under one authorization.

## 11. Successor runtime-acceptance gate

A still later live gate supplies a NEW distinct runtime-acceptance authorization.

Requirements:

- stage exactly `RUNTIME_STARTED`;
- prior failed runtime-acceptance authorization preserved;
- `runtime_acceptance_retry_eligible=true`;
- new authorization distinct from all current IDs and both activation/acceptance histories;
- source/package/installed-material binding is the repaired exact package.

On claim:

~~~text
runtime_acceptance_authorization_history += [old failed acceptance authorization]
runtime_acceptance_authorization_id=<new>
runtime_acceptance_authorization_claimed=true
runtime_acceptance_authorization_consumed=true
runtime_acceptance_authorization_replay_allowed=false
runtime_acceptance_retry_eligible=false
~~~

Then execute the normal repaired acceptance logic.

PASS stops at:

~~~text
RUNTIME_ACCEPTED
~~~

Persistence remains outside this route.

## 12. No combined mega-authorization

The recovery must use three different live authorizations:

~~~text
A. stopped-runtime-acceptance control recovery authorization
B. successor activation authorization
C. successor runtime-acceptance authorization
~~~

They MUST be distinct from one another and from every prior F4 authorization.

This preserves the project's one-operation / one-authorization boundary and gives a STOP point after each state
transition.

## 13. Required source changes

Expected implementation scope:

~~~text
tools/n3w_t1_f4_activation_host.py
tests/tools/test_n3w_t1_f4_activation_host.py
docs/development/N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_SOURCE_REPAIR_PROGRESS_20261015.md
~~~

The exact-package builder and workflow should not require semantic changes unless implementation review finds that the
successor-package execution-entrypoint binding cannot be proven with the existing package manifest.

Out of scope:

~~~text
infra/n3w-t1/production/docker-compose.yml
Broker configuration
Manager application code
Home Assistant code
firmware
radio state machine
board/NVS
certificate policy
persistence policy
~~~

## 14. Mandatory unit/source test matrix

The SOURCE_REPAIR gate must cover at least:

### Recovery prestate

- reject any stage other than `STOPPED_RUNTIME_ACCEPTANCE`;
- reject wrong failure error;
- reject rollback_proven != true;
- reject rollback_error_count != 0;
- reject runtime active or unknown;
- reject any running product service;
- reject any product listener;
- reject Broker/Services enabled;
- reject certificate timer enabled/active;
- reject certificate service active;
- reject existing runtime acceptance report;
- reject failed source/manifest/launcher mismatch.

### Package and delta

- reject invalid package manifest/source head;
- reject recovery entrypoint not equal to validated package launcher;
- reject successor launcher without Python shebang;
- reject any non-launcher package delta;
- reject installed-material drift before mutation;
- prove launcher-only replacement.

### Authorization

- reject malformed recovery authorization;
- reject recovery authorization equal to any prior F4 authorization;
- reject recovery replay;
- include recovery authorization in all-prior set;
- include runtime-acceptance history in all-prior set.

### Recovery success

- claim/consume recovery authorization before launcher replacement;
- transition to PREPARED;
- set activation_retry_eligible=true;
- set runtime_acceptance_retry_eligible=true;
- keep runtime stopped/listeners empty;
- keep persistence and timer false;
- preserve failed acceptance authorization evidence;
- copy the failed STOP fields into explicit `runtime_acceptance_last_failure_*` evidence before clearing stale
  top-level STOP-only fields;
- update source/manifest and installed launcher binding only.

### Recovery failure

- replacement failure remains stopped;
- post-repair stopped-proof failure remains stopped;
- rollback-unproven gets the explicit unproven suffix;
- consumed recovery authorization cannot be replayed.

### Successor activation

- existing activation authorization still rejected without retry eligibility;
- recovery-created retry eligibility allows one distinct successor activation;
- prior activation ID is preserved in activation history;
- successful activation clears activation_retry_eligible and reaches RUNTIME_STARTED.

### Successor runtime acceptance

- prior claimed acceptance without retry eligibility remains rejected;
- retry eligibility allows one distinct successor acceptance;
- old acceptance ID is added to runtime-acceptance history before overwrite;
- old acceptance ID remains rejected forever;
- recovery authorization cannot be reused as acceptance authorization;
- claim clears runtime_acceptance_retry_eligible;
- socket acceptance still requires exactly one Manager 8883 socket;
- observed bad socket count remains included in the failure code.

### End-to-end source simulation

Simulate:

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

Assert at every step that:

~~~text
old failed acceptance authorization never becomes reusable
no persistence is enabled
certificate timer remains disabled
board_access=false
~~~

## 15. Exact artifact / live sequence after source repair

No live step is authorized by this design gate.

After SOURCE_REPAIR + independent source review + exact CI:

1. build and bind a new exact F4 control package from the final recovery SOURCE_HEAD;
2. fresh stopped-state read-only preflight on T1;
3. transfer/extract exact package without executing it;
4. verify transport tar, manifest and successor launcher hashes;
5. execute successor package launcher with a new recovery authorization;
6. STOP at PREPARED;
7. fresh read-only PREPARED verification;
8. execute normal `activate` with a new activation authorization;
9. STOP at RUNTIME_STARTED;
10. verify stable runtime and repaired launcher/package binding;
11. execute `accept-runtime` with a new runtime-acceptance authorization;
12. STOP at RUNTIME_ACCEPTED.

Persistence, certificate audit/timer, reboot and board work remain separate successor gates.

## 16. Design decision

~~~text
RECOVERY_RESET_TRANSACTION=false
RECOVERY_REUSE_FAILED_ACCEPTANCE_AUTH=false
RECOVERY_REUSE_EXISTING_ACTIVATE_IMPLEMENTATION=true
RECOVERY_NEW_CONTROL_AUTH_REQUIRED=true
RECOVERY_NEW_ACTIVATION_AUTH_REQUIRED=true
RECOVERY_NEW_ACCEPTANCE_AUTH_REQUIRED=true

RECOVERY_ENTRYPOINT=SUCCESSOR_EXACT_PACKAGE_LAUNCHER
RECOVERY_ALLOWED_INSTALLED_DELTA=LAUNCHER_ONLY
RECOVERY_SUCCESS_STAGE=PREPARED
LIVE_RUNTIME_START_DURING_RECOVERY=false

DESIGN_RESULT=CLOSED_PASS
~~~

## 17. Next ONE Gate

~~~text
NEXT_ONE_GATE=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_SOURCE_REPAIR_20261015_01

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~
