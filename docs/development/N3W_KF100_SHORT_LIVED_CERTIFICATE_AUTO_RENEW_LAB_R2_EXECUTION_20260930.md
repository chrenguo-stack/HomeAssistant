# N3-W KF-100 Short-Lived Certificate Auto-Renew Lab R2 Execution — 2026-09-30

Status: `PREEXECUTION_READY`  
Base main: `d30c1631fb0be17f8263ded46217666a1f4e8cc7`  
Predecessor PR: `#519` merged  
Execution branch: `exec/n3w-kf100-short-lived-certificate-auto-renew-lab-r2-execution-20260930`

## Exact merged authority

```text
LAB_EXECUTOR=
tools/n3w_kf100_short_lived_certificate_auto_renew_lab.py

LAB_EXECUTOR_GIT_BLOB_SHA1=
c9b156f0f0f51d9a22fb3902fff2ee7c7a0acb22

PRODUCTION_LIFECYCLE_TOOL_GIT_BLOB_SHA1=
65187b27a2ddd8f57221500a7019486e02bca101
```

PR #519 exact head `a6b64ef5c4c931bd709e37f7d1840b0e636fe0aa` completed all 12 PR workflows successfully before merge.

Post-merge main:

```text
d30c1631fb0be17f8263ded46217666a1f4e8cc7
```

Post-merge push CI at preparation time:

```text
Public repository safety CI run 36651818583 = PASS
N3W Broker ingress guard CI run 36651818625 = PASS
```

Both post-merge checks are PASS. Live R2 execution is now released.

## R2 lab boundary

The lab runs only against isolated temporary TLS material and isolated temporary Broker containers.

Normal production state must remain unchanged:

```text
production_certificate_mutation=false
production_broker_restart=false
production_status_unchanged=true
production_timer_preserved=true
```

## R2 repairs over R1

R2:

1. reports lifecycle result fields before final TLS acceptance;
2. recreates only the isolated test Broker after atomic certificate replacement so single-file binds are rebound;
3. waits for the isolated live TLS fingerprint to equal the current test certificate fingerprint before activation success;
4. preserves the forced rollback case.

## Expected success case

```text
result=PASS
lifecycle_result=renewed
renewal_attempted=true
rollback_attempted=false
certificate_replaced=true
certificate_fingerprint_changed=true
server_key_unchanged=true
ca_certificate_unchanged=true
live_tls_uses_new_certificate=true
activation_recreate_count=1
```

## Expected rollback case

```text
result=PASS
lifecycle_result=renewal_failed_rolled_back
renewal_attempted=true
rollback_attempted=true
forced_postrenew_mismatch=true
original_certificate_restored=true
server_key_unchanged=true
ca_certificate_unchanged=true
live_tls_restored_to_original_certificate=true
activation_recreate_count=2
```

## Failure handling

Any STOP is a stop point. Do not replay without source review.

R2 may emit public-safe diagnostic fields:

```text
lifecycle_rc
lifecycle_result
renewal_attempted
rollback_attempted
```

to distinguish lifecycle behavior from the surrounding lab harness.

```text
NEXT_ONE_GATE=N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_R2_EXECUTION_20260930_01
```
