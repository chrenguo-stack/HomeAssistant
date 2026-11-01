# N3-W / P5 / M02 successor post-merge terminal handoff

Date: 2026-08-09

Status: `POSTMERGE_TERMINAL_ARCHIVE_PREPARED`

## Purpose

This document freezes the public, sanitized development handoff for the N3-W / P5 / M02 successor recovery after cumulative integration. It is an archive and review artifact only. It is not a physical, live-service, deployment, release, tag, or M03 authorization.

Preparation authorization:

`D1-N3W-P5-M02-SUCCESSOR-POSTMERGE-TERMINAL-ARCHIVE-AND-DEVELOPMENT-HANDOFF-PREPARATION-R1-EXACT-MAIN-433BF6E5B9C0363B95C747B0C4763EF4404184BC-PR292-PR296-CLOSURE-BOUND-PR276-PRESERVED-20260809-01`

## Exact repository binding

- Exact post-merge `main`: `433bf6e5b9c0363b95c747b0c4763ef4404184bc`.
- Exact pre-merge `main`: `8a57243fce0d347ebb20108f4ec5a2d5d4267486`.
- Cumulative integration PR: #296.
- Exact PR #296 head: `61f45f1476791aec303aa487af9000751fe2a994`.
- Integration method: merge commit.
- Integration branch remains preserved.

## Pull-request closure chain

| PR | Exact head | Terminal state |
| --- | --- | --- |
| #292 | `752c4709c6c9b60490dbcaf6da5807538dc03fa7` | closed / merged through PR #296 merge commit |
| #293 | `3f3ccf641a77ef7c9891373299b0e2d4abe4dd6b` | closed / not independently merged / superseded / branch preserved |
| #294 | `a2014677ea0449552f4f58fb0cca27a4f76e6542` | closed / not independently merged / superseded / branch preserved |
| #295 | `246160e98632806bf3ee249406e5d691cde7c1f6` | closed / not independently merged / superseded / branch preserved |
| #296 | `61f45f1476791aec303aa487af9000751fe2a994` | closed / merged as `433bf6e5b9c0363b95c747b0c4763ef4404184bc` |

PR #276 is intentionally outside this cumulative integration and remains preserved:

- state: open;
- merged: false;
- exact head: `239ea594c643d4990d449187f8b0cabae619e3d7`;
- exact base: `2d444f3e392249c8d7bf1a1aa036e738a418d1cb`.

## Public CI and evidence bindings

- PR #293: dedicated run `31270136039`, PASS at `3f3ccf641a77ef7c9891373299b0e2d4abe4dd6b`.
  - Public secret-free artifact ID: `9025351711`.
  - Public artifact digest: `sha256:8637cce425c453e86d17d4889b58807f50f98d032b88b64c7e1803a5f2fbf1b5`.
- PR #294: dedicated run `31292771162`, PASS at `a2014677ea0449552f4f58fb0cca27a4f76e6542`.
  - Public secret-free artifact ID: `9031937556`.
  - Public artifact digest: `sha256:6474d8fad7ba222bff4891fc6fe80d0534a20e224007febc1d476573ffa1276f`.
- PR #295: dedicated run `31304344487`, PASS at `246160e98632806bf3ee249406e5d691cde7c1f6`.
- PR #296: dedicated run `31308467411`, PASS at `61f45f1476791aec303aa487af9000751fe2a994`.
  - Public secret-free artifact ID: `9036679174`.
  - Public artifact digest: `sha256:11d1b66d12f444e23621f7e0cf20c83c3c124a225857f45fa334e8a6cf7b9c2c`.

The historical C06-B1 failures on PR #293 stopped at unrelated exact-scope gates. Their implementation and test steps did not run. The cumulative PR #296 lifecycle repair bound historical workflows to their exact PR context, and all applicable non-delegated checks passed.

## Development and validation closure

The successor chain closes the following development findings:

1. The Manager production image now carries the AEAD runtime dependency and exercises the real AES-GCM relay decrypt path.
2. Child relay-cache backpressure and sequence consumption are bounded; retry exhaustion discards the exact cache entry.
3. Relay sends an authenticated rejected receipt without false-positive forwarding acceptance.
4. Child and Relay reuse the connected STA channel for ESP-NOW initialization without attempting an invalid channel mutation or entering init/deinit churn.
5. The complete stacked implementation was integrated into `main` through PR #296 with exact ancestry and cumulative-scope validation.

Sanitized, previously published live-acceptance summary:

- both exact R5 Factory stages passed write, verify, and boot validation;
- ESP-NOW initialized while both roles remained connected as Wi-Fi stations;
- the separately authorized Relay-path acceptance window observed 24 gateway-ingress frames and 18 canonical telemetry messages;
- canonical boot-session continuity was preserved while sequence advanced from 143 to 167;
- active canonical transport was Relay;
- Manager AEAD failure signals were absent;
- Manager, Broker, and Home Assistant were neither modified nor restarted during that acceptance window.

The original R3 M02 terminal remains `CONSUMED_FAILED`, non-replayable, and historically preserved. This archive does not rewrite or replay it.

## Operator-state handoff

The last operator-confirmed state, not re-probed by this archive preparation, is:

- Child remains powered only by its unchanged direct Mac USB connection.
- Relay remains powered only by its direct Mac USB connection.
- Relay independent 5 V remains physically disconnected.
- No power or cable change was reported after the final accepted live sequence.

Any later power restoration, cabling change, board access, Flash, reset, serial access, or live path-control action requires a new explicit authorization and a fresh physical-state checkpoint.

## Public/private boundary

This public archive contains no:

- credentials, PMK, LMK, application key, session-floor secret, or private environment content;
- board MAC address or other private device-identity value;
- private evidence hash or private terminal transcript;
- current Factory-image hash or private execution-package hash;
- consumable or replayable physical authorization package.

Those bindings remain in the private handoff/evidence boundary and are not reproduced here.

## Safety and next gate

This preparation performed no board, USB, serial, Flash, erase, OTA, reset, power, MQTT publish, PATH RELAY, PATH DIRECT, live-service, production-network, deployment, release, or tag operation.

- M02 successor development integration: complete on exact `main`.
- M02 public terminal archive: prepared for review by this branch.
- PR #276: preserved and not folded into this closure.
- M03: prohibited and not authorized.
- Ready-for-review and merge of this archive remain separate authorization gates.
- Any next N3-W development target must begin with a fresh read-only drift review against the exact main then current.
