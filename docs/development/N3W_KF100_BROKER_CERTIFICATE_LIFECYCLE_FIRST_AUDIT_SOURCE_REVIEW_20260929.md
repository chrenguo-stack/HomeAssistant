# N3-W KF-100 Broker Certificate Lifecycle First Audit Source Review — 2026-09-29

Status: `SOURCE_REVIEW_PASS_PENDING_CI`  
PR: `#510`  
Branch: `exec/n3w-kf100-broker-certificate-lifecycle-first-audit-preparation-20260929`  
Reviewed source/test head: `f185018e333107e24a368339cfd06a62be8d6a3f`  
Reviewed executor Git blob SHA-1: `3c800633b557c0b1b22eb3ee5be129b69500c4df`  
Base main: `58e881d09fcc96beb9b6d8c1b496bee2e10b8472`

## Review result

```text
A1_EXACT_INSTALLED_SOURCE_BINDING=PASS
A2_FIRST_AUDIT_PRESTATE=PASS
A3_AUDIT_ONLY_INVOCATION=PASS
A4_PRIVATE_KEY_NONDEPENDENCY=PASS
A5_EXPECTED_HEALTHY_STATUS_CONTRACT=PASS
A6_DURABLE_STATUS_PRIVACY=PASS
A7_TIMER_SERVICE_DORMANCY=PASS
A8_BROKER_TLS_CONTINUITY=PASS
A9_FIRST_AUDIT_SINGLE_EXECUTION_BOUNDARY=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REVIEW=PASS_PENDING_CI
LIVE_FIRST_AUDIT=false
```

## A1. Exact installed source binding

The executor requires the exact production-installed lifecycle executable, service unit and timer unit Git blobs and their expected root ownership/modes.

Any installed-source drift stops before audit.

## A2. First-audit prestate

Before the first lifecycle invocation, the executor requires:

```text
status directory = root:root 0700
status.json absent
.certificate-lifecycle.lock absent
status directory otherwise empty

lifecycle service inactive
lifecycle timer inactive
lifecycle timer not enabled
```

The exact-empty status-directory rule prevents accepting an earlier untracked lifecycle execution or partial state.

## A3. Audit-only invocation

The only lifecycle command assembled by the executor is:

```text
/usr/local/sbin/n3w-broker-certificate-lifecycle audit ...
```

It does not start the systemd lifecycle service because that service is intentionally wired to `auto-renew`.

The executor source contains no systemctl start/enable/restart/stop or Docker mutation command.

## A4. Private-key nondependency

The direct audit command deliberately omits:

```text
--server-key
--ca-key
```

The private environment is parsed only to bind the deployed configuration and to prove that no private path leaks into status output. The audit CLI itself receives certificate and trust paths only.

Therefore the first expiry audit does not require the FC4 CA signing key or server private key as command inputs.

## A5. Expected healthy status contract

The executor requires exact current certificate identities and validity endpoints:

```text
SERVER_FINGERPRINT=8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb
SERVER_NOT_AFTER=2028-11-22T04:18:40Z

FC4_CA_FINGERPRINT=b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351
FC4_CA_NOT_AFTER=2036-08-17T04:18:39Z

SYSTEM_CA_FINGERPRINT=745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7
SYSTEM_CA_NOT_AFTER=2036-07-30T15:32:24Z
```

The first audit must return:

```text
action=audit
result=ok
server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY
renewal_attempted=false
rollback_attempted=false
```

A changed lifecycle state is treated as drift and stops acceptance rather than being normalized into PASS.

## A6. Durable status privacy

After audit, exactly two entries may exist in the private status directory:

```text
status.json
.certificate-lifecycle.lock
```

Both must be root-owned mode 0600.

The status JSON must equal the lifecycle CLI output and may contain only public-safe certificate/status fields. The executor rejects any raw private path or PEM material in the durable status document.

## A7. Timer/service dormancy

Both before and after audit:

```text
lifecycle service active != active
lifecycle timer active != active
lifecycle timer enabled != enabled
```

The gate does not alter systemd persistence state.

## A8. Broker/TLS continuity

The executor captures and then rechecks:

- Broker container identity;
- Broker `StartedAt`;
- active server certificate SHA-256;
- active server private-key SHA-256;
- active FC4 CA certificate SHA-256;
- verified loopback TLS/8883 served fingerprint.

All must remain unchanged after audit.

## A9. Single-execution boundary

This first-audit route is intentionally non-repeatable as a first-audit gate: once status/lock exist, the prestate no longer qualifies.

If the live audit runs but later acceptance fails, the next action is read-only forensic inspection of the created lifecycle state, not blind replay.

## CI boundary

The focused regression suite is wired into `N3W Broker ingress guard CI`.

Live execution remains blocked until the exact current PR head passes the focused tests and the normal PR workflows.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_AUDIT_EXECUTION_20260929_01
```
