# N3-W KF-100 Broker Certificate Lifecycle Production Installation Execution — 2026-09-29

Status: `PREEXECUTION_READY`  
Base main: `d066ddbd00fa7efbfcf677f1630c6a73bc8cf4e8`  
Predecessor PR: `#508` merged  
Execution branch: `exec/n3w-kf100-broker-certificate-lifecycle-production-installation-execution-20260929`

## Exact merged source authority

```text
tools/n3w_broker_certificate_lifecycle.py
blob=65187b27a2ddd8f57221500a7019486e02bca101

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.service
blob=fa13967ef0ffb0a271fcb7122febd83b83079deb

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer
blob=65b0365c5ea5f5d3c896a133adc0d689bb2deced

tools/n3w_broker_certificate_lifecycle_deployment_preflight.py
blob=8f3a09fee5cdad1d60dd76406e3dd03c7aa510ed

tools/n3w_broker_certificate_lifecycle_install.py
blob=6035008c539253b9951a7097d2a2aee9fa52b83a
```

Post-merge push CI at merge commit `d066ddbd00fa7efbfcf677f1630c6a73bc8cf4e8`:

```text
N3W Broker ingress guard CI run 36528019139 = PASS
Public repository safety CI run 36528019137 = PASS
```

## Execution transport

The operator Mac downloads and verifies the exact merged source blobs first.

Before any T1 staging write, the exact deployment preflight is streamed directly to `python3 -` over SSH and must return PASS.

Only after that zero-write live PASS, the exact merged source package is staged under a private temporary directory in `/run` on T1. The installation executor then re-runs the exact deployment preflight again before the first persistent lifecycle installation write.

The temporary `/run` staging directory is execution transport only and is removed at command exit.

## Allowed persistent mutation

```text
/usr/local/sbin/n3w-broker-certificate-lifecycle
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
/etc/n3wfc4/broker-certificate-lifecycle.env
/var/lib/n3wfc4-certificate-lifecycle/

systemctl daemon-reload
```

## Forbidden action

```text
timer enable=false
timer start=false
lifecycle service start=false
auto-renew invocation=false
Broker restart=false
certificate mutation=false
server key mutation=false
FC4 CA mutation=false
Manager restart=false
Home Assistant restart=false
node re-pairing=false
```

## Expected PASS evidence

```text
result=PASS
installation_only=true
certificate_mutation=false
broker_restart=false
timer_enablement=false
timer_start=false
auto_renew_start=false
daemon_reload=true

lifecycle_tool_installed=true
lifecycle_service_installed=true
lifecycle_timer_installed=true
lifecycle_environment_installed=true
status_authority_created=true

timer_active != active
timer_enabled != enabled
service_active != active

broker_container_continuity=true
broker_started_at_continuity=true
server_certificate_unchanged=true
server_private_key_unchanged=true
ca_certificate_unchanged=true
live_tls_verified=true
```

## Stop rule

Any STOP or nonzero exit is returned before proceeding to the audit gate.

A failed install must report either:

```text
installation_rollback=PASS
```

or:

```text
installation_rollback=UNPROVEN
```

The latter requires read-only forensic inspection before any retry.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_INSTALLATION_EXECUTION_20260929_01
```
