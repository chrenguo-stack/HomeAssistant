# N3-W T1 E03 successor recovery read-only preauth R2 closure — 2026-10-30

~~~text
TASK=N3W_T1_E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH_R2_20261030_01
PR739_HEAD_AT_EXECUTION=fc6d4746165dbd329534bcaaa2b556ea35342b14
PR740_EXACT_HEAD=16d568ed577a050e23ee0061203d2a4d09cd19a0

EXACT_SOURCE_REBIND=PASS
LOCAL_IDENTITY=PASS
PORTABLE_IDENTITY_SHA256=52c92c74648b657b05f7748014e0df4a0e406ae40e6d8a3201ff10633ea0d588
CONFIG_DIGEST=sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4

PREDECESSOR_FRESH_REBIND_R2=PASS
PREDECESSOR_SHA256=cb5e542a958886880b98d73742595694b93d3f4f16f83765e0fc3fc69d9a1bc8
HOST_BINDING_SHA256=550e4fa9e89ae98848d873823ad4c5d352275647be52e4f693b7dd58ae72a8da
COMPOSE_SHA256=9ea58161d5f8e24233bacbfe1f31edd5f6f6c62c272271823788c0c5b59e8357
COMPOSE_ENV_SHA256=feab54cf8c2a8e2eeb5350d8194ed0af21bcd4df2a6a0d3d53729a63443c4509
GH_MANAGER_IMAGE=local/greenhouse-manager:fresh-ff750b3801a2

PREAUTH_STATUS=PASS
PREAUTH_EXIT_CODE=0
PREAUTH_PLAN_SHA256=ff1a0e16886c6cc2d860173d8330602f1dc30e8da3a793f19efad3bb97c9bb3c
CURRENT_RELEASE_ID=4d6925334c4c6d0d741e3a8215954f4b136757f45e2295cbbe50e88996efa744
TARGET_RELEASE_ID=939e92d347a4cb925f760d58bafefdc2a41bfabc478f35ee086813d49da0f798
TARGET_RUNTIME_IMAGE_ID_OBSERVED=sha256:7751d48316836a50189490fc0c3bf6cdaf5ff741a3f638610887bf6b9ac5d5e8
CANDIDATE_PORTABLE_IDENTITY=VERIFIED
COMPOSE_PRESTATE=EXACT_PREDECESSOR
OLD_AUTHORIZATION=CONSUMED_NO_REPLAY
NO_OTHER_ACTIVE_TRANSACTION=true

KF137=LIVE_REVALIDATION_PASS
KF132_CURRENT_E03_CONTAINERD_REPRESENTATION=LIVE_REVALIDATION_PASS
KF132_GENERAL_DUAL_STORE_MATRIX=P1_PENDING

T1_MUTATION=false
SUCCESSOR_AUTHORIZATION_CLAIMED=false
TRANSACTION_CREATED=false
LIVE_RECOVERY=false
BOARD_ACCESS=false
MERGE=false

READONLY_PREAUTH_R2=CLOSED_PASS
CURRENT_STOP_POINT=PREAUTH_PASS_BEFORE_NEW_SUCCESSOR_AUTHORIZATION_CLAIM
NEXT_ONE_GATE=N3W_T1_E03_SUCCESSOR_RECOVERY_SUCCESSOR_TRANSACTION_CLAIM_20261030_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

## Result

The first live preauth failed on KF-137 because the successor incorrectly assumed a literal Manager image in raw Compose YAML. After the Compose-env authority repair, the same real T1 now passes read-only preauthorization at the exact PR #740 closure head.

The successor verified the already-loaded candidate by Portable Image Identity while observing the host-local runtime image ID sha256:7751d483..., proving that the current E03 containerd-store representation no longer triggers the old cross-store single-.Id false STOP.

The production Compose remained exact predecessor. The Compose env remained on the predecessor Manager image. The predecessor transaction raw SHA remained unchanged and its authorization remained consumed with replay disabled. No other active maintenance transaction was present.

## Safety boundary

This gate did not claim a successor authorization and did not create a successor transaction. It did not mutate Compose, Compose env, services, Docker image state, credentials, boards or live product state.

The next step requires a new explicit authorization because successor claim creates a new durable transaction and consumes a new authorization. The old authorization must never be replayed.
