# N3-W F350 KF-060 Source Closure — 2026-08-24

## Purpose

This document closes the source-level regression item **KF-060: Manager DynSec provisioning rollback ownership** after the F3:50 FC4 Final Physical Acceptance archive was independently reviewed.

This closure is source/test/CI only. It does not replay or supersede the accepted physical result:

`FC4_FINAL_PHYSICAL_ACCEPTANCE=PASS`

No board access, USB/serial operation, reset, flash, NVS write, pairing replay, production Manager/Broker mutation, or physical acceptance replay was performed for this closure.

## Historical defect

The affected `DynsecProvisioner.provision()` implementation used attempt-started flags (`role_started` / `client_started`) as rollback ownership. A failed `createRole` or `createClient` caused by a pre-existing object could therefore enter a cleanup path that deleted an object not proven to have been created by the current transaction.

Epoch5 remained business-layer fail-closed and committed no valid credential. The later observed `client present / role absent` target state was highly consistent with this rollback-ownership defect, without proving the exact pre-state sequence.

## Source repair

PR #333, `fix(manager): guard DynSec rollback ownership`, implements the source/test guard:

- `role_created` / `client_created` become true only after the corresponding create call returns success;
- definitive create collisions roll back only objects proven created by the current transaction;
- post-publish uncertain outcomes are classified as `DynsecOutcomeUncertain`;
- uncertain outcomes inventory the exact target before cleanup and preserve objects whose ownership is not proven.

The regression matrix covers:

1. pre-existing role + client are both preserved;
2. pre-existing client + newly-created role preserves the client and removes only the new role;
3. pre-existing role + absent client is never deleted after a `createRole` collision;
4. a clean target provisions normally;
5. uncertain client success leaves the complete target for reconciliation;
6. uncertain client absence permits rollback only of the confirmed newly-created role.

## Repository lineage

The F350 archive PR #332 was merged first into `docs/n3w-fc4-development-artifact-archive-20260821`:

- PR #332 exact head: `4e6bd8e113f5982618b964b5a86f77ddfb8dc131`
- PR #332 merge commit: `2af36f81dc8c0696f28a09b3efe1d8150c0e2ff8`

PR #333 was then retargeted to that integration branch and rebound without content changes:

- pre-rebind source/test head: `88c23b9401eac3d27c21d06c6184d0e7c3df0397`
- exact rebind head: `3e38cf74b976e9810a4b87c25dc5364b1d8030c7`
- exact rebind tree: `fb321da628174151a1ec6c81b23aa5d18e63b1ca`
- PR #333 merge commit: `18d7975da2fbe60d1b22c2ce7970aba80b13c3ab`

The net PR #333 scope remained exactly four Manager source/test files.

## Exact-head CI closure

All 13 pull-request workflows on exact rebind head `3e38cf74b976e9810a4b87c25dc5364b1d8030c7` completed successfully. This included:

- greenhouse-manager CI;
- M2 Dynamic Security CI;
- M2 manager runtime secret ownership CI;
- M2 private Mosquitto CI;
- M2 node auth board lab CI;
- M2 node auth isolated lab CI;
- M2 node auth native board lab CI;
- M0 vertical slice CI;
- C-07 node retirement CI;
- H0/H1 initialization and portable restore CI;
- H3 N2 Stage2B3 Pairing Runtime CI;
- Project roadmap V0.7 and C-07 identity semantics;
- Public repository safety CI.

The M2 node auth board-lab run also completed both the minimal ESP32-C6 auth target and full RC2 product board target compilations successfully.

## Final classification

```text
KF_060_ROOT_CAUSE=CONFIRMED
KF_060_SOURCE_FIX=MERGED
KF_060_REGRESSION_GUARDS=PASS
KF_060_STATUS=GUARDED
FC4_FINAL_PHYSICAL_ACCEPTANCE=PASS
PHYSICAL_REPLAY=false
```

The historical F350 archive remains an account of the state at the time of its review. This source-closure record and `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` are the subsequent authority for KF-060's final guarded status.
