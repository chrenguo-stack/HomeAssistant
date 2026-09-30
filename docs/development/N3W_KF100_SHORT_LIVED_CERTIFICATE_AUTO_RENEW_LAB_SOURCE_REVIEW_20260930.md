# N3-W KF-100 Short-Lived Certificate Auto-Renew Lab Source Review — 2026-09-30

Status: `SOURCE_REVIEW_PASS_PENDING_CI`  
Branch: `lab/n3w-kf100-short-lived-certificate-auto-renew-20260930`  
Reviewed source/test head: `49497128e451a5d1648cabba4427227a8bb087fb`  
Executor Git blob SHA-1: `16c1d1f3afedf18580a1096e92357f62380f2a53`

## Review result

```text
A1_PRODUCTION_LIFECYCLE_SOURCE_EXACT=PASS
A2_PRODUCTION_TLS_ISOLATION=PASS
A3_SHORT_LIVED_REAL_CERT_TRIGGER=PASS
A4_SUCCESSFUL_RENEWAL_PATH=PASS
A5_LIVE_TLS_NEW_CERTIFICATE_PROOF=PASS
A6_FORCED_ROLLBACK_PATH=PASS
A7_PRODUCTION_STATE_CONTINUITY_GUARD=PASS
A8_TEMPORARY_SECRET_CLEANUP=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REVIEW=PASS_PENDING_CI
LIVE_LAB=false
```

## A1. Exact production lifecycle source

The lab does not copy or reimplement renewal logic.

It first verifies the installed production lifecycle executable against exact Git blob:

```text
65187b27a2ddd8f57221500a7019486e02bca101
```

and then invokes that executable in `auto-renew` mode.

## A2. Production TLS isolation

The lab creates independent TLS material and an independent Broker container.

The endpoint is bound only to `127.0.0.1` on a dynamically allocated host port.

Production 8883 and production TLS files are read only for before/after continuity proof.

## A3. Real short-lived certificate trigger

The initial lab server certificate has one-day validity.

This enters the existing production `CRITICAL` threshold naturally.

No clock manipulation and no production threshold modification are used.

## A4. Successful renewal path

PASS requires the exact lifecycle tool to return:

```text
result=renewed
action=renew_server_certificate
renewal_attempted=true
rollback_attempted=false
server_state=HEALTHY
```

The new certificate must differ from the one-day certificate and have extended validity.

## A5. Live TLS proof

The isolated live TLS endpoint must present the same fingerprint as the newly written certificate after the activation restart.

Therefore the test is not satisfied by file replacement alone.

## A6. Forced rollback path

The second case deliberately causes the live endpoint to present a different valid certificate after replacement.

PASS requires the lifecycle tool to detect the mismatch, restore the original certificate and return:

```text
result=renewal_failed_rolled_back
renewal_attempted=true
rollback_attempted=true
```

The restored file fingerprint and live TLS fingerprint must both equal the original pre-renew fingerprint.

## A7. Production continuity

PASS is blocked if any of the following changes:

- production Broker container;
- production Broker StartedAt;
- production server certificate hash;
- production server private-key hash;
- production FC4 CA hash;
- production lifecycle status hash;
- production timer enabled/active state;
- production live TLS fingerprint.

The lab does not invoke production timer/service mutation commands.

## A8. Cleanup

Each lab container is force-removed at the end of its case.

The temporary lab tree under `/var/tmp` is deleted in the executor's final cleanup path.

The test private keys are intentionally ephemeral and never become production authorities.

## Execution boundary

Live execution remains blocked until the exact branch head passes focused CI and repository CI.

```text
NEXT_ONE_GATE=N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_EXECUTION_20260930_01
```
