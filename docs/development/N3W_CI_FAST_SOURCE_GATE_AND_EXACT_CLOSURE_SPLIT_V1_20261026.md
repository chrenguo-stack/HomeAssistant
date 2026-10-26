# N3W CI Fast Source Gate and Exact Closure Split V1

Date: 2026-10-26

```text
TASK=N3W_CI_FAST_SOURCE_GATE_AND_EXACT_CLOSURE_SPLIT_V1
N3W_CI_POLICY_REVISION=N3W_CI_POLICY_V1_20261026
BASE_HEAD=507dbd49495c558b1344f7d713938b733b3bad18
BRANCH=ci/n3w-fast-source-gate-exact-closure-split-v1-20261026
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
MERGE=false
```

## 1. Problem

Recent N3W pull requests showed a recurring feedback-cost problem:

- a small Manager source/test correction can trigger many workflows;
- the ordinary Manager lint/test feedback is usually available within tens of seconds;
- exact ARM64 closure can take more than ten minutes;
- the exact ARM64 workflow uploads a multi-gigabyte artifact and downloads it again to prove post-upload byte continuity;
- fixed-source S20 image binding can rerun even when a current Manager edit cannot change its pinned Manager input.

The expensive checks are valuable final evidence. The problem is running them on every Draft PR edit.

This repair implements the project process rule that Fast, Build, Evidence and Candidate gates are separate. It does not weaken final exact-head evidence.

## 2. Gate contract

### Fast source gate

Draft PR updates continue to run the normal lightweight/applicable source checks, including Manager lint/tests, public repository safety and focused source contracts.

A Draft PR does not run the five heavy closure jobs in this repair unless an explicit full-gate signal is present.

### Exact closure gate activation

A heavy job runs when any one of these conditions is true:

1. event is not `pull_request` (for example main push or `workflow_dispatch`);
2. the PR is Ready for review;
3. the PR has label `ci-ready`;
4. the PR body contains the exact marker `CI_READY=true`.

The pull-request event set includes `edited`, `labeled`, `unlabeled`, `ready_for_review` and `converted_to_draft`, so changing the gate state is observable without a source edit.

`CI_READY=true` is a repository-visible control surface, not chat state. It should be added only after the applicable Fast Source Gate is green and removed when the candidate is no longer intended for full closure.

### Main and manual execution

Pushes to `main` remain governed by the existing path filters and are not suppressed by the Draft PR gate.

The heavy workflows support `workflow_dispatch` so an exact closure can be launched explicitly on a selected ref when needed.

## 3. Heavy workflows in V1

This V1 gates these expensive workflows:

- `N3W T1 fresh bootstrap deployable payload CI`
- `N3W T1 fresh install exact ARM64 CI`
- `N3W T1 production Manager state binding CI`
- `N3W T1 production stack staging payload CI`
- `N3W T1 S20 production image binding CI`

These workflows perform QEMU/ARM64, frozen-image, staging-payload or large-artifact work. Production Manager state binding was added after the repository-wide scan found its QEMU/frozen ARM64 path.

## 4. Exact ARM64 cheap-failure preflight

Before QEMU/buildx setup, `N3W T1 fresh install exact ARM64 CI` now runs:

- Manager development dependency install;
- `ruff check .`;
- full Manager `pytest -q`.

If this cheap source preflight fails, ARM64 image construction and artifact transfer do not start.

The final exact closure still retains:

- exact checkout binding;
- QEMU ARM64 execution;
- current Manager ARM64 image build;
- exact external Home Assistant and Mosquitto image binding;
- runtime validation;
- three-image artifact creation;
- artifact upload;
- artifact re-download;
- post-download SHA/binding validation.

## 5. Path-filter corrections

### Fresh install exact ARM64

The Manager image build consumes `Dockerfile`, `pyproject.toml`, `README.md` and `src/**`. The workflow no longer treats arbitrary `host/greenhouse-manager/tests/**` edits as Manager image inputs.

The isolated Home Assistant runtime test used by the workflow is explicitly included in its path filter.

### S20 production image binding

The workflow builds Manager from the immutable pinned source:

`MANAGER_SOURCE_SHA=511db028780988a7c07cb9342c8be507380bae0f`

Therefore current `host/greenhouse-manager/**` changes cannot alter that Manager build. That broad trigger is removed. The workflow still runs when its own workflow definition or relevant production infrastructure changes, and it can be run manually.

## 6. Cancellation

All five heavy workflows use PR-scoped `concurrency` with `cancel-in-progress`.

A newer head or gate-state transition cancels an obsolete run of the same heavy workflow for the same PR. Main runs are not cancelled by this PR policy.

## 7. Safety and evidence boundaries

This optimization does not:

- remove a final exact-head validation;
- remove ARM64/QEMU runtime proof;
- remove artifact upload/download byte-continuity proof;
- modify greenhouse-manager product source;
- modify firmware;
- access T1;
- access boards;
- start production services;
- weaken credential or repository safety checks.

The optimization changes when expensive evidence is produced, not what final evidence means.

## 8. Expected steady-state flow

```text
Draft PR update
  -> Fast Source Gate
  -> repair until fast green
  -> set CI_READY=true / ci-ready / Ready for review
  -> Exact Closure Gate
  -> freeze exact candidate
  -> closure review
  -> merge decision
```

A source change after full-gate activation remains eligible for the heavy workflows and therefore produces fresh exact-head evidence.

## 9. Regression guard

`tests/tools/test_n3w_ci_fast_source_gate_exact_closure.py` statically verifies:

- the five heavy workflows keep the explicit gate contract;
- manual and main execution remain available;
- PR concurrency cancellation remains present;
- exact ARM64 keeps its fast preflight and post-upload binding proof;
- S20 fixed-source binding does not regain the broad Manager trigger.

```text
LONG_TERM_POLICY=true
FAST_GATE_EVIDENCE_RETAINED=true
EXACT_CLOSURE_EVIDENCE_RETAINED=true
PRODUCT_RUNTIME_CHANGED=false
```
