# N3-W T1 F4 RUNTIME_STARTED R2 and Continuation Authority Source Repair Closure — 2026-10-15

~~~text
TASK=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_R2_20261015_01
RESULT=CLOSED_PASS

ACTIVATION_AUTHORIZATION_CLAIMED=true
ACTIVATION_AUTHORIZATION_CONSUMED=true
ACTIVATION_AUTHORIZATION_REPLAY_ALLOWED=false
ACTIVATION_RETRY_ELIGIBLE=false

TRANSACTION_STAGE=RUNTIME_STARTED
RUNTIME_STARTED=true
RUNTIME_ACCEPTANCE_REQUIRED=true

RUNNING_SERVICES=[broker,homeassistant,manager]
PRODUCTION_SERVICE_START=true
PERSISTENCE_ENABLED=false

INGRESS_GUARD_ACTIVE=active
BROKER_ACTIVE=active
SERVICES_ACTIVE=active
BROKER_ENABLED=disabled
SERVICES_ENABLED=disabled
CERTIFICATE_TIMER_ACTIVE=inactive
CERTIFICATE_TIMER_ENABLED=disabled

FAILED_R1_ACTIVATION_AUTHORIZATION_PRESERVED_IN_HISTORY=true

T1_PACKAGE_SOURCE_HEAD=8f870d027eea674a4443097ab0d5761542b28a73
T1_PACKAGE_MANIFEST_SHA256=c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868

BOARD_ACCESS=false
REBOOT=false
~~~

## R2 live activation closure

The R2 activation reached `RUNTIME_STARTED` with Broker, Manager and Home Assistant simultaneously running.
The runtime-start race repair therefore closed the first activation failure without weakening the fail-closed
service-set contract.

The R2 activation authorization is consumed/no-replay.

## Continuation authorization blocker found before runtime acceptance

Pre-runtime-acceptance source review found that the existing downstream commands still compared their supplied
authorization ID to the original F4 PREPARE `transaction.authorization_id`.

Affected commands:

~~~text
accept-runtime
enable-persistence
certificate-audit
enable-certificate-timer
~~~

That would reuse an already-consumed PREPARE authority for four new mutation boundaries.

No downstream mutation was executed.

## Source repair

The source repair requires a fresh, distinct one-shot authorization for each continuation gate:

~~~text
runtime_acceptance_authorization_id
persistence_authorization_id
certificate_audit_authorization_id
certificate_timer_authorization_id
~~~

Each authorization:

- must be syntactically valid;
- must differ from every prior F4 authorization recorded in the transaction or activation history;
- is durably claimed/consumed before the corresponding mutation or acceptance procedure;
- is marked no-replay.

The repaired source also adds a bounded live control update:

~~~text
repair-runtime-continuation-authority
~~~

It is locked to the exact currently installed RUNTIME_STARTED package:

~~~text
FROM_SOURCE_HEAD=8f870d027eea674a4443097ab0d5761542b28a73
FROM_PACKAGE_MANIFEST_SHA256=c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868
FROM_LAUNCHER_SHA256=56445c031e20a7b4870b65dd8d0ee96b019314deb634123904f418630b268907
TRANSACTION_STAGE=RUNTIME_STARTED
RUNNING_SERVICES_EXACT=[broker,manager,homeassistant]
PRODUCTION_SERVICE_START=true
PERSISTENCE_ENABLED=false
~~~

The repair:

- requires its own one-shot control-repair authorization;
- proves all non-launcher package files are unchanged;
- snapshots the three running containers;
- atomically replaces only /usr/local/sbin/n3w-t1-f4-activation;
- proves the same containers remain running with unchanged identities/timestamps;
- rebinds package provenance;
- leaves the transaction at `RUNTIME_STARTED`;
- does not restart or stop product services.

Any repair failure after claim uses the existing downstream fail-closed rollback.

## Exact repaired source

~~~text
REPAIRED_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
REPAIRED_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING

REPLACEMENT_ARTIFACT_ID=11982052678
REPLACEMENT_ARTIFACT_ZIP_SHA256=beb128f237d2e07f29a5f9a32d35a535de1bf8b2a099a5a3c55fbfff7d34071b
REPLACEMENT_CONTROL_TAR_BYTES=215040
REPLACEMENT_CONTROL_TAR_SHA256=9d24125d136ed5a2c5e8f98687a2718a8caa50c565a8fa0d389e4ceabd09c074
REPLACEMENT_PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
REPLACEMENT_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
REPLACEMENT_LAUNCHER_FIRST_LINE=#!/usr/bin/python3
~~~

## Next boundary

~~~text
NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_CONTINUATION_AUTHORITY_CONTROL_REPAIR_LIVE_20261015_01
LIVE_CONTROL_REPAIR_AUTHORIZATION=NOT_GRANTED
AUTO_EXECUTE_NEXT_GATE=false
~~~

That gate may update only the F4 launcher/package provenance while keeping the current RUNTIME_STARTED containers
running.

After that gate passes, runtime acceptance requires another new explicit authorization:

~~~text
FOLLOWING_GATE=N3W_T1_F4_RUNTIME_ACCEPTANCE_LIVE_20261015_01
~~~

Runtime acceptance must not enable persistence or certificate lifecycle timers.
