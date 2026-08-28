# N3-W / FC4 S2R2 Known Failures Addendum V1.0

Date: 2026-08-26

This file is a public-safe addendum for failures discovered during the S2R1/F7/F7R1/F7R2/S2R2 recovery chain. Canonical `KF-xxx` IDs are intentionally not assigned here because the public index already preserves historical ID reservations; merge-time maintenance should assign non-conflicting IDs in `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.

## S2R2-KF-A — Port presence misclassified service ownership

**Symptom**  
A pairing-port precheck treated the presence of the expected TCP/UDP listeners as evidence that the expected Manager owned them.

**Root cause**  
The oracle verified port presence but did not bind listener PID/cgroup/container identity.

**Guard**  
Every pairing-port handoff must prove exact owner identity with PID + cgroup + container binding. `PORT_PRESENT_ONLY` is never sufficient ownership evidence.

**Status**  
GUARDED by execution-contract rule.

## S2R2-KF-B — Active Dynamic Security path inferred from stale material

**Symptom**  
A parser reported no matching Manager client and initially suggested identity drift.

**Root cause**  
The parser was structurally reasonable but was pointed at a historical/expected Dynamic Security path instead of the file actually loaded by the running Broker.

**Guard**  
Resolve the Dynamic Security plugin state path from the currently running Broker configuration/container bindings before parsing identity or password state. Never use historical expected paths as runtime authority.

**Status**  
RESOLVED by runtime-path authority rule.

## S2R2-KF-C — `encoded_password` misclassified as passwordless client

**Symptom**  
An active Manager client was reported as having no password.

**Root cause**  
The classifier only checked legacy top-level password/salt/iteration fields and did not recognize the current `encoded_password` representation.

**Guard**  
Dynamic Security credential classifiers must recognize the schema used by the active Broker version. Object-key inventory must be inspected before declaring password absence.

**Status**  
RESOLVED by schema-aware classifier rule.

## S2R2-KF-D — Handcrafted MQTT v5 authentication probe produced invalid evidence

**Symptom**  
TLS succeeded, the connection closed without a complete CONNACK, and no server-side rejection record was recovered.

**Root cause**  
The handcrafted MQTT v5 CONNECT packet had invalid CONNECT-properties encoding.

**Guard**  
Production-equivalent Manager authentication proofs must use the same proven MQTT v5 client stack used by the product image (Paho MQTTv5 in the current implementation). Handcrafted MQTT packets must not be used as credential authority evidence.

**Status**  
GUARDED by probe implementation rule.

## S2R2-KF-E — Stale successor runtime contract reached live preclaim

**Symptom**  
A live S2R2 transaction stopped before claim because the successor still contained an old Manager client-ID/defaults and omitted current product-runtime bindings.

**Root cause**  
The successor artifact had been created at an earlier stage and was not rematerialized after identity/product-runtime convergence changed the effective contract.

**Guard**  
Every live cutover authorization must bind an exact successor SHA and perform an effective-runtime-contract preclaim against that exact artifact. Source/image SHA alone is insufficient.

**Status**  
GUARDED by SHA-bound successor preclaim rule.

## S2R2-KF-F — Missing explicit state-path env was overclassified as state migration

**Symptom**  
An audit classified missing explicit state-path environment keys as host-object drift / possible migration requirement.

**Root cause**  
The classifier compared configuration text rather than the effective container path plus host mount object.

**Guard**  
For persistent state roles, compare: effective runtime container path -> exact persistent host source -> object identity. Missing explicit env is not proof of migration need when defaults resolve to the same directly reusable host object.

**Status**  
GUARDED by effective-path/host-object identity rule.

## Merge-time index action

At merge time, append these six records to `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` using the next non-conflicting canonical IDs and add their primary DOMAIN classifications. Do not duplicate an existing canonical failure with the same root cause.
