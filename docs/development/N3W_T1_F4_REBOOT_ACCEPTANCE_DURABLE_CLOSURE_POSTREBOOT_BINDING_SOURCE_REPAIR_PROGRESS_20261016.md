# N3-W T1 F4 reboot acceptance durable-closure post-reboot binding source repair

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_POSTREBOOT_BINDING_SOURCE_REPAIR_20261016_01
STATUS=IMPLEMENTED_CI_PENDING

REPAIR_BASE=f21b89d32297cef207f0e6bf4418af3069e7cb5f

A3_POSTREBOOT_PRECONDITION_REUSE=REPAIRED
IMMUTABLE_INSTALLED_CONTROL_BINDING_SPLIT=true
PRE_REBOOT_RUNTIME_ASSERTIONS_RETAINED_FOR_PRE_REBOOT_CALLERS=true
POST_REBOOT_FINALIZER_REUSES_PRE_REBOOT_TIMER_ASSERTION=false
POST_REBOOT_FINALIZER_REUSES_PRE_REBOOT_RUNTIME_SNAPSHOT=false
POST_REBOOT_TERMINAL_VERIFY_REUSES_PRE_REBOOT_RUNTIME_ASSERTIONS=false

F4_TRANSACTION_SHA256_STILL_EXACT=true
INSTALLED_CONTROL_MANIFEST_STILL_EXACT=true
INSTALLED_CONTROL_FILE_HASHES_STILL_EXACT=true
RECOVERY_READY_LINK_STILL_EXACT=true
POST_REBOOT_ACCEPTANCE_AUTHORITY=EXISTING_READONLY_REBOOT_VERIFIER

REGRESSION_TEST_POSTREBOOT_SAFE_MATERIAL_BINDING_ADDED=true

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_POSTREBOOT_BINDING_SOURCE_REVIEW_20261016_01
AUTO_EXECUTE_NEXT_GATE=true
```

## Repair

The source now separates immutable installed-control binding from pre-reboot runtime assertions.

`_verify_installed_control_material_binding()` verifies the exact frozen F4 transaction SHA-256, the install/recovery
claim linkage, the installed control manifest, and every installed control file hash/size/mode. It intentionally does
not require the certificate timer to remain in the pre-reboot inactive state and does not compare current container
`StartedAt` values with the pre-reboot runtime snapshot.

The existing `_verify_installed_control()` remains the stronger pre-reboot helper and still layers the original
pre-reboot runtime/timer/snapshot checks on top of the immutable material binding. Existing pre-reboot flows therefore
do not lose protection.

The post-reboot acceptance finalizer and terminal-state verifier use only the immutable material binding before the
existing full read-only reboot verifier supplies the actual post-reboot runtime acceptance proof.

A regression test explicitly makes `_base_pre_reboot()` fail if called and proves the new material-binding helper
still verifies the immutable state successfully. This closes the exact class of R2 failure before any T1 execution.

No T1, runtime, board, or merge mutation occurred in this source-repair gate.
