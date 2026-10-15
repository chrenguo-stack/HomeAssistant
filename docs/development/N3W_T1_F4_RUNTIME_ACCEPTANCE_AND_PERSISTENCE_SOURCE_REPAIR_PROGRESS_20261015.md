# N3-W T1 F4 Runtime Acceptance and Persistence Source Repair Progress — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_SOURCE_REPAIR_20261015_01
STATUS=IMPLEMENTED_R1_PENDING_CI_AND_INDEPENDENT_REVIEW

STACK_BASE=cd69684f757a6a2fe67ab1a0cde9350717f2df3d
TRANSITION_PR=548
PREPARATION_PR=549

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## Implemented source

The existing F4 host remains the single transition owner and now adds:

~~~text
accept-runtime
enable-persistence
certificate-audit
enable-certificate-timer
~~~

The implementation extends the durable route from RUNTIME_STARTED to PRE_REBOOT_READY without adding reboot
authority.

### Runtime acceptance

The source now checks, before writing RUNTIME_ACCEPTED:

- exact running service set: Broker, Manager and Home Assistant only;
- each running container bound to the deployed fresh-release image/rootfs/config contract;
- exact Broker two-network attachment and exact 1883/8883 host publication;
- installed ingress-guard rules through the installed guard's own validation functions;
- live TLS/8883 CA + hostname + bound server-certificate verification;
- Manager host-network, 999:999, read-only-rootfs, environment and mount contract;
- Manager simplified health endpoint;
- direct established Manager MQTT socket evidence;
- fresh Manager database/replay/relay state remains empty;
- Home Assistant private MQTT config-entry audit: exactly one enabled entry, exact metadata/password match in memory,
  one-way entry-ID fingerprint only, and zero MQTT entities before board pairing;
- direct established Home Assistant MQTT socket evidence;
- exact DynSec/service-credential inventory through the exact Manager image;
- wrong-client-ID rejection for manager/provisioning/homeassistant, anonymous rejection, and a bounded positive
  provisioning credential probe;
- no raw credential value is included in the public-safe acceptance document.

The acceptance report is stored root:root 0600 under the F4 transaction root. Only then may the transaction advance
to RUNTIME_ACCEPTED.

### Persistence

From RUNTIME_ACCEPTED the source enables only:

~~~text
n3wfc4-broker-activation.service
n3wfc4-services-activation.service
~~~

It does not use the historical combined activation helper and does not enable the certificate timer at this step.

The transaction advances to PERSISTENCE_ENABLED only after both runtime units are proven enabled and the current
running service set is unchanged.

### First certificate audit

The fresh route invokes the generic certificate lifecycle engine in audit mode, with per-device paths already
bound by F4.

The audit requires all three certificate domains to report HEALTHY and proves:

~~~text
renewal_attempted=false
rollback_attempted=false
server cert unchanged
server key unchanged
Broker CA cert unchanged
Broker CA private key unchanged
System CA unchanged
Broker container identity/StartedAt unchanged
live TLS still verified
~~~

The audit is classified as a bounded status-file mutation.

### Certificate timer

Only after the first audit is durably bound does the source enable the certificate timer.

The source requires:

~~~text
timer enabled
timer not active before reboot
certificate service not started by this gate
production runtime still active
~~~

The transaction remains PERSISTENCE_ENABLED and records pre_reboot_ready=true.

### Fail-closed downstream rollback

Runtime acceptance, persistence, certificate audit and certificate timer failures use a common downstream
fail-closed path:

~~~text
disable certificate timer
disable Broker/Services persistence
stop Services
stop Broker
prove no production runtime remains
record rollback proven/unproven
STOP
~~~

FACTORY_ACCEPTED and the consumed F4 transaction are preserved.

## Exact F4 control package

Added:

~~~text
tools/n3w_t1_f4_package_builder.py
tests/tools/test_n3w_t1_f4_package_builder.py
.github/workflows/n3w-t1-f4-exact-control-package.yml
~~~

The package builder takes the exact F4 INSTALL_MAP, copies only that file set, writes
gh.n3w-t1-f4-activation-package/1, and binds every file by size + SHA256 plus exact source head.

The artifact workflow builds and re-validates the package with the same F4 consumer before sealing a transport tar.

## Current classification

~~~text
RUNTIME_ACCEPTANCE_SOURCE=IMPLEMENTED_R1_PENDING_REVIEW
RUNTIME_ACCEPTED_TRANSITION=IMPLEMENTED_R1_PENDING_REVIEW
BROKER_SERVICES_PERSISTENCE=IMPLEMENTED_R1_PENDING_REVIEW
FRESH_CERT_FIRST_AUDIT=IMPLEMENTED_R1_PENDING_REVIEW
CERT_TIMER_ENABLEMENT=IMPLEMENTED_R1_PENDING_REVIEW
DOWNSTREAM_FAIL_CLOSED_ROLLBACK=IMPLEMENTED_R1_PENDING_REVIEW
EXACT_F4_PACKAGE_BUILDER=IMPLEMENTED_R1_PENDING_CI

REBOOT_ACCEPTANCE=NOT_ENTERED
LIVE_F4_AUTHORIZATION=NOT_GRANTED
T1_ACCESS=false
BOARD_ACCESS=false

NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_SOURCE_REPAIR_INDEPENDENT_REVIEW_20261015_01
~~~
