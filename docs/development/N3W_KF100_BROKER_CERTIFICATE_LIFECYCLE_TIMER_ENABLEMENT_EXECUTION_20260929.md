# N3-W KF-100 Broker Certificate Lifecycle Timer Enablement Execution — 2026-09-29

Status: `PREEXECUTION_READY`  
Base main: `2f624de4aa1e9d6947c52b4cf28869b00e73d240`  
Predecessor PR: `#512` merged  
Execution branch: `exec/n3w-kf100-broker-certificate-lifecycle-timer-enablement-execution-20260929`

## Exact merged authority

```text
TIMER_ENABLEMENT_EXECUTOR=
tools/n3w_broker_certificate_lifecycle_timer_enable.py
GIT_BLOB_SHA1=c39fe418642e12d5b0c8bc7994cd06a443086d33

LIFECYCLE_TOOL_BLOB=
65187b27a2ddd8f57221500a7019486e02bca101

LIFECYCLE_TIMER_BLOB=
65b0365c5ea5f5d3c896a133adc0d689bb2deced

LIFECYCLE_SERVICE_BLOB=
fa13967ef0ffb0a271fcb7122febd83b83079deb
```

PR #512 exact head `6cb00c615c4cd5dd7c5d7f2eb5de4975bf99fe1e` completed all 12 PR workflows successfully before merge.

Post-merge main:
`2f624de4aa1e9d6947c52b4cf28869b00e73d240`

Post-merge push CI at preparation time:

```text
Public repository safety CI run 36533156256 = PASS
N3W Broker ingress guard CI run 36533156258 = PASS
```

Post-merge focused CI is PASS. Live execution is now authorized by the current gate.

## Live mutation boundary

The only normal-path T1 mutation is:

```text
systemctl enable n3wfc4-broker-certificate-lifecycle.timer
```

The exact executor is streamed over SSH and is not persistently installed on T1.

The executor does not use `--now`.

## Prohibited actions

```text
timer start=false
lifecycle service start=false
auto-renew invocation=false
Broker restart=false
certificate mutation=false
server private-key mutation=false
FC4 CA mutation=false
Manager restart=false
Home Assistant restart=false
```

## Required prestate

Before enablement:

```text
timer enabled=disabled
timer active!=active
lifecycle service active!=active

first-audit durable status HEALTHY/HEALTHY/HEALTHY
renewal_attempted=false
rollback_attempted=false

status.json + lock remain root:root 0600
status directory contains exactly those two files

Broker/TLS/cert/key/CA identities match current authority
```

## Expected PASS

```text
result=PASS
timer_enablement=true
timer_enabled=enabled
timer_active!=active
lifecycle_service_active!=active

timer_start=false
enable_now_used=false
auto_renew_invocation=false
status_unchanged=true

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

If enablement fails or a non-activation postcondition fails, the executor may only run:

```text
systemctl disable n3wfc4-broker-certificate-lifecycle.timer
```

to restore the disabled prestate.

If the timer unexpectedly becomes active, the executor reports:

```text
enablement_rollback=UNPROVEN
```

and must not extend authority to stopping the timer. The next step would be read-only forensic inspection.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_ENABLEMENT_EXECUTION_20260929_01
```
