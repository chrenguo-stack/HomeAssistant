# N3W CI Policy as Code and Drift Guard V1

Date: 2026-10-26

```text
TASK=N3W_CI_POLICY_AS_CODE_AND_DRIFT_GUARD_V1
N3W_CI_POLICY_REVISION=N3W_CI_POLICY_V1_20261026
PARENT_TASK=N3W_CI_FAST_SOURCE_GATE_AND_EXACT_CLOSURE_SPLIT_V1
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
MERGE=false
```

## Purpose

The repository already had written requirements for Fast / Model / Build / Evidence / Candidate-style CI layering, Draft PR fast-only behavior, PR cancellation and bounded execution. The implementation had not fully converged to those requirements.

This V1 changes the control model from prose-only expectations to policy-as-code.

The goal is not to claim that all historical CI debt is already repaired. The goal is to make the current state explicit and make new silent drift fail closed.

## Machine authority

The machine-readable inventory is:

`docs/development/N3W_CI_POLICY_MANIFEST_V1.json`

The executable checker is:

`tools/n3w_ci_policy_check.py`

For CI execution policy, the manifest is the machine authority. Human-facing process documents explain the policy and carry the same revision marker, but they must not silently contradict or weaken the manifest.

## Required properties

The checker enforces:

1. every `.github/workflows/*.yml` or `*.yaml` file is registered;
2. stale manifest entries fail;
3. every entry has a valid class and Draft policy;
4. a new PR workflow cannot omit PR cancellation unless the debt is explicitly recorded;
5. a workflow cannot omit `timeout-minutes` unless the debt is explicitly recorded;
6. QEMU/Buildx work cannot be classified as Fast or Model;
7. QEMU/Buildx PR work must use the `ci-ready` gate or carry an explicit legacy-debt record;
8. `ci-ready` workflows must retain manual execution, main execution, Draft/Ready/label/body gate signals, PR cancellation and timeout;
9. obsolete exceptions fail after the implementation is repaired;
10. authority documents must carry the exact policy revision marker.

## Workflow classes

The V1 manifest uses:

- `FAST`: cheap static/unit/source checks;
- `MODEL`: host-only, isolated integration or model validation;
- `BUILD`: compile/build-oriented validation;
- `EVIDENCE`: artifact/evidence-oriented validation;
- `EXACT`: exact candidate/release-integrity validation;
- `LIVE`: reserved for workflows whose CI policy explicitly represents live execution authority.

Classification is not a claim that every historical workflow already has ideal scheduling. Historical gaps are represented as named exceptions.

## Explicit technical debt

Allowed V1 debt codes are:

- `missing_pr_cancel`;
- `missing_timeout`;
- `heavy_draft_execution`.

Each exception must include a concrete reason. Missing requirements without a recorded exception fail. Exceptions that become obsolete also fail, forcing the manifest to be cleaned up.

This makes debt visible and prevents silent expansion.

## CI-ready contract

Heavy exact closure uses repository-visible state rather than conversation state.

A gated Draft PR runs heavy work only when at least one of these is true:

- the PR is Ready for review;
- the `ci-ready` label is present;
- PR body contains `CI_READY=true`;
- the workflow is launched manually;
- the event is a qualifying main push.

The exact final evidence remains unchanged unless a separate reviewed policy revision explicitly changes it.

## Policy changes

A normative CI-policy change must update the policy revision deliberately when semantics change.

The manifest and all authority documents must carry:

`N3W_CI_POLICY_REVISION=N3W_CI_POLICY_V1_20261026`

The policy contract workflow watches the manifest, checker, tests, authority documents and controlled heavy workflows.

## Closure field

CI/process work that changes workflow behavior must report:

```text
CI_POLICY_ALIGNMENT=PASS|FAIL
```

A source or CI gate must not be declared closed when this checker reports FAIL.

## Safety boundary

This policy layer does not grant production authority. It does not authorize T1 access, board access, flashing, Broker mutation, service activation or merge.

```text
POLICY_AS_CODE=true
UNREGISTERED_WORKFLOW_FAIL_CLOSED=true
LEGACY_DEBT_EXPLICIT=true
NEW_SILENT_DEBT_ALLOWED=false
N3W_CI_POLICY_REVISION=N3W_CI_POLICY_V1_20261026
```
