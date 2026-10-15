# N3-W T1 F4 Runtime Acceptance and Persistence Source Repair — Independent Review — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_SOURCE_REPAIR_INDEPENDENT_REVIEW_20261015_01
RESULT=CLOSED_PASS_FOR_PRE_REBOOT_SOURCE_SCOPE

PREPARATION_HEAD=7e4ab972469f5755893136a250d7c8e9f3538b60
REVIEWED_SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
REVIEW_EXACT_HEAD_CI=13_SUCCESS_0_FAILURE_0_PENDING

EXACT_CONTROL_PACKAGE_ARTIFACT_ID=11967018401
EXACT_CONTROL_PACKAGE_ARTIFACT_DIGEST=sha256:6308fdc64347949d463f251713c359571b40f067182cfd4d686ba4495d6d162f
EXACT_CONTROL_PACKAGE_SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Review conclusion

The repository-owned F4 control source is CLOSED_PASS for the complete pre-reboot source scope:

~~~text
DEVICE_READY
→ FACTORY_ACCEPTED
→ exact F4 package install
→ Broker start/readiness
→ Manager + Home Assistant start
→ RUNTIME_STARTED
→ runtime end-to-end acceptance
→ RUNTIME_ACCEPTED
→ Broker/Services persistence enable
→ first per-device certificate lifecycle audit
→ certificate timer enable
→ PRE_REBOOT_READY
→ STOP
~~~

This is a source closure only. It is not a real-T1 F4 acceptance and it grants no live authorization.

Reboot remains a later independent gate.

## 2. Exact stack alignment

The source branch now contains the final preparation head directly in its ancestry:

~~~text
PREPARATION_HEAD=7e4ab972469f5755893136a250d7c8e9f3538b60
SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
SOURCE_BEHIND_PREPARATION=0
~~~

The final Manager liveness decision from preparation is preserved:

~~~text
GH_N3W_PRODUCT_PAIRING_ENABLED=false
PAIRING_HTTP_HEALTH_APPLICABLE=false
MANAGER_LIVENESS=
stable container identity
+ stable StartedAt
+ one established Manager MQTT/8883 socket
+ exact TLS/runtime contract
+ fresh Manager/N3-W state audit
~~~

No stale preparation revision is authoritative.

## 3. Independent review findings and repairs

### A1 — exact runtime package/install binding

Transition control already bound the package manifest, source head and installed control material by exact
size/SHA256/mode/uid/gid. Downstream continuation reuses the same transaction authority.

A1=CLOSED.

### A2 — runtime service/image binding

Runtime acceptance requires exactly Broker, Manager and Home Assistant in the expected Compose project and binds
each running container back to the deployed fresh release image/rootfs/config authority.

The review additionally requires that no extra running container use any of the three product images.

A2=CLOSED.

### A3 — Broker publication and ingress guard

Broker runtime must have:

~~~text
1883/tcp → 127.0.0.1:1883 exactly
8883/tcp → 0.0.0.0:8883 exactly
extra unbound exposed ports tolerated
extra host publication rejected
network set exact
~~~

Ingress-guard proof now requires all three:

~~~text
systemd active=true
systemd enabled=true
installed rule validation=PASS
~~~

A3=CLOSED.

### A4 — TLS and service identity

The runtime TLS probe verifies:

~~~text
CA validation
server-name=armbian
live peer certificate == bound server certificate
~~~

Service identity review now exact-binds:

~~~text
Manager runtime username/client ID
Provisioning runtime username/client ID
Home Assistant bootstrap username/client ID/generation
~~~

to the private per-device service identity records.

All three service usernames and client IDs must remain distinct.

A4=CLOSED.

### A5 — Broker authentication negative/positive proof

Runtime acceptance proves:

~~~text
Manager live authenticated connection
Home Assistant live authenticated connection
Provisioning exact credential authentication

Manager wrong client ID rejected
Provisioning wrong client ID rejected
Home Assistant wrong client ID rejected
Anonymous connection rejected
~~~

The positive Manager/Home Assistant claims are not based on Broker log text alone. They are coupled to exact
runtime identity/secret mounts plus direct established MQTT socket evidence.

A5=CLOSED.

### A6 — Manager runtime oracle

Because product pairing remains disabled, pairing HTTP health is deliberately not used.

Manager acceptance requires:

~~~text
runtime UID:GID=999:999
read-only rootfs
host network
exact writable/read-only mounts
exact tmpfs contract
exact TLS namespace configuration
exact Manager/Provisioning identity binding

same container ID across bounded stability window
same StartedAt across bounded stability window
exactly one established MQTT/8883 socket throughout window

business row count=0
replay state=empty
relay authorization state=empty
relay key state=empty
node credential count=0
~~~

A6=CLOSED.

### A7 — Home Assistant runtime acceptance

Home Assistant must prove:

~~~text
exact image/runtime mounts
direct HTTP API readiness
exactly one MQTT config entry
exactly one enabled MQTT config entry
entry values match private bootstrap metadata/password
entry ID exposed only as SHA256 fingerprint
zero MQTT entities before board pairing
at least one live MQTT/1883 socket
~~~

The source does not depend on missing log text as a failure oracle.

A7=CLOSED.

### A8 — durable RUNTIME_ACCEPTED transition

A root-owned mode-0600 public-safe runtime acceptance report is created before transaction advancement.

Downstream steps now revalidate:

~~~text
runtime_acceptance_passed=true
report SHA256 exact
package source/manifest exact
Home Assistant entry fingerprint exact
secret_values_included=false
board_access=false
~~~

A changed or missing acceptance report fails closed.

A8=CLOSED.

### A9 — persistence enablement continuity

Only Broker and Services units are enabled.

Certificate timer remains disabled.

Review repair additionally proves that all three current product containers retain the same container IDs and
StartedAt values across the enable operation. The runtime acceptance report is rebound before and after the
operation.

A9=CLOSED.

### A10 — first certificate lifecycle audit

The first audit remains generic lifecycle audit, never auto-renew.

Before audit:

~~~text
runtime acceptance binding exact
exact three-service runtime active
certificate status root=root:root:0700 and empty
TLS material owner/mode/keypair binding valid
certificate timer not enabled
~~~

After audit:

~~~text
action=audit
result=ok
server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY
renewal_attempted=false
rollback_attempted=false

all certificate/key hashes unchanged
all three production container identities unchanged
live TLS still verified
durable status JSON == audit result
status + lock exact private authority
~~~

A10=CLOSED.

### A11 — certificate timer enablement

Timer enablement is enable-only.

It requires:

~~~text
Broker persistence enabled
Services persistence enabled
first certificate audit exact
runtime acceptance exact
certificate service inactive
timer inactive before enable
exact three-service runtime active
~~~

After enable:

~~~text
timer enabled
timer still inactive
certificate service still inactive
all three container identities unchanged
certificate/key hashes unchanged
certificate audit status hash unchanged
~~~

No certificate renewal is authorized by this gate.

A11=CLOSED.

### A12 — downstream rollback proof

Review repair closes an earlier overclaim path.

A downstream failure now attempts, in bounded order:

~~~text
stop certificate timer
disable certificate timer
stop certificate lifecycle service
disable Broker/Services persistence
stop Services
stop Broker
~~~

Rollback can be recorded as proven only when:

~~~text
production runtime stopped
Broker disabled
Services disabled
certificate timer disabled
certificate timer inactive
certificate lifecycle service inactive
all product target listeners absent
rollback command errors=0
~~~

Otherwise the transaction records ROLLBACK_UNPROVEN.

A12=CLOSED.

### A13 — exact control package

The exact-package workflow at the reviewed source head:

- built only the F4 INSTALL_MAP file set;
- wrote the package manifest with exact source head;
- rebound every file by size + SHA256 using the same F4 consumer;
- sealed a transport tar;
- uploaded one artifact.

Authority:

~~~text
ARTIFACT_ID=11967018401
ARTIFACT_NAME=n3w-t1-f4-control-package-ad65bf7d10db76f12a09e19b337f4a0c7782894a
ARTIFACT_DIGEST=sha256:6308fdc64347949d463f251713c359571b40f067182cfd4d686ba4495d6d162f
~~~

A13=CLOSED.

### A14 — scope protection

The source repair does not add:

~~~text
provisioning start replay
reboot authority
board access
ESP32 firmware changes
pairing/NVS/RF mutation
automatic live F4 execution
~~~

A14=CLOSED.

## 4. Exact-head CI

Reviewed source head:

~~~text
ad65bf7d10db76f12a09e19b337f4a0c7782894a
~~~

Completed successfully:

~~~text
N3W T1 F4 activation source CI
N3W T1 F4 exact control package
Public repository safety CI
greenhouse-manager CI
M2 private Mosquitto CI
M2 Dynamic Security CI
M2 manager runtime secret ownership CI
M2 node auth isolated lab CI
M2 node auth board lab CI
M2 node auth native board lab CI
H3 N2 Stage2B3 Pairing Runtime CI
C-07 node retirement CI
M0 vertical slice CI
~~~

~~~text
TOTAL=13
SUCCESS=13
FAILURE=0
PENDING=0
~~~

## 5. Live boundary

Source closure does not authorize use on the real T1.

Before live F4, the exact package still needs a bounded transfer/read-only preauthorization package that proves:

~~~text
real T1 still DEVICE_READY
same deployed release
same current host binding
production services still stopped
FACTORY_ACCEPTED absent before F4 claim
F4 transaction absent before F4 claim
exact control artifact downloaded/cached and inner bindings PASS
target capacity/path/ownership prerequisites PASS
no board access
~~~

The later live mutation must receive a new explicit F4 authorization. The consumed provisioning authorization
cannot be reused.

## 6. Gate closure

~~~text
F4_PRE_REBOOT_SOURCE=CLOSED_PASS
F4_TRANSITION_CONTROL_SOURCE=CLOSED_PASS
F4_RUNTIME_ACCEPTANCE_SOURCE=CLOSED_PASS
F4_PERSISTENCE_SOURCE=CLOSED_PASS
F4_CERTIFICATE_FIRST_AUDIT_SOURCE=CLOSED_PASS
F4_CERTIFICATE_TIMER_SOURCE=CLOSED_PASS
F4_DOWNSTREAM_ROLLBACK_SOURCE=CLOSED_PASS
F4_EXACT_CONTROL_PACKAGE=CLOSED_PASS

FULL_F4_LIVE_ACCEPTANCE=false
LIVE_F4_AUTHORIZATION=NOT_GRANTED
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

CURRENT_STOP_POINT=AFTER_F4_PRE_REBOOT_SOURCE_REVIEW_BEFORE_EXACT_PACKAGE_READONLY_PREAUTH_PREPARATION

NEXT_ONE_GATE=N3W_T1_F4_EXACT_CONTROL_PACKAGE_AND_READONLY_PREAUTH_PREPARATION_20261015_01
AUTO_EXECUTE_LIVE_F4=false
~~~
