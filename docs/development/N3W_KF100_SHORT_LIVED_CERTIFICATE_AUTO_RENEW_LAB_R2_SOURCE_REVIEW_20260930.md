# N3-W KF-100 Short-Lived Certificate Auto-Renew Lab R2 Source Review — 2026-09-30

Status: `SOURCE_REVIEW_PASS_PENDING_CI`  
Branch: `fix/n3w-kf100-short-lived-renewal-lab-r2-20260930`  
Executor Git blob SHA-1: `c9b156f0f0f51d9a22fb3902fff2ee7c7a0acb22`

## R1 defect disposition

R1 stopped with `tls_probe_failed` after entering the success-path case. Production continuity remained proven.

R2 treats this as a harness/oracle defect unless and until the exact lifecycle result proves otherwise.

## R2 repairs

### 1. Do not hide the lifecycle result

R2 parses the exact lifecycle program result first.

If its return code or result is unexpected, the public-safe STOP output now includes:

```text
lifecycle_rc
lifecycle_result
renewal_attempted
rollback_attempted
```

before any final external TLS acceptance check.

### 2. Recreate the isolated Broker on activation

R1 used plain `docker restart`.

R2 removes and recreates only the uniquely named lab container using the same frozen run arguments and fixed loopback host port.

This forces the isolated single-file bind mounts to be rebound to the current host paths after atomic certificate replacement.

It does not touch the production Broker or production activation unit.

### 3. Wait for TLS identity, not only TCP readiness

The private `systemctl` shim now waits until:

```text
live isolated TLS fingerprint
==
current isolated server.pem fingerprint
```

before returning success to the lifecycle program.

This removes the R1 race where raw TCP readiness could be observed before the TLS endpoint had fully converged.

### 4. Preserve forced rollback semantics

In the forced-mismatch case, the first activation recreation substitutes a different valid test certificate.

The lifecycle program must detect that mismatch, restore the original certificate, invoke activation again, and R2 then recreates the isolated Broker a second time from the restored host path.

### 5. Production guard unchanged

PASS remains blocked on exact before/after continuity of:

- production Broker container and StartedAt;
- production server certificate hash;
- production server-key hash;
- production FC4 CA hash;
- production lifecycle status hash;
- production timer enabled/active state;
- production live TLS certificate.

## Review result

```text
R1_PRODUCTION_PRESERVED=true
R1_PRODUCT_DEFECT_CONFIRMED=false
R1_REPLAY=false

R2_LIFECYCLE_RESULT_OBSERVABILITY=PASS
R2_SINGLE_FILE_BIND_RECREATE_MODEL=PASS
R2_TLS_READINESS_ORACLE=PASS
R2_FORCED_ROLLBACK_MODEL=PASS
R2_PRODUCTION_ISOLATION=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REVIEW=PASS_PENDING_CI

NEXT_ONE_GATE=N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_R2_EXECUTION_20260930_01
```
