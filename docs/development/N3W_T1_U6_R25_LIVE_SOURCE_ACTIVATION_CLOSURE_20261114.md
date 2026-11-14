# N3-W T1 U6 R25 Live Source Activation Closure — 2026-11-14

## 1. Terminal result

```text
R25_GRANTED_HEAD=01dfb390c379764f0f8a4d0da2e92e474e240a9d
R25_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U6_SOURCE_ACTIVATION_R25_20261114_01
R25_EXECUTION_ID=U6-R25-LIVE-SOURCE-ACTIVATION-20261114T022923Z
R25_EXEC_RC=0
R25_STATUS=U6_R25_SOURCE_ACTIVATION_PASS

AUTHORIZATION_CLAIM_PERSISTENCE_UNKNOWN=false
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

R25 is terminal. Its one-shot authorization is consumed and must never be replayed.

## 2. Source activation result

```text
SOURCE_ACTIVATED=true
HOST_SOURCE_MUTATION=true
IMPORT_VALIDATION=true
ROLLBACK_REQUIRED=false
ROLLBACK=null

LIVE_PREPARE_HOST_SHA256=0d0c96d7ae2f26c2d2ae8388e6ee75ad0616081a6cdcb98727f2131dab31c30e
LIVE_INSTALL_SHA256=9391019fc01004373c16e66a42ac43cd8fc2119c6692448947e6019f1788e530
```

The activated live source set is exactly the R25 two-file target: the updated Home Assistant host-prepare module plus the new install module. Import validation passed after activation.

## 3. U5 and runtime preservation

```text
U5_PRESERVED=true
TRANSACTION_PHASE=U5_INSTALL_REQUESTED_REVALIDATING
TRANSACTION_SHA256=adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144

IPC_ACCEPTED=true
IPC_PHASE=INSTALL_REQUESTED_REVALIDATING
IPC_INSTALLED_VERSION=2026.10.0

MANAGER_CONTAINER=running_restart0
HOMEASSISTANT_CONTAINER=running_restart0
BROKER_CONTAINER=running_restart0
HOST_UNIT=active_running_success_nrestarts0
SERVICES_OWNER=active_running_success_nrestarts0
BROKER_OWNER=active_running_success_nrestarts0
```

The durable U5 transaction SHA-256 is unchanged from the pre-execution authority. Runtime containers and owner units remained healthy.

## 4. Forbidden mutations remained false

```text
SERVICE_RESTART=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
USB_TRANSACTION_METADATA_MUTATION=false
U6_TRANSITION=false
U7_PLUS=false
BOARD_ACCESS=false
MERGE=false
SSH_MASTER_CLEANUP=true
```

R25 did not enter the U6 transaction. The next actual lifecycle phase remains `U6_PREDECESSOR_RECOVERY_PREPARING`. No U5→U6 transaction authorization is granted by this closure.

## 5. Evidence and durable archive

- Public closure evidence: PR #807 comment 6870233266.
- Grant/fresh-CI/exact-review evidence: PR #807 comment 6870134446.
- Raw execution evidence remains in the approved local private evidence area and is not copied into the public repository.

```text
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_EVIDENCE_PATH_CLASS=approved-local-private-evidence/n3w-r25-live-source-activation
PRIVATE_EVIDENCE_EXECUTION_ID=U6-R25-LIVE-SOURCE-ACTIVATION-20261114T022923Z
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
SECRET_VALUES_INCLUDED=false
```

## 6. Stop boundary

```text
R25_LIVE_SOURCE_ACTIVATION=CLOSED_PASS
R25_REPLAY_PERMITTED=false
LIVE_TRANSACTION_PHASE=U5_INSTALL_REQUESTED_REVALIDATING
NEXT_LIFECYCLE_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
NEXT_ONE_GATE=DEFINE_AND_AUTHORIZE_U5_TO_U6_TRANSACTION_GATE

TRANSACTION_MUTATION_AUTHORIZED=false
USB_MUTATION_AUTHORIZED=false
SERVICE_RESTART_AUTHORIZED=false
U6_TRANSITION_AUTHORIZED=false
U7_PLUS_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

Execution stops at the real U6 transaction boundary. A separate gate definition, source/execution review as required, and explicit authorization are required before any U5→U6 transition.
