# N3-W PR #437 Board A same-artifact role-swap preparation — 2026-09-22

Status: `BOARD_A_SAME_ARTIFACT_WRITE_PASS; ROLE_SWAP_PHYSICAL_PENDING`

Canonical board-write procedure: `docs/development/N3W_ESP32C6_EXACT_ARTIFACT_BOARD_WRITE_RUNBOOK_V1.0_20260922.md`

## Purpose

Synchronize Board A to the exact physical-harness firmware already used for the final Board B PR #437 physical runs, then test the opposite role assignment:

```text
Board B = Direct / Gateway
Board A = Relay Child after Direct loss
```

This route is independent of Gateway Selection V1 source implementation. It tests the current PR #437 role symmetry with the exact already-validated harness artifact.

## Exact firmware authority

```text
SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_BLOB=37654481747b21ca51ccecc246bf84ca437ab7a9

WORKFLOW_RUN_ID=35553142523
ARTIFACT_ID=10619047221
ARTIFACT_NAME=n3w-pr437-4270f24-boardb-exact-source
ARTIFACT_ZIP_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895

APPLICATION_SIZE=1145984
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Fresh GitHub metadata on 2026-09-22 shows artifact `10619047221` is still available and expires at `2026-09-28T02:12:40Z`.

Despite the historical artifact name containing `boardb`, the payload was compiled from the generic Phase4 physical target. The board-specific identity and credentials remain in product NVS and are not replaced by this write route.

## Write scope

Only:

```text
0x9000  <- ota_data_initial.bin
0x10000 <- firmware.bin
```

Explicitly excluded:

```text
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

Post-write application readback must match the exact firmware artifact hash and the partition table must remain unchanged. Post-boot OTA-data byte equality is explicitly not a valid verifier because the firmware legitimately updates the OTA-data partition after boot.

## Target-safety sequence

The current Board-B writer cannot be reused unchanged because it deliberately hard-binds the historical Board B identity.

The Board-A executor therefore uses:

1. fresh ROM identity read;
2. ESP32-C6 / 8 MB / security-state / partition-table verification;
3. emit the public-safe fresh silicon hash;
4. explicit operator confirmation that the connected physical target is Board A;
5. require the exact fresh silicon hash to be echoed into the write command;
6. fresh identity re-read immediately before mutation;
7. single-use authorization claim;
8. minimal app + OTA-data write;
9. exact application + partition-table post-write readback; post-boot OTA-data is observation-only and is never compared byte-for-byte with the initial OTA-data image.

The current application contents are deliberately not read or used to distinguish Board A from Board B. Unknown or older pre-write application state is allowed.

A preflight older than 15 minutes cannot be used for the write.

## Role-swap physical sequence after write

Do not move both boards simultaneously.

### P0 — post-write Board A baseline

- boot Board A normally;
- prove Manager-visible Board A Direct telemetry is advancing;
- prove Board B remains healthy;
- keep both in Wi-Fi/Direct coverage long enough to establish a clean baseline.

### P1 — establish Board B as the Gateway side first

- place/keep Board B in the previously validated Direct/Wi-Fi position;
- require stable Board B Direct telemetry before moving Board A;
- no Board B flash, reset, NVS change, or T1 mutation.

### P2 — move Board A to the previous Relay-child position

Keep Board A in the same boot session:

```text
NO_REBOOT=true
NO_POWER_CYCLE=true
NO_USB_REQUIRED=true
```

Move Board A from Direct coverage to the prior remote/no-Wi-Fi test position.

Acceptance:

```text
BOARD_B_SOURCE=direct
BOARD_A_TRANSITION_TO_RELAY=PASS
BOARD_A_RELAY_GATEWAY=BOARD_B
BOARD_A_BOOT_SESSION_UNCHANGED=true
```

Direct -> Relay boundary loss remains allowed by the frozen Option-B contract and must be reported rather than hidden.

### P3 — Relay steady-state

Observe 600 seconds after stable Relay entry.

Required:

```text
BOARD_A_RELAY_600S=PASS
BOARD_A_STEADY_RELAY_MISSING_SEQUENCE_COUNT=0
BOARD_B_DIRECT_REMAINS_HEALTHY=true
MANAGER_RUNTIME_STABLE=true
```

### P4 — optional same-boot return

After the role-symmetry result is captured, moving Board A back into Direct coverage may be used to re-prove Relay -> Direct failback, but it is a separate acceptance sub-step and must not be used to hide a failed B-as-Gateway/A-as-Child result.

## Current stop point

Board A exact-artifact synchronization has completed successfully.

```text
BOARD_A_PREFLIGHT=PASS
BOARD_A_WRITE=PASS
APPLICATION_POSTWRITE_READBACK=PASS
PARTITION_TABLE_POSTWRITE_READBACK=PASS
PRODUCT_NVS_WRITE=false
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
ROLE_SWAP_PHYSICAL_ACCEPTANCE=NOT_YET_EXECUTED
NEXT_ONE_GATE=N3W_PR437_BOARD_A_POSTWRITE_DIRECT_BASELINE_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```


## 2026-09-22 preflight correction

The first fresh Board-A preflight reached the silicon identity guard and stopped before any flash mutation.

```text
ARTIFACT_SIZE_MATCH=PASS
ARTIFACT_SHA256_MATCH=PASS
BOARD_A_PREFLIGHT=STOP
STOP_REASON=historical Board-B hash used as hard exclusion
FLASH_WRITE=false
PRODUCT_NVS_WRITE=false
AUTHORIZATION_CONSUMED=false
```

The stop itself was safe. The admission rule was then reviewed and corrected.

Current rule:

```text
PREWRITE_APPLICATION_HASH_REQUIRED=false
PREWRITE_APPLICATION_HASH_USED_FOR_BOARD_IDENTITY=false
HISTORICAL_BOARD_B_HASH_AS_HARD_EXCLUSION=false
FRESH_ROM_SILICON_HASH_CAPTURE_REQUIRED=true
OPERATOR_TARGET_CONFIRMATION_REQUIRED=true
WRITE_MUST_ECHO_PREFLIGHT_HARDWARE_HASH=true
FRESH_SILICON_REREAD_BEFORE_WRITE=true
```

This supports both existing boards with arbitrary older firmware and future boards whose application region is initially unknown. A blank board with an incompatible or missing partition table remains a separate factory-provisioning case.


## 2026-09-22 Board A write closure

The corrected preflight and one-shot write completed against the operator-confirmed Board A.

```text
BOARD_A_PREFLIGHT=PASS
FRESH_SILICON_IDENTITY_BOUND=true
HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee

BOARD_A_WRITE=PASS
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
APPLICATION_POSTWRITE_READBACK=PASS

OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
OTADATA_POSTBOOT_SHA256=8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
OTADATA_POSTBOOT_BYTE_EQUALITY_ORACLE=false

PARTITION_TABLE_POSTWRITE_READBACK=PASS
PRODUCT_NVS_WRITE=false

AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

The differing post-boot OTA-data hash is expected and is not a failure signal. The application readback and unchanged partition-table readback are the exact post-write byte-level acceptance oracles.

This closes only the Board A firmware synchronization step. It does not yet prove Board A Direct runtime liveness or the B-as-Gateway/A-as-Child role-swap path.

```text
NEXT_ONE_GATE=N3W_PR437_BOARD_A_POSTWRITE_DIRECT_BASELINE_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```
