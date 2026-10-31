# N3W T1 E03 Fresh Replacement Post-Reboot Preauthorization Source Repair

Date: 2026-10-30

## Problem

A T1 reboot changes Docker Broker `StartedAt`. The old claimed replacement transaction is correctly invalidated and terminally blocked, but a new E03 replacement preauthorization still compares the current Broker `started_at` to the immutable predecessor evidence and therefore fails with `broker_predecessor_continuity_drift`.

## Safety rule

Do not weaken the Broker continuity checks of an already-created transaction.

Only the creation of a new transaction may establish a fresh Broker baseline. A changed `started_at` is accepted only when:

- Broker container ID is unchanged.
- Broker image ID is unchanged.
- Broker restart count is unchanged.
- The predecessor Broker start is older than the current kernel boot.
- The observed Broker start is at or after the current kernel boot.
- Broker activation occurred within 300 seconds of the current kernel boot.

Otherwise preauthorization fails closed.

## Resulting behavior

- Existing READY/APPLYING/VERIFYING transactions retain exact frozen Broker continuity.
- A host reboot invalidates an old READY transaction; that transaction must be terminally blocked.
- A subsequent fresh preauthorization may bind the Broker runtime from the current boot as the new transaction baseline.
- A later Broker restart in the same boot is not treated as a host reboot rebase.
- Product, service, Docker, Broker, Manager, Home Assistant and board mutation are out of scope for this source repair.

## Tests

Focused tests cover exact predecessor continuity, accepted current-boot rebase, identity drift rejection, and late same-boot restart rejection.
