# N3-W Production Multi-Relay Gateway Selection V1 Progress Alignment

Date: 2026-09-24

## Scope

This public-safe alignment freezes the repository/runtime handoff point immediately before the three-board Direct baseline for Production Multi-Relay Gateway Selection V1.

No raw MAC, NODE_ID, pairing ID, Setup Secret, MQTT credential, application key, T1 locator, USB device path, or private log is included.

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_HEAD_AT_ALIGNMENT=b32878682ab4981fd38b8982caefed95ba3e204d
WORK_BRANCH=exec/n3w-pr437-board-a-same-artifact-role-swap-20260922
PR=471
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_MERGEABLE=true
ALIGNMENT_INPUT_BRANCH_HEAD=91fc6f50f14143b9050f55263b7e99ed572d7c20
BRANCH_AHEAD_OF_MAIN=65
BRANCH_BEHIND_MAIN=6
```

The branch is intentionally not merged by this alignment. The current PR contains the historical Board A/B role-swap evidence, the ESP32-C6 write runbook, and the replacement Board C onboarding closure.

At the input head, all discovered pull-request workflow runs were completed successfully, including Public repository safety CI, greenhouse-manager CI and the Board-A same-artifact write executor CI.

## Frozen Production Multi-Relay firmware authority

```text
SOURCE_COMMIT=8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
EXACT_ARTIFACT_ID=10693728323
EXACT_ARTIFACT_OUTER_SHA256=e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814
FIRMWARE_SHA256=c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a
```

## Replacement Board C closure

```text
NEW_BOARD_C_HARDWARE_ID_SHA256=f972633ca16463c8324a6921b60a2916c71bc9cab102333049d56449005b636b
NEW_BOARD_C_NODE_ID_SHA256=a205b76cfbb7db6816ce476432e024fb796f5a2f1ba698d3ec8616a79b419f09
OLD_BOARD_C_NODE_ID_SHA256=73cd4e91562d425ec90acd114b622ee448680b5e011742744eb15fe54e9dd497
OLD_BOARD_C_NODE_ID_REUSED=false

REGISTRATION_STATE=approved
CREDENTIAL_STATE=active
CREDENTIAL_ACTIVE_GENERATION=1
CREDENTIAL_PENDING_GENERATION=NONE

APPLICATION_KEY_NODE_ACTIVE=true
APPLICATION_KEY_ACTIVE_COUNT=1
APPLICATION_KEY_MAX_EPOCH=1

CANONICAL_SEQ_BEFORE=15
CANONICAL_SEQ_AFTER=16
CANONICAL_SAME_BOOT=true
CANONICAL_CURSOR_ADVANCED=true
CANONICAL_LAST_SOURCE_DIRECT=true
REGISTRATION_STABLE_AFTER_60S=true

MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_RESTART_COUNT_UNCHANGED=true

NEW_BOARD_C_POST_REGISTRATION_READONLY_CLOSURE=PASS
PAIRING_SERIAL_QUIESCENCE=NOT_TESTED
```

Authority:
`docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_NEW_BOARD_C_ONBOARDING_CLOSURE_20260924.md`

## Pairing incident disposition

The replacement Board C onboarding re-encountered already-recorded harness classes around pairing TTL and executor transport. The relevant guards remain KF-044, KF-061, KF-062, KF-072 and KF-078.

```text
NEW_PRODUCT_DEFECT_PROVEN=false
SETUP_SECRET_REIMPORT_REQUIRED=false
PAIRING_REPLAY_REQUIRED=false
NVS_ERASE_REQUIRED=false
FIRMWARE_REWRITE_REQUIRED=false
```

Durable `approved` registration state is authoritative. Do not replay uncertain sensitive operations merely to reconstruct which earlier executor invocation completed them.

## Superseding physical-acceptance authority

The earlier alignment text below was written before the later frozen R0-R7 operator plan was recovered. Where the two conflict, this section and the frozen plan below are authoritative.

```text
PHYSICAL_PLAN_AUTHORITY=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_ACCEPTANCE_R0_R7_FROZEN_PLAN_20260923.md

BOARD_A_ROLE=CHILD_UNDER_TEST
BOARD_B_ROLE=RELAY_GATEWAY_CANDIDATE
BOARD_C_ROLE=RELAY_GATEWAY_CANDIDATE

BOARD_C_POWER=FIXED_STABLE
BOARD_C_MOVEMENT=STATIONARY
BOARD_A_MOVABLE=true
BOARD_B_MOVABLE=true

R0_R7_ORDER_FROZEN=true
```

The 90-second A/B/C Direct run completed on 2026-09-24 is precheck-only:

```text
THREE_BOARD_DIRECT_90S_PRECHECK=PASS
FORMAL_R0_PASS=false
R0_FROZEN_ACCEPTANCE=NOT_YET_EXECUTED

R0_OBSERVATION_SECONDS=180
R0_MIN_CANONICAL_SEQ_ADVANCEMENT_PER_BOARD=2
```

The previously written Board-C-as-Child next route is superseded and must not be executed.

## Physical handoff before formal R0

Board C has already been moved from Mac USB to the intended independent stable test power before the formal R0 baseline. That planned power transition is complete.

Do not move any board during R0.

```text
BOARD_C_USB_DISCONNECTED=true
BOARD_C_STABLE_POWER_REQUIRED=true
BOARD_C_STATIONARY_REQUIRED=true

R0_PHYSICAL_MOVEMENT=false
R0_BOARD_MUTATION=false
R0_T1_MUTATION=false
R0_DATABASE_MUTATION=false
R0_SERVICE_RESTART=false
```

## Correct next gate

```text
CURRENT_PRODUCT_ROUTE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R0_THREE_BOARD_DIRECT_180S_BASELINE_20260924_01
NEXT_GATE_AUTHORIZED=true
```

After formal R0 PASS, continue exactly in frozen order:

```text
R1=A_CHILD_B_ONLY_GATEWAY
R2=A_CHILD_C_ONLY_GATEWAY
R3=A_CHILD_B_AND_C_CANDIDATES_B_CLEARLY_STRONGER
R4=A_CHILD_B_AND_C_CANDIDATES_C_CLEARLY_STRONGER
R5=HEALTHY_ACTIVE_GATEWAY_STICKY_NO_PROACTIVE_ROAM
R6=ACTIVE_GATEWAY_FAILURE_RESELECT_SURVIVOR
R7=SAME_BOOT_RELAY_TO_DIRECT
```

