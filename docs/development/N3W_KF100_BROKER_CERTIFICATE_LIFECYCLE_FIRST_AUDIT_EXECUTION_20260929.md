# N3-W KF-100 Broker Certificate Lifecycle First Audit Execution — 2026-09-29

Status: `PREEXECUTION_READY`  
Base main: `6c50ccb7b3f10da4a13fed28dbdfe6418b700ef4`  
Predecessor PR: `#510` merged  
Execution branch: `exec/n3w-kf100-broker-certificate-lifecycle-first-audit-execution-20260929`

## Exact merged authority

```text
FIRST_AUDIT_EXECUTOR=
tools/n3w_broker_certificate_lifecycle_first_audit.py
GIT_BLOB_SHA1=3c800633b557c0b1b22eb3ee5be129b69500c4df

INSTALLED_LIFECYCLE_TOOL_BLOB=
65187b27a2ddd8f57221500a7019486e02bca101
```

PR #510 exact head completed 12/12 PR workflows successfully.

Post-merge push CI at merge commit `6c50ccb7b3f10da4a13fed28dbdfe6418b700ef4`:

```text
N3W Broker ingress guard CI run 36530750854 = PASS
Public repository safety CI run 36530750851 = PASS
```

## Live execution boundary

The executor itself is streamed over SSH and is not persistently installed on T1.

The only intended persistent writes are produced by the already-installed lifecycle CLI in `audit` mode:

```text
/var/lib/n3wfc4-certificate-lifecycle/.certificate-lifecycle.lock
/var/lib/n3wfc4-certificate-lifecycle/status.json
```

Expected ownership/mode:

```text
root:root 0600
```

## Prohibited operations

```text
auto-renew invocation=false
server private-key argument=false
FC4 CA private-key argument=false
lifecycle systemd service start=false
timer enable=false
timer start=false
Broker restart=false
certificate mutation=false
server key mutation=false
CA mutation=false
Manager restart=false
Home Assistant restart=false
```

## Expected result

```text
result=PASS
first_audit=true
audit_rc=0
audit_action=audit
audit_result=ok

server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY

renewal_attempted=false
rollback_attempted=false
certificate_mutation=false
broker_restart=false
timer_enablement=false
timer_start=false
auto_renew_invocation=false
private_key_arguments_used=false

status_written=true
lock_created=true
status_mode=0600
lock_mode=0600

broker_container_continuity=true
broker_started_at_continuity=true
server_certificate_unchanged=true
server_private_key_unchanged=true
ca_certificate_unchanged=true
live_tls_verified=true
```

## Non-replay rule

This is a true first-audit gate.

If the command enters the lifecycle audit and creates status/lock but the wrapper later returns STOP, do not replay blindly. The next step must be read-only forensic inspection of the durable status/lock state.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_AUDIT_EXECUTION_20260929_01
```
