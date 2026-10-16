# N3-W T1 F4 reboot acceptance durable-closure post-reboot binding CI test fix

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_POSTREBOOT_BINDING_CI_TEST_FIX_20261016_01
BASE_HEAD=b099ea221ca4b76a64223beccaa656aea0e6dce7
RESULT=TEST_FIX_COMMITTED_CI_PENDING

FAILED_WORKFLOW=N3W_T1_F4_ACTIVATION_SOURCE_CI_215
FAILED_STEP=FOCUSED_F4_TESTS
FAILED_TESTS=2
PRODUCT_SOURCE_DEFECT_PROVEN=false
TEST_FIX_REQUIRED=true

TEST_FIX_1=MOCK_NEW_MATERIAL_BINDING_HELPER_IN_FINALIZER_TEST
TEST_FIX_2=MOCK_NEW_MATERIAL_BINDING_HELPER_IN_TERMINAL_VERIFY_TEST
TEST_FIX_3=USE_TEST_RECORD_READER_FOR_NONROOT_GITHUB_RUNNER_FIXTURE

PRODUCTION_SOURCE_CHANGED=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## Failure classification

CI #215 failed after the post-reboot material-binding source repair, but the failure was in test fixtures rather
than in the production source path.

The finalizer test and terminal accepted-state test still mocked the old
`_verify_installed_control()` helper after production code moved to
`_verify_installed_control_material_binding()`. The finalizer test therefore fell through to the real
`/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json` path in GitHub CI.

The new material-binding regression test also used the production `_record()` metadata checker on temporary files
created by the non-root GitHub runner. Production correctly requires root-owned 0600/0644 state files; the unit-test
fixture must not attempt to satisfy host ownership semantics.

The repair updates only tests: they now mock the actual material-binding seam used by the finalizer/terminal verifier,
and the isolated material-binding test uses a JSON test reader while continuing to exercise transaction SHA-256,
manifest SHA-256, installed target hash/size/mode, claim structure, and the guard that `_base_pre_reboot()` must not
be called.

No production source, T1 state, runtime, board, or merge state was changed by this repair.
