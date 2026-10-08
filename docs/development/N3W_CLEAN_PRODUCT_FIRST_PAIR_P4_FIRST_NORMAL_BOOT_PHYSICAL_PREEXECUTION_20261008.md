# N3-W Clean Product First-Pair — P4 First Normal Product Boot Physical Preexecution — 2026-10-08

```text
STATUS=PREPARED_NOT_AUTHORIZED
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_FIRST_NORMAL_BOOT_PHYSICAL_PREEXECUTION_20261008_01
P4_PREBOOT_READONLY_RESULT=CLOSED_PASS
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_FIRST_NORMAL_BOOT_STARTED=false
BOARD_ACCESS=false
BOARD_RESET=false
BOARD_POWER_CYCLE=false
BOARD_FLASH_ERASE=false
BOARD_FLASH_WRITE=false
WIFI_PROVISIONING_STARTED=false
SETUP_SECRET_IMPORT=false
T1_MUTATION=false
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_REPLAY_CLEAR=false
MANAGER_HIGH_WATER_CLEAR=false
P4_AUTO_EXECUTE=false
STOP=true
```

## 1. Frozen prerequisites

```text
PR=522
PR_REQUIRED_STATE=OPEN_DRAFT_UNMERGED
P3_CLOSURE=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_OFFLINE_ARTIFACT_R2_CLOSURE_20261008.md
P3_RESULT=CLOSED_PASS
P3_READBACK_FOUR_REGIONS=PASS
CURRENT_BOARD_STATE=FOUR_REGIONS_WRITTEN_AND_EXACT_READBACK_PASS_NO_PRODUCT_BOOT

CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
ARTIFACT_ID=11469977052
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c

P4_PREBOOT_CLOSURE=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_CLOSURE_20261008.md
P4_PREBOOT_RESULT=CLOSED_PASS
P4_PREBOOT_READONLY_AUTHORIZATION_CONSUMED=true
P4_PREBOOT_READONLY_REPLAY=false
P4_MANAGER_BROKER_CONTINUITY=PASS
T1_HOST_MODE_AUTO=PASS
BROKER_TLS_A_8883=PASS
EXTERNAL_DISCOVERY_AUTO_A=PASS

FROZEN_PREBOOT_MANAGER_IDENTITY_COUNT=5
FROZEN_PREBOOT_IDENTITY_SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1
FROZEN_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c

P4_FIRST_BOOT_AUTHORIZATION_GRANTED=false
```

Historical P2, the current-board P1 successor, P3 exact flash closure, and the just-accepted P4 host-only preboot closure are distinct authorities. The ESP32-C6 ROM silicon binding is not the product runtime hardware identity; product identity is deferred until Manager pending registration and real optical LCD QR binding.

## 2. Do not create a pending transaction until its short-lived handoff is ready

The existing P4 stage can create the unique new pairing identity as soon as the product boots, connects to Wi-Fi, and sends Manager hello. The pending transaction has a finite TTL; historical KF-044 proves that pausing after hello for new authorizations, lengthy source checks, CI, or secret-transfer setup can consume the pending window and invalidate the physical trial.

Therefore the operator may not be instructed to perform first normal product boot until these readiness conditions are met:
- the unique current T1/Manager/Broker baseline and preboot identity set are available privately and verified;
- the exact product Wi-Fi provisioning method, LCD page-5 observation path, and QR optical capture means are ready;
- the private identity-binder for the real QR vs exactly one newly created Manager pending session is source-rebound and ready to execute promptly;
- the exact Manager-owned pairing.sock, `greenhouse-manager-pairing import-payload --payload-stdin` private handling path is staged, with no raw secret in argv, terminal transcript, logs, GitHub or chat;
- **separate operator consent** for any P4 secret import / Manager-side pairing mutation is obtained *before* product pending creation; no implicit permission follows from P4 boot approval;
- controlled interruption at Manager COMMIT but strictly before first Manager-accepted canonical telemetry is operationally feasible, or that interruption test is left for a separately designed legitimate new-product trial; do not replay an existing clean identity via erase/reset.

If any of those prerequisites is not ready, mark `P4_PHYSICAL_PRECLAIM_READY=false`, STOP, and leave the current product board in the post-P3 no-normal-boot state.

## 3. Proposed P4-A/P4-B bounded first-boot scope

This is a **design contract only**, not authorization or a runnable terminal command. Once pre-staged and independently authorized:

1. Freshly bind the same operator-connected physical ESP32-C6 candidate to the P3 verified silicon digest without re-erasing or rewriting flash. Mac USB port name is only a locator.
2. Freeze current host continuity and identity-snapshot authority, and preserve exact T1 address A and certificate identity privately.
3. Perform one explicitly approved normal product boot. Do not use alternate firmware, test harness, NVS edits, recovery-floor, app-image swaps, or legacy serial pairing path.
4. Use the product's normal Wi-Fi provisioning QR/path only. Require the real on-device LCD page-5 `GHN3W2` QR following Manager discovery, TCP/47112 hello acceptance and a unique new pending session.
5. Observe the QR optically from the physical LCD. Stop for the separately bounded private identity binding and secret handoff (already pre-staged; do not use the finite TTL period to write the executor).
6. Any ambiguity/mismatch or missing LCD QR is STOP. Do not erase, retry, manually fake a QR, or wipe Manager identities.

These steps do not prove P4-C identity binding, P4-D Setup Secret import, P4-E Manager COMMIT and controlled interruption, or P4-F reboot/telemetry recovery. Each still requires its own exact evidence and consent boundary.

## 4. P4 actual acceptance and STOP points

Authoritative P4 scope remains Stage P4-A through P4-F of:
`docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007.md`.

```text
P4_A_WIFI_PROVISIONING=DEFERRED
P4_B_MANAGER_HELLO_LCD_QR=DEFERRED
P4_C_PRIVATE_PRODUCT_RUNTIME_IDENTITY_BINDING=DEFERRED
P4_D_PRIVATE_SETUP_SECRET_HANDOFF=DEFERRED
P4_E_MANAGER_COMMIT_CONTROLLED_INTERRUPTION=DEFERRED
P4_F_REBOOT_RECOVERY_AND_TWO_CANONICAL_ADVANCES=DEFERRED

STOP_1=AFTER_P3_READBACK_BEFORE_FIRST_NORMAL_BOOT
STOP_2=AFTER_LCD_PAGE5_REAL_QR_VISIBLE_BEFORE_PRIVATE_QR_INTAKE
STOP_3=AFTER_UNIQUE_RUNTIME_IDENTITY_BOUND_BEFORE_SECRET_IMPORT
STOP_4=AFTER_COMMIT_WITH_CANONICAL_COUNT_ZERO_BEFORE_CUT_POWER_NOW
STOP_5=AFTER_REBOOT_RECOVERY_WITH_TWO_STRICT_CANONICAL_ADVANCES
```

The controlled interruption window can close quickly. If telemetry has already been accepted before COMMIT/interrupt decision, classify the interruption trial as `INVALID_WINDOW`, not product failure; do not re-erase/re-pair the same board to manufacture a new first-pair trial.

## 5. Next engineering and authorization boundary

```text
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_FIRST_NORMAL_BOOT_EXECUTOR=NOT_YET_PREPARED
P4_PRIVATE_IDENTITY_CAPTURE_AND_BINDER=REQUIRES_SOURCE_REBIND
P4_SECRET_IMPORT_AUTHORIZATION=NOT_GRANTED
P4_AUTOMATIC_NEXT_STAGE=false

NEXT_ENGINEERING_STEP=PREPARE_P4_PRIVATE_PENDING_IDENTITY_AND_SETUP_SECRET_HANDOFF_BEFORE_BOOT
NEXT_PHYSICAL_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_FIRST_NORMAL_BOOT_20261008_01
NEXT_PHYSICAL_GATE_AUTHORIZATION_GRANTED=false
STOP=true
```

This preparation file does not operate on physical boards or live T1 services. Authorize and run further physical steps only after their exact runbook, preflight and dedicated one-shot permission are complete.
