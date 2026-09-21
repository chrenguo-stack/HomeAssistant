# N3-W PR #437 current-head physical closure and pre-merge review

Updated: 2026-09-21  
Status: `CURRENT_HEAD_PHYSICAL_CLOSURE_PREMERGE_PASS`

## Authority

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
PR=437
PR_STATE=OPEN_DRAFT
PR_MERGED=false

SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
SOURCE_CI=11_OF_11_PASS

EXACT_ARTIFACT_RUN=35553142523
EXACT_ARTIFACT_ID=10619047221
EXACT_ARCHIVE_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895
EXACT_APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
EXACT_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Fresh exact repository/runtime/physical evidence supersedes older snapshots where they conflict.

## Exact-head source review

The last formal source review before the final Wi-Fi recovery-budget repair was bound to
`177468e290a207f2fb7f6c554aedf60b61373b4d`.

Fresh comparison from that reviewed revision to current head `4270f24...` is:

```text
AHEAD_BY=4
BEHIND_BY=0
CHANGED_FILE_COUNT=2

firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.h
tests/n3w_phase4/n3w_direct_recovery_liveness_host_test.cpp
```

The product-source delta is limited to Direct-recovery budget constants and comments:

```text
NO_RELAY_WIFI_RECOVERY_BUDGET_MS=85000
NO_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=120000
HEALTHY_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=30000
MQTT_RECOVERY_BUDGET_MS=25000
DIRECT_CONFIRM_BUDGET_MS=5000
```

The corresponding host regression models the ESPHome 2026.4.3 sequential scan/connect fallback and preserves the 30 s healthy-Relay single-radio ownership ceiling. No queue ownership, ESP-NOW completion, Relay restore, callback-quiescence, Option-B one-attempt/no-resend, or Direct-commit ordering code changed in this final delta.

Current-head CI has 11 pull-request workflow runs and all 11 completed successfully. There are no unresolved inline review threads.

```text
FINAL_EXACT_HEAD_SOURCE_REVIEW=PASS
CURRENT_HEAD_CI=PASS
SOURCE_REVIEW_BLOCKER_COUNT=0
```

## Current-main integration review

At this review, current `main` is:

```text
MAIN=327b833de9e933efa0cbe8e6963cd63b9c69587d
PR_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
MERGE_BASE=d9afc55b04042806ed8b6e1b1ae3553742aba2be
PR_AHEAD_OF_MAIN=50
PR_BEHIND_MAIN=70
GITHUB_MERGEABLE=true
```

The branch is intentionally not rebased because the physical artifact is frozen to exact product source `4270f24...`. Fresh comparison shows the current-main-only side is repository hygiene, documentation, workflow retirement, and the exact Board-B writer package. It does not modify the PR #437 product-source files or tests listed in the current PR diff. Therefore the frozen product-source physical evidence remains attributable to `4270f24...`; documentation-only/main-side repository advancement does not redefine that product revision.

No rebase, merge, or Board/T1 mutation is part of this review.

## Exact current-artifact deployment and Direct baseline

The bound exact artifact was written to the operator-confirmed Board B target using the single-use writer. The authorization was consumed and must not be replayed.

The current-artifact Direct baseline then showed approximately 93 minutes of same-boot stable Direct operation:

```text
DIRECT_OBSERVATION_SECONDS=5601
DIRECT_EXPECTED_SEQUENCE_COUNT=1120
DIRECT_ACCEPTED_SEQUENCE_COUNT=1120
DIRECT_MISSING_SEQUENCE_COUNT=0
DIRECT_MAX_ACCEPTED_INTERARRIVAL_SECONDS=5.054
DIRECT_RUNTIME_STATUS=HEALTHY_DIRECT_CONTINUOUS
```

A separate pre-execution observer later stopped before movement because the boot session had advanced. That event is retained as an independent diagnostic. Its cause is not proven and it is not classified as a Direct/Relay transition failure. The final round-trip below established a fresh same-boot baseline after that stop.

## Same-boot Direct -> Relay

Fresh current-artifact physical evidence:

```text
PREMOVE_DIRECT_BASELINE=PASS
LAST_DIRECT_SEQ=72
FIRST_RELAY_SEQ=76
POST_RELAY_LAST_SEQ=78
POST_RELAY_ADVANCE_COUNT=2

MOVE_START_TO_FIRST_RELAY_MS=50721
MANAGER_VISIBLE_GAP_MS=21414

MISSING_SEQUENCE_COUNT=1
MISSING_SEQUENCE_RANGE=73

SAME_BOOT_DIRECT_TO_RELAY=true
MANAGER_CANONICAL_RELAY_ACCEPTANCE=PASS
DIRECT_TO_RELAY_FUNCTIONAL_RESULT=PASS
```

Durable replay proves seq 74 and 75 were accepted through Relay in a compressed ordered burst immediately after Relay became usable. Seq 73 is absent from durable replay and no Manager acceptance log exists for it.

Under the accepted Option-B contract, a sample that has not received a real business transport opportunity is held in the bounded RAM FIFO. Once a real Direct/Relay transport attempt occurs, failure does not become application-level retry. Therefore the single missing seq 73 is an important diagnostic but does not fail the current latest-state product contract. The exact device-side loss layer is not uniquely proven because no contemporaneous Board-B application serial history was captured.

```text
SEQ73_LOSS_ALLOWED_BY_OPTION_B_CONTRACT=true
END_TO_END_EVERY_SAMPLE_DELIVERY=false
```

## Relay continuity 600 s

Board B remained at the Relay location on the same boot:

```text
OBSERVATION_SECONDS=600
START_SEQ=100
END_SEQ=221
EXPECTED_ROW_COUNT=122
ACCEPTED_ROW_COUNT=122
MISSING_SEQUENCE_COUNT=0
SOURCE_NON_RELAY_OBSERVED=false

MAX_MANAGER_INTERARRIVAL_SECONDS=32.584
AVG_MANAGER_INTERARRIVAL_SECONDS=5.007

RELAY_DATA_CONTINUITY_600S=PASS
```

The longest Manager-visible pause was seq 130 -> 131. It was followed by seq 131..136 arriving in order at approximately 0.1-0.15 s spacing, with no missing sequence. This is strong physical evidence that telemetry generated while the single radio was temporarily owned by Direct recovery was held and then drained in order after Relay transport returned.

```text
ORDERED_BACKLOG_CATCHUP=PASS
TRANSITION_HOLD_BUFFER_PHYSICAL_EFFECTIVENESS=PASS
```

## Same-boot Relay -> Direct

Fresh current-artifact failback evidence:

```text
PREMOVE_RELAY_BASELINE=PASS
LAST_RELAY_SEQ=592
FIRST_DIRECT_SEQ=593
POST_DIRECT_LAST_SEQ=597
POST_DIRECT_ADVANCE_COUNT=2

MOVE_START_TO_FIRST_DIRECT_MS=76031
MANAGER_VISIBLE_FAILBACK_GAP_MS=21519

MISSING_SEQUENCE_COUNT=0
MISSING_SEQUENCE_RANGE=NONE

SAME_BOOT_RELAY_TO_DIRECT=true
RELAY_AFTER_FIRST_DIRECT_OBSERVED=false
MANAGER_CANONICAL_DIRECT_ACCEPTANCE=PASS
RELAY_TO_DIRECT_DATA_CONTINUITY=PASS
PR437_RELAY_TO_DIRECT_FAILBACK=PASS
```

Durable replay confirms the observer's rapid 593 -> 596 cursor jump did not lose seq 594/595; they were accepted between cursor samples.

## Manager stability and mutation boundary

Across the physical route:

```text
MANAGER_RESTART_COUNT=0
MANAGER_STARTED_AT_UNCHANGED=true

T1_RUNTIME_MUTATION=false
APPLICATION_SERIAL_OPEN=false
BOARD_FLASH_MUTATION_DURING_ROUTE=false
```

The only Board persistent mutation in this current-artifact route was the separately authorized and already consumed exact-artifact write before validation.

## Closure

Current exact-head evidence now satisfies the KF-096 repair gate:

```text
DIRECT_LONG_BASELINE=PASS
DIRECT_TO_RELAY_FUNCTIONAL=PASS
RELAY_CONTINUITY_600S=PASS
RELAY_TO_DIRECT_FAILBACK=PASS
SAME_BOOT_ROUND_TRIP=PASS
TRANSITION_HOLD_BUFFER_PHYSICAL_EFFECTIVENESS=PASS
MANAGER_RUNTIME_STABILITY=PASS

KF096_STATUS=CLOSED_PASS
KNOWN_FAILURE_KF096=GUARDED
PR437_CURRENT_HEAD_SOURCE_REVIEW=PASS
PR437_CURRENT_HEAD_CI=11_OF_11_PASS
PR437_PHYSICAL_ROUTE=PASS
PR437_MERGE_READY=true
```

`PR437_MERGE_READY=true` is a pre-merge evidence disposition, not merge authorization. PR #437 remains draft/open/unmerged until a separate explicit merge decision is given.

The reliability boundary remains unchanged: Option B is not end-to-end every-sample delivery. Future guaranteed durable delivery remains the separate Option-C architecture track.
