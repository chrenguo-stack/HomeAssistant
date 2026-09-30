# N3-W KF-100 Short-Lived Certificate Auto-Renew Lab Execution — 2026-09-30

Status: `PREEXECUTION_READY`  
Base main: `1411fc5a283482fd1e3930249d157fd5d3582f0a`  
Predecessor PR: `#518` merged  
Execution branch: `exec/n3w-kf100-short-lived-certificate-auto-renew-lab-execution-20260930`

## Exact merged authority

```text
LAB_EXECUTOR=
tools/n3w_kf100_short_lived_certificate_auto_renew_lab.py

LAB_EXECUTOR_GIT_BLOB_SHA1=
16c1d1f3afedf18580a1096e92357f62380f2a53

PRODUCTION_LIFECYCLE_TOOL_GIT_BLOB_SHA1=
65187b27a2ddd8f57221500a7019486e02bca101
```

PR #518 exact head `afa6055b4a37d6599a9d4640219b530c050f1b49` completed all 12 PR workflows successfully before merge.

Post-merge main:

```text
1411fc5a283482fd1e3930249d157fd5d3582f0a
```

Post-merge push CI at preparation time:

```text
Public repository safety CI run 36651016649 = PASS
N3W Broker ingress guard CI run 36651016650 = PASS
```

Both post-merge checks are PASS. Live lab execution is now released.

## Lab boundary

The lab runs on T1 but does not replace any production TLS file.

It creates:

- temporary CA;
- temporary server key;
- one-day temporary server certificate;
- isolated temporary Broker container;
- loopback-only dynamic port;
- temporary lifecycle status.

The exact installed production lifecycle executable is used against the temporary material.

## Cases

```text
CASE_A=SUCCESSFUL_AUTO_RENEW
CASE_B=FORCED_POSTRENEW_MISMATCH_AND_ROLLBACK
```

CASE_A must prove:

```text
result=renewed
renewal_attempted=true
rollback_attempted=false
certificate_replaced=true
server_key_unchanged=true
ca_certificate_unchanged=true
live_tls_uses_new_certificate=true
```

CASE_B must prove:

```text
result=renewal_failed_rolled_back
renewal_attempted=true
rollback_attempted=true
original_certificate_restored=true
server_key_unchanged=true
ca_certificate_unchanged=true
live_tls_restored_to_original_certificate=true
```

## Production continuity

PASS additionally requires:

```text
production_certificate_mutation=false
production_broker_restart=false
production_status_unchanged=true
production_timer_preserved=true
lab_cleanup=true
```

The production Broker identity/start time, production certificate/key/CA hashes, production status hash, production timer enabled/active state and live production TLS identity are frozen before the lab and rechecked after both cases.

## Failure handling

A STOP is not replay authorization.

If the result is STOP, return the complete output and inspect the reported reason and `production_preserved` field before any retry.

```text
NEXT_ONE_GATE=N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_EXECUTION_20260930_01
```
