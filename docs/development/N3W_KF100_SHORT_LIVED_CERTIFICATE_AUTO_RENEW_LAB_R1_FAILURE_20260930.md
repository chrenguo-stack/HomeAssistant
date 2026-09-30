# N3-W KF-100 Short-Lived Certificate Auto-Renew Lab R1 Live Failure — 2026-09-30

Status: `LAB_HARNESS_FAILURE_PRODUCTION_PRESERVED`

## Live result

The first isolated short-lived renewal lab execution stopped during the success-path case.

```text
KF100_RENEWAL_LAB stage=production_preflight
KF100_RENEWAL_LAB stage=prepare_isolated_lab
KF100_RENEWAL_LAB stage=success_path

result=STOP
reason=tls_probe_failed
production_preserved=true
production_certificate_mutation=false
production_broker_restart=false
RENEWAL_LAB_RC=2
```

The local macOS shell-session warning occurred after the remote return code and is unrelated to T1.

## What this does and does not prove

The R1 result does not prove a production renewal defect.

The isolated Broker passed its initial TLS readiness check before the production lifecycle tool was invoked. The generic `tls_probe_failed` surfaced only after the lifecycle run had returned.

R1 then performed its final live-TLS probe before classifying and reporting the lifecycle tool's own result. This hid whether the exact lifecycle tool had:

- renewed successfully;
- entered rollback;
- or failed activation/post-renew verification.

R1 also mapped the production activation-unit restart to a plain `docker restart` of the isolated lab container. That was not a strong enough model for the single-file bind replacement hazard the production design is intended to handle.

Therefore:

```text
PRODUCT_DEFECT_CONFIRMED=false
PRODUCTION_STATE_PRESERVED=true
LAB_HARNESS_R1=FAIL
R1_REPLAY_AUTHORIZED=false
```

A repaired, source-bound R2 is required before another live lab attempt.
