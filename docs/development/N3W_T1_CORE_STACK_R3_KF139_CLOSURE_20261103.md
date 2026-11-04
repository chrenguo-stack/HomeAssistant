# N3-W T1 Core Stack R3 KF-139 closure — 2026-11-03

TASK=N3W_T1_CORE_STACK_R3_KF139_CLOSURE_ARCHIVE_AND_AUTHORITY_ALIGNMENT_20261103_01

## Final status

KF139_ROOT_CAUSE=PROVEN
KF139_SOURCE_REPAIR=PASS
KF139_REAL_T1_ISOLATED_VALIDATION=PASS
KF139_LIVE_REPAIR=PASS
KF139_R3_FIRST_REGISTRATION=PASS
KF139_OVERALL=CLOSED_PASS

## Root cause

The live T1 Manager created `credential-lifecycle.sqlite3` with mode 0644 through plain SQLite creation. Later, the dynamic 47112 pairing composition correctly required private database permissions and rejected that same DB with `SimplifiedProductRuntimeError`, producing E02 before 47112 could open.

## Source repair

PR #769 exact source-repair head:

`b863ddd959090ca139af76bd68dbef31d773e6de`

The repair creates a missing credential lifecycle DB as 0600 before SQLite opens it and explicitly preserves fail-closed behavior for pre-existing unsafe files. Existing unsafe files are not silently chmod-normalized by source code.

Exact Manager artifact:

- upstream run: 41583719655
- artifact: 13206763644
- artifact digest: sha256:eddeff81b3e670b66765558bb7e9795ae846caba6f487cfd6d727d5c0795403a
- Manager tar SHA256: ea158fbefe81084989941b951e0f5c8c65f630748c72bef3f8d03a1c453c328f
- image tag: local/greenhouse-manager:fresh-b863ddd95909

## Real-T1 isolated proof

The exact repaired Manager image was loaded on the real ARM64 T1 without changing production service bindings.

An isolated probe directory owned by 999:999 was used under `umask 000`.

Observed:

- created credential DB mode: 0600
- owner: 999:999
- existing `_ensure_private_database(Path(...))` gate: PASS
- production credential DB remained 0644 during this isolated proof
- production Manager and Home Assistant remained unchanged

This proves the source repair works in the real T1 Docker/ARM64 environment, not only in CI.

## Exact live repair

Execution/package PR #770 exact head:

`7dc77ff8e839613242819aaf35348dac05c88568`

Manager-only updater package:

- run: 41591610508
- artifact: 13209859306
- artifact digest: sha256:5e39b8b95dc55c19d1a3b8c1878c47b2765c426c2a09b169431d6df21aef9dc9
- updater pyz SHA256: 2e38c6c331b1275d609f805d0d22e158f3fc376ec1387e3453c8511667cf6f8a

Before live repair, the original 0644 DB was integrity-checked and backed up under a private forensic directory. The updater then committed the exact repaired Manager while preserving Broker continuity and leaving the Home Assistant image unchanged.

After Manager deployment:

- live Manager: local/greenhouse-manager:fresh-b863ddd95909
- restart_count: 0
- production credential DB: 0600 / 999:999
- live private-database gate: PASS
- unresolved first-registration count: 0
- historical attempts: 2 x EXPIRED / TERMINAL / COMPLETE
- pairing window: CLOSED
- 47112: CLOSED

## Final R3 first-registration acceptance

Exactly one post-repair first-registration attempt was executed.

Attempt #3:

- state: COMMITTED
- phase: TERMINAL
- cleanup_state: COMPLETE
- node_id: non-empty
- terminal_reason: null
- unresolved count: 0

Final durable state:

- registrations: 1
- node_id_leases: 1
- pairing_sessions: 1
- registration_events: 2
- credential lifecycle assignments: 1
- active credential generation: 1
- pairing window: CLOSED
- close_reason: committed
- failure_type: null
- 47112: CLOSED
- 47110: OPEN
- 47111: OPEN
- 8883: OPEN
- Manager restart_count: 0
- broker/services/registration-ingress-guard systemd units: active

## Historical rows

Attempts #1 and #2 remain `EXPIRED / TERMINAL / COMPLETE`. They are intentionally preserved durable replay tombstones. They must not be deleted to manufacture an empty ledger.

## Authority convergence

The closure originally stopped before merging PR #769/#770, leaving the repaired live runtime ahead of repository authority. The subsequently authorized stacked convergence upgrades canonical authority to schema `gh.n3w-t1-core-stack-current-authority/2` and binds it to the same repaired Manager:

- current product source: `b863ddd959090ca139af76bd68dbef31d773e6de`
- current Manager: `local/greenhouse-manager:fresh-b863ddd95909`
- immediate predecessor: `local/greenhouse-manager:fresh-3539c8f871e2`
- historical Clean Reference: unchanged at `local/greenhouse-manager:fresh-24382caae4a1`
- live/repository Manager authority: converged

Authority v2 intentionally removes dynamic zero-node inventory from the permanent current-stack contract. The stable acceptance authority is KF-139 CLOSED_PASS plus first-registration PASS, private-database gate PASS, committed pairing-window closure, and the exact Manager/package bindings.

`LIVE_RUNTIME_AHEAD_OF_CANONICAL_REPOSITORY_AUTHORITY=false`

NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_KF139_POST_MERGE_MAIN_READONLY_REBIND_20261103_01


## Post-merge main rebind and transition

```text
MAIN=e0841a5a43fd5847d5c5c40ab1cece42faedf3c8
MAIN_MERGE_TREE_DRIFT=ZERO
PR768_MERGED=true
PR769_MERGED=true
PR770_MERGED=true
PR771_MERGED=true
PR772_MERGED=true
POST_MERGE_READONLY_REBIND=PASS
KF139_OVERALL=CLOSED_PASS
CURRENT_BLOCKER_COUNT=0
NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_POST_REGISTRATION_PRODUCT_RUNTIME_BUSINESS_ACCEPTANCE_READONLY_PREFLIGHT_20261103_01
```

The KF-139/first-registration chain is complete. Follow-on work must not reopen or replay first registration merely to enter runtime acceptance. The next stage starts from the existing registered-node state and covers the downstream domains that the original R3 plan explicitly left out of first-registration acceptance: MQTT telemetry, Home Assistant discovery/entities, Direct/Relay failover, sensor measurements and longer runtime stability. The first gate in that stage is read-only.
