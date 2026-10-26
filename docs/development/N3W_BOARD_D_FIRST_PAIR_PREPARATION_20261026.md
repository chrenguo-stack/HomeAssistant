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

## 4. Board D QR availability — corrected by exact firmware review

The initial preparation assumption that the Board D pairing QR could be captured while the T1 pairing window remained CLOSED was incorrect and is superseded by this section.

Exact deployed Board D firmware behavior proves:

```text
discover_manager()
-> POST /hello
-> accepted hello with HelloNextAction::PROCEED
-> pairing_handoff_ready_=true
-> LCD pairing QR becomes eligible
```

At the beginning of every hello attempt, `pairing_handoff_ready_` is reset to false. A closed T1 pairing window therefore leaves Board D on the product LCD state:

```text
正在查找主机
```

The observed live state exactly matches that source contract.

Therefore the QR cannot be pre-captured before the first live window. No Board fault is inferred.

## 5. KF-044 adaptation to the actual current product sequence

KF-044's safety intent remains valid: do not spend the fixed pending TTL on avoidable preparation or authorization work.

The current product creates/observes the first pending registration during the accepted hello path that also unlocks the LCD QR. Therefore the safe sequence is:

```text
ALL NON-SECRET PREPARATION COMPLETE
-> LIVE AUTHORIZATION GRANTED
-> OPEN ONE 300s DYNAMIC PAIRING WINDOW
-> BOARD D DISCOVERY + ACCEPTED HELLO
-> PENDING TTL STARTS
-> LCD QR APPEARS
-> OPERATOR SCANS QR IMMEDIATELY
-> LOCAL HIDDEN-INPUT QR VALIDATION
-> EXACT PENDING PRETRANSFER TTL GATE
-> IMMEDIATE UDS SETUP SECRET IMPORT VIA STDIN
-> FIRST PAIR COMPLETES
-> EXACT SUCCESS EVIDENCE
-> CLOSE SUCCESS
```

The historical filesystem delivery chain is not current product authority. The filesystem inbox remains LAB_ONLY.

For this gate:

- no serial capture;
- no Setup Secret file is transferred to T1;
- no `predelivery` filesystem gate is used;
- the existing read-only `pretransfer` gate is reused to bind exact hardware ID, pairing-ID SHA-256, pending state and TTL;
- the Setup Secret is immediately imported via Manager-owned `pairing.sock` using stdin.

Because the operator must scan the LCD QR after the pending window has already started, the original preparation value of 100 seconds remaining is too aggressive for the normal product UI path and is superseded.

Frozen timing policy for this Board D acceptance:

```text
PAIRING_WINDOW_SECONDS=300
PENDING_TTL_EXPECTED_SECONDS=120
MIN_PENDING_TTL_REMAINING_SECONDS=60
```

A 60-second remaining margin is the minimum admission floor. This preserves a full minute for the UDS import and protocol completion while allowing the required human QR scan. The existing gate still fails closed below the floor.

All commands, SSH authentication paths, source bindings and abort/close paths must be prepared before the window is opened. The only human action permitted after pending begins is the immediate QR scan/copy into the already prepared hidden-input path.

## 6. Live private QR binding

Because exact firmware requires an accepted hello before the QR becomes available, private QR binding occurs only after the new live authorization has been explicitly granted and the single dynamic pairing window has opened.

Before that authorization is requested, the hidden-input local QR validator and the complete fail-closed live command chain must already be prepared. Once the LCD QR appears, the operator scans it and pastes the payload locally without sending it to ChatGPT or GitHub.

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

Fresh preauthorization read-only evidence is now complete:

```text
SOURCE_REBIND=PASS
PRODUCT_PATH_REVIEW=PASS
KF043_ADAPTATION=PASS:NO_SERIAL_NORMAL_PRODUCT_PATH
KF044_ADAPTATION=PASS:POST_HELLO_HIDDEN_QR_CAPTURE_PLUS_PRETRANSFER_TTL_GATE
LCD_PREAUTH_STATE=正在查找主机:EXPECTED_WITH_WINDOW_CLOSED

BOARD_D_MDNS_RESOLVE=PASS
BOARD_D_NATIVE_API_TCP_6053=PASS
BOARD_D_PRIVATE_LOCATOR_LOCAL_ONLY=true

T1_HOST_KEY_BINDING=PASS
T1_PREAUTH_INSPECT=PASS
T1_PAIRING_WINDOW_STATE=CLOSED
T1_PAIRING_UDP_LISTENER_COUNT=0
T1_PAIRING_HTTP_LISTENER_COUNT=0
T1_FIRST_PAIR_COUNTS_CLEAN=true
T1_SECURITY_COUNTS_CLEAN=true
T1_TRANSACTION_PRESENT=false
T1_SUCCESSOR_RECOVERY_PRESENT=false
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RUNNING=true
HOMEASSISTANT_RESTART_COUNT=0
T1_INSPECT_MUTATION=false

NEW_PRODUCT_SOURCE_REPAIR_REQUIRED=false
PRIVATE_QR_BINDING=DEFERRED_UNTIL_ACCEPTED_HELLO_BY_PRODUCT_CONTRACT
LIVE_COMMAND_CHAIN_PREARMED=true
LIVE_AUTHORIZATION_GRANTED=true
LIVE_AUTHORIZATION=N3W_T1_BOARD_D_FIRST_PAIR_LIVE_ACCEPTANCE_20261026_01
LIVE_AUTHORIZATION_CLAIMED=false
LIVE_AUTHORIZATION_CONSUMED=false
NEXT_STOP=ONE_SHOT_LIVE_EXECUTION
```

The pre-armed live chain is frozen as:

```text
fresh binding/SSH master
-> one onboarding open
-> accepted hello/pending
-> hidden local QR capture
-> hardware hash + pairing hash binding
-> pretransfer TTL >= 60 seconds
-> immediate pairing.sock Setup Secret import via stdin
-> bounded read-only exact success-evidence polling
-> close success only on exact evidence
-> otherwise close abort
-> final closed-exposure/continuity evidence
```

No automatic second first-pair attempt is permitted.



## 12. Live authorization granted

```text
AUTHORIZATION=N3W_T1_BOARD_D_FIRST_PAIR_LIVE_ACCEPTANCE_20261026_01
GRANTED=true
CLAIMED=false
CONSUMED=false
SECOND_ATTEMPT_ALLOWED=false
```

The authorization becomes consumed only when the onboarding transaction is claimed/opened. Pre-open SSH/control/capability checks remain non-claiming. Any post-open failure must fail closed and must not auto-retry.


## 13. First live invocation pre-claim STOP — authorization ID grammar

The first attempted live invocation did not claim an onboarding transaction and did not open a pairing window.

Observed public-safe result:

```text
EXACT_MAIN_OBJECT=PASS
EXACT_ONBOARDING_TOOL=PASS
TARGET_BINDING=PASS
T1_HOST_KEY=PASS
SSH_MASTER_CONNECT=PASS
MANAGER_CONTAINER_BINDING=PASS
LIVE_CHAIN_CAPABILITY_PREFLIGHT=PASS

OPEN_RESULT=STOP
ERROR=authorization_id_invalid
MUTATION_STATE=NONE
AUTHORIZATION_REUSABLE=null
OPEN_RC=2
```

Source review proves `tools/n3w_t1_first_pairing_onboarding.py::_authorization_id()` requires:

```text
authorization_id.startswith("N3W_T1_FIRST_PAIRING_")
length <= 200
only alphanumeric / underscore / hyphen
```

The previously proposed ID:

```text
N3W_T1_BOARD_D_FIRST_PAIR_LIVE_ACCEPTANCE_20261026_01
```

does not satisfy the required prefix and is therefore retired as an invalid execution identifier. It was never claimed or consumed by the product.

Corrected prospective live authorization ID:

```text
N3W_T1_FIRST_PAIRING_BOARD_D_LIVE_ACCEPTANCE_20261026_01
```

This is a new exact authorization identifier for the same previously frozen one-attempt scope. It is NOT granted merely by this correction.

```text
PREVIOUS_INVALID_AUTHORIZATION_ID_CLAIMED=false
PREVIOUS_INVALID_AUTHORIZATION_ID_CONSUMED=false
PAIRING_WINDOW_OPENED=false
T1_MUTATION=false
BOARD_MUTATION=false
CORRECTED_AUTHORIZATION_GRANTED=false
SECOND_ATTEMPT_COUNT=0
```


## 14. Corrected live authorization granted

```text
AUTHORIZATION=N3W_T1_FIRST_PAIRING_BOARD_D_LIVE_ACCEPTANCE_20261026_01
GRANTED=true
CLAIMED=false
CONSUMED=false
SECOND_ATTEMPT_ALLOWED=false

PREVIOUS_INVALID_ID=N3W_T1_BOARD_D_FIRST_PAIR_LIVE_ACCEPTANCE_20261026_01
PREVIOUS_INVALID_ID_CLAIMED=false
PREVIOUS_INVALID_ID_CONSUMED=false
FIRST_PAIR_ATTEMPT_COUNT=0
```

This corrected authorization preserves the already frozen one-attempt scope. It becomes consumed only if the onboarding transaction is successfully claimed.
