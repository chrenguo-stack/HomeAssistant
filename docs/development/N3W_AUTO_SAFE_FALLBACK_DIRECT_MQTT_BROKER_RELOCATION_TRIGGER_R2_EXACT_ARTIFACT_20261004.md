# N3-W Auto Safe Fallback Direct MQTT Broker Relocation Trigger R2 — Exact Artifact Binding — 2026-10-04

Status: `EXACT_ARTIFACT_FROZEN`

## Frozen source

```text
SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
SOURCE_REPAIR_R2=true
```

The R2 source closes the fail-closed rollback gap for standalone Direct Broker relocation and keeps standalone relocation mutually exclusive with phased Direct recovery.

## Workflow binding

```text
BUILD_BRANCH=build/n3w-auto-safe-fallback-f1rc2-67a0460-r2-artifact-20261004
WORKFLOW_TRIGGER_COMMIT=045245ed85c33ba46e404d1fdcc3594cda88dcc0
WORKFLOW_RUN_ID=37204582611
WORKFLOW_RESULT=SUCCESS
```

The build workflow explicitly checked out `SOURCE_HEAD` above and verified the exact source tree and critical target/config blobs before compiling.

## Artifact

```text
ARTIFACT_ID=11303803442
ARTIFACT_NAME=n3w-auto-safe-fallback-f1rc2-67a0460-r2-exact-source
ARTIFACT_OUTER_SIZE=4332304
ARTIFACT_OUTER_SHA256=be604ae4bba09d1a675017518a8847fdd655f2f5bb64dca200bb6e8d49378582
RELEASE_ZIP_SIZE=4331737
RELEASE_ZIP_SHA256=ae80eeb6a36d250ecdd3123f8ac084e40d7f4a47f7331b91a1d8b91818c74e7c
```

## Manifest binding

```text
BINDING_SCHEMA=N3W_PRODUCTION_EXACT_ARTIFACT_V1
TARGET_BLOB_SHA=32a2b3cb29be4e1bce46807d8825b6a4c37999ec
TELEMETRY_BRIDGE_BLOB_SHA=ce16f2389d146f9b25e95cbb628547e11ce36bd6
TRANSPORT_BLOB_SHA=aa39d4b083f2db1b30a76efb1afef156db355a35
PRODUCT_CORE_INIT_BLOB_SHA=75949b916144383ae57ebe90ece41e9f248b8cbe
PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
BINARY_DEHARNESS_PROOF=PASS
DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS
PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false
```

## Binary hashes

```text
FIRMWARE_BIN_SIZE=1409904
FIRMWARE_BIN_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
FIRMWARE_OTA_BIN_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
FIRMWARE_FACTORY_BIN_SHA256=ab47b2604eb2af6000e3bea05a88c791dcda84bcfd7eeb56619172d75576a295
BOOTLOADER_BIN_SHA256=99662c9b4bc1ac74a6e38ac95c9340b72d0f08e43fdf546c080e56c976cfc3e5
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
FLASH_ARGS_SHA256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

The partition table and initial OTA data hashes are unchanged from the previously bound Gate F artifact. Only the application binary changed for the R2 source repair.

## Physical validation boundary

```text
EXACT_ARTIFACT_FROZEN=true
BOARD_WRITE=false
T1_MUTATION=false
STALE_BROKER_PHYSICAL_ORACLE_PRESERVED=true
PHYSICAL_REVALIDATION_COMPLETE=false
MERGE=false
```

Next gate: Board B read-only preflight, then minimal application/OTA-state write only after identity and flash-safety checks pass.
