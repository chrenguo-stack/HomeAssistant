# N3-W Production Relay Discovery Channel Coverage Fallback V1 — Deferred Decision

Status: `DEFERRED_AFTER_CURRENT_MULTI_RELAY_V1_ACCEPTANCE`

## Decision

The current Production Multi-Relay Gateway Selection V1 exact artifact remains unchanged.
The existing Relay Discovery fast-scan policy continues to use the current allowed channel set
`{1,6,11}`, while preserving the runtime's existing last-Direct-channel hint behavior.

The coverage blind spot for Gateways operating on other valid 2.4 GHz channels is accepted as a
known limitation for the current physical acceptance because the present test environment is not
blocked by it.

The repair is scheduled immediately after the current Multi-Relay Gateway Selection V1 physical
acceptance closes and before the next production artifact is frozen.

## Planned successor direction

The follow-up design should prefer a layered discovery strategy rather than replacing the current
fast scan with an unconditional full-channel sweep:

```text
1. last_direct_channel
2. known_or_cached_gateway_channel
3. fast_scan_1_6_11
4. bounded_full_legal_channel_fallback
5. stop_full_scan_after_gateway_discovery
```

The follow-up must preserve:

- fast discovery performance on ordinary 1/6/11 deployments;
- single-radio ownership safety;
- protection against recurrence of Wi-Fi/ESP-NOW channel contention;
- Relay-to-Direct recovery behavior;
- Multi-Relay Gateway selection and stickiness behavior.

## Current execution boundary

```text
CURRENT_MULTI_RELAY_V1_ARTIFACT_CHANGE=false
CURRENT_PHYSICAL_ACCEPTANCE_CONTINUES=true
FOLLOWUP_ROUTE=N3W_PRODUCTION_RELAY_DISCOVERY_FULL_CHANNEL_FALLBACK_V1
FOLLOWUP_TIMING=AFTER_CURRENT_MULTI_RELAY_V1_PHYSICAL_ACCEPTANCE
FOLLOWUP_BEFORE_NEXT_PRODUCTION_ARTIFACT_FREEZE=true
```
