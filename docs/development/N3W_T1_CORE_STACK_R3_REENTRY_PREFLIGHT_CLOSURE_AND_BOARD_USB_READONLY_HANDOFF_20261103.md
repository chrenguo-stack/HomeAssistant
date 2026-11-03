# N3-W T1 Core Stack R3 re-entry preflight closure and Board USB readonly handoff — 2026-11-03

## Result

```text
TASK=N3W_T1_CORE_STACK_R3_SENSORLESS_REAL_FIRST_REGISTRATION_REENTRY_PREFLIGHT_20261103_01
RESULT=PASS

MAIN=964b60d7348b9392d98ac74cdddbcecfa9b6f721
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
LIVE_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2

UPDATER_TRANSACTION_PATH=/var/lib/n3w-t1-core-updater/manager-upgrade.json
UPDATER_TRANSACTION_STATUS=COMMITTED
UPDATER_TRANSACTION_PHASE=COMMITTED
UPDATER_AUTHORIZATION_BINDING=PASS

MANAGER_B_RUNTIME=PASS
TCP_47110=1
UDP_47111=1
TCP_47112=0
TCP_8883=1
PAIRING_WINDOW_STATE=CLOSED

TRUSTED_PRODUCT_LAN=PASS
REGISTRATION_INGRESS_GUARD=PASS
REGISTRATION_GUARD_ANCHORS=2,3,4

SEMANTIC_ZERO_NODE=PASS
UNRESOLVED_FIRST_REGISTRATION_COUNT=0
TERMINAL_REPLAY_TOMBSTONE_COUNT=1
REPLAY_STATE_ZERO=true
APPLICATION_KEY_STATE_ZERO=true

SYSTEM_PEER_TRUST_BASELINE=PASS
SYSTEM_PEER_TRUST_GENERATION=1

R3_SENSORLESS_FIRMWARE_ARTIFACT_ID=13118775924
R3_FIRMWARE_SOURCE_DRIFT=false

T1_MUTATION=false
BOARD_ACCESS=false
FIRST_REGISTRATION_STARTED=false
```

## Harness correction

The first re-entry attempt stopped on `updater_transaction_missing` because the ad-hoc preflight used the wrong filename `/var/lib/n3w-t1-core-updater/transaction.json`.

The updater V2 source authority uses:

```text
/var/lib/n3w-t1-core-updater/manager-upgrade.json
```

The corrected read-only continuation passed. This was a validation-harness false STOP, not a T1 runtime or updater failure. No reconciliation, apply, rollback, service restart, registration or Board action occurred.

## Source / artifact rebind

- The historical Clean Reference readiness bridge remains diagnostic only and is not reused as the R3 entry gate because it hard-binds the predecessor Manager/R2 runtime baseline.
- Manager A -> B registration-source comparison found only first-registration ledger timestamp canonicalization; no listener, trusted-LAN, ingress-guard or credential-lifecycle semantics drift was found.
- Sensorless firmware artifact run `41393417315`, artifact `13118775924`, source `ea1488845ba05d362454678f2801232010852ecf` remains usable.
- There are no firmware file changes from that artifact source to current main.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_BOARD_USB_READONLY_IDENTITY_BINDING_20261103_01

BOARD_ACCESS=true
BOARD_ACCESS_MODE=READONLY_USB_IDENTITY_ONLY
FLASH_MUTATION=false
NVS_MUTATION=false
APPLICATION_SERIAL_OPEN=false
T1_MUTATION=false
FIRST_REGISTRATION_STARTED=false
```

Allowed operations are fresh local USB enumeration, `esptool chip-id`, and `esptool flash-id`. Stop before any erase/write/NVS operation. Raw Board unique identity and exact local USB locator remain private and must not be committed to public GitHub.
