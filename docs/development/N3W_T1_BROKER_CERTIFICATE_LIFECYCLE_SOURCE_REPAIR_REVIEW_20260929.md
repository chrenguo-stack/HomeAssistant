# N3-W T1 Broker Certificate Lifecycle Source Repair Review — 2026-09-29

Status: `SOURCE_REPAIR_REVIEW_PASS`  
PR: `#506`  
Repair branch: `fix/n3w-t1-broker-certificate-lifecycle-20260929`  
Exact reviewed source/test head: `e3d51c7de58e66c772443202e7bd290a047302c3`  
Branch base: `main=60c05ada52c48a58243f666b3e631fd228c53df4`

## Review result

```text
A1_EXPIRY_CLASSIFICATION=PASS
A2_CURRENT_CERTIFICATE_TRUST_BINDING=PASS
A3_EXPIRED_CERTIFICATE_RECOVERY_BOUNDARY=PASS
A4_SIGNING_AUTHORITY_VALIDATION=PASS
A5_CANDIDATE_CERTIFICATE_CONTRACT=PASS
A6_SINGLE_FILE_BIND_ACTIVATION=PASS
A7_POST_ACTIVATION_TLS_PROOF=PASS
A8_ROLLBACK_AND_UNKNOWN_PROPAGATION=PASS
A9_PRIVATE_PATH_AND_SECRET_BOUNDARY=PASS
A10_SYSTEMD_TIMER_AND_OWNER_BOUNDARY=PASS
A11_CA_ROLLOVER_SCOPE_SEPARATION=PASS
A12_REGRESSION_COVERAGE=PASS

SOURCE_REVIEW_BLOCKER_COUNT=0
SOURCE_REPAIR_REVIEW=PASS
LIVE_T1_MUTATION=false
```

## Source repair inventory

The repair adds:

```text
tools/n3w_broker_certificate_lifecycle.py
tests/tools/test_n3w_broker_certificate_lifecycle.py

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.service
infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer
infra/n3w-t1/broker-certificate-lifecycle.env.example
```

and updates:

```text
infra/n3w-t1/install-systemd-persistence.sh
infra/n3w-t1/README.md
.github/workflows/n3w-broker-ingress-guard-ci.yml
```

The runtime baseline, repair design and design review are separately archived under `docs/development/`.

## A1. Expiry classification

The source freezes deterministic server states:

```text
>90 days      HEALTHY
<=90 days     WARNING
<=60 days     RENEW_DUE
<=30 days     CRITICAL
<=0           EXPIRED
```

FC4 CA and optional H0/H1 System CA use long-horizon `WARNING/CRITICAL/EXPIRED` monitoring. CA replacement is never performed by this tool.

## A2. Current certificate trust binding

Before a renewal is permitted, the stored server certificate must:

- parse as a non-CA certificate;
- contain the configured DNS SAN;
- verify against the configured FC4 CA and TLS server name with time checking disabled;
- additionally pass normal time-valid verification while it is not expired.

The active FC4 CA must parse as a CA certificate.

## A3. Expired-certificate recovery boundary

The implementation does not make a long powered-off interval permanently unrecoverable.

For an expired old server certificate, no-check-time verification is used only to prove unchanged CA/hostname identity before renewal. The running endpoint must still present the exact expected old certificate fingerprint.

Every newly issued certificate must pass full normal CA + hostname + time verification.

## A4. Signing authority validation

Renewal reads private keys only after the server reaches a renewal state.

Before signing:

- server certificate/public key must match the configured server private key;
- FC4 CA certificate/public key must match the configured CA private key;
- private-key files may not be group/other accessible;
- material must remain inside explicitly allowed roots;
- symlink path components are rejected;
- CA remaining lifetime must cover the full new 825-day certificate plus the frozen 90-day safety margin.

No unmanaged OpenSSL serial side file is used. Each candidate gets an explicit random positive serial.

## A5. Candidate certificate contract

V1 deliberately reuses the existing server private key.

The candidate is generated in a private same-filesystem workspace and requires:

```text
basicConstraints=CA:FALSE
extendedKeyUsage=serverAuth
SAN DNS=<configured TLS server name>
SHA-256 signature
validity <= 825 days
same FC4 CA
same server public key
```

Candidate verification completes before the active certificate pathname is touched.

## A6. Single-file bind activation

The repair correctly treats the current Broker TLS files as single-file Docker bind mounts.

The sequence is:

```text
candidate validate
→ candidate fsync
→ atomic host-path replace
→ parent-directory fsync
→ restart existing n3wfc4-broker-activation.service
```

The mutation flag is set immediately after successful `os.replace`, before directory fsync, so any failure after pathname replacement enters rollback rather than being misclassified as pre-mutation failure.

Manager and Home Assistant are not restarted.

## A7. Post-activation TLS proof

The post-renewal probe uses an SSL context loaded with the exact configured FC4 CA and normal hostname/time verification. Success additionally requires that the endpoint DER SHA-256 fingerprint equals the candidate certificate fingerprint.

The active host certificate is then re-read and must match both the candidate fingerprint and candidate expiration.

## A8. Rollback and UNKNOWN propagation

Any failure after active-path replacement triggers:

```text
restore exact old certificate bytes + mode/uid/gid
→ restart existing Broker activation owner
→ bind endpoint to old fingerprint
→ normal verified TLS proof when old certificate is still time-valid
```

A successful rollback is reported as a failed renewal, not a successful renewal.

If rollback restart or endpoint proof cannot be established, result remains `rollback_unproven`; private recovery workspace is preserved and no recovery claim is made.

## A9. Private-path and secret boundary

Durable status contains only normalized lifecycle fields, timestamps, remaining seconds and SHA-256 certificate fingerprints.

It does not contain:

- certificate PEM bodies;
- private-key material;
- MQTT credentials;
- raw private paths;
- private network locators;
- raw system-private identifiers;
- raw OpenSSL/subprocess stderr.

Errors are reduced to stable reason codes.

## A10. systemd ownership

The new lifecycle service is `Type=oneshot`; it does not use `Restart=always`.

The timer uses:

```text
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true
```

The service is ordered after Docker, the ingress guard and the existing Broker activation owner. It uses the existing activation unit for the only Broker restart needed by ordinary renewal.

The persistence installer enables the lifecycle timer together with the two existing units but still does not use `enable --now`, `start` or `restart`.

## A11. CA rollover separation

The tool monitors FC4 CA and System CA expiration but cannot automatically replace either trust root.

This preserves the required future dual-trust migration boundary for already-paired nodes. Ordinary server-certificate renewal therefore does not change node CA trust and does not require re-pairing.

## A12. Regression coverage and CI

The focused host tests cover, among other cases:

- healthy/warning no-mutation paths;
- renewal and critical thresholds;
- CA-lifetime refusal;
- hostname mismatch;
- symlink/material safety;
- unsafe private-key permissions;
- wrong server key;
- wrong CA key;
- real OpenSSL candidate issuance and validation;
- successful same-key renewal;
- post-activation failure rollback;
- rollback restart failure / `rollback_unproven`;
- explicit-serial behavior with no `.srl` file;
- public-safe status;
- System CA monitor-only behavior;
- expired old-certificate no-check-time boundary;
- failure after active `os.replace` entering rollback;
- systemd timer/service/installer contract;
- existing ingress-guard/activation ordering.

At exact source/test head `e3d51c7de58e66c772443202e7bd290a047302c3`:

```text
N3W_BROKER_INGRESS_GUARD_CI_RUN=36516146163
N3W_BROKER_INGRESS_GUARD_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI_RUN=36516146186
PUBLIC_REPOSITORY_SAFETY_CI=PASS
ALL_PR_WORKFLOW_RUNS_AT_REVIEW_HEAD=12_OF_12_PASS
```

The N3-W CI job executed the existing ingress-guard/lifecycle/Mosquitto repair tests plus the new certificate lifecycle test module.

## Remaining live prerequisite

The source repair intentionally does not guess the current FC4 CA private-key location.

```text
CURRENT_FC4_CA_CERTIFICATE_AUTHORITY=PROVEN
CURRENT_FC4_CA_PRIVATE_KEY_RUNTIME_AUTHORITY=UNPROVEN
SOURCE_REPAIR_BLOCKED_BY_THIS=false
LIVE_TIMER_ENABLEMENT_BLOCKED_BY_THIS=true
```

Before any production timer installation/enablement or live renewal exercise, a separate read-only live preflight must prove the exact FC4 CA private-key authority, permissions, cert/key match and rollback authority.

## Disposition

```text
KF100_SOURCE_REPAIR=PASS
KF100_SOURCE_TESTS=PASS
KF100_SOURCE_REVIEW=PASS
KF100_LIVE_ACTIVATION=NOT_PERFORMED
KF100_KNOWN_FAILURE_STATUS=OPEN
PR506_STATE=DRAFT

NEXT_ONE_GATE=N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_SOURCE_ALIGNMENT_20260929_01
```
