# N3-W KF-100 Broker Certificate Lifecycle Timer Enablement Preparation — 2026-09-29

Status: `SOURCE_PREPARED_PENDING_CI_AND_LIVE_ENABLEMENT`  
Base main: `9e29cfe2ecd709a0b8e9e824c947aa2a19a45d97`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-timer-enablement-preparation-20260929`  
Predecessor: production first-audit gate CLOSED_PASS

## 1. Goal

Enable persistence for the already-installed lifecycle timer without starting the timer, without starting the lifecycle service, and without invoking certificate lifecycle logic.

The only intended production mutation is:

```text
systemctl enable n3wfc4-broker-certificate-lifecycle.timer
```

The command is deliberately executed without `--now`.

## 2. Why enablement is separated from activation

The installed timer contains:

```text
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true
Unit=n3wfc4-broker-certificate-lifecycle.service
WantedBy=timers.target
```

The installed service executes `auto-renew`.

Therefore this gate creates only boot-time timer persistence. It does not start the timer in the current boot and cannot intentionally invoke the service.

A later activation/reboot gate must separately establish actual scheduled runtime behavior.

## 3. Exact production source authority

The executor requires the already-installed exact blobs:

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

The current first-audit durable status must still prove:

```text
action=audit
result=ok
server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY
renewal_attempted=false
rollback_attempted=false
```

with the frozen production fingerprints and validity endpoints.

## 4. Pre-enable state

The gate requires:

```text
lifecycle timer enabled=disabled
lifecycle timer active!=active
lifecycle service active!=active

status.json present
lock present
status/lock root:root 0600
status directory root:root 0700
status directory contains exactly status+lock
```

The current private environment remains root-owned mode 0600 and must bind the same Broker certificate/key/CA paths and server name as the live runtime.

## 5. Mutation contract

Normal-path systemd mutation is exactly:

```text
systemctl enable n3wfc4-broker-certificate-lifecycle.timer
```

Forbidden on the normal path:

```text
systemctl enable --now
systemctl start
systemctl restart
systemctl stop
lifecycle service invocation
auto-renew invocation
Broker restart
certificate mutation
server-key mutation
CA mutation
```

If `systemctl enable` itself fails after partially creating enablement state, the executor is allowed to issue only:

```text
systemctl disable n3wfc4-broker-certificate-lifecycle.timer
```

to restore the proven disabled prestate.

If the timer unexpectedly becomes active, rollback is reported `UNPROVEN`; the executor does not automatically stop an unexpectedly active timer because that would exceed this gate's enable-only mutation authority. That condition requires read-only forensic inspection before any next mutation.

## 6. Proof that enablement did not run lifecycle logic

Before enablement the executor records:

- durable lifecycle status SHA-256;
- Broker container identity;
- Broker StartedAt;
- server certificate SHA-256;
- server private-key SHA-256;
- FC4 CA certificate SHA-256;
- live verified TLS server fingerprint.

After enablement it requires:

```text
timer enabled=enabled
timer active!=active
lifecycle service active!=active

status SHA-256 unchanged

Broker container unchanged
Broker StartedAt unchanged
server certificate unchanged
server private key unchanged
FC4 CA certificate unchanged
live TLS fingerprint unchanged
```

The unchanged durable status is an additional oracle that the lifecycle service did not run even briefly and complete during enablement.

## 7. Source authority

```text
tools/n3w_broker_certificate_lifecycle_timer_enable.py
source/test head=e39f5e908843477b4880f727b9acc6058c3578a8
git blob=c39fe418642e12d5b0c8bc7994cd06a443086d33
```

Regression coverage includes:

- successful exact `systemctl enable` without `--now`;
- prestate must be disabled;
- enable failure restores disabled state;
- unexpected active timer produces rollback `UNPROVEN`;
- status drift after enablement triggers disable rollback;
- source contains no start/restart/auto-renew invocation.

## 8. Current boundary

```text
PRODUCTION_INSTALLATION=PASS
FIRST_AUDIT=PASS
DURABLE_STATUS_AUTHORITY=ESTABLISHED

TIMER_ENABLEMENT_EXECUTOR_SOURCE=PREPARED
TIMER_ENABLEMENT_TESTS=PREPARED
LIVE_TIMER_ENABLEMENT=false

TIMER_START=false
AUTO_RENEW_INVOCATION=false
BROKER_RESTART=false
CERTIFICATE_MUTATION=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_ENABLEMENT_EXECUTION_20260929_01
```
