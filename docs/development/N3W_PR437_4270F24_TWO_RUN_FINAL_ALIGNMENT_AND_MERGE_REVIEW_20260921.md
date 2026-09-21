# N3-W PR #437 two-run final alignment and merge-condition review

Updated: 2026-09-21  
Status: `PREMERGE_FINAL_REVIEW_PASS`

## Authority

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
PR=437
SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
CURRENT_HEAD_CI=11_OF_11_PASS

EXACT_ARTIFACT_RUN=35553142523
EXACT_ARTIFACT_ID=10619047221
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
ARCHIVE_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895
```

Fresh exact repository/runtime/physical evidence overrides older snapshots where they conflict.

## Two-run physical result

Both runs used the same deployed current-head artifact and completed Direct -> Relay -> Direct without Board reboot, Board flash, application serial access, or T1 runtime mutation during the route.

### Run 1

```text
DIRECT_TO_RELAY=PASS
DIRECT_TO_RELAY_MANAGER_VISIBLE_GAP_MS=21414
DIRECT_TO_RELAY_MOVE_TO_FIRST_RELAY_MS=50721
DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=1
DIRECT_TO_RELAY_MISSING_SEQUENCE_RANGE=73

RELAY_CONTINUITY_600S=PASS
RELAY_CONTINUITY_RANGE=100-221
RELAY_CONTINUITY_EXPECTED=122
RELAY_CONTINUITY_ACCEPTED=122
RELAY_CONTINUITY_MISSING=0
RELAY_MAX_MANAGER_INTERARRIVAL_SECONDS=32.584

RELAY_TO_DIRECT=PASS
RELAY_TO_DIRECT_MANAGER_VISIBLE_GAP_MS=21519
RELAY_TO_DIRECT_MOVE_TO_FIRST_DIRECT_MS=76031
RELAY_TO_DIRECT_MISSING_SEQUENCE_COUNT=0
```

### Run 2

```text
DIRECT_TO_RELAY=PASS
DIRECT_TO_RELAY_MANAGER_VISIBLE_GAP_MS=30686
DIRECT_TO_RELAY_MOVE_TO_FIRST_RELAY_MS=39779
DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=3
DIRECT_TO_RELAY_MISSING_SEQUENCE_RANGE=815-817

RELAY_CONTINUITY_600S=PASS
RELAY_CONTINUITY_RANGE=863-983
RELAY_CONTINUITY_EXPECTED=121
RELAY_CONTINUITY_ACCEPTED=121
RELAY_CONTINUITY_MISSING=0
RELAY_MAX_MANAGER_INTERARRIVAL_SECONDS=32.451

RELAY_TO_DIRECT=PASS
RELAY_TO_DIRECT_MANAGER_VISIBLE_GAP_MS=17619
RELAY_TO_DIRECT_MOVE_TO_FIRST_DIRECT_MS=61752
RELAY_TO_DIRECT_MISSING_SEQUENCE_COUNT=0
```

Manager remained running with restart count 0 and unchanged StartedAt in both routes.

## Repeatability conclusions

```text
DIRECT_TO_RELAY_FUNCTIONAL_SWITCH=REPEATABLE_PASS
DIRECT_TO_RELAY_ZERO_LOSS=NOT_GUARANTEED
DIRECT_TO_RELAY_BOUNDARY_LOSS=REPEATABLE

RELAY_STEADY_STATE_600S=REPEATABLE_PASS
RELAY_STEADY_STATE_ZERO_LOSS=REPEATABLE_PASS
HEALTHY_RELAY_DIRECT_RECOVERY_PAUSE_AROUND_32_5S=REPEATABLE
ORDERED_BACKLOG_CATCHUP=REPEATABLE_PASS

RELAY_TO_DIRECT_FAILBACK=REPEATABLE_PASS
RELAY_TO_DIRECT_MEASURED_ZERO_LOSS=REPEATABLE_PASS

SAME_BOOT_FULL_ROUND_TRIP=REPEATABLE_PASS
MANAGER_RUNTIME_STABILITY=REPEATABLE_PASS
```

The two independent Relay windows show nearly identical maximum Manager interarrival pauses, 32.584 s and 32.451 s, while retaining every sequence. This is strong physical evidence that the healthy-Relay Direct-recovery ownership interval is bounded and that the Option-B RAM FIFO preserves and drains telemetry generated while the single radio is temporarily unavailable to Relay transport.

The two Direct -> Relay transitions both lost durable sequence(s): one sample in run 1 and three consecutive samples in run 2. This is therefore a repeatable transition-boundary characteristic, not an isolated event.

Under the accepted Option-B latest-state contract, this does not fail PR #437: samples with no real business transport opportunity are held, but once a real transport attempt occurs there is no application-level resend or Manager durable ACK. Therefore PR #437 does not claim end-to-end every-sample delivery. A future requirement for guaranteed delivery belongs to the separate Option-C durable outbox/ACK architecture.

## Merge-condition review

Fresh GitHub read-back before this review:

```text
PR437_STATE=OPEN
PR437_DRAFT=true
PR437_MERGED=false
PR437_MERGEABLE=true
PR437_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENT_MAIN=3fa4cbe05b74847e6998bd43f4ffe062eb5ae4ee
PR437_AHEAD_OF_MAIN=50
PR437_BEHIND_MAIN=75
MERGE_BASE=d9afc55b04042806ed8b6e1b1ae3553742aba2be
UNRESOLVED_REVIEW_THREAD_COUNT=0
```

The branch remains intentionally unre-based because exact physical evidence is bound to source head `4270f24...`. Current-main advancement is repository/documentation/execution-package work and GitHub reports the PR mergeable. The exact current-head source review is PASS and all 11 current-head PR workflow runs are successful.

Merge conditions:

```text
EXACT_SOURCE_REVIEW=PASS
CURRENT_HEAD_CI=PASS
EXACT_ARTIFACT_BINDING=PASS
BOARD_B_DEPLOYMENT=PASS
TWO_RUN_PHYSICAL_REVALIDATION=PASS
KF096_STATUS=CLOSED_PASS
KNOWN_FAILURE_KF096=GUARDED
UNRESOLVED_REVIEW_THREADS=0
GITHUB_MERGEABLE=true

PR437_MERGE_CONDITION_REVIEW=PASS
PR437_MERGE_READY=true
```

The operator explicitly authorized completion of this review followed by merging PR #437. The merge must still use an exact-head guard so any head movement fails closed.
