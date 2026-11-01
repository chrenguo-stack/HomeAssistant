# N3-W P5 phase-exit blocker status rebaseline

Date: 2026-08-09

Status: `N3W_PHASE_EXIT_BLOCKED_M03_PROHIBITED`

## Authorization and scope

Prepared under:

`D1-N3W-P5-M02-SUCCESSOR-N3W-PHASE-EXIT-BLOCKER-STATUS-REBASELINE-AND-PR276-SUPERSEDED-CLOSURE-RECOMMENDATION-PREPARATION-R1-EXACT-MAIN-1C4D45F9CF9FE76865BDF58BD57CDBAB96586343-EXACT-PR276-HEAD-239EA594C643D4990D449187F8B0CABAE619E3D7-M03-PROHIBITED-NO-LIVE-NO-PACKAGE-20260809-01`

This is a public, read-only-derived status rebaseline and closure recommendation. It is not an M03 package, physical authorization, path-control authorization, PR #276 mutation, Ready, merge, release, tag, or deployment authorization.

## Exact repository state

- exact main: `1c4d45f9cf9fe76865bdf58bd57cdbab96586343`;
- PR #297: merged as exact main `1c4d45f9cf9fe76865bdf58bd57cdbab96586343`;
- PR #297 exact head: `9c6758b783844e70a2635f370e0466ca96c58944`;
- PR #276: open, not merged;
- PR #276 exact head: `239ea594c643d4990d449187f8b0cabae619e3d7`;
- PR #276 exact head is an ancestor of current main;
- current main is 149 commits ahead of PR #276 head and 0 commits behind;
- PR #276 is the only open pull request found by the N3-W repository query.

## Completed closure

The N3-W / P5 / M02 successor chain is closed on main:

- Manager production AEAD dependency and real relay decrypt path repaired;
- Child relay-cache backpressure and sequence consumption bounded;
- connected-STA ESP-NOW initialization repaired;
- Relay Factory and Child Factory stages passed under their separate exact authorizations;
- the separately authorized M02 Direct-to-Relay real-AEAD canonical-continuity acceptance passed;
- cumulative implementation integrated through PR #296;
- sanitized terminal archive integrated through PR #297.

The original R3 M02 terminal remains `CONSUMED_FAILED`, non-replayable, and historically preserved.

## N3-W phase-exit decision

The V0.7 N3-W exit condition requires ESP-NOW single-hop path lease and switching to demonstrate no duplicate device and no canonical rollback.

The public P5 execution matrix remains M01 through M14. This rebaseline has an exact terminal closure for M02, but it does not contain terminal execution evidence for the remaining matrix:

- M03: Relay-to-Direct path return and bounded old-path grace;
- M04: duplicate handling;
- M05: reorder handling;
- M06: late old-frame rollback rejection;
- M07: Child restart;
- M08: Relay restart;
- M09: Manager restart;
- M10–M11: authorization revoke and regrant;
- M12: key rotation;
- M13: Broker outage and recovery;
- M14: Home Assistant identity continuity.

Therefore:

- `N3W_PHASE_EXIT_READY=false`;
- `NEXT_REQUIRED_PHYSICAL_MATRIX=M03`;
- M03 remains prohibited;
- no M03 execution package may be generated, claimed, or executed by this status work;
- M04–M14 must not be skipped or claimed complete from M02 evidence.

## PR #276 superseded closure recommendation

PR #276 introduced the N3-W single-hop contract and host-only ingress model. Its exact head is already an ancestor of current main, and the later main lineage contains the production Manager, firmware, P5 validation, cumulative integration, and terminal archive successors.

Recommended disposition under a separate authorization:

1. add a sanitized superseded-closure status to PR #276;
2. close PR #276 without independently merging it;
3. preserve its head branch;
4. record that its contribution is present in current main through the successor lineage;
5. do not delete any N3-W branch;
6. do not treat closure as M03 or N3-W phase-exit authorization.

This preparation does not modify or close PR #276.

## Safety boundary

This work performs no board, USB, serial, Flash, erase, OTA, reset, power, MQTT publish, PATH RELAY, PATH DIRECT, live-service, production-network, deployment, release, tag, or M03 action.

It contains no credentials, board MAC, private evidence hash, Factory-image hash, private package hash, terminal transcript, or replayable authorization.

## Next gate

The immediate governance gate is review of this exact status rebaseline and the PR #276 superseded-closure recommendation.

The next substantive physical matrix remains M03, but it cannot begin unless the existing M03 prohibition is separately and explicitly lifted by a new exact authorization after a fresh physical-state and drift review.
