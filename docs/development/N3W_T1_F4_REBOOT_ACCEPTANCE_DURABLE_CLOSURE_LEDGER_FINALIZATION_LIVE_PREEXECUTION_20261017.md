# N3-W T1 F4 durable reboot ledger finalization — live preexecution

Date: 2026-10-17

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_LEDGER_FINALIZATION_LIVE_20261017_01
STATUS=AUTHORIZED_READY_FOR_TARGET_EXECUTION

PR=605
PR_STATE=OPEN_DRAFT_NOT_MERGED
PRODUCT_SOURCE_REVIEW_HEAD=19bd98386c4828c0768f2f3936429db8c7a59adf
PRODUCT_SOURCE_REVIEW_TREE=f5b66faf690c88d655e01ffc0a5d5ef122b589af
PRODUCT_SOURCE_DRIFT_AFTER_REVIEW=NONE

PREAUTH_GATE=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_LEDGER_FINALIZATION_ARTIFACT_AND_READONLY_PREAUTH_20261017_01
PREAUTH_RESULT=CLOSED_PASS
PREAUTH_ACCEPTANCE_REPORT_SHA256=ecb7bca66f27a9372b23ed928407de7a2e9d6ec957fcc5a0c1e0245dce40fecf

LIVE_AUTHORIZATION_GRANTED=true
LIVE_AUTHORIZATION_SCOPE=ONE_EXACT_LEDGER_FINALIZATION_PLUS_READONLY_TERMINAL_VERIFICATION
LIVE_AUTHORIZATION_REUSE_ALLOWED=false
LIVE_AUTHORIZATION_TARGET_STATE=REBOOT_ACCEPTED

ARTIFACT_ID=12056436272
FINALIZER_SOURCE_HEAD=19bd98386c4828c0768f2f3936429db8c7a59adf
FINALIZER_MANIFEST_SHA256=bab1f7f1a4834d4f85bd01ae05d4569d32798e6661c72caf0d2636cfbaecbe70
FINALIZER_EXECUTOR_SHA256=c4a738656e98b5f8bae27a34aba845c002287b253f99f54cf459f8d292f7d9ec

INSTALLED_SOURCE_HEAD=66788b22fc55f7bf1c003e0b97bc7e75ce859e35
INSTALLED_MANIFEST_SHA256=f970a4e49730f0f653e52508ef13bec2f018d8c47ea589ff295cfe398529f9a7
EXPECTED_F4_TRANSACTION_SHA256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
EXPECTED_PENDING_REBOOT_CLAIM_SHA256=61429105bc05f135f3d0b8be338d74899b2466cb65fa896be4254d37a54c5028
EXPECTED_POST_BOOT_ID_SHA256=e04f445426ee875b1c429a33c6b1e6893175727118fc8ad28e24c431c1fa66c7

REBOOT_AUTHORIZATION_ALREADY_CONSUMED=true
REBOOT_AUTHORIZATION_REPLAY_ALLOWED=false
RECOVERY_AUTHORIZATION_REPLAY_ALLOWED=false

ALLOWED_LIVE_MUTATION=ATOMIC_REBOOT_LEDGER_REPLACEMENT_ONLY
REBOOT_EXECUTION_ALLOWED=false
INSTALLED_CONTROL_REPLACEMENT_ALLOWED=false
F4_TRANSACTION_MUTATION_ALLOWED=false
CERTIFICATE_LIFECYCLE_TRIGGER_ALLOWED=false
BOARD_ACCESS=false
MERGE=false

POSTEXECUTION_TERMINAL_VERIFY_REQUIRED=true
TERMINAL_VERIFY_MUTATION=false
AUTO_RETRY_FINALIZER_ON_FAILURE=false
AUTO_EXECUTE_OTHER_GATE=false
STOP_AFTER_TERMINAL_VERIFY=true
```

## Authorization semantics

The explicit live authorization applies only to this exact gate, exact reviewed finalizer artifact and exact historical
pending reboot-claim SHA-256.

The finalizer does not create or consume a new authorization field inside the T1 ledger. The project-level live
authorization is instead bounded by the frozen gate record plus the exact pending-claim hash. Once the ledger has
advanced, the same finalizer invocation cannot validly replay against the old pending hash.

The old reboot authorization remains consumed/no-replay and is not reused. The old control-recovery authorization is
also not reused.

## Allowed target mutation

The only allowed production-state mutation is the authority's atomic replacement of:

```text
F4_REBOOT_AUTHORIZATION.json
REBOOT_PENDING
->
REBOOT_ACCEPTED
```

The source-reviewed finalizer must freshly verify the exact staged artifact, installed control material, F4
transaction, pending claim, and post-reboot acceptance evidence before this atomic write.

No host reboot, installed-control replacement, F4 transaction rewrite, certificate lifecycle invocation, board
operation or PR merge is authorized.

## Postexecution rule

If finalization returns PASS, immediately run the source-reviewed read-only `verify-reboot-accepted` using the
returned accepted-claim SHA-256.

If finalization returns FAIL, disconnects, or has an ambiguous result, do not run the finalizer again. Stop and
perform read-only forensic classification first. This prevents blind replay after a possibly committed atomic write.

No private T1 locator or credential is stored in this public document.
