# GitHub Repository Hygiene Audit — 2026-09-21

## Scope

Repository-only housekeeping for `chrenguo-stack/HomeAssistant`.

This work does not change product firmware, Board state, T1, Broker, Manager runtime, credentials, NVS, or physical-test authority.

## Exact audit baseline

```text
MAIN=f9df51171d3fac20d64ccff5202faf43926f26f6
OPEN_PRS_BEFORE=79
DRAFT_PRS_BEFORE=73
REMOTE_BRANCHES=494
WORKFLOW_FILES_BEFORE=53
```

The main branch is protected by the active repository ruleset `protect-main` (ruleset ID `20514758`) targeting the default branch. It blocks deletion and non-fast-forward updates, requires pull requests, requires review-thread resolution, allows merge commits, and requires 13 named CI status checks. The classic branch-protection endpoint is not readable through the current GitHub App connection, so ruleset data is the authoritative protection evidence used here.

## Pull-request cleanup completed

The active PR list was reduced from 79 to 5 by closing historical/superseded PRs while retaining their branches and Git history.

Closed groups:

- PR #442 — superseded by PR #447 working-context alignment.
- PR #446 — bound to historical PR #437 source/artifact `b289041...`.
- 41 inactive H3/N2 Stage2D Draft PRs from July 2026.
- 5 old N3-W archival/physical-stage Draft PRs: #302, #303, #304, #306, #321.
- PR #412 — head already fully contained in current main.
- KF-089 historical execution/acceptance chain #389–#405.
- Historical/superseded PRs #178, #179, #182, #216, #355, #361, #367, #387.

Remaining open PRs after cleanup:

```text
#447 docs(n3w): align PR437 Wi-Fi recovery repair and working context
#437 fix(n3w): harden KF-096 Direct recovery liveness and deadline commit
#388 docs(process): replace handoff DSL execution with versioned execution packages
#385 feat(n3w): OTA Guard review + identity repair; post-mutation repair pending
#127 docs(m3): define host golden image and firstboot provisioning
```

These remain open because they still represent current work, a current process candidate, unresolved follow-up, or a future product track.

## Branch cleanup status

494 remote branches existed at audit time.

Branch deletion was intentionally not performed in this pass. Closing a PR is reversible and preserves branch history. Before deleting remote refs, each branch should be proven to be either:

1. fully reachable from current main or an intentional archive ref; or
2. a temporary branch whose unique commits are no longer required.

Obvious temporary deletion candidates include:

```text
tmp/n3w-s4-pr319-rebaseline-materialize-20260814
tmp-do-not-use
tmp-do-not-use-2
tmp-do-not-use-3
tmp-do-not-use-4
tmp-do-not-use-5
```

## Workflow cleanup — first pass

PR #448 retired one-off, stage-bound workflow files whose associated execution chains are already historical/closed:

```text
.github/workflows/h3-n2-stage2d7-2d8-g2-integration-ci.yml
.github/workflows/h3-n2-stage2d8-dedicated-board-g2-v64-ci.yml
.github/workflows/h3-n2-stage2d9-g3-v67-artifact-ci.yml
.github/workflows/h3-n2-stage2d9-g3-v68-artifact-ci.yml
.github/workflows/h3-n2-stage2d9-g3-v69-artifact-ci.yml
.github/workflows/h3-n2-stage2d9-g3-v69-correction-ci.yml
.github/workflows/h3-n2-stage2d9r-g3r-d2-17-g18-main-integration-review-ci-v1.yml
.github/workflows/n3w-kf089-id23-t1-dynsec-relay-acl-readonly-forensic-ci.yml
.github/workflows/n3w-kf089-id24-manager-relay-dynsec-acl-repair-ci.yml
.github/workflows/n3w-kf089-id25-manager-relay-subscription-reactivation-ci.yml
.github/workflows/n3w-kf089-id26-minimal-end-to-end-relay-revalidation-ci.yml
```

The Stage2D7-2D8 integration gate was added to the retirement set after the first PR #448 CI run proved it is tied to frozen July ancestry. Its first step requires historical evidence/union commits to be ancestors of the current PR merge commit; current main does not contain those frozen branch commits, so it is not a valid long-lived current-main check.

## Workflow cleanup — second pass

The second read-only classification found another small high-confidence historical set:

```text
.github/workflows/h3-n2-stage2d7-isolated-acceptance-ci.yml
.github/workflows/h3-n2-stage2d8-isolated-device-driver-ci.yml
.github/workflows/h3-n2-stage2d9-g3-compile-ci.yml
.github/workflows/h3-n2-stage2d9-g3-prepare-ci.yml
.github/workflows/m401a-mosquitto-relay.yml
```

Reasons:

- the Stage2D7/8/9 workflows target July-only isolated lab components, board-lab YAMLs, historical acceptance documents, and stage-specific tools/tests;
- repository search did not show those isolated Stage2D7/8/9 components in current product runtime configuration;
- none of these workflow job contexts is one of the 13 required checks in the active `protect-main` ruleset;
- `m401a-mosquitto-relay.yml` is a manual-only workflow that creates the historical acceptance-only `m401a-mosquitto-relay-20260720` ARM64 archive/release.

The underlying source, tests, documents, releases, workflow-run history, and Git commits remain preserved. This pass removes only the active workflow entry points.

Long-lived path-specific regression workflows for current pairing, persistence, lifecycle, firmware, Manager, N3-W, identity, and public-safety code remain in place.

## Deferred cleanup

The following require a separate focused review rather than blind deletion:

- branch refs;
- deeper consolidation of overlapping long-lived CI rather than deletion by name/age;
- `docs/development` historical document consolidation;
- repository setting `delete_branch_on_merge`;
- periodic review of the active `protect-main` ruleset and its 13 required CI checks as CI is consolidated.

## Safety rule

Repository cleanup must not change the current PR #437 source/physical authority, rebuild or flash firmware, or delete unique unmerged product source merely to reduce branch/PR counts.

## Post-merge verification

```text
PR448_MERGED=true
PR448_MERGE_COMMIT=5afdd83c022585a2fb04b46d71e9114a46d35e07
WORKFLOW_FILES_AFTER_PR448=42
OPEN_PRS_AFTER_PR448=5

PR449_MERGED=true
PR449_MERGE_COMMIT=4bdaa9e347709da9f1307bfd3ba22d46913c15f1
```

The first PR #448 run exposed one stale July integration gate; after retiring that gate, the exact PR head `10e8fde28f28f54cf124ddeb2bc0b36d4498eff9` completed 11/11 CI successfully before merge.


## Second-pass merge verification

```text
PR450_MERGED=true
PR450_MERGE_COMMIT=e369a14544c0d5ba7d3e6e01e4af38c06892a3a7
WORKFLOW_FILES_AFTER_PR450=37
OPEN_PRS_AFTER_PR450=5
PR450_PREMERGE_CI=11_OF_11_PASS
```

The remaining 37 workflows were reclassified after PR #450. No further workflow deletion is proposed by name or age alone: the remaining older H3/N2 Stage2C/Stage2D1-6 workflows still target pairing, persistence, activation, lifecycle, firmware or other code paths that remain present in the repository, and several current workflows provide required `protect-main` status contexts. Further reduction therefore requires overlap/coverage analysis rather than historical cleanup.
