# GH H3 Node Profile Lifecycle Integration V1

## Scope

This contract binds three previously isolated node-side mechanisms without
making them production-active:

1. recover an authenticated `PREPARED` credential record;
2. validate that candidate with an independent MQTT client;
3. make the verified candidate runtime-active and commit the active marker last.

The contract is transport- and hardware-adapter independent. It does not define
an operator trigger, startup action, eFuse provisioning flow, physical NVS
partition, Broker address, or production MQTT setter.

## Lifecycle

```text
IDLE
→ RECOVERED_PREPARED
→ VALIDATING
→ VERIFIED
→ ACTIVATING
→ ACTIVATED
```

Terminal alternatives are `ROLLED_BACK`, `FAILED`, and `REBOOT_REQUIRED`.

## Recovery admission

Only these persistent states may enter the lifecycle:

- `NO_ACTIVE_PREPARED` for first enrollment;
- `ACTIVE_WITH_PREPARED` for credential rotation.

The active and candidate generations, record metadata, and decoded credential
generations must agree. The runtime staging adapter must acknowledge exactly the
same generation pair.

Committed orphan, invalid record, conflict, storage error, stale candidate, and
missing candidate states fail closed.

## Candidate validation

The candidate is copied into the Stage 2D-2 independent-client validator. The
integration requires:

- candidate generation greater than active generation;
- successful authentication;
- subscription readiness;
- a nonce- and generation-bound telemetry round trip;
- destruction of the temporary candidate probe client;
- proof that the active profile remained unchanged.

The integration clears its local candidate credential copy immediately after it
is transferred into the validator. The runtime adapter retains only the staged
material required for a later activation attempt.

## Activation

Activation may start only from `VERIFIED`. Before runtime mutation, the
persistent adapter re-reads storage and confirms the original `PREPARED`
generation pair.

The Stage 2D-3 transaction then executes:

```text
stop old runtime
→ start candidate runtime
→ confirm candidate round trip
→ commit candidate record and active marker
```

Persistent commit must not occur before the fresh runtime round trip.

## Persistence result mapping

- `COMMITTED`: recovery proves the candidate generation is now active.
- `OLD_ACTIVE_PRESERVED`: the commit failed, but recovery proves the old marker
  remains authoritative; candidate runtime is stopped and the old runtime is
  restored.
- `INDETERMINATE_REBOOT_REQUIRED`: storage cannot prove either authority; all
  runtimes are quiesced and reboot recovery is required.

For first enrollment, a failed commit may return `OLD_ACTIVE_PRESERVED` only
when recovery proves that no active marker exists.

## Credential handling

- local candidate credentials are explicitly cleared after validator staging;
- candidate runtime material is cleared on every terminal activation path;
- no credential value, CA body, username, client ID, password, or Broker address
  may be logged;
- validation failure leaves the persistent `PREPARED` record unchanged for an
  explicit retry or rollback decision.

## Exclusions

V1 does not enable:

- automatic startup recovery or activation;
- production ESPHome MQTT profile mutation;
- physical NVS writes from a laboratory assembly;
- real Broker access;
- firmware flashing or eFuse operations;
- previous-slot retirement, credential revocation, or factory reset.
