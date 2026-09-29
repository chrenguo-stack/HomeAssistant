# N3-W KF-100 Broker Certificate Lifecycle Production Deployment Preparation — 2026-09-29

Status: `SOURCE_PREPARATION_READY_PENDING_CI_AND_LIVE_READONLY_PREFLIGHT`  
Base main: `5d9e6007ab89e23403b4aaba98102ee2f5a6418a`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-production-deployment-preparation-20260929`  
Predecessor: PR #506 merged / KF-100 source repair + CA private-key authority PASS

## 1. Goal

Prepare the production T1 deployment of the merged Broker certificate lifecycle source without enabling automatic renewal and without modifying certificates.

This gate is intentionally split:

```text
Phase A
repository-versioned read-only deployment preflight
→ no T1 writes

Phase B
install lifecycle source/unit/env/status authority
→ still no timer enablement
→ no certificate renewal

Phase C
run lifecycle audit and verify durable status
→ audit status write only
→ no certificate renewal

Phase D
separate timer enablement gate
→ only after Phase B/C acceptance
```

This document currently authorizes preparation only. It does not execute Phase B/C/D.

## 2. Why a separate read-only preflight is required

The merged lifecycle CLI supports `audit`, but the CLI deliberately writes a lock file and durable status JSON. Therefore invoking the installed CLI is not a zero-write preflight.

Before any installation, a separate repository-versioned read-only source is used:

```text
tools/n3w_broker_certificate_lifecycle_deployment_preflight.py
```

This preflight performs no file creation, service mutation, Docker mutation, certificate mutation, or timer enablement.

## 3. Frozen current production identity

The preflight binds current runtime authority instead of trusting static host paths alone.

Required active Broker identity:

```text
Compose project=n3wfc4
Compose service=broker
running=true
```

Required read-only Broker TLS bind targets:

```text
/mosquitto/tls/ca.pem
/mosquitto/tls/server.pem
/mosquitto/tls/server.key
```

Archived certificate authority:

```text
FC4_CA_SHA256_FINGERPRINT=b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351
BROKER_SERVER_SHA256_FINGERPRINT=8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb
SYSTEM_CA_SHA256_FINGERPRINT=745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7
TLS_SERVER_NAME=armbian
```

Any fingerprint or runtime-object drift stops deployment preparation.

## 4. Read-only checks

The deployment preflight proves all of the following in one bounded run:

1. the current Broker object is unique and running;
2. all three TLS files are unique read-only bind mounts;
3. active FC4 CA fingerprint matches the archived authority and is a CA;
4. active server certificate fingerprint matches the archived authority;
5. server certificate is non-CA and SAN contains the frozen TLS server name;
6. server certificate verifies under the active FC4 CA for that hostname and current time;
7. active server certificate and active server private key have the same public key;
8. server private key is root-owned and not group/other accessible;
9. a real loopback TLS/8883 connection validates under the exact FC4 CA, hostname, and current time, and presents the same server certificate fingerprint;
10. the H0/H1 System CA matches the archived System CA authority;
11. a bounded current-authority scan still finds exactly one FC4 CA private-key match;
12. the unique FC4 CA key is root-owned and not group/other accessible;
13. existing ingress guard and Broker activation units are both active and enabled;
14. the certificate lifecycle timer is not already active/enabled;
15. the four intended lifecycle deployment targets are absent, avoiding silent overwrite of unknown pre-existing state.

The preflight prints only public-safe fingerprints, dates, modes, counts, systemd states, and a one-way token for the matching CA private-key path. It never prints the private-key body or raw private-key path.

## 5. Search limits

The CA private-key rebind remains bounded:

```text
MAX_FILE_BYTES=65536
DEFAULT_MAX_FILES=5000
DEFAULT_MAX_DEPTH=8
SYMLINK_FOLLOW=false
```

Search roots are:

- the persistent greenhouse FC4 root derived from the active Broker CA bind;
- bounded current `/root/n3w-fc4-private-materialization.*` roots.

Only private-key-looking files are passed to OpenSSL.

## 6. Intended Phase B production mapping

After read-only PASS, the later install gate will use the merged PR #506 source authority:

```text
tools/n3w_broker_certificate_lifecycle.py
→ /usr/local/sbin/n3w-broker-certificate-lifecycle
root:root 0755

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.service
→ /etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
root:root 0644

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer
→ /etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
root:root 0644

private generated environment
→ /etc/n3wfc4/broker-certificate-lifecycle.env
root:root 0600
```

The private environment will reference current runtime-resolved production paths. Raw private paths are not committed to GitHub.

The status authority will be under a root-owned mode-0700 private directory and the status JSON will be mode 0600.

## 7. Phase B prohibition

The install gate must not call the existing combined persistence installer because that installer intentionally enables the lifecycle timer.

Preparation requires:

```text
systemctl daemon-reload
allowed=true

systemctl enable n3wfc4-broker-certificate-lifecycle.timer
allowed=false

systemctl start n3wfc4-broker-certificate-lifecycle.service
allowed=false

systemctl start n3wfc4-broker-certificate-lifecycle.timer
allowed=false

systemctl restart n3wfc4-broker-activation.service
allowed=false

certificate write/replace
allowed=false
```

The first installed-state action will be an explicit audit gate after source/env/unit installation.

## 8. Phase C audit boundary

After installation, the first lifecycle invocation must be:

```text
mode=audit
```

Expected result while the current 2028 server certificate remains healthy:

```text
action=audit
server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY
renewal_attempted=false
rollback_attempted=false
result=ok
```

That audit writes only the lifecycle lock/status authority. It must not access renewal code that changes the certificate or restarts Broker.

A post-audit read-only check must prove:

- Broker container identity and uptime continuity were not changed by audit;
- served TLS fingerprint remains the archived current server fingerprint;
- Manager remains running;
- certificate files retain their pre-audit hashes;
- timer remains disabled/inactive.

## 9. Timer enablement remains separate

Timer enablement is not implied by source installation or audit PASS.

A later gate may enable the timer only after the installed service/env paths and audit result are independently reviewed.

No immediate `--now` behavior is allowed.

## 10. Current disposition

```text
KF100_SOURCE_REPAIR=PASS
KF100_CA_PRIVATE_KEY_RUNTIME_AUTHORITY=PROVEN
PR506_MERGED=true
PR506_MERGE_COMMIT=5d9e6007ab89e23403b4aaba98102ee2f5a6418a
PR506_POSTMERGE_CI=PASS

PRODUCTION_DEPLOYMENT_PREPARATION_BRANCH_CREATED=true
PRODUCTION_DEPLOYMENT_PREFLIGHT_SOURCE=PREPARED
T1_MUTATION=false
CERTIFICATE_MUTATION=false
TIMER_ENABLEMENT=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_DEPLOYMENT_READONLY_PREFLIGHT_20260929_01
```
