# N3-W KF-100 Broker Certificate Lifecycle Production Deployment Preflight Review — 2026-09-29

Status: `SOURCE_REVIEW_PASS`  
PR: `#507`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-production-deployment-preparation-20260929`  
Exact reviewed source/test head: `4b3d77e83f16c91cd73eabf543c02e1a40158c44`  
Base main: `5d9e6007ab89e23403b4aaba98102ee2f5a6418a`

## Review result

```text
A1_RUNTIME_OBJECT_BINDING=PASS
A2_CERTIFICATE_FINGERPRINT_BINDING=PASS
A3_SERVER_CERT_KEY_BINDING=PASS
A4_LIVE_TLS_ENDPOINT_BINDING=PASS
A5_CA_PRIVATE_KEY_REBIND=PASS
A6_SYSTEM_CA_BINDING=PASS
A7_SYSTEMD_PREDEPLOYMENT_STATE=PASS
A8_UNKNOWN_TARGET_OVERWRITE_GUARD=PASS
A9_NO_LIVE_MUTATION_SOURCE_CONTRACT=PASS
A10_HOST_TEST_COVERAGE=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REVIEW=PASS
LIVE_T1_MUTATION=false
```

## A1. Runtime object binding

The preflight discovers exactly one running Docker object using the frozen Compose labels:

```text
project=n3wfc4
service=broker
```

It does not select the Broker by image text or container name.

The active TLS authority is then derived from the current container's exact bind mounts for:

```text
/mosquitto/tls/ca.pem
/mosquitto/tls/server.pem
/mosquitto/tls/server.key
```

Each mount must be a unique read-only bind.

## A2. Certificate fingerprint binding

The preflight freezes the already archived current production fingerprints for:

- FC4 private CA;
- current Broker server certificate;
- H0/H1 System CA.

Any drift stops the gate instead of silently adopting new certificate authority.

This is appropriate for deployment preparation because ordinary certificate renewal has not yet been installed or enabled.

## A3. Server certificate/private-key binding

The source converts the current server certificate public key and mounted server private key public key to DER and requires byte equality.

The mounted server private key must also be root-owned and have no group/other permission bits.

This closes a production prerequisite that was previously inferred from working TLS but not independently bound in the KF-100 deployment route.

## A4. Live TLS endpoint binding

The preflight creates a real loopback TLS connection to TCP/8883 with:

```text
CA=current exact FC4 CA
server_name=armbian
certificate verification=required
hostname verification=required
time verification=required
```

The presented DER certificate SHA-256 must equal the archived current server certificate fingerprint.

Therefore file-level authority and actually served endpoint authority are both required.

## A5. FC4 CA private-key rebind

The preflight repeats the bounded schema-v2 private-key authority logic rather than relying only on historical evidence.

It searches:

- the active FC4 persistent root derived from the current CA bind;
- current bounded `/root/n3w-fc4-private-materialization.*` roots.

Only private-key-looking files are passed to OpenSSL.

Exactly one private key must match the active CA public key, and it must be root-owned with no group/other access.

The raw private-key path and key body are not printed. Only a one-way relative path token is emitted.

## A6. System CA binding

The existing H0/H1 System CA is monitor-only in KF-100. The preflight requires its archived fingerprint and CA basic constraint before later lifecycle environment materialization can reference it.

No System CA private key is read or required.

## A7. systemd predeployment state

The existing accepted units must both be:

```text
n3wfc4-broker-ingress-guard.service
active + enabled

n3wfc4-broker-activation.service
active + enabled
```

The new lifecycle timer must not already be active or enabled.

No systemd mutation command exists in the preflight source.

## A8. Unknown-target overwrite guard

Before installation, the following exact deployment targets must all be absent:

```text
/usr/local/sbin/n3w-broker-certificate-lifecycle
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
/etc/n3wfc4/broker-certificate-lifecycle.env
```

If any target already exists, preparation stops. The later deployment gate must classify that state rather than overwrite it.

## A9. No-live-mutation source contract

The preflight performs only:

- Docker read operations;
- certificate/key reads;
- OpenSSL verification;
- loopback TLS connection;
- bounded filesystem reads;
- `systemctl is-active`;
- `systemctl is-enabled`.

It contains no service start/stop/restart/enable, Docker mutation, file creation/removal/replace, certificate generation, certificate renewal, or status write.

## A10. Regression coverage and CI

Focused tests cover:

- happy read-only PASS;
- timer already enabled;
- pre-existing deployment target;
- active CA fingerprint drift;
- server certificate/private-key mismatch;
- duplicate matching CA private key;
- bounded source no-mutation primitive guard;
- invalid execution limits.

At exact source/test head `4b3d77e83f16c91cd73eabf543c02e1a40158c44`:

```text
PR_WORKFLOWS=12_OF_12_PASS
N3W_BROKER_INGRESS_GUARD_CI_RUN=36521261740
N3W_BROKER_INGRESS_GUARD_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI_RUN=36521261775
PUBLIC_REPOSITORY_SAFETY_CI=PASS
```

The reviewed preflight Git blob is:

```text
PATH=tools/n3w_broker_certificate_lifecycle_deployment_preflight.py
GIT_BLOB_SHA1=5740c6e30a867e8f32f8745e20b5135f23fb5a1e
```

## Disposition

```text
KF100_PRODUCTION_DEPLOYMENT_PREPARATION_SOURCE=PASS
KF100_PRODUCTION_DEPLOYMENT_PREPARATION_TESTS=PASS
KF100_PRODUCTION_DEPLOYMENT_PREFLIGHT_REVIEW=PASS
LIVE_T1_MUTATION=false
CERTIFICATE_MUTATION=false
TIMER_ENABLEMENT=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_DEPLOYMENT_READONLY_PREFLIGHT_20260929_01
```


## Post-review live correction

The first real T1 read-only execution exposed one review assumption error:

```text
OLD_ASSUMPTION=server.key must be root-owned
LIVE_FACT=running Mosquitto effective UID/GID is 1883:1883
LIVE_FACT=server.key UID/GID is 1883:1883
LIVE_FACT=server.key mode is 0600
LIVE_FACT=container-visible server.key UID/GID/mode is 1883:1883/0600
LIVE_FACT=server cert/key public-key match PASS
CLASSIFICATION=PREFLIGHT_HARNESS_DEFECT
PRODUCT_TLS_DEFECT=false
```

The corrected contract binds server-key ownership to the running Broker process effective UID/GID instead of root. This is stricter and more accurate for the actual runtime because it proves that the least-privilege Mosquitto process is the intended reader.

The FC4 CA signing key remains independently required to be root-owned and mode-safe.

The corrected source adds regression coverage for:

- non-root Broker UID/GID with exact server-key owner match = PASS;
- server-key owner not matching running Broker UID/GID = STOP.

A fresh source/test review must bind the corrected commit and CI before the live read-only preflight is repeated.


## Corrected source/test closure

The ownership correction is closed at exact source/test head:

```text
CORRECTED_SOURCE_TEST_HEAD=dadc698f25fdb47d9553876dcbe05874cfc7f95b
CORRECTED_PREFLIGHT_GIT_BLOB_SHA1=8f3a09fee5cdad1d60dd76406e3dd03c7aa510ed

PR_WORKFLOWS=12_OF_12_PASS
N3W_BROKER_INGRESS_GUARD_CI_RUN=36522237488
N3W_BROKER_INGRESS_GUARD_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI_RUN=36522237545
PUBLIC_REPOSITORY_SAFETY_CI=PASS

SERVER_KEY_OWNER_POLICY=RUNNING_BROKER_EFFECTIVE_UID_GID
SERVER_KEY_MODE_POLICY=NO_GROUP_OR_OTHER_BITS
FC4_CA_KEY_OWNER_POLICY=ROOT
FC4_CA_KEY_MODE_POLICY=NO_GROUP_OR_OTHER_BITS

LIVE_REPEAT_PREFLIGHT_AUTHORIZED=true
LIVE_MUTATION=false
```
