# N3-W / FC4 Historical PR Cleanup Archive — 2026-08-31

## 1. Purpose

This document is the public-safe cleanup record created after N3-W / FC4 Final Physical Acceptance and the final integration to `main` completed.

It preserves the disposition of superseded historical FC4 pull requests and branch lineages without replaying old execution authorities, restoring stale runtime state, or re-opening any physical gate.

This cleanup is repository-only. It performs no Manager/Broker/Home Assistant mutation, no Dynamic Security mutation, no credential operation, and no ESP32-C6 board/USB/serial/Flash/NVS action.

## 2. Canonical authority at cleanup start

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=PASS
FC4_GITHUB_DELIVERY_TO_MAIN=COMPLETE
MAIN_HEAD=83f046b2ab19071bc91d33b099b3d51164b2e8f0
FINAL_CLOSURE_DOC=docs/development/N3W_FC4_FINAL_PHYSICAL_ACCEPTANCE_CLOSURE_V1.0_20260831.md
```

The historical PRs listed below are not product authority and must not replace the final `main` state.

## 3. Superseded historical PR disposition

### PR #337 — Navigator route guard

- Title: `docs: add Navigator development route guard`
- Head: `672c642382df490c44e0ccc43a5932a1b47b3e49`
- Historical file:
  - `docs/development/Navigator_DEVELOPMENT_ROUTE_GUARD.md`
- Disposition: `CLOSE_AS_HISTORICAL_SUPERSEDED`
- Reason: the route-guard concept remains useful historically, but its active FC4 route state predates final physical-acceptance completion and is not current authority.

### PR #338 — New-chat handoff standard / Codex DSL process

- Title: `docs: standardize new-chat handoffs and Codex DSL execution`
- Head: `4300890dff0ce63d5a547df21426e287d084d9ee`
- Historical files:
  - `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`
  - `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`
  - historical edits to `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
- Disposition: `CLOSE_AS_HISTORICAL_SUPERSEDED`
- Reason: the process ideas are preserved by this PR/commit lineage, but its old Known-Failure allocation must not overwrite the current canonical index.

### PR #339 — Project development history reference

- Title: `docs: add project development history reference`
- Head: `0d7aa0698fd96eb6491c71505935b9a35b18e77b`
- Historical file:
  - `docs/development/PROJECT_DEVELOPMENT_HISTORY_REFERENCE_V1.0_20260827.md`
- Disposition: `CLOSE_AS_HISTORICAL_REFERENCE`
- Reason: useful historical reference, but it stops before the final FC4 acceptance closure and therefore is not a current route/status authority.

### PR #340 — R2C4E first-registration failure archive

- Title: `docs(fc4): archive R2C4E first-registration failures`
- Head: `064b615a206f6002f96531061d0111070fe48e01`
- Historical files:
  - `docs/development/FC4_R2C4E_FIRST_REGISTRATION_FAILURES_20260828.md`
  - historical edits to `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
- Disposition: `CLOSE_AS_SUPERSEDED_INCIDENT_ARCHIVE`
- Reason: the incident remains historically valid, but its KF numbering collided with later allocations and its route state was superseded by the completed registration/acceptance chain.

### PR #341 — R1-V2B through S1-F1 runtime convergence archive

- Title: `docs(fc4): archive R1-V2B through S1-F1 convergence`
- Head: `2ee977ab457b9526b0ad9837fd37bbabdda30989`
- Historical files:
  - `docs/development/FC4_R1V2C_S1F1_KNOWN_FAILURES_ADDENDUM_20260826.md`
  - `docs/development/archives/N3W_FC4_R1V2B_TO_S1F1_RUNTIME_CONVERGENCE_ARCHIVE_20260826.md`
  - `docs/development/handoffs/N3W_FC4_R1V2C_S1F1_NEW_CHAT_HANDOFF_V1.0_20260826.md`
- Disposition: `CLOSE_AS_HISTORICAL_SUPERSEDED`
- Reason: preserved as recovery history; later Spare-T1 convergence and FC4 final physical acceptance supersede its next-route state.

### PR #342 — Spare-T1 current-main convergence archive

- Title: `docs(fc4): archive Spare T1 current-main convergence`
- Head: `5b128b9501a4758a7813efed33887342ae1b81d6`
- Historical files:
  - `docs/development/N3W_FC4_SPARE_T1_CURRENT_MAIN_CONVERGENCE_ARCHIVE_20260828.md`
  - `docs/development/N3W_FC4_SPARE_T1_KNOWN_FAILURES_ADDENDUM_20260828.md`
- Disposition: `CLOSE_AS_HISTORICAL_SUPERSEDED`
- Reason: the convergence result is historical evidence; provisional `ST1-RG-*` identifiers and old route text are not canonical after final acceptance.

### PR #343 — S2R2 recovery and live-convergence handoff

- Title: `docs(n3w): archive FC4 S2R2 recovery and live-convergence handoff`
- Head: `3465200e5d9d05825395dbd30590ad1399fe64d8`
- Historical files:
  - `docs/development/N3W_FC4_S2R2_KNOWN_FAILURES_ADDENDUM_V1.0_20260826.md`
  - `docs/development/N3W_FC4_S2R2_LIVE_CONVERGENCE_HANDOFF_PUBLIC_V1.0_20260826.md`
  - `docs/development/N3W_FC4_S2R2_RUNTIME_RECOVERY_ARCHIVE_V1.0_20260826.md`
- Disposition: `CLOSE_AS_HISTORICAL_SUPERSEDED`
- Reason: later Manager/runtime convergence, Board C registration, TLS repair, HA DynSec repair, and final acceptance completed the route.

### PR #344 — PR-scope / provenance Known-Failure guards

- Title: `docs: add PR scope and artifact provenance regression guards`
- Head: `265e98aa4297da778a3420453ea682d9ee29e4ba`
- Historical file:
  - historical edits to `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
- Disposition: `CLOSE_WITHOUT_MERGE_KF_COLLISION`
- Reason: the concepts remain historically relevant, but its `KF-068` / `KF-069` numbering conflicts with later canonical FC4 allocations and must not be merged over the current index.

## 4. Branch cleanup inventory

The following branches were proven to be fully contained by current `main` and have no unique content required for product authority:

```text
integration/n3w-fc4-final-main-20260831
fix/fc4-boardc-p9-setup-secret-capture-risk-20260828
fix/n3w-fc4-boardc-tls-server-name-20260830
docs/fc4-r6-preauth-authority-archive-20260828
docs/n3w-fc4-boardc-handoff-20260829
fix/n3w-fc4-udp-broadcast-discovery-20260820
```

They are safe branch-deletion candidates after repository tooling exposes a delete-ref operation.

The following durable archive branches are intentionally retained:

```text
archive/n3w-fc4-final-physical-acceptance-closure-20260831
archive/n3w-fc4-tls-source-repair-20260831
archive/fc4-historical-pr-cleanup-20260831
```

`docs/n3w-fc4-boardc-recapture-handoff-20260829` is not deleted by this cleanup because it retains a divergent historical lineage.

## 5. Cleanup rules frozen

1. Closing an obsolete historical PR does not invalidate its historical evidence.
2. Closed PR heads and commits remain historical references, not current product authority.
3. No old authorization, request, credential, private package, successor runtime, or physical gate is made replayable by cleanup.
4. The canonical Known-Failure index is the version reachable from current `main`; conflicting historical KF allocations are not merged.
5. The final product authority remains the completed FC4 acceptance state integrated through PR #348.
6. Any future development starts from current `main`, not from one of the historical FC4 PR heads listed above.

## 6. Cleanup closure target

```text
HISTORICAL_PR_337_344_ARCHIVED=true
HISTORICAL_PR_337_344_MERGE_REQUIRED=false
HISTORICAL_PR_337_344_CLOSE_ALLOWED=true
FC4_PRODUCT_RUNTIME_MUTATION=false
BOARD_ACTION=false
FINAL_MAIN_AUTHORITY_PRESERVED=true
```
