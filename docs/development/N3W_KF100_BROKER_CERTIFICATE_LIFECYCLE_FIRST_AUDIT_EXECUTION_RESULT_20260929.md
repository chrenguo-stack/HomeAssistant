# N3-W KF-100 Broker Certificate Lifecycle First Audit Execution Result — 2026-09-29

Status: `CLOSED_PASS`  
Execution branch: `exec/n3w-kf100-broker-certificate-lifecycle-first-audit-execution-20260929`  
Merged source authority: `6c50ccb7b3f10da4a13fed28dbdfe6418b700ef4`

## Result

The first explicit production lifecycle audit completed successfully.

```text
FIRST_AUDIT_RC=0
RESULT=PASS

FIRST_AUDIT=true
AUDIT_RC=0
AUDIT_ACTION=audit
AUDIT_RESULT=ok
```

## Lifecycle health state

```text
SERVER_STATE=HEALTHY
CA_STATE=HEALTHY
SYSTEM_CA_STATE=HEALTHY

SERVER_SHA256_FINGERPRINT=
8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb

FC4_CA_SHA256_FINGERPRINT=
b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351

SYSTEM_CA_SHA256_FINGERPRINT=
745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7
```

The first audit observed the expected current healthy certificate state and did not enter warning, renewal, critical, or expired handling.

## Renewal boundary

```text
RENEWAL_ATTEMPTED=false
ROLLBACK_ATTEMPTED=false
AUTO_RENEW_INVOCATION=false
PRIVATE_KEY_ARGUMENTS_USED=false

CERTIFICATE_MUTATION=false
BROKER_RESTART=false
TIMER_ENABLEMENT=false
TIMER_START=false
```

The first audit therefore proved the audit-only path remains separated from the renewal path.

## Durable lifecycle status authority

The audit created the first durable lifecycle status authority:

```text
STATUS_WRITTEN=true
LOCK_CREATED=true

STATUS_MODE=0600
LOCK_MODE=0600
```

The first-audit executor verified that the durable status JSON matched the CLI output and contained no raw private paths, PEM certificate content, or PEM private-key content.

## Broker and TLS continuity

```text
BROKER_CONTAINER_CONTINUITY=true
BROKER_STARTED_AT_CONTINUITY=true

SERVER_CERTIFICATE_UNCHANGED=true
SERVER_PRIVATE_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true

LIVE_TLS_VERIFIED=true
```

No Broker restart or TLS material change occurred.

## Non-blocking local shell warning

After `FIRST_AUDIT_RC=0`, the macOS shell-session helper printed:

```text
shell_session_save:9: shell_session_save_user_state_functions: parameter not set
```

This occurred after the remote first-audit execution had completed and returned success. It is local terminal history/session-save behavior and does not change the T1 audit result.

## Gate closure

```text
KF100_FIRST_AUDIT=PASS
LIFECYCLE_DURABLE_STATUS_AUTHORITY=ESTABLISHED
LIFECYCLE_AUTOMATION_ACTIVE=false

CERTIFICATE_MUTATION=false
BROKER_RESTART=false
TIMER_ENABLEMENT=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_ENABLEMENT_PREPARATION_20260929_01
```

The next gate is timer enablement preparation. Enabling the timer remains a separate production mutation and must preserve the no-`--now` boundary so that enablement does not immediately invoke lifecycle renewal logic.
