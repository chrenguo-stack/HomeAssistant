# N3-W Auto Safe Fallback Gate F R2 — Broker Identity Reconciliation — 2026-10-04

## Scope

Read-only reconciliation after the R2 stale-Broker physical run reached current-T1 discovery, runtime-only Broker retarget, TCP connection, and TLS traffic but did not restore Manager-visible canonical telemetry.

## Observed Manager credential lifecycle

- target node registration match: true
- credential lifecycle row found: true
- state: ACTIVE
- active generation: 3
- pending generation: none

## Observed Broker configuration

- listener 8883 is published on IPv4 wildcard
- anonymous access disabled
- CA/server certificate/server key configured
- TLS listener configured for TLS v1.2
- Dynamic Security plugin config is present
- no `require_certificate true` observed
- no `use_identity_as_username true` observed

## Dynamic Security identity reconciliation

The target node's expected MQTT username hash matches one Dynamic Security client entry exactly. That entry has one role and contains a configured clientid plus encoded password material.

## Current interpretation

The evidence does not support either of these explanations:

1. the Manager credential lifecycle is still pending/rotating; or
2. the target MQTT username is absent from the running Broker Dynamic Security database.

The remaining investigation should stay below the already-proven stale-address recovery path and reconcile the target Dynamic Security client-id binding, actual Broker authentication/log output, and TLS terminal behavior.

## Safety / mutation record

- Board reset: false
- Board flash write: false
- Board NVS mutation: false
- T1 configuration mutation: false
- PR merge: false
