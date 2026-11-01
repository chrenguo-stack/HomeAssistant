# N3-W KF-089 Local Chat ↔ GitHub Alignment Archive — 2026-09-07

Status: `PUBLIC_SAFE_ALIGNMENT_ARCHIVE`  
Purpose: durable reconciliation of the 2026-09-06/07 local ChatGPT + Codex execution history with GitHub source, PRs, CI, physical-test closures and the current forward route.

This document exists because several KF-089 physical/test facts were first carried in local conversation/Codex closure blocks. It archives the reusable, public-safe facts needed to continue development without depending on chat history.

Sensitive material is intentionally excluded. Raw NVS, credentials, Setup Secrets, private node identities, keys and private packet/session evidence remain private/local.

## 1. Alignment authority

Repository:

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=483ff1c662dc74d6e12529e27a69819e68160f9e
ALIGNMENT_BASE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
```

Active design authority:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current concise state authority created by this alignment:

`docs/development/N3W_CURRENT_STATE.md`

The older `N3W_CURRENT_DEVELOPMENT_PROGRESS_ALIGNMENT_20260906.md` remains historical. It predates the merged KF-089 source repair, the 2026-09-07 physical retests, the legacy-app purge and PR #370 observability merge.

## 2. Why KF-089 changed direction

The active product-direction decision separated two distinct problems:

1. **required Wi-Fi-disconnected Relay discovery** — a provisioned node must be able to start N3-W and autonomously search for a trusted Relay when Direct Wi-Fi is unavailable;
2. **associated off-channel lifecycle** — keeping an AP association while temporarily operating off-channel, which remains optional/separate and is not a prerequisite for disconnected failover.

The project therefore stopped treating full associated off-channel lifecycle closure as a prerequisite for repairing KF-089.

The minimal product objective became:

```text
PROVISIONED
-> bounded Direct grace
-> if Direct unavailable, legitimate DISCOVERY startup
-> bounded channel sweep
-> trusted Relay acquisition
-> Relay telemetry
-> later Direct recovery
```

A full custom `WIFI_OWNS_RADIO` / `ESPNOW_OWNS_RADIO` subsystem remains deferred unless later physical evidence proves it necessary.

## 3. PR #369 — KF-089 startup architecture source repair

PR:

`https://github.com/chrenguo-stack/HomeAssistant/pull/369`

Frozen source authority:

```text
PR_369_HEAD=2bf4324c7ebdb06532d54ccacd9d9dfdfb327f86
PR_369_MERGE_COMMIT=d27c4aec59c75ebcc18b19cb2cc9d0562d0b7e08
```

Primary code/test files changed:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.h
tests/n3w_phase4/n3w_phase4_runtime_host_test.cpp
tests/n3w_phase4/test_n3w_disconnected_startup_contract.py
tests/n3w_phase4/test_phase4_source_contract.py
```

Core behavior introduced:

- remove live Wi-Fi association as a hard runtime-start prerequisite;
- preserve durable runtime state + MQTT configuration as startup prerequisites;
- add `SimpleProductStartMode::{DIRECT,DISCOVERY}`;
- give Direct Wi-Fi a 15 s startup grace window;
- allow DISCOVERY startup with direct channel `0`;
- allow discovery to begin from the allowed channel set when no Direct channel is known;
- use allowed channels `{1,6,11}` with 250 ms dwell in the current policy;
- keep associated-STA channel mutation forbidden;
- while disconnected, use the radio channel setter and rebind the ESP-NOW broadcast peer;
- bound retry timing after discovery channel-set failure;
- retain a later Direct-recovery path.

Frozen startup constants after PR #369:

```text
INITIAL_DIRECT_GRACE_MS=15000
ALLOWED_DISCOVERY_CHANNELS=1,6,11
SCAN_DWELL_MS=250
RELAY_ADVERTISEMENT_INTERVAL_MS=2000
CHALLENGE_TIMEOUT_MS=1500
DIRECT=0
DISCOVERY=1
RELAY_ACTIVE=2
```

Source/compile status at that boundary:

```text
KF089_ROOT_CAUSE_SOURCE_REPAIR=MERGED_TO_MAIN
HOST_REGRESSION=PASS
ESP32C6_CHILD_COMPILE=PASS
ESP32C6_RELAY_COMPILE=PASS
ESP32C6_PHASE4_HARNESS_COMPILE=PASS
KF089_PHYSICAL_CLOSURE=NOT_YET_PROVEN
```

## 4. First exact-main KF-089 artifact

Build-only preclaim from `d27c4aec...`:

```text
SOURCE_COMMIT=d27c4aec59c75ebcc18b19cb2cc9d0562d0b7e08
SOURCE_TREE=1b971d76e96b722d8b76c3b9c1eafbbae491b293
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
ESPRESSIF32_VERSION=55.3.38
TOOLCHAIN=riscv32-esp-elf 14.2.0+20260121
TARGET_YAML=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_CONFIG_VALID=PASS
ESPHOME_COMPILE=PASS
```

Important artifact hashes:

```text
firmware.bin
size=1109312
sha256=11f21dc41cf91affb5a93bd0a302909b7694a00393b6636ac5f2c5f5a4b7bc05

firmware.factory.bin
size=1174848
sha256=b10232e2b891ee9b02bb391cf3032bed79876ef11d1da164cf5dabfeb595ea64

partitions.bin
sha256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

flash_args
sha256=78ed19de41bcae32ab9fcd79964cc3b52ba0f9565261362a7433275bc60cd97a
```

Partition layout:

```text
otadata  0x9000   0x2000
app0     0x10000  0x3C0000
app1     0x3D0000 0x3C0000
nvs      0x790000 0x70000
```

The physical update was deliberately application-only. Factory image, bootloader and partition-table writes were forbidden.

## 5. Two-board exact-main application refresh and Direct baseline

The initial two-board refresh used the safe inactive-slot procedure rather than assuming `app0` was the active physical slot:

```text
read physical partition table
-> read current OTA slot
-> write exact firmware.bin to opposite inactive slot
-> exact-size readback SHA256
-> switch otadata to the verified slot
```

Both boards were initially on slot 0 and were written to slot 1 at `0x3D0000`.

Frozen result:

```text
BOARD_A_FLASH_VERIFY=PASS
BOARD_A_RUNTIME_ACTIVE_MODE_DIRECT=true
BOARD_A_DIRECT_TELEMETRY_COUNT=10
BOARD_A_T1_CORRELATED_COUNT=10
BOARD_A_T1_REJECTED_COUNT=0
BOARD_A_PAIRING_RETRIGGERED=false
BOARD_A_EXISTING_IDENTITY_PRESERVED=true

BOARD_B_FLASH_VERIFY=PASS
BOARD_B_RUNTIME_ACTIVE_MODE_DIRECT=true
BOARD_B_DIRECT_TELEMETRY_COUNT=9
BOARD_B_T1_CORRELATED_COUNT=9
BOARD_B_T1_REJECTED_COUNT=0
BOARD_B_PAIRING_RETRIGGERED=false
BOARD_B_EXISTING_IDENTITY_PRESERVED=true

NVS_MUTATION=false
TWO_BOARD_EXACT_MAIN_DIRECT_BASELINE=PASS
```

This proved the repaired exact-main image still preserved normal Direct behavior and existing provisioned identity.

## 6. First battery cold-boot attempt — correctly classified inconclusive

Board A remained Direct/Relay-capable. Board B was disconnected from USB, powered off, moved to a physical candidate and battery cold-booted.

Observed public-safe result:

```text
BOARD_A_PRETEST_DIRECT_BASELINE=PASS
BOARD_A_WIFI_CONNECTED=true
BOARD_A_MQTT_CONNECTED=true
BOARD_A_RELAY_CAPABLE=true

BOARD_B_COLD_BOOT_OPERATOR_CONFIRMED=true
BOARD_B_POWER_SOURCE=BATTERY
BOARD_B_USB_CONNECTED=false

BOARD_B_NEW_BOOT_SESSION_OBSERVED=false
BOARD_B_NEW_BOOT_DIRECT_ACCEPTED_COUNT=0
BOARD_B_NEW_BOOT_RELAY_ACCEPTED_COUNT=0

BOARD_A_DIRECT_TELEMETRY_ACCEPTED_DURING_TEST=60
BOARD_A_DIRECT_PATH_STABLE=true

KF089_PHYSICAL_RESULT=INCONCLUSIVE
FAILURE_CLASS=ZONE_OR_OBSERVABILITY_NOT_PROVEN
```

The key adjudication rule was preserved: **no new Board B telemetry at all is not enough to call KF-089 FAIL**, because a battery-only remote node does not independently prove new application boot, Direct unavailability and A↔B ESP-NOW reachability.

`ZONE_C_VALID` should therefore be read as `UNKNOWN`, not as a proven false zone.

## 7. Post-test boot-state forensic

The board was entered directly into ROM Download Mode without an intervening application boot, and the product boot-session state was read from NVS read-only.

Recovered:

```text
PRETEST_BOARD_B_SESSION=15870905187090026227
EXPECTED_TARGET_SESSION=15870905187090026228
POSTTEST_BOARD_B_BOOT_STATE=15870905187090026229
SESSION_DELTA=2
```

The result proved at least two post-pretest runtime-ready boot-session allocations but did not uniquely attribute which one belonged to the target battery session.

Frozen forensic classification:

```text
TARGET_COLD_BOOT_RUNTIME_READY_DURABLE_EVIDENCE=AMBIGUOUS
TARGET_SESSION_ATTRIBUTION=AMBIGUOUS
MULTIPLE_POSTTEST_BOOT_SESSIONS=true
POSTTEST_FORENSIC_RESULT=INCONCLUSIVE
```

This evidence is historical and was superseded as the active baseline after the application-slot cleanup described below.

## 8. Historical YAML/application image interference concern

During the local review, an important alternative explanation was raised: much older hardware-test application images had previously been flashed while testing sensors, battery handling, LCD12864, RS485/EWM communication and related hardware.

One historical class of firmware contained battery/low-power logic capable of changing Wi-Fi/peripheral behavior. Another historical EWM communication image changed UART/GPIO behavior. The exact old YAML source is not reproduced in this public archive because the relevant engineering fact is the **possible stale application image**, not any historical credentials/configuration embedded in those files.

Even though the observed 120–300 s KF-089 window did not cleanly match the long low-battery protection timing of the historical battery test logic, keeping unknown old application code in the alternate OTA slot was an unnecessary physical variable.

The route was therefore intentionally reset at the application-partition level without erasing product NVS.

## 9. Legacy application purge + dual-slot normalization

Both complete application partitions on Board A and Board B were erased and rewritten with the same exact `d27c4aec...` application image.

Frozen result:

```text
BOARD_A_APP0_IMAGE_SHA256=11f21dc41cf91affb5a93bd0a302909b7694a00393b6636ac5f2c5f5a4b7bc05
BOARD_A_APP1_IMAGE_SHA256=11f21dc41cf91affb5a93bd0a302909b7694a00393b6636ac5f2c5f5a4b7bc05
BOARD_A_APP0_TAIL_ERASED=true
BOARD_A_APP1_TAIL_ERASED=true
BOARD_A_LEGACY_APP_PURGED=PASS
BOARD_A_DIRECT_BASELINE=PASS

BOARD_B_APP0_IMAGE_SHA256=11f21dc41cf91affb5a93bd0a302909b7694a00393b6636ac5f2c5f5a4b7bc05
BOARD_B_APP1_IMAGE_SHA256=11f21dc41cf91affb5a93bd0a302909b7694a00393b6636ac5f2c5f5a4b7bc05
BOARD_B_APP0_TAIL_ERASED=true
BOARD_B_APP1_TAIL_ERASED=true
BOARD_B_LEGACY_APP_PURGED=PASS
BOARD_B_DIRECT_BASELINE=PASS

OLD_APPLICATION_CODE_REMAINS_BOARD_A=false
OLD_APPLICATION_CODE_REMAINS_BOARD_B=false
PAIRING_RETRIGGERED=false
NVS_MUTATION=false
LEGACY_APP_PURGE_AND_NORMALIZATION=PASS
```

Fresh Board B baseline after this normalization:

```text
NEW_KF089_BASELINE_BOARD_B_SESSION=15870905187090026231
```

From this point forward, stale historical YAML/application code is not an accepted explanation for KF-089 behavior unless new evidence contradicts the purge/readback result.

## 10. Clean baseline battery cold-boot retest — startup gate physically proven

A second cold-boot test was executed from the clean dual-slot baseline.

Frozen result:

```text
PRETEST_BOARD_B_SESSION=15870905187090026231
EXPECTED_TARGET_SESSION=15870905187090026232

TARGET_SESSION_DIRECT_COUNT=0
TARGET_SESSION_RELAY_ACCEPTED_COUNT=0
TARGET_SESSION_RELAY_REJECTED_COUNT=0

POSTTEST_BOARD_B_BOOT_STATE=15870905187090026232
POSTTEST_SESSION_DELTA=1

TARGET_SESSION_ATTRIBUTION=PASS
TARGET_RUNTIME_READY_PHYSICAL=PASS
TARGET_WINDOW_MULTIPLE_RUNTIME_BOOTS=false
UNEXPECTED_TARGET_REBOOT=false

BOARD_A_DIRECT_ACCEPTED_DURING_TEST=36
BOARD_A_DIRECT_PATH_STABLE=true

ZONE_C_VALID=UNKNOWN

KF089_STARTUP_GATE_REPAIR=PASS
AUTONOMOUS_RELAY_DISCOVERY=NOT_PROVEN
AUTHENTICATED_RELAY_ACQUISITION=NOT_PROVEN
END_TO_END_RELAY_TELEMETRY=NOT_PROVEN

KF089_PHYSICAL_RESULT=PARTIAL_PASS
FAILURE_CLASS=DISCOVERY_OR_RF_PATH_NOT_OBSERVED
```

This is the most important physical adjudication of the day:

- the exact repaired application cold-booted in the target battery-only test;
- it reached the N3-W runtime-ready / telemetry-identity stage;
- it created exactly one expected new durable boot session;
- it did not unexpectedly reboot;
- no Direct telemetry reached T1;
- no Relay telemetry reached T1.

Therefore the original runtime-startup gate defect is physically closed as a sub-defect, but the full KF-089 Relay-acquisition requirement remains open.

## 11. Why observability became the next source task

After the clean retest, the remaining failure window was too wide:

```text
runtime ready
-> discovery scan/channel switch
-> Relay advertisement reception
-> challenge
-> accept
-> encrypted peer installation
-> RELAY_ACTIVE
-> Relay telemetry
```

The current source discarded `runtime_.tick()` return values and lacked durable battery-only evidence for the individual handshake stages. A new blind distance/location test would therefore have repeated the same ambiguity.

The chosen correction was **lab-only observability**, not a product-path behavior change.

## 12. PR #370 — Relay discovery observability

PR:

`https://github.com/chrenguo-stack/HomeAssistant/pull/370`

Frozen authority:

```text
BASE=d27c4aec59c75ebcc18b19cb2cc9d0562d0b7e08
FINAL_HEAD=54a83bac9ae4a413b01f71e02be4e899dd12fb64
MERGE_COMMIT=483ff1c662dc74d6e12529e27a69819e68160f9e
MERGE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
```

Final changed-file set includes:

```text
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
firmware/esphome_rc/components/greenhouse_n3w_core/__init__.py
firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_lab_diagnostics.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_lab_diagnostics.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.h
tests/n3w_kf089/n3w_lab_diagnostics_host_test.cpp
tests/n3w_kf089/test_relay_discovery_observability_contract.py
tests/n3w_phase4/n3w_phase4_runtime_host_test.cpp
tools/n3w_read_diag_snapshot.py
```

### 12.1 Initial review blockers found before merge

The first PR #370 implementation was not merged immediately. Review found four evidence-contract blockers:

1. persistent snapshot was not bound to the physical boot session;
2. actual scan channel could be overwritten by the Direct hint and ordinary 250 ms scanning could force excessive NVS persistence;
3. `scan_attempts/successes/failures` could be polluted by generic Direct channel operations;
4. the post-test host reader only parsed an already-extracted blob and did not provide the complete ROM/NVS read-only path.

The branch was repaired before merge.

### 12.2 Repaired schema-v2 contract

The repaired implementation added:

- explicit `phase4_lab_diagnostics` config, default false;
- explicit enable only in `n3w_phase4_physical/generic.yml`;
- `boot_session` and `snapshot_uptime_ms` binding;
- separate `direct_channel_hint` and actual `working_channel`;
- true discovery scan instrumentation inside runtime discovery control flow;
- separate generic channel-set counters;
- 5 s bounded persistence for ordinary scan/channel events;
- behavioral 180 s / 720-scan persistence test;
- Direct-start scan-counter delta = 0;
- read-only ROM NVS capture + `gh_n3w_diag/snapshot` sanitized extraction utility.

Frozen review-repair evidence:

```text
DIRECT_START_SCAN_COUNTER_DELTA=0
SIMULATED_DISCOVERY_DURATION_MS=180000
SIMULATED_SCAN_ATTEMPTS=720
SIMULATED_PERSIST_COUNT=36
PERSISTENCE_RATE_BOUND=PASS
POSTTEST_ROM_READ_CONTRACT=PASS
POSTTEST_SANITIZED_EXTRACTION=PASS
PRODUCT_BEHAVIOR_CHANGED=false
```

### 12.3 Final advertisement-side observability blocker

A final review found one remaining ambiguity: if Board B scanned successfully but saw zero discovery frames, there was no durable proof that Board A actually attempted/submitted Relay advertisements during the target window.

The final PR head therefore added:

```text
relay_advertisement_attempts
relay_advertisement_submit_success
relay_advertisement_submit_failure
broadcast_completion_count
broadcast_completion_success
broadcast_completion_failure
```

The persistent schema was bumped to:

```text
DIAGNOSTIC_SCHEMA_VERSION=3
```

The asynchronous ESP-NOW send-completion callback is accumulated with atomic counters and drained/persisted from the normal component loop, preserving thread-safety and the persistence-rate bound.

Final behavior-neutral validation included:

```text
SIMULATED_ADVERTISEMENT_DURATION_MS=20000
SIMULATED_ADVERTISEMENT_ATTEMPTS=10
PERSISTENCE_RATE_BOUND=PASS
ADVERTISEMENT_BEHAVIORAL_TEST=PASS
DIAGNOSTICS_BEHAVIOR_NEUTRAL_TEST=PASS
PRODUCT_BEHAVIOR_CHANGED=false
```

All associated PR-head workflows completed successfully before merge.

## 13. Current lab diagnostic contract after PR #370

```text
DIAGNOSTIC_SCHEMA_VERSION=3
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PRODUCT_TARGET_DIAGNOSTICS_ENABLED=false
PHASE4_GENERIC_DIAGNOSTICS_ENABLED=true
```

The snapshot/serial diagnostic surface can distinguish the following classes in a future physical test:

```text
A advertisement attempt/submission failure
A lower-level broadcast completion failure
B scan/channel-set failure
A->B discovery receive absence/rejection
B challenge submission
A challenge receive/verification
A accept submission
B accept receive/verification
B encrypted peer install
RELAY_ACTIVE transition
Relay telemetry send result
```

This instrumentation is evidence-only. It does not change path thresholds, scan dwell, allowed-channel set, advertisement interval, handshake crypto, peer trust, Wi-Fi association logic or radio-ownership architecture.

## 14. Exact-main observability artifact built after merge

Build task:

`N3W_KF089_OBSERVABILITY_EXACT_MAIN_ARTIFACT_BUILD_PRECLAIM_20260907_01`

Frozen source/toolchain:

```text
SOURCE_COMMIT=483ff1c662dc74d6e12529e27a69819e68160f9e
SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
ESPRESSIF32_VERSION=55.03.38
TOOLCHAIN_VERSION=riscv32-esp-elf 14.2.0+20260121
TARGET_CONFIG_VALID=PASS
ESPHOME_COMPILE=PASS
LAB_DIAGNOSTICS_IN_BUILT_TARGET=PASS
```

New artifact authority:

```text
firmware.bin
size=1114144
sha256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d

firmware.ota.bin
size=1114144
sha256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d

firmware.factory.bin
size=1179680
sha256=df63670dcf9b771fccda9e1881057d347d7b3c2adebc0ea2d5c8a70c6dace33a

firmware.elf
size=17629172
sha256=f25f2f38a8a7113436c76c6bda935825c0b8818e65fba306955682078100bd40

bootloader.bin
size=22576
sha256=571d5af5ece56d2fa2fd63ea05622b936c1cd1e49a1e71f69b8b40c00d36989b

partitions.bin
sha256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

ota_data_initial.bin
sha256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

flash_args
sha256=78ed19de41bcae32ab9fcd79964cc3b52ba0f9565261362a7433275bc60cd97a
```

The new artifact is intentionally different from the first KF-089 artifact:

```text
OLD_KF089_FIRMWARE_SHA256=11f21dc41cf91affb5a93bd0a302909b7694a00393b6636ac5f2c5f5a4b7bc05
NEW_OBSERVABILITY_FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
OLD_NEW_ARTIFACT_DISTINCT=true
```

Partition compatibility remains PASS.

## 15. Current physical-board state versus repository state

This distinction is important at the end of the alignment:

```text
GITHUB_CURRENT_MAIN=483ff1c662dc74d6e12529e27a69819e68160f9e
NEW_OBSERVABILITY_ARTIFACT=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
NEW_ARTIFACT_BUILD=PASS
NEW_ARTIFACT_FLASH_TO_A_B=NOT_YET_EXECUTED_IN_CURRENT_ROUTE
```

The last physically proven dual-slot board normalization used the prior repaired firmware `11f21dc4...`.

Therefore it is incorrect to claim that the physical boards are already running current main merely because PR #370 is merged and the new artifact has been built.

## 16. Next safe entry point

```text
NEXT_GATE=KF089_OBSERVABILITY_TWO_BOARD_APP_REFRESH_AND_DIRECT_DIAGNOSTIC_BASELINE
```

This gate must:

1. freshly bind Board A/B identity without relying on historical `/dev/cu.usbmodem*` numbering;
2. rebind physical partition layout;
3. refresh application slots to `efae17f4...` using inactive-first + exact readback verification;
4. normalize both app slots to the same new exact-main image;
5. preserve product provisioning NVS;
6. establish Direct telemetry baseline on both boards;
7. prove schema-v3 diagnostics on real hardware;
8. prove Direct mode has zero discovery-scan count;
9. prove Relay-advertisement submission and broadcast completion are healthy before the remote battery test;
10. freeze a fresh Board B Direct boot session and prove diagnostic `boot_session` binding.

Only after that should the route enter:

`KF089_OBSERVABILITY_BATTERY_COLD_BOOT_RELAY_DIAGNOSTIC_EXECUTION`.

## 17. NVS mutation semantics after PR #370

A prior test constraint used the blanket statement `NVS_MUTATION=false`. That is no longer accurate for the Phase 4 lab target because the observability implementation intentionally persists a bounded diagnostic snapshot.

Correct boundary from PR #370 onward:

```text
LAB_DIAGNOSTIC_NVS_MUTATION=true
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
PRODUCT_NVS_MUTATION=false
PAIRING_MUTATION=false
CREDENTIAL_MUTATION=false
APPLICATION_KEY_MUTATION=false
PEER_TRUST_MUTATION=false
```

Manual writes to the diagnostic namespace are not required; normal lab firmware produces the snapshot.

## 18. Known-failure alignment

The central `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` already contains KF-087/KF-088/KF-089 numbering.

No new KF number is created by this alignment.

KF-089 remains overall `OPEN` because its product requirement is broader than the now-closed startup-gate sub-defect:

```text
KF089_STARTUP_GATE_REPAIR=PASS
AUTONOMOUS_RELAY_DISCOVERY=NOT_PROVEN
AUTHENTICATED_RELAY_ACQUISITION=NOT_PROVEN
END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

The current `DISCOVERY_OR_RF_PATH_NOT_OBSERVED` result is not assigned a new known-failure ID because a unique product root cause has not yet been established. PR #370 exists specifically to produce the evidence needed for that classification.

KF-088 also remains relevant: USB/host-controlled reset can transiently enter ROM Download Mode when GPIO9 is sampled low. Physical tasks must continue to distinguish ROM mode from application/runtime failure and avoid treating USB port names as stable board identity.

## 19. Test-log / closure index archived from local conversation

The following local/Codex closure boundaries are now represented durably by this document:

```text
N3W_KF089_EXACT_MAIN_ARTIFACT_BUILD_PRECLAIM_20260907_01
N3W_KF089_TWO_BOARD_PHYSICAL_PRECLAIM_20260907_01
N3W_KF089_TWO_BOARD_APP_ONLY_FLASH_AND_DIRECT_BASELINE_20260907_01
N3W_KF089_BOARD_B_COLD_BOOT_NO_WIFI_AUTONOMOUS_RELAY_ACQUISITION_20260907_01
N3W_KF089_INCONCLUSIVE_POSTTEST_BOOTSTATE_FORENSIC_20260907_01
N3W_KF089_TWO_BOARD_LEGACY_APP_PURGE_AND_EXACT_MAIN_NORMALIZATION_20260907_01
N3W_KF089_CLEAN_BASELINE_COLD_BOOT_RELAY_RETEST_20260907_01
N3W_KF089_RELAY_DISCOVERY_OBSERVABILITY_REPAIR_20260907_01
N3W_KF089_PR370_OBSERVABILITY_REVIEW_BLOCKER_REPAIR_20260907_01
N3W_KF089_PR370_ADVERTISEMENT_OBSERVABILITY_FINAL_REPAIR_20260907_01
N3W_KF089_OBSERVABILITY_EXACT_MAIN_ARTIFACT_BUILD_PRECLAIM_20260907_01
```

The closure blocks themselves were public-safe summaries; this archive retains their decisive fields rather than copying private raw evidence.

## 20. Source-change archive index

The source-level changes that matter to the active route are durably represented in GitHub itself:

```text
PR #369
n3w: start provisioned runtime without live Wi-Fi
merge=d27c4aec59c75ebcc18b19cb2cc9d0562d0b7e08

PR #370
fix(n3w): repair relay discovery observability
merge=483ff1c662dc74d6e12529e27a69819e68160f9e
```

PR #369 is product behavior/source repair.  
PR #370 is lab-only diagnostic/evidence infrastructure and explicitly preserves product behavior.

The code, host tests, compile coverage, review comments and CI history for both PRs remain in GitHub and are the exact source-change authority. This document is a route/evidence index, not a substitute for the commits.

## 21. Private evidence boundary

No private secret material is copied into this archive.

Public-safe binding for the local physical-session evidence used by the 2026-09-07 closures:

```text
PRIVATE_EVIDENCE_PRESENT=true
PRIVATE_EVIDENCE_PATH_CLASS=LOCAL_CODEX_PHYSICAL_SESSION_EVIDENCE
PRIVATE_EVIDENCE_SHA256=NOT_EXPORTED_TO_CHAT
PRIVATE_EVIDENCE_SIZE=NOT_EXPORTED_TO_CHAT
PRIVATE_EVIDENCE_CREATED_AT=2026-09-07
PRIVATE_EVIDENCE_PURPOSE=KF089_BOARD_BINDING_FLASH_READBACK_BOOTSTATE_AND_RELAY_PHYSICAL_DIAGNOSTICS
SECRET_VALUES_INCLUDED=false
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
```

Where the local raw files are later retained long-term, their private hashes/paths may be added to a private evidence manifest. The public engineering claims above do not require exposing those values.

## 22. Development artifact archive audit

This alignment applies `docs/development/development-artifact-archive-rules.md` to the knowledge available in the conversation and current GitHub state.

```text
ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=not-required
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=true
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=true
UNTRACKED_CRITICAL_ARTIFACTS=UNKNOWN_LOCAL_HOST_NOT_SCANNED_BY_GITHUB_ALIGNMENT
UNARCHIVED_CRITICAL_KNOWLEDGE=0
ALIGNMENT_BASE_MAIN=483ff1c662dc74d6e12529e27a69819e68160f9e
ALIGNMENT_BASE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
NEXT_SAFE_ENTRY_POINT=KF089_OBSERVABILITY_TWO_BOARD_APP_REFRESH_AND_DIRECT_DIAGNOSTIC_BASELINE
```

`UNTRACKED_CRITICAL_ARTIFACTS` is intentionally not asserted as zero because this GitHub-side alignment cannot inspect every local `/private/tmp`, Downloads or ignored worktree path. The critical *knowledge* carried by the current local conversation has been reduced to durable public-safe source/test/doc/hash/state records here.

## 23. Alignment conclusion

After this archive is merged, a new chat can recover the active route from GitHub without relying on the local transcript:

```text
main=483ff1c662dc74d6e12529e27a69819e68160f9e
KF089 startup gate physical repair=PASS
legacy app/YAML slot interference=eliminated
full Relay acquisition=OPEN
PR370 observability=MERGED
new physical artifact=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
new artifact flashed to boards=NOT_YET_PROVEN
next gate=KF089_OBSERVABILITY_TWO_BOARD_APP_REFRESH_AND_DIRECT_DIAGNOSTIC_BASELINE
```

This is the current public-safe handoff point.
