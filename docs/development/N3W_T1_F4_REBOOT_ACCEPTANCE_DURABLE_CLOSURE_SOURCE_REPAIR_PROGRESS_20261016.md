# N3-W T1 F4 reboot acceptance durable-closure source repair progress

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_SOURCE_REPAIR_20261016_01
STATUS=IMPLEMENTED_CI_PENDING

REPAIR_BASE=6d2758a6a6dda4dae2d98cdcc625a5dcaeb1606a
LIVE_REBOOT_ACCEPTANCE=PASS:REBOOT_ACCEPTED
LIVE_T1_MUTATION_IN_THIS_GATE=false

DESIGN_POLICY=IMMUTABLE_PRODUCT_MATERIAL_PLUS_MUTABLE_DEVICE_TRANSACTION_LEDGER
REBOOT_VERIFIER_REMAINS_READ_ONLY=true
DURABLE_ACCEPTANCE_FINALIZER_ADDED=true
READONLY_TERMINAL_VERIFIER_ADDED=true
CONSUMED_AUTHORIZATION_REPLAY_ALLOWED=false
PENDING_CLAIM_HASH_CHAIN_PRESERVED=true
PRE_AND_POST_BOOT_BINDING_PRESERVED=true
F4_TRANSACTION_HASH_MUTATION_REQUIRED=false
PRODUCT_MATERIAL_HASH_MUTATION_REQUIRED=false

NEW_COMMAND=finalize-reboot-acceptance
NEW_READONLY_COMMAND=verify-reboot-accepted

BOARD_ACCESS=false
MERGE=false
NEXT_STEP=EXACT_HEAD_CI_AND_FOCUSED_SOURCE_REVIEW
```

## Scope

This repair closes the source-state-machine gap found by the final PR #605 pre-merge review. It does not repeat the
already-passed reboot and does not alter immutable product material semantics. The existing post-reboot verifier
remains read-only.

The authority now adds a separate fail-closed finalization step. Finalization requires the exact SHA-256 of the
existing `REBOOT_PENDING` record, re-runs the repository-owned post-reboot verifier, requires the current boot to
match the verified post-boot identity, and only then atomically replaces the mutable transaction record with
`REBOOT_ACCEPTED`.

The terminal record preserves the consumed/no-replay authorization fields, the pre-acceptance pending-claim SHA-256,
the pre/post boot binding, and the canonical acceptance-report SHA-256. The accepted record is itself hashed and
returned by the finalizer. A separate `verify-reboot-accepted` command performs a no-write terminal-state check.

This is the production-facing separation requested by the architecture review: immutable installed scripts,
manifest and F4 transaction bindings remain hash-stable, while the mutable device transaction ledger advances
through a validated state transition.

CI and focused source review are still required before any repaired artifact or real-T1 finalization is authorized.
