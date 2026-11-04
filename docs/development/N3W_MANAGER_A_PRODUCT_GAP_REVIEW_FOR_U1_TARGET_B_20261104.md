# N3-W Manager A product-gap review for U1 Target B

Date: 2026-11-04

## Scope

```text
TASK=N3W_MANAGER_A_PRODUCT_GAP_REVIEW_FOR_U1_TARGET_B_20261104_01
MANAGER_A_PRODUCT_SOURCE=b863ddd959090ca139af76bd68dbef31d773e6de
MANAGER_A_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
REPOSITORY_MUTATION=DOCS_ONLY_REVIEW_ARCHIVE
MANAGER_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

The review is intentionally limited to finding a real product improvement suitable for the
first U1 Manager A -> B validation. A target created only by retagging or rebuilding identical
Manager application content is rejected.

The following Manager business-source blobs are unchanged from Manager A through the current
PR #774 head at the time of review:

```text
runtime/mqtt_service.py=66b83b96a4fa320ef92912a16063b507e8d7f7f5
runtime/ha_discovery.py=912eaf5e28a6cb3cd516fd376c09a6a3ac9601f6
runtime/ingest.py=62f8102778697002d93a0f99a6a6b261f371d1c3
pyproject.toml=48c271cdeb7ba7a8b25f8fd2807d845f42c2c069
```

## Finding 1 — Discovery cache can suppress retry after an immediate MQTT publish failure

Severity: MEDIUM product reliability.

`HomeAssistantDiscovery.messages_for_telemetry()` stores the new discovery payload hash in
`_published_hashes` before the Manager attempts the MQTT publish.

`ManagerMqttService._publish_discovery()` then calls `_publish()` but ignores the returned
boolean and logs "Published Home Assistant discovery" unconditionally.

Therefore this sequence is possible:

1. telemetry is accepted;
2. discovery payload is generated and its hash is cached;
3. MQTT `publish()` returns a non-success rc;
4. no discovery message reached the Broker;
5. the next unchanged telemetry sees the cached hash and returns no discovery message;
6. discovery is not retried until the cache is cleared, Manager restarts, or discovery content
   changes.

The current tests prove unchanged discovery is intentionally suppressed, but there is no test
covering publish failure followed by retry.

This is a concrete false-success/retry-loss path.

### Recommended bounded repair

Keep the existing discovery de-duplication model, but make transport success control cache
commit/retry semantics.

A minimal safe form is:

- attempt all generated discovery publishes;
- log "published" only on a successful transport result;
- if any discovery publish fails immediately, invalidate the node discovery cache so the next
  telemetry retries the retained discovery documents;
- add regression tests for first publish failure -> next telemetry retries;
- do not block the MQTT callback waiting for PUBACK.

This repair does not require a schema change, persistent-state migration, runtime environment
change, Broker change, Home Assistant change, or Board change.

## Finding 2 — Canonical telemetry state is committed before MQTT delivery outcome is known

Severity: MEDIUM, larger repair surface than Finding 1.

`TelemetryProcessor.commit_prepared()` records the dedup key and updates last-seen/availability
before returning the canonical telemetry and availability messages.

`ManagerMqttService._on_message()` then ignores the return value of `_publish()` for those
messages and still logs the ingress as accepted.

If an immediate publish failure occurs, the same node packet can subsequently be classified as
duplicate and will not republish the same canonical state. A later sequence normally heals the
latest-state stream, but the failed sample is lost from the canonical path.

The existing stale-unavailable path already contains explicit failure rollback/retry behavior
through `mark_unavailable_publish_failed()`; the accepted telemetry path does not have an
equivalent contract.

Repairing this correctly should be a separate reliability gate because it requires defining the
boundary between validation/dedup commit and MQTT delivery.

## Finding 3 — Core Manager subscription readiness does not validate MQTT v5 SUBACK

Severity: MEDIUM readiness/observability.

`ManagerMqttService._on_connect()` treats a successful local `client.subscribe()` return code
as if the subscription itself were active and logs `Subscribed to ...` immediately.

The service does not register an `on_subscribe` handler, so a Broker-side rejected SUBACK is not
bound into Manager readiness.

This matters because the project has previously experienced Dynamic Security ACL defects affecting
Manager subscription permissions.

The repository already contains the correct stronger pattern in
`PahoProjectionRpcTransport`: it records the subscription MID, waits for `on_subscribe`, rejects
failure reason codes, and only then marks the transport connected.

Adopting the same semantic contract in the core Manager is desirable, but the failure action
(retry subscription, degrade readiness, or terminate for supervised restart) needs an explicit
design decision. It is therefore not the smallest U1 Target B.

## Finding 4 — Manager package version is operationally weak as an exact build identity

Severity: LOW observability.

The package version is currently `0.4.99`. Home Assistant discovery origin metadata uses the
installed package version as `origin.sw_version`.

Exact deployment identity is correctly controlled elsewhere by source/image/artifact authority, so
this is not a correctness blocker. However the ordinary product-facing runtime metadata does not
identify the exact Manager source/image revision.

This should not be used alone to manufacture Target B. It can be improved later together with a
real product change.

## Recommendation for first real Manager B

```text
RECOMMENDED_TARGET_B_CHANGE=DISCOVERY_PUBLISH_FAILURE_RETRY_CORRECTNESS
REAL_PRODUCT_DEFECT=true
DATABASE_MIGRATION=false
CONFIG_MIGRATION=false
RUNTIME_TEMPLATE_CHANGE=false
BROKER_CHANGE=false
HOMEASSISTANT_CHANGE=false
BOARD_CHANGE=false
PAIRING_STATE_CHANGE=false
EXPECTED_RISK=LOW
U1_IMAGE_ONLY_V1_COMPATIBLE=true
```

Use Finding 1 as the first Manager successor B.

Do not combine Finding 2 or Finding 3 into the same first U1 upgrade unless source review proves the
small repair insufficient. They are valuable follow-up reliability work but have larger behavioral
boundaries.

## Required source tests before building Target B

The B source gate should prove at minimum:

- unchanged successful discovery still publishes once and is de-duplicated afterward;
- immediate publish failure does not leave the discovery cache suppressing the next attempt;
- the next identical telemetry causes discovery retry;
- successful retry restores normal de-duplication;
- failed publish is not logged as successful;
- retirement cache clearing remains unchanged;
- no canonical telemetry, registration, pairing, history, Broker or Home Assistant contract changes.

## U1 boundary

This review does not authorize a live T1 apply.

After the Target B source repair, source review, exact ARM64 artifact build and exact target manifest
binding, U1 may run plan/simulation. The real T1_B apply remains a separate explicit live-mutation
authorization boundary.
