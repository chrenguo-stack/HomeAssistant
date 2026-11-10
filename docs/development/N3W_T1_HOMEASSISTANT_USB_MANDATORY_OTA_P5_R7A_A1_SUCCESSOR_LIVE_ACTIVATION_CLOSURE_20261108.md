# N3-W T1 Home Assistant mandatory-USB OTA P5 / R7A A1 successor live activation closure — 2026-11-08

## 1. Gate

```text
GATE=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02
RESULT=CLOSED_PASS

AUTHORIZED_HEAD=c01b982e9d889a269e79aedeb8b9f18c15f8b3e6
AUTHORIZED_TREE=74d193f675d712cf53f3484e478b523b975e1dff
AUTHORIZED_CI=25_SUCCESS_0_FAILURE_0_PENDING
```

## 2. One-shot authorization

```text
AUTHORIZATION=N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02
GRANTED=true
CLAIMED=true
CONSUMED=true
REPLAY_PERMITTED=false
OLD_A1_01_REPLAY_PERMITTED=false
```

The authorization was bound to the exact reviewed executor source and crossed its durable claim boundary during the live run. It must never be replayed.

## 3. Real-T1 execution evidence

```text
EXECUTION_ID=N3W_R7A_HOST_A1_20261107T174129Z
EXECUTOR_RC=0
STATUS=PASS

T1_ACCESS=true
T1_FILE_WRITE=true
ACTIVATION_INVOKED=true
SECOND_ACTIVATION_INVOKED=false
SERVICES_OWNER_RESTART_INVOKED=true

HOST_DAEMON_ACTIVE=true
MANAGER_OTA_ENABLED=true

AUTOMATIC_A1_ROLLBACK_INVOKED=false
AUTOMATIC_A1_ROLLBACK_PASS=null
RECOVERY_REQUIRED=false
SSH_MASTER_CLEANUP=true

USB_MUTATION=false
PREPARE_INTENT=false
CONFIRM_USB_ERASE=false
BOARD_ACCESS=false
FIRST_FAILED_OPERATION=null
```

The private T1 locator, operator known_hosts path, expected host-key fingerprint, password, and private evidence-root path are intentionally not archived in GitHub.

## 4. KF-143 closure

The first A1 attempt exposed a post-restart container-convergence race because the Type=simple services owner returned before Manager/Home Assistant container convergence. The repaired executor retained strict immediate preflight and added a bounded 120 s convergence wait only after activation and rollback restarts.

The successor live run completed PASS without `container_cardinality_invalid`, without automatic rollback, and with `recovery_required=false`. This provides real-T1 validation of the KF-143 repair. KF-143 is therefore RESOLVED while its regression guards remain permanent.

## 5. Scope boundary

This closure proves the A1 software activation boundary only.

```text
REAL_USB_INSERTION_AUTHORIZED=false
PREPARE_AUTHORIZED=false
CONFIRM_USB_ERASE_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

No result from this gate authorizes removable-media insertion, PREPARE, destructive confirmation, U2+, board access, or merge.

## 6. Next ONE gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_BOUNDARY_B_PREPARE_ONLY_PREEXECUTION_20261108_01
```

Purpose: independently freeze the Boundary B real-USB PREPARE-only procedure, candidate-selection/read-only evidence contract, exact stop boundary, and rollback/recovery assumptions while keeping real USB insertion and PREPARE execution disabled.

Boundary B must remain a separate physical gate. Its design must preserve the architecture requirement that PREPARE performs discovery only and does not format, mount, or write the candidate media.
