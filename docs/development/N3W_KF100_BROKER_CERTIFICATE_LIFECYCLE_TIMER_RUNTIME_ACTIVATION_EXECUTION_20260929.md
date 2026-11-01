# N3-W KF-100 Broker Certificate Lifecycle Timer Runtime Activation Execution — 2026-09-29

Status: `PREEXECUTION_READY`  
Base main: `a363962a118e823f97022a6c398383e9e43fc830`  
Predecessor PR: `#514` merged  
Execution branch: `exec/n3w-kf100-broker-certificate-lifecycle-timer-runtime-activation-execution-20260929`

## Exact merged authority

```text
TIMER_RUNTIME_ACTIVATION_EXECUTOR=
tools/n3w_broker_certificate_lifecycle_timer_activate.py
GIT_BLOB_SHA1=61e54cd3d27a615b56db913ef7b4ac0916c6a9ab

LIFECYCLE_TOOL_BLOB=
65187b27a2ddd8f57221500a7019486e02bca101

LIFECYCLE_TIMER_BLOB=
65b0365c5ea5f5d3c896a133adc0d689bb2deced

LIFECYCLE_SERVICE_BLOB=
fa13967ef0ffb0a271fcb7122febd83b83079deb
```

PR #514 exact head `913978cf7d99ca70ab1b2d17cd339b5d7b55f060` completed all 12 PR workflows successfully before merge.

Post-merge main:
`a363962a118e823f97022a6c398383e9e43fc830`

Post-merge push CI at preparation time:

```text
Public repository safety CI run 36535555874 = PASS
N3W Broker ingress guard CI run 36535555955 = PASS
```

Post-merge focused CI is PASS. Live execution is now authorized by the current gate.

## Live mutation boundary

The only normal-path T1 mutation is:

```text
systemctl start n3wfc4-broker-certificate-lifecycle.timer
```

The exact executor is streamed over SSH and is not persistently installed on T1.

## Persistent timer semantics

The reviewed timer is:

```text
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true
Unit=n3wfc4-broker-certificate-lifecycle.service
```

A persistent catch-up may occur after activation if systemd determines that a calendar firing was missed while the timer was inactive.

Therefore the gate accepts either:

```text
A. timer becomes active/scheduled and lifecycle status remains unchanged

B. a timer-triggered catch-up occurs, but the resulting status remains:
   server_state=HEALTHY
   ca_state=HEALTHY
   system_ca_state=HEALTHY
   renewal_attempted=false
   rollback_attempted=false
   and all Broker/TLS/certificate/key/CA continuity checks pass
```

## Required prestate

```text
timer enabled=enabled
timer active!=active
lifecycle service active!=active

durable status HEALTHY/HEALTHY/HEALTHY
renewal_attempted=false
rollback_attempted=false

Broker/TLS/cert/key/CA identities match current authority
```

## Expected PASS

```text
result=PASS
timer_runtime_activation=true
timer_enabled=enabled
timer_active=active
lifecycle_service_active=inactive
next_elapse_realtime=<scheduled value>

persistent_catchup_observed=<true|false>
status_changed_during_activation=<true|false>
status_health_valid=true
renewal_attempted=false
rollback_attempted=false

broker_restart=false
certificate_mutation=false

broker_container_continuity=true
broker_started_at_continuity=true
server_certificate_unchanged=true
server_private_key_unchanged=true
ca_certificate_unchanged=true
live_tls_verified=true
```

## Failure handling

If timer start or any post-activation invariant fails, the executor may run:

```text
systemctl stop n3wfc4-broker-certificate-lifecycle.timer
systemctl disable n3wfc4-broker-certificate-lifecycle.timer
```

Rollback is PASS only when:

```text
timer inactive
timer disabled
lifecycle service not active/activating
```

If that cannot be proven:

```text
activation_rollback=UNPROVEN
```

and further mutation stops.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_RUNTIME_ACTIVATION_EXECUTION_20260929_01
```
