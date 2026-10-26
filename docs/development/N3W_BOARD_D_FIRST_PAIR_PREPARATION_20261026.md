# N3-W Board D First-Pair Preparation and New Authorization — 2026-10-26

## 1. Task and boundaries

```text
TASK=N3W_T1_BOARD_D_FIRST_PAIR_PREPARATION_AND_NEW_AUTHORIZATION
MAIN=507dbd49495c558b1344f7d713938b733b3bad18
T1_DEPLOYED_PRODUCT_SOURCE=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
BOARD_D_PRODUCT_SOURCE=ec5f6d68e33db7757d91c807fff708ca81b075dc

REPOSITORY_MUTATION=DOCS_ONLY
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
PAIRING_WINDOW_OPEN=false
SETUP_SECRET_IMPORT=false
FIRST_PAIR_EXECUTION=false
MERGE=false
```

This stage prepares the next one-shot Board D first-pair acceptance. It does not itself authorize a pairing window or first pair.

The immediately preceding Wi-Fi recovery gate is CLOSED_PASS. Board D has rejoined the normal site Wi-Fi, fresh ESPHome mDNS and Native API TCP liveness are proven, and final T1 onboarding inspect remains clean with the pairing window CLOSED.

## 2. Fresh source rebind

Repository main remains:

```text
507dbd49495c558b1344f7d713938b733b3bad18
```

The deployed T1 source authority is:

```text
03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
```

The following first-pair components are present in the deployed T1 source and match the current-main implementations used for this preparation:

```text
tools/n3w_t1_first_pairing_onboarding.py
  blob=332a59ad083e1db1c29de174139b3f45342c5fa8

host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_dynamic_pairing_window.py
  blob=1b95c85ac3ec2755f69f0ca4db40315d59272379

host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_pairing_local_ipc.py
  blob=ca709cbe7d86b70055f88800de2b4d6751fd95ff

host/greenhouse-manager/src/greenhouse_manager/ops/n3w_setup_secret_handoff_delivery_gate.py
  blob=09270f4c512b83efecd438c9f26394f3e99b64f8
```

The deployed Manager package includes all required entry points:

```text
greenhouse-manager-pairing
greenhouse-manager-n3w-setup-secret-delivery-gate
```

No product-source repair is required by this preparation review.

## 3. Current product Setup Secret path

ADR-0008 is authoritative for the normal product path.

The old filesystem Setup Secret inbox is LAB_ONLY and must not be revived for this Board D acceptance.

The normal product path is:

```text
Board D LCD QR
GHN3W2:<hardware_id>:<pairing_id>:<setup_secret>
-> private operator handoff
-> greenhouse-manager-pairing import --setup-secret-stdin
-> Manager-owned pairing.sock
-> SimplifiedPairingCoordinator.import_setup_secret()
```

The Manager-owned socket is local-only and uses the current product IPC framing and response-schema guards.

Therefore:

```text
SERIAL_SETUP_SECRET_CAPTURE=FORBIDDEN_FOR_NORMAL_PRODUCT_PATH
FILESYSTEM_SETUP_SECRET_INBOX=FORBIDDEN_FOR_NORMAL_PRODUCT_PATH
SETUP_SECRET_ON_COMMAND_LINE=FORBIDDEN
SETUP_SECRET_IN_CHAT=FORBIDDEN
SETUP_SECRET_IN_GITHUB=FORBIDDEN
```

KF-043 is satisfied by avoiding the serial capture path entirely in this normal product flow.

## 4. Board D QR availability

The deployed Board D product source enables the first-pair QR only when:

- Wi-Fi is connected;
- the node is not yet provisioned;
- pairing handoff material is ready.

The LCD page-4 product flow shows the pairing QR and the user-facing text “扫码添加节点 / 等待添加”.

The QR payload is generated from the device-held current hardware ID, pairing ID and Setup Secret.

The operator can therefore capture and privately bind the exact QR before opening any T1 pairing window.

This ordering is important:

```text
PRIVATE_QR_CAPTURE
-> HASH BINDING
-> LIVE AUTHORIZATION
-> OPEN PAIRING WINDOW
-> EXACT PENDING OBSERVATION
-> TTL MARGIN GATE
-> UDS SETUP SECRET IMPORT
-> FIRST PAIR
```

It prevents the 120-second pending TTL from being consumed while the operator is still preparing the private handoff.

## 5. KF-044 adaptation to current product architecture

KF-044's safety intent remains valid: do not spend the fixed pending TTL on preparation or authorization work.

The historical filesystem delivery chain is not current product authority.

For this gate, the equivalent current-product protection is:

1. capture the LCD QR privately before opening the window;
2. pre-stage all commands and exact source bindings before live authorization;
3. after open, wait only for the exact Board D pending registration;
4. run the existing delivery gate in `pretransfer` mode only;
5. require a large remaining-TTL margin;
6. immediately import the Setup Secret over Manager-owned UDS stdin;
7. never stage or atomically rename a Setup Secret file on T1.

Frozen timing policy:

```text
PAIRING_WINDOW_SECONDS=300
PENDING_TTL_EXPECTED_SECONDS=120
MIN_PENDING_TTL_REMAINING_SECONDS=100
```

If the exact pending session cannot be observed with at least 100 seconds remaining, the attempt must fail closed and the onboarding window must be aborted. No second automatic attempt is permitted.

The `predelivery` filesystem gate is not used because the product delivery is UDS, not filesystem inbox.

## 6. Pre-authorization private QR binding

Before requesting the new live authorization, the operator must privately capture the current Board D LCD QR without sending the payload to ChatGPT or GitHub.

The local private result must prove only public-safe metadata:

```text
QR_SCHEMA=GHN3W2
HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
PAIRING_ID_SHA256=<fresh private-derived hash>
SETUP_SECRET_LENGTH=43
SETUP_SECRET_DECODED_BYTES=32
PRIVATE_HANDOFF_MODE=0600
RAW_HARDWARE_ID_PUBLIC=false
RAW_PAIRING_ID_PUBLIC=false
SETUP_SECRET_PUBLIC=false
```

The private handoff is retained only on the operator's Mac and is never committed.

If the hardware hash does not equal the frozen Board D hardware binding, STOP.

## 7. Final live preflight before authorization claim

After private QR binding, but before any pairing-window open:

1. fresh Board D mDNS resolve and Native API TCP reachability;
2. confirm LCD pairing QR remains available and Board D is still unprovisioned;
3. fresh T1 onboarding `inspect`;
4. require pairing window CLOSED;
5. require UDP/47111 and TCP/47112 listener counts 0;
6. require all first-pair and security counts 0;
7. require no transaction or successor recovery;
8. require Broker, Manager and Home Assistant running with unchanged restart counts;
9. bind the current Board D private IPv4 as the dynamic window peer;
10. pre-stage the exact live command sequence without executing it.

## 8. Prospective live authorization

The next live authorization is proposed as:

```text
N3W_T1_BOARD_D_FIRST_PAIR_LIVE_ACCEPTANCE_20261026_01
```

It is NOT granted by this preparation document.

If explicitly granted later, it authorizes exactly one first-pair attempt consisting of:

- one onboarding transaction claim;
- one 300-second Manager-owned dynamic pairing window;
- one exact Board D pending-session observation;
- one pretransfer TTL gate requiring at least 100 seconds remaining;
- one private Setup Secret import over Manager-owned pairing.sock using stdin;
- one Board D first-pair transaction;
- read-only verification of exact registration, NODE_ID lease, MQTT credential generation 1, application-key epoch 1 and peer-trust generation 1;
- one success close if and only if all success evidence is exact;
- otherwise one abort/fail-closed close;
- final proof that 47111/47112 and pairing.sock are closed and Broker/Manager/Home Assistant continuity is preserved.

Not authorized:

- a second first-pair attempt;
- Setup Secret in argv/chat/GitHub;
- serial access;
- NVS erase/restore;
- Flash/OTA;
- Wi-Fi reprovisioning replay;
- Manager/Broker/Home Assistant restart as a normal success action;
- Direct/Relay/RF acceptance;
- merge.

## 9. Success binding

A successful close must additionally match the private pre-bound Board D identity:

```text
SUCCESS_EVIDENCE.hardware_id_sha256 == BOARD_D_HARDWARE_ID_SHA256
SUCCESS_EVIDENCE.pairing_id_sha256 == PRIVATE_QR_PAIRING_ID_SHA256
credential_generation == 1
application_key_epoch == 1
peer_trust_generation == 1
```

The onboarding tool's normal close-success evidence remains authoritative for database/security-state exactness.

## 10. Stop policy

Stop before live authorization if:

- QR hardware hash mismatch;
- QR is unavailable while Board D is otherwise expected unprovisioned;
- mDNS/API liveness is lost;
- T1 is not clean/CLOSED;
- deployed source/image binding drifts;
- any secret-safe preparation step would require serial;
- any plan attempts to reuse filesystem inbox as the normal product path.

During the live attempt, any exact-pending mismatch, TTL margin failure, UDS import rejection, partial security state, timeout or continuity violation must fail closed. Do not auto-retry.

## 11. Current preparation result

```text
SOURCE_REBIND=PASS
PRODUCT_PATH_REVIEW=PASS
KF043_ADAPTATION=PASS:NO_SERIAL_NORMAL_PRODUCT_PATH
KF044_ADAPTATION=PASS:PRECAPTURE_PLUS_PRETRANSFER_TTL_GATE
NEW_PRODUCT_SOURCE_REPAIR_REQUIRED=false
PRIVATE_QR_BINDING=PENDING_OPERATOR_LOCAL_CAPTURE
LIVE_AUTHORIZATION_GRANTED=false
NEXT_STOP=PRIVATE_QR_BINDING_AND_FRESH_PREAUTH_READONLY_PREFLIGHT
```
