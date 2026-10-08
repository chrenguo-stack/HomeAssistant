# N3-W Clean-Product First-Pair Setup-Secret Handoff and Runtime Identity Design — 2026-10-07

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_DESIGN_20261007_01
STATUS=PASS
DESIGN_ONLY=true
PRODUCT_SOURCE_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false
```

## 1. Authority and purpose

This design follows the clean-product P4 blocker recorded in:

- `docs/development/N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_FIRST_PAIR_INTERRUPTION_ACCEPTANCE_BLOCKER_20261007.md`
- ADR-0008 `docs/adr/0008-n3w-pairing-recovery-simplification-v2.md`
- the frozen F1.0-RC2 N3-W product target at source `157448b621f288c5ac5038e7a1ac906cf2575a7f`
- the product design contract in `温室环境监测系统_分阶段技术开发路线_V0.5_双产品线与接口冻结版`, especially the first-pair QR flow and LCD page-5 state machine.

The blocked live board proved Wi-Fi, Manager discovery, TCP/47112 and `/hello` intake. It did not reach credential issuance because the normal-product route did not deliver the board-generated Setup Secret to the Manager before `/begin`.

This gate freezes the smallest product-aligned repair. It does not alter pairing cryptography, credential lifecycle, replay/high-water semantics, Broker relocation, Direct/Relay behavior or PR #474 RF scope.

## 2. Product behavior to restore

The original product UX is retained:

```text
node boot
-> configure Wi-Fi
-> discover Manager
-> LCD page 5 shows add-device QR
-> operator scans/confirms
-> Setup Secret enters Manager only through pairing.sock
-> authenticated pairing completes
-> Manager assigns NODE_ID and credentials
-> LCD leaves pairing QR and returns to normal status
```

The repair must not reintroduce USB serial capture, a filesystem Setup-Secret inbox, direct SQLite writes or a recovery helper as a normal-product pairing path.

## 3. LCD design: keep the existing five-page UI

The current F1.0-RC2 display already has five pages (`display_page % 5`). Page 4 is the fifth page and currently owns Wi-Fi provisioning / connected status.

Do not add a sixth page. Page 4 becomes state-sensitive:

### State A — Wi-Fi not connected

Keep the current behavior unchanged:

```text
LCD_PAGE_5=wifi_provisioning_qr
```

The existing `setup_qr` remains the Wi-Fi captive-portal QR.

### State B — Wi-Fi connected, product not yet provisioned

If `id(n3w_product_core).pairing_qr_payload()` returns a non-empty value:

```text
LCD_PAGE_5=n3w_pairing_qr
PAYLOAD=GHN3W2:<hardware_id>:<pairing_id>:<setup_secret>
```

Requirements:

- use a dedicated dynamic `pairing_qr` object;
- update the QR only when the payload changes;
- render the QR on the 64-pixel logical width with scale selected to fit the actual encoded payload;
- do not print the raw payload, pairing ID or Setup Secret as normal production log text;
- show only short user text such as `扫码添加设备` / `等待添加` outside the QR;
- if the pairing transaction renews and the payload changes, the LCD must replace the QR with the new exact payload.

The current payload length is expected to be about 107 ASCII bytes, but physical fit and scanability are acceptance conditions, not assumptions.

### State C — product provisioned

After the pairing acknowledgement commits, the Setup Secret and pairing intent are erased by the existing pairing client, so `pairing_qr_payload()` becomes empty.

Page 4 then returns to the existing connected-status display.

This makes the existing secret lifecycle itself control QR visibility; no new durable `show_pairing_qr` flag is introduced.

## 4. Manager-side supported import path

ADR-0008 remains authoritative: Setup Secret import occurs only through the Manager-owned local Unix socket (`pairing.sock`).

The existing `greenhouse-manager-pairing import` command remains supported. Add one bounded convenience operation for scanner/UI input:

```text
greenhouse-manager-pairing import-payload --payload-stdin
```

The command must:

1. read exactly one bounded `GHN3W2` payload from stdin;
2. strictly parse the hardware ID, pairing ID and Setup Secret;
3. validate the Setup Secret as 32 bytes encoded as unpadded base64url;
4. reject extra fields, malformed identifiers, oversized input and trailing non-whitespace data;
5. call the existing `import_setup_secret_over_socket(...)` function;
6. never write SQLite directly;
7. never put the Setup Secret in argv, process listings, logs, normal stdout or public evidence;
8. print only secret-safe status and hashes/lengths.

This CLI is the supported installer/backend client for the immediate source repair and physical acceptance. A later camera-based `greenhouse_system` / Home Assistant UI may feed the same exact payload into the same parser/socket path without changing the pairing protocol.

For clean-product physical acceptance, the `GHN3W2` value must be obtained by optically scanning the production LCD. USB serial, raw NVS extraction and lab-only firmware are forbidden substitutes.

## 5. Identity model: separate silicon binding from product runtime identity

The previous P1 tool called an esptool-derived MAC identity `HARDWARE_ID_SHA256`. P4 then observed a different hardware identity in the real Manager registration.

Do not freeze an unproven explanation that ROM/base MAC and Wi-Fi STA MAC must differ. The live discrepancy is real, but its low-level cause remains open.

The acceptance model is therefore split into two explicit identities.

### 5.1 Physical silicon binding

Before flash / first boot, esptool may bind the physical board using the factory/base MAC or another immutable silicon readout.

Public evidence uses:

```text
SILICON_BINDING_SHA256=<hash>
```

This proves that the same physical candidate is being used and that it is not historical Board A/B. It is not automatically asserted to be the product `hardware_id`.

### 5.2 Product runtime hardware identity

The product identity authority is the exact `hardware_id` generated by the running product pairing client.

It is bound after first boot by two independent product-path observations:

1. the hardware ID contained in the optically scanned LCD `GHN3W2` payload;
2. the hardware ID of the new Manager `pending` registration created by that first-pair transaction.

They must be byte-for-byte equal before Setup Secret import is allowed.

Public evidence uses only:

```text
PRODUCT_HARDWARE_ID_SHA256=<hash>
```

### 5.3 Manager-history clean-state check

Manager-history absence must no longer be queried using a guessed MAC-derived product identity before the board has exposed its real runtime identity.

Instead:

1. before first product boot, capture a read-only hashed set of all existing Manager hardware identities relevant to registration/credential/replay history;
2. after the clean board boots and sends `/hello`, require exactly one new pending product identity attributable to this acceptance window;
3. require the LCD-scanned hardware ID to equal that new pending identity;
4. before importing the Setup Secret, prove that this identity has no pre-existing approved NODE_ID, credential assignment, replay/high-water binding, retirement record or historical product ownership outside the newly created pending transaction.

This preserves the clean-product requirement without relying on a host-side MAC conversion rule.

## 6. Exact source-repair scope

The next source gate may modify only what is required for this repair, expected primarily in:

```text
firmware/esphome_rc/f1_0_rc2/packages/display.yml
firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml   # only if wiring is required
host/greenhouse-manager/src/greenhouse_manager/ops/n3w_pairing_cli.py
host/greenhouse-manager/src/greenhouse_manager/runtime/...       # parser helper only if justified
tools/execution_packages/n3w/auto_safe_fallback/...              # acceptance identity tooling
tests/...                                                         # source, parser, compile and executor guards
```

The existing product pairing cryptography and Manager coordinator behavior should remain unchanged unless a source review proves a direct defect.

Out of scope:

- changing the Setup Secret format;
- weakening `/begin` fail-closed behavior;
- automatic LAN transfer of the Setup Secret;
- direct database import;
- restoring the legacy filesystem inbox as product authority;
- changing replay/high-water policy;
- changing boot-session KF-050 semantics;
- changing Broker relocation / ESP-NOW / full-channel RF behavior;
- implementing a full consumer camera UI in this source-repair gate.

## 7. Source and CI acceptance

The source repair is not complete until CI proves at least:

### Board / display

- exact F1.0-RC2 N3-W target compiles;
- page count remains five;
- Wi-Fi provisioning QR remains available while Wi-Fi is not connected;
- a non-empty `pairing_qr_payload()` drives the pairing QR on page 5;
- an empty payload after provisioning restores connected status;
- pairing payload changes update the displayed QR;
- no raw `GHN3W2`, pairing ID or Setup Secret is emitted through normal production logs.

### Host import

- valid payload -> existing Manager socket import;
- malformed prefix -> reject;
- malformed hardware ID -> reject;
- malformed pairing ID -> reject;
- invalid/incorrect-length Setup Secret -> reject;
- extra fields / oversized input / trailing non-whitespace -> reject;
- secret never appears in normal output;
- no direct SQLite write path is introduced.

### Acceptance tooling

- silicon binding and product hardware identity use different field names and cannot be silently substituted;
- pre-boot Manager history snapshot cannot identify the target by guessed product MAC;
- post-boot import is blocked unless LCD payload hardware ID equals the new pending Manager identity;
- pre-existing credential/replay/ownership history blocks clean-product acceptance;
- only public-safe hashes are emitted.

## 8. Physical acceptance after source repair

The replacement exact artifact must be built and bound before physical execution.

Final clean-product acceptance must use a new genuinely clean candidate board. The current P4 board remains blocker evidence and must not be erased merely to manufacture a second `clean` starting state.

The first-pair physical sequence becomes:

```text
P1 silicon-clean readonly preflight
-> P2 healthy T1 baseline
-> P3 exact full product flash, no normal boot
-> P4 arm Manager-history-before snapshot
-> first normal boot
-> configure Wi-Fi
-> observe new pending Manager identity
-> optically scan LCD GHN3W2
-> bind scanned hardware_id == new pending hardware_id
-> prove no prior history for that product identity
-> import scanned payload through pairing.sock client
-> observe pairing COMMIT
-> perform the already-designed KF-050 controlled interruption window
-> prove valid boot session and >=2 canonical advances
```

## 9. Security invariants

```text
SETUP_SECRET_PUBLIC_LOGGING=false
SETUP_SECRET_PUBLIC_EVIDENCE=false
SETUP_SECRET_ARGV=false
SERIAL_SECRET_CAPTURE_FOR_FINAL_ACCEPTANCE=false
RAW_NVS_SECRET_EXTRACTION_FOR_FINAL_ACCEPTANCE=false
PAIRING_SOCKET_AUTHORITY=true
DIRECT_SQLITE_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
LEGACY_RECOVERY_HELPER=false
```

## 10. Gate disposition

```text
DESIGN=PASS
FIRST_PAIR_QR_PRODUCT_DIRECTION=FROZEN
LCD_PAGE_COUNT=5
PAIRING_QR_PAGE=5
PAIRING_QR_SOURCE=product_pairing_qr_payload
PAIRING_IMPORT_AUTHORITY=manager_owned_pairing_socket
SILICON_BINDING_AND_PRODUCT_IDENTITY=SEPARATE_AUTHORITIES
MAC_RELATION_ROOT_CAUSE=OPEN_NOT_REQUIRED_FOR_ACCEPTANCE
CURRENT_BLOCKED_BOARD_REUSE_AS_CLEAN=false
MERGE=false

NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_SOURCE_REPAIR_20261007_01
```
