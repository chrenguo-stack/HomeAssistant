# N3-W T1 F4 Factory Acceptance and Activation Source Repair — Independent Review — 2026-10-15

~~~text
TASK=N3W_T1_F4_FACTORY_ACCEPTANCE_AND_ACTIVATION_SOURCE_REPAIR_INDEPENDENT_REVIEW_20261015_01
RESULT=CLOSED_PASS_FOR_TRANSITION_CONTROL_SCOPE

BASE_MAIN=b12c69be5c1d1d61887e9be4a776f575141d44c6
REVIEW_HEAD=be14b74e6c74cc8ac036e41cc99b49439a2fc20c
MAIN_DRIFT=false
PR=548
PR_MERGEABLE=true
PR_DRAFT=true

EXACT_HEAD_CI=13_SUCCESS_0_FAILURE_0_PENDING

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Review conclusion

The F3 → F4 transition-control scope is source-complete and independently reviewable at
be14b74e6c74cc8ac036e41cc99b49439a2fc20c.

This does not mean the whole live F4 stage is ready. The reviewed repair safely owns:

~~~text
DEVICE_READY
→ one-shot F4 claim
→ current stopped-state audit
→ FACTORY_ACCEPTED
→ exact activation-package install while stopped/disabled
→ phase-locked Broker start
→ authenticated Broker readiness
→ phase-locked Manager/Home Assistant start
→ RUNTIME_STARTED
→ STOP
~~~

Full runtime acceptance, persistence enablement, certificate timer enablement and reboot acceptance remain
downstream source work.

## 2. Independent findings

### A1 — exact F4 package/source binding

Initial review found a blocker: --package-root could name source material that was not itself cryptographically
bound to the approved F4 source head.

Repair now requires:

~~~text
package_source_head=<40-hex exact source>
package_manifest_sha256=<64-hex exact manifest>
manifest schema=gh.n3w-t1-f4-activation-package/1
manifest exact file set=INSTALL_MAP
each file exact size + SHA256
secret_values_included=false
production_service_start=false
board_access=false
~~~

The package is validated before the F4 authorization claim. Copy-time size/SHA256 checks protect against package
mutation between prevalidation and installation.

The one-shot transaction persists both package source head and package manifest SHA256.

A1=CLOSED.

### A2 — installed control-material drift

Initial implementation did not persist an exact post-install binding for the installed F4 control material.

Repair now stores exact SHA256/size/mode/uid/gid bindings for:

~~~text
F4 host helper
Broker readiness helper
certificate lifecycle helper
Broker activation unit
Services activation unit
certificate lifecycle service/timer
NetworkManager ingress-guard dispatcher
runtime Compose file
Broker activation env
certificate lifecycle env
~~~

Every Broker/Services/certificate eligibility check verifies this installed material before allowing systemd to
enter the protected phase.

A2=CLOSED.

### A3 — post-transition service restart

Review found that restricting Broker/Services units only to the transient STARTING stage would make
Restart=always and later reboot recovery fail after the transaction advanced.

Repair allows:

~~~text
Broker:
  BROKER_STARTING
  BROKER_READY
  SERVICES_STARTING
  RUNTIME_STARTED
  RUNTIME_ACCEPTED
  PERSISTENCE_ENABLED

Services:
  SERVICES_STARTING
  RUNTIME_STARTED
  RUNTIME_ACCEPTED
  PERSISTENCE_ENABLED
~~~

while still denying direct Broker/Services start from PREPARED.

Certificate lifecycle remains denied until RUNTIME_ACCEPTED.

A3=CLOSED.

### A4 — runtime rollback proof

Initial failure handling could overstate rollback success by relying on systemd unit state alone.

Repair now checks both unit state and the actual Docker Compose running-service set. An unprovable Compose probe
produces:

~~~text
production_service_start=null
rollback_proven=false
STOPPED_RUNTIME_ROLLBACK_UNPROVEN
~~~

rather than a false stopped claim.

A4=CLOSED.

### A5 — one-shot lifecycle and factory acceptance

The repair preserves:

~~~text
claim before first F4 mutation
authorization_consumed=true
replay_allowed=false
exclusive non-blocking F4 execution lock
FACTORY_ACCEPTED new-record-only
FACTORY_ACCEPTED exact release/host/system binding
~~~

An existing malformed or mismatched factory record fails closed.

A5=CLOSED.

### A6 — direct systemd bypass

The fresh-route Broker, Services and certificate-lifecycle unit variants execute the F4 eligibility guard before
their runtime action. Services cannot transitively pull Broker from PREPARED, because Broker is itself denied
until the transaction has been advanced by the top-level F4 owner.

A6=CLOSED.

### A7 — fresh per-device certificate identity

The fresh F4 route uses the per-device Broker CA/server identity created by explicit provisioning and does not
reuse historical fixed certificate fingerprints. Broker CA/server key-pair matches and hostname/chain validation
are checked before the F4 control package is installed.

A7=CLOSED.

### A8 — scope and predecessor protection

~~~text
provisioning_start_replay=false
production_persistence_enablement=false
certificate_timer_enablement=false
runtime_accepted_transition=false
reboot=false
board_access=false
~~~

The already-consumed F3/provisioning authorization is not reused.

A8=CLOSED.

## 3. CI evidence

Exact-head CI at be14b74e6c74cc8ac036e41cc99b49439a2fc20c:

~~~text
N3W T1 F4 activation source CI=SUCCESS
N3W Broker ingress guard CI=SUCCESS
Public repository safety CI=SUCCESS
greenhouse-manager CI=SUCCESS
M2 private Mosquitto CI=SUCCESS
M2 Dynamic Security CI=SUCCESS
M2 manager runtime secret ownership CI=SUCCESS
M2 node auth isolated lab CI=SUCCESS
M2 node auth board lab CI=SUCCESS
M2 node auth native board lab CI=SUCCESS
H3 N2 Stage2B3 Pairing Runtime CI=SUCCESS
C-07 node retirement CI=SUCCESS
M0 vertical slice CI=SUCCESS
~~~

## 4. Downstream blocker

The reviewed transition control must not be used on the real T1 yet.

The following source authority is still missing:

~~~text
RUNTIME_STARTED
→ Broker TLS/ACL negative-client acceptance
→ Manager runtime/blank-business-state acceptance
→ Home Assistant MQTT bootstrap continuity acceptance
→ RUNTIME_ACCEPTED durable transition
→ persistence enablement
→ first certificate lifecycle read-only audit
→ certificate timer enablement
→ STOP before reboot
~~~

Therefore:

~~~text
F4_TRANSITION_CONTROL_SOURCE=CLOSED_PASS
FULL_F4_LIVE_READY=false
LIVE_F4_AUTHORIZATION=NOT_GRANTED
~~~

## 5. Next one gate

~~~text
NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_SOURCE_PREPARATION_20261015_01

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_LIVE_F4=false
~~~
