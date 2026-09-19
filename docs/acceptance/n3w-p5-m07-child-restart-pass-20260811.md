# N3-W / P5 / M07 Child restart acceptance

- Date: 2026-08-11
- Matrix: `M07`
- Status: `SANITIZED_M07_CONSUMED_PASS`
- Repository baseline: `main` at `9ff26629146fe2c1056f52e269c044a135306772`
- Baseline tree: `5cbe98c4e5838fb64378093691997423e3b65149`
- Existing PR #303: not modified by this archive

## Exact-main contract

M07 is the Child restart matrix item. Its acceptance expectation is a newly persisted boot session with no nonce reuse.

## Execution closure

The first executor invocation stopped before authorization claim because its preclaim credential-resolution logic could not uniquely resolve the intended local test credential. That invocation performed no mutating action and sent no Child restart command. It is therefore classified as `STOP_PRECLAIM_UNCLAIMED`, not as an M07 failure.

A corrected successor executor then passed the passive preclaim gates and crossed the exactly-one boundary once. Exactly one Child `RESTART` publication was attempted, the publication process completed successfully, the authorization was consumed, and the execution terminal was `PASS`.

Frozen execution semantics:

- R1 authorization claimed: false
- R1 authorization consumed: false
- R1 Child restart publication attempts: 0
- R2 authorization claimed: true
- R2 authorization consumed: true
- R2 Child restart publication attempts: 1
- Total M07 Child restart publication attempts: 1
- M07 replay allowed: false
- Second M07 Child restart prohibited: true

## Validated behavior

The live M07 execution demonstrated all of the following without publishing raw private tuple values in this archive:

- exactly one new Child boot identity was observed after restart;
- the new persisted boot session was the exact successor of the prior session;
- sequence numbering restarted at zero and then progressed strictly within the new session;
- canonical telemetry advanced to the new boot session;
- canonical state did not roll back across the boot-session transition;
- the active path remained Direct and no candidate path was present;
- no unexpected Gateway ingress was observed;
- the new boot session created a nonce domain disjoint from the prior boot session;
- nonce reuse was not observed;
- Manager, Broker, and Home Assistant remained stable without restart.

The apparent drop in the sequence component across restart is expected because the boot session advanced. Sequence values are interpreted together with the persisted boot-session identity rather than as a global cross-boot scalar.

## Identity claim boundary

NODE_ID continuity was observed during M07. This M07 transcript does not independently prove unchanged HARDWARE_ID or unchanged Home Assistant device identity. Those broader identity-continuity claims remain outside this acceptance record and are not inferred here.

## Private immutable evidence

The complete R1/R2 transcript and normalized terminal have been frozen separately in private immutable evidence. That private evidence passed exact readback, content binding, read-only mode, and non-overwrite validation.

This public archive intentionally does **not** include the private evidence digest, private filesystem path, raw boot/session values, raw sequence/revision values, credentials, keys, session material, or raw live traces.

## Matrix boundary

This record accepts only M07. It does not claim that deferred M06 live physical E2E passed, and it does not authorize or execute M08 Relay restart or any later matrix item.

No board access, USB/serial access, reset, power change, Flash/erase, PATH, RESEND, REORDER, service restart, or other live mutation is authorized by this documentation archive.

## Terminal

`M07_ACCEPTED=true`

`M07_TERMINAL=PASS`

`TOTAL_M07_RESTART_PUBLISH_ATTEMPT_COUNT=1`

`M07_REPLAY_ALLOWED=false`

`SECOND_M07_CHILD_RESTART_PROHIBITED=true`

`TERMINAL=SANITIZED_M07_CONSUMED_PASS`
