# N3-W KF-100 Broker Certificate Lifecycle Production Installation Execution Result — 2026-09-29

Status: `CLOSED_PASS`  
Execution branch: `exec/n3w-kf100-broker-certificate-lifecycle-production-installation-execution-20260929`  
Merged source authority: `d066ddbd00fa7efbfcf677f1630c6a73bc8cf4e8`

## Result

The production installation-only gate completed successfully.

```text
PREINSTALL_PREFLIGHT_RC=0
INSTALL_RC=0
INSTALL_PIPELINE_RC=0

RESULT=PASS
INSTALLATION_ONLY=true
CERTIFICATE_MUTATION=false
BROKER_RESTART=false
TIMER_ENABLEMENT=false
TIMER_START=false
AUTO_RENEW_START=false
DAEMON_RELOAD=true
```

## Fresh pre-install read-only rebind

Immediately before installation, the exact deployment preflight passed again:

```text
BROKER_RUNNING=true
LIVE_TLS_VERIFIED=true
LIVE_TLS_FINGERPRINT_MATCH=true
SERVER_CERTIFICATE_KEY_MATCH=true

BROKER_EFFECTIVE_UID_GID=1883:1883
SERVER_KEY_UID_GID=1883:1883
SERVER_KEY_MODE=0600
SERVER_KEY_OWNER_MATCHES_BROKER=true

CA_PRIVATE_KEY_MATCH_COUNT=1
CA_PRIVATE_KEY_UID_GID=0:0
CA_PRIVATE_KEY_MODE=0600
CA_PRIVATE_KEY_ROOT_OWNED=true

INGRESS_GUARD_ACTIVE=active
INGRESS_GUARD_ENABLED=enabled
BROKER_ACTIVATION_ACTIVE=active
BROKER_ACTIVATION_ENABLED=enabled

LIFECYCLE_TIMER_ACTIVE=inactive
LIFECYCLE_TIMER_ENABLED=not-found
DEPLOYMENT_TARGET_PRESENT_COUNT=0
```

No persistent lifecycle installation write began until this fresh preflight returned PASS.

## Installed production authority

The executor installed the exact merged source artifacts:

```text
LIFECYCLE_TOOL_INSTALLED=true
LIFECYCLE_TOOL_BLOB=65187b27a2ddd8f57221500a7019486e02bca101

LIFECYCLE_SERVICE_INSTALLED=true
LIFECYCLE_SERVICE_BLOB=fa13967ef0ffb0a271fcb7122febd83b83079deb

LIFECYCLE_TIMER_INSTALLED=true
LIFECYCLE_TIMER_BLOB=65b0365c5ea5f5d3c896a133adc0d689bb2deced

LIFECYCLE_ENVIRONMENT_INSTALLED=true
ENVIRONMENT_MODE=0600

STATUS_AUTHORITY_CREATED=true
STATUS_DIRECTORY_MODE=0700
```

The private environment was materialized locally on T1 and its private path values were not emitted into public evidence.

## Post-install dormancy

After `systemctl daemon-reload`:

```text
LIFECYCLE_SERVICE_ACTIVE=inactive
LIFECYCLE_TIMER_ACTIVE=inactive
LIFECYCLE_TIMER_ENABLED=disabled
```

Therefore installation did not activate automatic renewal.

## Broker and TLS continuity

The executor proved:

```text
BROKER_CONTAINER_CONTINUITY=true
BROKER_STARTED_AT_CONTINUITY=true

SERVER_CERTIFICATE_UNCHANGED=true
SERVER_PRIVATE_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true

LIVE_TLS_VERIFIED=true
```

No Broker restart or certificate/key mutation occurred.

## Non-blocking terminal warnings

The transport tar command printed future-timestamp warnings for staged files. They were caused by clock/mtime skew between the Mac-created staging files and T1 extraction time. They did not alter blob verification, installation result, or runtime continuity.

The local macOS shell-session helper also printed a post-command history-save warning after the pipeline had already returned `INSTALL_PIPELINE_RC=0`. It is outside the T1 execution path and does not change the installation result.

## Gate closure

```text
KF100_PRODUCTION_INSTALLATION=PASS
LIFECYCLE_SOURCE_INSTALLED=true
LIFECYCLE_AUTOMATION_ACTIVE=false
CERTIFICATE_MUTATION=false
BROKER_RESTART=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_AUDIT_PREPARATION_20260929_01
```

The next gate is the first explicit audit-only invocation. That gate may create the lifecycle lock/status files, but must not enter renewal or restart the Broker.
