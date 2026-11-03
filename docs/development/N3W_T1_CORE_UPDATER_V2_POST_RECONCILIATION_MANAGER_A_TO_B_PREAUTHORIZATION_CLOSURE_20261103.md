# N3-W T1 Core Updater V2 post-reconciliation Manager A -> B read-only preauthorization closure — 2026-11-03

## 1. Gate result

```text
GATE=N3W_T1_CORE_UPDATER_V2_POST_RECONCILIATION_MANAGER_A_TO_B_READONLY_PREAUTH_20261103_01
RESULT=CLOSED_PASS

MAIN=92e7dfaa5e508fae1bb6477b9cdb23712a33588c
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

UPDATER_V2_PACKAGE_RUN=41544508199
UPDATER_V2_PACKAGE_ARTIFACT_ID=13187736541
UPDATER_V2_PACKAGE_DIGEST=sha256:e09fb86c8444e0510b0200e759551d3571496064c743b4171992d46ab73babb9
UPDATER_V2_PYZ_SHA256=e92c093c7028d57ddc1e2c9c1eeb3fb97a0791a27b262b472c75482eaa3026bf
UPDATER_V2_ARTIFACT_EXPIRED=false

LIVE_MUTATION=false
APPLY_EXECUTED=false
BOARD_ACCESS=false
```

## 2. Fresh real-T1 status

```text
STATUS=PASS
STATUS_MUTATION=false
RECOVERY_REQUIRED=false
TRANSACTION_STATUS=ROLLED_BACK
TRANSACTION_PHASE=RECOVERY_COMPLETE_FAILED_EMERGENCY
TRANSACTION_AUTHORIZATION_CONSUMED=true
```

The previous R2 transaction is terminal. It no longer blocks a new updater transaction. Its authorization remains consumed and must not be replayed.

## 3. Fresh real-T1 inspect

```text
INSPECT=PASS
INSPECT_MUTATION=false

LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_MANAGER_IMAGE_ID=sha256:2bfead7d72535aecae943277a70715811ad29d089d7fb45ba6bd0d3dc68bc286

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306

BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563

MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0

TCP_8883=1
TCP_47110=1
UDP_47111=1
TCP_47112=0
LISTENER_CONTRACT=PASS
```

## 4. Fresh exact target plan

```text
PLAN=PASS
PLAN_MUTATION=false

CURRENT_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd

TARGET_ARTIFACT_ID=13124977192
TARGET_ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-3539c8f871e2cb63f18462009fa03a5eb36d39fd
TARGET_ARTIFACT_DIGEST_SHA256=f01dfc79fe2e2f1b20127f718487afe32f939b0ec09b47ad628fc88e6ff79b77
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0

MANAGER_TAR_VERIFIED=true
TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT
ROLLBACK_AVAILABLE=true

BROKER_MUTATION=false
HOMEASSISTANT_IMAGE_MUTATION=false
HOST_PLATFORM_MUTATION=false
```

## 5. Authorization boundary

The read-only preauthorization gate is closed PASS. It does not itself authorize live apply.

```text
OLD_R1_R2_AUTHORIZATION_REPLAY_PERMITTED=false

PROPOSED_APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_POST_RECONCILIATION_20261103_01
APPLY_AUTHORIZATION_GRANTED=false
APPLY_AUTHORIZATION_CONSUMED=false

APPLY_CONFIRMATION=T1_CORE_UPDATER_MANAGER_APPLY
AUTO_EXECUTE_APPLY=false
```

If the user explicitly grants the proposed authorization, it authorizes exactly one Manager A -> B V2 apply transaction using the already reviewed exact package and target tar.

It does not authorize:
- a second apply attempt after failure;
- manual transaction edit/delete;
- Home Assistant image mutation;
- Broker image mutation;
- host-platform mutation;
- Board access;
- firmware/NVS mutation.

## 6. Failure boundary for future apply

After any future apply attempt:
1. capture updater status and inspect;
2. do not issue explicit rollback blindly;
3. terminal ROLLED_BACK + healthy predecessor A means freeze evidence and diagnose;
4. any nonterminal state or recovery_required=true stops at recovery boundary;
5. FAILED_EMERGENCY is a hard stop and requires separately authorized V2 reconciliation.

## 7. Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_POST_RECONCILIATION_AUTHORIZATION_20261103_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

The next gate is authorization only. No live apply occurs until the exact new authorization is explicitly granted.
