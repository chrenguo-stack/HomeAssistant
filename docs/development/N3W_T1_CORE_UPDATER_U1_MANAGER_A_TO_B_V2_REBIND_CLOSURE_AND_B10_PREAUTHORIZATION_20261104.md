# N3-W T1 Core Updater U1 — Manager A -> B V2 rebind closure and B10 preauthorization

Date: 2026-11-04

## Result

```text
TASK=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_V2_REBIND_CLOSURE_20261104_01
V2_REBIND_HEAD=29f3094a08f28f4f6660f2394fc90a6d66ab6c79
V2_REBIND_CI_RUN_ID=41841275491
V2_REBIND_CI_RUN_NUMBER=179
V2_REBIND_RESULT=CLOSED_PASS

SOURCE_TESTS=128_PASSED
EXACT_MANAGER_SLICE=PASS
PRE_U1_V2_SIMULATION=PASS
TERMINAL_V2_TRANSACTION_ARCHIVE=PASS

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## Exact V2 package authority

```text
PACKAGE_ARTIFACT_ID=13329432192
PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-v2-5b32e1ae8210
PACKAGE_ARTIFACT_DIGEST_SHA256=b2cd55cf11de3a97f5d0df13e790094778b76582e1c885318387a8368b6ecfc5
PACKAGE_SIZE_BYTES=63057214

UPDATER_PYZ_SHA256=17849b16c0f60b30b69bcd7d0a17826058748fff053a93a3d90cf349c5baded7
MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
MANAGER_BUILD_IMAGE_ID=sha256:80d34358094638ce9c8ce5fb2635fe0a5c75ee7cc5e8c628b38ab223134e585f

TARGET_MANIFEST=infra/n3w-t1/upgrades/manager-5b32e1ae8210.json
TARGET_SCHEMA=gh.n3w-t1-core-updater-target/2
TRANSACTION_SCHEMA=gh.n3w-t1-core-updater-transaction/2
BASELINE_MANIFEST=infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json
EXPECTED_PREDECESSOR=local/greenhouse-manager:fresh-b863ddd95909
TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
MANAGER_REBUILT=false
```

## V2 simulation proof

The same CI run downloaded the newly produced V2 Manager-only package and executed the real V2
updater path against the frozen Pre-U1/U0 authority.

```text
U1_B8_V2_PRE_U1_INSPECT_PLAN_SIMULATION=PASS
U1_B8_V2_TERMINAL_TRANSACTION_ARCHIVE=PASS
SIMULATED_APPLY=A_TO_B_PASS
SIMULATED_ROLLBACK=B_TO_A_PASS
PEER_IMAGE_MUTATION=false
REAL_T1_ACCESS=false
REAL_T1_MUTATION=false
```

The simulation starts with a pre-existing terminal V2 transaction and proves that the updater archives
that terminal transaction before creating the new V2 Manager transaction. This closes the V1/V2 split
blocker found before the first live apply attempt.

## Previous authorization disposition

```text
OLD_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_U1_20261104_01
OLD_AUTHORIZATION_GRANTED=true
OLD_AUTHORIZATION_CLAIMED=false
OLD_AUTHORIZATION_CONSUMED=false
OLD_AUTHORIZATION_VOID_BEFORE_CLAIM=true
OLD_AUTHORIZATION_REPLAY_PERMITTED=false
```

The old authorization was bound to the superseded legacy-v1 package/control path and may not be
replayed or reinterpreted for the V2 package.

## New B10 single-use authorization boundary

```text
PROPOSED_APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_U1_V2_20261104_02
APPLY_CONFIRMATION=T1_CORE_UPDATER_APPLY
APPLY_AUTHORIZATION_GRANTED=false
APPLY_AUTHORIZATION_CLAIMED=false
APPLY_AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
AUTO_EXECUTE_B10=false
```

If later explicitly granted, B10 must first run fresh real-T1 `status / inspect --component manager / plan`
with the exact package, V2 target manifest and Baseline A. Any transaction, predecessor, target archive,
A1 hard/soft policy, pairing/registration, service-owner, peer image or runtime drift stops before apply.

Only after all fresh prechecks PASS may exactly one V2 Manager A -> B apply be attempted. Any failure
after mutation starts stops automatic retry and requires fresh transaction evidence before any recovery
decision.

```text
V2_REBIND=CLOSED_PASS
B10_PREAUTHORIZATION_READY=true
U1_LIVE_APPLY_AUTHORIZED=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_B10_V2_LIVE_APPLY_AUTHORIZATION_20261104_02
STOP=true
```
