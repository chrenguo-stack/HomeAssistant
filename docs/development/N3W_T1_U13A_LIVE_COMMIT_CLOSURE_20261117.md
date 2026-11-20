# N3-W T1 U13A live commit closure — 2026-11-17

## Result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U13A_LIVE_COMMIT_20261117_01
EXECUTION_ID=u13a-live01-20261117T022518Z
AUTHORIZED_PACKAGE_HEAD=b1d4ea98bc768ed26d626b895d494cd8ca38cc69
AUTHORIZED_PACKAGE_CI=16_OF_16_SUCCESS

LOCAL_RC=0
STATUS=U13A_LIVE_COMMIT_PASS
FRESH_PREFLIGHT_PASS=true
REMOTE_EXECUTE_INVOKED=true
REMOTE_EXECUTE_RESULT_OBSERVED=true
STATUS_RECONCILIATION_ATTEMPTED=false
SSH_MASTER_CLEANUP=true

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

TRANSACTION_PHASE=U13A_COMMITTED
TRANSACTION_STATUS=COMMITTED
TRANSACTION_SHA256=06951ac4d8a8723ae808f25d955560052eee02f884ab78f5c6ffe0580e84b600
RECOVERY_REQUIRED=false
USB_PHASE=U13A_COMMITTED
USB_PHASE_SHA256=11d150bc3828a0e400a90670671a607a02f6d1a53350ef53b3366d95fcb64288
USB_MIRROR_EXACT=true

SERVICE_MUTATION=false
IMAGE_MUTATION=false
U13B_TRANSITION=false
BOARD_ACCESS=false
MERGE=false
```

U13A completed through the exact authorized package. The embedded fresh read-only preflight passed before authorization claim and proved `FORWARD_COMMIT_ELIGIBLE=true` with `rollback_required=false`. The one-shot authorization was then claimed and consumed. Replay remains permanently forbidden.

## Pre-claim verification

The embedded U13A preflight returned `U13A_COMMIT_READONLY_PREFLIGHT_PASS` with:

- host transaction still exact `U12_TARGET_ACCEPTANCE`, SHA-256 `32a92edcd9fbdad1356b874a55d40f6e919518363c5740b495f9b5fa08a56071`;
- USB mirror exact at U12, phase SHA-256 `ca5cbcaa0d915f9a0fe590d2beeeace846ce7029bdf6dcb8b46331d205212283`;
- power-loss re-entry classification `FORWARD_COMMIT_ELIGIBLE`;
- target archive SHA-256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`, size 835,309,535 bytes;
- predecessor archive SHA-256 `34cec37ab021e1081e236502bfd06760894f6bca93bd8d6bf99d8d90bb89848d`, size 743,074,537 bytes;
- HA backup verified;
- USB capacity PASS with 28,132,077,568 bytes free versus 1,610,612,736 bytes required after recovery assets;
- Broker, Manager and Home Assistant running, services owner active, production config mounted;
- Manager and Home Assistant MQTT authentication PASS;
- Home Assistant HTTP readiness status 401.

The preflight was read-only and reported no transaction, USB, service, image, board or merge mutation.

## Durable terminal state

The live commit durably advanced the normal success path:

```text
U12_TARGET_ACCEPTANCE
-> U13A_COMMITTED
```

Terminal verification proved:

- host transaction phase `U13A_COMMITTED`, status `COMMITTED`;
- `recovery_required=false`;
- host transaction SHA-256 `06951ac4d8a8723ae808f25d955560052eee02f884ab78f5c6ffe0580e84b600`;
- USB mirror exact at `U13A_COMMITTED`;
- USB phase SHA-256 `11d150bc3828a0e400a90670671a607a02f6d1a53350ef53b3366d95fcb64288`;
- USB manifest SHA-256 `3aa5e247636b1bb891aa151a8fb0219294d4803ea22dc7b66d821f6250d9e728`;
- USB content-authority SHA-256 `3da14eb03447beaf38579a3fa5e4e076d4f3e806f7a787cbc0bba6b2cb1b8727`;
- USB checksums SHA-256 `2a21aa2b8fb362242fa087a49a2ebfb93caf65d1dd8a6f9c6da44edbb9f8c7f2`;
- target runtime image ID unchanged at `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`;
- Broker, Manager and Home Assistant running;
- Manager and Home Assistant MQTT authentication PASS;
- Home Assistant HTTP readiness status 401.

The execution performed the authorized U13A transaction/USB metadata commit only. It did not mutate services or images, did not enter U13B, did not access boards and did not merge PR #807.

## Authorization closure

```text
AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U13A_LIVE_20261117_01
CONFIRMATION=EXECUTE U13A LIVE COMMIT: YES
GRANTED=true
CLAIMED=true
CONSUMED=true
REPLAY_PERMITTED=false
```

This authorization is terminal and must never be reused or replayed.

## Private evidence

```text
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PATH_CLASS=approved_local_mac_private_evidence_root
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_EXECUTION_ID=u13a-live01-20261117T022518Z
PRIVATE_EVIDENCE_SHA256=UNAVAILABLE_FROM_CHAT_EXECUTION_ENVIRONMENT
PRIVATE_EVIDENCE_SIZE=UNAVAILABLE_FROM_CHAT_EXECUTION_ENVIRONMENT
SECRET_VALUES_INCLUDED_IN_THIS_PUBLIC_CLOSURE=false
```

The exact local private-evidence path is intentionally not copied into the public repository. The execution ID and durable public-safe hashes above provide the continuation binding available to this session.

## Local shell post-command note

After the executor had already returned RC=0 and printed `[进程已完成]`, the local shell emitted:

`shell_session_save_user_state_functions: parameter not set`

This occurred in the terminal session-save hook after the U13A executor completed. It is not a T1/U13A failure and does not alter the durable executor result.

## Stop boundary

```text
U13A_CLOSED_PASS=true
U13B_EXECUTED=false
U13B_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
NEXT_LIVE_MUTATION_AUTHORIZED=false
NEXT_SAFE_ENTRY_POINT=POST_U13A_ARCHIVE_OR_SEPARATELY_AUTHORIZED_FUTURE_GATE
```

No U13B, board, merge, service/image mutation, recovery-asset cleanup or further live transition is authorized by this closure.

## Archive status

```text
ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=not-required
PUBLIC_TESTS_ARCHIVED=not-required
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=not-required
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=true
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=not-required
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
NEXT_SAFE_ENTRY_POINT=POST_U13A_ARCHIVE_OR_SEPARATELY_AUTHORIZED_FUTURE_GATE
```
