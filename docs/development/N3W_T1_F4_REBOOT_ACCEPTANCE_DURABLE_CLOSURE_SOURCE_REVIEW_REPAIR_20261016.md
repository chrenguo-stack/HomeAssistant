# N3-W T1 F4 reboot acceptance durable-closure source review repair

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_SOURCE_REPAIR_20261016_01
REVIEWED_HEAD=b4287d574907c8715c4e837139d9df5cd4864177
REVIEW_RESULT=BLOCKED_REPAIRED_SOURCE_PENDING_CI

A1_LEDGER_TERMINAL_TRANSITION=IMPLEMENTED
A2_FINALIZER_EXECUTOR_DEPLOYMENT_BINDING=REPAIRED
A2_ROOT_CAUSE=INITIAL_FINALIZER_REQUIRED_NEW_INSTALLED_CONTROL_BINDING_WITHOUT_AN_UPDATE_PATH

FINALIZER_EXECUTION_MODEL=EXACT_STAGED_ARTIFACT
FINALIZER_SELF_BINDING_REQUIRED=true
INSTALLED_CONTROL_BINDING_REMAINS_EXISTING_CONTROL_READY_ARTIFACT
IMMUTABLE_INSTALLED_PRODUCT_MATERIAL_REPLACEMENT_REQUIRED=false

REBOOT_VERIFIER_REMAINS_READ_ONLY=true
AUTHORIZATION_CONSUMED_NO_REPLAY_PRESERVED=true
PENDING_CLAIM_HASH_CHAIN_PRESERVED=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

Focused review of the first durable-closure repair found a deployment-path defect. The initial finalizer code verified
the installed control against its own new source/manifest. The real T1 still has the previously accepted
`CONTROL_READY` artifact installed, and the existing installer cannot replace that verified installed control
without entering a different authorized update transaction. Therefore the first implementation could not be used
on the real T1 without an untracked/manual replacement.

The repair separates the two identities. The finalizer now executes directly from an exact staged repository-owned
artifact and must self-bind its executing file to that package manifest. Independently, it verifies the existing
installed `CONTROL_READY` artifact using explicit installed-source and installed-manifest arguments. No immutable
installed product file needs to be replaced merely to close the mutable ledger.

The terminal accepted record preserves both identities: the original installed-control source/manifest remain the
control binding, while the finalization executor source/manifest/executor SHA-256 are recorded separately together
with the prior pending-claim SHA-256 and the acceptance report hash.

Exact-head CI and a fresh focused review remain required before any artifact staging or T1 finalization.
