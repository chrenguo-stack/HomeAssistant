# N3-W P4 private QR binder/importer R3 source repair and synthetic regression — progress checkpoint (2026-10-08)

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_IMPORTER_R3_SOURCE_REPAIR_AND_SYNTHETIC_REGRESSION_20261008_01
STATUS=SOURCE_REPAIR_COMMITTED_CI_PENDING
PREDECESSOR_R2_SOURCE_REVIEW=BLOCKERS_FOUND
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE_REQUIRED=OPEN_DRAFT_UNMERGED
CODE_REPAIR_HEAD=905dd5052680f8d2ba66734e9d54f5b37a8c3554
CI_WORKFLOW=N3W P4 private pairing binder R3 synthetic regression
CI_RUN_ID=37773448859
CI_RUN_STATE_OBSERVED=queued
CI_RESULT=NOT_YET_PROVEN
STOP=true
```

## 1. Prior R2 findings

Source authority:
- `docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_BINDER_IMPORTER_R2_INDEPENDENT_SOURCE_REVIEW_20261008.md`
- `docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_BINDER_IMPORTER_R2_HOST_ONLY_READONLY_PREFLIGHT_DESIGN_20261008.md`

R2 opened three source blockers: caller-forgeable live/authorization booleans; remote read-only script assembled from an import-capable Mac module; and lack of exact frozen private preboot-snapshot verification. Additional open work includes real T1 compatibility, lifecycle/TTL policy convergence, and durable operator one-shot claim.

## 2. Submitted source repairs and exact blobs

All package files reside in `tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/`.

| File | Git blob after R3 edit | Scope |
| --- | --- | --- |
| `bridge_handoff.py` | `e277949c3db5675bd460124832a382d6a2765539` | Source-only `OneShotImporter.import_once` now always rejects; `ssh_manager_stdin_transport` has no executable SSH import operation; fake `live_attested=True` and fake approvals can no longer deliver a secret through this source-stage path |
| `host_readonly.py` | `b5732e2ae716c2bba9b5313aadec6cd8abf7b776` | Require the exact frozen owner-only private P4 preboot snapshot SHA256; verify immutable Git blobs for both bridge and remote projection sources; extract **only** the read-only SQLite projection classes/functions by Python AST before composing remote SSH code; forbid importer, secret-bearing helpers and mutating SQL in the assembled source |
| `test_bridge_handoff.py` | `f806b54eb7e15edcbcf8e4bb71977424b23f17bb` | Fail-closed forged grant, simulated import and SSH import-path tests; never call transport |
| `test_host_readonly.py` | `c5a57527e5b45f6d9049b1520124944880cbcc98` | Frozen snapshot path, immutable source SHA, absent import code in assembled remote script, forbidden mutation source, stale authority and SSH target failures |

Immutable input blobs: remote projection `7b3ba146583b61271b41390736b67207c8d4c14e`; original binder core `3b7dc0d085dcda52fda0334840d75d5f8678bc1b`; original 24-case binder test `4f626fbacfd4a64e36d46e5e396a610df64526ee`.

Dedicated source-only workflow:
`.github/workflows/n3w-p4-private-pairing-binder-r3-synthetic-ci.yml`.

## 3. Coverage and status — distinguish test declarations from test execution

```text
SYNTHETIC_TESTS_PRESENT_IN_SOURCE=60
TEST_VALIDATOR_DECLARED=24
TEST_BRIDGE_HANDOFF_DECLARED=22
TEST_HOST_READONLY_DECLARED=14
TEST_RUNTIME_RESULT=CI_PENDING
TESTS_PASS=NOT_YET_CLAIMED
LIVE_T1_READONLY_RUN=NOT_EXECUTED
BOARD_ACCESS=NO
REAL_LCD_QR=NOT_CAPTURED
REAL_SETUP_SECRET=NOT_IMPORTED
```

The targeted GitHub Actions workflow runs only Python compilation and synthetic `unittest` discovery with no production T1, board or secret access. The run `37773448859` was observed queued; do not report PASS until its conclusion and genuine failing-job evidence are checked.

**R3 A1 outcome:** the legacy source-only import execution path is **disabled**, not replaced with a safe approved live importer. Source-code exposure to fake booleans has been mitigated by refusing delivery, but first-pair functionality is intentionally incomplete. A later field orchestrator needs a durable one-shot authorization claim plus exact SSH provenance; no blanket real import approval follows from this fix.

**R3 A2 outcome:** read-only SSH code must contain only the AST-extracted projection core and source-pinned probe. No source of the import helper, Setup Secret, QR input or direct Manager-write transport is passed in the remote preflight. The exact file hashes are pinned before assembly.

**R3 A3 outcome:** the host-side assembly now requires the frozen private file at
`~/N3W_PRIVATE_EVIDENCE/N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01/manager_preboot_identity_snapshot.json`; exact SHA256 `81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c`; five historical identity hashes; strict path and file controls.

## 4. Further gates and STOP

```text
SOURCE_REPAIR_STATUS=COMMITTED
SYNTHETIC_CI_STATUS=QUEUED_AT_CHECKPOINT
R3_FINAL_REVIEW=NOT_YET_PERFORMED
R3_GATE_FINAL_CLOSURE=NOT_CLAIMED

MANAGER_FIELD_IMPORTER_READY=false
RUNNABLE_MAC_FIELD_ORCHESTRATOR_READY=false
LIVE_T1_HOST_ONLY_PREFLIGHT_AUTHORIZED=false
LIVE_T1_HOST_ONLY_PREFLIGHT_EXECUTED=false
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
P3_PRODUCT_NORMAL_BOOT_OCCURRED=false
SETUP_SECRET_IMPORT_OCCURRED=false
BOARD_ACCESS=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
MERGE=false
AUTO_P4=false

NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_QR_BINDER_IMPORTER_R3_CI_REVIEW_AND_REMAINING_FIELD_ORCHESTRATOR_DESIGN_20261008_01
STOP=true
```

If CI fails, recover the **first real failure** and repair only the exact source branch; do not repeatedly poll or auto-retry the live stage. If CI passes, conduct a separate source review and explicitly retain field importer and T1 readonly blockers. The prior P3 flash/write, P4 preboot and pairing IPC readiness acceptances remain valid but cannot authorize first normal product boot.
