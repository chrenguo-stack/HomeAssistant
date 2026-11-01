# N3-W FC4 CA Rollover Product-Lifecycle Decision — 2026-09-30

Status: `CLOSED_NOT_PLANNED`  
Decision type: product-lifecycle scope closure  
Base main: `d50a991d9fc8368d31de8bf07f310edc64425e02`

## 1. Decision

The FC4 private CA rollover / migration workstream is closed and is not planned for this product generation.

```text
FC4_CA_ROLLOVER_WORKSTREAM=CLOSED_NOT_PLANNED
FC4_CA_DUAL_TRUST_MIGRATION=NOT_IMPLEMENTED
FC4_CA_PRODUCTION_REPLACEMENT=NOT_PLANNED
KF100_REOPEN=false
```

## 2. Product-lifecycle basis

The currently active FC4 private CA has the confirmed production lifetime:

```text
FC4_PRIVATE_CA_NOT_BEFORE=2026-08-20T04:18:39Z
FC4_PRIVATE_CA_NOT_AFTER=2036-08-17T04:18:39Z
FC4_PRIVATE_CA_VALIDITY_DAYS=3650
```

The product decision is that this product generation will be retired before that CA lifetime is exhausted. A normal age-based FC4 CA rollover would therefore occur outside the supported product service life.

Accordingly, the project will not spend current engineering scope on:

- dual-root FC4 CA trust;
- FC4 CA trust-generation / acknowledgement protocol;
- active-node CA migration orchestration;
- Broker cutover from FC4 CA V1 to a future FC4 CA V2;
- normal end-of-life FC4 CA retirement tooling.

## 3. What remains in force

This decision does not change the already completed Broker server-certificate lifecycle.

The existing KF-100 implementation remains authoritative:

- daily expiry audit;
- server-certificate warning / renewal / critical thresholds;
- automatic same-FC4-CA server-certificate renewal;
- same Broker server private key for ordinary V1 renewal;
- Broker activation/recreate after single-file certificate replacement;
- live TLS verification;
- automatic old-server-certificate rollback when post-renew verification fails.

The 2026-09-30 isolated T1 lab already proved both the real server-certificate renewal path and the forced rollback path.

## 4. Monitoring behavior

The FC4 CA remains monitored for expiry state, but monitoring does not imply a planned rollover implementation.

Normal expected disposition for this product generation:

```text
FC4_CA_EXPIRY_MONITORING=ENABLED
FC4_CA_ROLLOVER_AUTOMATION=DISABLED_BY_DESIGN
FC4_CA_ROLLOVER_PROJECT_WORKSTREAM=CLOSED_NOT_PLANNED
```

## 5. Reopen conditions

This closure is based on the current product-lifecycle assumption. The FC4 CA rollover workstream must be reopened only if at least one of the following becomes true:

1. the supported product service life is extended close to or beyond the FC4 CA expiry;
2. deployed units are intentionally refurbished/reused beyond the current product life;
3. the FC4 CA private key is lost, exposed, suspected compromised, or otherwise can no longer be trusted;
4. certificate-policy/security requirements force an earlier CA replacement;
5. the currently deployed FC4 CA must be replaced for a non-age-related operational reason.

A CA compromise or loss is an exceptional security-recovery event and is not covered by the normal age-based closure.

## 6. Scope separation

The H0/H1 System CA remains a distinct authority and is not automatically closed by this FC4 CA decision.

This decision also does not change:

- NODE_ID lifecycle;
- MQTT credentials;
- Dynamic Security identity/ACL;
- N3-W application keys;
- SYSTEM_PEER_KEY;
- pairing/recovery authorization;
- Broker hostname / TLS server-name policy.

## 7. Final disposition

```text
FC4_CA_CURRENT_RUNTIME=HEALTHY
FC4_CA_EXPIRES=2036-08-17T04:18:39Z
PRODUCT_EXPECTED_RETIREMENT_BEFORE_FC4_CA_EXPIRY=true

FC4_CA_ROLLOVER_WORKSTREAM=CLOSED_NOT_PLANNED
FC4_CA_DUAL_TRUST_MIGRATION=NOT_REQUIRED_FOR_CURRENT_PRODUCT_LIFECYCLE
FC4_CA_AGE_BASED_ROLLOVER_TESTING=NOT_PLANNED

KF100_ROUTE_STATUS=CLOSED_PASS
KF100_REOPEN=false
```
