# N3-W T1 Core Stack Clean Reference R3 sensorless real first-registration execution plan

## 1. Frozen decision

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_SENSORLESS_REAL_FIRST_REGISTRATION_20261102_01
STATE=FROZEN_READY_FOR_EXACT_FIRMWARE_ARTIFACT_AND_PREEXECUTION
T1_PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
SOURCE_REVIEW_HEAD=e091ec469ebdacb146a84931344aa8931aa14be1

NODE_PROFILE=FRESH_ESP32_C6
LCD_REQUIRED_FOR_PRODUCT_FLOW=true
USB_SERIAL_REQUIRED_FOR_ACCEPTANCE_EVIDENCE=true
SCD30_CONNECTED=false
SHT30_CONNECTED=false
BH1750_CONNECTED=false
RS485_SOIL_CONNECTED=false
LORA_CONNECTED=false

REGISTRATION_PATH=NORMAL_PRODUCT_PATH
DIRECT_DATABASE_WRITE=false
DIRECT_CREDENTIAL_INJECTION=false
LEGACY_ONBOARDING_PATH=false
READINESS_BRIDGE_ENTRY_GATE=false

POST_CAPTURE_RULE=COMMIT_THEN_IMMEDIATE_NODE_POWER_OFF_THEN_T1_POST_SNAPSHOT
TELEMETRY_INTERVAL_SECONDS=60

MERGE=false
```

This document freezes the R3 execution route after re-reading the frozen first-registration design, current product source and current exact CI evidence. The objective is one real first registration on the already-running Clean Reference T1, followed by semantic PRE/POST comparison.

The earlier pairing-readiness bridge is retained only as historical/diagnostic material. It is not an R3 entry authority and must not be repaired further merely to permit this execution.

## 2. Why this is the correct R3 boundary

R0/R1 established the Clean Reference host and exact product stack. R2A/R2B then proved a real production start, one real host reboot and persistent restoration of Broker, Manager and Home Assistant.

R3 therefore starts from a real zero-node production runtime and proves the transition:

```text
healthy zero-node production T1
-> one normal first-registration transaction
-> durable Manager COMMIT
-> healthy one-node production T1
```

R3 is not the sensor/telemetry/HA/ESP-NOW runtime acceptance stage. Those remain downstream physical-runtime work.

## 3. Current source and simulated-flow proof

The current repository head contains the complete scan-triggered registration implementation: registration discovery, node-local registration portal, TLS-pinned 47110 bootstrap, identity/source-bound 47112 pairing, simplified pairing, durable ledger, pending-ACK status recovery and post-commit product runtime loading.

A source comparison from the T1 product authority head to the review head found no changes under:
- `firmware/esphome_rc/**`;
- `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_*`;
- `host/greenhouse-manager/src/greenhouse_manager/runtime/registration.py`.

Current-head evidence:
- greenhouse-manager CI run `41382450590`: SUCCESS;
- full Manager pytest: `1486 passed, 1 skipped`;
- R8 simulated first-registration E2E: `8 passed`;
- F1.0-RC2 firmware CI run `41382450749`: SUCCESS;
- exact N3-W target compile: PASS.

The R8 simulated E2E exercises:
- discovery;
- user selection boundary;
- 47110 confirmation;
- durable ACTIVE / BOOTSTRAP_ACCEPTED;
- temporary 47112 OPEN;
- HELLO / BEGIN / ESTABLISH;
- Setup Secret proof;
- encrypted credential delivery;
- BUNDLE_STAGED;
- final delivery-digest ACK;
- Registration APPROVED;
- active NODE_ID lease;
- CredentialLifecycle generation 1 ACTIVE;
- application-key availability;
- DynSec client/role creation;
- durable COMMITTED;
- 47112 close;
- RAM intent clear;
- pending-ACK exact digest recovery;
- source/hardware/pairing binding rejection;
- second-node busy behavior;
- multi-candidate no-auto-selection behavior.

No R3 product-design blocker was found in this review.

## 4. Sensorless hardware profile

The real R3 board uses:
- one ESP32-C6 production node board;
- LCD12864 connected so the normal QR/product UX is exercised;
- USB connected for exact firmware write and serial evidence;
- stable USB power during preparation and registration.

The following remain physically disconnected:
- SCD30;
- SHT30;
- BH1750;
- RS485 soil temperature/moisture/EC;
- LoRa;
- solar/battery power subsystem.

Source review found no first-registration dependency on those sensors. The sensor entities may have no state, while registration is owned by Wi-Fi and `greenhouse_n3w_core`.

## 5. Telemetry isolation rule

The N3-W production target defines:

```text
n3w_telemetry_interval=60s
```

After first-registration COMMIT, firmware loads the persisted product state, configures MQTT, enables the MQTT client and starts the N3-W runtime. Missing sensor numeric values are omitted and quality fields may still be emitted, so disconnecting sensors alone does not guarantee zero telemetry.

Therefore the R3 evidence rule is:

```text
Manager COMMIT proven
-> node reports registration success
-> operator immediately removes node power
-> T1 POST snapshot is collected with node off
```

Operational target: power off as soon as success is observed, preferably within 10 seconds. This is evidence hygiene, not a product protocol deadline.

The frozen protocol already requires the node to persist the credential bundle before final ACK. Power removal after a proven Manager COMMIT is therefore after the durable registration boundary.

If telemetry is observed before power removal, R3 does not automatically fail. It is classified separately as post-registration runtime activity and must not be confused with first-registration transaction state.

## 6. PRE snapshot

PRE is collected after:
- exact firmware is written;
- the board is confirmed fresh/unregistered;
- Wi-Fi has been configured through the normal captive-portal path;
- the board is on the trusted product LAN;
- the registration QR is visible;
- the user has not yet started the QR registration session.

PRE must prove at least:

### Host/runtime continuity
- system running;
- zero failed units;
- Broker, Manager and Home Assistant running;
- Manager restart count unchanged;
- production units active;
- trusted-product-LAN state valid;
- registration ingress guard active.

### Listener state
- TCP/47110 = 1;
- UDP/47111 = 1;
- TCP/47112 = 0;
- Manager pairing window = CLOSED.

### Stable system authority
- SYSTEM_ID binding unchanged;
- Broker CA/TLS public identity unchanged;
- system peer-trust identity/generation unchanged;
- R2A/R2B durable transaction authority unchanged.

### Zero-node business state for the fresh board
- no registration for the board hardware identity;
- no current NODE_ID lease for the board;
- no credential assignment for the board;
- no application-key epoch for a board NODE_ID;
- no deterministic DynSec node client/role for the board;
- no first-registration attempt for its pairing identity;
- no active first-registration transaction.

Raw hardware ID, pairing ID, Setup Secret, MQTT password and key material are private evidence only and must not be committed to the public repository.

## 7. Registration execution

The operator follows the normal product UX:

```text
LCD registration QR
-> phone opens node-local registration page
-> bounded T1 discovery
-> user selects/confirms the intended T1
-> node TLS-pins the selected 47110 endpoint
-> node sends gh.registration.confirm/1
-> T1 creates durable ACTIVE attempt
-> exact 47112 window opens
-> existing simplified pairing executes
-> credential bundle is persisted by node
-> final delivery-digest ACK
-> Manager durable COMMIT
-> 47112 closes
-> node reports registration success
```

No SSH/USB command may directly write NODE_ID, registration rows, MQTT credentials, application keys or DynSec node identities.

## 8. Transaction evidence

R3 must retain enough evidence to prove the ordered transition, without requiring continuous high-frequency system snapshots:

```text
BOOTSTRAP_ACCEPTED
HELLO_OBSERVED
BUNDLE_STAGED
COMMITTING
COMMITTED / TERMINAL / COMPLETE
```

Required order properties:
- durable ACTIVE precedes successful 47110 acceptance;
- prestate ownership evidence precedes DynSec/application-key creation;
- BUNDLE_STAGED precedes credential release;
- COMMITTING precedes external final commit;
- COMMITTED is written only after the exact cross-store commit oracle passes;
- successful COMMIT closes 47112.

## 9. POST snapshot

POST is collected with the node powered off immediately after successful COMMIT.

Expected changed domains:
- exactly one first-registration ledger tombstone for this transaction;
- ledger final `state=COMMITTED`, `phase=TERMINAL`, `cleanup_state=COMPLETE`;
- registration = APPROVED;
- one automatically allocated opaque NODE_ID;
- NODE_ID lease = ACTIVE for the same hardware identity;
- one ACTIVE CredentialLifecycle assignment, generation 1, no pending generation;
- exact initial application-key epoch ACTIVE/enabled and no conflicting ACTIVE/GRACE epoch;
- exact deterministic generation-1 DynSec client/role/ACL plan exists;
- pairing/registration history contains the successful transaction.

Expected unchanged domains:
- T1 host identity;
- SYSTEM_ID;
- Broker CA/TLS identity;
- Broker/Manager/Home Assistant container continuity;
- Manager restart count;
- trusted-product-LAN authority;
- registration ingress guard;
- system peer trust identity/generation/key binding;
- R2 stable system authority.

Expected quiescent final state:
- TCP/47110 = 1;
- UDP/47111 = 1;
- TCP/47112 = 0;
- pairing window CLOSED;
- no RAM first-registration intent;
- no REQUIRED/FAILED cleanup;
- no unresolved UNKNOWN reconciliation.

## 10. Commit oracle

R3 PASS requires all four T1-side commit-oracle domains to agree:

```text
RegistrationRegistry:
  exact pairing/hardware/node binding
  registration APPROVED
  node lease ACTIVE

CredentialLifecycle:
  ACTIVE
  exact pairing/node binding
  active_generation=1
  pending_generation=null

Application key:
  recorded epoch ACTIVE + enabled
  key-file/hash binding valid
  no conflicting ACTIVE/GRACE epoch

DynSec:
  deterministic generation-1 client/role exists
  exact role assignment/priority/ACL match
```

A row-count-only success claim is forbidden.

## 11. Stop conditions

Stop before QR confirmation if any PRE invariant fails.

After the transaction starts:
- do not manually delete or rewrite transaction state;
- do not reuse a terminal pairing ID;
- do not reset T1 business state to manufacture a clean result;
- do not interpret a partial store match as COMMITTED;
- UNKNOWN remains fail-closed;
- any Manager restart is a separate recovery case and cannot be silently accepted as the normal success path.

If the board fails because a disconnected sensor causes a true boot/reboot blocker, classify it as a board-firmware integration defect and stop before modifying T1.

## 12. Out of scope

R3 does not require:
- valid sensor measurements;
- MQTT telemetry acceptance;
- HA discovery/entity acceptance;
- Direct/Relay failover;
- ESP-NOW relay traffic;
- long-duration runtime stability;
- LoRa;
- solar/battery operation.

Those are downstream physical-runtime acceptance domains.

## 13. Execution stages

```text
E0  freeze this plan
E1  produce exact current-head factory firmware artifact
E2  operator connects sensorless board + LCD + USB
E3  read-only USB enumeration and board identity evidence
E4  erase/write exact factory image and verify boot
E5  captive-portal Wi-Fi setup; prove idle unregistered QR
E6  collect T1 PRE snapshot
E7  user scans QR and confirms intended T1
E8  observe durable COMMIT
E9  immediately power off board
E10 collect T1 POST snapshot
E11 semantic PRE/POST compare and archive
```

Board flash/erase and live first registration are physical mutations. They occur only through the explicit execution route and must remain evidence-bound. Merge remains separately authorized.
