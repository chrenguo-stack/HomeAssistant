# N3-W KF-100 Short-Lived Certificate Auto-Renew Lab R2 Execution Result — 2026-09-30

Status: `CLOSED_PASS`  
Base main: `d30c1631fb0be17f8263ded46217666a1f4e8cc7`  
Executor Git blob SHA-1: `c9b156f0f0f51d9a22fb3902fff2ee7c7a0acb22`

## Live execution result

```text
RENEWAL_LAB_R2_RC=0
RESULT=PASS
ISOLATED_LAB=true
LAB_CLEANUP=true
```

The isolated T1 lab completed both the successful renewal path and the forced rollback path.

## Case A — successful automatic renewal

The lab started from a one-day certificate:

```text
INITIAL_NOT_AFTER=Oct 1 00:20:56 2026 GMT
INITIAL_SERVER_STATE=CRITICAL
```

The exact production lifecycle tool then completed a real renewal:

```text
RESULT=PASS
LIFECYCLE_RESULT=renewed
RENEWAL_ATTEMPTED=true
ROLLBACK_ATTEMPTED=false

CERTIFICATE_REPLACED=true
CERTIFICATE_FINGERPRINT_CHANGED=true
SERVER_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true
LIVE_TLS_USES_NEW_CERTIFICATE=true
ACTIVATION_RECREATE_COUNT=1

RENEWED_NOT_AFTER=Jan 2 00:21:01 2029 GMT
```

This proves the short-lived certificate entered the existing production renewal threshold naturally, a new certificate was generated from the existing test server key and test CA, the isolated Broker was re-created to rebind the single-file certificate mount, and the live TLS endpoint presented the new certificate.

## Case B — forced post-renew mismatch and rollback

A second fresh one-day certificate was used:

```text
INITIAL_NOT_AFTER=Oct 1 00:21:08 2026 GMT
INITIAL_SERVER_STATE=CRITICAL
```

The lab deliberately forced the first post-renew activation to present a different valid test certificate.

The production lifecycle tool detected the mismatch and completed the rollback path:

```text
RESULT=PASS
LIFECYCLE_RESULT=renewal_failed_rolled_back
RENEWAL_ATTEMPTED=true
ROLLBACK_ATTEMPTED=true

FORCED_POSTRENEW_MISMATCH=true
ORIGINAL_CERTIFICATE_RESTORED=true
SERVER_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true
LIVE_TLS_RESTORED_TO_ORIGINAL_CERTIFICATE=true
ACTIVATION_RECREATE_COUNT=2

RESTORED_NOT_AFTER=Oct 1 00:21:08 2026 GMT
```

This proves that a post-renew TLS identity failure causes the exact old certificate to be restored and then reactivated successfully.

## Production continuity

The production T1 path remained untouched throughout both cases:

```text
PRODUCTION_CERTIFICATE_MUTATION=false
PRODUCTION_BROKER_RESTART=false
PRODUCTION_STATUS_UNCHANGED=true
PRODUCTION_TIMER_PRESERVED=true
```

The lab used only temporary CA/key/certificate material and isolated temporary Broker containers.

## Disposition

```text
KF100_ROUTE_STATUS=CLOSED_PASS
KF100_REOPEN=false

SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_R2=PASS
SUCCESSFUL_REAL_RENEWAL_PATH=PASS
FORCED_ROLLBACK_PATH=PASS
SINGLE_FILE_BIND_REBIND_MODEL=PASS
LIVE_TLS_NEW_CERTIFICATE_PROOF=PASS
LIVE_TLS_ROLLBACK_PROOF=PASS
PRODUCTION_CONTINUITY=PASS
LAB_CLEANUP=PASS
```

The ordinary Broker server-certificate lifecycle is now proven beyond unit tests:

- autonomous scheduled audit path on production T1;
- real short-lived certificate renewal in an isolated T1 Broker;
- real post-renew live-TLS verification;
- real forced failure and automatic old-certificate rollback;
- no production certificate/Broker/timer mutation during the lab.

FC4 CA rollover remains a separate future lifecycle problem and is not part of KF-100.
