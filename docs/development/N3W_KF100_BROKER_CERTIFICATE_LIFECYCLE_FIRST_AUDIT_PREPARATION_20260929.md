# N3-W KF-100 Broker Certificate Lifecycle First Audit Preparation — 2026-09-29

Status: `SOURCE_PREPARED_PENDING_CI_AND_LIVE_AUDIT`  
Base main: `58e881d09fcc96beb9b6d8c1b496bee2e10b8472`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-first-audit-preparation-20260929`  
Predecessor: production installation-only gate CLOSED_PASS

## 1. Goal

Run the first explicit production lifecycle `audit` after installation, while proving that the system remains outside the renewal path.

This gate intentionally permits only two new durable lifecycle artifacts:

```text
/var/lib/n3wfc4-certificate-lifecycle/.certificate-lifecycle.lock
/var/lib/n3wfc4-certificate-lifecycle/status.json
```

Both must be root-owned mode `0600`.

The gate does not enable or start the timer, does not start the installed systemd lifecycle service, does not invoke `auto-renew`, and does not restart Broker.

## 2. Why direct audit invocation is used

The installed systemd service is intentionally wired to:

```text
auto-renew
```

Therefore the first audit must not start the service unit.

The first-audit executor invokes the installed lifecycle CLI directly with:

```text
mode=audit
```

and deliberately omits:

```text
--server-key
--ca-key
```

This proves that ordinary expiry inspection does not depend on either production signing private key.

## 3. Exact installed source authority

The first-audit prestate requires the exact already-installed production blobs:

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

The private lifecycle environment must remain:

```text
root:root 0600
```

and the status directory must remain:

```text
root:root 0700
```

## 4. First-audit preconditions

Before invoking `audit`, the executor requires:

- lifecycle tool/service/timer exact blob identities;
- private env exact key set and safe permissions;
- status directory root-owned mode 0700;
- no existing status JSON;
- no existing lifecycle lock file;
- lifecycle service inactive;
- lifecycle timer inactive;
- lifecycle timer not enabled;
- current env server/CA paths equal the current Broker bind mounts;
- server name still `armbian`;
- current server/FC4 CA/System CA fingerprints equal the archived production authority;
- live loopback TLS/8883 still verifies and serves the current server fingerprint.

The first-audit gate is fail-closed if a status/lock already exists because that would prove some lifecycle execution happened outside this first-audit authority.

## 5. Expected audit state

At the current certificate dates, expected output is:

```text
schema=gh.n3w-broker-certificate-lifecycle/1
action=audit
result=ok

server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY

renewal_attempted=false
rollback_attempted=false
```

Expected fingerprints remain:

```text
SERVER=
8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb

FC4_CA=
b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351

SYSTEM_CA=
745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7
```

Any warning/renewal/critical/expired state in this first audit is treated as drift and stops the gate for review rather than silently accepting a changed lifecycle state.

## 6. Status privacy contract

The durable `status.json` is compared to the CLI's public JSON result.

It must not contain:

- raw server certificate path;
- raw server private-key path;
- raw FC4 CA certificate path;
- raw FC4 CA signing-key path;
- raw System CA path;
- raw allowed-root paths;
- PEM certificate data;
- PEM private-key data.

The raw environment body is never printed by the first-audit executor.

## 7. Post-audit continuity

After status/lock creation, the executor must prove:

```text
lifecycle service remains inactive
lifecycle timer remains inactive
lifecycle timer remains not enabled

Broker container identity unchanged
Broker StartedAt unchanged

server certificate SHA-256 unchanged
server private-key SHA-256 unchanged
FC4 CA certificate SHA-256 unchanged

live TLS/8883 still verifies
served certificate fingerprint unchanged
```

Therefore audit status creation is separated from renewal and Broker activation behavior.

## 8. Source under review

```text
tools/n3w_broker_certificate_lifecycle_first_audit.py
source head=7e2d5af707b487117ba52e06094b8e3d09d5f363
git blob=a1d181c00d82fa455356b6f18f514788030e7dd0
```

Regression coverage includes:

- direct audit command contains no private-key arguments and no `auto-renew`;
- successful first audit;
- existing status blocks execution;
- unexpected audit document blocks acceptance;
- environment exact-key-set validation;
- source-level no service/timer activation commands.

## 9. Current boundary

```text
PRODUCTION_INSTALLATION=PASS

FIRST_AUDIT_EXECUTOR_SOURCE=PREPARED
FIRST_AUDIT_TESTS=PREPARED
LIVE_FIRST_AUDIT=false

STATUS_FILE_CREATED=false
LOCK_FILE_CREATED=false
CERTIFICATE_MUTATION=false
BROKER_RESTART=false
TIMER_ENABLEMENT=false
AUTO_RENEW_INVOCATION=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_AUDIT_EXECUTION_20260929_01
```
