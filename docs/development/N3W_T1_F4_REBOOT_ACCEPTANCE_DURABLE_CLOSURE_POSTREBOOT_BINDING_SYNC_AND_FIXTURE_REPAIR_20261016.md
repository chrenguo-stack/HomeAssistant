# N3-W T1 F4 post-reboot binding synchronization audit and fixture/source repair

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_POSTREBOOT_BINDING_SYNC_AND_FIXTURE_REPAIR_20261016_01
BASE_HEAD=b463c086366e12a227336a853acd5947d80d365e
STATUS=REPAIR_COMMITTED_CI_PENDING

SYNC_AUDIT_GITHUB_FULLY_CURRENT_BEFORE_REPAIR=false
MISSING_BEFORE_REPAIR=CI_217_FINAL_FAILURE_AND_CORRECTED_ROOT_CAUSE
SYNC_AUDIT_ARCHIVED_TO_PR605=true

CI_217=FAIL:FOCUSED_F4_TESTS
CI_217_PASSED_TESTS=133
CI_217_FAILED_TESTS=2

CORRECTED_FINDING_TERMINAL_VERIFY_PRE_REBOOT_HELPER_REUSE=true
PRODUCT_SOURCE_REPAIR_REQUIRED=true
TERMINAL_VERIFY_NOW_USES_POSTREBOOT_SAFE_MATERIAL_BINDING=true
PRE_REBOOT_HELPER_REUSE_GUARD_TEST_ADDED=true

FIXTURE_1_MATERIAL_BINDING_MOCK_RETURNS_TUPLE=true
FIXTURE_2_INSTALLED_TARGET_ROOT_METADATA_MODELED=true
PRODUCTION_ROOT_OWNERSHIP_CHECK_WEAKENED=false

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_POSTREBOOT_BINDING_SOURCE_REVIEW_20261016_01
AUTO_EXECUTE_NEXT_GATE=true
```

## Synchronization audit

Before further mutation, PR #605, exact head CI, recent PR comments, current-state documents and KF guards were
freshly rebound. GitHub had the syntax-fix commit and its in-progress CI archive, but did not yet contain the final
CI #217 result. The latest current-state documents also stopped at the CI #215 fixture repair. Therefore local
conversation progress and GitHub were not fully synchronized.

The missing CI #217 result and corrected root-cause classification were first archived in PR #605 before this repair.

## Corrected source finding

CI #217 exposed two focused-test failures. Re-reading the exact production source showed that
`verify_reboot_accepted()` still called `_verify_installed_control()`. That helper intentionally layers
pre-reboot runtime/timer/snapshot assertions over the immutable installed-control binding, so it is not valid for a
post-reboot terminal verifier.

The terminal verifier now calls `_verify_installed_control_material_binding()` directly. This preserves exact F4
transaction SHA-256, install/recovery claim linkage, control manifest binding and installed target hashes without
reintroducing pre-reboot timer or container `StartedAt` requirements.

The terminal-verifier test additionally makes the old pre-reboot helper raise if called, so future regression to that
path fails immediately.

## Fixture repair

The material-binding helper returns a two-item tuple. Test mocks now honor that contract instead of returning
`None`.

The isolated material-binding regression test still exercises production file hash, size and mode checks. Because a
GitHub-hosted runner cannot create root-owned temporary targets, the test models only the installed target's
`uid=0/gid=0` metadata through a test-only `Path.stat` shim. Production `_record()` and installed-target
ownership enforcement are unchanged.

No T1, runtime, board, or merge mutation occurred.
