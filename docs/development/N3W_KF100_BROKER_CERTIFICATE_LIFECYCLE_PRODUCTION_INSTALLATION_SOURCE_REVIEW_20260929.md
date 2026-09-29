# N3-W KF-100 Broker Certificate Lifecycle Production Installation Source Review — 2026-09-29

Status: `SOURCE_REVIEW_PASS_PENDING_CI`  
PR: `#508`  
Installation branch: `exec/n3w-kf100-broker-certificate-lifecycle-production-installation-20260929`  
Reviewed implementation/source-test head: `c88034a7ec957610552841794f39cedcbc22dd38`  
Base main: `bc13f7c21a4441ef06261f69b08cb7937e2ab613`

## Review result

```text
A1_EXACT_SOURCE_BINDING=PASS
A2_FRESH_PREMUTATION_PREFLIGHT=PASS
A3_PRIVATE_ENVIRONMENT_MATERIALIZATION=PASS
A4_INSTALLATION_ONLY_BOUNDARY=PASS
A5_TIMER_DORMANCY=PASS
A6_BROKER_AND_TLS_CONTINUITY=PASS
A7_ROLLBACK=PASS
A7B_POST_REPLACE_FAILURE_BOUNDARY=PASS
A7C_STATUS_DIRECTORY_FAILURE_BOUNDARY=PASS
A8_PUBLIC_SAFE_OUTPUT=PASS
A9_NO_CERTIFICATE_MUTATION=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REVIEW=PASS_PENDING_CI
LIVE_INSTALLATION=false
```

## A1. Exact source binding

The executor accepts only exact Git blob identities for the merged lifecycle tool, service unit, timer unit, and corrected deployment preflight.

A mismatched staged file stops before installation.

## A2. Fresh pre-mutation preflight

The exact corrected deployment preflight is imported and executed immediately before the first write.

Installation therefore cannot rely only on the previous chat-visible PASS. The live Broker/TLS/CA-key/systemd/target-absence facts must still pass at execution time.

## A3. Private environment materialization

The lifecycle environment is generated only on T1.

It references current runtime-resolved server certificate, server key, FC4 CA certificate, unique FC4 CA signing key, System CA, status path, server name, and allowed roots.

Raw private paths are never printed by the executor.

The FC4 CA signing key is additionally required to remain under the active persistent FC4 root; installation refuses to broaden the allowed root to an unrelated private-materialization authority.

## A4. Installation-only boundary

Allowed writes are limited to the lifecycle executable, service unit, timer unit, private environment, and private status directory.

The executor source contains no lifecycle timer/service enable/start/restart operation and no Broker/Docker mutation command.

The only systemd mutation is `daemon-reload`.

## A5. Timer dormancy

Before installation the timer must not already be active/enabled.

After daemon-reload:

- timer must not be active;
- timer must not be enabled;
- lifecycle service must not be active.

Therefore installing the unit files cannot silently activate auto-renewal.

## A6. Broker and TLS continuity

The executor captures Broker container identity/start time and hashes of server certificate, server private key and FC4 CA certificate before writes.

After installation it requires all of them unchanged and performs a verified loopback TLS/8883 fingerprint check.

No Broker restart is part of the gate.

## A7. Rollback

All lifecycle deployment targets were previously proven absent.

If a failure occurs after installation begins, the executor removes only newly created lifecycle files/status authority and performs a second daemon-reload.

Rollback is reported PASS only when cleanup and daemon-reload succeed; otherwise the result remains UNPROVEN.

The implementation additionally closes two partial-mutation edges found during source review:

- if an atomic target replace succeeds but the subsequent parent-directory fsync fails, the just-created target is removed inside the atomic-write helper before the error propagates;
- the status-directory mutation flag is set immediately after mkdir, before owner/mode operations, so a later chown/chmod failure still removes the newly created directory.

Focused host tests cover both boundaries.

## A8. Public-safe output

Success output contains only installation-state booleans, source blob IDs, modes, systemd state and continuity results.

The private environment body and private key paths are not emitted.

## A9. Certificate mutation boundary

The executor does not invoke the lifecycle tool in either audit or auto-renew mode.

It records pre-install hashes and requires the same server certificate, server private key and FC4 CA certificate after installation.

```text
CERTIFICATE_MUTATION=false
BROKER_RESTART=false
TIMER_ENABLEMENT=false
AUTO_RENEW_START=false
```

## Pending closure item

The focused host test suite has been wired into `N3W Broker ingress guard CI`.

Source review can close only after that exact implementation test run completes successfully.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_INSTALLATION_EXECUTION_20260929_01
```
