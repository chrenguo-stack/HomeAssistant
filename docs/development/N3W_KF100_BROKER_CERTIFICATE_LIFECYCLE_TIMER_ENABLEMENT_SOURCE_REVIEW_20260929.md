# N3-W KF-100 Broker Certificate Lifecycle Timer Enablement Source Review — 2026-09-29

Status: `SOURCE_REVIEW_PASS_PENDING_CI`  
Preparation branch: `exec/n3w-kf100-broker-certificate-lifecycle-timer-enablement-preparation-20260929`  
Reviewed source/test head: `e39f5e908843477b4880f727b9acc6058c3578a8`  
Executor Git blob SHA-1: `c39fe418642e12d5b0c8bc7994cd06a443086d33`  
Base main: `9e29cfe2ecd709a0b8e9e824c947aa2a19a45d97`

## Review result

```text
A1_EXACT_INSTALLED_SOURCE_BINDING=PASS
A2_FIRST_AUDIT_STATUS_AUTHORITY=PASS
A3_DISABLED_INACTIVE_PRESTATE=PASS
A4_ENABLE_WITHOUT_NOW=PASS
A5_NO_CURRENT_BOOT_ACTIVATION=PASS
A6_STATUS_NOEXECUTION_ORACLE=PASS
A7_BROKER_TLS_CONTINUITY=PASS
A8_ENABLEMENT_ROLLBACK_BOUNDARY=PASS
A9_NO_CERTIFICATE_MUTATION=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REVIEW=PASS_PENDING_CI
LIVE_TIMER_ENABLEMENT=false
```

## A1. Exact installed source binding

The executor binds the exact production lifecycle executable, service unit and timer unit blobs before mutation. The timer behavior therefore cannot drift from the reviewed `daily + RandomizedDelaySec=1h + Persistent=true` contract.

## A2. First-audit status authority

Enablement is allowed only after the durable first-audit status remains exact HEALTHY/HEALTHY/HEALTHY with the archived certificate identities and no renewal/rollback attempt.

The status directory must contain exactly the reviewed status and lock files, with root-only permissions.

## A3. Disabled/inactive prestate

Before mutation:

```text
timer enabled=disabled
timer active!=active
lifecycle service active!=active
```

Any other enablement state stops before `systemctl enable`.

## A4. Enable without --now

The normal mutation path is an argv-safe call:

```text
systemctl enable n3wfc4-broker-certificate-lifecycle.timer
```

The executor contains no `--now`, start, restart or auto-renew command.

## A5. No current-boot activation

Post-enable acceptance requires:

```text
timer enabled=enabled
timer active!=active
lifecycle service active!=active
```

Therefore this gate establishes persistence only; it does not claim scheduled lifecycle execution in the current boot.

## A6. Status no-execution oracle

The durable status JSON hash is frozen before enablement and must remain byte-identical after enablement.

Because any successful lifecycle CLI invocation writes a fresh `checked_at` status document, an unchanged status hash is a strong independent oracle that enablement did not run the lifecycle service.

## A7. Broker/TLS continuity

The executor proves unchanged Broker container identity/start time, unchanged server certificate/private key/FC4 CA hashes, and the same live TLS server fingerprint after enablement.

## A8. Enablement rollback boundary

If the enable command fails or a postcondition other than unexpected activation fails, the executor issues `systemctl disable` to restore the proven disabled prestate.

If the timer is unexpectedly active, disable alone cannot prove restoration of the inactive prestate. The result therefore becomes `enablement_rollback=UNPROVEN` and live execution must stop for read-only forensic inspection rather than extending authority to a timer stop.

## A9. Certificate mutation boundary

The executor does not invoke the lifecycle CLI or systemd lifecycle service. It does not use the CA signing key for any operation and does not modify certificate/key files.

```text
AUTO_RENEW_INVOCATION=false
BROKER_RESTART=false
CERTIFICATE_MUTATION=false
```

## CI boundary

The timer-enable tests are added to `N3W Broker ingress guard CI`.

Live enablement remains blocked until the exact PR head passes focused and normal repository workflows.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_ENABLEMENT_EXECUTION_20260929_01
```
