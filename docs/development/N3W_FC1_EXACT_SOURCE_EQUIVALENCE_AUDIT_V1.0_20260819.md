# N3-W FC-1 Exact-source Equivalence Audit

Date: 2026-08-19  
Status: `FC1=PASS`  
Mode: source/GitHub read-only audit; this document commit is documentation-only.

## 1. Binding and scope

This audit implements FC-1 from `N3W_FINAL_PRODUCT_VALIDATION_AND_ROUTE_C_CLOSURE_PLAN_V1.0_20260819.md`.

Frozen inputs:

```text
R5_VALIDATED_HEAD=d5ccf7f53e450eb46a2285b0c6d8f41403ea0df7
R5_VALIDATED_TREE=6c0e0eedefb701e8f9ad0cc1214c2e95cd78febb
PHASE5_FINAL_HEAD=147ead29b5963150e17d582492b148854b0250b4
PHASE5_FINAL_TREE=9c62b1c87549120e0b8f53b0bd949ce5b00a0569
R5_TO_PHASE5_STATUS=ahead
R5_TO_PHASE5_AHEAD_BY=42
R5_TO_PHASE5_BEHIND_BY=0
R5_TO_PHASE5_MERGE_BASE=d5ccf7f53e450eb46a2285b0c6d8f41403ea0df7
```

This audit does **not** replay R5 and makes no new physical PASS claim. No board/USB/serial/Flash/erase/RF action and no production Broker/Manager/Home Assistant mutation is part of FC-1.

FC-0 remains authoritative: R5 proved controlled Direct MQTT/application-uplink failure -> discovery -> authenticated ESP-NOW Relay -> Manager canonical ingress -> Direct recovery while STA association remained. R5 does not prove real STA Wi-Fi loss/recovery or the three-board scenarios reserved for FC-4.

## 2. Audit method

The audit used the exact GitHub compare `d5cc... -> 147ead...`, then resolved the actual selected source surfaces rather than treating every historical/lab file as active product code.

The checks were:

1. compare all changed paths between the two exact commits;
2. bind normal F1.0 RC2 and the R5 physical N3-W generic harness at both commits;
3. bind simplified-runtime source files by exact blob SHA where unchanged;
4. inspect the only changed active-core radio files and separate preserved active control/path behavior from retired reliability machinery;
5. verify legacy radio is explicit opt-in and not selected by normal RC2 or the Phase-4/R5 generic physical harness;
6. bind Manager relay decoding/router/canonical-ingress sources needed to interpret the final E2E path;
7. classify intended host-side Phase-5 promotion/retirement changes separately and carry them into FC-4 physical scope instead of retroactively extending R5.

## 3. Actual dependency surfaces

### 3.1 Normal F1.0 RC2

The following blobs are identical at R5 and Phase-5 final:

```text
firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml
  R5 = final = dcb7127f4abd32a7176472871bff3923ce022a1d

firmware/esphome_rc/f1_0_rc2/packages/core.yml
  R5 = final = b35ca36bcabbe4e1e0a55725738a4c1c52b0ba01
```

Normal RC2 does not select `greenhouse_n3w_product_core`, `greenhouse_n3w_product_runtime`, or `GREENHOUSE_N3W_ENABLE_LEGACY_RADIO`. Phase-5 regression guards explicitly assert those absences.

Result:

```text
NORMAL_RC2_CONFIG_DELTA=0
NORMAL_RC2_LEGACY_RADIO_SELECTED=false
NORMAL_RC2_RETIRED_PRODUCT_RUNTIME_SELECTED=false
```

### 3.2 R5 physical N3-W generic harness

The actual R5/Phase-4 generic physical harness is also byte-identical:

```text
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
  R5 = final = 6e40a198c5fcc9f445668da6e78f455a390e991f
```

It selects only `greenhouse_n3w_core`, with `phase4_source_harness: true` and `phase4_product_runtime: true`. It does not select the legacy radio component and does not define the legacy radio build flag.

The component code-generation contract is byte-identical:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/__init__.py
  R5 = final = b388d64fc2b4898d61e5339a94db52e17512bac4
```

Therefore the correct R5-to-final firmware comparison is the selected simplified product runtime inside `greenhouse_n3w_core`, not the retired S2/S3/S5 product-runtime lineages.

## 4. Exact-source equivalence matrix

The following selected implementation blobs are identical at R5 and Phase-5 final:

| Concern | Path | Exact blob SHA | Result |
|---|---|---|---|
| Simplified product component / Wi-Fi integration | `greenhouse_n3w_core/n3w_simple_product_component.cpp` | `c52c3d5167dcbe881eba34d093e0184b4827194b` | EXACT |
| Simplified product runtime | `greenhouse_n3w_core/n3w_simple_product_runtime.cpp` | `fad10a5e6484d09ec91447720ef3bae5853846a9` | EXACT |
| Simplified product runtime interface | `greenhouse_n3w_core/n3w_simple_product_runtime.h` | `c3b37e3c5cd520a17c694364124d5da4d2910f6f` | EXACT |
| Peer discovery/auth runtime | `greenhouse_n3w_core/n3w_simple_runtime.cpp` | `48f3dc08be2901fda39d0e18b4ced0d896b6aa5c` | EXACT |
| Long-lived peer/LMK crypto | `greenhouse_n3w_core/n3w_simple_crypto.cpp` | `af1734b404da07117eba37ee607b90fd7dd485d5` | EXACT |
| Simplified NVS credential persistence | `greenhouse_n3w_core/n3w_esp32_simple_nvs.cpp` | `f487c7f65ad58958382a08107aa131ecbbfe614b` | EXACT |
| N3W2 compact telemetry | `greenhouse_n3w_core/n3w_compact_telemetry.cpp` | `4e524b3c65defe6188dfe03d70d5e03bf85a16f3` | EXACT |
| BOOT_ID / sequence core | `greenhouse_n3w_core/n3w_core.cpp` | `5b3e322b6865bce631ee0bf77056b23ad3526e6a` | EXACT |
| ESP-NOW driver | `greenhouse_n3w_core/n3w_espnow_driver.cpp` | `2018ce5d395d24c0225f2560f055ad1f1f6780db` | EXACT |

Consequences of those exact bindings:

- Wi-Fi and MQTT readiness remain separate signals. While STA is associated, ESP-NOW shares the observed Wi-Fi channel; same-channel requests are idempotent and different-channel movement is rejected. Once STA is disconnected, discovery may control the radio channel.
- Direct -> Discovery -> RelayActive -> Direct state transitions in `SimpleProductRuntime` are unchanged.
- relay discovery/challenge/accept and encrypted-peer installation are unchanged.
- long-lived LMK derivation is unchanged.
- persisted `system_id`, `node_id`, peer-trust generation, system peer key, N3-W key epoch and application key format are unchanged.
- the N3W2 single-frame/AAD binding to `system_id`, `node_id`, `key_epoch`, `boot_id`, and `seq` is unchanged.
- BOOT_ID session persistence and per-session SEQ monotonic behavior are unchanged.

These are source-equivalence conclusions only; real Wi-Fi loss/recovery remains a new FC-4 physical requirement under the corrected FC-0 contract.

## 5. Changed radio core: active behavior versus retired reliability stack

The selected files `n3w_radio.h` and `n3w_radio.cpp` do change between R5 and Phase-5 final.

R5 active radio contained both:

- discovery/probe/authentication, channel scan and local path state-machine helpers used by the simplified runtime; and
- historical fragmentation/receipt/reassembly/retry/cache machinery (`DataFragment`, `ReceiptAckPacket`, `RelayReassembler`, `RetryPolicy`, `ChildRelayCache`, etc.).

Phase-5 final keeps the first group in the active radio surface and moves the second group behind the explicit `GREENHOUSE_N3W_ENABLE_LEGACY_RADIO` regression gate / legacy component.

The preserved active implementations were checked source-for-source for:

```text
valid_radio_channel
same_mac
RelayPeerBinding / ChildPeerBinding validation
discovery advertisement encode/decode/match
authenticated probe encode/decode
authenticated probe-ack encode/decode
ChannelScanPlan configure/current/advance
LocalPathPolicy validity
LocalPathController Direct -> Discovery
LocalPathController Discovery -> RelayActive
LocalPathController RelayActive -> Discovery
LocalPathController Relay/Discovery -> Direct recovery
```

No behavior-changing difference was found in the active subset consumed by `n3w_simple_product_runtime.*`; changes there are formatting/placement around removal of the retired reliability implementation.

The Phase-5 firmware source-contract regression additionally asserts that the active header/source no longer expose fragmentation/receipt/retry/cache machinery while preserving `MacAddress`, `LinkKey`, `ChannelScanPlan`, `LocalPathController`, channel validation and MAC comparison.

Classification:

```text
RADIO_ACTIVE_SIMPLIFIED_BEHAVIOR_DELTA=0
RADIO_RETIRED_RELIABILITY_EXTRACTION=LEGACY_UNSELECTED
```

## 6. Firmware delta classification

Every firmware-side changed path in the exact compare is classified below.

| Changed area | Classification | FC-1 conclusion |
|---|---|---|
| `greenhouse_n3w_core/n3w_radio.{h,cpp}` | `LEGACY_UNSELECTED` extraction plus source-equivalent active subset | No unexplained simplified-runtime behavior delta |
| `greenhouse_n3w_core/n3w_radio_legacy.h` | `LEGACY_UNSELECTED` | Explicit regression compatibility only |
| `greenhouse_n3w_legacy_radio/*` | `LEGACY_UNSELECTED` / `BUILD_ONLY` | Separate opt-in component; not selected by normal RC2 or R5 generic physical harness |
| `greenhouse_n3w_p5_lab/__init__.py` | `BUILD_ONLY` / `LEGACY_UNSELECTED` | Historical P5 regression packaging only |
| `board_lab/n3w_product_completion_s5/{child,relay}.yml` | `BUILD_ONLY` / `LEGACY_UNSELECTED` | Frozen S5 regression targets explicitly opt in; not the final active factory target |
| removed `greenhouse_n3w_product_core/*` | `DELETED_RETIRED_CODE` | Not selected by R5 generic physical harness / normal RC2 |
| removed `greenhouse_n3w_product_runtime/*` | `DELETED_RETIRED_CODE` | Not selected by R5 generic physical harness / normal RC2 |

Repository changes outside firmware are classified as follows:

- retired N3-W/P5 workflows and one-shot historical gates: `CI_ONLY` / retired authority cleanup;
- replacement regression tests: `TEST_ONLY`;
- handoff/known-failure updates: `DOC_ONLY`;
- Manager runtime promotion, automatic NODE_ID admin contract, and removal of PATH/finite-grant legacy authority: explained host-side `ACTIVE_BEHAVIOR`, not a hidden firmware delta, and therefore explicitly included in FC-4 final E2E coverage.

## 7. Manager relay/canonical equivalence relevant to FC-4

The core Direct/Relay/canonical processing used to interpret R5 evidence remains byte-identical:

```text
n3w_multi_ingress_router.py
  R5 = final = 1ff292318e734e11c724ac736bf8ecb56aeb92d1

n3w_phase4_isolated_harness.py
  R5 = final = ddb5398e1a6ea103b55dc2e4813840b8183a29ab

n3w_compact_relay.py
  R5 = final = fa28c9e9d7eb31f643e596b5451c26b826f9cddc

n3w_canonical_ingress.py
  R5 = final = 9b51b1847d24becae23014c4b9a9cd3760f63b0c

n3w_auto_node_id.py
  R5 = final = 6d1e9fa70b0cf16c656a525d8ce10def84ccbca0
```

Phase 5 adds `n3w_manager_runtime_wiring.py` and promotes the already validated simplified Direct/Relay service behind normal Manager startup when N3-W is enabled. It also disables superseded legacy pairing intake and removes PATH/finite-grant authority from the active wiring. This is an intentional, explained host-side active delta and is **not** retroactively claimed as physically proven by R5.

Accordingly FC-4 must exercise the final promoted Manager path, not only the historical isolated harness.

## 8. Final FC-4 physical scope derived by FC-1

FC-4 must use one newly materialized exact final artifact and a fresh independent physical authorization. It must cover at least:

1. A/B/C using the same generic final factory image;
2. independent first-use registration and Manager-assigned stable NODE_ID values;
3. Direct telemetry through the final promoted Manager path;
4. B actual STA Wi-Fi loss with Direct IP unavailable, then automatic discovery, authenticated peer/LMK establishment, encrypted ESP-NOW Relay and canonical Manager ingress;
5. actual B Wi-Fi recovery and automatic return to Direct with BOOT_ID/SEQ/canonical continuity;
6. late C join without A/B reflash, re-pair, or manual C information on existing nodes;
7. C actual Wi-Fi loss and automatic legitimate Relay selection;
8. simultaneous B/C Relay with identity/BOOT_ID/SEQ/canonical isolation;
9. multi-Relay failover without Manager PATH instruction, manual relay selection, re-pairing, or finite peer grant;
10. final A/B/C return to Direct with no duplicate device, stale relay ownership or canonical rollback;
11. explicit absence of PATH authority, finite gateway/peer grants and manual peer configuration in the exercised product route.

This scope is additive to the corrected R5 claim boundary; it does not require or permit replay of R5.

## 9. FC-1 terminal decision

The exact-source audit found no unexplained active firmware behavior difference between the R5 validated simplified product path and the Phase-5 final simplified product path. The only selected core file family that changed (`n3w_radio.*`) preserves the simplified active control/path behavior and removes historical reliability machinery into an explicit unselected legacy boundary. All other critical simplified firmware mechanisms listed by the FC-1 plan are exact-blob identical.

The intended Manager promotion/retirement changes are explained and are carried forward into the new FC-4 physical scope rather than being attributed to R5.

```text
FC1_EXACT_SOURCE_AUDIT=PASS
FIRMWARE_DELTA_FULLY_CLASSIFIED=true
UNEXPLAINED_ACTIVE_DELTA=0
FINAL_PHYSICAL_SCOPE_DEFINED=true
R5_REPLAY_REQUIRED=false
R5_REPLAY_ALLOWED=false
FC2_STARTED=false
FC3_STARTED=false
FC4_AUTHORIZED=false
```

FC-2 remains a separate next stage. No final firmware artifact is frozen by this document.
