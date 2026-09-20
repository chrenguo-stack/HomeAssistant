# N3-W PR #437 177468e Board B exact-artifact write

Status: PREPARED_FOR_AUTHORIZED_OPERATOR_EXECUTION

## Authority

```text
TASK=N3W_PR437_BOARD_B_EXACT_ARTIFACT_WRITE_20260920_01
PRODUCT_SOURCE_HEAD=177468e290a207f2fb7f6c554aedf60b61373b4d
PRODUCT_SOURCE_TREE=a50ff98887b14b70cf9d278c6f8b7edf536eae88

ARTIFACT_ID=10607030747
ARTIFACT_NAME=n3w-pr437-boardb-exact-source
ARTIFACT_ZIP_SHA256=371d4369b791df527c595bc43ac203487f18a000b47ec73692d728ce58483dd8
APPLICATION_SHA256=74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

WRITE_CONFIRMATION=N3W_PR437_177468E_BOARD_B_WRITE_AUTHORIZED
```

## Required preflight

The write executor accepts only the fresh PASS closure produced by:

```text
SCHEMA=n3w.kf096.pr437-177468e.boardb-preflight/1
AUTOMATED_IDENTITY_MATCH=true
IDENTITY_OVERRIDE_PERMITTED=false
PREFLIGHT_MAX_AGE_SECONDS=900
```

The 2026-09-19 identity override is not reusable.

## Mutation scope

Only these two ranges may be written:

```text
0x9000  <- ota_data_initial.bin
0x10000 <- firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
T1_MUTATION=false
```

Before mutation, the executor re-checks Board B identity, ESP32-C6, 8MB flash, security state and partition-table hash. It then atomically consumes the preflight closure before issuing write-flash.

After writing, it reads back the exact two written byte ranges and requires their SHA-256 hashes to equal the frozen artifact hashes.

## Artifact download

From repository root:

```bash
gh api repos/chrenguo-stack/HomeAssistant/actions/artifacts/10607030747/zip \
  > /tmp/n3w-pr437-boardb-exact-source.zip
```

The executor independently checks ZIP size/hash, exact member set, all inner hashes, and MANIFEST content before any write.

## Execution

```bash
python3 /tmp/n3w-pr437-177468e-boardb-write.py \
  --port /dev/cu.usbmodem14101 \
  --artifact-zip /tmp/n3w-pr437-boardb-exact-source.zip \
  --preflight /tmp/n3w-pr437-177468e-boardb-preflight.json \
  --output /tmp/n3w-pr437-177468e-boardb-write.json \
  --confirm N3W_PR437_177468E_BOARD_B_WRITE_AUTHORIZED
```

If the preflight is older than 15 minutes, the executor stops before write; rerun the read-only preflight rather than bypassing the freshness guard.

## Boundary after PASS

A PASS proves exact application/otadata write plus byte-for-byte readback. It does not prove Direct/Relay runtime behavior. Application serial remains unopened; T1 remains unchanged. The next gate is post-write Manager-visible Direct baseline.
