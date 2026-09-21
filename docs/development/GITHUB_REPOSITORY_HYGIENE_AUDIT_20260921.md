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


## Remaining CI overlap / coverage audit

Read-only coverage review was completed after PR #451 at:

```text
MAIN_AFTER_PR451=85a9b9e8e48508350659afc7b748bd22117df9ca
WORKFLOW_FILES=37
OPEN_PRS=5
PR451_PREMERGE_CI=11_OF_11_PASS
```

### Required `protect-main` coverage

The active `protect-main` ruleset requires 13 status contexts. They are produced by 11 workflow files and must not be removed without an explicit ruleset migration:

```text
c07-node-retirement-ci.yml
  -> isolated-retirement

greenhouse-manager-ci.yml
  -> test

h3-n2-stage2b3-pairing-runtime-ci.yml
  -> isolated-runtime

m0-vertical-slice-ci.yml
  -> simulator-unit
  -> compose-integration

m2-dynsec-ci.yml
  -> dynsec-integration

m2-manager-runtime-secret-ownership-ci.yml
  -> ownership-gate

m2-node-auth-board-lab-ci.yml
  -> validate
  -> esp32-c6-board-targets

m2-node-auth-board-lab-native-ci.yml
  -> native-board-lab

m2-node-auth-isolated-lab-ci.yml
  -> isolated-broker-matrix

m2-private-mosquitto-ci.yml
  -> private-mosquitto

public-repository-safety-ci.yml
  -> tracked-content-safety
```

These 11 workflows are the reason a documentation-only PR still reports the full protected status set. Their presence is currently a branch-protection contract, not historical clutter.

### Non-required workflows retained after coverage review

The other 26 workflow files are not part of the required status-context set, but this audit did not find a high-confidence delete candidate among them.

They fall into these groups:

```text
C06 history / Home Assistant projection
  c06-history-replay-ci.yml
  c06b1-history-projection-ci.yml
  c06b2a-ha-target-ledger-ci.yml
  c06b2b-runtime-wiring-ci.yml

Firmware targets
  f1-0-rc2-ci.yml
  n1-firmware-ci.yml

Initialization / identity governance
  h0h1-init-portable-restore-ci.yml
  project-roadmap-v07-c07-identity-ci.yml

H3/N2 pairing and lifecycle focused regressions
  h3-n2-stage2c1-node-pairing-core-ci.yml
  h3-n2-stage2c2-node-secure-transport-ci.yml
  h3-n2-stage2c3-async-persistence-ci.yml
  h3-n2-stage2d1-crypto-output-safety-ci.yml
  h3-n2-stage2d1-nvs-persistence-ci.yml
  h3-n2-stage2d2-candidate-mqtt-validator-ci.yml
  h3-n2-stage2d3-activation-transaction-ci.yml
  h3-n2-stage2d4-profile-lifecycle-integration-ci.yml
  h3-n2-stage2d5-production-adapters-ci.yml
  h3-n2-stage2d6-lifecycle-assembly-ci.yml

Developer / M2 focused regressions
  local-dev-environment-tooling-ci.yml
  m2-esphome-node-auth-adapter-ci.yml
  m2-manager-failure-diagnostic-ci.yml

N3-W focused regressions / execution tooling
  n3w-boot-session-recovery-helper-ci.yml
  n3w-esp32c6-frame-boot-keystate-core-ci.yml
  n3w-kf096-pr437-boardb-write-executor-ci.yml
  n3w-manager-replay-registry-ci.yml
  n3w-single-hop-contract-ci.yml
```

### Important overlap findings

The audit found overlap, but not semantic duplication:

- `f1-0-rc2-ci.yml` and `n1-firmware-ci.yml` watch the same firmware tree, but build different configurations. The first uses `tools/rc2.sh` with the default `f1_0_rc2.yml`; the second prepares N1 CI secrets and uses `tools/n1.sh`, which binds `RC2_CONFIG=f1_0_rc2_n1.yml`.
- `h0h1-init-portable-restore-ci.yml` and `project-roadmap-v07-c07-identity-ci.yml` overlap on Manager / identity files, but the former runs initialization, portable-restore, persistence-migration and legacy-adoption harnesses while the latter enforces roadmap / retirement governance and identity-lifecycle tests.
- the Stage2C / Stage2D1-6 workflows share ESPHome setup and some source trees, but each owns a different focused contract, board-lab target or fault matrix. Consolidation is possible only by preserving those distinct checks in a matrix or reusable-workflow design.
- N3-W boot-session recovery and frame/keystate workflows share `greenhouse_n3w_core` source paths but validate different contracts and test suites.
- `n3w-kf096-pr437-boardb-write-executor-ci.yml` is intentionally task-specific and should be reconsidered only after PR #437 reaches final disposition.

### Third-pass decision

```text
THIRD_PASS_BLIND_WORKFLOW_DELETION=STOP
HIGH_CONFIDENCE_ADDITIONAL_DELETE_CANDIDATES=0
CURRENT_WORKFLOW_COUNT=37
REQUIRED_CONTEXT_WORKFLOWS=11
NON_REQUIRED_BUT_DISTINCT_WORKFLOWS=26
```

The repository has therefore reached the safe limit of name/age-based workflow cleanup.

Any further CI reduction should be an engineering refactor, not archival deletion. The most promising future direction is to consolidate repeated setup/compile scaffolding through reusable workflows while preserving the existing focused tests and, for protected checks, preserving or deliberately migrating the 13 required status contexts.

Branch-ref cleanup remains separately blocked by the current GitHub connector because it exposes branch creation/update but no safe remote-ref deletion operation. No force-update substitute should be used.
