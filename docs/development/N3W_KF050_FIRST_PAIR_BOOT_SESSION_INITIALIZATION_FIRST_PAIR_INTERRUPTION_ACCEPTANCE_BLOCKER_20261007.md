# N3-W KF-050 First-Pair Interruption Acceptance — Product Blocker — 2026-10-07

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_FIRST_PAIR_INTERRUPTION_ACCEPTANCE_20261006_01
STATUS=STOP_PRODUCT_BLOCKER
KF050_FIRST_PAIR_INTERRUPTION_ACCEPTANCE=BLOCKED
MERGE=false
BOARD_ERASE=false
BOARD_REFLASH=false
PAIRING_REPAIR=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
RECOVERY_FLOOR_EXECUTION=false
```

## 1. Bound product authority

```text
SOURCE_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
ARTIFACT_ID=11320812037
RELEASE_ZIP_SHA256=44610382a0e7d9c04e4445e873b9d99fd9a781d18fd497f39cb382d3fce3b3ff
```

The board had already passed the clean-board preflight, T1 healthy-Broker-A preparation, full erase, exact four-region flash and per-region readback verification. Normal product firmware boot was then started for first-pair acceptance.

## 2. Live result

The board successfully left the provisioning AP, joined the normal WLAN and became bidirectionally reachable. Live T1 capture proved repeated successful TCP handshakes on the simplified-pairing port. Manager registration state for the real runtime hardware identity is present and remains pending.

Public-safe live state at the stop point:

```text
RUNTIME_HARDWARE_ID_SHA256=9c907d6e26ba9b19fad02befbdd0d0e7a2b18b736ab36e9426983680b27b7171
REGISTRATION_STATE=pending
PAIRING_EPOCH_AUDIT_VALUE=15
NODE_ID_PRESENT=false
CREDENTIAL_ASSIGNMENT_COUNT=0
REPLAY_COUNT=0
CANONICAL_TELEMETRY_COUNT=0
MANAGER_RESTART_COUNT=0
```

The registration event history starts with `hello_created` and then repeatedly records `hello_superseded`; one expiration is visible before the next hello replacement. The node never reaches credential issuance or Manager COMMIT.

## 3. Acceptance-tool identity binding defect

The clean-board preflight derived its public hardware identity from the ROM MAC read by esptool. The actual product runtime derives `hardware_id` from `esp_read_mac(..., ESP_MAC_WIFI_STA)`.

Therefore:

```text
PREFLIGHT_ROM_IDENTITY_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
RUNTIME_STA_IDENTITY_SHA256=9c907d6e26ba9b19fad02befbdd0d0e7a2b18b736ab36e9426983680b27b7171
IDENTITY_BINDING_MATCH=false
```

The initial P4 monitor watched the ROM-derived identity and was stopped once this mismatch was proven. No board/T1/replay/high-water mutation was used to compensate for the tooling error.

This also means the P1 Manager-history absence evidence must be reconciled against the STA-derived product identity before final clean-product acceptance can be claimed.

## 4. Product Setup Secret blocker

ADR-0008 freezes the product Setup Secret intake contract as a Manager-owned local Unix-domain socket. The Manager pairing coordinator requires the exact `(hardware_id, pairing_id)` Setup Secret to have been imported before `/begin`; otherwise `begin()` rejects with `setup_secret_unavailable`.

The exact product firmware exposes the secret only through `SimplePairingClient::pairing_qr_payload()`, which returns a `GHN3W2:<hardware_id>:<pairing_id>:<setup_secret>` payload. Repository board-lab configuration has wiring that periodically emits this payload to serial, but the exact F1.0-RC2 production target does not wire `pairing_qr_payload()` into its production display, Web/API surface, or normal product logging path.

The observed live behavior matches this missing handoff path:

```text
Wi-Fi=PASS
Manager discovery=PASS
TCP_47112_HANDSHAKE=PASS
HELLO_INTAKE=PASS
REGISTRATION=pending
CREDENTIALS=0
NODE_ID=absent
CANONICAL=0
```

Using a lab serial capture, raw NVS extraction, legacy recovery helper, or direct database manipulation to obtain/import the Setup Secret would bypass the missing normal-product provisioning surface. Such a bypass is not acceptable as Final Product Acceptance evidence.

## 5. Disposition

This gate is stopped without declaring KF-050 itself failed. The immediate blocker is the clean-product first-pair provisioning path.

Required follow-up before physical acceptance resumes:

1. define one supported normal-product way for the user/operator to obtain the board-bound `GHN3W2` payload without lab-only firmware or secret leakage;
2. deliver that payload to a CLI/UI client that imports it only through the Manager-owned pairing socket;
3. align clean-board/P4 tooling to the product STA-derived hardware identity rather than the esptool ROM-MAC identity;
4. add source/CI coverage proving production-target exposure and identity binding;
5. build and bind a replacement exact artifact;
6. restart clean-product physical acceptance from an authority-consistent state rather than forcing the current board to PASS with engineering extraction.

```text
FINAL_CLEAN_PRODUCT_STATE_ACCEPTANCE=BLOCKED
PR522_MERGE=false
NEXT_ONE_GATE=REQUIRES_EXPLICIT_FOLLOWUP_DESIGN_AUTHORIZATION
```
