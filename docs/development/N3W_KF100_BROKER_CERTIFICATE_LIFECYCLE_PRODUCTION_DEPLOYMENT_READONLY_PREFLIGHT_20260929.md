# N3-W KF-100 Broker Certificate Lifecycle Production Deployment Read-Only Preflight — 2026-09-29

Status: `CLOSED_PASS`  
Preparation PR: `#507`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-production-deployment-preparation-20260929`  
Corrected preflight source/test head: `dadc698f25fdb47d9553876dcbe05874cfc7f95b`  
Corrected preflight Git blob SHA-1: `8f3a09fee5cdad1d60dd76406e3dd03c7aa510ed`

## Result

The corrected production deployment read-only preflight completed with:

```text
RESULT=PASS
PREFLIGHT_RC=0

READ_ONLY=true
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_MUTATION=false
HOMEASSISTANT_MUTATION=false
CERTIFICATE_MUTATION=false
TIMER_ENABLEMENT=false
```

## Runtime binding

```text
BROKER_RUNNING=true

INGRESS_GUARD_ACTIVE=active
INGRESS_GUARD_ENABLED=enabled

BROKER_ACTIVATION_ACTIVE=active
BROKER_ACTIVATION_ENABLED=enabled

LIFECYCLE_TIMER_ACTIVE=inactive
LIFECYCLE_TIMER_ENABLED=not-found

DEPLOYMENT_TARGET_PRESENT_COUNT=0
```

No lifecycle deployment target existed before installation preparation.

## Broker TLS authority

```text
SERVER_NAME=armbian

BROKER_CA_SHA256_FINGERPRINT=
b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351

BROKER_SERVER_SHA256_FINGERPRINT=
8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb

BROKER_SERVER_NOT_AFTER=2028-11-22T04:18:40Z
BROKER_CA_NOT_AFTER=2036-08-17T04:18:39Z

LIVE_TLS_VERIFIED=true
LIVE_TLS_FINGERPRINT_MATCH=true
SERVER_CERTIFICATE_KEY_MATCH=true
```

The real loopback TLS/8883 endpoint passed current-time CA and hostname verification and presented the same server certificate fingerprint as the mounted production certificate.

## Broker server-key privilege authority

The corrected preflight bound the private-key owner to the actual running Mosquitto effective identity:

```text
BROKER_EFFECTIVE_UID=1883
BROKER_EFFECTIVE_GID=1883

SERVER_KEY_UID=1883
SERVER_KEY_GID=1883
SERVER_KEY_MODE=0600
SERVER_KEY_MODE_SAFE=true
SERVER_KEY_OWNER_MATCHES_BROKER=true
```

This confirms the first preflight STOP was a harness assumption defect, not a product TLS defect. No permission change is required.

## FC4 CA signing-key authority

The bounded production search repeated the earlier authority proof:

```text
SEARCH_ROOT_COUNT=2
SEARCH_FILE_COUNT=2101
SEARCH_SKIPPED_LARGE_FILE_COUNT=21
PRIVATE_KEY_CANDIDATE_COUNT=17
PARSEABLE_PRIVATE_KEY_COUNT=3

CA_PRIVATE_KEY_MATCH_COUNT=1
CA_PRIVATE_KEY_UID=0
CA_PRIVATE_KEY_GID=0
CA_PRIVATE_KEY_MODE=0600
CA_PRIVATE_KEY_MODE_SAFE=true
CA_PRIVATE_KEY_ROOT_OWNED=true

CA_PRIVATE_KEY_PATH_TOKEN=
cdb208b8dc60893545103e08e6dd2e272c418f1ae6dc1c747e56900a3ef381f5
```

The one-way path token matches the previous KF-100 CA private-key authority probe, proving continuity without publishing the private path.

## H0/H1 System CA

```text
SYSTEM_CA_SHA256_FINGERPRINT=
745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7

SYSTEM_CA_NOT_AFTER=2036-07-30T15:32:24Z
```

The System CA identity remains unchanged.

## Gate interpretation

All prerequisites for a controlled installation-only deployment step are now proven:

- current Broker and TLS authority match the archived production baseline;
- current server certificate and server key match;
- the running Broker process has the intended least-privilege access to the server key;
- the active FC4 CA signing key is unique, root-owned and mode-safe;
- live TLS/8883 is healthy;
- ingress guard and Broker activation are active and persistent;
- lifecycle timer is not active or enabled;
- no unknown lifecycle deployment target exists;
- no T1 mutation occurred during the preflight.

This PASS does not itself install lifecycle source, create lifecycle status state, enable the timer, or exercise certificate renewal.

## Next gate

The next controlled phase is installation-only:

```text
install merged lifecycle executable
install lifecycle systemd service
install lifecycle timer unit
materialize private lifecycle environment
systemctl daemon-reload

DO_NOT_ENABLE_TIMER=true
DO_NOT_START_TIMER=true
DO_NOT_START_AUTO_RENEW_SERVICE=true
DO_NOT_RESTART_BROKER=true
DO_NOT_CHANGE_CERTIFICATES=true
```

After installation-only acceptance, a separate first `audit` invocation may create the lifecycle lock/status files while remaining outside the renewal path.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_INSTALLATION_20260929_01
```
