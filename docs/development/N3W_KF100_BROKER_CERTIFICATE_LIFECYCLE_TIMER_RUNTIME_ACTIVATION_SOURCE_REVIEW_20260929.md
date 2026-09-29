# N3-W KF-100 Broker Certificate Lifecycle Timer Runtime Activation Source Review — 2026-09-29

Status: `SOURCE_REVIEW_PASS_PENDING_CI`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-timer-runtime-activation-preparation-20260929`  
Reviewed source/test head: `1d2f6ee2bc6c4f027583cdb8fddc7066077f083c`  
Executor Git blob SHA-1: `61e54cd3d27a615b56db913ef7b4ac0916c6a9ab`  
Base main: `2e777f6da816a5b3ba8a3562f7356d4af21c4eab`

## Review result

```text
A1_EXACT_INSTALLED_SOURCE_BINDING=PASS
A2_ENABLED_INACTIVE_PRESTATE=PASS
A3_PERSISTENT_CATCHUP_SEMANTICS=PASS
A4_TIMER_RUNTIME_SCHEDULE_ORACLE=PASS
A5_HEALTHY_CATCHUP_BOUNDARY=PASS
A6_BROKER_TLS_CONTINUITY=PASS
A7_SAFE_ROLLBACK=PASS
A8_NO_DIRECT_AUTO_RENEW_INVOCATION=PASS
A9_NO_BROKER_RESTART=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REVIEW=PASS_PENDING_CI
LIVE_TIMER_RUNTIME_ACTIVATION=false
```

## A1. Exact installed source binding

The executor requires exact installed lifecycle tool/service/timer blobs and the current durable healthy lifecycle status before starting the timer.

## A2. Enabled/inactive prestate

Activation is allowed only from:

```text
timer enabled=enabled
timer inactive
lifecycle service inactive
```

This directly follows the previously accepted enable-without-start gate.

## A3. Persistent catch-up semantics

The reviewed timer uses `OnCalendar=daily`, `Persistent=true`, and `RandomizedDelaySec=1h`.

A persistent calendar timer may catch up a missed firing when it becomes active. The catch-up can also be delayed by the configured randomized delay.

Therefore the executor correctly avoids treating every lifecycle status change after timer start as an automatic failure.

## A4. Runtime scheduling oracle

The timer must report:

```text
ActiveState=active
UnitFileState=enabled
NextElapseUSecRealtime=<non-empty scheduled value>
```

after activation and again after the bounded service-settle check.

This proves current-boot timer runtime scheduling rather than only unit-file enablement.

## A5. Healthy catch-up boundary

Two PASS outcomes are accepted:

1. status unchanged during activation;
2. status changed and `LastTriggerUSec` proves timer activity, while the new lifecycle status remains HEALTHY/HEALTHY/HEALTHY and reports no renewal/rollback attempt.

A changed status with no timer-trigger authority is rejected.

## A6. Broker/TLS continuity

The executor requires unchanged:

- Broker container identity;
- Broker StartedAt;
- server certificate hash;
- server private-key hash;
- FC4 CA certificate hash;
- verified loopback TLS server fingerprint.

Therefore a timer catch-up can be accepted only as a healthy no-op lifecycle run.

## A7. Safe rollback

If activation/postcheck fails, the executor stops and disables the timer.

The rollback is PASS only when the timer is inactive+disabled and the lifecycle service is no longer active/activating.

This returns the system to a dormant safe state instead of leaving an unproven activation path enabled across reboot.

## A8. No direct auto-renew invocation

The executor invokes only the timer unit. It does not directly invoke the lifecycle CLI or service.

If systemd performs a persistent catch-up, that is classified and verified from durable status/runtime evidence rather than being hidden.

## A9. No Broker restart

The activation executor contains no Broker activation/restart command.

Any server-certificate change, server-key change, CA change, Broker identity/start-time change, or TLS fingerprint change blocks PASS.

## CI boundary

The runtime-activation tests are wired into `N3W Broker ingress guard CI`.

Live timer start remains blocked until the exact PR head passes focused and normal repository workflows.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_RUNTIME_ACTIVATION_EXECUTION_20260929_01
```
