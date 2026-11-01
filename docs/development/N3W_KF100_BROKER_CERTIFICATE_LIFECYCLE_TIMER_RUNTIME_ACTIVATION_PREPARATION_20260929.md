# N3-W KF-100 Broker Certificate Lifecycle Timer Runtime Activation Preparation — 2026-09-29

Status: `SOURCE_PREPARED_PENDING_CI_AND_LIVE_ACTIVATION`  
Base main: `2e777f6da816a5b3ba8a3562f7356d4af21c4eab`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-timer-runtime-activation-preparation-20260929`  
Predecessor: timer enablement gate CLOSED_PASS

## 1. Goal

Activate the already-enabled lifecycle timer in the current boot and prove that systemd has accepted it as an active scheduled timer without allowing an unobserved certificate mutation.

The normal-path production mutation is:

```text
systemctl start n3wfc4-broker-certificate-lifecycle.timer
```

## 2. Persistent timer semantics

The installed timer is:

```text
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true
Unit=n3wfc4-broker-certificate-lifecycle.service
```

For a persistent calendar timer, systemd may trigger the service when the timer is activated if a calendar firing was missed while the timer was inactive. Such catch-up triggering remains subject to `RandomizedDelaySec`.

Therefore this gate does **not** assume that starting the timer is guaranteed to be service-free.

It accepts either:

```text
A. timer becomes active/scheduled and durable lifecycle status remains unchanged
B. a persistent catch-up run is observed, but the resulting status remains
   HEALTHY/HEALTHY/HEALTHY with renewal_attempted=false and no TLS material change
```

If the catch-up is delayed by the randomized delay, the gate may finish before that later scheduled run occurs. A later first-trigger acceptance may still be required before final KF-100 closure.

## 3. Exact production authority

The executor requires:

```text
/usr/local/sbin/n3w-broker-certificate-lifecycle
blob=65187b27a2ddd8f57221500a7019486e02bca101
mode=0755

/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
blob=fa13967ef0ffb0a271fcb7122febd83b83079deb
mode=0644

/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
blob=65b0365c5ea5f5d3c896a133adc0d689bb2deced
mode=0644
```

The durable lifecycle status must still be public-safe and report:

```text
action=audit
result=ok
server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY
renewal_attempted=false
rollback_attempted=false
```

with the frozen production certificate fingerprints and validity endpoints.

## 4. Required prestate

```text
timer enabled=enabled
timer active!=active
lifecycle service active!=active

status directory=root:root 0700
status.json=root:root 0600
lock=root:root 0600
status directory contains exactly status+lock

Broker/TLS/certificate/key/CA authority unchanged
```

## 5. Runtime activation acceptance

After `systemctl start ...timer`:

```text
timer ActiveState=active
timer UnitFileState=enabled
NextElapseUSecRealtime present
lifecycle service eventually inactive
```

The executor re-reads timer properties after a bounded service-settle window.

If the durable status changes during activation, it is accepted only when timer `LastTriggerUSec` proves a timer trigger and the resulting lifecycle status still satisfies the healthy/no-renewal contract.

## 6. No certificate-mutation acceptance

Before timer activation the executor freezes:

- Broker container identity;
- Broker StartedAt;
- server certificate SHA-256;
- server private-key SHA-256;
- FC4 CA certificate SHA-256;
- live verified TLS/8883 fingerprint;
- durable lifecycle status SHA-256.

After activation it requires:

```text
Broker container unchanged
Broker StartedAt unchanged
server certificate unchanged
server private key unchanged
FC4 CA certificate unchanged
live TLS fingerprint unchanged
```

If a catch-up status update occurs, its document must still state:

```text
renewal_attempted=false
rollback_attempted=false
server/CA/System-CA=HEALTHY
```

## 7. Failure rollback

If timer start fails or a post-activation invariant fails, the executor uses a bounded safety rollback:

```text
systemctl stop n3wfc4-broker-certificate-lifecycle.timer
systemctl disable n3wfc4-broker-certificate-lifecycle.timer
```

The safe rollback target is:

```text
timer inactive
timer disabled
lifecycle service not active/activating
```

This intentionally returns to the last fully dormant lifecycle state rather than leaving a failed runtime-activation route enabled for a future reboot.

If that state cannot be proven, the executor returns:

```text
activation_rollback=UNPROVEN
```

and further mutation stops.

## 8. Source authority

```text
tools/n3w_broker_certificate_lifecycle_timer_activate.py
source/test head=1d2f6ee2bc6c4f027583cdb8fddc7066077f083c
git blob=61e54cd3d27a615b56db913ef7b4ac0916c6a9ab
```

Regression coverage includes:

- active scheduled timer with no immediate catch-up;
- healthy persistent catch-up acceptance;
- status change without timer trigger rejection;
- missing next-elapse rejection + rollback;
- timer-enabled precondition;
- source-level no Broker restart / no direct auto-renew invocation.

## 9. Current boundary

```text
PRODUCTION_INSTALLATION=PASS
FIRST_AUDIT=PASS
TIMER_ENABLEMENT=PASS

TIMER_RUNTIME_ACTIVATION_EXECUTOR_SOURCE=PREPARED
TIMER_RUNTIME_ACTIVATION_TESTS=PREPARED
LIVE_TIMER_RUNTIME_ACTIVATION=false

BROKER_RESTART=false
CERTIFICATE_MUTATION=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_RUNTIME_ACTIVATION_EXECUTION_20260929_01
```
