# N3-W T1 OTA V1.3 R8V13-07 fresh transaction A U4 physical PASS

Date: 2026-11-24
PR: #824
Stage: N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
Task: R8V13-07

## 1. Physical result

The user executed the CI-sealed PREPARE→U4 gate:

`N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261124_01`

Result:

```text
OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS
PREMUTATION_RUNTIME=PASS
TARGET_10_0_PRESENT_BEFORE_PREPARE=false
OLD_USB_TARGET_SOURCE=PASS

ROOT_AVAILABLE_BYTES=4686041088
INTERNAL_CANDIDATE_REQUIRED_BYTES=2448560128
INTERNAL_CANDIDATE_CAPACITY=PASS

CANDIDATE_MATERIALIZATION=PASS
NEW_FRESH_TRANSACTION_ID=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
NEW_FRESH_TRANSACTION_U1=PASS
NEW_PREPARE_AUTHORITY=PASS

NEW_FRESH_TRANSACTION_A_U4=PASS
FINAL_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
FINAL_SELF_TEST_SHA256=fd23789ae3cf611fa1b7c379ab95be5fd7d6f4bb21a36b2459674a7d8e609eda

PREPARED_TARGET_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
PREPARED_TARGET_SIZE=2448553472
PREPARED_PREDECESSOR_SHA256=6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f
PREPARED_PREDECESSOR_SIZE=2447090176

INSTALL_AUTHORITY_RESIDUE=OLD_TERMINAL_SAFE_REPLACEABLE
TARGET_10_0_PRESENT_AFTER_PREPARE=false

NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=PASS
R8V13_07_SUBSTATE=NEW_FRESH_U4_READY_TO_INSTALL
INSTALL_INTENT=false
INSTALL_AUTHORITY_ISSUED_FOR_NEW_TRANSACTION=false
HA_INSTALL_OR_CUTOVER=false
BROKER_OTA=false
HOST_REBOOT=false
OLD_TRANSACTION_REPLAY=false
NEXT_BOUNDARY=STOP_BEFORE_NEW_INSTALL_AUTHORIZATION
```

## 2. Classification

- The previously failed transaction remains terminal and no-replay.
- The current fresh transaction A is exclusively:
  `d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4`.
- The current durable phase is `ACTIVE / U4_READY_TO_INSTALL`.
- Exact target and predecessor archives are prepared, verified and fsynced.
- Home Assistant remains on exact predecessor 2026.10.4; target 2026.10.0 is not loaded.
- No install intent, install authority, authorization claim/consume or cutover has occurred for the new transaction.
- R8V13-08 remains blocked.

## 3. Capacity evidence

V1.3 dynamic internal-capacity admission was exercised on the real spare T1:

```text
ROOT_AVAILABLE_BYTES=4686041088
INTERNAL_CANDIDATE_REQUIRED_BYTES=2448560128
CAPACITY_HEADROOM_BYTES=2237480960
INTERNAL_CANDIDATE_CAPACITY=PASS
```

This is action-time capacity evidence only. Later predecessor release/import/protected-data steps continue to use their own action-time measurements.

## 4. Next bounded gate

The next real-T1 boundary remains inside R8V13-07 and may only use the existing product transaction/recovery mechanisms:

1. fresh U4 exact rebind;
2. if the existing release pin is expired and every non-expiry binding remains exact, refresh only `expires_at_unix`;
3. submit exactly one INSTALL intent for transaction `d86669e6...`;
4. issue one schema-v3 install authority using a valid `N3W_T1_CORE_UPDATER_...` authorization ID;
5. dispatch the existing `n3w-t1-ha-recovery-retry.service` product worker;
6. accept only `U13A_COMMITTED` or safe `U13B_ROLLED_BACK` as terminal;
7. on nonterminal durable state, do not replay and classify from the ledger.

Still excluded:

```text
OLD_TRANSACTION_REPLAY=false
BROKER_OTA=false
HOST_REBOOT=false
USB_FORMAT=false
USB_HISTORY_DELETE=false
R8V13_08_AUTO_ADVANCE=false
MERGE=false
RELEASE=false
```

Historical evidence already proves the expired-pin-only refresh path and the schema-v3 U5→terminal product path. No new recovery engine is required.

## 5. Stop point

```text
CURRENT_TASK=R8V13-07
CURRENT_TRANSACTION=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
CURRENT_PHASE=U4_READY_TO_INSTALL
R8V13_07_RESULT=NOT_PASS
R8V13_08_BLOCKED=true
NEXT_BOUNDARY=EXPLICIT_FRESH_TX_A_INSTALL_CUTOVER_AUTHORIZATION
```
